"""Data models for AgentArts Sandbox SDK."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Union


@dataclass
class ExecutionResult:
    """Standard execution result, compatible with LangChain / BaseSandbox specification."""

    exit_code: int
    stdout: str = ""
    stderr: str = ""
    output: str = ""

    def __post_init__(self) -> None:
        if not self.output:
            self.output = self.stdout if self.stdout else self.stderr

    @property
    def is_success(self) -> bool:
        """Whether the command executed with exit code 0."""
        return self.exit_code == 0

    def to_dict(self) -> dict[str, Any]:
        """Convert result to dictionary."""
        return {
            "exit_code": self.exit_code,
            "stdout": self.stdout,
            "stderr": self.stderr,
            "output": self.output,
            "is_success": self.is_success,
        }


@dataclass
class FileItem:
    """File item specification for upload / download operations."""

    path: str
    content: Union[str, bytes]
    description: str = ""


SESSION_EXPIRED_MESSAGE = "当前环境已过期，环境里的所有文件和运行状态已经无法找回。请在新的环境中重新开始操作。"


class SandboxSessionExpiredError(Exception):
    """Raised when the AgentArts sandbox session has expired or terminated."""

    def __init__(self, message: str = SESSION_EXPIRED_MESSAGE) -> None:
        super().__init__(message)
        self.message = message
