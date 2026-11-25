"""
Common FastAPI dependencies for DeepAgent.
Enforces request header validation and user context extraction at the top level.
"""

from __future__ import annotations

import re
from fastapi import Header, HTTPException, Request

USER_ID_PATTERN = re.compile(r"^[a-zA-Z0-9_\-]+$")


def get_current_user_id(
    request: Request,
    x_user_id: str = Header(..., alias="X-User-Id"),
) -> str:
    """
    顶层统一提取并强制校验 X-User-Id 请求头。
    若未提供该 Header（由 FastAPI 参数校验直接返回 422）或格式不合法，直接阻断报错。
    通过后将 user_id 挂载至 request.state.user_id 供全局使用。
    """
    user_id = x_user_id.strip()
    if not user_id or not USER_ID_PATTERN.match(user_id):
        raise HTTPException(
            status_code=400,
            detail="Header 'X-User-Id' 不能为空且仅支持字母、数字、下划线与短横线",
        )

    request.state.user_id = user_id
    return user_id
