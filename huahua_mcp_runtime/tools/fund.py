"""fund MCP tool implementations."""

import asyncio  # noqa: F401
import json  # noqa: F401
import os  # noqa: F401
import re  # noqa: F401
import time  # noqa: F401
from typing import Optional  # noqa: F401

from .binding import bind_runtime

_RUNTIME_DEPENDENCIES = ("_fetch_estimates", "_get", "_normalize_data_source_mode", "_post", "_require_token", "_validate_fund_code")

if False:  # pragma: no cover - populated by bind() before tool registration
    _fetch_estimates = None
    _get = None
    _normalize_data_source_mode = None
    _post = None
    _require_token = None
    _validate_fund_code = None


def bind(runtime_globals: dict) -> None:
    bind_runtime(globals(), runtime_globals, _RUNTIME_DEPENDENCIES)


async def search_item(query: str) -> list:
    """
    按编号或名称搜索项目，返回最多 20 条结果。
    仅在不知道基金代码时使用；若已知代码（如用户直接提供），可跳过此步骤直接查询。

    Args:
        query: 搜索关键词，如 "000001"、"华夏"
    """
    _require_token()
    normalized = str(query or "").strip()
    if not normalized:
        raise ValueError("搜索关键词不能为空")
    if len(normalized) > 100:
        raise ValueError("搜索关键词过长，最多 100 字符")
    data = await _get("/api/search", params={"key": normalized})
    return data if isinstance(data, list) else []


async def get_item_detail(code: str) -> dict:
    """
    获取项目深度信息，包括历史收益率、胜率分析、完整净值序列、费率等。
    适合用户需要详细分析某只基金时调用；仅查询当前净值/涨跌请用 get_item_estimate，更轻量快速。

    Args:
        code: 项目编号，如 "000001"
    """
    _require_token()
    validated_code = _validate_fund_code(code)
    return await _get(f"/api/fund/{validated_code}")


async def get_item_estimate(
    codes: list[str],
    default_data_source_mode: str = "huahua",
    data_source_mode_by_code: Optional[dict] = None,
) -> dict:
    """
    批量获取项目今日实时估算净值（最多 50 个）。
    适合查询"现在涨了多少""今天净值多少"等日常行情问题，比 get_item_detail 轻量得多。
    结果在同一 session 内缓存 60 秒，与 get_records 共享缓存，无重复网络请求。
    支持新版后端多行情源：default_data_source_mode / data_source_mode_by_code。

    Args:
        codes: 项目编号列表，如 ["000001", "110022"]，最多 50 个
        default_data_source_mode: 默认行情源模式：huahua/a/b/c。
        data_source_mode_by_code: 可选，每只基金单独指定行情源模式。
    """
    _require_token()
    # 验证并去重基金代码
    validated_codes = []
    seen = set()
    for code in codes[:50]:
        try:
            normalized = _validate_fund_code(code)
            if normalized not in seen:
                validated_codes.append(normalized)
                seen.add(normalized)
        except ValueError:
            continue  # 跳过无效代码
    if not validated_codes:
        return {"data": []}
    estimate_map = await _fetch_estimates(
        validated_codes,
        default_data_source_mode=default_data_source_mode,
        data_source_mode_by_code=data_source_mode_by_code,
    )
    return {"data": list(estimate_map.values())}


async def get_fund_source_previews(code: str) -> dict:
    """
    获取单只基金在多个行情源下的实时估算预览。
    适合用户询问"不同数据源现在差多少"或需要选择基金级 dataSourceMode 时调用。

    Args:
        code: 项目编号，如 "000001"

    Returns:
        dict 包含 code 和 data，其中 data 通常是 huahua/a/b/c 到估算帧的映射。
    """
    _require_token()
    validated_code = _validate_fund_code(code)
    return await _get(f"/api/estimate/source-previews/{validated_code}")


async def get_daily_rank() -> dict:
    """
    获取今日涨幅榜和跌幅榜。
    返回涨幅最大和跌幅最大的项目列表，以及板块概览。
    """
    _require_token()
    return await _get("/api/fund/today-rank")


async def get_item_history(code: str) -> list:
    """
    获取项目历史净值数据（用于查看过去走势）。

    Args:
        code: 项目编号，如 "000001"
    """
    _require_token()
    validated_code = _validate_fund_code(code)
    data = await _get(f"/api/history/{validated_code}")
    return data if isinstance(data, list) else []


async def get_item_dividends(code: str) -> list:
    """
    获取项目历史派息记录。

    Args:
        code: 项目编号，如 "000001"
    """
    _require_token()
    validated_code = _validate_fund_code(code)
    data = await _get(f"/api/fund/dividends/{validated_code}")
    return data if isinstance(data, list) else []


async def get_fund_timeline(code: str, source_mode: str = "huahua") -> list:
    """
    获取指定项目今日分时估值走势（每隔几分钟一个数据点，盘中更新）。
    适合了解今日净值走势曲线，判断入场时机。
    非交易日或盘前返回空列表。

    Args:
        code: 项目编号，如 "000001"
        source_mode: 行情源模式：huahua/a/b/c。
    """
    _require_token()
    validated_code = _validate_fund_code(code)
    data = await _get(
        f"/api/fund/today-timeline/{validated_code}",
        params={"sourceMode": _normalize_data_source_mode(source_mode)},
    )
    return data if isinstance(data, list) else []


async def get_fund_fees(code: str) -> dict:
    """
    获取项目交易规则，包括确认天数、申购状态、QDII/限大额日累计限购金额等。
    在制定买卖决策时可参考确认周期、限购状态和手续费成本。

    Args:
        code: 项目编号，如 "000001"
    """
    _require_token()
    validated_code = _validate_fund_code(code)
    return await _get(f"/api/fund/fees/{validated_code}")


async def get_batch_fund_fees(codes: list[str]) -> dict:
    """
    批量获取基金费率、申购状态、限购规则。最多 50 个代码。
    适合配合 get_purchase_limit_watchlist 一次性检查限购观察列表。

    Args:
        codes: 6 位基金代码列表。
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
        return {"data": {}, "truncated": False, "limit": 50}
    return await _post("/api/fund/fees/batch", {"codes": validated_codes})


async def get_fund_period_rank(code: str) -> dict:
    """
    获取项目近期业绩排名，包含近 1 个月、3 个月、6 个月、1 年的收益率及同类排名百分位。
    适合评估基金经理和产品的中长期表现。

    Args:
        code: 项目编号，如 "000001"
    """
    _require_token()
    validated_code = _validate_fund_code(code)
    return await _get(f"/api/fund/period-rank/{validated_code}")


async def get_fund_profile(code: str) -> dict:
    """
    获取基金画像，包含基本信息、费率、业绩排名、持仓、行业分布、分红、风险指标等综合数据。
    比 get_item_detail 更聚焦于基金本身的静态属性，适合深度分析和对比。

    Args:
        code: 项目编号，如 "000001"
    """
    _require_token()
    validated_code = _validate_fund_code(code)
    return await _get(f"/api/fund/profile/{validated_code}")


async def get_batch_fund_profiles(codes: list[str]) -> dict:
    """
    批量获取多只基金的画像数据，返回 code → 画像的映射。
    适合同时对比多只基金的基本面，一次最多 20 只。

    Args:
        codes: 项目编号列表，如 ["000001", "161725"]，最多 20 个
    """
    _require_token()
    validated_codes = []
    seen = set()
    for code in codes[:20]:
        try:
            normalized = _validate_fund_code(code)
            if normalized not in seen:
                validated_codes.append(normalized)
                seen.add(normalized)
        except ValueError:
            continue
    if not validated_codes:
        return {}
    payload = await _post("/api/fund/profile/batch", {"codes": validated_codes})
    return payload.get("data", {}) if isinstance(payload, dict) else {}


async def get_batch_fund_period_ranks(codes: list[str]) -> dict:
    """
    批量获取多个项目的近期业绩排名，返回 code → 排名数据的映射。
    一次请求处理最多 50 个项目，适合同时查看多个项目的表现对比。

    Args:
        codes: 项目编号列表，如 ["000001", "161725"]，最多 50 个
    """
    _require_token()
    # 验证并去重基金代码
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
        return {}
    payload = await _post("/api/fund/period-rank/batch", {"codes": validated_codes})
    return payload.get("data", {}) if isinstance(payload, dict) else {}
