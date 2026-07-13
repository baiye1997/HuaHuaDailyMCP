"""system MCP tool implementations."""

import asyncio  # noqa: F401
import json  # noqa: F401
import os  # noqa: F401
import re  # noqa: F401
import time  # noqa: F401
from typing import Optional  # noqa: F401

from .binding import bind_runtime

_RUNTIME_DEPENDENCIES = ("_OFFICIAL_API", "_clear_session_caches", "_get", "_require_token", "_session", "build_tool_manifest")

if False:  # pragma: no cover - populated by bind() before tool registration
    _OFFICIAL_API = None
    _clear_session_caches = None
    _get = None
    _require_token = None
    _session = None
    build_tool_manifest = None


def bind(runtime_globals: dict) -> None:
    bind_runtime(globals(), runtime_globals, _RUNTIME_DEPENDENCIES)


async def set_token(token: str) -> str:
    """
    手动设置 Agent Token（运行时配置）。
    推荐通过环境变量 HUAHUA_AGENT_TOKEN 配置，无需调用此工具。

    Args:
        token: 从 App 设置页「Agent 访问令牌」中生成的令牌（PRO 会员专属）
    """
    _session["token"] = token.strip()
    _clear_session_caches()
    return f"✅ Token 已设置，将连接官方后端：{_session['base_url']}"


async def get_tool_manifest() -> dict:
    """
    返回本 MCP 服务的能力边界、认证方式和建议调用顺序。
    不访问后端，可用于 Agent 在会话开始时自检。
    """
    return build_tool_manifest(_OFFICIAL_API)


async def get_current_user() -> dict:
    """
    获取当前登录用户的账号信息（昵称、UID、会员状态等）。
    需要有效的 Agent Token（PRO 会员专属）。
    """
    _require_token()
    return await _get("/api/auth/me")


async def get_app_version() -> dict:
    """
    获取最新 App 版本信息，包括版本号、更新日志、下载地址、是否强制更新。
    适合回答"最新版本是多少""有什么新功能"等问题。
    """
    _require_token()
    return await _get("/api/version")


async def get_app_versions(page: int = 1, page_size: int = 5) -> dict:
    """
    获取 App 版本历史列表（分页，从新到旧）。
    适合查看历史更新记录。

    Args:
        page: 页码，从 1 开始
        page_size: 每页条数，1-20，默认 5
    """
    _require_token()
    return await _get("/api/versions", params={
        "page": max(1, page),
        "page_size": min(20, max(1, page_size)),
    })
