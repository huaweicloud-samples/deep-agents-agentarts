from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Optional, Union


@dataclass
class ThreadItem:
    id: str
    userId: str
    name: str
    agentId: str
    createdAt: str
    updatedAt: str
    archived: bool = False
    title: Optional[str] = None
    lastRunAt: Optional[str] = None
    sandboxSessionId: Optional[str] = None


@dataclass
class ThreadListResponse:
    threads: list[ThreadItem] = field(default_factory=list)
    nextCursor: Optional[str] = None
    joinCode: Optional[str] = None


@dataclass
class ThreadCreateRequest:
    id: Optional[str] = None
    name: Optional[str] = None
    title: Optional[str] = None
    agentId: Optional[str] = "sample_agent"

    def get_name(self) -> str:
        return self.name or self.title or "新对话"


@dataclass
class ThreadUpdateRequest:
    name: Optional[str] = None
    title: Optional[str] = None
    archived: Optional[bool] = None

    def get_name(self) -> Optional[str]:
        return self.name or self.title


@dataclass
class FunctionCallItem:
    name: str
    arguments: str


@dataclass
class ToolCallItem:
    id: str
    function: FunctionCallItem
    type: str = "function"


@dataclass
class UserMessageItem:
    id: str
    content: Union[str, list[Any]]
    role: str = "user"


@dataclass
class AssistantMessageItem:
    id: str
    content: Union[str, list[Any]] = ""
    role: str = "assistant"
    toolCalls: Optional[list[ToolCallItem]] = None


@dataclass
class ToolMessageItem:
    id: str
    content: Union[str, list[Any]]
    toolCallId: str
    role: str = "tool"


ThreadMessageItem = Union[UserMessageItem, AssistantMessageItem, ToolMessageItem]


@dataclass
class ThreadMessagesResponse:
    thread_id: str
    messages: list[Any] = field(default_factory=list)
