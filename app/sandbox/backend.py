"""AgentArts Sandbox backend for DeepAgent.

Implements SandboxBackendProtocol (BaseSandbox) by routing calls to thread-scoped
AgentArtsSandbox instances managed by AgentArtsSessionManager.
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

from deepagents.backends.protocol import (
    ExecuteResponse,
    FileDownloadResponse,
    FileUploadResponse,
)
from deepagents.backends.sandbox import BaseSandbox
from langgraph.config import get_config

if TYPE_CHECKING:
    from .client import AgentArtsSandbox
    from .manager import AgentArtsSessionManager

logger = logging.getLogger(__name__)


class AgentArtsBackend(BaseSandbox):
    """DeepAgent Sandbox backend backed by Huawei Cloud AgentArts CodeInterpreter."""

    def __init__(self, manager: AgentArtsSessionManager) -> None:
        super().__init__()
        self.manager = manager

    def _get_current_sandbox_context(self) -> tuple[str, AgentArtsSandbox]:
        """Resolve current thread_id and sandbox instance."""
        try:
            config = get_config()
            thread_id = config.get("configurable", {}).get("thread_id")
        except Exception as exc:
            msg = f"Failed to retrieve thread_id from execution config: {exc}"
            raise ValueError(msg) from exc

        if not thread_id:
            msg = (
                "thread_id is required in execution config to route to sandbox session."
            )
            raise ValueError(msg)

        sandbox = self.manager.get(thread_id)
        if sandbox is None:
            msg = f"Sandbox session for thread '{thread_id}' is not initialized. It must be created in before_agent."
            raise RuntimeError(msg)

        return thread_id, sandbox

    @staticmethod
    def _to_abs_path(path: str, workspace_dir: str) -> str:
        """Normalize path to absolute path under the sandbox workspace (/home/user)."""
        clean = path.strip()
        if clean.startswith(workspace_dir):
            return clean
        return f"{workspace_dir}/{clean.lstrip('/')}"

    @property
    def id(self) -> str:
        return "agentarts-sandbox"

    def execute(
        self,
        command: str,
        *,
        timeout: int | None = None,
    ) -> ExecuteResponse:
        """Execute a shell command inside the thread-scoped sandbox."""
        _, sandbox = self._get_current_sandbox_context()
        result = sandbox.execute(command, timeout=timeout)
        return ExecuteResponse(
            output=result.output,
            exit_code=result.exit_code,
            truncated=False,
        )

    def upload_files(
        self,
        files: list[tuple[str, bytes]],
    ) -> list[FileUploadResponse]:
        """Upload multiple files to the sandbox workspace."""
        if not files:
            return []

        _, sandbox = self._get_current_sandbox_context()
        upload_dict = {
            self._to_abs_path(orig_path, sandbox.workspace_dir): content
            for orig_path, content in files
        }

        try:
            sandbox.upload_files(upload_dict)
            return [FileUploadResponse(path=path, error=None) for path, _ in files]
        except Exception as exc:
            return [FileUploadResponse(path=path, error=str(exc)) for path, _ in files]

    def download_files(
        self,
        paths: list[str],
    ) -> list[FileDownloadResponse]:
        """Download multiple files from the sandbox workspace."""
        if not paths:
            return []

        _, sandbox = self._get_current_sandbox_context()
        path_mapping = {self._to_abs_path(p, sandbox.workspace_dir): p for p in paths}

        downloaded = sandbox.download_files(list(path_mapping.keys()))
        normalized = {k.rstrip("/"): v for k, v in downloaded.items()}

        results: list[FileDownloadResponse] = []
        for abs_path, orig_path in path_mapping.items():
            clean_target = abs_path.rstrip("/")
            if clean_target in normalized:
                content = normalized[clean_target]
                content_bytes = (
                    content.encode("utf-8") if isinstance(content, str) else content
                )
                results.append(
                    FileDownloadResponse(
                        path=orig_path, content=content_bytes, error=None
                    )
                )
            else:
                results.append(
                    FileDownloadResponse(
                        path=orig_path, content=None, error="file_not_found"
                    )
                )
        return results
