"""Pure adapters for structured portfolio snapshot responses."""

import json
import re

CONFIRMED_EMPTY_PORTFOLIO_KEYS = {
    "funds", "archivedLedger", "deletedFundsMeta", "dismissedDividendKeys",
    "userPreferences", "groups", "watchlistGroups", "globalTags", "tagDisplayCount",
    "fieldConfigs", "watchlistFieldConfigs", "nightWatchCodes", "purchaseLimitWatchItems",
    "purchaseLimitWatchNightDefaultsMigrated", "marketIndexSelection", "emptyPortfolioConfirmed",
    "clearedAt", "timestamp", "version",
}


def parse_sync_payload(data) -> dict:
    parsed = data
    try:
        for _ in range(4):
            if isinstance(parsed, str):
                parsed = json.loads(parsed)
                continue
            if isinstance(parsed, dict) and isinstance(parsed.get("data"), (dict, str)):
                parsed = parsed["data"]
                continue
            break
        return parsed if isinstance(parsed, dict) else {}
    except Exception:
        return {}


def is_valid_fund_code_value(value) -> bool:
    return bool(re.fullmatch(r"\d{6}", str(value or "").strip()))


def is_restorable_fund(fund) -> bool:
    return isinstance(fund, dict) and is_valid_fund_code_value(fund.get("code"))


def is_empty_plain_object(value) -> bool:
    return isinstance(value, dict) and len(value) == 0


def summarize_sync_payload(parsed: dict) -> dict:
    funds = parsed.get("funds")
    has_funds_array = isinstance(funds, list)
    fund_items = funds if has_funds_array else []
    restorable = [fund for fund in fund_items if is_restorable_fund(fund)]
    empty_portfolio_confirmed = parsed.get("emptyPortfolioConfirmed") is True
    is_confirmed_empty = (
        bool(parsed)
        and not any(key not in CONFIRMED_EMPTY_PORTFOLIO_KEYS for key in parsed)
        and has_funds_array
        and len(fund_items) == 0
        and empty_portfolio_confirmed
        and ("archivedLedger" not in parsed or is_empty_plain_object(parsed.get("archivedLedger")))
        and ("deletedFundsMeta" not in parsed or is_empty_plain_object(parsed.get("deletedFundsMeta")))
    )
    return {
        "has_payload": bool(parsed),
        "has_funds_array": has_funds_array,
        "fund_count": len(fund_items),
        "restorable_fund_count": len(restorable),
        "portfolio_fund_count": sum(1 for fund in restorable if fund.get("isWatchlist") is not True),
        "watchlist_fund_count": sum(1 for fund in restorable if fund.get("isWatchlist") is True),
        "empty_portfolio_confirmed": empty_portfolio_confirmed,
        "is_confirmed_empty_portfolio_snapshot": is_confirmed_empty,
        "has_restorable_sync_payload": len(restorable) > 0 or is_confirmed_empty,
    }


def portfolio_payload_source(raw: dict, fallback: str = "") -> str:
    if raw.get("version") == "portfolio-v1":
        return "structured_portfolio"
    return fallback or "structured_portfolio"


def unwrap_sync_payload(raw: dict, source: str = "") -> dict:
    json_data = raw.get("json_data") or "{}"
    parsed = parse_sync_payload(json_data)
    summary = summarize_sync_payload(parsed)
    parsed["_meta_summary"] = summary
    parsed["_meta_updated_at"] = raw.get("updated_at", "")
    parsed["_meta_etag"] = raw.get("etag", "")
    parsed["_meta_data_source"] = portfolio_payload_source(raw, source)
    json_text = json_data if isinstance(json_data, str) else json.dumps(json_data, ensure_ascii=False)
    parsed["_meta_size_bytes"] = raw.get("size_bytes") or len(json_text.encode("utf-8"))
    for key, value in summary.items():
        parsed[f"_meta_{key}"] = value
    return parsed
