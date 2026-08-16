# AGENTS.md

## Cursor Cloud specific instructions

jctrader 是 **MCP 服务**（`jctrader-mcp` v1.0.0），不是独立技能包。配置与上次接入相同：

```json
{
  "mcpServers": {
    "jctrader": {
      "type": "sse",
      "url": "http://8.159.152.196:3000/sse?token=friends-chenji"
    }
  }
}
```

仓库文件：`.cursor/mcp.json`。桌面 Cursor 打开本仓库后，在 Settings / Customize → MCP 启用 `jctrader`。

### 云端限制

Cursor Cloud Agent **不支持 SSE**，也不会自动加载项目里的 `.cursor/mcp.json`。要在云端把 jctrader 当 MCP 工具用，到 [cursor.com/agents](https://cursor.com/agents) 的 MCP 下拉菜单添加 **stdio** 服务器：

- command: `python3`
- args: `.cursor/skills/jctrader/scripts/jctrader_stdio_mcp.py`

该桥接进程在 VM 内把 stdio 转到上面的 SSE 地址。

若当前会话仍没有 jctrader MCP 工具，不要判定服务不存在，改跑：

```bash
python3 .cursor/skills/jctrader/scripts/jctrader_client.py board
```

只使用 jctrader 返回的数据，不要编造信号。
