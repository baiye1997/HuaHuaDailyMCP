"""portfolio MCP tool implementations."""

import asyncio  # noqa: F401
import json  # noqa: F401
import os  # noqa: F401
import re  # noqa: F401
import time  # noqa: F401
from typing import Optional  # noqa: F401

from .binding import RuntimeCallable, bind_runtime

_RUNTIME_DEPENDENCIES = ("_calc_fund_stats", "_download_portfolio", "_download_portfolio_raw", "_fetch_estimates", "_get", "_is_valid_fund_code_value", "_normalize_data_source_mode", "_portfolio_payload_source", "_post", "_put", "_r2", "_ratio_pct", "_require_token", "_to_float", "_unwrap_sync_payload", "_validate_amount", "_validate_date", "_validate_fund_code")

if False:  # pragma: no cover - populated by bind() before tool registration
    _calc_fund_stats = None
    _download_portfolio = None
    _download_portfolio_raw = None
    _fetch_estimates = None
    _get = None
    _is_valid_fund_code_value = None
    _normalize_data_source_mode = None
    _portfolio_payload_source = None
    _post = None
    _put = None
    _r2 = None
    _ratio_pct = None
    _require_token = None
    _to_float = None
    _unwrap_sync_payload = None
    _validate_amount = None
    _validate_date = None
    _validate_fund_code = None
    _runtime_get_records = None


def bind(runtime_globals: dict) -> None:
    bind_runtime(globals(), runtime_globals, _RUNTIME_DEPENDENCIES)
    globals()["_runtime_get_records"] = RuntimeCallable(runtime_globals, "get_records")


async def get_night_watchlist() -> dict:
    """
    获取用户在 App「夜盘估值」页面手动添加的基金代码列表。

    数据来自云端实时同步主数据的 nightWatchCodes 字段；典型用法是把
    返回的 codes 作为参数传给 get_night_estimate，实现 "拉取用户自选
    夜盘基金的最新估值" 的端到端调用，无需用户在对话中手动报代码。

    Returns:
        dict 包含：
        - codes: 用户添加的 6 位基金代码列表（list[str]）
        - count: 代码数量
        - has_customized: 用户是否自定义过（False 表示用户从未修改，
          App 端会回退到内置默认列表；此时返回的 codes 为空，Agent
          可以提示用户先去 App 添加夜盘自选）
        - dataUpdatedAt: 云端实时同步主数据时间
    """
    _require_token()
    portfolio = await _download_portfolio()
    raw = portfolio.get("nightWatchCodes")
    has_customized = isinstance(raw, list)
    codes = [str(c) for c in raw if c] if has_customized else []
    return {
        "codes": codes,
        "count": len(codes),
        "has_customized": has_customized,
        "dataUpdatedAt": portfolio.get("_meta_updated_at", ""),
    }


async def get_purchase_limit_watchlist() -> dict:
    """
    获取用户在 App「限购观察」中保存的基金列表。

    数据来自云端实时同步主数据的 purchaseLimitWatchItems 字段。新版 App 会把
    夜盘默认基金并入限购观察列表；旧版本或尚未同步过该功能的主数据可能没有此字段。

    Returns:
        dict 包含：
        - items: 观察项列表，含 code/name/type/addedAt/snapshot
        - codes: 6 位基金代码列表，可传给 get_fund_fees 批量检查申购状态
        - count: 观察项数量
        - has_customized: 云端主数据是否包含该字段
        - dataUpdatedAt: 云端实时同步主数据时间
    """
    _require_token()
    portfolio = await _download_portfolio()
    raw = portfolio.get("purchaseLimitWatchItems")
    has_customized = isinstance(raw, list)
    items = []
    seen = set()
    if has_customized:
        for item in raw:
            if not isinstance(item, dict):
                continue
            code = str(item.get("code") or "").strip()
            if not _is_valid_fund_code_value(code) or code in seen:
                continue
            seen.add(code)
            items.append({
                "code": code,
                "name": str(item.get("name") or "").strip(),
                "type": str(item.get("type") or "").strip(),
                "addedAt": item.get("addedAt") or "",
                "snapshot": item.get("snapshot") if isinstance(item.get("snapshot"), dict) else None,
            })
    return {
        "items": items,
        "codes": [item["code"] for item in items],
        "count": len(items),
        "has_customized": has_customized,
        "dataUpdatedAt": portfolio.get("_meta_updated_at", ""),
    }


async def get_sync_meta() -> dict:
    """
    获取云端实时同步主数据元信息，不下载完整数据。
    返回 updated_at、etag、size_bytes 和历史快照摘要，用于判断 App 数据是否已经同步到云端。
    """
    _require_token()
    meta = await _get("/api/sync/meta")
    if isinstance(meta, dict):
        restorable_count = int(meta.get("restorable_fund_count") or 0)
        empty_confirmed = meta.get("empty_portfolio_confirmed") is True
        has_empty_tombstone = (
            empty_confirmed
            and meta.get("has_funds_array") is True
            and int(meta.get("fund_count") or 0) == 0
        )
        meta["has_restorable_sync_payload"] = restorable_count > 0 or has_empty_tombstone
        meta["data_source"] = _portfolio_payload_source(meta)
        meta["history_snapshot"] = {
            "latest_snapshot_created_at": meta.get("latest_snapshot_created_at"),
            "latest_snapshot_etag": meta.get("latest_snapshot_etag"),
            "latest_snapshot_source": meta.get("latest_snapshot_source"),
        }
    return meta


async def get_raw_sync_data(include_json_text: bool = False) -> dict:
    """
    获取完整云端实时同步主数据。默认返回解析后的 JSON，不返回原始 JSON 字符串以节省上下文。

    实时同步主数据包含 funds、groups、watchlistGroups、globalTags、字段显示配置、
    nightWatchCodes、purchaseLimitWatchItems、marketIndexSelection 等。
    profit ledger 是 App 可由交易记录和历史净值重建的派生数据；当前主数据通常不包含 ledger。

    Args:
        include_json_text: 是否同时返回服务端原始 json_data 字符串；只有做导出/迁移审计时才建议开启。
    """
    _require_token()
    raw, source = await _download_portfolio_raw()
    parsed = _unwrap_sync_payload(raw if isinstance(raw, dict) else {}, source=source)
    result = {
        "data": {k: v for k, v in parsed.items() if not k.startswith("_meta_")},
        "meta": {
            "updated_at": parsed.get("_meta_updated_at", ""),
            "etag": parsed.get("_meta_etag", ""),
            "data_source": parsed.get("_meta_data_source", source),
            "size_bytes": parsed.get("_meta_size_bytes", 0),
            "contains_ledger": "ledger" in parsed,
            "contains_archived_ledger": "archivedLedger" in parsed,
            **parsed.get("_meta_summary", {}),
        },
    }
    if include_json_text:
        result["json_data"] = raw.get("json_data", "") if isinstance(raw, dict) else ""
    return result


async def get_transactions(code: str = "", include_pending: bool = True) -> dict:
    """
    获取云端实时同步主数据中的交易流水。默认返回全部基金；传入 code 时只返回该基金。

    Args:
        code: 可选，6 位基金代码。
        include_pending: 是否包含待确认交易。
    """
    _require_token()
    # 验证基金代码（如果提供）
    validated_code = ""
    if code:
        validated_code = _validate_fund_code(code)
    portfolio = await _download_portfolio()
    funds = portfolio.get("funds", [])
    items = []
    for fund in funds:
        if validated_code and str(fund.get("code", "")) != validated_code:
            continue
        txs = fund.get("transactions") or []
        if not include_pending:
            txs = [tx for tx in txs if tx.get("status") == "CONFIRMED"]
        items.append({
            "code": fund.get("code", ""),
            "name": fund.get("name", ""),
            "groupId": fund.get("groupId", ""),
            "transactions": txs,
        })
    return {
        "items": items,
        "dataUpdatedAt": portfolio.get("_meta_updated_at", ""),
    }


async def get_groups() -> dict:
    """
    获取持仓分组和自选分组。
    """
    _require_token()
    portfolio = await _download_portfolio()
    return {
        "groups": portfolio.get("groups", []),
        "watchlistGroups": portfolio.get("watchlistGroups", []),
        "dataUpdatedAt": portfolio.get("_meta_updated_at", ""),
    }


async def get_tags() -> dict:
    """
    获取全局标签注册表，以及每只基金绑定的标签。
    """
    _require_token()
    portfolio = await _download_portfolio()
    funds = portfolio.get("funds", [])
    return {
        "globalTags": portfolio.get("globalTags", []),
        "fundTags": [
            {
                "code": fund.get("code", ""),
                "name": fund.get("name", ""),
                "tags": fund.get("tags", []),
                "visibleTags": fund.get("visibleTags", []),
            }
            for fund in funds
        ],
        "dataUpdatedAt": portfolio.get("_meta_updated_at", ""),
    }


async def get_records(include_transactions: bool = False) -> dict:
    """
    获取用户持仓记录，并自动计算今日收益、持有收益、累计收益、市值、持有收益率等字段。
    需要 Agent Token 且账号需开通会员才能使用云端实时同步数据。

    数据来自云端实时同步主数据（dataUpdatedAt 字段）。若刚在 App 中刷新了净值或新增了交易，
    请先确认 App 实时同步已完成后再查询，以获取最新数据。

    返回结构：
    - holdings: 有持仓的记录列表（含实时收益计算）
    - watchlist: 观察列记录（无持仓，仅供参考）
    - summary: 持仓汇总（总市值/今日收益/持有收益/持有收益率/累计收益/在途金额）
      - todayProfitRate: 今日/昨日收益率（todayProfit / totalDayBaseMarketValue × 100%，分母为归属日组合期初市值）
      - totalDayBaseMarketValue: 今日/昨日收益率使用的组合期初市值
      - totalHoldingProfit: 持有收益总额（市值 - 成本，不含落袋/已实现收益）
      - totalHoldingReturnRate: 持有收益率（totalHoldingProfit / totalCost × 100%，仅反映浮动亏盈）
      - cumulativeProfit: 累计收益（持有收益 + 已实现收益，含落袋；不代表用户所有平台/历史交易的完整累计）
    - dataUpdatedAt: 云端实时同步主数据的最后更新时间（UTC），展示给用户让其知晓数据新鲜度
    - strategyPreferences.maxDrawdownLimitPct: 用户设置的组合回撤阈值百分数；0 表示未启用

    Args:
        include_transactions: 是否在每条记录中附带原始 transactions。默认 false 以节省上下文。
            需要审计交易流水、重算收益或排查数据时设为 true。
    """
    _require_token()
    # 下载记录并复用缓存。
    portfolio = await _download_portfolio()
    funds: list = portfolio.get("funds", [])
    data_updated_at: str = portfolio.get("_meta_updated_at", "")
    data_source: str = portfolio.get("_meta_data_source", "")
    snapshot_summary: dict = portfolio.get("_meta_summary", {})
    user_preferences = portfolio.get("userPreferences") if isinstance(portfolio.get("userPreferences"), dict) else {}
    try:
        max_drawdown_limit_pct = float(user_preferences.get("strategyMaxDrawdownLimitPct", 10))
    except (TypeError, ValueError):
        max_drawdown_limit_pct = 10.0
    if max_drawdown_limit_pct != 0 and not 5 <= max_drawdown_limit_pct <= 30:
        max_drawdown_limit_pct = 10.0

    # 2. 找出有持仓的项目编号
    held_codes = [f["code"] for f in funds if (f.get("holdingShares") or 0) > 0]

    # 3. 并行批量获取今日估算数值（共享 60s 缓存）
    estimate_map: dict = {}
    if held_codes:
        default_mode = _normalize_data_source_mode(user_preferences.get("fundDataSourceMode"))
        mode_by_code = {}
        for fund in funds:
            code = str(fund.get("code") or "").strip()
            if not _is_valid_fund_code_value(code):
                continue
            fund_mode = fund.get("dataSourceMode")
            if fund_mode or code not in mode_by_code:
                mode_by_code[code] = _normalize_data_source_mode(fund_mode or default_mode)
        estimate_map = await _fetch_estimates(
            held_codes,
            default_data_source_mode=default_mode,
            data_source_mode_by_code=mode_by_code,
        )

    # 4. 计算每条记录的收益字段，剥离原始 transactions（减少 token 消耗）
    holdings = []
    watchlist = []

    for fund in funds:
        code = fund.get("code", "")
        est = estimate_map.get(code, {})
        stats = _calc_fund_stats(fund, est)
        txs = fund.get("transactions") or []

        # 响应仅保留汇总字段，不返回原始交易明细。
        enriched = {
            "code": code,
            "name": fund.get("name", ""),
            "type": fund.get("type", ""),
            "groupId": fund.get("groupId", ""),
            "tags": fund.get("tags", []),
            **stats,
        }
        if include_transactions:
            enriched["transactions"] = txs

        # 估算时间（来自后端 gztime 字段）
        if est:
            enriched["estimateTime"] = est.get("gztime", "")
            enriched["estimateSource"] = est.get("source", "")

        # 在途资产（PENDING 买入交易）
        pending_buy_txs = [
            {"date": tx.get("date"), "amount": tx.get("amount"), "note": tx.get("note")}
            for tx in txs if tx.get("status") == "PENDING" and tx.get("type") == "BUY"
        ]
        in_transit_amount = _r2(sum(_to_float(tx.get("amount")) for tx in pending_buy_txs))
        enriched["inTransitAmount"] = in_transit_amount
        if pending_buy_txs:
            enriched["pendingBuyTransactions"] = pending_buy_txs

        if (fund.get("holdingShares") or 0) > 0:
            holdings.append(enriched)
        else:
            # 观察列仅包含基础信息和行情。
            watchlist.append({
                "code": code,
                "name": fund.get("name", ""),
                "type": fund.get("type", ""),
                "lastNav": stats.get("lastNav"),
                "estimatedNav": stats.get("estimatedNav"),
                "estimatedChangePercent": stats.get("estimatedChangePercent"),
                **({"transactions": txs} if include_transactions else {}),
            })

    # 5. 汇总统计（只统计持仓项目）
    # 使用迭代累加而非 sum-then-round，精确对齐前端 analytics.ts 的逐步 r2 模式：
    #   totalMarketValue = r2(totalMarketValue + r2(stats.currentMarketValue))
    # 逐步舍入用于限制多基金累加的浮点误差。
    total_market_value = 0.0
    total_cost = 0.0
    total_today_profit = 0.0
    total_holding_profit = 0.0
    total_cumulative_profit = 0.0
    total_in_transit = 0.0
    total_invested = 0.0
    total_day_base_market_value = 0.0
    attributable_count = 0
    updated_count = 0
    pending_attribution_count = 0
    for f in holdings:
        total_market_value = _r2(total_market_value + f.get("marketValue", 0))
        total_cost = _r2(total_cost + f.get("costTotal", 0))
        total_today_profit = _r2(total_today_profit + f.get("todayProfit", 0))
        total_day_base_market_value = _r2(total_day_base_market_value + f.get("dayBaseMarketValue", 0))
        total_holding_profit = _r2(total_holding_profit + f.get("holdingProfit", 0))
        total_cumulative_profit = _r2(total_cumulative_profit + f.get("totalProfit", 0))
        total_in_transit = _r2(total_in_transit + f.get("inTransitAmount", 0))
        total_invested = _r2(total_invested + f.get("totalInvested", 0))
        if f.get("displayedDayAttributable"):
            attributable_count += 1
            if f.get("estimateSource") == "official_published":
                updated_count += 1
        elif f.get("estimateSource") == "official_published":
            pending_attribution_count += 1
    total_holding_return_rate = _ratio_pct(total_holding_profit, total_cost)
    today_profit_rate = _ratio_pct(total_today_profit, total_day_base_market_value)

    return {
        "holdings": holdings,
        "watchlist": watchlist,
        "groups": portfolio.get("groups", []),
        "summary": {
            "totalMarketValue": total_market_value,
            "totalCost": total_cost,
            "todayProfit": total_today_profit,
            "todayProfitRate": today_profit_rate,
            "totalDayBaseMarketValue": total_day_base_market_value,
            "totalHoldingProfit": total_holding_profit,
            "totalHoldingReturnRate": total_holding_return_rate,
            "cumulativeProfit": total_cumulative_profit,
            "totalInvested": total_invested,
            "heldItemCount": len(holdings),
            "totalInTransitAmount": total_in_transit,
            "emptyPortfolioConfirmed": snapshot_summary.get("empty_portfolio_confirmed", False),
            "isConfirmedEmptyPortfolioSnapshot": snapshot_summary.get("is_confirmed_empty_portfolio_snapshot", False),
            "hasRestorableSyncPayload": snapshot_summary.get("has_restorable_sync_payload", False),
            "dataSource": data_source,
            "displayedDayCompleteness": {
                "totalCount": len(holdings),
                "attributableCount": attributable_count,
                "updatedCount": updated_count,
                "pendingAttributionCount": pending_attribution_count,
                "complete": pending_attribution_count == 0,
            },
        },
        "snapshotSummary": snapshot_summary,
        "strategyPreferences": {
            "maxDrawdownLimitPct": max_drawdown_limit_pct,
        },
        "dataUpdatedAt": data_updated_at,
        "dataSource": data_source,
    }


async def get_summary() -> dict:
    """
    获取持仓总览摘要（总市值、今日收益、今日收益率、持有收益、持有收益率、累计收益）。
    输出比 get_records 更精简（不含每只基金明细），适合快速查询资产概况。
    今日收益率 todayProfitRate 使用 todayProfit / totalDayBaseMarketValue，
    即归属日组合期初市值口径，不使用当前总市值。

    返回的 dataUpdatedAt 字段表示云端实时同步主数据的更新时间，请将此时间告知用户，
    让其了解数据是否为最新（若时间较旧，提示用户在 App 确认实时同步已完成）。
    """
    _require_token()
    result = await _runtime_get_records()
    summary = result.get("summary", {})
    summary["dataUpdatedAt"] = result.get("dataUpdatedAt", "")
    return summary
