# 基金与市场

## 基金识别

- 用户提供 6 位代码：直接调用对应批量或单只工具。
- 用户只提供名称：先 `search_item`；多个候选时向用户轻确认。
- 多只基金优先批量工具，避免逐只循环。

## 常用能力

- 当前估值：`get_item_estimate`。
- 画像、费率、周期排名、量化指标：优先批量版本。
- 市场概览：`get_overview`；只需要交易状态时用 `get_status`。
- 指数/ETF：先 catalog，再 quotes；时间线和历史只在用户需要时读取。
- 资金流和板块：使用 fund flow、sector metrics 等有界工具，不把单一指标解释成确定交易信号。
- 交易日、确认日推导：使用 `calculate_trading_dates` / `get_next_trading_day`，不按自然日猜节假日。

## 数据表达

- 明确区分官方净值、盘中估算和 QDII 夜盘参考。
- 夜盘只作执行参考，不是官方净值，也不是已确认收益。
- 技术指标数据不足、freshness 不可靠或 partial 时说明限制。
- 用户要完整长区间历史文件时使用 CLI export；普通分析使用 MCP 的范围参数。
