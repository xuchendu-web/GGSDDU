#!/usr/bin/env python3
"""Call jctrader MCP tools over SSE. Used when Cursor Cloud has no jctrader MCP tools."""

from __future__ import annotations

import argparse
import json
import os
import sys
import threading
import time
import urllib.error
import urllib.request
from queue import Empty, Queue
from typing import Any


DEFAULT_BASE = "http://8.159.152.196:3000"
DEFAULT_TOKEN = "friends-chenji"

BOARD_CALLS = [
    ("sentiment", "get_market_sentiment", {"metric": "all"}),
    ("breadth", "get_market_breadth", {"index": "all"}),
    ("resonance", "get_market_resonance_matrix", {"granularity": "stock", "freshness_threshold": 5}),
    ("index_strength", "get_sector_strength", {"dimension": "index", "top_n": 20, "signal_type": "both", "sort_by": "strength"}),
    ("industry_strength", "get_sector_strength", {"dimension": "industry_l1", "top_n": 40, "signal_type": "both", "sort_by": "strength"}),
    ("industry_fresh", "get_sector_freshness", {"dimension": "industry_l1", "top_n": 15, "freshness_days": 5}),
    ("reversal", "get_reversal_risk", {"dimension": "industry_l1", "top_n": 12}),
    ("crowding", "get_signal_crowding", {"dimension": "industry_l1", "top_n": 15}),
    ("allocation", "get_allocation_weights", {"dimensions": ["industry_l1", "theme"], "exclude_crowded": True}),
    ("commodity", "get_commodity_signals", {"category": "all"}),
]


class JctraderClient:
    def __init__(self, base: str, token: str, timeout: float = 90.0) -> None:
        self.base = base.rstrip("/")
        self.token = token
        self.timeout = timeout
        self.events: Queue[tuple[str | None, str]] = Queue()
        self.session_id: str | None = None
        self._thread = threading.Thread(target=self._read_sse, daemon=True)
        self._thread.start()
        deadline = time.time() + 15
        while time.time() < deadline:
            if self.session_id:
                break
            time.sleep(0.05)
        if not self.session_id:
            raise RuntimeError("无法建立 jctrader SSE 会话，请检查地址、token 与网络")
        time.sleep(0.2)
        self._drain()
        self._rpc(
            "initialize",
            {
                "protocolVersion": "2024-11-05",
                "capabilities": {},
                "clientInfo": {"name": "jctrader-skill", "version": "1.0.0"},
            },
        )
        self._post({"jsonrpc": "2.0", "method": "notifications/initialized", "params": {}})

    def _sse_url(self) -> str:
        sep = "&" if "?" in self.base else "?"
        if self.base.endswith("/sse"):
            return f"{self.base}{sep}token={self.token}"
        return f"{self.base}/sse{sep}token={self.token}"

    def _read_sse(self) -> None:
        req = urllib.request.Request(self._sse_url(), headers={"Accept": "text/event-stream"})
        try:
            with urllib.request.urlopen(req, timeout=self.timeout) as resp:
                event = None
                data_lines: list[str] = []
                for raw in resp:
                    line = raw.decode("utf-8", errors="replace").rstrip("\n")
                    if line.startswith("event:"):
                        event = line[6:].strip()
                    elif line.startswith("data:"):
                        data_lines.append(line[5:].lstrip())
                    elif line == "":
                        if data_lines:
                            data = "\n".join(data_lines)
                            self.events.put((event, data))
                            if event == "endpoint" and "session_id=" in data:
                                self.session_id = data.split("session_id=")[-1].strip()
                        event = None
                        data_lines = []
        except Exception as exc:  # noqa: BLE001 — surface on next RPC
            self.events.put(("error", str(exc)))

    def _drain(self) -> None:
        while True:
            try:
                self.events.get_nowait()
            except Empty:
                return

    def _post(self, payload: dict[str, Any]) -> None:
        url = f"{self.base}/messages?session_id={self.session_id}"
        req = urllib.request.Request(
            url,
            data=json.dumps(payload).encode("utf-8"),
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        try:
            urllib.request.urlopen(req, timeout=30).read()
        except urllib.error.HTTPError as exc:
            if exc.code not in (200, 202):
                raise
        except urllib.error.URLError:
            # Some MCP SSE servers ACK via the stream only.
            pass

    def _rpc(self, method: str, params: dict[str, Any] | None = None, timeout: float | None = None) -> dict[str, Any]:
        rid = int(time.time() * 1000) % 1_000_000
        self._post({"jsonrpc": "2.0", "id": rid, "method": method, "params": params or {}})
        deadline = time.time() + (timeout or self.timeout)
        while time.time() < deadline:
            try:
                event, body = self.events.get(timeout=1)
            except Empty:
                continue
            if event == "error":
                raise RuntimeError(f"SSE 中断: {body}")
            try:
                obj = json.loads(body)
            except json.JSONDecodeError:
                continue
            if obj.get("id") == rid:
                if "error" in obj and "result" not in obj:
                    raise RuntimeError(json.dumps(obj["error"], ensure_ascii=False))
                return obj
        raise TimeoutError(f"调用超时: {method}")

    def list_tools(self) -> list[dict[str, Any]]:
        result = self._rpc("tools/list")
        return result["result"]["tools"]

    def call(self, name: str, arguments: dict[str, Any] | None = None) -> Any:
        result = self._rpc("tools/call", {"name": name, "arguments": arguments or {}})
        content = result["result"]["content"]
        if result["result"].get("isError"):
            raise RuntimeError(json.dumps(content, ensure_ascii=False))
        text = content[0]["text"]
        try:
            return json.loads(text)
        except json.JSONDecodeError:
            return {"_raw": text}

    def board(self) -> dict[str, Any]:
        out: dict[str, Any] = {}
        for key, name, args in BOARD_CALLS:
            out[key] = self.call(name, args)
        return out


def _parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="jctrader MCP 客户端（云端无 MCP 工具时使用）")
    parser.add_argument("--base", default=os.environ.get("JCTRADER_MCP_URL", DEFAULT_BASE))
    parser.add_argument("--token", default=os.environ.get("JCTRADER_TOKEN", DEFAULT_TOKEN))
    sub = parser.add_subparsers(dest="cmd", required=True)
    sub.add_parser("list", help="列出全部工具")
    call_p = sub.add_parser("call", help="调用单个工具")
    call_p.add_argument("name")
    call_p.add_argument("arguments", nargs="?", default="{}")
    sub.add_parser("board", help="拉取盘面核心信号包")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = _parse_args(argv or sys.argv[1:])
    try:
        client = JctraderClient(args.base, args.token)
        if args.cmd == "list":
            tools = [{"name": t["name"], "description": t.get("description", "")} for t in client.list_tools()]
            json.dump(tools, sys.stdout, ensure_ascii=False, indent=2)
        elif args.cmd == "call":
            payload = json.loads(args.arguments)
            if not isinstance(payload, dict):
                raise ValueError("arguments 必须是 JSON 对象")
            json.dump(client.call(args.name, payload), sys.stdout, ensure_ascii=False, indent=2)
        else:
            json.dump(client.board(), sys.stdout, ensure_ascii=False, indent=2)
        sys.stdout.write("\n")
        return 0
    except Exception as exc:  # noqa: BLE001
        print(f"jctrader_client 失败: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
