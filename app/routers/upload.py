"""File upload and retrieval router backed by Huawei Cloud AgentArts Sandbox.

Attachments are directly uploaded and stored inside the thread's sandbox workspace
at `/home/user/uploads/{filename}`, completely replacing local disk storage.
"""

from __future__ import annotations

import logging
import mimetypes
import os
import urllib.parse
from fastapi import APIRouter, Depends, File, Form, HTTPException, Response, UploadFile

from app.config import settings
from app.dependencies import get_current_user_id
from app.sandbox.manager import sandbox_manager

logger = logging.getLogger(__name__)

router = APIRouter(tags=["Upload"])

MAX_UPLOAD_SIZE = 20 * 1024 * 1024  # 20 MB


@router.post("")
async def upload_file(
    file: UploadFile = File(...),
    thread_id: str = Form(...),
    user_id: str = Depends(get_current_user_id),
):
    """Upload an attachment directly to the conversation's sandbox environment."""
    if not thread_id or not thread_id.strip():
        raise HTTPException(status_code=400, detail="必须提供 thread_id 以绑定沙箱环境")

    content = await file.read()
    size = len(content)
    if size > MAX_UPLOAD_SIZE:
        raise HTTPException(
            status_code=413,
            detail=f"文件大小超出限制 (最大 {MAX_UPLOAD_SIZE // (1024 * 1024)}MB)",
        )

    original_name = file.filename or "upload"
    safe_filename = os.path.basename(original_name).strip() or "upload"
    sandbox_path = f"/home/user/uploads/{safe_filename}"

    try:
        sandbox = sandbox_manager.get_or_create(thread_id)
        sandbox.upload_file(path=sandbox_path, content=content)
    except Exception as exc:
        logger.exception(
            "Failed to upload file to sandbox for thread '%s': %s", thread_id, exc
        )
        raise HTTPException(
            status_code=500,
            detail=f"上传至沙箱失败: {exc}",
        )

    mime_type = (
        file.content_type
        or mimetypes.guess_type(safe_filename)[0]
        or "application/octet-stream"
    )
    url = f"{settings.API_PREFIX}/upload/file?thread_id={urllib.parse.quote(thread_id)}&path={urllib.parse.quote(sandbox_path)}"

    return {
        "status": "ok",
        "sandbox_path": sandbox_path,
        "url": url,
        "filename": safe_filename,
        "mime_type": mime_type,
        "size": size,
        "thread_id": thread_id,
    }


@router.get("/file")
async def get_sandbox_file(
    thread_id: str,
    path: str,
    user_id: str = Depends(get_current_user_id),
):
    """Retrieve or download a file stored inside the sandbox."""
    if not thread_id or not path:
        raise HTTPException(status_code=400, detail="缺少必要参数 thread_id 或 path")

    sandbox = sandbox_manager.get_or_create(thread_id)
    try:
        content = sandbox.download_file(path)
    except Exception as exc:
        logger.warning(
            "File not found in sandbox (thread=%s, path=%s): %s", thread_id, path, exc
        )
        raise HTTPException(status_code=404, detail=f"沙箱中文件未找到: {exc}")

    if isinstance(content, str):
        data_bytes = content.encode("utf-8")
    else:
        data_bytes = content

    mime_type, _ = mimetypes.guess_type(path)
    if not mime_type:
        mime_type = "application/octet-stream"

    filename = os.path.basename(path)
    return Response(
        content=data_bytes,
        media_type=mime_type,
        headers={
            "Content-Disposition": f'inline; filename="{urllib.parse.quote(filename)}"',
        },
    )
