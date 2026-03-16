---
name: huahua-daily
description: 花花日记助手 - 查询数据/收益/记录，获取概览信息（只读）
homepage: https://github.com/baiye1997/baiye-fund
user-invocable: false
metadata: {"openclaw":{"requires":{"env":["BAIYE_AGENT_TOKEN"]},"primaryEnv":"BAIYE_AGENT_TOKEN","emoji":"🌸","os":["darwin","linux","win32"]}}
---

# 花花日记助手 (HuahuaDaily)

通过此技能，OpenClaw 可以直接访问您的花花日记数据，支持查询数据行情、查看持仓记录与收益、获取整体概况等。
交易操作（买入/卖出/分红）请在 App 或网页端进行，MCP 仅作为只读展示端。

## 配置

在 OpenClaw 的 MCP 配置中添加以下内容：

```json
{
  "mcpServers": {
    "huahua-daily": {
      "command": "python",
      "args": ["/path/to/mcp-server/server.py"],
      "env": {
        "BAIYE_AGENT_TOKEN": "从 App 设置页生成的 Agent 令牌"
      }
    }
  }
}
```

> 如需连接自建后端，可额外添加 `"BAIYE_API_BASE": "https://你的域名"`

## 获取 Agent Token

1. 打开花花日记 App → 设置页
2. 点击「Agent 访问令牌」
3. 点击「生成新令牌」，完成邮箱验证
4. 复制一次性显示的令牌（关闭后无法再查看）

## 可用工具

### 认证
- `set_token` — 设置 Agent Token 和 API 地址

### 数据查询（无需认证）
- `search_item` — 按编号/名称搜索项目
- `get_item_detail` — 获取项目详情（数值、收益率、持仓、费率等）
- `get_item_estimate` — 批量获取今日估算数值（最多 50 个）
- `get_daily_rank` — 今日涨跌幅排行
- `get_item_history` — 历史数值走势
- `get_item_dividends` — 历史派息记录

### 概览数据（无需认证）
- `get_status` — 今日状态查询
- `get_overview` — 整体概览（指数 + 板块 + 涨跌榜）
- `get_indices` — 主要指数（沪深、纳斯达克等）

### 记录管理（需 Agent Token + 会员）
- `get_current_user` — 当前账号信息
- `get_records` — 完整记录 + 实时计算今日收益/累计收益/市值/在途资产
- `get_summary` — 总资产摘要（轻量版，含在途资金汇总）
- `request_transaction` — 向 App 发送交易请求，用户在 App 中一键确认后执行

> **交易流程说明：**
> `request_transaction` 仅发送"信号"，不直接写入数据。
> App 收到信号后弹出预填好的交易表单，由用户确认后走完整交易逻辑（净值日计算、手续费、PENDING 状态等），确保数据安全一致。
