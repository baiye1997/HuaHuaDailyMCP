"""Estimate validation helpers shared by fund MCP tools."""

import math

from ..validation import (
    DATA_SOURCE_MODES,
    LEGACY_DATA_SOURCE_MODES,
    normalize_data_source_mode,
)

_HISTORICAL_ESTIMATE_SOURCES = {
    "estimate",
    "p6_b",
    "p6_c",
    "p6_external_a",
    "p6_external_b",
    "official_overseas_est",
    "index_direct_estimate",
    "reference_direct_estimate",
    "special_silver",
    "gold_spot",
    "huahua_stock",
    "huahua_bond",
    "sector_proxy_estimate",
}


def estimate_frame_available(item: dict) -> bool:
    if not isinstance(item, dict) or not item:
        return False
    source = str(item.get("source") or "").strip().lower()
    if not source or source in {
        "reset",
        "timeout",
        "unavailable",
    }:
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


def sanitize_estimate_frame(item):
    """Never expose obsolete calculation details as a usable current frame."""

    if not isinstance(item, dict):
        return item
    sanitized = dict(item)
    if not estimate_frame_available(sanitized):
        sanitized.pop("breakdown", None)
        sanitized.pop("_breakdown_payload", None)
        sanitized["estimatedNav"] = None
        sanitized["estimatedChangePercent"] = None
        if "gsz" in sanitized:
            sanitized["gsz"] = ""
        if "gszzl" in sanitized:
            sanitized["gszzl"] = ""
        if "marketPriceChangePercent" in sanitized:
            sanitized["marketPriceChangePercent"] = None
    return sanitized


def sanitize_source_preview_payload(payload):
    if not isinstance(payload, dict):
        return payload
    data = payload.get("data")
    if not isinstance(data, dict):
        return payload
    sanitized_data = {}
    for mode, raw_item in data.items():
        if not isinstance(raw_item, dict):
            continue
        item = sanitize_estimate_frame(raw_item)
        snapshot = item.get("last_estimate_snap")
        if isinstance(snapshot, dict):
            source = str(snapshot.get("source") or "")
            date = str(snapshot.get("date") or "")[:10]
            display_date = str(item.get("display_date") or "")[:10]
            decision = snapshot.get("estimateDecision")
            nav = snapshot.get("nav")
            change = snapshot.get("change")
            try:
                nav_value = float(nav)
                change_value = float(change)
            except (TypeError, ValueError):
                nav_value = float("nan")
                change_value = float("nan")
            snapshot_unavailable = (
                isinstance(decision, dict)
                and str(decision.get("status") or "").lower() == "unavailable"
            )
            if (
                source not in _HISTORICAL_ESTIMATE_SOURCES
                or not date
                or (display_date and date != display_date)
                or not math.isfinite(nav_value)
                or nav_value <= 0
                or not math.isfinite(change_value)
                or snapshot_unavailable
            ):
                item.pop("last_estimate_snap", None)
        sanitized_data[mode] = item
    return {**payload, "data": sanitized_data}


def validate_public_data_source_mode(value, field: str) -> str:
    normalized = str(value or "").strip().lower()
    if (
        normalized not in DATA_SOURCE_MODES
        and normalized not in LEGACY_DATA_SOURCE_MODES
    ):
        raise ValueError(f"{field} 仅支持 source_a、source_b 或 huahua")
    return normalize_data_source_mode(normalized)
