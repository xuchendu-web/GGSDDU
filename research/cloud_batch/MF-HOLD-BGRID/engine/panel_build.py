#!/usr/bin/env python3
"""Build daily P + weekly W from CLOUD-BATCH research_cache (sina + day + week + Tencent)."""
from __future__ import annotations

import json
import ssl
import time
import urllib.error
import urllib.request
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

import numpy as np
import pandas as pd

KIT = Path(__file__).resolve().parents[2] / "CLOUD-BATCH-2026-10-26"
if not KIT.exists():
    KIT = Path("/workspace/uploads_extract/CLOUD-BATCH-2026-10-26")
CACHE = KIT / "data" / "research_cache"
WEEK_DIR = CACHE / "week"
SINA_DIR = CACHE / "sina_daily"
DAY_DIR = CACHE / "day"
RESEARCH_PX = Path(__file__).resolve().parents[2] / "prices_daily"
PANEL_PKL = Path(__file__).resolve().parents[2] / "panel" / "mf_panel_v1.pkl"

START_S = "2016-01-01"
END_S = "2026-10-16"
UA = {"User-Agent": "Mozilla/5.0 (compatible; MF-HOLD-BGRID/1.0)"}
CTX = ssl.create_default_context()
EXTRA_CODES = ("511880", "511010", "511260")


def _mkt(code: str) -> str:
    return "sh" if code.startswith(("5", "6", "9")) and not code.startswith("159") else "sz"


def http_get(url: str, timeout: int = 25) -> bytes:
    req = urllib.request.Request(url, headers=UA)
    with urllib.request.urlopen(req, timeout=timeout, context=CTX) as resp:
        return resp.read()


def fetch_tencent_daily(code: str) -> pd.Series:
    m = _mkt(code)
    url = (
        "https://web.ifzq.gtimg.cn/appstock/app/fqkline/get"
        f"?param={m}{code},day,{START_S},{END_S},2000,qfq"
    )
    for attempt in range(4):
        try:
            payload = json.loads(http_get(url))
            data = payload.get("data") or {}
            key = f"{m}{code}"
            node = data.get(key) or (next(iter(data.values())) if data else None)
            if not isinstance(node, dict):
                raise ValueError("empty")
            rows = node.get("qfqday") or node.get("day") or []
            if not rows:
                raise ValueError("no rows")
            idx = pd.to_datetime([str(r[0])[:10] for r in rows])
            px = pd.Series([float(r[2]) for r in rows], index=idx, dtype=float)
            px = px[~px.index.duplicated(keep="last")].sort_index()
            out = RESEARCH_PX / f"{code}.json"
            out.parent.mkdir(parents=True, exist_ok=True)
            out.write_text(
                json.dumps(
                    {"code": code, "source": "tencent_qfq_day", "bars": [
                        {"date": d.strftime("%Y-%m-%d"), "c": float(px[d])} for d in px.index
                    ]},
                    ensure_ascii=False,
                ),
                encoding="utf-8",
            )
            return px
        except Exception:
            time.sleep(0.5 + attempt)
    return pd.Series(dtype=float)


def load_daily(code: str) -> pd.Series:
    parts: list[pd.Series] = []
    sp = SINA_DIR / f"{code}.csv"
    if sp.exists():
        df = pd.read_csv(sp, parse_dates=["date"])
        s = df.set_index("date")["close"].astype(float).sort_index()
        parts.append(s)
    dp = DAY_DIR / f"{code}.json"
    if dp.exists():
        j = json.loads(dp.read_text(encoding="utf-8"))
        bars = j.get("bars") or []
        if bars:
            idx = pd.to_datetime([b["date"] for b in bars])
            px = pd.Series([float(b["c"]) for b in bars], index=idx, dtype=float)
            px = px[~px.index.duplicated(keep="last")].sort_index()
            parts.append(px)
    rp = RESEARCH_PX / f"{code}.json"
    if rp.exists():
        j = json.loads(rp.read_text(encoding="utf-8"))
        bars = j.get("bars") or []
        if bars:
            idx = pd.to_datetime([b["date"] for b in bars])
            px = pd.Series([float(b["c"]) for b in bars], index=idx, dtype=float)
            px = px[~px.index.duplicated(keep="last")].sort_index()
            parts.append(px)
    if not parts:
        px = fetch_tencent_daily(code)
        if not px.empty:
            parts.append(px)
    if not parts:
        return pd.Series(dtype=float)
    s = parts[0]
    for p in parts[1:]:
        s = p.combine_first(s)
    return s.sort_index()


def load_weekly_grid(code: str = "510300") -> pd.DatetimeIndex:
    wp = WEEK_DIR / f"{code}.json"
    j = json.loads(wp.read_text(encoding="utf-8"))
    dates = pd.to_datetime([b["date"] for b in j["bars"]])
    return pd.DatetimeIndex(sorted(dates.unique()))


def build_panel(force: bool = False) -> dict:
    PANEL_PKL.parent.mkdir(parents=True, exist_ok=True)
    if PANEL_PKL.exists() and not force:
        return pd.read_pickle(PANEL_PKL)

    week_codes = sorted(p.stem for p in WEEK_DIR.glob("*.json"))
    uni_path = Path("/workspace/etf-correlation/data/research_pool_v2.csv")
    if uni_path.exists():
        import pandas as pd

        pool_codes = set(pd.read_csv(uni_path, dtype={"code": str}).code.str.zfill(6))
        week_codes = sorted(set(week_codes) & pool_codes)
    codes = sorted(set(week_codes) | set(EXTRA_CODES))
    daily: dict[str, pd.Series] = {}
    missing = []
    with ThreadPoolExecutor(max_workers=12) as ex:
        futs = {ex.submit(load_daily, c): c for c in codes}
        for fut in as_completed(futs):
            c = futs[fut]
            s = fut.result()
            if len(s) >= 60:
                daily[c] = s
            else:
                missing.append(c)

    G = load_weekly_grid("510300")
    G = G[(G >= pd.Timestamp(START_S)) & (G <= pd.Timestamp(END_S))]

    # Weekly W from week json closes aligned to G
    W_cols = {}
    for c in week_codes:
        wp = WEEK_DIR / f"{c}.json"
        if not wp.exists():
            continue
        j = json.loads(wp.read_text(encoding="utf-8"))
        bars = j.get("bars") or []
        if not bars:
            continue
        idx = pd.to_datetime([b["date"] for b in bars])
        px = pd.Series([float(b["c"]) for b in bars], index=idx, dtype=float)
        px = px[~px.index.duplicated(keep="last")]
        W_cols[c] = px.reindex(G)

    W = pd.DataFrame(W_cols).sort_index()
    # Daily P: union index
    P = pd.DataFrame({c: daily[c] for c in daily}).sort_index()
    P = P[(P.index >= pd.Timestamp(START_S)) & (P.index <= pd.Timestamp(END_S))]
    # extend W with daily-only codes (e.g. 511880)
    for c in daily:
        if c not in W.columns:
            W[c] = P[c].reindex(G)

    SIG = pd.DataFrame(index=G)  # unused for HOLD grid
    pack = dict(P=P, W=W, SIG=SIG, G=list(G), codes=sorted(P.columns), missing=missing)
    pd.to_pickle(pack, PANEL_PKL)
    return pack


if __name__ == "__main__":
    p = build_panel(force=True)
    print("panel", PANEL_PKL, "P", p["P"].shape, "W", p["W"].shape, "missing", p.get("missing"))
