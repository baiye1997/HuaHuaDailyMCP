"""Fail-closed current estimate frame contract shared by MCP consumers."""

from __future__ import annotations

import math


CURRENT_ESTIMATE_SOURCES = frozenset({
    "estimate",
    "estimate_official_confirmation",
    "gold_spot",
    "huahua",
    "huahua_bond",
    "huahua_estimate",
    "huahua_stock",
    "index_direct_estimate",
    "market_factor_proxy_estimate",
    "official_overseas_est",
    "official_published",
    "p6_b",
    "p6_c",
    "p6_external_a",
    "p6_external_b",
    "qdii_market_proxy_estimate",
    "realtime",
    "reference_direct_estimate",
    "sector_proxy_estimate",
    "sina_official_current",
    "special_silver",
})


def estimate_frame_available(item: dict) -> bool:
    if not isinstance(item, dict) or not item:
        return False
    source = str(item.get("source") or "").strip().lower()
    if source not in CURRENT_ESTIMATE_SOURCES:
        return False
    decision = item.get("estimateDecision")
    decision_status = (
        str(decision.get("status") or "").strip().lower()
        if isinstance(decision, dict)
        else ""
    )
    freshness = str(
        item.get("freshness") or item.get("estimateFreshness") or ""
    ).strip().lower()
    if (
        decision_status == "unavailable"
        or item.get("stale") is True
        or item.get("estimateStale") is True
        or freshness == "stale"
    ):
        return False

    def to_float(value) -> float:
        if isinstance(value, bool):
            return float("nan")
        try:
            return float(str(value).replace("%", ""))
        except (TypeError, ValueError):
            return float("nan")

    previous_nav = to_float(item.get("prev_dwjz") or item.get("prevNav"))
    estimated_nav = to_float(item.get("estimatedNav") or item.get("nav"))
    change_percent = item.get("estimatedChangePercent")
    if change_percent is None:
        change_percent = item.get("gszzl")
    parsed_change_percent = to_float(change_percent)
    return (
        math.isfinite(previous_nav)
        and previous_nav > 0
        and (
            (math.isfinite(estimated_nav) and estimated_nav > 0)
            or math.isfinite(parsed_change_percent)
        )
    )
