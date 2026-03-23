# 花花日记 MCP 服务（HuahuaDaily）

通过 MCP 协议让 OpenClaw 等 AI agent 访问花花日记的数据，支持查询持仓收益、市场行情、发送交易请求等。

> **前置要求：** 花花日记 PRO 会员（Agent Token 为 PRO 专属功能）

---

## 安装步骤

### 第一步：安装 mcporter（如尚未安装）

OpenClaw 无法直接连接 MCP 服务进程，需要 **mcporter** 作为桥接工具。请参考 mcporter 官方文档完成安装。

### 第二步：获取 Agent Token

前往 https://huahuadaily.preview.aliyun-zeabur.cn/ 注册账号并开通 PRO 会员，或在已安装的花花日记 App 中操作：

1. 打开花花日记 App → 设置页
2. 点击「Agent 访问令牌」
3. 点击「生成新令牌」，完成邮箱验证
4. 复制一次性显示的令牌（关闭后无法再查看）

### 第三步：从 ClawHub 安装（官方推荐）

```bash
clawhub install huahua-daily
```

安装后在 OpenClaw 配置中添加环境变量 `BAIYE_AGENT_TOKEN`。

ClawHub 主页：https://clawhub.ai/baiye1997/huahua-daily

### 第四步：在 mcporter.json 中添加配置（手动安装）

#### 方式一：uvx（推荐，无需手动安装 Python 环境）

> 需先安装 [uv](https://docs.astral.sh/uv/getting-started/installation/)，uvx 会自动管理依赖。

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
        "BAIYE_AGENT_TOKEN": "粘贴你的 Agent 令牌"
      }
    }
  }
}
```

#### 方式二：本地 Python 脚本

先克隆仓库并安装依赖：

```bash
git clone https://github.com/baiye1997/HuaHuaDailyMCP.git skills/huahua-daily
cd skills/huahua-daily
pip install -r requirements.txt
```

然后在 mcporter.json 中添加：

```json
{
  "mcpServers": {
    "huahua-daily": {
      "command": "python",
      "args": ["/你的路径/skills/huahua-daily/server.py"],
      "env": {
        "BAIYE_AGENT_TOKEN": "粘贴你的 Agent 令牌"
      }
    }
  }
}
```

---

## 数据同步说明

MCP 的持仓数据来自**云端同步备份**，不是实时本地数据。

| 数据类型 | 来源 | 说明 |
|---------|------|------|
| 估算净值（`estimatedNav`、`todayProfit`） | 实时拉取 | 每次查询均为最新 |
| 市值、持仓收益、累计收益率 | 官方净值（`lastNav`） | 与 App 首页一致 |
| 持仓份额、成本价、交易记录 | 最近一次云同步 | `dataUpdatedAt` 字段显示上传时间 |

**如果你刚在 App 中刷新了数据或新增了交易，请先在 App「设置 → 立即同步」手动上传，再来 AI 端查询。**

---

## 在 OpenClaw 中添加 System Prompt（可选）

加入以下内容可让 AI 更准确地响应自然语言查询：

```
你可以访问花花日记（HuahuaDaily）MCP 工具来查询我的基金持仓数据。

使用规则：
- 查询我的总资产/今日收益/累计收益时，调用 get_summary
- 查询我的完整持仓明细时，调用 get_records
- 查询某只基金的实时估算/涨跌时，调用 get_item_estimate
- 查询市场整体行情时，调用 get_overview 或 get_indices
- 搜索基金时，调用 search_item
- 如果我想买入或卖出，调用 request_transaction 发送信号让我在 App 中确认
- 如果我想对比大盘/沪深300，调用 get_benchmark_history
- 如果我问今天/某日下单几天后到账，调用 calculate_trading_dates
- 如果我问某日是否交易日或节假日后首个交易日，调用 get_next_trading_day
- 数据来自云同步，若我提到"刚刚刷新"，请提醒我先在 App 触发同步
- 不要反复调用相同工具，一次查询结果可复用回答多个问题
```

---

## 文件说明

| 文件 | 用途 |
|------|------|
| `server.py` | MCP 服务实现（FastMCP，20 个工具） |
| `pyproject.toml` | 打包配置，定义 `huahua-daily` 命令入口（uvx 部署必需） |
| `SKILL.md` | AI 指令文件（OpenClaw skill 描述） |
| `requirements.txt` | Python 依赖（mcp、httpx） |
