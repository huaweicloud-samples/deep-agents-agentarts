from __future__ import annotations

from dataclasses import asdict
from typing import Any, Optional
from tortoise import fields
from tortoise.models import Model

from app.schemas.thread import ThreadItem


class Thread(Model):
    id = fields.CharField(pk=True, max_length=64)
    user_id = fields.CharField(max_length=64, index=True)
    name = fields.CharField(max_length=255)
    agent_id = fields.CharField(max_length=64, default="sample_agent")
    sandbox_session_id = fields.CharField(max_length=128, null=True)
    archived = fields.BooleanField(default=False)
    created_at = fields.DatetimeField(auto_now_add=True)
    updated_at = fields.DatetimeField(auto_now=True)
    last_run_at = fields.DatetimeField(null=True)

    class Meta:
        table = "threads"

    def to_item(self) -> ThreadItem:
        return ThreadItem(
            id=self.id,
            userId=self.user_id,
            name=self.name,
            title=self.name,
            agentId=self.agent_id,
            archived=self.archived,
            createdAt=self.created_at.isoformat() if self.created_at else "",
            updatedAt=self.updated_at.isoformat() if self.updated_at else "",
            lastRunAt=self.last_run_at.isoformat() if self.last_run_at else None,
            sandboxSessionId=self.sandbox_session_id,
        )

    def to_dict(self) -> dict[str, Any]:
        return asdict(self.to_item())
