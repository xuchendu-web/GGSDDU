# Multi-Market Real-Time Monitor (Prototype)

Mock-first single-page dashboard for **A-share / HK / US** indices and a few ETF stubs. Emits fake ticks over **WebSocket** or **SSE** — no broker credentials, no live trading.

## Hypothesis

A static UI + local mock feed is enough as a **reusable scaffold** before wiring real market data.

## Contents

| Path | Role |
|------|------|
| `frontend/` | HTML/CSS/JS: indices, FX, rates, commodities, crypto stub, breadth, volume heat, clock strip, alerts |
| `mock_server.py` | FastAPI app: static assets, `/ws/ticks`, `/sse/ticks` |
| `DESIGN.md` | Visual language (premium finance, site burn aligned) |

## Requirements

- Python 3.10+
- pip packages in `requirements.txt`

## Run locally

From repository root:

```bash
cd research/multi-market-monitor
python3 -m venv .venv
source .venv/bin/activate   # Windows: .venv\Scripts\activate
pip install -r requirements.txt
python mock_server.py
```

Open **http://127.0.0.1:8765/** in a browser.

### Endpoints

| URL | Description |
|-----|-------------|
| `/` | Dashboard |
| `/ws/ticks` | WebSocket JSON ticks (~1.2s interval) |
| `/sse/ticks` | Server-Sent Events stream |
| `/health` | `{ "status": "ok", "mode": "mock" }` |

Use the header control to switch between WebSocket and SSE.

## Payload shape (tick)

```json
{
  "type": "tick",
  "ts": "2026-10-25T17:06:00Z",
  "mock": true,
  "indices": [{ "id", "market", "name", "symbol", "price", "change_pct", ... }],
  "fx": [{ "id", "name", "price", "change_pct" }],
  "rates": [{ "id", "name", "region", "yield_pct", "change_bp" }],
  "commodities": [{ "id", "name", "symbol", "unit", "price", "change_pct" }],
  "crypto": [{ "id", "symbol", "price", "change_pct", "stub": true }],
  "breadth": { "A": { "adv", "dec", "unch", "adv_ratio", "advance_ratio", "sparkline", "limit_up", "limit_down" }, ... },
  "volume_heat": [{ "name", "market", "change_pct", "vol_ratio", "intensity" }],
  "sessions": [{ "id", "label", "tz", "phase" }],
  "movers": [ "... top 10 by |change_pct| ..." ],
  "alert": { "id", "ts", "market", "severity", "message" } | null
}
```

## Next steps (out of scope here)

- Replace `mock_server._build_payload` with adapter to cjpy / zsmcp / vendor WS
- Persist alerts; auth gateway for internal deploy
- Sparklines from ring buffer of ticks

## Skip list

Real API keys, order routing, production deployment.
