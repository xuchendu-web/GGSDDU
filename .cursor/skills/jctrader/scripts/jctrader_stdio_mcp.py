#!/usr/bin/env python3
"""stdio MCP 桥：把 jctrader 的远程 SSE 服务转成本地 stdio，供 Cloud Agent 接入。

Cursor Cloud 自定义 MCP 只支持 HTTP / stdio，不支持 SSE。
本进程在 VM 内运行，对上讲 stdio，对下连
http://8.159.152.196:3000/sse?token=...
"""

from __future__ import annotations

import json
import os
import sys
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parent))
from jctrader_client import DEFAULT_BASE, DEFAULT_TOKEN, JctraderClient  # noqa: E402


def _read_message() -> dict[str, Any] | None:
    headers: dict[str, str] = {}
    while True:
        line = sys.stdin.buffer.readline()
        if not line:
            return None
        if line in (b"\r\n", b"\n"):
            break
        decoded = line.decode("utf-8", errors="replace")
        if ":" not in decoded:
            continue
        key, value = decoded.split(":", 1)
        headers[key.strip().lower()] = value.strip()
    length = int(headers.get("content-length", "0"))
    if length <= 0:
        return None
    body = sys.stdin.buffer.read(length)
    return json.loads(body.decode("utf-8"))


def _write_message(payload: dict[str, Any]) -> None:
    data = json.dumps(payload, ensure_ascii=False, separators=(",", ":")).encode("utf-8")
    sys.stdout.buffer.write(f"Content-Length: {len(data)}\r\n\r\n".encode("ascii"))
    sys.stdout.buffer.write(data)
    sys.stdout.buffer.flush()


def _ok(rid: Any, result: Any) -> dict[str, Any]:
    return {"jsonrpc": "2.0", "id": rid, "result": result}


def _err(rid: Any, code: int, message: str) -> dict[str, Any]:
    return {"jsonrpc": "2.0", "id": rid, "error": {"code": code, "message": message}}


def main() -> int:
    base = os.environ.get("JCTRADER_MCP_URL", DEFAULT_BASE)
    token = os.environ.get("JCTRADER_TOKEN", DEFAULT_TOKEN)
    remote: JctraderClient | None = None
    tools_cache: list[dict[str, Any]] | None = None

    def ensure_remote() -> JctraderClient:
        nonlocal remote
        if remote is None:
            remote = JctraderClient(base, token)
        return remote

    while True:
        msg = _read_message()
        if msg is None:
            return 0
        method = msg.get("method")
        rid = msg.get("id")
        params = msg.get("params") or {}

        if method == "initialize":
            _write_message(
                _ok(
                    rid,
                    {
                        "protocolVersion": "2024-11-05",
                        "capabilities": {"tools": {"listChanged": False}},
                        "serverInfo": {"name": "jctrader-mcp", "version": "1.0.0"},
                    },
                )
            )
            continue
        if method == "notifications/initialized" or method == "notifications/cancelled":
            continue
        if method == "ping":
            _write_message(_ok(rid, {}))
            continue
        if method == "tools/list":
            try:
                if tools_cache is None:
                    tools_cache = ensure_remote().list_tools()
                _write_message(_ok(rid, {"tools": tools_cache}))
            except Exception as exc:  # noqa: BLE001
                _write_message(_err(rid, -32000, f"jctrader tools/list 失败: {exc}"))
            continue
        if method == "tools/call":
            name = params.get("name")
            arguments = params.get("arguments") or {}
            if not name:
                _write_message(_err(rid, -32602, "缺少 tools/call.name"))
                continue
            try:
                data = ensure_remote().call(name, arguments)
                text = json.dumps(data, ensure_ascii=False, indent=2)
                _write_message(
                    _ok(
                        rid,
                        {
                            "content": [{"type": "text", "text": text}],
                            "isError": False,
                        },
                    )
                )
            except Exception as exc:  # noqa: BLE001
                _write_message(
                    _ok(
                        rid,
                        {
                            "content": [{"type": "text", "text": f"jctrader 调用失败: {exc}"}],
                            "isError": True,
                        },
                    )
                )
            continue
        if rid is not None:
            _write_message(_err(rid, -32601, f"Method not found: {method}"))


if __name__ == "__main__":
    raise SystemExit(main())
