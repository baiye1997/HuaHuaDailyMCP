"""Portfolio report and mutation-request MCP tools."""

import json

from .binding import bind_runtime

_RUNTIME_DEPENDENCIES = ("_get", "_post", "_put", "_require_token", "_validate_amount", "_validate_date", "_validate_fund_code")

if False:  # pragma: no cover - populated by bind() before tool registration
    _get = None
    _post = None
    _put = None
    _require_token = None
    _validate_amount = None
    _validate_date = None
    _validate_fund_code = None


def bind(runtime_globals: dict) -> None:
    bind_runtime(globals(), runtime_globals, _RUNTIME_DEPENDENCIES)


async def submit_personal_strategy_report(
    title: str,
    summary: str,
    payload: dict,
    client_message_id: str = "",
) -> dict:
    """
    将用户自己的 Agent 生成的个人策略报告投递到当前用户报告中心。

    认证要求：
    - 需要当前用户自己的 Agent Token。
    - Token 需要显式包含 messages:write scope；不要使用 hermes:write。

    安全边界：
    - 只写当前 Agent Token 所属用户的报告中心。
    - 不能广播，不能指定 user_id，不能调用 /api/hermes/reports。
    - 可基于用户明确授权读取的持仓、交易和行情数据生成个人报告。

    Args:
        title: 报告标题，如 "7月1日 个人组合复盘"。
        summary: 报告列表摘要，最多 500 字。
        payload: 策略报告 JSON，建议包含 kind/date/body/sections/themes/riskNotes。
        client_message_id: 当前用户内幂等 ID，如 personal:2026-07-01:evening。
    """
    _require_token()
    clean_title = str(title or "").strip()
    clean_summary = str(summary or "").strip()
    if not clean_title:
        raise ValueError("title 不能为空")
    if not clean_summary:
        raise ValueError("summary 不能为空")
    if not isinstance(payload, dict) or not payload:
        raise ValueError("payload 必须是非空对象")

    body = {
        "type": "STRATEGY_REPORT",
        "title": clean_title,
        "summary": clean_summary,
        "payload": payload,
    }
    if client_message_id:
        body["clientMessageId"] = str(client_message_id).strip()
    return await _post("/api/agent/messages", body)


async def request_transaction(
    item_code: str,
    item_name: str,
    record_type: str,
    amount: float,
    date: str = "",
    note: str = "",
    group_name: str = "",
) -> str:
    """
    向用户的 App 发送一条交易请求信号。
    用户会在 App 中收到提示，点击后打开预填好的交易表单，确认后执行。
    交易逻辑（净值日计算、手续费、PENDING/CONFIRMED 状态）由 App 处理，不会产生数据冲突。

    重要：调用前须向用户确认基金名称和代码无误，尤其是通过搜索推断出来的代码。
    发送后须告知用户"需在 App 中确认才会生效"，不要让用户误以为已执行。

    如用户说"XX分组的XX基金买入XX元"，请从 get_records 获取分组信息后填入 group_name。
    App 会按分组名精确匹配，匹配失败时降级为弹出分组选择器。

    Args:
        item_code: 项目编号，如 "110022"
        item_name: 项目名称，如 "易方达消费行业"
        record_type: "BUY"（买入）或 "SELL"（卖出）
        amount: 金额（元），如 10000.00
        date: 操作日期 YYYY-MM-DD，留空则由 App 使用今日
        note: 备注说明（可选）
        group_name: 目标分组名称（可选），如 "沪深宽基"；有值时 App 直接路由到该分组

    Returns:
        str: 发送结果提示
    """
    _require_token()
    tx_type = record_type.upper()
    if tx_type not in ("BUY", "SELL"):
        return "❌ record_type 必须是 'BUY' 或 'SELL'"

    validated_code = _validate_fund_code(item_code)
    normalized_name = str(item_name or "").strip()
    if not normalized_name:
        raise ValueError("item_name 不能为空")
    validated_amount = _validate_amount(amount)
    validated_date = _validate_date(date)

    payload_dict: dict = {
        "code": validated_code,
        "name": normalized_name,
        "amount": validated_amount,
        "date": validated_date,
        "note": note,
    }
    if group_name:
        payload_dict["group_name"] = group_name

    payload = json.dumps(payload_dict, ensure_ascii=False)

    await _post("/api/agent/request", {"action_type": tx_type, "payload": payload})
    action = "买入" if tx_type == "BUY" else "卖出"
    group_hint = f"（分组：{group_name}）" if group_name else ""
    return f"✅ {action}请求已发送：{item_name}（{validated_code}）¥{validated_amount:,.2f}{group_hint}，请打开 App 确认后生效。"


async def get_agent_requests() -> list:
    """
    获取当前账号仍待处理的 Agent 交易请求。
    主要用于 Agent 自检是否已经重复发送请求；App 端仍是最终确认入口。
    """
    _require_token()
    data = await _get("/api/agent/request")
    return data if isinstance(data, list) else []


async def update_agent_request(request_id: str, status: str) -> dict:
    """
    更新 Agent 交易请求状态。通常由 App 调用；Agent 只应在用户明确要求撤销/忽略时使用。

    Args:
        request_id: get_agent_requests 返回的 id。
        status: "DISMISSED" 或 "PROCESSED"。Agent 常用 "DISMISSED"。
    """
    _require_token()
    normalized_request_id = str(request_id or "").strip()
    if not normalized_request_id:
        raise ValueError("request_id 不能为空")
    normalized = (status or "").strip().upper()
    if normalized not in ("PROCESSED", "DISMISSED"):
        raise ValueError("status 必须是 PROCESSED 或 DISMISSED")
    return await _put(f"/api/agent/request/{normalized_request_id}", {"status": normalized})
