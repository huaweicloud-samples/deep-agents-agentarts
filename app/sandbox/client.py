"""AgentArts Sandbox client implementation.

Wraps Huawei Cloud AgentArts CodeInterpreter without rewriting underlying HTTP
transports or authentication, providing unified interfaces:
- execute
- upload_files
- download_files
"""

from __future__ import annotations

import base64
import logging
import os
from collections.abc import Sequence
from contextlib import AbstractContextManager
from typing import Any, Union

from agentarts.sdk.service.tools_http import ToolsAPIError
from agentarts.sdk.tools.code_interpreter import CodeInterpreter

from .models import (
    ExecutionResult,
    FileItem,
    SandboxSessionExpiredError,
    SESSION_EXPIRED_MESSAGE,
)

logger = logging.getLogger(__name__)

DEFAULT_WORKSPACE = "/home/user"


def is_session_expired_error(exc: BaseException) -> bool:
    """Determine whether an exception indicates the sandbox session has expired or closed."""
    if isinstance(exc, SandboxSessionExpiredError):
        return True
    if isinstance(exc, ToolsAPIError):
        return exc.status_code in (404, 409, 410)
    return False


class AgentArtsSandbox(AbstractContextManager["AgentArtsSandbox"]):
    """Lightweight sandbox adapter over AgentArts CodeInterpreter client.

    Provides three core capabilities:
        1. execute: Execute shell commands safely and reliably.
        2. upload_files: Bulk upload files (both text and binary).
        3. download_files: Bulk download files from the sandbox environment.
    """

    def __init__(
        self,
        interpreter: CodeInterpreter,
        code_interpreter_name: str | None = None,
        session_id: str | None = None,
        session_name: str | None = None,
        workspace_dir: str = DEFAULT_WORKSPACE,
        session_timeout: int | None = None,
        auto_stop_session: bool = True,
    ) -> None:
        """Initialize the sandbox adapter.

        Args:
            interpreter: Underlying initialized CodeInterpreter client instance.
            code_interpreter_name: Name of the target code interpreter instance in AgentArts.
                If not provided, reads from interpreter.code_interpreter_name or environment.
            session_id: Existing active session ID if already created.
            session_name: Custom session name (thread_id for 1-to-1 binding).
            workspace_dir: Sandbox base workspace directory (defaults to /home/user).
            session_timeout: Cloud session timeout in seconds.
            auto_stop_session: Whether to stop the session upon context exit.
        """
        self.interpreter = interpreter
        self.code_interpreter_name = (
            code_interpreter_name
            or interpreter.code_interpreter_name
            or os.getenv("AGENTARTS_CODE_INTERPRETER_NAME")
        )
        self.session_name = session_name
        self.workspace_dir = workspace_dir
        self.session_timeout = session_timeout
        self.auto_stop_session = auto_stop_session
        self._owned_session = False

        if session_id:
            self.interpreter.session_id = session_id

    # -------------------------------------------------------------------------
    # Session Lifecycle Management
    # -------------------------------------------------------------------------

    def is_alive(self) -> bool:
        """Check if the current session is active on the cloud plane."""
        if not self.interpreter.session_id or not self.code_interpreter_name:
            return False
        try:
            self.interpreter.get_session(
                code_interpreter_name=self.code_interpreter_name,
                session_id=self.interpreter.session_id,
            )
            return True
        except ToolsAPIError as exc:
            if exc.status_code == 404 or "not found" in str(exc).lower():
                return False
            logger.warning("Error checking session status: %s", exc)
            return False

    def ensure_session(self) -> str:
        """Ensure an active session exists; lazily initialize if needed.

        Returns:
            Active session ID.
        """
        if self.interpreter.session_id and self.interpreter.code_interpreter_name:
            if self.is_alive():
                return self.interpreter.session_id

        if not self.code_interpreter_name:
            msg = (
                "code_interpreter_name is required to start a sandbox session. "
                "Provide it in constructor or set AGENTARTS_CODE_INTERPRETER_NAME."
            )
            raise ValueError(msg)

        if not self.session_name:
            msg = "session_name is required to start a sandbox session. A valid thread_id must be provided."
            raise ValueError(msg)

        logger.info(
            "Starting session '%s' on interpreter '%s' (timeout=%s)",
            self.session_name,
            self.code_interpreter_name,
            self.session_timeout,
        )
        session_id = self.interpreter.start_session(
            code_interpreter_name=self.code_interpreter_name,
            session_name=self.session_name,
            session_timeout=self.session_timeout,
        )
        self.interpreter.session_id = session_id
        self._owned_session = True
        return session_id

    def stop(self) -> bool:
        """Stop current sandbox session if active."""
        if self.interpreter.session_id:
            logger.info("Stopping sandbox session %s", self.interpreter.session_id)
            try:
                self.interpreter.stop_session()
            except BaseException as exc:
                logger.warning(
                    "Ignored error while stopping session %s: %s",
                    self.interpreter.session_id,
                    exc,
                )
            self._owned_session = False
            return True
        return False

    def __enter__(self) -> AgentArtsSandbox:
        self.ensure_session()
        return self

    def __exit__(self, exc_type: Any, exc_val: Any, exc_tb: Any) -> None:
        if self.auto_stop_session and self._owned_session:
            self.stop()

    # -------------------------------------------------------------------------
    # Core Feature 1: execute
    # -------------------------------------------------------------------------

    def execute(self, command: str, timeout: int | None = None) -> ExecutionResult:
        """Execute a shell command inside the sandbox environment.

        Args:
            command: Shell command to execute.
            timeout: Optional execution timeout.

        Returns:
            ExecutionResult: Standardized result containing exit_code, stdout, and stderr.

        Raises:
            SandboxSessionExpiredError: When the cloud session is terminated or expired.
        """
        self.ensure_session()
        cmd_summary = (command[:100] + "...") if len(command) > 100 else command
        logger.info(
            "Executing command in sandbox: %s", cmd_summary.strip().replace("\n", " ")
        )

        try:
            response = self.interpreter.invoke(
                operate_type="execute_command",
                arguments={"command": command},
            )
            sc = response.get("result", {}).get("structured_content", {})
            exit_code = sc.get("exit_code", 0)
            stdout = sc.get("stdout", "")
            stderr = sc.get("stderr", "")

            out_summary = (
                (stdout[:100] + "...")
                if len(stdout) > 100
                else (stderr[:100] + "...") if stderr else ""
            )
            logger.info(
                "Command completed (exit_code=%d, stdout=%r)",
                exit_code,
                out_summary.strip().replace("\n", " "),
            )
            return ExecutionResult(exit_code=exit_code, stdout=stdout, stderr=stderr)

        except BaseException as exc:
            if is_session_expired_error(exc):
                logger.warning(
                    "Sandbox session expired during command execution: %s", exc
                )
                raise SandboxSessionExpiredError() from exc
            logger.exception("Sandbox command execution failed: %s", exc)
            return ExecutionResult(exit_code=1, stdout="", stderr=str(exc))

    # -------------------------------------------------------------------------
    # Core Feature 2: upload_files
    # -------------------------------------------------------------------------

    def upload_files(
        self,
        files: Union[
            dict[str, Union[str, bytes]],
            Sequence[Union[dict[str, Any], FileItem]],
        ],
    ) -> dict[str, Any]:
        """Bulk upload files into the sandbox environment.

        Args:
            files: Files to upload with absolute paths.

        Returns:
            Raw response dictionary from AgentArts data plane.

        Raises:
            SandboxSessionExpiredError: When the cloud session is terminated or expired.
        """
        self.ensure_session()

        items: list[dict[str, Any]] = []
        if isinstance(files, dict):
            for path, content in files.items():
                items.append({"path": path, "content": content})
        else:
            for item in files:
                if isinstance(item, FileItem):
                    items.append({"path": item.path, "content": item.content})
                elif isinstance(item, dict):
                    items.append({"path": item["path"], "content": item["content"]})

        clean_files = []
        for file_info in items:
            clean = file_info["path"].strip()
            clean_path = (
                clean
                if clean.startswith(self.workspace_dir)
                else f"{self.workspace_dir}/{clean.lstrip('/')}"
            )
            clean_files.append({"path": clean_path, "content": file_info["content"]})

        logger.info("Uploading %d file(s) to sandbox", len(clean_files))
        try:
            return self.interpreter.upload_files(clean_files)
        except BaseException as exc:
            if is_session_expired_error(exc):
                logger.warning("Sandbox session expired during file upload: %s", exc)
                raise SandboxSessionExpiredError() from exc
            raise

    def upload_file(
        self,
        path: str,
        content: Union[str, bytes],
        description: str = "",
    ) -> dict[str, Any]:
        """Convenience single-file upload helper."""
        return self.upload_files(
            [FileItem(path=path, content=content, description=description)]
        )

    # -------------------------------------------------------------------------
    # Core Feature 3: download_files
    # -------------------------------------------------------------------------

    def download_files(self, paths: list[str]) -> dict[str, Union[str, bytes]]:
        """Bulk download files from the sandbox environment.

        Args:
            paths: List of file paths to retrieve.

        Returns:
            Dictionary mapping absolute path -> content (str for text, bytes for binary).

        Raises:
            SandboxSessionExpiredError: When the cloud session is terminated or expired.
        """
        self.ensure_session()

        if not paths:
            return {}

        clean_paths: list[str] = []
        for p in paths:
            clean = p.strip()
            clean_paths.append(
                clean
                if clean.startswith(self.workspace_dir)
                else f"{self.workspace_dir}/{clean.lstrip('/')}"
            )

        logger.info("Downloading %d file(s) from sandbox", len(clean_paths))
        try:
            return self.interpreter.download_files(clean_paths)
        except ToolsAPIError as exc:
            if is_session_expired_error(exc):
                logger.warning("Sandbox session expired during file download: %s", exc)
                raise SandboxSessionExpiredError() from exc
            if "does not exist" in str(exc).lower():
                logger.warning("File download skipped, path not found: %s", exc)
                return {}
            raise
        except BaseException as exc:
            if is_session_expired_error(exc):
                logger.warning("Sandbox session expired during file download: %s", exc)
                raise SandboxSessionExpiredError() from exc
            raise

    def download_file(self, path: str) -> Union[str, bytes]:
        """Convenience single-file download helper."""
        clean = path.strip()
        if not clean.startswith("/"):
            clean = f"{self.workspace_dir}/{clean}"
        res = self.download_files([clean])
        if clean in res:
            return res[clean]
        msg = f"File not found in sandbox response: {path}"
        raise FileNotFoundError(msg)
