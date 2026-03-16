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

```bash
mcporter call huahua-daily.<工具名> 参数名=值 --output json
```

## 可用工具

### 概览与账户
- `get_overview` — 大盘概览（指数 + 板块）
- `get_summary` — 资产摘要（总市值/收益/持仓数）
- `get_records` — 完整持仓记录
- `get_current_user` — 用户信息

### 项目查询
- `search_item query="关键词"` — 搜索项目
- `get_item_detail code="代码"` — 项目详情
- `get_item_estimate` — 今日估算
- `get_daily_rank` — 涨跌排行

---

# 输出格式规范

**核心原则：一条消息说完，简洁优雅，Discord 友好（禁用 markdown 表格）**

## 用户信息 `get_current_user`

```
👤 **{nickname}** (`{username}`)
UID: {uid} | {'VIP✨' if vip else '普通用户'}
{'Pro会员至 ' + pro_expires_at[:10] if pro else ''}
```

## 资产摘要 `get_summary`

```
📊 **资产总览**
💰 总市值: **{totalMarketValue:,.2f}**
📈 累计收益: **{cumulativeProfit:+,.2f}** ({totalReturnRate:+.2%})
📅 今日收益: {todayProfit:+,.2f}
🔢 持仓: {heldItemCount}支 | 在途: {totalInTransitAmount}
```

## 持仓记录 `get_records`

**单条消息，智能截断（Top 5 + 盈亏王）**

```
📊 **持仓总览** | {heldItemCount}支 | 市值 {totalMarketValue:,.0f}

**Top 5 持仓**
• **{name1}** `{code1}` — {value1:,.0f} | {profit1:+,.0f} ({rate1:+.1%})
• {name2} `{code2}` — {value2:,.0f} | {profit2:+,.0f} ({rate2:+.1%})
• {name3} `{code3}` — {value3:,.0f} | {profit3:+,.0f} ({rate3:+.1%})
• {name4} `{code4}` — {value4:,.0f} | {profit4:+,.0f} ({rate4:+.1%})
• {name5} `{code5}` — {value5:,.0f} | {profit5:+,.0f} ({rate5:+.1%})

🏆 **盈利王**: {best_name} `{best_code}` +{best_profit:,.0f} ({best_rate:+.1%})
💀 **亏损王**: {worst_name} `{worst_code}` {worst_profit:,.0f} ({worst_rate:+.1%})

📄 累计收益: **{cumulativeProfit:+,.0f}** ({cumulativeRate:+.2%})
```

## 大盘概览 `get_overview`

```
🌍 **今日大盘**

上证 {sh_value:.1f} ({sh_change:+.2%}) | 深证 {sz_value:.0f} ({sz_change:+.2%})
创业板 {cy_value:.0f} ({cy_change:+.2%}) | 科创50 {kc_value:.0f} ({kc_change:+.2%})
恒生 {hs_value:.0f} ({hs_change:+.2%}) | 纳指 {nq_value:.0f} ({nq_change:+.2%})
```

## 项目详情 `get_item_detail`

**单条消息，分层展示**

```
📈 **{name}** `{code}`

**持仓** | 市值 {marketValue:,.0f} | 收益 {profit:+,.0f} ({rate:+.1%})
份额 {shares:,.2f} | 成本 {costPrice:.4f} | 净值 {nav:.4f}
预估: {estimateNav:.4f} ({estimateChange:+.2%})

**交易记录** ({transaction_count}笔)
{最近一笔: 日期 类型 金额 净值}

**前5重仓** | {stock1} {p1:.1%} | {stock2} {p2:.1%} | {stock3} {p3:.1%} | {stock4} {p4:.1%} | {stock5} {p5:.1%}

💡 {简要点评}
```

## 搜索结果 `search_item`

**最多5条，单行一条**

```
🔍 **搜索结果**

• **{name1}** `{code1}` — {type1}
• **{name2}** `{code2}` — {type2}
• **{name3}** `{code3}` — {type3}
(共 {total} 条结果)
```

## 涨跌排行 `get_daily_rank`

```
📊 **今日排行** | {date}

🚀 **涨幅榜**
1. {name1} `{code1}` +{rate1:.2%}
2. {name2} `{code2}` +{rate2:.2%}
3. {name3} `{code3}` +{rate3:.2%}

📉 **跌幅榜**
1. {name1} `{code1}` {rate1:.2%}
2. {name2} `{code2}` {rate2:.2%}
3. {name3} `{code3}` {rate3:.2%}
```

---

# 格式要点

1. **数字格式化**: 金额用千分位，收益率用百分比，保留合理精度
2. **收益标记**: 正数用 `+` 前缀和绿色/加粗，负数保持原样
3. **代码高亮**: 用反引号包裹基金代码
4. **层级清晰**: 用换行和空行分隔不同区块
5. **智能精简**: 
   - 持仓超过5支只显示 Top 5 + 盈亏王
   - 交易记录超过3笔只显示最近一笔
   - 重仓股只显示前5
6. **单条消息**: 所有输出必须能装进一条 Discord 消息（2000字符内）
