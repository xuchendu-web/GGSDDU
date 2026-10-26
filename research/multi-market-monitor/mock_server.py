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
    {"id": "sh000688", "market": "A", "kind": "index", "name": "科创50", "symbol": "SH000688", "price": 982.4},
    {"id": "sh510300", "market": "A", "kind": "etf", "name": "沪深300ETF", "symbol": "SH510300", "price": 4.012},
    {"id": "sz159915", "market": "A", "kind": "etf", "name": "创业板ETF", "symbol": "SZ159915", "price": 2.156},
    {"id": "hkhsi", "market": "HK", "kind": "index", "name": "恒生指数", "symbol": "HSI", "price": 19876.0},
    {"id": "hkhscei", "market": "HK", "kind": "index", "name": "恒生国企", "symbol": "HSCEI", "price": 7012.5},
    {"id": "hk02800", "market": "HK", "kind": "etf", "name": "盈富基金", "symbol": "02800.HK", "price": 24.85},
    {"id": "usspx", "market": "US", "kind": "index", "name": "标普500", "symbol": "SPX", "price": 5842.1},
    {"id": "usndx", "market": "US", "kind": "index", "name": "纳斯达克", "symbol": "NDX", "price": 20511.0},
    {"id": "usdjia", "market": "US", "kind": "index", "name": "道琼斯", "symbol": "DJI", "price": 42880.0},
    {"id": "usqqq", "market": "US", "kind": "etf", "name": "纳指100 ETF", "symbol": "QQQ", "price": 492.35},
]

FX_PAIRS: list[dict[str, Any]] = [
    {"id": "usdcny", "name": "USD/CNY", "price": 7.2456, "decimals": 4},
    {"id": "usdhkd", "name": "USD/HKD", "price": 7.7821, "decimals": 4},
    {"id": "eurusd", "name": "EUR/USD", "price": 1.0842, "decimals": 4},
    {"id": "usdjpy", "name": "USD/JPY", "price": 149.82, "decimals": 2},
    {"id": "gbpusd", "name": "GBP/USD", "price": 1.2634, "decimals": 4},
    {"id": "audusd", "name": "AUD/USD", "price": 0.6512, "decimals": 4},
    {"id": "usdcnh", "name": "USD/CNH", "price": 7.2891, "decimals": 4},
    {"id": "dxy", "name": "DXY (stub)", "price": 103.45, "decimals": 2},
]

RATES: list[dict[str, Any]] = [
    {"id": "cn10y", "name": "中国10Y", "region": "CN", "yield_bp": 218.5},
    {"id": "us10y", "name": "美国10Y", "region": "US", "yield_bp": 428.2},
    {"id": "us02y", "name": "美国2Y", "region": "US", "yield_bp": 412.8},
    {"id": "us30y", "name": "美国30Y", "region": "US", "yield_bp": 451.0},
    {"id": "de10y", "name": "德国10Y", "region": "EU", "yield_bp": 235.4},
    {"id": "jp10y", "name": "日本10Y", "region": "JP", "yield_bp": 92.1},
    {"id": "uk10y", "name": "英国10Y", "region": "UK", "yield_bp": 412.6},
]

COMMODITIES: list[dict[str, Any]] = [
    {"id": "xau", "name": "黄金", "symbol": "XAU", "unit": "USD/oz", "price": 2654.3},
    {"id": "xag", "name": "白银", "symbol": "XAG", "unit": "USD/oz", "price": 31.42},
    {"id": "wti", "name": "WTI原油", "symbol": "CL", "unit": "USD/bbl", "price": 71.85},
    {"id": "brent", "name": "布伦特", "symbol": "BZ", "unit": "USD/bbl", "price": 75.12},
    {"id": "copper", "name": "铜", "symbol": "HG", "unit": "USD/lb", "price": 4.128},
    {"id": "natgas", "name": "天然气", "symbol": "NG", "unit": "USD/MMBtu", "price": 2.84},
]

CRYPTO_STUB: list[dict[str, Any]] = [
    {"id": "btc", "name": "Bitcoin", "symbol": "BTC", "price": 67842.0, "note": "stub"},
    {"id": "eth", "name": "Ethereum", "symbol": "ETH", "price": 3421.5, "note": "stub"},
    {"id": "sol", "name": "Solana", "symbol": "SOL", "price": 168.42, "note": "stub"},
]

SECTOR_HEAT: list[dict[str, Any]] = [
    {"id": "tech", "name": "科技", "market": "A"},
    {"id": "finance", "name": "金融", "market": "A"},
    {"id": "consumer", "name": "消费", "market": "A"},
    {"id": "health", "name": "医药", "market": "A"},
    {"id": "energy", "name": "能源", "market": "A"},
    {"id": "semi", "name": "半导体", "market": "US"},
    {"id": "mega", "name": "Mag7", "market": "US"},
    {"id": "hkprop", "name": "港股地产", "market": "HK"},
]

MARKET_SESSIONS: list[dict[str, Any]] = [
    {"id": "shanghai", "label": "上海", "market": "A", "tz": "Asia/Shanghai"},
    {"id": "hongkong", "label": "香港", "market": "HK", "tz": "Asia/Hong_Kong"},
    {"id": "london", "label": "伦敦", "market": "EU", "tz": "Europe/London"},
    {"id": "newyork", "label": "纽约", "market": "US", "tz": "America/New_York"},
    {"id": "chicago", "label": "芝加哥", "market": "US", "tz": "America/Chicago"},
    {"id": "tokyo", "label": "东京", "market": "JP", "tz": "Asia/Tokyo"},
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

fx_state: dict[str, dict[str, Any]] = {}
for row in FX_PAIRS:
    fx_state[row["id"]] = {**row, "prev": row["price"], "price": row["price"]}

rate_state: dict[str, dict[str, Any]] = {}
for row in RATES:
    rate_state[row["id"]] = {**row, "prev_bp": row["yield_bp"], "yield_bp": row["yield_bp"]}

comm_state: dict[str, dict[str, Any]] = {}
for row in COMMODITIES:
    comm_state[row["id"]] = {**row, "prev": row["price"], "price": row["price"]}

crypto_state: dict[str, dict[str, Any]] = {}
for row in CRYPTO_STUB:
    crypto_state[row["id"]] = {**row, "prev": row["price"], "price": row["price"]}

breadth_state: dict[str, dict[str, int]] = {
    "A": {"adv": 2145, "dec": 1823, "unch": 312, "limit_up": 42, "limit_down": 18},
    "HK": {"adv": 412, "dec": 389, "unch": 88, "limit_up": 0, "limit_down": 0},
    "US": {"adv": 2841, "dec": 1922, "unch": 412, "limit_up": 0, "limit_down": 0},
}

BREADTH_HISTORY_LEN = 48
breadth_history: list[float] = [
    random.uniform(0.42, 0.58) for _ in range(BREADTH_HISTORY_LEN)
]

heat_state: dict[str, dict[str, float]] = {}
for s in SECTOR_HEAT:
    heat_state[s["id"]] = {
        **s,
        "change_pct": random.uniform(-2.5, 2.5),
        "vol_ratio": random.uniform(0.6, 1.8),
    }

ALERT_TEMPLATES = [
    "{name} 1分钟波动超过 {pct:.2f}%",
    "{name} 触及日内模拟阈值",
    "跨市场：{market} 板块同步走强（mock）",
    "ETF 折溢价 stub：{name} 偏离 IOPV +{bps}bp（示意）",
    "FX：{name} 突破 mock 区间",
    "利率：{name} 日内变动 {bps:+.1f}bp（示意）",
    "广度：{market} 上涨家数占比升至 {ratio:.0f}%（mock）",
    "量能：{name} 板块量比 {vr:.1f}x（示意）",
    "Crypto stub：{name} 24h mock 波动放大",
]

app = FastAPI(title="Multi-Market Monitor Mock", version="0.2.0")
app.mount("/assets", StaticFiles(directory=FRONTEND), name="assets")


def _utc_iso() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _pct_change(cur: float, prev: float) -> float:
    if prev == 0:
        return 0.0
    return (cur - prev) / prev * 100


def _step_price(price: float, market: str, kind: str) -> float:
    vol = {"A": 0.0008, "HK": 0.0012, "US": 0.0010}.get(market, 0.001)
    shock = random.gauss(0, vol)
    new_p = price * (1 + shock)
    if kind == "etf" or new_p < 50:
        return round(new_p, 3)
    return round(new_p, 2)


def _step_fx(price: float, decimals: int) -> float:
    shock = random.gauss(0, 0.00015)
    return round(price * (1 + shock), decimals)


def _step_rate(bp: float) -> float:
    return round(bp + random.gauss(0, 0.35), 1)


def _step_commodity(price: float) -> float:
    return round(price * (1 + random.gauss(0, 0.0015)), 2)


def _step_crypto(price: float) -> float:
    return round(price * (1 + random.gauss(0, 0.0025)), 2 if price < 1000 else 1)


def _jitter_breadth(mkt: str) -> dict[str, Any]:
    global breadth_history
    b = breadth_state[mkt]
    adv = max(0, b["adv"] + random.randint(-35, 35))
    dec = max(0, b["dec"] + random.randint(-35, 35))
    unch = max(0, b["unch"] + random.randint(-12, 12))
    out: dict[str, Any] = {**b, "adv": adv, "dec": dec, "unch": unch}
    if mkt == "A":
        out["limit_up"] = max(0, b["limit_up"] + random.randint(-3, 3))
        out["limit_down"] = max(0, b["limit_down"] + random.randint(-2, 2))
        ratio = adv / max(adv + dec, 1)
        breadth_history.append(ratio)
        if len(breadth_history) > BREADTH_HISTORY_LEN:
            breadth_history = breadth_history[-BREADTH_HISTORY_LEN:]
        out["advance_ratio"] = round(ratio, 4)
        out["sparkline"] = [round(x, 4) for x in breadth_history]
    breadth_state[mkt] = out
    total = adv + dec + unch or 1
    out["adv_ratio"] = round(adv / total * 100, 1)
    return out


def _tick_fx() -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for iid, row in fx_state.items():
        prev = row["price"]
        new_p = _step_fx(prev, row["decimals"])
        row["price"] = new_p
        chg_pct = _pct_change(new_p, row["prev"])
        rows.append(
            {
                "id": iid,
                "name": row["name"],
                "price": new_p,
                "change_pct": round(chg_pct, 3),
            }
        )
    return rows


def _tick_rates() -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for iid, row in rate_state.items():
        prev = row["yield_bp"]
        new_bp = _step_rate(prev)
        row["yield_bp"] = new_bp
        rows.append(
            {
                "id": iid,
                "name": row["name"],
                "region": row["region"],
                "yield_pct": round(new_bp / 100, 3),
                "change_bp": round(new_bp - row["prev_bp"], 2),
            }
        )
    return rows


def _tick_commodities() -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for iid, row in comm_state.items():
        prev = row["price"]
        new_p = _step_commodity(prev)
        row["price"] = new_p
        rows.append(
            {
                "id": iid,
                "name": row["name"],
                "symbol": row["symbol"],
                "unit": row["unit"],
                "price": new_p,
                "change_pct": round(_pct_change(new_p, row["prev"]), 2),
            }
        )
    return rows


def _tick_crypto() -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for iid, row in crypto_state.items():
        prev = row["price"]
        new_p = _step_crypto(prev)
        row["price"] = new_p
        rows.append(
            {
                "id": iid,
                "name": row["name"],
                "symbol": row["symbol"],
                "price": new_p,
                "change_pct": round(_pct_change(new_p, row["prev"]), 2),
                "stub": True,
                "note": row.get("note", "stub"),
            }
        )
    return rows


def _tick_volume_heat() -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for sid, row in heat_state.items():
        chg = row["change_pct"] + random.gauss(0, 0.15)
        vr = max(0.3, row["vol_ratio"] + random.gauss(0, 0.05))
        row["change_pct"] = round(chg, 2)
        row["vol_ratio"] = round(vr, 2)
        intensity = min(1.0, abs(chg) / 3.0 * 0.6 + min(vr, 2.0) / 2.0 * 0.4)
        rows.append(
            {
                "id": sid,
                "name": row["name"],
                "market": row["market"],
                "change_pct": row["change_pct"],
                "vol_ratio": row["vol_ratio"],
                "intensity": round(intensity, 3),
            }
        )
    rows.sort(key=lambda x: x["intensity"], reverse=True)
    return rows


def _session_snapshot() -> list[dict[str, Any]]:
    """Mock open/closed flags (not real exchange calendars)."""
    out: list[dict[str, Any]] = []
    for s in MARKET_SESSIONS:
        phase = random.choices(
            ["open", "pre", "closed", "after"],
            weights=[45, 10, 35, 10],
            k=1,
        )[0]
        out.append({**s, "phase": phase})
    return out


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
    movers = movers_candidates[:10]

    breadth = {mkt: _jitter_breadth(mkt) for mkt in ("A", "HK", "US")}

    alert = None
    if random.random() < 0.28:
        pick = random.choice(movers[:5])
        tpl = random.choice(ALERT_TEMPLATES)
        b_a = breadth["A"]
        heat_pick = random.choice(list(heat_state.values()))
        alert = {
            "id": f"alt-{int(time.time() * 1000)}",
            "ts": _utc_iso(),
            "market": pick.get("market", "SYS"),
            "severity": random.choice(["info", "watch", "watch", "critical"]),
            "message": tpl.format(
                name=pick.get("name", heat_pick["name"]),
                pct=abs(pick.get("change_pct", 0)),
                market=pick.get("market", "A"),
                bps=random.randint(5, 45),
                ratio=b_a.get("adv_ratio", 50),
                vr=heat_pick.get("vol_ratio", 1.0),
            ),
        }

    return {
        "type": "tick",
        "ts": _utc_iso(),
        "mock": True,
        "indices": indices,
        "fx": _tick_fx(),
        "rates": _tick_rates(),
        "commodities": _tick_commodities(),
        "crypto": _tick_crypto(),
        "breadth": breadth,
        "volume_heat": _tick_volume_heat(),
        "sessions": _session_snapshot(),
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
    return {"status": "ok", "mode": "mock", "version": "0.2.0"}


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
