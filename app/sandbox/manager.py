"""Sandbox session manager for AgentArts CodeInterpreter.

Manages 1-to-1 binding between LangGraph thread_id and AgentArts sandbox sessions.
The thread_id is used directly as session_name on the cloud data plane.
"""

from __future__ import annotations

import logging
from typing import Dict

from agentarts.sdk.tools.code_interpreter import CodeInterpreter

from .client import DEFAULT_WORKSPACE, AgentArtsSandbox

logger = logging.getLogger(__name__)


class AgentArtsSessionManager:
    """Manages thread-scoped AgentArts sandbox instances."""

    def __init__(
        self,
        code_interpreter_name: str,
        region: str = "cn-southwest-2",
        data_endpoint: str | None = None,
        workspace_dir: str = DEFAULT_WORKSPACE,
        session_timeout: int = 3600,
    ) -> None:
        """Initialize session manager.

        Args:
            code_interpreter_name: Target code interpreter instance name.
            region: Huawei Cloud region.
            data_endpoint: AgentArts code interpreter data plane endpoint.
            workspace_dir: Working directory in sandbox.
            session_timeout: Cloud session timeout in seconds.
        """
        self.code_interpreter_name = code_interpreter_name
        self.region = region
        self.data_endpoint = data_endpoint
        self.workspace_dir = workspace_dir
        self.session_timeout = session_timeout
        self._sandboxes: Dict[str, AgentArtsSandbox] = {}

    def get_or_create(
        self,
        thread_id: str,
        session_id: str | None = None,
    ) -> AgentArtsSandbox:
        """Get existing sandbox or lazily create a new one using thread_id as session_name.

        Args:
            thread_id: Current conversation thread ID.
            session_id: Existing cloud session ID to resume if still active.

        Returns:
            Active AgentArtsSandbox instance.
        """
        if not thread_id:
            msg = "thread_id must not be empty to create or resolve a sandbox session."
            raise ValueError(msg)

        if thread_id in self._sandboxes:
            sandbox = self._sandboxes[thread_id]
            if sandbox.is_alive():
                return sandbox
            self._sandboxes.pop(thread_id, None)

        if session_id:
            logger.info(
                "Attempting to resume sandbox session '%s' for thread '%s'",
                session_id,
                thread_id,
            )
            interpreter = CodeInterpreter(
                region=self.region,
                data_endpoint=self.data_endpoint or None,
                auth_type="IAM",
            )
            sandbox = AgentArtsSandbox(
                interpreter=interpreter,
                code_interpreter_name=self.code_interpreter_name,
                session_id=session_id,
                session_name=thread_id,
                workspace_dir=self.workspace_dir,
                session_timeout=self.session_timeout,
                auto_stop_session=False,
            )
            if sandbox.is_alive():
                logger.info(
                    "Successfully resumed sandbox session '%s' for thread '%s'",
                    session_id,
                    thread_id,
                )
                self._sandboxes[thread_id] = sandbox
                return sandbox
            logger.warning(
                "Sandbox session '%s' is no longer active, launching fresh session",
                session_id,
            )

        logger.info(
            "Creating AgentArts sandbox session for thread '%s' (interpreter=%s)",
            thread_id,
            self.code_interpreter_name,
        )

        interpreter = CodeInterpreter(
            region=self.region,
            data_endpoint=self.data_endpoint or None,
            auth_type="IAM",
        )
        sandbox = AgentArtsSandbox(
            interpreter=interpreter,
            code_interpreter_name=self.code_interpreter_name,
            session_name=thread_id,
            workspace_dir=self.workspace_dir,
            session_timeout=self.session_timeout,
            auto_stop_session=False,
        )

        # Initialize session eagerly
        sandbox.ensure_session()
        self._sandboxes[thread_id] = sandbox
        return sandbox

    def get(self, thread_id: str) -> AgentArtsSandbox | None:
        """Get sandbox instance if cached."""
        return self._sandboxes.get(thread_id)

    def release(self, thread_id: str) -> bool:
        """Stop and remove sandbox session for a thread."""
        if sandbox := self._sandboxes.pop(thread_id, None):
            logger.info("Releasing sandbox session for thread '%s'", thread_id)
            return sandbox.stop()
        return False

    def recreate(self, thread_id: str) -> AgentArtsSandbox:
        """Dispose of expired sandbox session and immediately start a fresh one."""
        if not thread_id:
            msg = "thread_id must not be empty to recreate a sandbox session."
            raise ValueError(msg)

        logger.info("Recreating expired sandbox session for thread '%s'", thread_id)
        self.release(thread_id)
        return self.get_or_create(thread_id)


from app.config import settings

sandbox_manager = AgentArtsSessionManager(
    code_interpreter_name=settings.AGENTARTS_CODE_INTERPRETER_NAME,
    region=settings.AGENTARTS_REGION,
    data_endpoint=settings.AGENTARTS_CODEINTERPRETER_DATA_ENDPOINT,
    workspace_dir=settings.AGENTARTS_WORKSPACE,
    session_timeout=settings.AGENTARTS_SESSION_TIMEOUT,
)
