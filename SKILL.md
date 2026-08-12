---
name: huahua-daily
description: Use HuahuaDaily MCP for authorized portfolio and transaction queries, fund and market data, strategy backtests and quant snapshots, community actions, screenshot recognition, and App-confirmed trade or import requests. Trigger when users ask about their HuahuaDaily holdings or cloud sync, request fund or market analysis through HuahuaDaily, run or review portfolio backtests, save or review strategy snapshots, use HuahuaDaily community features, or send transactions/imports for App confirmation.
---

# 花花日记助手（HuahuaDaily）

## 0. Compatibility

This SKILL.md intentionally uses the smallest common Agent Skills format: YAML frontmatter with only `name` and `description`, followed by Markdown instructions. Platform-specific setup for Codex, Codex CLI, Claude Code, Claude Desktop, OpenClaw, and other MCP clients belongs in README/configuration, not in this file.

## 1. 核心边界

花花日记 MCP 让 Agent 读取用户授权的云端同步数据、基金行情、交易流水和系统公告，识别截图，并向 App 发送待确认请求。

Agent 不直接写入交易、不直接导入持仓、不覆盖云同步。所有买入、卖出、持仓导入、自选导入、交易记录导入，都必须由用户在 App 确认页最终确认。

社区授权、取消授权、关注/取消关注、社区收益同步是直接后端写操作，不走 App 待确认页。只有用户明确确认该社区操作时才调用；不要把它们描述为“已发送到 App 等待确认”。

MCP 可读取完整持仓、交易流水、原始云端实时同步主数据和截图内容，可能包含金额、成本、收益率等敏感投资数据。回答时不要主动暴露超过用户问题所需的明细。

策略实验室的组合回放和历史试算必须调用服务端工具，不要在 Agent 内复制交易排序、收益或回撤算法。`save_quant_snapshot` 是不可变的“当时判断”档案：真实持仓和组合版本由服务端捕获，只保存市场状态、特征、逐基金观察、风险否决和数据质量，不创建虚拟账户、不计算模拟收益、不保存建议金额，也不会下单。

业务请求仅通过 MCP 注册工具执行。`server.py` 是兼容入口，`huahua_mcp_runtime` 是内部实现包；内部 Python 模块不构成公共调用面。

## 2. 会话启动

每个 Agent 会话首次使用 HuahuaDaily 时，调用：

```json
get_tool_manifest()
```

用途：
- 确认可用工具、认证方式、安全边界。
- 检查 MCP 启动时生成的 `runtime.updateCheck`。若 `updateAvailable=true`，先告知用户当前版本、最新版本和返回的 `updateInstructions`；不要自行安装或覆盖用户环境。`unavailable` 只表示版本检查暂不可用，不阻断其他工具。
- 检查 `backendCompatibility`。若 `compatible=false`，说明后端量化契约与当前 MCP 不兼容，不要继续调用量化写入工具；`unavailable` 只表示握手暂不可用。
- 不访问用户数据，不消耗行情请求。

Token 缺失、无效或过期时，提示用户在 App「小窝 / 设置 → Agent 访问令牌」重新生成，并配置环境变量 `HUAHUA_AGENT_TOKEN`。

如果当前 MCP client 支持运行时传 token，也可以调用：

```json
set_token({"token": "HUAHUA_AGENT_TOKEN_VALUE"})
```

确认当前账号信息（昵称、UID、会员状态）：

```json
get_current_user()
```

适合回答"我是谁""我的会员什么时候到期"等问题。

## 3. 查询持仓和云端实时同步

本节所有持仓、交易、分组、标签、自选和原始同步数据读取，都以云端实时同步主数据为准：固定读取结构化组合快照，不读取旧版同步大包。不要把 `history_snapshot` 或 `/api/cloud-snapshots` 历史备份快照当成当前持仓数据源。

### 3.1 用户问“今天收益/总资产/持有收益”

首选：

```json
get_summary()
```

返回重点：
- `totalMarketValue`：总市值。
- `todayProfit`：今日收益。
- `todayProfitRate`：今日/昨日收益率，口径为 `todayProfit / totalDayBaseMarketValue × 100%`，不要用当前总市值重算。
- `totalDayBaseMarketValue`：`todayProfitRate` 使用的归属日组合期初市值。
- `displayedDayCompleteness`：组合当日收益完整度。若 `complete=false` 或 `pendingAttributionCount>0`，说明至少一只 QDII/T+N 最新官方净值尚无可靠 G 日；现有 `todayProfit` / `todayProfitRate` 仅覆盖可归属基金，不得表述为完整组合当日收益。
- `estimateCompleteness`：当前估值帧可用性。若 `complete=false`、`timeoutCount>0` 或 `staleCount>0`，至少一只持仓缺少可用估值帧；`evidenceComplete`、`partialCodes` 和汇率/代理证据用于避免 Agent 虚构完整覆盖。普通回答不要主动逐只传播这些技术状态，只有用户明确询问诊断、证据或估算口径时才展开。0 元不能表述为真实零涨跌；过期 last-good 只供内部审计，不参与今日收益。
- `totalHoldingProfit`：持有收益。
- `totalHoldingReturnRate`：持有收益率。
- `cumulativeProfit`：累计收益；这是本 App 已记录交易推导的累计，仅在用户明确询问历史累计或该字段时使用。
- `portfolioUpdatedAt`（兼容字段 `dataUpdatedAt`）：云端实时同步主数据时间。
- `strategyPreferences.maxDrawdownLimitPct`：用户在策略实验室设置的组合回撤阈值百分数；`0` 表示未启用。不得自行假定为 10%。

回答时必须说明 `portfolioUpdatedAt`（旧客户端可读 `dataUpdatedAt`）。原始数据中的 `data.timestamp`/`meta.payload_timestamp` 只是客户端快照谱系或迁移元数据，不表示同步新鲜度。如果同步时间明显旧，提醒用户在 App 开启实时同步或点击「从云端同步恢复 / 手动同步」相关入口。

不要为了资产概况先调用 `get_raw_sync_data()`。

### 3.2 用户问“完整持仓/自选/分组”

首选：

```json
get_records({"include_transactions": false})
```

返回重点：
- `holdings`：有持仓的基金；已配置定投时含 `autoInvestPlans`。
- `watchlist`：App 中可见的自选或清仓观察项；不包含已送养隐藏项，同代码的显式自选优先；
  与 App 刷新口径一致，含估算值及 source/freshness/estimateAudit（观察列不按估算计价）；
  已配置定投时含 `autoInvestPlans`。
- `groups`：分组。
- `summary`：汇总。
- `portfolioUpdatedAt`（兼容字段 `dataUpdatedAt`）：云端实时同步主数据时间。

云端实时同步主数据会保存最后一次官方净值作为恢复基线，但不会保存盘中估值等高频行情。`get_records` 会主动拉取最新行情，并比较行情帧的官方 `dwjz/last_nav_date` 与主数据 `lastNav/lastNavDate`：`marketValue` 使用较新的官方锚点，`valuationNavDate`/`valuationSource` 说明依据；盘中 `estimatedNav` 仅用于 `estimatedMarketValue` 和当日收益，绝不冒充官方市值。

当前口径：持仓市值和持有收益只按官方净值计价；MCP 可用行情接口返回的更新官方锚点修正滞后的云端恢复基线，但盘中估算不会回填官方市值。`cumulativeProfit` 是本 App 已记录交易推导的累计收益，不代表用户所有平台/历史清仓买卖的完整累计收益。`get_records` 会读取云端主数据里的 `userPreferences.fundDataSourceMode` 和基金级 `dataSourceMode`，自动按用户选择的行情源请求估值。

`huahua` 是稳定的花花托管策略身份，不等于某一个固定内部实现。用户明确要求排查链路时才读取并展开 holdings/watchlist 的 `estimateAudit`：`provider`、`engine`、`proxyCoverage`、`fxDegraded`、`partial`、`evidenceComplete`、`fallback`，以及审计传输实际提供时才存在的 `coverage`。普通回答只给估值时间、类型、来源、涨幅、估算净值和官方净值日期；不能把代理描述成持仓股票完整覆盖。`targetNavDate`/`latestOfficialNavDate` 是净值 D 日，`estimateDisplayDate` 是估算展示/T 帧日期，`returnAttributionDate` 才是可靠收益 G 日；后者为 null 时不得用 D 日代替。

用户询问定投计划、止盈止损纪律、夜盘自选或限购观察等组合偏好时，优先使用聚合只读工具一次取回（共享同一快照缓存，不产生额外网络请求）：

```json
get_portfolio_preferences({"include_night_watch": true, "include_purchase_limit": true, "include_auto_invest": true, "include_disciplines": true, "code": ""})
```

返回 `nightWatch`（夜盘实际生效代码，可传给 `get_night_estimate`）、`purchaseLimit`（按 App 迁移规则得到的实际生效限购观察，可配合 `get_batch_fund_fees`）、`autoInvest`（定投计划）和 `disciplines`（止盈止损纪律）四个 section。`nightWatch.configuredCodes` 与 `purchaseLimit.configuredItems` 保留用户原始配置；不要把默认池误述为用户手动添加。只读，不会创建、修改、暂停或删除任何计划；不得把 `triggered=true` 描述成 Agent 已执行交易。

需要单独读取某一类偏好时，也可用旧工具 `get_auto_invest_plans`、`get_fund_disciplines`、`get_night_watchlist`、`get_purchase_limit_watchlist`（full profile）。

如果用户要求交易流水、成本来源、审计收益，再调用：

```json
get_transactions({"code": "", "include_pending": true})
```

需要费用、确认日、净值日和分页游标齐全的量化账本时，优先调用：

```json
get_transaction_ledger({"start_date": "2026-01-01", "end_date": "2026-12-31", "limit": 100})
```

账本的日期筛选和排序统一使用 `effectiveDate = confirmDate || tradeDate`；`tradeDate` 与 `confirmDate` 仍会同时返回用于审计。不要按下单日自行重排确认后的持仓。

真实组合历史单位净值与回撤使用：

```json
get_portfolio_nav_history({"start_date": "2025-01-01", "end_date": "2026-01-01", "benchmark_code": "000300"})
```

不要用 `get_transactions` 返回值自行另算一套组合净值。

或：

```json
get_records({"include_transactions": true})
```

### 3.3 用户问“云端主数据是不是最新/同步是否完整”

先调用：

```json
get_sync_meta()
```

返回重点：
- `updated_at`：云端实时同步主数据更新时间。
- `etag`：云端主数据指纹。
- `data_source`：`structured_portfolio` 表示结构化实时同步主数据。
- `size_bytes`：主数据大小。
- `has_restorable_sync_payload`：是否可由新版 App 安全恢复。
- `empty_portfolio_confirmed`：是否是用户确认过的空组合主数据；为 true 且可恢复时，不要误判为云端损坏。
- `history_snapshot`：最新云端历史快照摘要，只用于恢复、回滚和灾备，不代表当前主数据。

需要完整检查时调用：

```json
get_raw_sync_data({"include_json_text": false})
```

默认复用会话内 30 秒组合缓存；若刚完成实时同步，先调用 `get_sync_meta()` 确认
`updated_at` 已更新，再对比 `get_raw_sync_data` 返回的 `meta.updated_at`。仅当用户
明确要求导出原始 JSON 时才设置 `include_json_text=true`（该模式绕过缓存，只用于
导出/迁移审计，不要默认使用）。

检查重点：
- `data.funds` 是否存在且非空。
- 若 `meta.is_confirmed_empty_portfolio_snapshot=true`，这是用户确认清空组合后的合法空组合主数据。
- `data.groups`、`data.watchlistGroups` 是否存在。
- `data.globalTags` 是否存在。
- `data.nightWatchCodes`、`data.purchaseLimitWatchItems`、`data.marketIndexSelection` 是否存在。
- `meta.contains_ledger` 通常为 false，这是正常的。

### 3.4 用户问“标签/分组”

分组：

```json
get_groups()
```

标签：

```json
get_tags()
```

使用规则：
- `get_groups()` 用于解释持仓账户分组、自选分组。
- `get_tags()` 用于解释全局标签和每只基金绑定标签。

### 3.5 用户问“限购观察/哪些基金限制申购”

先读取用户在 App 保存的观察列表：

```json
get_purchase_limit_watchlist()
```

再按需对返回的代码调用 `get_batch_fund_fees(codes)` 或 `get_fund_fees(code)` 查看申购状态、QDII/限大额日累计限购金额和确认天数。`items[].lastSnapshot` 只是 App 最近一次检查快照，当前状态仍以费用接口为准；`snapshot` 是兼容别名。旧版本或尚未同步过该功能的云端主数据会按 App 相同规则并入默认池，并通过 `migrationApplied=true` 标明。

### 3.6 策略实验室

需要多只基金官方净值时，使用 `get_batch_fund_nav_history`，不要并发循环调用 `get_item_history`。逐基金检查 `coverageStart`、`coverageEnd`、`baselineDate` 和 `complete`；只有请求区间的期初基线与结束边界都覆盖时，`complete` 才为 true。

量化复盘优先使用 `get_quant_strategy_context` 获取紧凑、真实、可审计的聚合输入。`view=full` 的 `market.indices` 包含全部启用指数的服务端预计算收益、均线、回撤、波动和 `trendState`；默认 compact 视图只保留主基准明细。`market.indexGroups`、`market.indexThemes`、`leaders20d`、`laggards20d` 在两种视图中都已完成市场宽度、科技成长等主题结构、平均收益与强弱排序。使用排名前必须检查 `rankingEligible`、`asOf`、`freshness` 和 `market.indexCoverage.rankingAsOf`。Agent 不得再逐指数拉取原始历史或自行计算、计数、排序，只负责解释这些确定性结果。该上下文不含资讯、Serenity 研究、评分、信号、建议金额或交易建议。

逐基金 `metrics` 已直接提供 `r5Pct`、`r10Pct`、`r20Pct` 等交易点收益，
`bias5Pct`、`bias10Pct`、`bias20Pct`、`bias60Pct` 分别表示最新官方净值相对最近
5、10、20、60 个有效官方净值点简单均值的乖离百分比；`consecutiveDownDays`
表示最新官方净值序列的连续下跌交易点数。Agent 和策略引擎必须直接使用这些
服务端字段，并在字段为 `null` 或列入 `missing` 时退出对应判断，不得拉取原始
净值自行重算。

个人组合量化复盘应先单独调用 `get_quant_strategy_context`，不要同时并发调用
`get_index_metrics`、`get_fund_flow` 或 `get_status`。上下文已经包含核心指数指标、
与持仓相关的板块资金流、执行窗口和数据质量；只有用户随后明确要求完整市场明细，
或需要诊断服务健康状态时，才按需补充对应工具。读取 `portfolio.risk` 时同时检查
`blockingFunds` 与 `pendingFirstReturnFunds`：后者表示新持仓尚未产生首个可归属 G 日
收益，不等同于历史不可重建。若全部持仓都处于该状态，顶层阻断原因为
`portfolio_risk_pending_first_return`，不得改写成“历史数据丢失”。

MCP 默认请求 `view=compact`：保留分析就绪状态、风控、执行、市场和逐基金核心指标，省略
可由顶层审计统一表达的逐基金指标来源/方法版本、重复净值与成本明细以及
`drillRefs`；`market.indices` 只保留主基准逐指数明细，全市场结构仍由
`indexCoverage`、`indexGroups`、`indexThemes`、`leaders20d` 和 `laggards20d`
完整表达。需要逐基金份额、成本、官方净值、完整指数明细或下钻引用时才显式使用
`view=full`。两种视图复用同一份服务端 canonical Context 缓存，不会重复触发重任务。

`execution.canCancel` 表示当前是否存在可撤销的花花日记本地 `PENDING` 记录，
`execution.cancelableTransactionIds` 给出对应 ID，语义固定为
`delete_local_pending_ledger_record`。这与外部基金公司订单无关；尚未在 App
确认的 Agent 请求则通过 `update_agent_request(..., "DISMISSED")` 撤回提示。

历史回测使用 `run_portfolio_backtest`，统一采用零费率。`strategy_type=target_rebalance` 按 `none/daily/weekly/monthly/quarterly` 频率恢复目标权重；`strategy_type=threshold_reentry` 按止盈、止损及反向波动再次买入阈值运行。只能提交基金代码、目标权重、日期、初始资金和这些白名单参数；不得提交动态代码、URL、文件路径或表达式。如果要重试同一次运行，复用同一 `client_run_id`。

运行成功后保留返回的 `run_id`。需要读取已保存回测、审计完整交易或继续分页时调用：

```json
get_portfolio_backtest({
  "run_id": 123,
  "trade_offset": 0,
  "trade_limit": 100,
  "max_series_points": 300
})
```

`trade_limit` 最大 200，`max_series_points` 最大 500。完整审计应持续使用 `nextTradeOffset` 分页，直到该字段为空。已保存的服务端交易序列是回测审计的权威数据源。

需要证明“某日、某版本、基于当时数据得出了什么判断”时调用 `save_quant_snapshot`：

```json
save_quant_snapshot({
  "snapshot_key": "strategy-a:<北京时间今天>:close:v1",
  "snapshot_date": "<北京时间今天 YYYY-MM-DD>",
  "strategy_id": "strategy-a",
  "strategy_version": "1.0.0",
  "group_id": "<可选的资产分组 ID>",
  "data_cutoff_at": "<不晚于当前写入时间的 UTC ISO 时间>",
  "market_mode": {"regime": "range"},
  "features": {"momentumWindow": 20},
  "risk": {"portfolioAlert": false},
  "data_quality": {"complete": true},
  "fund_signals": [{
    "code": "000001",
    "observation": "HOLD",
    "triggers": ["20日动量仍为正"],
    "riskVeto": {"blocked": false, "reasons": []}
  }]
})
```

只分析某个资产分组时，组合查询、历史试算和 `save_quant_snapshot` 必须使用同一个 `group_id`；未传表示全部持仓，旧快照也按全部持仓解释。

`snapshot_key` 是幂等键，同一键且内容相同才返回原记录，内容不同会返回冲突。首版只允许写入北京时间当天快照，`data_cutoff_at` 不能晚于服务端写入时间，也必须属于快照当天。服务端会补入真实持仓、组合版本、写入时间和 SHA-256 `payloadHash`。每条逐基金观察必须明确 `observation`、`triggers` 和 `riskVeto.blocked`；任何层级出现建议金额、建议份额或同义建议文本都会被拒绝。读取旧判断用 `get_quant_snapshots` 分页获取摘要，再传 `snapshot_id` 读取完整内容。后续方向统一调用 `get_quant_snapshot_review`，按 1、7、20、60 个收益日读取后端权威验证结果；不得自行复制收益或 G 日归属算法，不回填或覆盖原快照，也不得把 QDII 涨跌提前。需要复盘真实加减仓时调用 `get_portfolio_trade_review`，不要从交易账本自行推算 T1/T7/T20/T60 表现。

## 4. 查询基金和市场

### 4.1 用户提供 6 位基金代码

查询实时估算：

```json
get_item_estimate({"codes": ["110022"]})
```

用途：
- “现在涨多少”
- “今天估算净值”
- “这只今天收益如何”

注意：
- `codes` 最多 50 个。
- 可批量传入，避免逐个调用。
- 可用当前新鲜帧在同一 session 内缓存 60 秒；reset/unavailable/cache-only miss 或 stale 不缓存，后续调用可及时读到物化恢复帧。
- 可传 `default_data_source_mode`（`source_a`/`source_b`/`huahua`）和 `data_source_mode_by_code`，对齐 App 的多行情源设置；默认是 `source_a`，只有 Pro 可切换，未知值会直接报错。
- 必须检查顶层 `complete`、`missingCodes`、`invalidCodes`、`unavailableCodes` 和 `timeoutCodes`；部分返回或 timeout 占位帧不能当成整批成功。
- `complete` 只表示每个代码都有可用数值；还要内部检查 `evidenceComplete`、`partialCodes`、`fxDegradedCodes` 和每项 `estimateEvidence.proxyCoverage/fxStatus`，避免作出错误完整性断言。`fxStatus=omitted` 表示本地资产涨幅仍可用。普通回答不主动枚举这些技术状态；只有用户明确要求诊断时，才用 `estimateEvidence.calibration{applied,reason,weight,modelVersion}` 等证据解释口径，并明确市场因子、QDII 市场代理或板块代理不等于持仓股票完整覆盖。
- 数据来源 A/B 对部分基金没有覆盖时，只表示对应基金或来源不可用；必须按代码检查上述集合，不能把单来源缺失描述成整批基金请求失败。

### 4.2 用户只提供基金名称

先搜索：

```json
search_item({"query": "易方达消费"})
```

处理规则：
- 搜索结果只有一个高可信候选时，可继续查询。
- 多个候选或名称相近时，先让用户确认代码。
- 不要凭名字猜代码后直接发交易请求。

### 4.3 用户要深度分析单只基金

按需调用：

```json
get_item_detail({"code": "110022"})
get_item_history({"code": "110022"})
get_fund_source_previews({"code": "110022"})
get_fund_fees({"code": "110022"})
get_item_dividends({"code": "110022"})
get_fund_period_rank({"code": "110022"})
get_batch_fund_period_ranks({"codes": ["110022", "161725"]})
get_fund_timeline({"code": "110022"})
get_fund_profile({"code": "110022"})
get_batch_fund_profiles({"codes": ["110022", "161725"]})
get_fund_quant_metrics({"code": "110022", "view": "technical"})
get_batch_fund_quant_metrics({"codes": ["110022", "161725"], "view": "momentum"})
```

选择规则：
- 当前估算/涨跌：`get_item_estimate`。
- 对比同一基金的多个行情源：`get_fund_source_previews`。来源面板不是统一的“实时估值”：
  净值公布后，每个来源可能返回收盘前归档估值、当前上游 A/B 已切换的官方值，
  权威官方净值，或花花严格证据链产出的关联标的估算。必须同时检查
  条目的 `source` 与 `last_estimate_snap.source`；
  `data` 缺少数据来源 A/B 只表示单来源覆盖或归档不足，不代表整个请求失败。
- 显式选择数据来源 A/B 但该源无覆盖时，后端会继续回退完整花花链路；检查
  `dataSourceSelection.fellBackToHuahua`，不得把回退值
  误述为上游 A/B 的值。该回退只影响对应基金，不应把整批请求判为失败。
- 历史走势：`get_item_history`。
- 申购状态、QDII/限大额日累计限购金额、确认天数：`get_fund_fees`（单只）或 `get_batch_fund_fees`（批量，最多 50 只）；批量结果检查 `complete` 和 `missingCodes`。
- 分红派息：`get_item_dividends`。
- 近 1/3/6 月、1 年排名：`get_fund_period_rank`（单只）或 `get_batch_fund_period_ranks`（批量，最多 50 只）；批量排名从 `data` 读取并检查 `complete` 和 `missingCodes`。
- 今日盘中估值曲线：`get_fund_timeline`；若用户指定行情源，传 `source_mode`。
- 基础详情与持仓信息：`get_item_detail`。该工具不触发量化计算；收益、均线偏离、
  回撤、波动和历史统计必须按需调用 `get_fund_quant_metrics`。
- QDII 夜盘物化估值：`get_night_estimate`（需会员，最多 30 只）；用户在 App 添加的夜盘自选基金列表用 `get_night_watchlist`，通常先调这个再传给 `get_night_estimate`。forecast 看 `currentComplete/warming/frameRefreshing`，last_close 看 `complete`，不能把固定收盘快照的 stale 当作刷新失败。`item.fxStatus=omitted` 仍可 ready，但证据不完整；持仓模型的 `item.calibration` 是只读校准审计，夜盘不会训练。
- 基金画像（综合信息）：`get_fund_profile`。包含费率、排名、持仓、行业、分红、风险指标等。
- 批量画像：`get_batch_fund_profiles`（最多 20 只）。读取 `data`，并检查
  `complete`、`missingCodes`、`timedOut`；缺失表示服务端在 20 秒预算内未取得，
  不得臆造画像或把部分结果当完整结果。任何非法基金代码都会使调用直接
  失败，不会被静默跳过。
- 单基金量化数据：`get_fund_quant_metrics`。必须按问题选择视图：`technical`
  只取技术卡与历史统计，`momentum` 只取短中期收益、均线偏离和连跌，`risk`
  只取中长期收益、回撤和波动，只有确实同时需要两类数据时才用 `full`。这些数据
  均由后端按统一口径计算；如已取得盘中估算帧，可在 `technical/full` 视图传
  `technical_value`、`value_basis="live_estimate"` 及日期字段。同步传递估算结果的
  `freshness`、`stale`、`fallbackReason` 和 `lastGoodCapturedAt`；响应为
  `estimateFreshness="stale"` 或 `"unavailable"` 时必须明确数据口径，不能当作新鲜
  盘中值。`value_basis="official_nav"` 时不得传入自定义净值，官方值始终由服务端读取。
- 多基金排序/对比：`get_batch_fund_quant_metrics`。必须传语义视图；
  `technical/momentum/risk` 最多 50 只，`full` 最多 10 只。
  优先一次批量调用，不要并发调用多次单只接口，也不要拉取 NAV 历史重复计算。
  如传 `current_frames`，同样检查每项的 `estimateFreshness`、`estimateStale` 和
  `fallbackReason`。`current_frames` 只适用于 `technical/full`。顶层 `complete` 只表示
  全部代码至少有一条官方净值；指标窗口看 `item.metrics.complete`（`full` 看
  `item.official.metrics.complete`），历史统计看 `item.current.status`。`computing` 按
  `retryAfterMs` 稍后重试，
  `insufficient_history` / `insufficient_samples` 是当前数据集下的终态，不得推断缺失
  统计。返回值只提供数据与历史统计，不包含买卖方向或建议金额。

### 4.4 用户问市场整体

用户只问指数结构、均线、收益或强弱时，直接使用服务端指标接口，不要为了
一个指数拉取个人持仓上下文：

```json
get_index_metrics({"codes": ["399006", "000688", "KS11"]})
```

省略 `codes` 返回全部已启用指数。必须检查 `complete`、`rankingEligible`、
`asOf`、`freshness`、`historyFreshness`、`historyExpectedAsOf`、
`historyFreshnessBasis`、`historyLagCalendarDays` 和 `technicalValueBasis`；
历史新鲜度按所属市场当前时刻已完成的预期收盘日判断，calendar lag
仅作跨度展示。`historyFreshness=stale` 或 `unknown` 时不得使用对应 MA、收益或
排名结论，即使实时价格本身可用。不得调用
`get_instrument_history` 自行计算 MA、收益、回撤、波动或排名。

概览：

```json
get_overview()
```

主要指数：

```json
get_instrument_catalog()
get_instrument_quotes({"codes": ["000300", "000001"]})
```

板块风向：

```json
get_sector_wind()
```

板块结构、均线和强弱排名直接调用：

```json
get_sector_metrics()
```

该工具一次返回全部已配置行业/主题 ETF 代理的服务端预计算指标；必须检查
`historyBasis`、`technicalValueBasis`、`asOf`、`freshness`、
`historyFreshness`、`historyExpectedAsOf`、`historyFreshnessBasis`、
`historyLagCalendarDays` 和 `rankingEligible`。`fund_nav_fallback` 仅作降级展示，
不参与场内强弱排名。交易日历不可证明完整时，
`historyFreshness=unknown` 且必须退出排名。
不得再调用
`get_instrument_history` 自行计算 MA、收益、回撤、波动或排名。

`get_fund_flow()` 的 `sectorFlow` 正常同时包含 `industry` 与 `concept`。
始终检查 `sectorFlow.freshness`、`partial`、`categoriesPresent` 和
`categoriesFailed`。若某一分类由完整 last-good 快照补齐，还会返回
`categoryFreshness` 与 `categoryPolledAt`；字段存在时必须检查，不得把补齐分类
描述成当前轮询时点的实时数据。

今日涨跌榜：

```json
get_daily_rank()
```

上一交易日涨跌榜：

```json
get_yesterday_rank()
```

是否交易日：

```json
get_status()
```

### 4.5 用户问"大家都在买什么/热门基金"

持有人排行：

```json
get_holder_ranking()
```

返回 App 内持有人数最多的 30 只基金，含持有人数和涨跌幅。

### 4.6 用户问"资金在流向哪里/板块热度"

资金流向：

```json
get_fund_flow()
```

返回 `fundFlow`（基金资金流）、`sectorFlow`（板块资金流）、`polledAt`（数据时间）。
先检查 `sectorFlow` 是否非空；非空时 `byCategory.industry` 与
`byCategory.concept` 始终存在。同时检查 `categoriesPresent`、
`categoriesFailed`、`partial` 和 `sectorFlow.freshness`。若响应包含
`categoryFreshness` 和 `categoryPolledAt`，再按分类核对它们，
不得把上游缺失或 last-good 补齐解释为当前轮零流入。
需要 PRO 会员权限。适合回答"主力资金在买什么板块""哪些基金被大额申购/赎回"等问题。

### 4.7 用户问指数/ETF 行情

目录：

```json
get_instrument_catalog()
```

最近物化行情快照：

```json
get_instrument_quotes({"codes": ["000300", "000001"]})
```

这里必须使用 `get_instrument_catalog` 返回的标准代码；程序化查询严格按请求
集合返回，不会自动补默认标的或截断成 App 卡片数量。
`updatedAt/quoteDate` 是源行情时点，`polledAt` 是缓存采集时点。必须检查
`cacheMeta.freshness/missingCodes/staleCodes/repairingCodes`；repairing 表示后台补帧，
本次请求不会为了“强刷”而直连 Yahoo。

分时走势：

```json
get_instrument_timeline({"code": "000300"})
```

历史数据：

```json
get_instrument_history({"code": "000300", "period": "1m"})
```

### 4.8 用户问"跑赢大盘/对比沪深300"

默认沪深300：

```json
get_benchmark_history({"code": "sh000300"})
```

常用代码：
- `sh000300`：沪深300。
- `sh000001`：上证指数。
- `sz399001`：深证成指。
- 数字 ETF 代码也可传入，如 `510300`。

需要基金自身走势时，再调用 `get_item_history(code)`。

### 4.9 用户问 QDII 基金夜盘

QDII 基金投资美股/港股，北京时间夜间才是它们的交易时段。夜盘工具读取共享物化帧，行情允许处于当前轮刷新或等待 poller 的状态，不是股票软件逐笔报价。

**推荐流程（无需用户报代码）**：先用 `get_night_watchlist()` 读用户在 App 添加的夜盘自选列表，再用其结果调 `get_night_estimate()`：

```json
get_night_watchlist()
// 返回 {"codes": ["016665", "018147", ...], "count": N, "has_customized": true, "dataUpdatedAt": "..."}
```

若 `has_customized=false`（用户未自定义过），codes 为空，应提示用户先去 App 夜盘页面添加自选基金，或允许用户手动指定一组代码。

```json
get_night_estimate({"codes": ["016665", "018147"]})
```

`force` 是废弃兼容参数；true/false 都不会跳过服务端共享缓存或触发 Yahoo 抓取。`view: "last_close"` 查询上一收盘快照口径，默认 `forecast`。一次最多 30 只。

返回每只基金的：
- `estimatedChangePercent`：盘后复合涨跌幅（股价×汇率）。
- `estimatedNav`：估算净值。
- `breakdown`：穿透到个股的持仓明细、股价涨跌、汇率变动、贡献度。
- `status`：`ready`（数据就绪）/ `pending`（等待开盘）/ `closed`（休市）。
- `currentComplete`：forecast 是否全部为当前新鲜帧；必须同时看 `warming`、`frameRefreshing`、`pollerPendingCodes`、`timeoutPendingCodes`、`staleCodes`。
- `complete`：所选 view 的返回完整度。last_close 即使 freshness=stale 也可能是完整固定历史快照，此时 `currentComplete=false` 是正常结果。

注意：
- 需要 VIP 或 PRO 会员。
- 非美股交易时段返回休市状态，不是错误。
- `actual_session_date` 是海外行情交易日，顶层 `date` 是北京时间响应日；item 的 `navRequiredDate/lastNavDate` 是基金净值 D 日。它们都不能直接当作基金收益归属 G 日。
- 不要在 A 股交易时段频繁调用。
- 夜盘自选列表需要 App 至少做过一次实时同步才能读到用户自定义值；云端主数据没有 `nightWatchCodes` 时，`has_customized=false`、`source=default`，`codes` 已返回与 App 一致的默认池，不能提示用户必须手动逐只添加。

### 4.10 用户问交易日/T+N

下一个交易日：

```json
get_next_trading_day({"date": "2026-05-13"})
```

基金确认日期：

```json
calculate_trading_dates({
  "date": "2026-05-13",
  "time_mode": "PRE_MARKET",
  "confirm_days": 2
})
```

参数：
- `time_mode`: `PRE_MARKET` 表示收盘前，`POST_MARKET` 表示收盘后。
- `confirm_days`: T+1/T+2/T+3 等，未知时先用 `get_fund_fees(code)` 获取 `confirm_days`；该工具也返回 `daily_purchase_limit` 等限购字段。

返回口径：
- `data_date` 是按 `nav_date` 与 `confirm_days` 反推的估值反映日，返回中会明确给出 `data_date_inferred=true` 和 `data_date_basis=nav_date_minus_confirm_days_offset`。
- 它不是上游已观察到的官方净值 D 日、公布日或收益归属 G 日；不得把它当作已确认日期向用户陈述。

## 5. 交易请求

### 5.1 用户想买入/卖出

先确认：
- 基金代码。
- 基金名称。
- 买入或卖出。
- 买入金额；卖出时明确按金额还是按份额，并确认对应数值。
- 日期，可留空让 App 使用今日。
- 分组 ID 和名称；如果用户指定了账户/分组，先从 `get_records` 取稳定的 `groupId`。
- `client_request_id`；7 天内重试同一逻辑请求时必须复用，超过窗口请生成新的请求 ID。

发送请求：

```json
request_transaction({
  "item_code": "110022",
  "item_name": "易方达消费行业股票",
  "record_type": "BUY",
  "amount": 1000,
  "date": "2026-05-13",
  "note": "Agent 发起",
  "group_name": "我的账户",
  "group_id": "group-id",
  "client_request_id": "tx:110022:20260513:buy:1"
})
```

规则：
- `record_type` 只能是 `BUY` 或 `SELL`。
- 卖出使用 `sell_mode="AMOUNT"` 配合 `amount`，或 `sell_mode="SHARES"` 配合 `shares`。
- 指定分组时优先传 `group_id`；精确匹配失败会由 App 让用户选择，不会静默落到其他持仓。
- 7 天内重试同一请求时复用 `client_request_id`，不要重新生成；服务端会在该窗口内保留幂等记录。
- 如果基金代码来自搜索推断，必须先让用户确认。
- 调用后必须告诉用户：“请求已发送，请打开花花日记 App 确认后才会生效。”
- 不要说“已买入”或“已卖出”。

### 5.2 查看或撤销待处理请求

查看：

```json
get_agent_requests()
```

用户明确要求忽略/撤销时：

```json
update_agent_request({
  "request_id": "请求 id",
  "status": "DISMISSED"
})
```

不要替 App 把请求标记为 `PROCESSED`；MCP 会拒绝该状态，只有 App 能在用户确认后设置。

### 5.3 个人报告投递

仅在用户明确要求生成并保存报告时调用：

```json
submit_personal_strategy_report({
  "title": "8月2日 个人组合复盘",
  "summary": "今日组合主要受科技和黄金方向影响。",
  "payload": {
    "kind": "evening",
    "date": "2026-08-02",
    "body": "基于用户已授权数据生成的报告正文。",
    "sections": [],
    "riskNotes": ["不构成投资建议，仅供复盘参考。"]
  },
  "client_message_id": "personal:2026-08-02:evening"
})
```

规则：

- 只投递到当前 Agent Token 所属用户的报告中心，不能指定 `user_id`，不能广播。
- Pro 用户在 App 创建的默认 Agent Token 已具备该权限，无需额外选择。
- 同一报告重试必须复用 `client_message_id`；同一 ID 携带不同内容会被服务端拒绝。
- 可使用用户明确授权读取的持仓、交易和行情生成报告。
- 不得调用 `/api/hermes/reports`；该接口只属于管理员开发者 MCP。

## 6. 截图导入

### 6.1 持仓/自选截图识别

截图一律使用 Base64 传入（`image_paths` 本地路径已禁用，调用会直接报错，
防止读取并上传任意本地文件）：

```json
import_holding_screenshots({
  "images_base64": [
    {"filename": "holding.png", "mime": "image/png", "base64": "..."}
  ],
  "import_type": "HOLDINGS"
})
```

自选截图（务必传 `import_type: "WATCHLIST"`）：

```json
import_holding_screenshots({
  "images_base64": [
    {"filename": "watchlist.png", "mime": "image/png", "base64": "..."}
  ],
  "import_type": "WATCHLIST"
})
```

Base64：

```json
import_holding_screenshots({
  "images_base64": [
    {"filename": "holding.png", "mime": "image/png", "base64": "..."}
  ],
  "import_type": "HOLDINGS"
})
```

本地路径模式已禁用：`image_paths` 传入会直接报错（安全限制，防止读取并上传任意本地文件），请一律使用 `images_base64`。

`import_type` 说明：
- `HOLDINGS`（默认）：持仓页面通常不显示基金代码，后端按名称四步匹配（可能出现模糊匹配）。
- `WATCHLIST`：自选页面明确显示 6 位代码，后端用专门 prompt 提取代码并精确匹配；AI 漏识别代码时回退名称匹配。**自选场景务必传此值**，否则会强制走名称模糊匹配。

返回重点：
- `items`：识别条目。
- `summary.total`：总条数。
- `summary.unmatched`：未匹配数量。
- `resolution_required`：是否需要轻确认。
- `resolution_reason`：轻确认原因。

用途：
- 持仓截图导入（`import_type="HOLDINGS"`）。
- 自选截图导入（`import_type="WATCHLIST"`）。

识别后不要直接声称导入完成。

### 6.2 交易记录截图识别

截图同样使用 Base64 传入（`image_paths` 已禁用）：

```json
import_transaction_screenshots({
  "images_base64": [
    {"filename": "transactions.png", "mime": "image/png", "base64": "..."}
  ]
})
```

同样地，`image_paths` 已禁用（传入会直接报错），一律使用 `images_base64`。

返回重点：
- `type`: `BUY` 或 `SELL`。
- `fund_name`：截图识别名称。
- `fund_code`：匹配代码。
- `fund_real_name`：标准基金名。
- `matched`：是否匹配。
- `date`、`time_mode`、`amount`、`shares`。
- `skip` / `skip_reason`：应跳过的条目。
- `resolution_required` / `resolution_reason`。

### 6.3 Agent 轻确认规则

只在对话里确认“识别歧义”，不要让用户在对话里完成大型表格审核。

需要轻确认的情况：
- `resolution_required=true`。
- `match_status=unmatched`。
- `matched=false`。
- 多个候选基金。
- 日期缺失或明显不合法。
- 买入缺 `amount`。
- 卖出缺 `shares`。

轻确认完成后，修改 `items` 中对应字段，再发送到 App。

### 6.4 发送到 App 确认页

持仓导入：

```json
request_import_review({
  "import_type": "HOLDINGS",
  "items": [...],
  "source_note": "Agent 识别持仓截图",
  "client_request_id": "import:holdings:20260513:1"
})
```

自选导入：

```json
request_import_review({
  "import_type": "WATCHLIST",
  "items": [...],
  "source_note": "Agent 识别自选截图",
  "client_request_id": "import:watchlist:20260513:1"
})
```

交易记录导入：

```json
request_import_review({
  "import_type": "TRANSACTIONS",
  "items": [...],
  "source_note": "Agent 识别交易记录截图",
  "client_request_id": "import:transactions:20260513:1"
})
```

限制：
- `import_type` 只能是 `HOLDINGS`、`WATCHLIST`、`TRANSACTIONS`。
- `items` 最多 300 条。
- 请求体最多 1MB。
- 7 天内重试同一导入请求时复用 `client_request_id`，避免重复确认页；超过窗口请生成新的请求 ID。

调用后必须告诉用户：
- “已发送到 App，请打开花花日记批量确认。”
- “导入尚未完成，只有 App 确认后才会写入。”

## 7. 喵舍社区

### 7.1 排行榜

```json
get_community_ranking({"tab": "weekly"})
```

`tab` 可选 `weekly`（周收益）、`monthly`（月收益）、`total`（总收益）。

我的排名：

```json
get_community_my_rank()
```

用户详情（十大重仓前5）：

```json
get_community_user({"uid": "12345678"})
```

搜索用户（UID / 昵称）：

```json
search_community_users({"query": "花花"})
```

关注/粉丝数：

```json
get_community_stats()
```

关注列表：

```json
get_community_following()
```

授权管理：

```json
// 查询授权状态
get_community_authorization()

// 授权参与排行（须向用户确认）
authorize_community({"show_amount": false, "anonymous": false})

// 取消授权，退出排行
revoke_community_authorization()
```

关注操作：

```json
// 关注/取消关注（取反操作）
follow_community_user({"target_uid": "12345678"})
```

规则：
- 社区功能需要 PRO 会员。
- 授权、取消授权、关注/取消关注调用后会直接生效，不会进入 App 确认页；调用前必须向用户明确确认。
- 授权操作前须向用户确认是否愿意公开持仓数据，以及是否展示金额、是否匿名。
- `follow_community_user` 是取反操作：已关注则取消，未关注则添加。
- 社区排名收益由服务端基于实时云端组合数据核算，MCP 不提供手动写入收益率工具。
- 系统公告、社区通知和弹幕属于 App 推送与展示功能，MCP 不再提供查询工具。

## 8. JCTI 投资人格分析

用户完成 JCTI（韭彩测试指标）答题后，可提交四维分数获取 AI 个性化分析：

```json
analyze_jcti({
  "personality_id": "tepulang",
  "ye": 85,
  "wen": 60,
  "sui": 30,
  "duan": 45
})
```

参数：
- `personality_id`：人格 ID，可选 `tepulang`（特普朗）、`jiuhuang`（韭黄）、`faguo-dushen`（法国赌神）、`ji-wuli`（姬无力）、`yingshengchong`（应声虫）、`shanmu`（山姆）、`taozhongren`（套中人）、`tuoluowang`（陀螺王）。
- `ye` / `wen` / `sui` / `duan`：野、稳、随、短四个维度的分数，每项 0-100。

返回 AI 生成的个性化投资人格分析文本。需要 VIP 或 PRO 会员。

## 9. App 版本信息

最新版本：

```json
get_app_version()
```

返回版本号、更新日志、下载地址、是否强制更新。

## 10. 常见降级

- `401`：Token 无效或过期，要求用户重新生成。
- `403`：权限不足或会员状态不满足；Agent Token 和多数 MCP 能力需要 PRO，部分行情/JCTI 能力可能要求 VIP 或 PRO。
- 云端无数据：要求用户打开 App 确认实时同步已开启，或从设置页主动同步 / 恢复云端主数据。
- 行情估算为空：可能是非交易日、盘前或数据源暂不可用，不要当作错误。
- 截图识别为空：提示用户换清晰截图，或分批上传。
- 导入请求发送成功后：不要继续追问大表格细节，等待用户在 App 确认。
- 持有人排行需要 PRO 会员，非会员返回 403。
