"""Stateful helpers used by the compatibility facade."""

import asyncio
import re
import time
from typing import Any, Optional

from .tools.fund_estimate_helpers import estimate_frame_available
from .validation import DATA_SOURCE_PREFERENCE_EPOCH


estimate_semaphore = asyncio.Semaphore(3)
_estimate_semaphore_loop: Optional[asyncio.AbstractEventLoop] = None
_estimate_inflight_lock: Optional[asyncio.Lock] = None
_estimate_inflight_loop: Optional[asyncio.AbstractEventLoop] = None
_estimate_inflight: dict[tuple[str, ...], dict[str, Any]] = {}
_MAX_ESTIMATE_INFLIGHT = 100


def _estimate_item_is_cacheable(item: object) -> bool:
    """Keep only usable current frames in the MCP's short process cache."""

    if not isinstance(item, dict) or not item:
        return False
    source = str(item.get("source") or "").strip().lower()
    status = str(item.get("status") or "").strip().lower()
    if (
        not source
        or source in {"reset", "timeout", "unavailable", "cache_only_miss"}
        or status == "unavailable"
    ):
        return False
    decision = item.get("estimateDecision")
    if isinstance(decision, dict):
        decision_status = str(decision.get("status") or "").strip().lower()
        decision_route = str(decision.get("routeId") or "").strip().lower()
        decision_reason = str(decision.get("reason") or "").strip().lower()
        if (
            decision_status == "unavailable"
            or decision_route == "cache_only_miss"
            or decision_reason == "cache_only_miss"
        ):
            return False
    freshness = str(
        item.get("freshness")
        or item.get("estimateFreshness")
        or ""
    ).strip().lower()
    if (
        item.get("stale") is True
        or item.get("estimateStale") is True
        or item.get("frameRefreshing") is True
        or freshness in {"stale", "unavailable"}
        or str(item.get("fallbackReason") or "").strip().lower()
        == "frame_refreshing"
    ):
        return False
    return estimate_frame_available(item)


def _get_estimate_semaphore() -> asyncio.Semaphore:
    global estimate_semaphore, _estimate_semaphore_loop
    loop = asyncio.get_running_loop()
    if _estimate_semaphore_loop is not loop:
        estimate_semaphore = asyncio.Semaphore(3)
        _estimate_semaphore_loop = loop
    return estimate_semaphore


def _get_estimate_inflight_lock() -> asyncio.Lock:
    global _estimate_inflight_lock, _estimate_inflight_loop, _estimate_inflight
    loop = asyncio.get_running_loop()
    if _estimate_inflight_lock is None or _estimate_inflight_loop is not loop:
        _estimate_inflight_lock = asyncio.Lock()
        _estimate_inflight_loop = loop
        _estimate_inflight = {}
    return _estimate_inflight_lock


async def fetch_estimates(
    runtime: dict[str, Any],
    codes: list,
    default_data_source_mode: str = "source_a",
    data_source_mode_by_code: Optional[dict] = None,
) -> dict:
    """Fetch estimates while resolving patchable dependencies from the facade."""
    codes = list(dict.fromkeys(codes))
    normalize_mode = runtime["_normalize_data_source_mode"]
    validate_code = runtime["_validate_fund_code"]
    estimate_cache = runtime["_estimate_cache"]
    session = runtime["_session"]
    session_generation = int(session.get("generation") or 0)
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

    async def fetch_batch(batch: list) -> dict:
        async with _get_estimate_semaphore():
            return await runtime["_post"](
                "/api/estimate/batch",
                {
                    "codes": batch,
                    "defaultDataSourceMode": default_mode,
                    "dataSourcePreferenceEpoch": DATA_SOURCE_PREFERENCE_EPOCH,
                    "dataSourceModeByCode": {
                        code: mode_for(code) for code in batch if mode_for(code) != default_mode or code in mode_by_code
                    },
                },
            )

    async def fetch_missing(miss_codes: list) -> dict:
        batches = [
            miss_codes[index : index + 50]
            for index in range(0, len(miss_codes), 50)
        ]
        responses = await asyncio.gather(
            *(fetch_batch(batch) for batch in batches),
            return_exceptions=True,
        )
        fetched: dict = {}
        cache_ts = time.monotonic()
        for response in responses:
            if isinstance(response, Exception):
                continue
            batch_data = (
                response.get("data", response)
                if isinstance(response, dict)
                else response
            )
            if not isinstance(batch_data, list):
                continue
            for item in batch_data:
                code_key = item.get("fundcode") or item.get("code")
                if not code_key:
                    continue
                fetched[code_key] = item
                if (
                    _estimate_item_is_cacheable(item)
                    and int(session.get("generation") or 0) == session_generation
                ):
                    mode = normalize_mode(
                        item.get("dataSourceMode") or mode_for(code_key)
                    )
                    estimate_cache[f"{code_key}:{mode}"] = {
                        "data": item,
                        "ts": cache_ts,
                        "generation": session_generation,
                    }
        return fetched

    async def run_inflight(
        key: tuple[str, ...],
        miss_codes: list,
    ) -> dict:
        try:
            return await fetch_missing(miss_codes)
        finally:
            current_task = asyncio.current_task()
            async with _get_estimate_inflight_lock():
                entry = _estimate_inflight.get(key)
                if entry and entry["task"] is current_task:
                    _estimate_inflight.pop(key, None)

    result: dict = {}
    inflight_key: tuple[str, ...] = ()
    task: Optional[asyncio.Task] = None
    async with _get_estimate_inflight_lock():
        now = time.monotonic()
        miss_codes: list = []
        for code in codes:
            entry = estimate_cache.get(cache_key(code))
            if (
                entry
                and entry.get("generation") == session_generation
                and now - entry["ts"] < runtime["_ESTIMATE_TTL"]
            ):
                result[code] = entry["data"]
            else:
                miss_codes.append(code)
        if not miss_codes:
            return result
        if len(estimate_cache) > 500:
            # 先驱逐过期条目，保留仍新鲜的帧；若全部新鲜仍超限（极端积压），
            # 兜底全清避免每次请求都重复遍历且永远清不掉。
            cutoff = time.monotonic() - runtime["_ESTIMATE_TTL"]
            for key in [
                key
                for key, entry in estimate_cache.items()
                if entry.get("ts", 0) < cutoff
            ]:
                estimate_cache.pop(key, None)
            if len(estimate_cache) > 500:
                estimate_cache.clear()
        inflight_key = (
            f"generation:{session_generation}",
            *(sorted(cache_key(code) for code in miss_codes)),
        )
        entry = _estimate_inflight.get(inflight_key)
        if entry is None:
            if len(_estimate_inflight) >= _MAX_ESTIMATE_INFLIGHT:
                raise RuntimeError("并发估值请求过多，请稍后重试")
            task = asyncio.create_task(run_inflight(inflight_key, miss_codes))
            entry = {"task": task, "waiters": 0}
            _estimate_inflight[inflight_key] = entry
        task = entry["task"]
        entry["waiters"] += 1

    try:
        fetched = await asyncio.shield(task)
        if int(session.get("generation") or 0) != session_generation:
            raise RuntimeError("Agent Token 已在请求期间变更，请重试")
        result.update(fetched)
    finally:
        async with _get_estimate_inflight_lock():
            entry = _estimate_inflight.get(inflight_key)
            if entry and entry["task"] is task:
                entry["waiters"] -= 1
                if entry["waiters"] <= 0:
                    _estimate_inflight.pop(inflight_key, None)
                    if not task.done():
                        task.cancel()
    return result


async def download_portfolio(runtime: dict[str, Any]) -> dict:
    """Download and cache the canonical structured portfolio snapshot."""
    cache = runtime["_portfolio_cache"]
    session = runtime["_session"]
    requested_generation = int(session.get("generation") or 0)
    now = time.monotonic()
    if (
        cache["data"] is not None
        and cache.get("generation") == requested_generation
        and now - cache["ts"] < runtime["_PORTFOLIO_TTL"]
    ):
        return cache["data"]
    async with runtime["_get_download_lock"]():
        if int(session.get("generation") or 0) != requested_generation:
            raise RuntimeError("Agent Token 已在请求期间变更，请重试")
        now = time.monotonic()
        if (
            cache["data"] is not None
            and cache.get("generation") == requested_generation
            and now - cache["ts"] < runtime["_PORTFOLIO_TTL"]
        ):
            return cache["data"]
        raw, source = await runtime["_download_portfolio_raw"]()
        if int(session.get("generation") or 0) != requested_generation:
            raise RuntimeError("Agent Token 已在请求期间变更，请重试")
        parsed = runtime["_unwrap_sync_payload"](raw if isinstance(raw, dict) else {}, source=source)
        cache["data"] = parsed
        cache["ts"] = time.monotonic()
        cache["generation"] = requested_generation
        return parsed


async def download_portfolio_raw(runtime: dict[str, Any]) -> tuple[dict, str]:
    state = await runtime["_get"]("/api/sync/v3/state")
    return state if isinstance(state, dict) else {}, "portfolio_v3"
