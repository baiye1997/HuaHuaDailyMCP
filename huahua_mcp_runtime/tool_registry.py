"""Public MCP tool ordering and registration.

Framework v2 (2026-08): tools are annotated with a profile (``core`` / ``full``)
and cancelled tools are removed from the registry. ``HUAHUA_MCP_PROFILE`` selects
the active surface; the default remains ``full`` so existing deployments keep
every compatible tool. Cancelled tools are not registered at all.
"""

import os
from typing import Optional

from .tools import community, fund, import_tools, market, portfolio, portfolio_actions, quant, reports, system


CORE_PROFILE = "core"
FULL_PROFILE = "full"
DEFAULT_PROFILE = FULL_PROFILE
PROFILE_ENV = "HUAHUA_MCP_PROFILE"

# Tools cancelled in framework v2. Kept for one release window in the changelog
# so agents still running older SKILL instructions can reconcile; they are not
# registered and return unknown-tool errors from hosts.
REMOVED_TOOLS = frozenset({
    "get_app_versions",
    "get_indices",
    "get_danmaku",
    "send_danmaku",
    "get_notices",
    "get_community_notices",
})

# High-frequency daily surface. Single-code variants of batch tools and all
# low-frequency/quant/community tools live only in the full profile.
CORE_TOOLS = frozenset({
    # system
    "set_token",
    "get_tool_manifest",
    "get_current_user",
    "get_app_version",
    # portfolio
    "get_summary",
    "get_records",
    "get_transactions",
    "get_sync_meta",
    "get_portfolio_preferences",
    # fund (batch-first)
    "search_item",
    "get_item_estimate",
    "get_batch_fund_fees",
    "get_batch_fund_profiles",
    "get_batch_fund_quant_metrics",
    "get_batch_fund_period_ranks",
    # market
    "get_status",
    "get_overview",
    "get_index_metrics",
    "get_sector_metrics",
    "get_instrument_catalog",
    "get_instrument_quotes",
    "calculate_trading_dates",
    "get_next_trading_day",
    "get_night_estimate",
    "get_fund_flow",
    # trade
    "request_transaction",
    "get_agent_requests",
    "update_agent_request",
    # import
    "import_holding_screenshots",
    "import_transaction_screenshots",
    "request_import_review",
    # reports
    "submit_personal_strategy_report",
    # quant
    "get_quant_strategy_context",
    "get_batch_fund_nav_history",
    "get_transaction_ledger",
})

TOOL_MODULES = (system, fund, market, portfolio, reports, portfolio_actions, import_tools, community, quant)
TOOL_NAMES = (
    "set_token",
    "get_tool_manifest",
    "get_current_user",
    "search_item",
    "get_item_detail",
    "get_item_estimate",
    "get_fund_source_previews",
    "get_daily_rank",
    "get_item_history",
    "get_item_dividends",
    "get_fund_timeline",
    "get_fund_fees",
    "get_batch_fund_fees",
    "get_fund_period_rank",
    "get_fund_profile",
    "get_batch_fund_profiles",
    "get_fund_quant_metrics",
    "get_batch_fund_quant_metrics",
    "get_batch_fund_period_ranks",
    "get_status",
    "get_overview",
    "get_sector_wind",
    "get_yesterday_rank",
    "get_fund_flow",
    "get_index_metrics",
    "get_sector_metrics",
    "get_holder_ranking",
    "get_night_estimate",
    "get_night_watchlist",
    "get_purchase_limit_watchlist",
    "get_auto_invest_plans",
    "get_fund_disciplines",
    "get_portfolio_preferences",
    "get_benchmark_history",
    "get_instrument_catalog",
    "get_instrument_quotes",
    "get_instrument_timeline",
    "get_instrument_history",
    "calculate_trading_dates",
    "get_next_trading_day",
    "get_sync_meta",
    "get_raw_sync_data",
    "get_transactions",
    "get_groups",
    "get_tags",
    "get_records",
    "get_summary",
    "submit_personal_strategy_report",
    "request_transaction",
    "get_agent_requests",
    "update_agent_request",
    "import_holding_screenshots",
    "import_transaction_screenshots",
    "request_import_review",
    "get_community_ranking",
    "get_community_my_rank",
    "get_community_user",
    "get_community_stats",
    "get_community_following",
    "search_community_users",
    "get_community_authorization",
    "authorize_community",
    "revoke_community_authorization",
    "follow_community_user",
    "analyze_jcti",
    "get_transaction_ledger",
    "get_batch_fund_nav_history",
    "get_portfolio_nav_history",
    "get_portfolio_trade_review",
    "get_quant_strategy_context",
    "run_portfolio_backtest",
    "get_portfolio_backtest",
    "save_quant_snapshot",
    "get_quant_snapshots",
    "get_quant_snapshot_review",
    "get_app_version",
)

assert not (REMOVED_TOOLS & set(TOOL_NAMES)), "cancelled tools must not be registered"
assert CORE_TOOLS <= set(TOOL_NAMES), "core tools must exist in the registry"


def resolve_profile() -> str:
    """Return the active profile from ``HUAHUA_MCP_PROFILE`` (default ``full``)."""
    profile = os.environ.get(PROFILE_ENV, "").strip().lower()
    return profile if profile in {CORE_PROFILE, FULL_PROFILE} else DEFAULT_PROFILE


def active_tool_names(profile: Optional[str] = None) -> tuple[str, ...]:
    """Return the tool names registered for a profile (default: resolved env)."""
    selected = resolve_profile() if profile is None else profile
    if selected == CORE_PROFILE:
        return tuple(name for name in TOOL_NAMES if name in CORE_TOOLS)
    return TOOL_NAMES


def register_tools(mcp, runtime_globals: dict) -> None:
    names = active_tool_names()
    for name in names:
        runtime_globals[name] = next(getattr(module, name) for module in TOOL_MODULES if hasattr(module, name))
    for module in TOOL_MODULES:
        module.bind(runtime_globals)
    for name in names:
        mcp.tool()(runtime_globals[name])
