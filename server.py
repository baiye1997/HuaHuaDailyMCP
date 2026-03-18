"""
HuahuaDaily MCP Server (OpenClaw Skills)
=========================================
让 OpenClaw 等 AI agent 通过 MCP 协议直接访问花花日记的数据与功能。

配置方式：
  在 mcporter.json 的 mcpServers 中添加：
  {
    "huahua-daily": {
      "command": "uvx",
      "args": ["--from", "git+https://github.com/baiye1997/baiye-fund#subdirectory=mcp-server", "huahua-daily"],
      "env": {
        "BAIYE_AGENT_TOKEN": "从 App 设置页生成并复制的 Agent 令牌"
      }
    }
  }

认证说明：
  所有工具均需 Agent Token（PRO 会员专属功能）。
  通过环境变量 BAIYE_AGENT_TOKEN 配置（推荐），或运行时调用 set_token 工具。
  Agent Token 需在 App 设置页 → "Agent 访问令牌" 中生成（需邮箱验证，仅 PRO 会员可用）。
"""

import os
import json
import math
import asyncio
import time
from decimal import Decimal
from typing import Optional

import httpx
from mcp.server.fastmcp import FastMCP

# ── Session state ─────────────────────────────────────────────────────────────
_OFFICIAL_API = "https://huahua.preview.aliyun-zeabur.cn"

_session: dict = {
    "token": os.environ.get("BAIYE_AGENT_TOKEN", "").strip(),
    "base_url": _OFFICIAL_API,
}

mcp = FastMCP("huahua-daily")

# ── 连接池（模块级，整个 MCP session 复用同一个 client，避免每次请求重建 TCP 连接）─────
_http_client: Optional[httpx.AsyncClient] = None

def _get_client() -> httpx.AsyncClient:
    global _http_client
    if _http_client is None or _http_client.is_closed:
        _http_client = httpx.AsyncClient(
            timeout=30,
            limits=httpx.Limits(max_connections=5, max_keepalive_connections=2),
        )
    return _http_client

# ── Portfolio 内存缓存（TTL=30s，避免 get_summary 重复下载）─────────────────────
_portfolio_cache: dict = {"data": None, "ts": 0.0}
_PORTFOLIO_TTL = 30  # seconds
_download_lock: asyncio.Lock = asyncio.Lock()  # 防止并发调用时重复下载（双检锁模式）

# ── Estimates 内存缓存（TTL=60s，避免同 session 内多工具调用重复拉取相同基金估算）──────
_estimate_cache: dict = {}  # {code: {"data": {...}, "ts": float}}
_ESTIMATE_TTL = 60  # seconds

# ── Helpers ───────────────────────────────────────────────────────────────────

def _require_token() -> None:
    """所有工具（除 set_token）均须调用此函数，确保 Agent Token 已配置。"""
    if not _session["token"]:
        raise ValueError(
            "未配置 Agent Token。请在 mcporter.json 的 env 中设置 BAIYE_AGENT_TOKEN，"
            "或调用 set_token 工具。Agent Token 需在 App 设置页 →「Agent 访问令牌」中生成（PRO 会员专属）。"
        )

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
    try:
        r = await _get_client().get(_url(path), params=params, headers=_headers())
        if r.status_code == 401:
            raise ValueError("Agent Token 无效或已过期，请在 App 重新生成并更新配置。")
        if r.status_code == 403:
            raise ValueError("无访问权限，请确认 Agent Token 正确，且账号为 PRO 会员。")
        r.raise_for_status()
        return r.json()
    except ValueError:
        raise
    except httpx.TimeoutException:
        raise RuntimeError("请求超时，请稍后重试。")
    except httpx.HTTPStatusError as e:
        raise RuntimeError(f"服务器返回错误 {e.response.status_code}，请稍后重试。")

async def _post(path: str, body: dict = None) -> dict:
    try:
        r = await _get_client().post(_url(path), json=body or {}, headers=_headers())
        if r.status_code == 401:
            raise ValueError("Agent Token 无效或已过期，请在 App 重新生成并更新配置。")
        if r.status_code == 403:
            raise ValueError("无访问权限，请确认 Agent Token 正确，且账号为 PRO 会员。")
        r.raise_for_status()
        return r.json()
    except ValueError:
        raise
    except httpx.TimeoutException:
        raise RuntimeError("请求超时，请稍后重试。")
    except httpx.HTTPStatusError as e:
        raise RuntimeError(f"服务器返回错误 {e.response.status_code}，请稍后重试。")

async def _delete(path: str) -> dict:
    try:
        r = await _get_client().delete(_url(path), headers=_headers())
        if r.status_code == 401:
            raise ValueError("Agent Token 无效或已过期，请在 App 重新生成并更新配置。")
        if r.status_code == 403:
            raise ValueError("无访问权限，请确认 Agent Token 正确，且账号为 PRO 会员。")
        r.raise_for_status()
        return r.json()
    except ValueError:
        raise
    except httpx.TimeoutException:
        raise RuntimeError("请求超时，请稍后重试。")
    except httpx.HTTPStatusError as e:
        raise RuntimeError(f"服务器返回错误 {e.response.status_code}，请稍后重试。")


# ── 精度工具（严格对齐前端 _round，消除 IEEE 754 差异）───────────────────────────
#
# 前端 _round(v, d)：Number(`${Math.round(Number(`${v}e+${d}`))}e-${d}`)
#   1. `${v}` 先转字符串，再拼成指数形式后 Number() 解析，避免 IEEE 754 乘法漂移
#      （如 1.005*100 在 float 中实为 100.4999...，导致 round 结果偏低）
#   2. Math.round 向 +∞ 舍入（正数同四舍五入，负数 -.5 → 0）
#
# Python 对齐实现：
#   - Decimal(repr(v)) 利用 Python repr 给出精确字符串（同 JS `${v}`）
#   - * Decimal(10**d) 精确乘法，等效 Number(`${v}e+${d}`)
#   - math.floor(x + 0.5) 完全等同 JS Math.round

def _js_round(v: float, d: int) -> float:
    """精确对齐前端 _round(v, d)。"""
    try:
        shifted = float(Decimal(repr(v)) * Decimal(10 ** d))
        return math.floor(shifted + 0.5) / (10 ** d)
    except Exception:
        return round(v, d)

def _r2(v: float) -> float: return _js_round(v, 2)
def _r4(v: float) -> float: return _js_round(v, 4)
def _r6(v: float) -> float: return _js_round(v, 6)

def _r2_pct(holding_profit: float, cost_total: float) -> float:
    """
    对齐前端 returnRate：Math.round((holdingProfit / costTotal) * 10000) / 100。
    使用 math.floor(v + 0.5) 而非 int(v + 0.5)：
    - int() 向零截断，对负值行为与 JS Math.round 不同（负半数向 +∞ 舍入）
    - math.floor(x + 0.5) 精确复现 JS Math.round 的 round-half-toward-+∞ 语义
    示例：returnRate = -0.6% 时，int(-0.1)=0 给出 0%，floor(-0.1)=-1 给出 -0.01%（正确）
    """
    if cost_total <= 0:
        return 0.0
    try:
        v = holding_profit / cost_total
        return math.floor(v * 10000 + 0.5) / 100
    except Exception:
        return 0.0


# ── 收益计算（严格对齐前端 calculateFundStats 逻辑）──────────────────────────────

def _calc_fund_stats(fund: dict, est: Optional[dict] = None) -> dict:
    """
    计算单条记录的统计字段，逻辑对齐前端 calculateFundStats。

    关键对齐点：
    1. marketValue / holdingProfit / returnRate 均基于官方净值（lastNav），
       不受盘中估算影响（前端 getFundOfficialNav 的语义）。
    2. todayProfit = shares × (estimatedNav - prevNav)，用 prevNav（估算基准净值）
       而非 lastNav，避免 QDII / 新建仓场景下的偏差。
    3. 若 source == 'reset'（盘前重置）或 source == 'timeout'，忽略 estimatedNav，todayProfit = 0。
    4. returnRate 使用 _r2_pct 对齐前端 Math.round(v*10000)/100 语义。
    """
    shares: float = fund.get("holdingShares", 0) or 0
    cost_per_share: float = fund.get("holdingCost", 0) or 0
    last_nav: float = fund.get("lastNav", 0) or 0
    realized: float = fund.get("realizedProfit", 0) or 0

    # 估算信息（timeout 帧视同无估算，对齐前端拒收逻辑）
    est = est or {}
    source: str = est.get("source") or fund.get("source") or ""
    _ignore_est = source in ("reset", "timeout")
    estimated_nav_raw: float = est.get("estimatedNav") or est.get("nav") or 0
    estimated_nav: float = estimated_nav_raw if (estimated_nav_raw > 0 and not _ignore_est) else 0

    # prevNav：当日涨跌比较基准（前一交易日官方净值）
    # 估算接口返回字段名为 prev_dwjz（字符串），优先取实时值；
    # 降级顺序：est.prev_dwjz → est.prevNav(兼容) → fund.prevNav(云同步存储) → last_nav
    _prev_raw = est.get("prev_dwjz") or est.get("prevNav") or fund.get("prevNav") or 0
    try:
        prev_nav = float(_prev_raw) or last_nav
    except (TypeError, ValueError):
        prev_nav = last_nav

    # 官方净值（前端 getFundOfficialNav：lastNav > 0 ? lastNav : 1.0）
    official_nav: float = last_nav if last_nav > 0 else 1.0

    # ── 基于官方净值的稳定字段（对齐前端 currentMarketValue / holdingProfit）──
    cost_total = _r2(shares * cost_per_share)
    market_value = _r2(shares * official_nav)
    holding_profit = _r2(market_value - cost_total)
    total_profit = _r2(holding_profit + realized)
    return_rate = _r2_pct(holding_profit, cost_total)

    # ── 今日盈亏：estimatedNav vs prevNav（对齐前端 calculateFundDayProfit）──────
    if estimated_nav > 0 and prev_nav > 0 and shares > 0:
        today_profit = _r2((estimated_nav - prev_nav) * shares)
    else:
        today_profit = 0.0

    # 展示用净值：盘中优先展示估算，否则展示官方
    display_nav = estimated_nav if estimated_nav > 0 else official_nav

    return {
        "marketValue": market_value,
        "costPerShare": _r4(cost_per_share),
        "costTotal": cost_total,
        "holdingShares": _r6(shares),
        "holdingProfit": holding_profit,
        "realizedProfit": _r2(realized),
        "totalProfit": total_profit,
        "returnRate": return_rate,
        "todayProfit": today_profit,
        "currentNav": display_nav,
        "lastNav": official_nav,
        "estimatedNav": estimated_nav if estimated_nav > 0 else None,
        "estimatedChangePercent": est.get("estimatedChangePercent"),
    }


# ── Estimates 带缓存拉取（60s TTL，多工具共享，避免重复网络请求）──────────────────────

async def _fetch_estimates(codes: list) -> dict:
    """
    批量获取今日估算数据，60s 内存缓存。
    get_records() 和 get_item_estimate() 共用此函数，同 session 内不重复请求。
    缓存超过 500 条时自动清空，防止长时间运行内存膨胀。
    source='timeout' 的结果不写入缓存，避免后端瞬时超时污染后续请求。
    """
    now = time.monotonic()

    # 分离缓存命中 vs 需要请求
    result: dict = {}
    miss_codes: list = []
    for code in codes:
        entry = _estimate_cache.get(code)
        if entry and now - entry["ts"] < _ESTIMATE_TTL:
            result[code] = entry["data"]
        else:
            miss_codes.append(code)

    if not miss_codes:
        return result

    # 资源控制：条目过多时清空
    if len(_estimate_cache) > 500:
        _estimate_cache.clear()

    # 并行批量请求未命中的（每批 50 个）
    # return_exceptions=True 保证 gather 本身不会抛出，各批次异常通过 isinstance 判断处理
    batches = [miss_codes[i:i+50] for i in range(0, len(miss_codes), 50)]
    responses = await asyncio.gather(
        *[_post("/api/estimate/batch", {"codes": batch}) for batch in batches],
        return_exceptions=True,
    )
    for resp in responses:
        if isinstance(resp, Exception):
            continue
        batch_data = resp.get("data", resp) if isinstance(resp, dict) else resp
        if isinstance(batch_data, list):
            for item in batch_data:
                code_key = item.get("fundcode") or item.get("code")
                if not code_key:
                    continue
                # timeout 帧不缓存，避免污染后续 60s 内的查询
                if item.get("source") == "timeout":
                    result[code_key] = item
                else:
                    _estimate_cache[code_key] = {"data": item, "ts": now}
                    result[code_key] = item

    return result


# ═══════════════════════════════════════════════════════════════════════════════
# Tools: 认证类
# ═══════════════════════════════════════════════════════════════════════════════

@mcp.tool()
async def set_token(token: str) -> str:
    """
    手动设置 Agent Token（运行时配置）。
    推荐通过环境变量 BAIYE_AGENT_TOKEN 配置，无需调用此工具。

    Args:
        token: 从 App 设置页「Agent 访问令牌」中生成的令牌（PRO 会员专属）
    """
    _session["token"] = token.strip()
    return f"✅ Token 已设置，将连接官方后端：{_session['base_url']}"


@mcp.tool()
async def get_current_user() -> dict:
    """
    获取当前登录用户的账号信息（昵称、UID、会员状态等）。
    需要有效的 Agent Token（PRO 会员专属）。
    """
    _require_token()
    return await _get("/api/auth/me")


# ═══════════════════════════════════════════════════════════════════════════════
# Tools: 数据查询（需 Agent Token）
# ═══════════════════════════════════════════════════════════════════════════════

@mcp.tool()
async def search_item(query: str) -> list:
    """
    按编号或名称搜索项目，返回最多 20 条结果。
    仅在不知道基金代码时使用；若已知代码（如用户直接提供），可跳过此步骤直接查询。

    Args:
        query: 搜索关键词，如 "000001"、"华夏"
    """
    _require_token()
    data = await _get("/api/search", params={"key": query})
    return data if isinstance(data, list) else []


@mcp.tool()
async def get_item_detail(code: str) -> dict:
    """
    获取项目深度信息，包括历史收益率、胜率分析、完整净值序列、费率等。
    适合用户需要详细分析某只基金时调用；仅查询当前净值/涨跌请用 get_item_estimate，更轻量快速。

    Args:
        code: 项目编号，如 "000001"
    """
    _require_token()
    return await _get(f"/api/fund/{code}")


@mcp.tool()
async def get_item_estimate(codes: list[str]) -> dict:
    """
    批量获取项目今日实时估算净值（最多 50 个）。
    适合查询"现在涨了多少""今天净值多少"等日常行情问题，比 get_item_detail 轻量得多。
    结果在同一 session 内缓存 60 秒，与 get_records 共享缓存，无重复网络请求。

    Args:
        codes: 项目编号列表，如 ["000001", "110022"]，最多 50 个
    """
    _require_token()
    if len(codes) > 50:
        codes = codes[:50]
    estimate_map = await _fetch_estimates(codes)
    return {"data": list(estimate_map.values())}


@mcp.tool()
async def get_daily_rank() -> dict:
    """
    获取今日涨幅榜和跌幅榜。
    返回涨幅最大和跌幅最大的项目列表，以及板块概览。
    """
    _require_token()
    return await _get("/api/fund/today-rank")


@mcp.tool()
async def get_item_history(code: str) -> list:
    """
    获取项目历史净值数据（用于查看过去走势）。

    Args:
        code: 项目编号，如 "000001"
    """
    _require_token()
    data = await _get(f"/api/history/{code}")
    return data if isinstance(data, list) else []


@mcp.tool()
async def get_item_dividends(code: str) -> list:
    """
    获取项目历史派息记录。

    Args:
        code: 项目编号，如 "000001"
    """
    _require_token()
    data = await _get(f"/api/fund/dividends/{code}")
    return data if isinstance(data, list) else []


@mcp.tool()
async def get_fund_timeline(code: str) -> list:
    """
    获取指定项目今日分时估值走势（每隔几分钟一个数据点，盘中更新）。
    适合了解今日净值走势曲线，判断入场时机。
    非交易日或盘前返回空列表。

    Args:
        code: 项目编号，如 "000001"
    """
    _require_token()
    data = await _get(f"/api/fund/today-timeline/{code}")
    return data if isinstance(data, list) else []


@mcp.tool()
async def get_fund_fees(code: str) -> dict:
    """
    获取项目费率信息，包括申购费率、赎回费率、管理费率、托管费率等。
    在制定买卖决策时可参考手续费成本。

    Args:
        code: 项目编号，如 "000001"
    """
    _require_token()
    return await _get(f"/api/fund/fees/{code}")


@mcp.tool()
async def get_fund_period_rank(code: str) -> dict:
    """
    获取项目近期业绩排名，包含近 1 个月、3 个月、6 个月、1 年的收益率及同类排名百分位。
    适合评估基金经理和产品的中长期表现。

    Args:
        code: 项目编号，如 "000001"
    """
    _require_token()
    return await _get(f"/api/fund/period-rank/{code}")


# ═══════════════════════════════════════════════════════════════════════════════
# Tools: 概览数据（需 Agent Token）
# ═══════════════════════════════════════════════════════════════════════════════

@mcp.tool()
async def get_status() -> dict:
    """
    查询今日状态。
    返回 is_trading_day: true/false。
    """
    _require_token()
    return await _get("/api/market/status")


@mcp.tool()
async def get_overview() -> dict:
    """
    获取整体概览数据，包括主要指数涨跌、热门板块、涨跌排行。
    适合快速了解今日整体情况。
    """
    _require_token()
    return await _get("/api/market/overview")


@mcp.tool()
async def get_indices() -> list:
    """
    获取主要指数实时数据（上证、深证、创业板、沪深300、纳斯达克等）。
    """
    _require_token()
    data = await _get("/api/market/indices")
    return data if isinstance(data, list) else []


# ═══════════════════════════════════════════════════════════════════════════════
# Tools: 记录管理（需 Agent Token + 会员）
# ═══════════════════════════════════════════════════════════════════════════════

async def _download_portfolio() -> dict:
    """
    下载云同步数据并解析 JSON。
    使用 30s 内存缓存 + asyncio.Lock 双检锁，避免并发调用时发出重复下载请求。
    """
    now = time.monotonic()
    # 快速路径：缓存命中，无需加锁
    if _portfolio_cache["data"] is not None and now - _portfolio_cache["ts"] < _PORTFOLIO_TTL:
        return _portfolio_cache["data"]

    # 慢速路径：加锁后二次检查，确保只有一个协程执行下载和写入
    async with _download_lock:
        now = time.monotonic()
        if _portfolio_cache["data"] is not None and now - _portfolio_cache["ts"] < _PORTFOLIO_TTL:
            return _portfolio_cache["data"]

        raw = await _get("/api/sync/download")
        if not isinstance(raw, dict):
            raw = {}
        json_data = raw.get("json_data") or "{}"
        updated_at = raw.get("updated_at", "")
        try:
            parsed = json.loads(json_data)
            if not isinstance(parsed, dict):
                parsed = {}
        except Exception:
            parsed = {}

        parsed["_meta_updated_at"] = updated_at
        _portfolio_cache["data"] = parsed
        _portfolio_cache["ts"] = now
        return parsed


@mcp.tool()
async def get_records() -> dict:
    """
    获取用户持仓记录，并自动计算今日收益、累计收益、市值、收益率等字段。
    需要 Agent Token 且账号需开通会员才能使用云同步功能。

    数据来自最近一次云同步（dataUpdatedAt 字段）。若刚在 App 中刷新了净值或新增了交易，
    请先在 App 设置页手动触发"立即同步"后再查询，以获取最新数据。

    返回结构：
    - holdings: 有持仓的记录列表（含实时收益计算）
    - watchlist: 观察列记录（无持仓，仅供参考）
    - summary: 持仓汇总（总市值/今日收益/持有收益/持有收益率/累计收益/收益率/在途金额）
      - totalHoldingProfit: 持有收益总额（市值 - 成本，不含落袋/已实现收益）
      - totalHoldingReturnRate: 持有收益率（持有收益 / 成本 × 100%）
    - dataUpdatedAt: 云同步数据的最后更新时间（UTC），展示给用户让其知晓数据新鲜度
    """
    _require_token()
    # 1. 下载记录（有缓存时直接复用）
    portfolio = await _download_portfolio()
    funds: list = portfolio.get("funds", [])
    data_updated_at: str = portfolio.get("_meta_updated_at", "")

    # 2. 找出有持仓的项目编号
    held_codes = [f["code"] for f in funds if (f.get("holdingShares") or 0) > 0]

    # 3. 并行批量获取今日估算数值（共享 60s 缓存）
    estimate_map: dict = {}
    if held_codes:
        estimate_map = await _fetch_estimates(held_codes)

    # 4. 计算每条记录的收益字段，剥离原始 transactions（减少 token 消耗）
    holdings = []
    watchlist = []

    for fund in funds:
        code = fund.get("code", "")
        est = estimate_map.get(code, {})
        stats = _calc_fund_stats(fund, est)

        # 只保留对 AI 有用的字段，剥离原始交易记录（可能数百条）
        enriched = {
            "code": code,
            "name": fund.get("name", ""),
            "type": fund.get("type", ""),
            "groupId": fund.get("groupId", ""),
            "tags": fund.get("tags", []),
            **stats,
        }

        # 估算时间（来自后端 gztime 字段）
        if est:
            enriched["estimateTime"] = est.get("gztime", "")
            enriched["estimateSource"] = est.get("source", "")

        # 在途资产（PENDING 买入交易）
        txs = fund.get("transactions") or []
        pending_buy_txs = [
            {"date": tx.get("date"), "amount": tx.get("amount"), "note": tx.get("note")}
            for tx in txs if tx.get("status") == "PENDING" and tx.get("type") == "BUY"
        ]
        in_transit_amount = _r2(sum(tx.get("amount", 0) for tx in pending_buy_txs))
        enriched["inTransitAmount"] = in_transit_amount
        if pending_buy_txs:
            enriched["pendingBuyTransactions"] = pending_buy_txs

        if (fund.get("holdingShares") or 0) > 0:
            holdings.append(enriched)
        else:
            # 观察列只保留基础信息和行情，不需要收益字段
            watchlist.append({
                "code": code,
                "name": fund.get("name", ""),
                "type": fund.get("type", ""),
                "lastNav": fund.get("lastNav"),
                "estimatedNav": stats.get("estimatedNav"),
                "estimatedChangePercent": stats.get("estimatedChangePercent"),
            })

    # 5. 汇总统计（只统计持仓项目）
    # 使用迭代累加而非 sum-then-round，精确对齐前端 analytics.ts 的逐步 r2 模式：
    #   totalMarketValue = r2(totalMarketValue + r2(stats.currentMarketValue))
    # 各个 item 字段已是 _r2 值，累加时每步再 _r2 可消除多只基金累计的浮点漂移。
    total_market_value = 0.0
    total_cost = 0.0
    total_today_profit = 0.0
    total_holding_profit = 0.0
    total_cumulative_profit = 0.0
    total_in_transit = 0.0
    for f in holdings:
        total_market_value = _r2(total_market_value + f.get("marketValue", 0))
        total_cost = _r2(total_cost + f.get("costTotal", 0))
        total_today_profit = _r2(total_today_profit + f.get("todayProfit", 0))
        total_holding_profit = _r2(total_holding_profit + f.get("holdingProfit", 0))
        total_cumulative_profit = _r2(total_cumulative_profit + f.get("totalProfit", 0))
        total_in_transit = _r2(total_in_transit + f.get("inTransitAmount", 0))
    total_return_rate = _r2_pct(total_cumulative_profit, total_cost)
    total_holding_return_rate = _r2_pct(total_holding_profit, total_cost)

    return {
        "holdings": holdings,
        "watchlist": watchlist,
        "groups": portfolio.get("groups", []),
        "summary": {
            "totalMarketValue": total_market_value,
            "totalCost": total_cost,
            "todayProfit": total_today_profit,
            "totalHoldingProfit": total_holding_profit,
            "totalHoldingReturnRate": total_holding_return_rate,
            "cumulativeProfit": total_cumulative_profit,
            "totalReturnRate": total_return_rate,
            "heldItemCount": len(holdings),
            "totalInTransitAmount": total_in_transit,
        },
        "dataUpdatedAt": data_updated_at,
    }


@mcp.tool()
async def get_summary() -> dict:
    """
    获取持仓总览摘要（总市值、今日收益、累计收益、收益率）。
    比 get_records 更轻量，适合快速查询资产概况。

    返回的 dataUpdatedAt 字段表示云同步数据的更新时间，请将此时间告知用户，
    让其了解数据是否为最新（若时间较旧，提示用户在 App 触发同步）。
    """
    _require_token()
    result = await get_records()
    summary = result.get("summary", {})
    summary["dataUpdatedAt"] = result.get("dataUpdatedAt", "")
    return summary


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

    重要：调用前须向用户确认基金名称和代码无误，尤其是通过搜索推断出来的代码。
    发送后须告知用户"需在 App 中确认才会生效"，不要让用户误以为已执行。

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
    _require_token()
    tx_type = record_type.upper()
    if tx_type not in ("BUY", "SELL"):
        return "❌ record_type 必须是 'BUY' 或 'SELL'"

    payload = json.dumps({
        "code": item_code,
        "name": item_name,
        "amount": round(amount, 2),  # 保留两位小数，避免浮点序列化漂移（如 1000.0000000001）
        "date": date,
        "note": note,
    }, ensure_ascii=False)

    await _post("/api/agent/request", {"action_type": tx_type, "payload": payload})
    action = "买入" if tx_type == "BUY" else "卖出"
    return f"✅ {action}请求已发送：{item_name}（{item_code}）¥{amount:,.2f}，请打开 App 确认后生效。"


# ═══════════════════════════════════════════════════════════════════════════════
# Entry point
# ═══════════════════════════════════════════════════════════════════════════════

def main() -> None:
    """uvx / console_scripts 入口点。"""
    mcp.run()


if __name__ == "__main__":
    main()
