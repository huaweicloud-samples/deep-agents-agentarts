"""Sandbox lifecycle middleware for DeepAgent.

Intercepts execution before agent starts to ensure the thread's sandbox session
is initialized, with thread_id mapped 1-to-1 to the AgentArts session_name.
Also intercepts tool calls to catch expired session errors and return clear notifications.
"""

from __future__ import annotations

import logging
from collections.abc import Awaitable, Callable
from typing import Any

from langchain.agents.middleware import AgentMiddleware, ToolCallRequest
from langchain_core.messages import ToolMessage
from langgraph.config import get_config
from langgraph.runtime import Runtime
from langgraph.types import Command

from .client import is_session_expired_error
from .manager import AgentArtsSessionManager
from .models import SESSION_EXPIRED_MESSAGE

logger = logging.getLogger(__name__)

# deepagents 沙箱与文件系统工具名称集合
SANDBOX_TOOL_NAMES = frozenset(
    {
        "execute",
        "read_file",
        "write_file",
        "edit_file",
        "delete",
        "ls",
        "glob",
        "grep",
    }
)


class SandboxLifecycleMiddleware(AgentMiddleware):
    """Middleware ensuring thread-scoped sandbox session is established before agent runs."""

    def __init__(self, manager: AgentArtsSessionManager) -> None:
        """Initialize middleware.

        Args:
            manager: AgentArtsSessionManager instance.
        """
        super().__init__()
        self.manager = manager

    def before_agent(self, state: Any, runtime: Runtime[Any]) -> dict[str, Any] | None:
        """Ensure thread sandbox session exists before agent runs."""
        try:
            config = get_config()
            thread_id = config.get("configurable", {}).get("thread_id")
        except Exception as exc:
            msg = f"Failed to retrieve thread_id from execution config: {exc}"
            raise ValueError(msg) from exc

        if not thread_id:
            msg = "thread_id is required in configurable to bind sandbox session."
            raise ValueError(msg)

        existing_session_id = None
        if isinstance(state, dict):
            existing_session_id = state.get("sandbox_session_id")
        elif hasattr(state, "sandbox_session_id"):
            existing_session_id = getattr(state, "sandbox_session_id")

        # Eagerly prepare or resume sandbox session
        sandbox = self.manager.get_or_create(thread_id, session_id=existing_session_id)
        session_id = getattr(sandbox.interpreter, "session_id", None)
        logger.info(
            "Sandbox session ready for thread '%s' (session_id=%s)",
            thread_id,
            session_id,
        )

        if session_id:
            import asyncio
            from app.models.thread import Thread

            async def _persist_session(tid: str, sid: str):
                try:
                    await Thread.filter(id=tid).update(sandbox_session_id=sid)
                except Exception as err:
                    logger.debug("Failed to update thread sandbox_session_id: %s", err)

            try:
                loop = asyncio.get_running_loop()
                loop.create_task(_persist_session(thread_id, session_id))
            except RuntimeError:
                pass

        return {
            "sandbox_session_id": session_id,
        }

    @staticmethod
    def _is_sandbox_tool(request: ToolCallRequest) -> bool:
        """Check if the tool call target is a sandbox tool."""
        tool_call = getattr(request, "tool_call", None)
        if isinstance(tool_call, dict):
            name = tool_call.get("name")
        else:
            name = getattr(tool_call, "name", None)
        return name in SANDBOX_TOOL_NAMES

    def _handle_tool_call_error(
        self, request: ToolCallRequest, exc: BaseException
    ) -> ToolMessage:
        """Handle expired session exception by recreating session and returning tool message.

        Only intercepts tools operating in the sandbox. Other tools' exceptions are re-raised.
        """
        if not self._is_sandbox_tool(request):
            raise exc

        if is_session_expired_error(exc):
            try:
                config = get_config()
                thread_id = config.get("configurable", {}).get("thread_id")
            except Exception:
                thread_id = None

            if thread_id:
                logger.warning(
                    "Sandbox session for thread '%s' expired during tool execution. Recreating...",
                    thread_id,
                )
                new_sandbox = self.manager.recreate(thread_id)
                new_session_id = getattr(new_sandbox.interpreter, "session_id", None)
                if new_session_id:
                    import asyncio
                    from app.models.thread import Thread

                    async def _persist(tid: str, sid: str):
                        try:
                            await Thread.filter(id=tid).update(sandbox_session_id=sid)
                        except Exception as err:
                            logger.debug(
                                "Failed to update thread sandbox_session_id on recreate: %s",
                                err,
                            )

                    try:
                        loop = asyncio.get_running_loop()
                        loop.create_task(_persist(thread_id, new_session_id))
                    except RuntimeError:
                        pass

            return ToolMessage(
                content=SESSION_EXPIRED_MESSAGE,
                name=request.tool_call["name"],
                tool_call_id=request.tool_call["id"],
                status="error",
            )
        raise exc

    def wrap_tool_call(
        self,
        request: ToolCallRequest,
        handler: Callable[[ToolCallRequest], ToolMessage | Command],
    ) -> ToolMessage | Command:
        """Intercept sync tool execution and handle expired session notifications."""
        if not self._is_sandbox_tool(request):
            return handler(request)

        try:
            return handler(request)
        except BaseException as exc:
            return self._handle_tool_call_error(request, exc)

    async def awrap_tool_call(
        self,
        request: ToolCallRequest,
        handler: Callable[[ToolCallRequest], Awaitable[ToolMessage | Command]],
    ) -> ToolMessage | Command:
        """Intercept async tool execution and handle expired session notifications."""
        if not self._is_sandbox_tool(request):
            return await handler(request)

        try:
            return await handler(request)
        except BaseException as exc:
            return self._handle_tool_call_error(request, exc)
