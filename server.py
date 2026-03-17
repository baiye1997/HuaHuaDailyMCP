"""
HuahuaDaily MCP Server (OpenClaw Skills)
=========================================
让 OpenClaw 等 AI agent 通过 MCP 协议直接访问花花日记的数据与功能。

配置方式：
  在 OpenClaw/Claude Desktop 配置文件中添加：
  {
    "mcpServers": {
      "huahua-daily": {
        "command": "python",
        "args": ["/path/to/mcp-server/server.py"],
        "env": {
          "BAIYE_AGENT_TOKEN": "从 App 设置页生成并复制的 Agent 令牌"
        }
      }
    }
  }

认证说明：
  使用 BAIYE_AGENT_TOKEN 环境变量（推荐），或运行时调用 set_token 工具。
  Agent Token 需在 App 设置页 → "Agent 访问令牌" 中生成（需邮箱验证）。
  如需连接自建后端，可额外添加 BAIYE_API_BASE 环境变量。
"""

import os
import json
from typing import Optional

import httpx
from mcp.server.fastmcp import FastMCP

# ── Session state ─────────────────────────────────────────────────────────────
_OFFICIAL_API = "https://huahua.preview.aliyun-zeabur.cn"

_session: dict = {
    "token": os.environ.get("BAIYE_AGENT_TOKEN", "").strip(),
    "base_url": os.environ.get("BAIYE_API_BASE", _OFFICIAL_API).rstrip("/"),
}

mcp = FastMCP("huahua-daily", description="花花日记助手 MCP Server — 查询数据、概览、记录，管理日常条目")

# ── Helpers ───────────────────────────────────────────────────────────────────

def _headers() -> dict:
    """构建 HTTP 请求头：优先使用 AgentToken，否则回退到 Bearer JWT。"""
    tok = _session["token"]
    if not tok:
        return {}
    if tok.startswith("ey"):
        return {"Authorization": f"Bearer {tok}"}
    return {"Authorization": f"AgentToken {tok}"}

def _url(path: str) -> str:
    return f"{_session['base_url']}{path}"

async def _get(path: str, params: dict = None) -> dict:
    async with httpx.AsyncClient(timeout=30) as client:
        r = await client.get(_url(path), params=params, headers=_headers())
        r.raise_for_status()
        return r.json()

async def _post(path: str, body: dict = None) -> dict:
    async with httpx.AsyncClient(timeout=30) as client:
        r = await client.post(_url(path), json=body or {}, headers=_headers())
        r.raise_for_status()
        return r.json()

async def _delete(path: str) -> dict:
    async with httpx.AsyncClient(timeout=30) as client:
        r = await client.delete(_url(path), headers=_headers())
        r.raise_for_status()
        return r.json()

def _r2(v: float) -> float:
    return round(v, 2)

def _r4(v: float) -> float:
    return round(v, 4)

def _r6(v: float) -> float:
    return round(v, 6)


# ── 收益计算 ──────────────────────────────────────────────────────────────────

def _calc_fund_stats(fund: dict, estimated_nav: Optional[float] = None) -> dict:
    """
    计算单条记录的统计字段。
    holdingCost 是每份成本价（不是总成本）。
    """
    shares: float = fund.get("holdingShares", 0) or 0
    cost_per_share: float = fund.get("holdingCost", 0) or 0
    last_nav: float = fund.get("lastNav", 0) or 0
    realized: float = fund.get("realizedProfit", 0) or 0

    current_nav = estimated_nav if estimated_nav else last_nav

    cost_total = shares * cost_per_share
    market_value = shares * current_nav
    holding_profit = market_value - cost_total
    total_profit = holding_profit + realized
    return_rate = _r2(holding_profit / cost_total * 100) if cost_total > 0 else 0.0
    today_profit = shares * (current_nav - last_nav)

    return {
        "marketValue": _r2(market_value),
        "costPerShare": _r4(cost_per_share),
        "costTotal": _r2(cost_total),
        "holdingShares": _r6(shares),
        "holdingProfit": _r2(holding_profit),
        "realizedProfit": _r2(realized),
        "totalProfit": _r2(total_profit),
        "returnRate": return_rate,
        "todayProfit": _r2(today_profit),
        "currentNav": current_nav,
        "lastNav": last_nav,
    }


# ═══════════════════════════════════════════════════════════════════════════════
# Tools: 认证类
# ═══════════════════════════════════════════════════════════════════════════════

@mcp.tool()
async def set_token(token: str, api_base_url: str = "") -> str:
    """
    手动设置 Agent Token 或 API 地址（运行时配置）。
    推荐通过环境变量 BAIYE_AGENT_TOKEN 配置，无需调用此工具。

    Args:
        token: 从 App 设置页「Agent 访问令牌」中生成的令牌
        api_base_url: API 基础 URL（可选，不填则保留现有配置）
    """
    _session["token"] = token.strip()
    if api_base_url:
        _session["base_url"] = api_base_url.rstrip("/")
    return f"✅ Token 已设置，API 地址：{_session['base_url']}"


@mcp.tool()
async def get_current_user() -> dict:
    """
    获取当前登录用户的账号信息（昵称、UID、会员状态等）。
    需要有效的 Agent Token。
    """
    return await _get("/api/auth/me")


# ═══════════════════════════════════════════════════════════════════════════════
# Tools: 数据查询（无需认证）
# ═══════════════════════════════════════════════════════════════════════════════

@mcp.tool()
async def search_item(query: str) -> list:
    """
    按编号或名称搜索项目，返回最多 20 条结果。

    Args:
        query: 搜索关键词，如 "000001"、"华夏"
    """
    data = await _get("/api/search", params={"key": query})
    return data if isinstance(data, list) else []


@mcp.tool()
async def get_item_detail(code: str) -> dict:
    """
    获取项目详细信息，包括名称、数值、历史收益、持仓、费率等。

    Args:
        code: 项目编号，如 "000001"
    """
    return await _get(f"/api/fund/{code}")


@mcp.tool()
async def get_item_estimate(codes: list[str]) -> dict:
    """
    批量获取项目今日实时估算数值（最多 50 个）。

    Args:
        codes: 项目编号列表，如 ["000001", "110022"]，最多 50 个
    """
    if len(codes) > 50:
        codes = codes[:50]
    return await _post("/api/estimate/batch", {"codes": codes})


@mcp.tool()
async def get_daily_rank() -> dict:
    """
    获取今日涨幅榜和跌幅榜。
    返回涨幅最大和跌幅最大的项目列表，以及板块概览。
    """
    return await _get("/api/fund/today-rank")


@mcp.tool()
async def get_item_history(code: str) -> list:
    """
    获取项目历史数值数据（用于查看过去走势）。

    Args:
        code: 项目编号，如 "000001"
    """
    data = await _get(f"/api/history/{code}")
    return data if isinstance(data, list) else []


@mcp.tool()
async def get_item_dividends(code: str) -> list:
    """
    获取项目历史派息记录。

    Args:
        code: 项目编号，如 "000001"
    """
    data = await _get(f"/api/fund/dividends/{code}")
    return data if isinstance(data, list) else []


# ═══════════════════════════════════════════════════════════════════════════════
# Tools: 概览数据（无需认证）
# ═══════════════════════════════════════════════════════════════════════════════

@mcp.tool()
async def get_status() -> dict:
    """
    查询今日状态。
    返回 is_trading_day: true/false。
    """
    return await _get("/api/market/status")


@mcp.tool()
async def get_overview() -> dict:
    """
    获取整体概览数据，包括主要指数涨跌、热门板块、涨跌排行。
    适合快速了解今日整体情况。
    """
    return await _get("/api/market/overview")


@mcp.tool()
async def get_indices() -> list:
    """
    获取主要指数实时数据（上证、深证、创业板、沪深300、纳斯达克等）。
    """
    data = await _get("/api/market/indices")
    return data if isinstance(data, list) else []


# ═══════════════════════════════════════════════════════════════════════════════
# Tools: 记录管理（需 Agent Token + 会员）
# ═══════════════════════════════════════════════════════════════════════════════

async def _download_portfolio() -> dict:
    """下载云同步数据并解析 JSON。"""
    raw = await _get("/api/sync/download")
    json_data = raw.get("json_data", "{}")
    try:
        return json.loads(json_data)
    except Exception:
        return {}

@mcp.tool()
async def get_records() -> dict:
    """
    获取用户完整记录数据，并自动计算今日收益、累计收益、市值、收益率等字段。
    需要 Agent Token 且账号需开通会员才能使用云同步功能。

    返回字段包括：
    - funds: 记录列表（含计算后的收益字段）
    - groups: 分组信息
    - summary: 总资产/今日收益/累计收益汇总
    """
    # 1. 下载记录
    portfolio = await _download_portfolio()
    funds: list = portfolio.get("funds", [])

    # 2. 找出有持仓的项目编号
    held_codes = [f["code"] for f in funds if (f.get("holdingShares") or 0) > 0]

    # 3. 批量获取今日估算数值
    estimate_map: dict = {}
    if held_codes:
        try:
            for i in range(0, len(held_codes), 50):
                batch = held_codes[i:i+50]
                result = await _post("/api/estimate/batch", {"codes": batch})
                batch_data = result.get("data", result) if isinstance(result, dict) else result
                if isinstance(batch_data, list):
                    for item in batch_data:
                        code_key = item.get("fundcode") or item.get("code")
                        if code_key:
                            estimate_map[code_key] = item
        except Exception:
            pass

    # 4. 计算每条记录的收益字段
    enriched_funds = []
    for fund in funds:
        code = fund.get("code", "")
        est = estimate_map.get(code, {})
        estimated_nav = est.get("estimatedNav") or est.get("nav") or None
        stats = _calc_fund_stats(fund, estimated_nav)

        enriched = {**fund, **stats}
        if est:
            enriched["estimatedChangePercent"] = est.get("estimatedChangePercent", 0)
            enriched["estimateTime"] = est.get("time", "")

        # 提取在途资产（PENDING 买入交易）
        txs = fund.get("transactions") or []
        pending_txs = [tx for tx in txs if tx.get("status") == "PENDING"]
        in_transit_amount = _r2(sum(
            tx.get("amount", 0) for tx in pending_txs if tx.get("type") == "BUY"
        ))
        enriched["pendingTransactions"] = pending_txs
        enriched["inTransitAmount"] = in_transit_amount

        enriched_funds.append(enriched)

    # 5. 汇总统计（只统计有持仓的记录）
    held_funds = [f for f in enriched_funds if (f.get("holdingShares") or 0) > 0]
    total_market_value = sum(f.get("marketValue", 0) for f in held_funds)
    total_cost = sum(f.get("costTotal", 0) for f in held_funds)
    total_today_profit = sum(f.get("todayProfit", 0) for f in held_funds)
    total_cumulative_profit = sum(f.get("totalProfit", 0) for f in held_funds)
    total_return_rate = _r2(total_cumulative_profit / total_cost * 100) if total_cost > 0 else 0.0
    total_in_transit = _r2(sum(f.get("inTransitAmount", 0) for f in enriched_funds))

    return {
        "funds": enriched_funds,
        "groups": portfolio.get("groups", []),
        "summary": {
            "totalMarketValue": _r2(total_market_value),
            "totalCost": _r2(total_cost),
            "todayProfit": _r2(total_today_profit),
            "cumulativeProfit": _r2(total_cumulative_profit),
            "totalReturnRate": total_return_rate,
            "heldItemCount": len(held_funds),
            "totalInTransitAmount": total_in_transit,
        }
    }


@mcp.tool()
async def get_summary() -> dict:
    """
    获取记录总览摘要（总资产、今日收益、累计收益、收益率）。
    比 get_records 更轻量，适合快速查询资产概况。
    """
    result = await get_records()
    return result.get("summary", {})


@mcp.tool()
async def request_transaction(
    item_code: str,
    item_name: str,
    record_type: str,
    amount: float,
    date: str = "",
    note: str = "",
) -> str:
    """
    向用户的 App 发送一条交易请求信号。
    用户会在 App 中收到提示，点击后打开预填好的交易表单，确认后执行。
    交易逻辑（净值日计算、手续费、PENDING/CONFIRMED 状态）由 App 处理，不会产生数据冲突。

    Args:
        item_code: 项目编号，如 "110022"
        item_name: 项目名称，如 "易方达消费行业"
        record_type: "BUY"（买入）或 "SELL"（卖出）
        amount: 金额（元），如 10000.00
        date: 操作日期 YYYY-MM-DD，留空则由 App 使用今日
        note: 备注说明（可选）

    Returns:
        str: 发送结果提示
    """
    tx_type = record_type.upper()
    if tx_type not in ("BUY", "SELL"):
        return "❌ record_type 必须是 'BUY' 或 'SELL'"

    payload = json.dumps({
        "code": item_code,
        "name": item_name,
        "amount": amount,
        "date": date,
        "note": note,
    }, ensure_ascii=False)

    await _post("/api/agent/request", {"action_type": tx_type, "payload": payload})
    action = "买入" if tx_type == "BUY" else "卖出"
    return f"✅ {action}请求已发送：{item_name}（{item_code}）¥{amount:,.2f}，请打开 App 确认。"


# ═══════════════════════════════════════════════════════════════════════════════
# Entry point
# ═══════════════════════════════════════════════════════════════════════════════

if __name__ == "__main__":
    mcp.run()
