"""fund MCP tool implementations."""

import asyncio  # noqa: F401
import json  # noqa: F401
import os  # noqa: F401
import re  # noqa: F401
import time  # noqa: F401
from typing import Optional  # noqa: F401

from .binding import bind_runtime
from ..quant_validation import (
    validate_quant_current_frame as _validate_quant_current_frame,
    validate_quant_view as _validate_quant_view,
)

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
    获取单只基金的基础详情与持仓信息。
    本工具不触发量化指标或历史统计计算；量化数据请按需调用
    get_fund_quant_metrics，当前净值/涨跌请调用 get_item_estimate。

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
    适合查询"现在涨了多少""今天净值多少"等日常行情问题，不会附带量化计算。
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
    批量获取多只基金的画像数据，一次最多 20 只。
    返回 data（code → 画像）、complete、missingCodes、timedOut；
    适合同时对比多只基金的基本面，并显式识别部分结果。

    Args:
        codes: 项目编号列表，如 ["000001", "161725"]，最多 20 个
    """
    _require_token()
    validated_codes = []
    seen = set()
    for code in codes:
        normalized = _validate_fund_code(code)
        if normalized not in seen:
            validated_codes.append(normalized)
            seen.add(normalized)
    if len(validated_codes) > 20:
        raise ValueError("codes 最多支持 20 只基金")
    if not validated_codes:
        return {
            "data": {},
            "requestedCodes": [],
            "missingCodes": [],
            "complete": True,
            "timedOut": False,
        }
    payload = await _post("/api/fund/profile/batch", {"codes": validated_codes})
    return payload if isinstance(payload, dict) else {
        "data": {},
        "requestedCodes": validated_codes,
        "missingCodes": validated_codes,
        "complete": False,
        "timedOut": False,
    }


async def get_fund_quant_metrics(
    code: str,
    view: str,
    technical_value: Optional[float] = None,
    value_basis: str = "official_nav",
    value_as_of: str = "",
    source: str = "",
    target_nav_date: str = "",
    latest_official_nav_date: str = "",
    estimate_freshness: str = "",
    estimate_stale: Optional[bool] = None,
    fallback_reason: str = "",
    last_good_captured_at: str = "",
) -> dict:
    """
    按语义视图获取单只基金由后端统一计算的量化数据。
    technical=技术卡与历史统计；momentum=短中期收益/均线偏离/连跌；
    risk=中长期收益/回撤/波动；full=完整数据。必须按问题选择视图。
    默认使用最新官方净值；如已通过 get_item_estimate 取得盘中估算值，可传
    technical_value 和 value_basis="live_estimate"，避免 Agent 拉取净值历史重复计算。
    本工具只提供数据与统计，不输出买卖方向或建议金额。

    Args:
        code: 6 位基金代码。
        view: technical、momentum、risk 或 full；不要无条件使用 full。
        technical_value: 可选，当前有效估算净值；不传则使用官方净值口径。
        value_basis: official_nav 或 live_estimate。
        value_as_of: 当前值归属/观察日期，建议使用估算帧的 display_date。
        source: 当前值的数据源标识。
        target_nav_date: 当前估算帧对应的目标净值 D 日。
        latest_official_nav_date: 已公布的最新官方净值 D 日。
        estimate_freshness: 对应估算帧的 fresh、stale 或 unavailable 状态。
        estimate_stale: 对应估算帧是否来自陈旧兜底。
        fallback_reason: 估算帧发生降级时的原因。
        last_good_captured_at: last-good 估算帧的 ISO 8601 捕获时间。
    """
    _require_token()
    validated_code = _validate_fund_code(code)
    validated_view = _validate_quant_view(view)
    has_current_frame = any((
        technical_value is not None,
        value_basis != "official_nav",
        value_as_of,
        source,
        target_nav_date,
        latest_official_nav_date,
        estimate_freshness,
        estimate_stale is not None,
        fallback_reason,
        last_good_captured_at,
    ))
    if has_current_frame and validated_view not in {"technical", "full"}:
        raise ValueError("当前估算帧仅适用于 technical 或 full 视图")
    frame = _validate_quant_current_frame({
        "valueBasis": value_basis,
        **({"technicalValue": technical_value} if technical_value is not None else {}),
        **({"valueAsOf": value_as_of} if value_as_of else {}),
        **({"source": source} if source else {}),
        **({"targetNavDate": target_nav_date} if target_nav_date else {}),
        **({"latestOfficialNavDate": latest_official_nav_date} if latest_official_nav_date else {}),
        **({"estimateFreshness": estimate_freshness} if estimate_freshness else {}),
        **({"estimateStale": estimate_stale} if estimate_stale is not None else {}),
        **({"fallbackReason": fallback_reason} if fallback_reason else {}),
        **({"lastGoodCapturedAt": last_good_captured_at} if last_good_captured_at else {}),
    }) if validated_view in {"technical", "full"} else {}
    params = {"view": validated_view, **frame}
    return await _get(f"/api/fund/quant-metrics/{validated_code}", params=params)


async def get_batch_fund_quant_metrics(
    codes: list[str],
    view: str,
    current_frames: Optional[dict] = None,
) -> dict:
    """
    批量获取后端统一量化数据。technical、momentum、risk 最多 50 只，
    full 最多 10 只。服务端按视图加载依赖并批量读缓存/数据库；
    不要为每只基金并发调用单只接口。本工具不输出投资建议。
    顶层 complete 只表示所有代码至少有一条官方净值；指标视图的 251 点窗口检查
    item.metrics.complete，full 检查 item.official.metrics.complete；历史统计检查
    item.current.status。computing 可按 retryAfterMs 稍后重试，
    insufficient_history / insufficient_samples 是当前数据集下的终态。

    Args:
        codes: 6 位基金代码列表，最多 50 只；非法代码会直接报错。
        view: technical、momentum、risk 或 full；不要无条件使用 full。
        current_frames: 可选，code 到当前估算帧的映射；字段使用 technicalValue、
            valueBasis、valueAsOf、source、targetNavDate、latestOfficialNavDate，及可选的
            estimateFreshness、estimateStale、fallbackReason、lastGoodCapturedAt。
    """
    _require_token()
    validated_view = _validate_quant_view(view)
    if len(codes) > 50:
        raise ValueError("codes 最多支持 50 只基金")
    validated_codes = []
    seen = set()
    for code in codes:
        normalized = _validate_fund_code(code)
        if normalized not in seen:
            validated_codes.append(normalized)
            seen.add(normalized)
    if not validated_codes:
        raise ValueError("codes 不能为空")
    if validated_view == "full" and len(validated_codes) > 10:
        raise ValueError("full 视图批量请求最多支持 10 只基金")
    if current_frames is not None and not isinstance(current_frames, dict):
        raise ValueError("current_frames 必须是对象")
    normalized_frames = current_frames or {}
    if normalized_frames and validated_view not in {"technical", "full"}:
        raise ValueError("current_frames 仅适用于 technical 或 full 视图")
    unexpected = set(normalized_frames) - set(validated_codes)
    if unexpected:
        raise ValueError("current_frames 只能包含本次请求的基金代码")
    normalized_frames = {
        code: _validate_quant_current_frame(frame)
        for code, frame in normalized_frames.items()
    }
    return await _post(
        "/api/fund/quant-metrics/batch",
        {
            "codes": validated_codes,
            "view": validated_view,
            "currentFrames": normalized_frames,
        },
    )


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
