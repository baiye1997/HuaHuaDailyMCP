"""Portfolio preference and plan MCP tools."""

from .binding import bind_runtime


_RUNTIME_DEPENDENCIES = (
    "_download_portfolio",
    "_is_valid_fund_code_value",
    "_require_token",
    "_validate_fund_code",
)

if False:  # pragma: no cover - populated by bind() before tool registration
    _download_portfolio = None
    _is_valid_fund_code_value = None
    _require_token = None
    _validate_fund_code = None


def bind(runtime_globals: dict) -> None:
    bind_runtime(globals(), runtime_globals, _RUNTIME_DEPENDENCIES)


def auto_invest_plans(fund: dict) -> list[dict]:
    configs = fund.get("autoInvestConfigs")
    if not isinstance(configs, list) or not configs:
        legacy = fund.get("autoInvestConfig")
        configs = [legacy] if isinstance(legacy, dict) else []
    return [dict(config) for config in configs if isinstance(config, dict)]


def fund_disciplines(fund: dict) -> list[dict]:
    disciplines = fund.get("disciplines")
    if not isinstance(disciplines, list):
        return []
    return [dict(discipline) for discipline in disciplines if isinstance(discipline, dict)]


def _night_watch_section(portfolio: dict) -> dict:
    raw = portfolio.get("nightWatchCodes")
    has_customized = isinstance(raw, list)
    codes = [str(c) for c in raw if c] if has_customized else []
    return {
        "codes": codes,
        "count": len(codes),
        "has_customized": has_customized,
    }


def _purchase_limit_section(portfolio: dict) -> dict:
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
    }


def _auto_invest_section(portfolio: dict, validated_code: str = "") -> dict:
    items = []
    plan_count = 0
    enabled_plan_count = 0
    for fund in portfolio.get("funds", []):
        fund_code = str(fund.get("code") or "").strip()
        if validated_code and fund_code != validated_code:
            continue
        plans = auto_invest_plans(fund)
        if not plans:
            continue
        plan_count += len(plans)
        enabled_plan_count += sum(1 for plan in plans if plan.get("enabled") is True)
        items.append({
            "code": fund_code,
            "name": fund.get("name", ""),
            "groupId": fund.get("groupId", ""),
            "plans": plans,
        })
    return {
        "items": items,
        "fundCount": len(items),
        "planCount": plan_count,
        "enabledPlanCount": enabled_plan_count,
    }


def _disciplines_section(portfolio: dict, validated_code: str = "") -> dict:
    items = []
    discipline_count = 0
    triggered_count = 0
    for fund in portfolio.get("funds", []):
        fund_code = str(fund.get("code") or "").strip()
        if validated_code and fund_code != validated_code:
            continue
        disciplines = fund_disciplines(fund)
        if not disciplines:
            continue
        discipline_count += len(disciplines)
        triggered_count += sum(1 for discipline in disciplines if discipline.get("triggered") is True)
        items.append({
            "code": fund_code,
            "name": fund.get("name", ""),
            "groupId": fund.get("groupId", ""),
            "disciplines": disciplines,
        })
    return {
        "items": items,
        "fundCount": len(items),
        "disciplineCount": discipline_count,
        "triggeredCount": triggered_count,
    }


async def get_portfolio_preferences(
    include_night_watch: bool = True,
    include_purchase_limit: bool = True,
    include_auto_invest: bool = True,
    include_disciplines: bool = True,
    code: str = "",
) -> dict:
    """
    一次读取用户在 App 中配置的组合偏好：夜盘自选、限购观察、定投计划、止盈止损纪律。

    该聚合工具只读，不会创建、修改、暂停或删除任何计划。所有 section 来自
    同一次云端实时同步主数据快照，共享会话缓存，不产生额外网络请求。

    旧版单工具（get_night_watchlist、get_purchase_limit_watchlist、
    get_auto_invest_plans、get_fund_disciplines）仍可用，但新会话建议优先
    使用本工具一次取回，减少调用轮次。

    Args:
        include_night_watch: 是否返回 nightWatch section（夜盘自选代码列表）。
        include_purchase_limit: 是否返回 purchaseLimit section（限购观察列表）。
        include_auto_invest: 是否返回 autoInvest section（定投计划）。
        include_disciplines: 是否返回 disciplines section（止盈止损纪律）。
        code: 可选，6 位基金代码；只对定投与纪律 section 生效，留空返回全部基金。

    Returns:
        dict 包含：
        - nightWatch: {codes, count, has_customized}；未自定义时为 {codes: [], count: 0, has_customized: false}
        - purchaseLimit: {items, codes, count, has_customized}
        - autoInvest: {items, fundCount, planCount, enabledPlanCount}
        - disciplines: {items, fundCount, disciplineCount, triggeredCount}
        - dataUpdatedAt: 云端实时同步主数据时间
    """
    _require_token()
    validated_code = _validate_fund_code(code) if code else ""
    portfolio = await _download_portfolio()
    sections: dict = {}
    if include_night_watch:
        sections["nightWatch"] = _night_watch_section(portfolio)
    if include_purchase_limit:
        sections["purchaseLimit"] = _purchase_limit_section(portfolio)
    if include_auto_invest:
        sections["autoInvest"] = _auto_invest_section(portfolio, validated_code)
    if include_disciplines:
        sections["disciplines"] = _disciplines_section(portfolio, validated_code)
    sections["dataUpdatedAt"] = portfolio.get("_meta_updated_at", "")
    return sections


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
    result = _night_watch_section(portfolio)
    result["dataUpdatedAt"] = portfolio.get("_meta_updated_at", "")
    return result


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
    result = _purchase_limit_section(portfolio)
    result["dataUpdatedAt"] = portfolio.get("_meta_updated_at", "")
    return result


async def get_auto_invest_plans(code: str = "") -> dict:
    """
    读取用户在 App 中设置的定投计划。只读，不会创建、修改、暂停或删除计划。

    同时兼容旧版单计划 autoInvestConfig 与新版多计划 autoInvestConfigs，
    并统一返回每只基金的 plans 数组。

    Args:
        code: 可选，6 位基金代码；留空返回全部已配置定投的基金。

    Returns:
        dict 包含 items、fundCount、planCount、enabledPlanCount 和 dataUpdatedAt。
    """
    _require_token()
    validated_code = _validate_fund_code(code) if code else ""
    portfolio = await _download_portfolio()
    result = _auto_invest_section(portfolio, validated_code)
    result["dataUpdatedAt"] = portfolio.get("_meta_updated_at", "")
    return result


async def get_fund_disciplines(code: str = "") -> dict:
    """
    读取用户在 App 中为基金设置的止盈止损纪律。只读，不会新增、修改、触发或删除纪律。

    Args:
        code: 可选，6 位基金代码；留空返回全部已配置纪律的基金。

    Returns:
        dict 包含 items、fundCount、disciplineCount、triggeredCount 和 dataUpdatedAt。
    """
    _require_token()
    validated_code = _validate_fund_code(code) if code else ""
    portfolio = await _download_portfolio()
    result = _disciplines_section(portfolio, validated_code)
    result["dataUpdatedAt"] = portfolio.get("_meta_updated_at", "")
    return result
