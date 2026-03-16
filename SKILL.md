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

**核心原则：一条消息说完，只用 Discord 支持的格式（无表格）**

## Discord 支持的格式

```
**粗体**
*斜体* 或 _斜体_
__下划线__
~~删除线~~
`代码`
```代码块```
> 引用
||剧透||
```

---

## 用户信息 `get_current_user`

```
👤 **{nickname}** `{username}`
UID: {uid} | VIP✨
Pro会员至 {pro_date}
```

## 资产摘要 `get_summary`

```
📊 **资产总览**
💰 总市值: **{totalMarketValue:,.0f}**
📈 累计收益: **{cumulativeProfit:+,.0f}** ({totalReturnRate:+.2%})
📅 今日: {todayProfit:+,.0f}
🔢 持仓 {heldItemCount}支 | 在途 {totalInTransitAmount}
```

## 持仓记录 `get_records`

**单条消息，Top 5 + 盈亏王**

```
📊 **持仓** | {count}支 | 市值 {total:,.0f}

**Top 5**
• **{name1}** `{code1}` — {value:,.0f} | {profit:+,.0f} ({rate:+.1%})
• {name2} `{code2}` — {value:,.0f} | {profit:+,.0f} ({rate:+.1%})
• {name3} `{code3}` — {value:,.0f} | {profit:+,.0f} ({rate:+.1%})
• {name4} `{code4}` — {value:,.0f} | {profit:+,.0f} ({rate:+.1%})
• {name5} `{code5}` — {value:,.0f} | {profit:+,.0f} ({rate:+.1%})

🏆 盈利王: {best_name} `{best_code}` +{best:,.0f}
💀 亏损王: {worst_name} `{worst_code}` {worst:,.0f}

📄 累计 **{cumulative:+,.0f}** ({rate:+.2%})
```

## 大盘概览 `get_overview`

```
🌍 **今日大盘**

上证 {sh:,.1f} ({sh_pct:+.2%}) | 深证 {sz:,.0f} ({sz_pct:+.2%})
创业板 {cy:,.0f} ({cy_pct:+.2%}) | 科创 {kc:,.0f} ({kc_pct:+.2%})
恒生 {hs:,.0f} ({hs_pct:+.2%}) | 纳指 {nq:,.0f} ({nq_pct:+.2%})
```

## 项目详情 `get_item_detail`

**单条消息，分层展示**

```
📈 **{name}** `{code}`

**持仓** 市值 {value:,.0f} | 收益 {profit:+,.0f} ({rate:+.1%})
份额 {shares:,.2f} | 成本 {cost:.4f} | 净值 {nav:.4f}
预估 {est:.4f} ({est_pct:+.2%})

**交易** {最近一笔: 日期 类型 金额}

**重仓** {s1} {p1:.1%} | {s2} {p2:.1%} | {s3} {p3:.1%}

💡 {简要点评}
```

## 搜索结果 `search_item`

**最多5条，单行一条**

```
🔍 **搜索结果**

• **{name1}** `{code1}` — {type}
• **{name2}** `{code2}` — {type}
• **{name3}** `{code3}` — {type}
(共 {total} 条)
```

## 涨跌排行 `get_daily_rank`

```
📊 **今日排行** | {date}

🚀 **涨幅榜**
1. {name} `{code}` +{rate:.2%}
2. {name} `{code}` +{rate:.2%}
3. {name} `{code}` +{rate:.2%}

📉 **跌幅榜**
1. {name} `{code}` {rate:.2%}
2. {name} `{code}` {rate:.2%}
3. {name} `{code}` {rate:.2%}
```

---

# 格式要点

1. **数字格式化**: 金额千分位，收益率百分比，保留合理精度
2. **收益标记**: 正数 `+` 前缀 + 加粗，负数保持原样
3. **代码高亮**: 用反引号包裹基金代码
4. **用换行分块**: 空行分隔不同信息区块
5. **智能精简**: 
   - 持仓超过5支只显示 Top 5 + 盈亏王
   - 交易记录只显示最近一笔
   - 重仓股只显示前3
6. **单条消息**: 所有输出 ≤2000 字符
