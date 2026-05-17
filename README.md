# 花花日记 MCP 服务（HuahuaDaily）

通过 MCP 让 Codex、Codex CLI、Claude Code、Claude Code CLI、Claude Desktop、Cursor、Windsurf、OpenClaw、Hermes Agent 以及其他支持 MCP 的 Agent 读取花花日记后端数据、查询市场行情、识别截图，并向 App 发送待确认交易或导入请求。

交易和导入不会由 Agent 直接写入。Agent 只负责识别、轻确认和发起请求，最终写入必须回到花花日记 App 的现有确认页。

## 前置条件

- 花花日记账号已开通 PRO。
- 在 App「小窝 / 设置 → Agent 访问令牌」生成新的 Agent Token。
- Token 只显示一次，配置为环境变量 `HUAHUA_AGENT_TOKEN`。

官方 API 固定地址：`https://huahua.preview.aliyun-zeabur.cn`

## 通用 MCP stdio 配置

适用于 Codex、Codex CLI、Claude Code、Claude Code CLI、Claude Desktop、Cursor、Windsurf、Hermes Agent 等支持 stdio MCP server 的 Agent。

```json
{
  "mcpServers": {
    "huahua-daily": {
      "command": "uvx",
      "args": [
        "--from",
        "git+https://github.com/baiye1997/HuaHuaDailyMCP#subdirectory=mcp-server",
        "huahua-daily"
      ],
      "env": {
        "HUAHUA_AGENT_TOKEN": "粘贴你的 Agent Token"
      }
    }
  }
}
```

## OpenClaw / ClawHub

```bash
clawhub install huahua-daily
```

然后配置环境变量 `HUAHUA_AGENT_TOKEN`。

## 建议 System Prompt

```text
你可以使用花花日记 HuahuaDaily MCP 工具查询用户基金持仓、交易流水、云同步状态、市场行情和公告，也可以识别截图并把导入结果发送到 App 确认页。

调用规则：
- 会话开始可调用 get_tool_manifest 自检能力和安全边界。
- 查询资产概况优先调用 get_summary；需要明细再调用 get_records。
- 需要审计交易流水或重算收益时，调用 get_transactions 或 get_records(include_transactions=true)。
- 需要完整云同步快照时，调用 get_raw_sync_data；不要默认请求 include_json_text=true。
- 查询某只基金行情：已知代码直接 get_item_estimate；未知代码先 search_item。
- 用户想买入/卖出时，必须先确认基金名称、代码、金额、分组，再调用 request_transaction。
- request_transaction 只发送待确认信号，必须明确告知用户需要打开 App 确认。
- 截图导入先调用 import_holding_screenshots 或 import_transaction_screenshots。
- 对 unmatched / ambiguous 条目只做轻确认，补齐基金代码、日期、金额、份额等识别歧义。
- 轻确认后调用 request_import_review，把整批结果发送到 App 现有导入确认页。
- 不要直接写云同步，不要声称导入已完成；用户必须在 App 批量确认后才会写入。
- 数据来自云同步。若用户刚在 App 操作，提醒其先在 App 执行「立即同步」再查询。
```

## 工具能力

认证与自检：

- `set_token(token)`：运行时设置 Agent Token。
- `get_tool_manifest()`：返回能力边界、认证方式和安全说明。
- `get_current_user()`：读取当前账号和会员信息。

云同步与持仓：

- `get_sync_meta()`：读取云同步更新时间、etag、大小。
- `get_raw_sync_data(include_json_text=false)`：读取解析后的完整云同步快照。
- `get_records(include_transactions=false)`：读取持仓、自选、实时估算收益和汇总。
- `get_summary()`：读取资产摘要。
- `get_transactions(code="", include_pending=true)`：读取交易流水。
- `get_groups()`：读取持仓分组和自选分组。
- `get_tags()`：读取全局标签和基金标签。

市场与基金：

- `search_item(query)`
- `get_item_estimate(codes)`
- `get_item_detail(code)`
- `get_item_history(code)`
- `get_item_dividends(code)`
- `get_fund_timeline(code)`
- `get_fund_fees(code)`
- `get_fund_period_rank(code)`
- `get_batch_fund_period_ranks(codes)`：批量获取多只基金排名，最多 50 只。
- `get_night_estimate(codes)`：QDII 基金夜间实时估值，含持仓穿透、汇率变动（需会员）。
- `get_daily_rank()`
- `get_status()`
- `get_overview()`
- `get_indices()`
- `get_benchmark_history(code="sh000300")`
- `calculate_trading_dates(date, time_mode="PRE_MARKET", confirm_days=1)`
- `get_next_trading_day(date)`

交易请求：

- `request_transaction(item_code, item_name, record_type, amount, date="", note="", group_name="")`
- `get_agent_requests()`
- `update_agent_request(request_id, status)`

截图导入：

- `import_holding_screenshots(image_paths?, images_base64?)`：识别持仓/自选截图，返回 `items`、`summary`、`resolution_required` 等字段，不写入数据。
- `import_transaction_screenshots(image_paths?, images_base64?)`：识别交易流水截图，返回交易类型、基金匹配、日期、金额/份额和歧义标记，不写入数据。
- `request_import_review(import_type, items, source_note?)`：把轻确认后的整批结果发送到 App 现有确认页。`import_type` 只能是 `HOLDINGS`、`WATCHLIST`、`TRANSACTIONS`。

社区与公告：

- `get_danmaku(code)`
- `send_danmaku(fund_code, text, color="#ffffff")`
- `get_notices(since=0)`

## 截图导入流程

1. Agent 调用截图识别工具，获取结构化结果。
2. Agent 只对未匹配或有歧义的条目做轻确认。
3. Agent 调用 `request_import_review` 创建一个批量导入请求。
4. App 展示一个 Agent Banner。
5. 用户点击后进入现有确认页：
   - `IMPORT_HOLDINGS` → 持仓截图导入确认页
   - `IMPORT_WATCHLIST` → 自选截图导入确认页
   - `IMPORT_TRANSACTIONS` → 交易记录截图导入确认页
6. 用户在 App 中批量编辑、分组、去重并确认后才写入。

## 数据完整性说明

云同步快照用于跨设备恢复，包含：

- `funds`：基金、自选、持仓、成本、交易记录、标签、纪律、定投等核心数据。
- `groups` / `watchlistGroups`：分组。
- `globalTags`：全局标签注册表。
- `fieldConfigs` / `watchlistFieldConfigs`：字段显示配置。
- `timestamp` / `version`：客户端导出时间和数据版本。

云同步通常不包含 `ledger`。收益日历账本是派生数据，App 会用交易记录和历史净值重建；本地备份导出会包含 ledger，但导入时也会清空并重建，避免旧账本覆盖新交易状态。

Agent 如需完整审计，应优先读取 `get_transactions` 和 `get_raw_sync_data`，不要只依赖 `get_summary`。

## 安全边界

- Agent Token 存储为 SHA256，不保存明文。
- Token 可设置有效期，可在 App 内撤销。
- 后端对 AgentToken 使用权限白名单。
- 交易类能力只创建待确认请求，不直接写入交易。
- 截图导入只把识别结果发送到 App 确认页，不直接写入数据。
- MCP 不提供云同步覆盖写入工具。
