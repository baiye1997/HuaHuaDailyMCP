"""import_tools MCP tool implementations."""

import asyncio  # noqa: F401
import json  # noqa: F401
import os  # noqa: F401
import re  # noqa: F401
from typing import Optional  # noqa: F401

from .binding import bind_runtime

_RUNTIME_DEPENDENCIES = ("_normalize_upload_files", "_post", "_post_files", "_require_token", "_summarize_import_items")

if False:  # pragma: no cover - populated by bind() before tool registration
    _normalize_upload_files = None
    _post = None
    _post_files = None
    _require_token = None
    _summarize_import_items = None


def bind(runtime_globals: dict) -> None:
    bind_runtime(globals(), runtime_globals, _RUNTIME_DEPENDENCIES)


async def import_holding_screenshots(
    image_paths: Optional[list[str]] = None,
    images_base64: Optional[list[dict]] = None,
    import_type: str = "HOLDINGS",
) -> dict:
    """
    识别持仓/自选截图，只返回结构化结果，不写入 App。

    Agent 可先对 unmatched / ambiguous 条目做轻确认，然后调用 request_import_review
    把结果发送到 App 现有导入确认页。

    Args:
        image_paths: 本地图片路径列表，适合 Codex、Claude Code 等本地 CLI/桌面 Agent。
        images_base64: 图片对象列表，格式 {filename, mime, base64}。
        import_type: "HOLDINGS"（持仓，默认）或 "WATCHLIST"（自选）。
            自选截图通常显示 6 位基金代码，传 "WATCHLIST" 后端会用专门 prompt
            提取代码并精确匹配，避免名称模糊匹配的误配。
    """
    _require_token()
    normalized_import_type = (import_type or "").strip().upper()
    if normalized_import_type not in {"HOLDINGS", "WATCHLIST"}:
        raise ValueError("import_type 必须是 HOLDINGS 或 WATCHLIST")
    files = _normalize_upload_files(image_paths, images_base64)
    mode = "watchlist" if normalized_import_type == "WATCHLIST" else "holdings"
    raw = await _post_files("/api/import_screenshot", files, form_data={"mode": mode})
    items = raw if isinstance(raw, list) else []
    normalized = []
    for item in items:
        if not isinstance(item, dict):
            continue
        code = item.get("code") or "000000"
        match_quality = item.get("match_quality") or ("exact" if code != "000000" else "none")
        normalized.append({
            **item,
            "match_status": "unmatched" if code == "000000" else match_quality,
            "resolution_required": code == "000000" or match_quality in {"none", "ambiguous"},
            "resolution_reason": "未匹配到基金代码" if code == "000000" else "",
        })
    return {
        "items": normalized,
        "summary": _summarize_import_items(normalized),
        "next_step": "如有未匹配或歧义项，先在对话中轻确认；确认后调用 request_import_review 发送到 App。",
    }


async def import_transaction_screenshots(
    image_paths: Optional[list[str]] = None,
    images_base64: Optional[list[dict]] = None,
) -> dict:
    """
    识别交易记录截图，只返回结构化结果，不写入 App。

    Args:
        image_paths: 本地图片路径列表，适合 Codex、Claude Code 等本地 CLI/桌面 Agent。
        images_base64: 图片对象列表，格式 {filename, mime, base64}。
    """
    _require_token()
    files = _normalize_upload_files(image_paths, images_base64)
    raw = await _post_files("/api/import_transactions", files)
    items = raw if isinstance(raw, list) else []
    normalized = []
    for item in items:
        if not isinstance(item, dict):
            continue
        matched = bool(item.get("matched"))
        reason = ""
        if not matched:
            reason = "未匹配到基金代码"
        elif not item.get("date"):
            reason = "交易日期缺失"
        elif item.get("type") == "BUY" and item.get("amount") is None:
            reason = "买入金额缺失"
        elif item.get("type") == "SELL" and item.get("shares") is None:
            reason = "卖出份额缺失"
        normalized.append({
            **item,
            "match_status": "exact" if matched else "unmatched",
            "resolution_required": bool(reason),
            "resolution_reason": reason,
        })
    return {
        "items": normalized,
        "summary": _summarize_import_items(normalized),
        "next_step": "如有未匹配或日期/金额歧义，先在对话中轻确认；确认后调用 request_import_review 发送到 App。",
    }


async def request_import_review(
    import_type: str,
    items: list[dict],
    source_note: str = "Agent screenshot import",
    client_request_id: str = "",
) -> str:
    """
    将 Agent 识别和轻确认后的导入结果发送到 App，复用 App 现有批量导入确认页。

    Args:
        import_type: "HOLDINGS"、"WATCHLIST" 或 "TRANSACTIONS"。
        items: 识别结果数组，最多 300 条。
        source_note: 展示给用户的来源说明。
        client_request_id: 当前用户内幂等 ID；同一导入请求重试时必须复用。
    """
    _require_token()
    normalized_type = (import_type or "").strip().upper()
    action_map = {
        "HOLDINGS": "IMPORT_HOLDINGS",
        "WATCHLIST": "IMPORT_WATCHLIST",
        "TRANSACTIONS": "IMPORT_TRANSACTIONS",
    }
    action_type = action_map.get(normalized_type)
    if not action_type:
        raise ValueError("import_type 必须是 HOLDINGS、WATCHLIST 或 TRANSACTIONS")
    if not isinstance(items, list) or not items:
        raise ValueError("items 不能为空")
    if len(items) > 300:
        raise ValueError("单次导入请求最多 300 条")
    normalized_client_request_id = str(client_request_id or "").strip()
    if normalized_client_request_id and not re.fullmatch(r"[A-Za-z0-9:_-]{1,120}", normalized_client_request_id):
        raise ValueError("client_request_id 仅支持 1-120 位字母、数字、冒号、下划线或连字符")
    payload_dict = {
        "importType": normalized_type,
        "source": "agent_screenshot",
        "sourceNote": source_note,
        "summary": _summarize_import_items(items),
        "items": items,
    }
    if normalized_client_request_id:
        payload_dict["client_request_id"] = normalized_client_request_id
    payload = json.dumps(payload_dict, ensure_ascii=False)
    if len(payload.encode("utf-8")) > 1024 * 1024:
        raise ValueError("导入请求体不能超过 1MB，请拆分后发送")
    request_body = {"action_type": action_type, "payload": payload}
    if normalized_client_request_id:
        request_body["client_request_id"] = normalized_client_request_id
    await _post("/api/agent/request", request_body)
    return f"✅ 已发送 {payload_dict['summary']['total']} 条导入结果到 App，请打开花花日记批量确认后导入。"
