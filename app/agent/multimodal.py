"""Multimodal processing middleware for DeepAgent backed by Huawei Cloud AgentArts Sandbox.

Handles image attachments (hydrated to data URLs for cloud vision LLMs),
PDF documents (extracted via pypdf), and directly readable files (TXT, CSV, JSON,
Markdown, code, etc. stored inside the sandbox workspace for the agent to inspect via `read_file`).
"""

from __future__ import annotations

import base64
import io
import logging
import mimetypes
import os
import urllib.parse
from typing import Any, Awaitable, Callable, Dict, List, Optional

import pypdf
from langchain.agents.middleware.types import (
    AgentMiddleware,
    ContextT,
    ModelRequest,
    ModelResponse,
    ResponseT,
)
from langchain_core.messages import AnyMessage, HumanMessage
from langgraph.config import get_config

from app.sandbox.manager import sandbox_manager

logger = logging.getLogger(__name__)

IMAGE_EXTENSIONS = {".png", ".jpg", ".jpeg", ".webp", ".gif", ".svg", ".bmp", ".ico"}


def extract_pdf_text(
    filename: str,
    data_bytes: bytes,
    max_chars: int = 100_000,
) -> str:
    """Extract human-readable text from PDF raw bytes using pypdf."""
    try:
        reader = pypdf.PdfReader(io.BytesIO(data_bytes))
        pages_text: List[str] = []
        for i, page in enumerate(reader.pages):
            page_content = page.extract_text() or ""
            if page_content.strip():
                pages_text.append(f"--- [第 {i + 1} 页] ---\n{page_content}")

        if pages_text:
            full_text = "\n\n".join(pages_text)
            if len(full_text) > max_chars:
                full_text = (
                    full_text[:max_chars]
                    + f"\n... [文本过长，截取前 {max_chars} 字符] ..."
                )
            return full_text
        return "[PDF 文档已解析，但未检测到文本内容（可能是扫描图片型 PDF）。]"
    except Exception as e:
        logger.warning("PDF parsing failed for %s: %s", filename, e)
        return f"[PDF 解析异常: {e}]"


def _extract_sandbox_path(block: Dict[str, Any]) -> Optional[str]:
    """Extract sandbox path from block metadata or URL."""
    meta = block.get("metadata") or {}
    if meta.get("sandbox_path"):
        return meta["sandbox_path"]

    url = block.get("url") or (block.get("source") or {}).get("value")
    if isinstance(url, str):
        if url.startswith("/home/user"):
            return url
        parsed = urllib.parse.urlparse(url)
        params = urllib.parse.parse_qs(parsed.query)
        if "path" in params and params["path"]:
            return params["path"][0]

    return None


class MultimodalProcessorMiddleware(AgentMiddleware):
    """DeepAgent middleware that translates sandbox-backed attachments.

    - Images: downloaded from sandbox and hydrated into vision base64 data URLs.
    - PDF: downloaded from sandbox and extracted via pypdf into structured text blocks.
    - Directly readable files (TXT, Markdown, CSV, JSON, code, etc.): referenced by their
      sandbox absolute path (`/home/user/uploads/...`) so the agent can read them using `read_file`.
    """

    name: str = "MultimodalProcessorMiddleware"

    def _resolve_sandbox(self) -> Optional[Any]:
        """Resolve thread_id and sandbox instance from LangGraph execution config."""
        try:
            config = get_config()
            thread_id = config.get("configurable", {}).get("thread_id")
            if thread_id:
                return sandbox_manager.get_or_create(thread_id)
        except Exception as exc:
            logger.debug(
                "Failed to retrieve sandbox in MultimodalProcessorMiddleware: %s", exc
            )
        return None

    def _process_message(self, message: AnyMessage) -> AnyMessage:
        """Inspect and transform sandbox-backed attachments."""
        if not isinstance(message, HumanMessage) or not isinstance(
            message.content, list
        ):
            return message

        sandbox = self._resolve_sandbox()
        new_content: List[Dict[str, Any]] = []
        modified = False

        for block in message.content:
            if not isinstance(block, dict):
                new_content.append(block)
                continue

            block_type = block.get("type")

            # 1. Image block -> Hydrate to base64 data URL for cloud vision LLMs
            if block_type in ("image", "image_url"):
                url = None
                if block_type == "image_url":
                    img_data = block.get("image_url")
                    if isinstance(img_data, dict):
                        url = img_data.get("url")
                    elif isinstance(img_data, str):
                        url = img_data
                elif block_type == "image":
                    url = block.get("url") or (block.get("source") or {}).get("value")

                # If already base64 data URL or external HTTP URL, keep as is
                if (
                    url
                    and isinstance(url, str)
                    and (
                        url.startswith("data:")
                        or url.startswith("http://")
                        or url.startswith("https://")
                    )
                ):
                    new_content.append(block)
                    continue

                sandbox_path = _extract_sandbox_path(block) or (
                    url
                    if isinstance(url, str) and url.startswith("/home/user")
                    else None
                )
                if sandbox_path and sandbox:
                    try:
                        file_data = sandbox.download_file(sandbox_path)
                        img_bytes = (
                            file_data.encode("utf-8")
                            if isinstance(file_data, str)
                            else file_data
                        )
                        mime, _ = mimetypes.guess_type(sandbox_path)
                        mime = mime or "image/png"
                        b64 = base64.b64encode(img_bytes).decode("utf-8")
                        data_url = f"data:{mime};base64,{b64}"
                        modified = True
                        new_content.append(
                            {
                                "type": "image_url",
                                "image_url": {"url": data_url},
                            }
                        )
                        continue
                    except Exception as e:
                        logger.warning(
                            "Failed to download image from sandbox %s: %s",
                            sandbox_path,
                            e,
                        )

                new_content.append(block)

            # 2. File / Document block
            elif block_type == "file":
                modified = True
                filename = (
                    block.get("filename")
                    or (block.get("metadata") or {}).get("filename")
                    or "document"
                )
                mime_type = (
                    block.get("mime_type")
                    or (block.get("metadata") or {}).get("mimeType")
                    or "application/octet-stream"
                )
                ext = os.path.splitext(filename)[1].lower()
                sandbox_path = _extract_sandbox_path(block)

                # If base64 content is provided inline and not yet in sandbox, upload it
                inline_base64 = block.get("base64")
                if not sandbox_path and inline_base64 and sandbox:
                    try:
                        raw_bytes = base64.b64decode(inline_base64)
                        safe_name = os.path.basename(filename)
                        sandbox_path = f"/home/user/uploads/{safe_name}"
                        sandbox.upload_file(sandbox_path, raw_bytes)
                    except Exception as e:
                        logger.warning("Failed to save inline base64 to sandbox: %s", e)

                # Case 2A: File is an image
                if ext in IMAGE_EXTENSIONS or mime_type.startswith("image/"):
                    hydrated = False
                    if sandbox_path and sandbox:
                        try:
                            file_data = sandbox.download_file(sandbox_path)
                            img_bytes = (
                                file_data.encode("utf-8")
                                if isinstance(file_data, str)
                                else file_data
                            )
                            mime = (
                                mime_type
                                if mime_type.startswith("image/")
                                else (
                                    mimetypes.guess_type(sandbox_path)[0] or "image/png"
                                )
                            )
                            b64 = base64.b64encode(img_bytes).decode("utf-8")
                            new_content.append(
                                {
                                    "type": "image_url",
                                    "image_url": {"url": f"data:{mime};base64,{b64}"},
                                }
                            )
                            hydrated = True
                        except Exception as e:
                            logger.warning(
                                "Failed to read image %s from sandbox: %s",
                                sandbox_path,
                                e,
                            )

                    if not hydrated:
                        new_content.append(
                            {
                                "type": "text",
                                "text": f"\n[用户上传图片附件: {filename} (沙箱路径: {sandbox_path or '未知'}) - 无法读取图片内容]\n",
                            }
                        )
                    continue

                # Case 2B: PDF document (parsed via pypdf)
                if ext == ".pdf" or mime_type == "application/pdf":
                    text_content = None
                    if sandbox_path and sandbox:
                        try:
                            file_data = sandbox.download_file(sandbox_path)
                            pdf_bytes = (
                                file_data.encode("utf-8")
                                if isinstance(file_data, str)
                                else file_data
                            )
                            text_content = extract_pdf_text(filename, pdf_bytes)
                        except Exception as e:
                            logger.warning(
                                "Failed to download PDF %s from sandbox: %s",
                                sandbox_path,
                                e,
                            )

                    if text_content:
                        new_content.append(
                            {
                                "type": "text",
                                "text": (
                                    f"\n\n========================================\n"
                                    f"【用户上传PDF文档】: {filename} (沙箱存储路径: {sandbox_path})\n"
                                    f"========================================\n"
                                    f"{text_content}\n"
                                    f"========================================\n"
                                ),
                            }
                        )
                    else:
                        new_content.append(
                            {
                                "type": "text",
                                "text": f"\n\n[用户上传PDF文档: {filename} (沙箱存储路径: {sandbox_path or '未知'}) - 内容为空或读取失败]\n",
                            }
                        )
                    continue

                # Case 2C: Directly readable files (TXT, CSV, JSON, Markdown, code, etc.)
                if sandbox_path:
                    new_content.append(
                        {
                            "type": "text",
                            "text": (
                                f"\n[用户上传附件: {filename} (沙箱存储路径: {sandbox_path})]，"
                                f"该文件已保存在沙箱工作区中，你可以使用内置的 `read_file` 工具或在终端执行命令按需读取和分析其内容。\n"
                            ),
                        }
                    )
                else:
                    new_content.append(
                        {
                            "type": "text",
                            "text": f"\n[用户上传附件: {filename} - 未找到沙箱存储路径]\n",
                        }
                    )

            else:
                new_content.append(block)

        if modified:
            return message.model_copy(update={"content": new_content})
        return message

    def wrap_model_call(
        self,
        request: ModelRequest[ContextT],
        handler: Callable[[ModelRequest[ContextT]], ModelResponse[ResponseT]],
    ) -> ModelResponse[ResponseT]:
        """Synchronously intercept model call to transform attachments."""
        new_messages = [self._process_message(msg) for msg in request.messages]
        return handler(request.override(messages=new_messages))

    async def awrap_model_call(
        self,
        request: ModelRequest[ContextT],
        handler: Callable[
            [ModelRequest[ContextT]], Awaitable[ModelResponse[ResponseT]]
        ],
    ) -> ModelResponse[ResponseT]:
        """Asynchronously intercept model call to transform attachments."""
        new_messages = [self._process_message(msg) for msg in request.messages]
        return await handler(request.override(messages=new_messages))
