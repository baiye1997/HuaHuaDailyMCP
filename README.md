# HuaHuaDailyMCP

基金投资助手 MCP 技能 - 让 OpenClaw 连通你的基金数据。

## 功能

- 查询基金净值、收益、持仓
- 管理买卖记录
- 获取大盘行情

## 安装

```bash
claw skill install baiye1997/HuaHuaDailyMCP
```

## 配置

在 OpenClaw 的 MCP 配置中添加：

```json
{
  "mcpServers": {
    "baiye-fund": {
      "command": "python",
      "args": ["/path/to/server.py"],
      "env": {
        "BAIYE_API_BASE": "https://你的域名.zeabur.app",
        "BAIYE_AGENT_TOKEN": "从 App 设置页生成的 Agent 令牌"
      }
    }
  }
}
```

## 获取 Agent Token

1. 打开白也基金 App → 设置页
2. 点击「Agent 访问令牌」
3. 点击「生成新令牌」，完成邮箱验证
4. 复制一次性显示的令牌
