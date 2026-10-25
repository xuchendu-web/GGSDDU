#!/usr/bin/env python3
"""Mock tick server: static frontend + WebSocket + SSE. No credentials required."""

from __future__ import annotations

import asyncio
import json
import random
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.responses import FileResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles

ROOT = Path(__file__).resolve().parent
FRONTEND = ROOT / "frontend"

# Seed instruments: indices + ETF stubs
INSTRUMENTS: list[dict[str, Any]] = [
    {"id": "sh000001", "market": "A", "kind": "index", "name": "上证指数", "symbol": "SH000001", "price": 3288.5},
    {"id": "sz399001", "market": "A", "kind": "index", "name": "深证成指", "symbol": "SZ399001", "price": 10542.0},
    {"id": "sz399006", "market": "A", "kind": "index", "name": "创业板指", "symbol": "SZ399006", "price": 2145.3},
    {"id": "sh510300", "market": "A", "kind": "etf", "name": "沪深300ETF", "symbol": "SH510300", "price": 4.012},
    {"id": "sz159915", "market": "A", "kind": "etf", "name": "创业板ETF", "symbol": "SZ159915", "price": 2.156},
    {"id": "hkhsi", "market": "HK", "kind": "index", "name": "恒生指数", "symbol": "HSI", "price": 19876.0},
    {"id": "hkhscei", "market": "HK", "kind": "index", "name": "恒生国企", "symbol": "HSCEI", "price": 7012.5},
    {"id": "hk02800", "market": "HK", "kind": "etf", "name": "盈富基金", "symbol": "02800.HK", "price": 24.85},
    {"id": "usspx", "market": "US", "kind": "index", "name": "标普500", "symbol": "SPX", "price": 5842.1},
    {"id": "usndx", "market": "US", "kind": "index", "name": "纳斯达克", "symbol": "NDX", "price": 20511.0},
    {"id": "usqqq", "market": "US", "kind": "etf", "name": "纳指100 ETF", "symbol": "QQQ", "price": 492.35},
]

state: dict[str, dict[str, Any]] = {}
for inst in INSTRUMENTS:
    p = inst["price"]
    state[inst["id"]] = {
        **inst,
        "prev_close": p * random.uniform(0.985, 1.015),
        "price": p,
        "volume": random.randint(1_000_000, 50_000_000),
    }

ALERT_TEMPLATES = [
    "{name} 1分钟波动超过 {pct:.2f}%",
    "{name} 触及日内模拟阈值",
    "跨市场：{market} 板块同步走强（mock）",
    "ETF 折溢价 stub：{name} 偏离 IOPV +{bps}bp（示意）",
]

app = FastAPI(title="Multi-Market Monitor Mock", version="0.1.0")
app.mount("/assets", StaticFiles(directory=FRONTEND), name="assets")


def _utc_iso() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _pct_change(cur: float, prev: float) -> float:
    if prev == 0:
        return 0.0
    return (cur - prev) / prev * 100


def _step_price(price: float, market: str, kind: str) -> float:
    vol = {"A": 0.0008, "HK": 0.0012, "US": 0.0010}[market]
    shock = random.gauss(0, vol)
    new_p = price * (1 + shock)
    if kind == "etf" or new_p < 50:
        return round(new_p, 3)
    return round(new_p, 2)


def _build_payload() -> dict[str, Any]:
    indices: list[dict[str, Any]] = []
    movers_candidates: list[dict[str, Any]] = []

    for iid, row in state.items():
        prev = row["price"]
        new_p = _step_price(prev, row["market"], row["kind"])
        row["price"] = new_p
        row["volume"] = int(row["volume"] * random.uniform(0.998, 1.004))
        chg_pct = _pct_change(new_p, row["prev_close"])
        chg_abs = new_p - row["prev_close"]
        tick = {
            "id": iid,
            "market": row["market"],
            "kind": row["kind"],
            "name": row["name"],
            "symbol": row["symbol"],
            "price": new_p,
            "change": round(chg_abs, 4 if new_p < 50 else 2),
            "change_pct": round(chg_pct, 2),
            "volume": row["volume"],
        }
        if row["kind"] == "index":
            indices.append(tick)
        movers_candidates.append(tick)

    movers_candidates.sort(key=lambda x: abs(x["change_pct"]), reverse=True)
    movers = movers_candidates[:8]

    alert = None
    if random.random() < 0.22:
        pick = random.choice(movers[:4])
        tpl = random.choice(ALERT_TEMPLATES)
        alert = {
            "id": f"alt-{int(time.time() * 1000)}",
            "ts": _utc_iso(),
            "market": pick["market"],
            "severity": random.choice(["info", "watch", "watch"]),
            "message": tpl.format(
                name=pick["name"],
                pct=abs(pick["change_pct"]),
                market=pick["market"],
                bps=random.randint(5, 45),
            ),
        }

    return {
        "type": "tick",
        "ts": _utc_iso(),
        "mock": True,
        "indices": indices,
        "movers": movers,
        "alert": alert,
    }


ws_clients: set[WebSocket] = set()
sse_queues: set[asyncio.Queue] = set()
_broadcast_task: asyncio.Task | None = None


@app.on_event("startup")
async def startup() -> None:
    global _broadcast_task

    async def run_loop() -> None:
        while True:
            payload = _build_payload()
            for ws in list(ws_clients):
                try:
                    await ws.send_json(payload)
                except Exception:
                    ws_clients.discard(ws)
            for q in list(sse_queues):
                try:
                    q.put_nowait(payload)
                except asyncio.QueueFull:
                    pass
            await asyncio.sleep(1.2)

    _broadcast_task = asyncio.create_task(run_loop())


@app.get("/")
async def index() -> FileResponse:
    return FileResponse(FRONTEND / "index.html")


@app.get("/health")
async def health() -> dict[str, str]:
    return {"status": "ok", "mode": "mock"}


@app.websocket("/ws/ticks")
async def ws_ticks(websocket: WebSocket) -> None:
    await websocket.accept()
    ws_clients.add(websocket)
    try:
        await websocket.send_json(
            {
                "type": "hello",
                "ts": _utc_iso(),
                "mock": True,
                "message": "Connected to mock tick stream",
            }
        )
        while True:
            # keepalive: client may send ping text
            msg = await websocket.receive_text()
            if msg.strip().lower() == "ping":
                await websocket.send_json({"type": "pong", "ts": _utc_iso()})
    except WebSocketDisconnect:
        pass
    finally:
        ws_clients.discard(websocket)


async def _sse_generator():
    q: asyncio.Queue = asyncio.Queue(maxsize=32)
    sse_queues.add(q)
    try:
        yield f"data: {json.dumps({'type': 'hello', 'ts': _utc_iso(), 'mock': True})}\n\n"
        while True:
            payload = await q.get()
            yield f"data: {json.dumps(payload, ensure_ascii=False)}\n\n"
    finally:
        sse_queues.discard(q)


@app.get("/sse/ticks")
async def sse_ticks() -> StreamingResponse:
    return StreamingResponse(
        _sse_generator(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


def main() -> None:
    import uvicorn

    uvicorn.run(
        "mock_server:app",
        host="127.0.0.1",
        port=8765,
        reload=False,
        log_level="info",
    )


if __name__ == "__main__":
    main()
