import json
import logging
import uuid
from typing import Optional

from ag_ui_langgraph.utils import langchain_messages_to_agui
from fastapi import APIRouter, Depends, HTTPException, Query
from tortoise import connections

from app.agent.agent import agent, sandbox_manager
from app.browser.manager import browser_manager
from app.database import get_checkpointer
from app.dependencies import get_current_user_id
from app.models.thread import Thread
from app.schemas.thread import (
    ThreadCreateRequest,
    ThreadItem,
    ThreadListResponse,
    ThreadMessagesResponse,
    ThreadUpdateRequest,
)

logger = logging.getLogger(__name__)

router = APIRouter(tags=["Threads"])


@router.get("", response_model=ThreadListResponse)
async def list_threads(
    agentId: Optional[str] = Query(None),
    includeArchived: bool = Query(False),
    limit: Optional[int] = Query(None),
    user_id: str = Depends(get_current_user_id),
):
    """List all threads belonging to the authenticated user."""
    query = Thread.filter(user_id=user_id)
    if not includeArchived:
        query = query.filter(archived=False)
    if agentId:
        query = query.filter(agent_id=agentId)

    query = query.order_by("-updated_at")
    if limit is not None and limit > 0:
        query = query.limit(limit)

    threads = await query.all()
    thread_items = [t.to_item() for t in threads]
    return ThreadListResponse(threads=thread_items, nextCursor=None, joinCode=None)


@router.post("", response_model=ThreadItem)
async def create_thread(
    req: ThreadCreateRequest,
    user_id: str = Depends(get_current_user_id),
):
    """Create a new conversation thread for the user."""
    thread_id = req.id or str(uuid.uuid4())
    name = req.get_name()
    agent_id = req.agentId or "sample_agent"

    thread, _ = await Thread.update_or_create(
        id=thread_id,
        defaults={
            "user_id": user_id,
            "name": name,
            "agent_id": agent_id,
            "archived": False,
        },
    )
    return thread.to_item()


@router.patch("/{thread_id}")
async def update_thread(
    thread_id: str,
    req: ThreadUpdateRequest,
    user_id: str = Depends(get_current_user_id),
):
    """Update thread metadata for the user."""
    thread = await Thread.get_or_none(id=thread_id, user_id=user_id)
    if not thread:
        raise HTTPException(status_code=404, detail="会话不存在")

    new_name = req.get_name()
    if new_name is not None:
        thread.name = new_name
    if req.archived is not None:
        thread.archived = req.archived

    await thread.save()
    return {"status": "ok", "id": thread_id, "name": new_name}


@router.post("/{thread_id}/archive")
async def archive_thread(
    thread_id: str,
    user_id: str = Depends(get_current_user_id),
):
    thread = await Thread.get_or_none(id=thread_id, user_id=user_id)
    if not thread:
        raise HTTPException(status_code=404, detail="会话不存在")
    thread.archived = True
    await thread.save()
    return {"status": "ok", "id": thread_id, "archived": True}


@router.post("/{thread_id}/unarchive")
async def unarchive_thread(
    thread_id: str,
    user_id: str = Depends(get_current_user_id),
):
    thread = await Thread.get_or_none(id=thread_id, user_id=user_id)
    if not thread:
        raise HTTPException(status_code=404, detail="会话不存在")
    thread.archived = False
    await thread.save()
    return {"status": "ok", "id": thread_id, "archived": False}


@router.delete("/{thread_id}")
async def delete_thread(
    thread_id: str,
    user_id: str = Depends(get_current_user_id),
):
    """Delete thread and its LangGraph checkpoints from SQLite for the user."""
    thread = await Thread.get_or_none(id=thread_id, user_id=user_id)
    if not thread:
        raise HTTPException(status_code=404, detail="会话不存在")
    await thread.delete()

    sandbox_manager.release(thread_id)
    browser_manager.release(thread_id)

    try:
        checkpointer = get_checkpointer()
        await checkpointer.adelete_thread(thread_id)
    except Exception as exc:
        logger.warning("Failed to delete thread checkpoints from postgres: %s", exc)

    return {"status": "ok", "deleted_thread_id": thread_id}


@router.get("/{thread_id}/messages", response_model=ThreadMessagesResponse)
async def get_thread_messages(
    thread_id: str,
    user_id: str = Depends(get_current_user_id),
):
    """Read saved message history directly from LangGraph SQLite checkpointer in standard AG-UI format."""
    exists = await Thread.filter(id=thread_id, user_id=user_id).exists()
    if not exists:
        raise HTTPException(status_code=404, detail="会话不存在或无权访问")

    try:
        state = await agent.aget_state({"configurable": {"thread_id": thread_id}})
        raw_messages = state.values.get("messages", []) if state else []
        for msg in raw_messages:
            if hasattr(msg, "content_blocks") and msg.content_blocks:
                msg.content = msg.content_blocks

        agui_messages = langchain_messages_to_agui(raw_messages)
        formatted = [
            msg.model_dump(by_alias=True, exclude_none=True) for msg in agui_messages
        ]
        return ThreadMessagesResponse(thread_id=thread_id, messages=formatted)
    except Exception:
        logger.exception("加载会话历史消息失败 (thread_id=%s)", thread_id)
        return ThreadMessagesResponse(thread_id=thread_id, messages=[])
