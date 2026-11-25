"""Long-term memory middleware for DeepAgent backed by Huawei Cloud AgentArts Memory.

Requirements:
1. Writes ONLY user messages and model replies to the memory service (tool calls and results excluded).
2. At the start of a new thread, retrieves long-term memories for the user and injects them into the prompt.
3. Anchors strictly to the current turn's latest user message, capturing all model replies in that turn.
"""

from __future__ import annotations

import asyncio
from datetime import datetime, timezone
import logging
from collections.abc import Awaitable, Callable
from typing import Any

from deepagents.middleware._utils import append_to_system_message
from langchain.agents.middleware.types import (
    AgentMiddleware,
    ContextT,
    ModelRequest,
    ModelResponse,
    ResponseT,
)
from langchain_core.messages import AIMessage, HumanMessage
from langgraph.config import get_config
from langgraph.runtime import Runtime

from agentarts.sdk.memory import TextMessage

from app.config import settings
from app.models.thread import Thread
from .client import memory_service

logger = logging.getLogger(__name__)


def extract_text_content(content: Any) -> str:
    """Extract plain text string from str or multimodal message content blocks."""
    if isinstance(content, str):
        return content.strip()
    if isinstance(content, list):
        texts: list[str] = []
        for part in content:
            if isinstance(part, str):
                texts.append(part)
            elif isinstance(part, dict) and part.get("type") == "text":
                val = part.get("text", "")
                if val:
                    texts.append(val)
        return "\n".join(texts).strip()
    return str(content or "").strip()


class LongTermMemoryMiddleware(AgentMiddleware):
    """Middleware for AgentArts cross-session long-term memory management."""

    name: str = "LongTermMemoryMiddleware"

    async def abefore_agent(
        self, state: Any, runtime: Runtime[Any]
    ) -> dict[str, Any] | None:
        """At the start of a thread, retrieve relevant memories and cache into state."""
        if not memory_service.is_enabled():
            return None

        # Skip if long-term memory is already loaded in state (matches deepagents official pattern)
        if isinstance(state, dict):
            if state.get("long_term_memory") is not None:
                return None
        elif (
            hasattr(state, "long_term_memory")
            and getattr(state, "long_term_memory") is not None
        ):
            return None

        try:
            config = get_config()
            configurable = config.get("configurable", {})
            thread_id = configurable.get("thread_id")
            user_id = configurable.get("user_id", "default_user")
        except Exception as exc:
            logger.debug("Failed to get config in abefore_agent: %s", exc)
            return None

        if not thread_id:
            return None

        # Resolve user_id from thread record if present
        thread = await Thread.get_or_none(id=thread_id)
        if thread and thread.user_id:
            user_id = thread.user_id

        # Extract initial search query from first user message if available
        messages = []
        if isinstance(state, dict):
            messages = state.get("messages", [])
        elif hasattr(state, "messages"):
            messages = getattr(state, "messages", [])

        query: str | None = None
        for m in messages:
            if isinstance(m, HumanMessage):
                query = extract_text_content(m.content)
                if query:
                    break

        logger.info(
            "Thread '%s' starting for user '%s'. Retrieving long-term memories...",
            thread_id,
            user_id,
        )

        try:
            memories = await memory_service.retrieve_memories(
                user_id=user_id,
                query=query,
                top_k=settings.AGENTARTS_MEMORY_TOP_K,
            )
        except Exception as exc:
            logger.warning(
                "Failed to retrieve memories for user '%s': %s", user_id, exc
            )
            memories = []

        memory_text = memory_service.format_memory_context(memories) if memories else ""

        logger.info(
            "Retrieved %d memories for thread '%s' (injected=%s)",
            len(memories),
            thread_id,
            bool(memory_text),
        )

        return {
            "long_term_memory": memory_text,
        }

    def before_agent(self, state: Any, runtime: Runtime[Any]) -> dict[str, Any] | None:
        """Sync fallback for abefore_agent."""
        try:
            loop = asyncio.get_event_loop()
            if loop.is_running():
                return None
            return loop.run_until_complete(self.abefore_agent(state, runtime))
        except Exception:
            return None

    def modify_request(self, request: ModelRequest[ContextT]) -> ModelRequest[ContextT]:
        """Inject retrieved long-term memory into the model's system prompt."""
        memory_text = None
        if isinstance(request.state, dict):
            memory_text = request.state.get("long_term_memory")
        elif hasattr(request.state, "long_term_memory"):
            memory_text = getattr(request.state, "long_term_memory")

        if memory_text:
            new_system_message = append_to_system_message(
                request.system_message, memory_text
            )
            return request.override(system_message=new_system_message)
        return request

    def wrap_model_call(
        self,
        request: ModelRequest[ContextT],
        handler: Callable[[ModelRequest[ContextT]], ModelResponse[ResponseT]],
    ) -> ModelResponse[ResponseT]:
        """Sync wrapper injecting memory into system prompt."""
        modified_request = self.modify_request(request)
        return handler(modified_request)

    async def awrap_model_call(
        self,
        request: ModelRequest[ContextT],
        handler: Callable[
            [ModelRequest[ContextT]], Awaitable[ModelResponse[ResponseT]]
        ],
    ) -> ModelResponse[ResponseT]:
        """Async wrapper injecting memory into system prompt."""
        modified_request = self.modify_request(request)
        return await handler(modified_request)

    async def aafter_agent(
        self, state: Any, runtime: Runtime[Any]
    ) -> dict[str, Any] | None:
        """Write current turn's user message and all model replies to AgentArts Memory service."""
        if not memory_service.is_enabled():
            return None

        try:
            config = get_config()
            thread_id = config.get("configurable", {}).get("thread_id")
        except Exception as exc:
            logger.debug("Failed to get thread_id in aafter_agent: %s", exc)
            return None

        if not thread_id:
            return None

        thread = await Thread.get_or_none(id=thread_id)
        user_id = (
            thread.user_id
            if thread
            else config.get("configurable", {}).get("user_id", "default_user")
        )

        all_messages = []
        if isinstance(state, dict):
            all_messages = state.get("messages", [])
        elif hasattr(state, "messages"):
            all_messages = getattr(state, "messages", [])

        if not all_messages:
            return None

        # 1. Locate the latest HumanMessage (user input triggering the current turn)
        latest_human_idx = -1
        for i in range(len(all_messages) - 1, -1, -1):
            if isinstance(all_messages[i], HumanMessage):
                latest_human_idx = i
                break

        if latest_human_idx == -1:
            return None

        latest_human_msg = all_messages[latest_human_idx]
        turn_ai_messages = [
            m for m in all_messages[latest_human_idx + 1 :] if isinstance(m, AIMessage)
        ]

        messages_to_write: list[TextMessage] = []

        # Current turn user message
        user_text = extract_text_content(latest_human_msg.content)
        if user_text:
            messages_to_write.append(
                TextMessage(
                    role="user",
                    content=user_text,
                    actor_id=user_id,
                )
            )

        # Current turn model replies (supporting multiple model replies in one turn)
        for ai_msg in turn_ai_messages:
            ai_text = extract_text_content(ai_msg.content)
            if ai_text:
                messages_to_write.append(
                    TextMessage(
                        role="assistant",
                        content=ai_text,
                        assistant_id=settings.DEFAULT_AGENT_ID,
                    )
                )

        if messages_to_write:
            try:
                await memory_service.add_messages(
                    thread_id=thread_id,
                    user_id=user_id,
                    messages=messages_to_write,
                )
                logger.info(
                    "Persisted %d messages (current turn: 1 user, %d assistant replies) to AgentArts Memory for thread '%s'",
                    len(messages_to_write),
                    len(messages_to_write) - (1 if user_text else 0),
                    thread_id,
                )
            except Exception as exc:
                logger.error(
                    "Failed to persist conversation messages to AgentArts Memory: %s",
                    exc,
                )

        if thread:
            try:
                await Thread.filter(id=thread_id).update(
                    last_run_at=datetime.now(timezone.utc)
                )
            except Exception as db_exc:
                logger.debug("Failed to update thread last_run_at in DB: %s", db_exc)

        return None

    def after_agent(self, state: Any, runtime: Runtime[Any]) -> dict[str, Any] | None:
        """Sync fallback for aafter_agent."""
        try:
            loop = asyncio.get_event_loop()
            if loop.is_running():
                return None
            return loop.run_until_complete(self.aafter_agent(state, runtime))
        except Exception:
            return None
