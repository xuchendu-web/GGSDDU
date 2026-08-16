# AGENTS.md

## Cursor Cloud specific instructions

本仓库会给 Cursor Cloud Agent 使用。分析 A 股盘面、板块、ETF、商品或 jctrader 信号时：

1. 先读并遵循 `.cursor/skills/jctrader/SKILL.md`。
2. 云端 MCP 目录常常只有 `cursor-cloud`，看不到 jctrader 工具。这时不要判定服务不存在，直接运行：

```bash
python3 .cursor/skills/jctrader/scripts/jctrader_client.py board
```

3. 只使用 jctrader 返回的数字和名单，不要编造信号，也不要用网页行情顶替。
4. 项目里同时有 `.cursor/mcp.json`。若会话已注入 jctrader MCP 工具，优先走 MCP。

仓库本身没有需要安装的应用依赖。jctrader 客户端只用 Python 标准库。
