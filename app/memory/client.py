"""AgentArts Memory Service client wrapper for DeepAgent.

Provides asynchronous interfaces for session management, writing conversation
messages, and retrieving cross-session long-term memories.
"""

from __future__ import annotations

import json
import logging
import os
import uuid
from typing import Any

from agentarts.sdk.memory import (
    AsyncMemoryClient,
    MemoryListFilter,
    MemorySearchFilter,
    TextMessage,
)
from agentarts.sdk.service.http_client import MemoryAPIException

from app.config import settings

logger = logging.getLogger(__name__)


class AgentArtsMemoryService:
    """Service wrapping AgentArts Memory SDK for persistent agent memory."""

    def __init__(self) -> None:
        self._client: AsyncMemoryClient | None = None
        self._known_sessions: set[str] = set()

    def is_enabled(self) -> bool:
        """Check whether AgentArts Memory service is configured and enabled."""
        return bool(
            settings.AGENTARTS_MEMORY_SPACE_ID and settings.AGENTARTS_MEMORY_API_KEY
        )

    def _get_client(self) -> AsyncMemoryClient:
        """Get or lazily instantiate AsyncMemoryClient."""
        if self._client is None:
            self._client = AsyncMemoryClient(
                region_name=settings.AGENTARTS_REGION,
                api_key=settings.AGENTARTS_MEMORY_API_KEY,
            )
        return self._client

    @staticmethod
    def to_session_id(thread_id: str) -> str:
        """Convert a thread_id to a deterministic valid UUID session_id."""
        try:
            uuid.UUID(thread_id)
            return thread_id
        except ValueError:
            return str(uuid.uuid5(uuid.NAMESPACE_DNS, thread_id))

    async def ensure_session(self, thread_id: str, user_id: str) -> str:
        """Ensure the session exists on the memory data plane."""
        session_id = self.to_session_id(thread_id)
        if session_id in self._known_sessions:
            return session_id

        client = self._get_client()
        try:
            await client.create_memory_session(
                space_id=settings.AGENTARTS_MEMORY_SPACE_ID,
                id=session_id,
                actor_id=user_id,
                assistant_id=settings.DEFAULT_AGENT_ID,
            )
            logger.info(
                "Created AgentArts Memory session '%s' for user '%s' in space '%s'",
                session_id,
                user_id,
                settings.AGENTARTS_MEMORY_SPACE_ID,
            )
        except Exception as exc:
            logger.debug(
                "Session existence or create notice for session_id '%s': %s",
                session_id,
                exc,
            )

        self._known_sessions.add(session_id)
        return session_id

    async def add_messages(
        self,
        thread_id: str,
        user_id: str,
        messages: list[TextMessage],
    ) -> None:
        """Add user and assistant messages to the memory service session."""
        if not self.is_enabled() or not messages:
            return

        session_id = await self.ensure_session(thread_id, user_id)
        client = self._get_client()

        try:
            await client.add_messages(
                space_id=settings.AGENTARTS_MEMORY_SPACE_ID,
                session_id=session_id,
                messages=messages,
                is_force_extract=True,
            )
            logger.info(
                "Successfully added %d messages to AgentArts Memory (session_id=%s)",
                len(messages),
                session_id,
            )
        except MemoryAPIException as exc:
            if exc.status_code == 404:
                self._known_sessions.discard(session_id)
                session_id = await self.ensure_session(thread_id, user_id)
                await client.add_messages(
                    space_id=settings.AGENTARTS_MEMORY_SPACE_ID,
                    session_id=session_id,
                    messages=messages,
                    is_force_extract=True,
                )
            else:
                raise

    @staticmethod
    def _format_memory_record(content: str, strategy: str) -> str:
        """Format an individual memory record, parsing JSON structured preferences if present."""
        clean_content = content
        if clean_content.startswith("{") and clean_content.endswith("}"):
            try:
                data = json.loads(clean_content)
                if isinstance(data, dict):
                    parts = []
                    if "preference" in data:
                        parts.append(f"偏好: {data['preference']}")
                    if "fact" in data:
                        parts.append(f"事实: {data['fact']}")
                    if "context" in data:
                        parts.append(f"背景: {data['context']}")
                    if parts:
                        clean_content = "; ".join(parts)
            except Exception:
                pass
        tag = f"[{strategy}] " if strategy else ""
        return f"{tag}{clean_content}"

    async def retrieve_memories(
        self,
        user_id: str,
        query: str | None = None,
        top_k: int = 5,
    ) -> list[str]:
        """Retrieve relevant long-term memories for the given user.

        First attempts targeted semantic search if a query is provided;
        falls back to listing recent memories for the user if search yields no results.
        """
        if not self.is_enabled():
            return []

        client = self._get_client()
        space_id = settings.AGENTARTS_MEMORY_SPACE_ID
        memories: list[str] = []

        # 1. Targeted semantic search
        if query and query.strip():
            try:
                search_filter = MemorySearchFilter(
                    query=query.strip(),
                    actor_id=user_id,
                    top_k=top_k,
                    min_score=0.2,
                )
                response = await client.search_memories(
                    space_id=space_id,
                    filters=search_filter,
                )
                raw_results = (
                    getattr(response, "results", None)
                    or getattr(response, "records", None)
                    or []
                )
                for item in raw_results:
                    rec = item.get("record", item) if isinstance(item, dict) else item
                    content = getattr(rec, "content", None) or (
                        rec.get("content") if isinstance(rec, dict) else ""
                    )
                    strat = getattr(rec, "strategy_type", None) or (
                        rec.get("strategy_type") if isinstance(rec, dict) else ""
                    )
                    if content:
                        mem = self._format_memory_record(content, strat)
                        if mem not in memories:
                            memories.append(mem)
            except Exception as exc:
                logger.warning("AgentArts search_memories failed: %s", exc)

        # 2. Fallback to list_memories if semantic search has no results
        if not memories:
            try:
                list_filter = MemoryListFilter(
                    actor_id=user_id,
                    sort_by="created_at",
                    sort_order="desc",
                )
                list_resp = await client.list_memories(
                    space_id=space_id,
                    limit=top_k,
                    filters=list_filter,
                )
                items = getattr(list_resp, "items", None) or []
                for item in items:
                    content = getattr(item, "content", "")
                    strat = getattr(item, "strategy_type", "")
                    if content:
                        mem = self._format_memory_record(content, strat)
                        if mem not in memories:
                            memories.append(mem)
            except Exception as exc:
                logger.warning("AgentArts list_memories fallback failed: %s", exc)

        return memories[:top_k]

    @staticmethod
    def format_memory_context(memories: list[str]) -> str:
        """Format retrieved memories into a clean Markdown system prompt fragment."""
        if not memories:
            return ""
        bullet_list = "\n".join(f"- {m}" for m in memories)
        return (
            "<long_term_memory>\n"
            "以下是检索到的关于当前用户的长期记忆与历史偏好（跨会话沉淀），请在回答时作为上下文知识参考，自然融入对话中，无需刻意提及记忆系统的存在：\n"
            f"{bullet_list}\n"
            "</long_term_memory>"
        )


memory_service = AgentArtsMemoryService()
