# 量化、回放与快照

## 策略上下文

- 默认调用 `get_quant_strategy_context(view="compact")`。
- 先检查 `readyForAnalysis`、`readyForAction`、`blockingReasons` 和 `dataQuality`，再生成结论。
- full view 只在 compact 缺少当前分析所需证据时使用。

## 历史与组合

- 交易账本使用分页和过滤条件。
- 组合净值、回撤与交易复盘必须使用后端统一 G 日口径。
- 批量基金净值是官方 D 日原始数据；进入组合收益或信号前使用后端返回的归属语义。
- 长区间完整净值导出走 `huahua export nav-history`。

## 回测

- 回测信号只能使用当时已可获得的数据；不能同日使用未来公布净值成交。
- 检查完整度、覆盖率、基准和方法版本，不把零费率或非严格 point-in-time 结果描述成真实可实现收益。
- `client_run_id` 在同一次回测重试中保持稳定。

## 快照

- 快照只归档观察和证据，不直接交易，也不保存建议金额。
- 写入前确认 data cutoff、策略 ID/版本和 risk veto。
- 保存重试使用稳定 snapshot key；读取列表使用分页，详情按 ID 获取。
