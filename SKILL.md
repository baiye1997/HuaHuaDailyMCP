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

**核心原则：一个字段一行，用空行分块，视觉清晰**

---

## 用户信息 `get_current_user`

```
👤 **{nickname}** `{username}`

UID: {uid}
身份: VIP✨
Pro到期: {pro_date}
```

---

## 资产摘要 `get_summary`

```
📊 **资产总览**

💰 总市值
**{totalMarketValue:,.0f}**

📈 累计收益
**{cumulativeProfit:+,.0f}** ({totalReturnRate:+.2%})

📅 今日收益
{todayProfit:+,.0f}

🔢 持仓: {heldItemCount} 支
📦 在途: {totalInTransitAmount}
```

---

## 持仓记录 `get_records`

**每个持仓单独一行，空行分隔**

```
📊 **持仓总览** ({count} 支)

**{name1}** `{code1}`
市值 {value:,.0f} | 收益 {profit:+,.0f} ({rate:+.1%})

**{name2}** `{code2}`
市值 {value:,.0f} | 收益 {profit:+,.0f} ({rate:+.1%})

**{name3}** `{code3}`
市值 {value:,.0f} | 收益 {profit:+,.0f} ({rate:+.1%})

**{name4}** `{code4}`
市值 {value:,.0f} | 收益 {profit:+,.0f} ({rate:+.1%})

**{name5}** `{code5}`
市值 {value:,.0f} | 收益 {profit:+,.0f} ({rate:+.1%})

---

🏆 **盈利王**
{best_name} `{best_code}`
+{best_profit:,.0f} ({best_rate:+.1%})

💀 **亏损王**
{worst_name} `{worst_code}`
{worst_profit:,.0f} ({worst_rate:+.1%})

---

📄 累计收益: **{cumulative:+,.0f}** ({rate:+.2%})
```

---

## 大盘概览 `get_overview`

**每个指数单独一行**

```
🌍 **今日大盘**

上证指数
{sh:,.1f} ({sh_pct:+.2%})

深证成指
{sz:,.0f} ({sz_pct:+.2%})

创业板指
{cy:,.0f} ({cy_pct:+.2%})

科创50
{kc:,.0f} ({kc_pct:+.2%})

恒生指数
{hs:,.0f} ({hs_pct:+.2%})

纳斯达克
{nq:,.0f} ({nq_pct:+.2%})
```

---

## 项目详情 `get_item_detail`

**分层展示，每块用空行分隔**

```
📈 **{name}** `{code}`

─── 持仓 ───

市值
**{value:,.0f}**

收益
**{profit:+,.0f}** ({rate:+.1%})

份额
{shares:,.2f}

成本净值
{cost:.4f}

当前净值
{nav:.4f}

预估净值
{est:.4f} ({est_pct:+.2%})

─── 交易记录 ───

{date} | {type} | {amount:,.0f} | 净值 {nav}

─── 重仓股 ───

{s1} — {p1:.1%}
{s2} — {p2:.1%}
{s3} — {p3:.1%}

─── 点评 ───

💡 {comment}
```

---

## 搜索结果 `search_item`

**每个结果单独一行，用空行分隔**

```
🔍 **搜索结果** (共 {total} 条)

**{name1}** `{code1}`
{type}

**{name2}** `{code2}`
{type}

**{name3}** `{code3}`
{type}
```

---

## 涨跌排行 `get_daily_rank`

```
📊 **今日排行** | {date}

🚀 **涨幅榜**

1. **{name}** `{code}`
   +{rate:.2%}

2. **{name}** `{code}`
   +{rate:.2%}

3. **{name}** `{code}`
   +{rate:.2%}

📉 **跌幅榜**

1. **{name}** `{code}`
   {rate:.2%}

2. **{name}** `{code}`
   {rate:.2%}

3. **{name}** `{code}`
   {rate:.2%}
```

---

# 格式要点

1. **一行一字段** — 绝不在一行挤多个值
2. **空行分块** — 用空行清晰分隔不同信息块
3. **标签在值上方** — 重要数据单独一行加粗
4. **代码反引号** — 基金代码用 `code` 格式
5. **收益正负标记** — 正数加 `+` 前缀
6. **智能精简**:
   - 持仓最多显示 5 个
   - 重仓股只显示前 3
   - 交易记录只显示最近 1 笔
