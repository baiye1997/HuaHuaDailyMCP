"""Stateful helpers used by the compatibility facade."""

import asyncio
import re
import time
from typing import Any, Optional


estimate_semaphore = asyncio.Semaphore(3)


async def fetch_estimates(
    runtime: dict[str, Any],
    codes: list,
    default_data_source_mode: str = "huahua",
    data_source_mode_by_code: Optional[dict] = None,
) -> dict:
    """Fetch estimates while resolving patchable dependencies from the facade."""
    normalize_mode = runtime["_normalize_data_source_mode"]
    validate_code = runtime["_validate_fund_code"]
    estimate_cache = runtime["_estimate_cache"]
    now = time.monotonic()
    default_mode = normalize_mode(default_data_source_mode)
    mode_by_code = {
        validate_code(str(code)): normalize_mode(mode)
        for code, mode in (data_source_mode_by_code or {}).items()
        if re.fullmatch(r"\d{6}", str(code or "").strip())
    }

    def mode_for(code: str) -> str:
        return mode_by_code.get(code, default_mode)

    def cache_key(code: str) -> str:
        return f"{code}:{mode_for(code)}"

    result: dict = {}
    miss_codes: list = []
    for code in codes:
        entry = estimate_cache.get(cache_key(code))
        if entry and now - entry["ts"] < runtime["_ESTIMATE_TTL"]:
            result[code] = entry["data"]
        else:
            miss_codes.append(code)
    if not miss_codes:
        return result
    if len(estimate_cache) > 500:
        estimate_cache.clear()

    async def fetch_batch(batch: list) -> dict:
        async with estimate_semaphore:
            return await runtime["_post"](
                "/api/estimate/batch",
                {
                    "codes": batch,
                    "defaultDataSourceMode": default_mode,
                    "dataSourceModeByCode": {
                        code: mode_for(code) for code in batch if mode_for(code) != default_mode or code in mode_by_code
                    },
                },
            )

    batches = [miss_codes[index : index + 50] for index in range(0, len(miss_codes), 50)]
    responses = await asyncio.gather(*(fetch_batch(batch) for batch in batches), return_exceptions=True)
    for response in responses:
        if isinstance(response, Exception):
            continue
        batch_data = response.get("data", response) if isinstance(response, dict) else response
        if not isinstance(batch_data, list):
            continue
        for item in batch_data:
            code_key = item.get("fundcode") or item.get("code")
            if not code_key:
                continue
            result[code_key] = item
            if item.get("source") != "timeout":
                mode = normalize_mode(item.get("dataSourceMode") or mode_for(code_key))
                estimate_cache[f"{code_key}:{mode}"] = {"data": item, "ts": now}
    return result


async def download_portfolio(runtime: dict[str, Any]) -> dict:
    """Download and cache the canonical structured portfolio snapshot."""
    cache = runtime["_portfolio_cache"]
    now = time.monotonic()
    if cache["data"] is not None and now - cache["ts"] < runtime["_PORTFOLIO_TTL"]:
        return cache["data"]
    async with runtime["_get_download_lock"]():
        now = time.monotonic()
        if cache["data"] is not None and now - cache["ts"] < runtime["_PORTFOLIO_TTL"]:
            return cache["data"]
        raw, source = await runtime["_download_portfolio_raw"]()
        parsed = runtime["_unwrap_sync_payload"](raw if isinstance(raw, dict) else {}, source=source)
        cache["data"] = parsed
        cache["ts"] = now
        return parsed


async def download_portfolio_raw(runtime: dict[str, Any]) -> tuple[dict, str]:
    structured = await runtime["_get"]("/api/portfolio/snapshot")
    return structured if isinstance(structured, dict) else {}, "structured_portfolio"
