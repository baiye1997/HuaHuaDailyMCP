"""market MCP tool implementations."""

import asyncio  # noqa: F401
import json  # noqa: F401
import os  # noqa: F401
import re  # noqa: F401
import time  # noqa: F401
from typing import Optional  # noqa: F401

from .binding import bind_runtime

_RUNTIME_DEPENDENCIES = ("_get", "_post", "_require_token", "_validate_date", "_validate_fund_code")

if False:  # pragma: no cover - populated by bind() before tool registration
    _get = None
    _post = None
    _require_token = None
    _validate_date = None
    _validate_fund_code = None


def bind(runtime_globals: dict) -> None:
    bind_runtime(globals(), runtime_globals, _RUNTIME_DEPENDENCIES)


async def get_status() -> dict:
    """
    查询今日状态。
    返回 is_trading_day: true/false。
    """
    _require_token()
    return await _get("/api/market/status")


async def get_overview() -> dict:
    """
    获取整体概览数据，包括主要指数涨跌、热门板块、涨跌排行。
    适合快速了解今日整体情况。
    """
    _require_token()
    async def safe_get(name: str, path: str, params: dict = None):
        try:
            return name, await _get(path, params=params)
        except Exception as exc:
            return name, {"error": str(exc)}

    catalog = await _get("/api/market/indices/catalog")
    default_codes = catalog.get("defaultCodes", []) if isinstance(catalog, dict) else []
    default_codes = [str(code) for code in default_codes if code][:10]
    results = await asyncio.gather(
        safe_get("status", "/api/market/status"),
        safe_get("todayRank", "/api/fund/today-rank"),
        safe_get("sectorWind", "/api/market/sector-wind"),
        safe_get("yesterdayRank", "/api/market/yesterday-rank"),
        safe_get("indices", "/api/market/indices/latest", params={"codes": ",".join(default_codes)}) if default_codes else asyncio.sleep(0, result=("indices", {"quotes": []})),
    )
    overview = {name: value for name, value in results}
    overview["instrumentCatalog"] = catalog
    return overview


async def get_sector_wind() -> dict:
    """
    获取市场板块风向数据，包含领涨/领跌板块和数据时间。
    适合单独回答"今天哪些板块强/弱"。
    """
    _require_token()
    return await _get("/api/market/sector-wind")


async def get_yesterday_rank() -> dict:
    """
    获取上一交易日基金涨跌榜。
    适合回答"昨天哪些基金涨得多/跌得多"，或和今日榜做对比。
    """
    _require_token()
    return await _get("/api/market/yesterday-rank")


async def get_fund_flow() -> dict:
    """
    获取资金流向数据，包括主力资金流向和板块资金流向。
    需要 PRO 会员权限。适合回答"资金在流向哪里""哪些板块受追捧"等问题。

    Returns:
        dict 包含 fundFlow（基金资金流）、sectorFlow（板块资金流）、polledAt（数据时间）
    """
    _require_token()
    return await _get("/api/market/fund-flow")


async def get_indices() -> list:
    """
    获取主要指数实时数据（上证、深证、创业板、沪深300、纳斯达克等）。
    """
    _require_token()
    catalog = await _get("/api/market/indices/catalog")
    default_codes = catalog.get("defaultCodes", []) if isinstance(catalog, dict) else []
    code_str = ",".join(str(code) for code in default_codes if code)
    if not code_str:
        return []
    data = await _get("/api/market/indices/latest", params={"codes": code_str})
    return data.get("quotes", []) if isinstance(data, dict) else []


async def get_holder_ranking() -> dict:
    """
    获取 App 内持有人数排行榜（持有用户最多的 30 只基金）。
    返回每只基金的持有人数、最新涨跌幅，按涨幅排序。
    适合了解"大家都在买什么"的社区热度。
    """
    _require_token()
    return await _get("/api/market/holder-ranking")


async def get_night_estimate(codes: list[str], force: bool = False, view: str = "forecast") -> dict:
    """
    获取QDII基金的夜间实时估值（美股/港股盘后/盘前交易时段）。
    返回每只基金的盘后涨跌幅、持仓穿透明细、汇率变动等数据。
    仅在美股交易时段（北京时间夜间）数据有效，需要会员权限。

    Args:
        codes: 基金代码列表，如 ["016665", "018147"]，最多 50 个
        force: 是否强制刷新（跳过服务端缓存），默认 false
        view: forecast（预测口径）或 last_close（上一收盘快照口径）
    """
    _require_token()
    validated_codes = []
    seen = set()
    for code in codes[:50]:
        try:
            normalized = _validate_fund_code(code)
            if normalized not in seen:
                validated_codes.append(normalized)
                seen.add(normalized)
        except ValueError:
            continue
    if not validated_codes:
        return {"status": "empty", "items": []}
    code_str = ",".join(validated_codes)
    params = {"codes": code_str}
    if force:
        params["force"] = "true"
    if view in {"forecast", "last_close"}:
        params["view"] = view
    return await _get("/api/market/night-est", params=params)


async def get_benchmark_history(code: str = "sh000300") -> list:
    """
    获取指数或 ETF 的历史走势数据，用于与持仓基金进行基准对比。
    默认返回沪深300（sh000300）的历史数据。

    支持两类代码：
    - 指数代码：如 "sh000300"（沪深300）、"sh000001"（上证指数）、"sz399001"（深证成指）
    - ETF 代码（纯数字）：如 "510300"（沪深300ETF）

    适合回答"我的基金跑赢大盘了吗"、"与沪深300比较"等问题。

    Args:
        code: 指数或 ETF 代码，默认 "sh000300"（沪深300）
    """
    _require_token()
    normalized = str(code or "").strip().lower()
    # 验证格式：指数代码（sh/sz开头+6位数字）或 ETF 代码（6位数字）
    if not re.fullmatch(r'(sh|sz)\d{6}|\d{6}', normalized):
        raise ValueError(f"基准代码格式无效：{code}，应为 sh000300 或 510300 格式")
    data = await _get(f"/api/market/benchmark-history/{normalized}")
    return data if isinstance(data, list) else []


async def get_instrument_catalog() -> dict:
    """
    获取市场行情仪表盘的可选指数/ETF 目录。
    返回完整的标的分类列表和默认展示代码，用于了解可查询的指数/ETF 范围。
    """
    _require_token()
    return await _get("/api/market/indices/catalog")


async def get_instrument_quotes(codes: list[str]) -> dict:
    """
    批量获取指数/ETF 实时行情报价。
    适合同时查看多个指数的最新价格、涨跌幅。

    Args:
        codes: 标的代码列表，如 ["sh000300", "sh000001", "sz399001"]，最多 20 个
    """
    _require_token()
    validated = [str(c).strip() for c in (codes or [])[:20] if str(c).strip()]
    if not validated:
        return {"quotes": [], "polledAt": None}
    code_str = ",".join(validated)
    return await _get("/api/market/indices/latest", params={"codes": code_str})


async def get_instrument_timeline(code: str, range: str = "1d") -> dict:
    """
    获取单个指数/ETF 的分时走势（5 分钟 K 线）。
    适合了解今日盘中走势。

    Args:
        code: 标的代码，如 "sh000300"
        range: 时间范围，默认 "1d"（当日）
    """
    _require_token()
    normalized = str(code or "").strip()
    if not normalized:
        raise ValueError("标的代码不能为空")
    return await _get("/api/market/indices/timeline", params={"code": normalized, "range": range})


async def get_instrument_history(code: str, period: str = "1m") -> dict:
    """
    获取单个指数/ETF 的日线历史数据。
    适合分析中长期走势。

    Args:
        code: 标的代码，如 "sh000300"
        period: 时间周期，可选 "1m"（1个月）、"3m"（3个月）、"6m"（6个月）、"1y"（1年）
    """
    _require_token()
    normalized = str(code or "").strip()
    if not normalized:
        raise ValueError("标的代码不能为空")
    if period not in ("1m", "3m", "6m", "1y"):
        period = "1m"
    return await _get("/api/market/indices/history", params={"code": normalized, "period": period})


async def calculate_trading_dates(
    date: str,
    time_mode: str = "PRE_MARKET",
    confirm_days: int = 1,
) -> dict:
    """
    计算基金申赎的净值日、数据日、确认到账日（T+N 日期推算）。
    跳过周末和法定节假日，适合辅助用户规划买卖时机。

    Args:
        date: 操作日期，格式 "YYYY-MM-DD"
        time_mode: 操作时间段。
            "PRE_MARKET"（默认）= 当日收盘前买入，T 日起算；
            "POST_MARKET" = 收盘后买入，T+1 日起算
        confirm_days: 确认天数（即 T+N 的 N），常见值：
            1 = T+1（货币基金、部分债基）
            2 = T+2（多数股票型/混合型基金）
            3 = T+3（部分 QDII、特殊基金）

    Returns:
        dict 包含：
            nav_date: 净值日（基金以哪天净值计算）
            data_date: 数据日（净值数据公布日）
            confirm_date: 确认到账日（份额/资金到账日）
    """
    _require_token()
    validated_date = _validate_date(date)
    if time_mode not in ("PRE_MARKET", "POST_MARKET"):
        raise ValueError(f"time_mode 必须是 PRE_MARKET 或 POST_MARKET，收到：{time_mode}")
    if not (1 <= confirm_days <= 30):
        raise ValueError(f"confirm_days 必须在 1-30 之间，收到：{confirm_days}")
    return await _post("/api/market/calculate-dates", {
        "date": validated_date,
        "time_mode": time_mode,
        "confirm_days": confirm_days,
    })


async def get_next_trading_day(date: str) -> dict:
    """
    获取指定日期起（含当日）的下一个交易日，自动跳过周末和法定节假日。
    适合回答"元旦后第一个交易日是哪天"、"这个日期能买基金吗"等问题。

    Args:
        date: 起始日期，格式 "YYYY-MM-DD"

    Returns:
        dict 包含 date 字段，值为下一个交易日日期（"YYYY-MM-DD"）
    """
    _require_token()
    validated_date = _validate_date(date)
    return await _get("/api/market/next-trading-day", params={"date": validated_date})
