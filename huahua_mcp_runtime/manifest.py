"""Capability manifest for the public MCP surface."""

from typing import Any

from .tool_registry import CORE_PROFILE, FULL_PROFILE, resolve_profile
from .version import __version__


def _capabilities() -> dict[str, list[str]]:
    """Return the full capability lists.

    Cancelled tools (removed in framework v2) are absent from every profile;
    profile narrowing happens in :func:`_filter_for_profile`.
    """
    return {
        "profile": ["get_current_user"],
        "portfolio": [
            "get_sync_meta",
            "get_raw_sync_data",
            "get_records",
            "get_summary",
            "get_transactions",
            "get_groups",
            "get_tags",
            "get_night_watchlist",
            "get_purchase_limit_watchlist",
            "get_auto_invest_plans",
            "get_fund_disciplines",
            "get_portfolio_preferences",
            "get_transaction_ledger",
            "get_portfolio_nav_history",
            "get_portfolio_trade_review",
        ],
        "quant": [
            "get_batch_fund_nav_history",
            "get_quant_strategy_context",
            "run_portfolio_backtest",
            "get_portfolio_backtest",
            "save_quant_snapshot",
            "get_quant_snapshots",
            "get_quant_snapshot_review",
        ],
        "market": [
            "search_item",
            "get_item_estimate",
            "get_fund_source_previews",
            "get_item_detail",
            "get_item_history",
            "get_item_dividends",
            "get_fund_timeline",
            "get_fund_fees",
            "get_batch_fund_fees",
            "get_fund_period_rank",
            "get_batch_fund_period_ranks",
            "get_fund_profile",
            "get_batch_fund_profiles",
            "get_fund_quant_metrics",
            "get_batch_fund_quant_metrics",
            "get_night_estimate",
            "get_daily_rank",
            "get_status",
            "get_overview",
            "get_sector_wind",
            "get_yesterday_rank",
            "get_fund_flow",
            "get_index_metrics",
            "get_sector_metrics",
            "get_holder_ranking",
            "get_benchmark_history",
            "get_instrument_catalog",
            "get_instrument_quotes",
            "get_instrument_timeline",
            "get_instrument_history",
            "calculate_trading_dates",
            "get_next_trading_day",
        ],
        "community": [
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
        ],
        "trade": ["request_transaction", "get_agent_requests", "update_agent_request"],
        "personal_reports": ["submit_personal_strategy_report"],
        "imports": [
            "import_holding_screenshots",
            "import_transaction_screenshots",
            "request_import_review",
        ],
        "misc": [
            "analyze_jcti",
            "get_app_version",
        ],
    }


def _filter_for_profile(capabilities: dict[str, list[str]], profile: str) -> dict[str, list[str]]:
    """Drop full-only tools when the active profile is ``core``.

    Cancelled tools are already absent from the static lists above, so this
    only narrows the surface; it never re-adds removed tools.
    """
    if profile == FULL_PROFILE:
        return capabilities
    from .tool_registry import CORE_TOOLS

    return {
        key: [name for name in names if name in CORE_TOOLS]
        for key, names in capabilities.items()
    }


def _filter_safety_for_profile(safety: dict[str, Any], profile: str) -> dict[str, Any]:
    """Keep tool lists in the safety section aligned with the active profile."""
    if profile == FULL_PROFILE:
        return safety
    from .tool_registry import CORE_TOOLS

    filtered = dict(safety)
    for key in (
        "direct_state_change_tools",
        "confirmation_required_tools",
        "non_idempotent_toggle_tools",
        "destructive_tools",
    ):
        values = filtered.get(key)
        if isinstance(values, list):
            filtered[key] = [name for name in values if name in CORE_TOOLS]
    scopes = filtered.get("quant_tool_scopes")
    if isinstance(scopes, dict):
        filtered["quant_tool_scopes"] = {
            name: scope for name, scope in scopes.items() if name in CORE_TOOLS
        }
    return filtered


def build_tool_manifest(
    official_api: str,
    update_status: dict[str, Any] | None = None,
    backend_compatibility: dict[str, Any] | None = None,
    profile: str | None = None,
) -> dict:
    """
    返回本 MCP 服务的能力边界、认证方式和建议调用顺序。
    可用于 Agent 在会话开始时自检。

    ``profile`` 显式传入时使用该值；否则从 ``HUAHUA_MCP_PROFILE`` 解析，
    默认 ``full``。非法显式值回退到环境解析（与 tool_registry 一致）。
    """
    if profile not in {CORE_PROFILE, FULL_PROFILE}:
        profile = None
    active_profile = resolve_profile() if profile is None else profile
    return {
        "name": "huahua-daily",
        "transport": "stdio",
        "profile": active_profile,
        "runtime": {
            "version": __version__,
            "updateCheck": update_status or {
                "status": "not_checked",
                "currentVersion": __version__,
                "latestVersion": None,
                "updateAvailable": None,
            },
        },
        "auth": {
            "primary_env": "HUAHUA_AGENT_TOKEN",
            "header": "Authorization: AgentToken <token>",
        },
        "api_base": official_api,
        "backendCompatibility": backend_compatibility or {
            "status": "not_checked",
            "compatible": None,
        },
        "capabilities": _filter_for_profile(_capabilities(), active_profile),
        "safety": _filter_safety_for_profile({
            "direct_trading": False,
            "trade_flow": "request_transaction 支持买入金额、卖出金额/份额和精确分组，只创建待确认信号，必须由用户在 App 内确认。",
            "trade_request_idempotency": "同一交易或导入请求重试时复用 client_request_id；服务端按当前用户在 7 天窗口内去重。",
            "agent_request_update_boundary": "MCP 只能把待确认请求标记为 DISMISSED；PROCESSED 必须由 App 在用户确认后设置。",
            "direct_state_change_tools": [
                "authorize_community",
                "revoke_community_authorization",
                "follow_community_user",
                "request_transaction",
                "update_agent_request",
                "request_import_review",
                "submit_personal_strategy_report",
                "run_portfolio_backtest",
                "save_quant_snapshot",
            ],
            "confirmation_required_tools": [
                "authorize_community",
                "revoke_community_authorization",
                "follow_community_user",
                "request_transaction",
                "update_agent_request",
                "request_import_review",
                "submit_personal_strategy_report",
            ],
            "non_idempotent_toggle_tools": ["follow_community_user"],
            "personal_report_write": True,
            "personal_report_flow": "submit_personal_strategy_report 只写入当前 Agent Token 所属用户的报告中心；不能指定 user_id 或广播。",
            "personal_report_required_scope": "agent:full（默认 Token 已包含）",
            "quant_snapshot_write": True,
            "quant_snapshot_write_boundary": "仅归档 token 所属用户的策略观察；真实持仓、组合版本和内容哈希由服务端捕获，不保存建议金额。",
            "quant_tool_scopes": {
                "get_transaction_ledger": "portfolio:read",
                "get_portfolio_nav_history": "portfolio:read",
                "get_portfolio_trade_review": "portfolio:read",
                "get_batch_fund_nav_history": "market:read",
                "get_fund_quant_metrics": "market:read",
                "get_batch_fund_quant_metrics": "market:read",
                "get_quant_strategy_context": "quant:read",
                "run_portfolio_backtest": "quant:write",
                "get_portfolio_backtest": "quant:read",
                "get_quant_snapshots": "quant:read",
                "get_quant_snapshot_review": "quant:read",
                "save_quant_snapshot": "quant:write",
            },
            "quant_data_basis": "单基金指标使用官方净值 D 日；组合回放使用 linked_daily_return_v1 的 G 日归属；QDII 夜盘仅作执行参考；回测零费率；不宣称严格 point-in-time。",
            "public_report_write": False,
            "cloud_sync_read": "get_records/get_summary/get_raw_sync_data 读取云端实时同步主数据；固定使用结构化组合接口，不读取云端历史备份快照。",
            "portfolio_freshness": "组合新鲜度只看 portfolioUpdatedAt/dataUpdatedAt（原始接口为 meta.portfolio_updated_at）；data.timestamp 是客户端谱系/迁移元数据，不得作为同步时间。",
            "valuation_basis": "marketValue 使用不晚于北京时间今日的最新官方净值锚点：优先比较行情帧 dwjz/last_nav_date 与组合快照 lastNav/lastNavDate；estimatedNav 只进入 estimatedMarketValue，不进入官方市值。",
            "estimate_timeout_handling": "timeout、stale last-good 或 estimateDecision=unavailable 的帧不参与当日收益；检查 summary.estimateCompleteness，不能把不可用帧的 0 元当成真实零涨跌。",
            "cloud_sync_write": False,
            "cloud_history_snapshot_write": False,
            "empty_portfolio_restore": "已确认的空组合主数据会被识别为合法可恢复状态，但 MCP 不提供恢复或覆盖写入工具。",
            "destructive_tools": [],
        }, active_profile),
    }
