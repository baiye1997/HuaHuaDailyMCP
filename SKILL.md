---
name: huahua-daily
description: 花花日记助手 - 查询数据/收益/记录，获取概览信息
homepage: https://github.com/baiye1997/HuaHuaDailyMCP
user-invocable: false
metadata: {"openclaw":{"requires":{"env":["BAIYE_AGENT_TOKEN"],"bins":["mcporter"]},"primaryEnv":"BAIYE_AGENT_TOKEN","emoji":"🌸"}}
---

# 花花日记助手 (HuahuaDaily)

通过此技能查询花花日记数据，包括项目行情、持仓记录、收益概况等。

## 调用方式

使用 `mcporter call` 命令调用工具：

```bash
mcporter call huahua-daily.<工具名> 参数名=值
```

## 可用工具

### 认证
- `set_token` — 设置 Agent Token 和 API 地址（一般不需要，已通过环境变量配置）

### 数据查询（无需认证）
- `search_item` — 按编号/名称搜索项目
- `get_item_detail` — 获取项目详情
- `get_item_estimate` — 批量获取今日估算数值
- `get_daily_rank` — 今日涨跌幅排行
- `get_item_history` — 历史数值走势
- `get_item_dividends` — 历史派息记录

### 概览数据（无需认证）
- `get_status` — 今日状态查询
- `get_overview` — 整体概览
- `get_indices` — 主要指数

### 记录管理（需 Agent Token）
- `get_current_user` — 当前账号信息
- `get_records` — 完整记录
- `get_summary` — 总资产摘要
- `request_transaction` — 发送交易请求

## 示例

```bash
# 搜索项目
mcporter call huahua-daily.search_item query="华夏"

# 获取项目详情
mcporter call huahua-daily.get_item_detail code="000001"

# 获取概览
mcporter call huahua-daily.get_overview

# 获取当前用户信息
mcporter call huahua-daily.get_current_user
```
