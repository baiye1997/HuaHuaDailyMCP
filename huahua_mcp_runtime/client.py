"""Session state, shared caches, and HTTP transport for the MCP facade."""

import asyncio
import os
import threading
from typing import Optional

import httpx

OFFICIAL_API = os.environ.get("HUAHUA_API_BASE", "https://api.huahuadaily.cn").strip().rstrip("/")

session: dict = {
    "token": os.environ.get("HUAHUA_AGENT_TOKEN", "").strip(),
    "base_url": OFFICIAL_API,
}

http_client: Optional[httpx.AsyncClient] = None
http_client_lock = threading.Lock()

portfolio_cache: dict = {"data": None, "ts": 0.0}
PORTFOLIO_TTL = 30
download_lock: Optional[asyncio.Lock] = None

estimate_cache: dict = {}
ESTIMATE_TTL = 60


def get_client() -> httpx.AsyncClient:
    global http_client
    with http_client_lock:
        is_closed = bool(getattr(http_client, "is_closed", False)) if http_client is not None else True
        if http_client is None or is_closed:
            http_client = httpx.AsyncClient(
                timeout=30,
                limits=httpx.Limits(
                    max_connections=20,
                    max_keepalive_connections=10,
                    keepalive_expiry=30,
                ),
            )
    return http_client


def get_download_lock() -> asyncio.Lock:
    global download_lock
    if download_lock is None:
        download_lock = asyncio.Lock()
    return download_lock


def clear_session_caches() -> None:
    """Clear data tied to the current token/base URL."""
    portfolio_cache["data"] = None
    portfolio_cache["ts"] = 0.0
    estimate_cache.clear()


def require_token() -> None:
    if not session["token"]:
        raise ValueError(
            "未配置 Agent Token。请在 MCP server env 中设置 HUAHUA_AGENT_TOKEN"
            "，或调用 set_token 工具。"
            "Agent Token 需在 App 设置页 →「Agent 访问令牌」中生成（PRO 会员专属）。"
        )


def headers() -> dict:
    token = session["token"]
    return {"Authorization": f"AgentToken {token}"} if token else {}


def url(path: str) -> str:
    return f"{session['base_url']}{path}"


def _raise_auth_error(response: httpx.Response) -> None:
    if response.status_code == 401:
        raise ValueError("Agent Token 无效或已过期，请在 App 重新生成并更新配置。")
    if response.status_code == 403:
        raise ValueError("无访问权限，请确认 Agent Token 正确，且账号为 PRO 会员。")


def _translate_transport_error(error: Exception) -> None:
    if isinstance(error, httpx.TimeoutException):
        raise RuntimeError("请求超时，请稍后重试。") from error
    if isinstance(error, httpx.HTTPStatusError):
        raise RuntimeError(f"服务器返回错误 {error.response.status_code}，请稍后重试。") from error
    raise error


async def get(path: str, params: dict = None) -> dict:
    try:
        response = await get_client().get(url(path), params=params, headers=headers())
        _raise_auth_error(response)
        response.raise_for_status()
        return response.json()
    except ValueError:
        raise
    except (httpx.TimeoutException, httpx.HTTPStatusError) as error:
        _translate_transport_error(error)


async def get_optional(path: str, params: dict = None) -> Optional[dict]:
    try:
        response = await get_client().get(url(path), params=params, headers=headers())
        _raise_auth_error(response)
        if response.status_code == 404:
            return None
        response.raise_for_status()
        return response.json()
    except ValueError:
        raise
    except (httpx.TimeoutException, httpx.HTTPStatusError) as error:
        _translate_transport_error(error)


async def post(path: str, body: dict = None, params: dict = None) -> dict:
    try:
        response = await get_client().post(url(path), params=params, json=body or {}, headers=headers())
        _raise_auth_error(response)
        response.raise_for_status()
        return response.json()
    except ValueError:
        raise
    except (httpx.TimeoutException, httpx.HTTPStatusError) as error:
        _translate_transport_error(error)


async def post_files(
    path: str,
    files: list[tuple[str, bytes, str]],
    form_data: Optional[dict] = None,
) -> dict | list:
    try:
        multipart = [("files", (filename, content, mime)) for filename, content, mime in files]
        upload_client = httpx.AsyncClient(timeout=httpx.Timeout(120, connect=30))
        async with upload_client:
            response = await upload_client.post(
                url(path),
                files=multipart,
                data=form_data or None,
                headers=headers(),
            )
        _raise_auth_error(response)
        response.raise_for_status()
        return response.json()
    except ValueError:
        raise
    except (httpx.TimeoutException, httpx.HTTPStatusError) as error:
        _translate_transport_error(error)


async def put(path: str, body: dict = None) -> dict:
    try:
        response = await get_client().put(url(path), json=body or {}, headers=headers())
        _raise_auth_error(response)
        response.raise_for_status()
        return response.json()
    except ValueError:
        raise
    except (httpx.TimeoutException, httpx.HTTPStatusError) as error:
        _translate_transport_error(error)


async def delete(path: str) -> dict:
    try:
        response = await get_client().delete(url(path), headers=headers())
        _raise_auth_error(response)
        response.raise_for_status()
        return response.json()
    except ValueError:
        raise
    except (httpx.TimeoutException, httpx.HTTPStatusError) as error:
        _translate_transport_error(error)
