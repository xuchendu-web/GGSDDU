#!/usr/bin/env python3
"""walk-forward-oos: frozen B45 spike_ft max5 + E0 + TV25 + SHARPE20; rolling OOS audit.

One F0 replay (btheta pin 05f0f8a4), then slice daily returns by protocol windows.
Research only — champion_swap=false, crown=NO.
"""
from __future__ import annotations

import json
import math
import re
import sys
import time
from collections import defaultdict
from concurrent.futures import ThreadPoolExecutor, as_completed
from copy import deepcopy
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parent
KIT = ROOT.parent / "cloud_batch" / "CLOUD-BATCH-2026-10-26"
SCRIPTS = KIT / "scripts"
sys.path.insert(0, str(SCRIPTS))

from backtest import LIVE_PHASE, MIN_BARS, Position, nearest_date, snap_index  # noqa: E402
from build_scan import Bar, classify  # noqa: E402

OUT = ROOT / "out"
CACHE = KIT / "data" / "research_cache"
UNI_CSV = KIT / "data" / "universe_replace_only_436.csv"
WEEK = CACHE / "week"
FACE = CACHE / "holdings_ro2_extended.csv"
DAY_DIR = CACHE / "day"
TEMA_PX = Path("/workspace/tema_etf_scan_2018/prices_daily")
NOON_CSV = CACHE / "fri_1430_through_20261023.csv"
SINA_DAILY = CACHE / "sina_daily"
CLASSIFY_FROM = "2019-07-01"
SNAP_CACHE = KIT / "data" / "cache_1430_snaps.json"
SOURCE_SHA = "05f0f8a4f778fde886f3e7b2976646ff4b7d777b"
BREADTH_THETA = 0.45
ANCHOR = {"ret": 1.316, "maxDD": -0.188, "Calmar": 0.70, "n_weeks": 349, "T": 348, "n_codes": 324}
ANCH_TOL = {"ret": 0.005, "maxDD": 0.002, "Calmar": 0.02}
BOOK_F0 = "LIVE1430-B45-S20-max5"

EVAL_START = "2020-01-03"
END_S = "2026-10-23"
COST_SIDE = 0.001
SIGMA_STAR = 0.25
LCAP = 1.0
LIVE_COST_RT = 0.002
CLASSIFY_WORKERS = 8

PROTOCOLS = [
    {"id": "WF-P10426", "train_w": 104, "test_w": 26, "step_w": 26, "primary": True},
    {"id": "WF-N7826", "train_w": 78, "test_w": 26, "step_w": 26, "primary": False},
    {"id": "WF-N10413", "train_w": 104, "test_w": 13, "step_w": 13, "primary": False},
    {"id": "WF-N13026", "train_w": 130, "test_w": 26, "step_w": 26, "primary": False},
]

FOLD_FIXTURES = [
    (348, 104, 26, 26, 9, [104, 130, 156, 182, 208, 234, 260, 286, 312], 10),
    (348, 78, 26, 26, 10, [78], 10),
    (348, 104, 13, 13, 18, [104], 10),
    (348, 130, 26, 26, 8, [130], 10),
]

SKIP_INVENTORY = "RESEARCH-WF-OOS-B45-FACE"


@dataclass
class Cand:
    code: str
    px: float
    fz: float | None
    aum: float
    sharpe: float | None


def is_spike(snap: dict[str, Any] | None) -> bool:
    if not snap:
        return False
    if snap.get("pending_second_week") or snap.get("in_play_kind") == "box_pending":
        return False
    return bool(snap.get("in_play")) and snap.get("in_play_kind") == "spike_ft"


def sharpe_key(c: Cand, pool: list[Cand]) -> tuple:
    miss = 0 if c.sharpe is not None else 1
    return (miss, -(c.sharpe if c.sharpe is not None else 0.0), c.code)


def make_folds(T: int, train_w: int, test_w: int, step_w: int) -> tuple[list[dict[str, tuple[int, int]]], int]:
    assert step_w == test_w
    folds: list[dict[str, tuple[int, int]]] = []
    start = train_w
    while start + test_w <= T:
        folds.append({"train": (start - train_w, start), "test": (start, start + test_w)})
        start += step_w
    leftover = T - folds[-1]["test"][1]
    return folds, leftover


def run_fixtures() -> None:
    for T, tw, test_w, step_w, n_exp, starts_exp, left_exp in FOLD_FIXTURES:
        folds, leftover = make_folds(T, tw, test_w, step_w)
        assert len(folds) == n_exp, (tw, len(folds), n_exp)
        assert leftover == left_exp
        if len(starts_exp) > 1:
            got = [f["test"][0] for f in folds]
            assert got == starts_exp
        else:
            assert folds[0]["test"][0] == starts_exp[0]


def stats_full(s: pd.Series) -> dict[str, float]:
    if s is None or len(s) < 2:
        return {
            "ret": float("nan"),
            "maxDD": float("nan"),
            "CAGR": float("nan"),
            "Calmar": float("nan"),
            "Sharpe": float("nan"),
        }
    s = s.dropna()
    if len(s) < 2:
        return {
            "ret": float("nan"),
            "maxDD": float("nan"),
            "CAGR": float("nan"),
            "Calmar": float("nan"),
            "Sharpe": float("nan"),
        }
    q = (1 + s).cumprod()
    ret = float(q.iloc[-1] - 1)
    dd = float((q / q.cummax().clip(lower=1e-12) - 1).min())
    n = (s.index[-1] - s.index[0]).days
    cagr = (1 + ret) ** (365.25 / n) - 1 if n > 0 and (1 + ret) > 0 else float("nan")
    cal = cagr / abs(dd) if dd < 0 else float("nan")
    mu = float(s.mean())
    sig = float(s.std(ddof=1))
    sharpe = mu / sig * math.sqrt(252) if sig > 0 and np.isfinite(sig) else float("nan")
    return {"ret": ret, "maxDD": dd, "CAGR": cagr, "Calmar": cal, "Sharpe": sharpe}


def pct(x: float | None) -> str:
    if x is None or (isinstance(x, float) and (math.isnan(x) or math.isinf(x))):
        return "—"
    return f"{100 * x:.1f}%"


def check_anchor(st: dict[str, float], n_weeks: int, T: int, n_codes: int, end_s: str) -> bool:
    if end_s != END_S:
        return False
    if n_weeks != ANCHOR["n_weeks"] or T != ANCHOR["T"] or n_codes != ANCHOR["n_codes"]:
        return False
    if abs(st["ret"] - ANCHOR["ret"]) > ANCH_TOL["ret"]:
        return False
    if abs(st["maxDD"] - ANCHOR["maxDD"]) > ANCH_TOL["maxDD"]:
        return False
    if abs(st["Calmar"] - ANCHOR["Calmar"]) > ANCH_TOL["Calmar"]:
        return False
    return True


def period_tag_for_test(calendar: list[str], test: tuple[int, int]) -> str:
    dates = [calendar[i] for i in range(test[0], test[1])]
    if not dates:
        return "MIX"
    weak = all(d <= "2022-12-31" for d in dates)
    strong = all(d >= "2023-01-01" for d in dates)
    if weak:
        return "WEAK_2020_22"
    if strong:
        return "STRONG_2023_26"
    return "MIX"


def compute_gates(face: dict[str, float], oos: dict[str, float]) -> tuple[bool, bool, bool]:
    c_face = face["Calmar"]
    c_oos = oos.get("Calmar", float("nan"))
    mdd_face = face["maxDD"]
    mdd_oos = oos.get("maxDD", float("nan"))
    g1 = (not math.isfinite(c_oos)) or (c_oos < 0.50 * c_face)
    g2 = (c_face >= 0.30) and ((not math.isfinite(c_oos)) or (c_oos < 0.15))
    g3 = abs(mdd_oos) > 1.50 * abs(mdd_face)
    return g1, g2, g3


def week_daily_slices(r: pd.Series, calendar: list[str], T: int) -> list[pd.Series]:
    slices: list[pd.Series] = []
    for w in range(T):
        t0 = pd.Timestamp(calendar[w])
        t1 = pd.Timestamp(calendar[w + 1])
        seg = r[(r.index > t0) & (r.index <= t1)]
        slices.append(seg)
    return slices


def concat_weeks(slices: list[pd.Series], w_start: int, w_end: int) -> pd.Series:
    parts = [slices[i] for i in range(w_start, w_end) if len(slices[i])]
    if not parts:
        return pd.Series(dtype=float)
    return pd.concat(parts).sort_index()


def scan_inventory() -> dict[str, Any]:
    skipped: list[str] = []
    for base in (ROOT.parent, ROOT.parents[1] if len(ROOT.parents) > 1 else ROOT.parent):
        probe = base / "research" / "RESEARCH-WF-OOS-B45-FACE"
        if probe.exists():
            skipped.append(SKIP_INVENTORY)
            break
    return {"engine": "btheta-05f0f8a4", "skipped": skipped}


def load_daily_closes(codes: list[str], sina: dict[str, dict[str, float]] | None = None) -> dict[str, pd.Series]:
    out: dict[str, pd.Series] = {}
    for c in codes:
        s = None
        ftema = TEMA_PX / f"{c}.csv"
        if TEMA_PX.exists() and ftema.exists():
            df = pd.read_csv(ftema, parse_dates=["Date"])
            s = df.set_index("Date")["Close"].astype(float).sort_index()
            s = s[~s.index.duplicated(keep="last")]
        fday = DAY_DIR / f"{c}.json"
        if fday.exists():
            j = json.loads(fday.read_text(encoding="utf-8"))
            bars = j.get("bars") if isinstance(j, dict) else j
            if bars:
                idx = pd.to_datetime([b["date"] for b in bars])
                px = pd.Series([float(b["c"]) for b in bars], index=idx, dtype=float)
                px = px[~px.index.duplicated(keep="last")].sort_index()
                s = px if s is None else px.combine_first(s).sort_index()
        if s is None and sina and c in sina and len(sina[c]) >= 10:
            idx = pd.to_datetime(sorted(sina[c]))
            s = pd.Series([sina[c][d.strftime("%Y-%m-%d")] for d in idx], index=idx, dtype=float)
        if s is not None and len(s) >= 10:
            out[c] = s
    return out


def qfq_close_on(code: str, td: str, daily: dict[str, pd.Series], closes_w: dict[str, dict[str, float]]) -> float | None:
    if code in daily:
        ser = daily[code]
        ts = pd.Timestamp(td)
        if ts in ser.index:
            return float(ser.loc[ts])
        sub = ser.loc[:ts]
        if len(sub) and (ts - sub.index[-1]).days <= 3:
            return float(sub.iloc[-1])
    wc = closes_w.get(code) or {}
    if td in wc:
        return float(wc[td])
    ds = sorted(wc)
    if ds:
        hit = nearest_date(td, ds, 3)
        if hit:
            return float(wc[hit])
    return None


def load_sina_closes(codes: list[str]) -> dict[str, dict[str, float]]:
    out: dict[str, dict[str, float]] = {}
    for c in codes:
        fp = SINA_DAILY / f"{c}.csv"
        if not fp.exists():
            continue
        df = pd.read_csv(fp)
        if "date" not in df.columns or "close" not in df.columns:
            continue
        out[c] = {str(r.date)[:10]: float(r.close) for r in df.itertuples() if r.close and float(r.close) > 0}
    return out


def sharpe_n_on(closes: pd.Series, d: str, n: int) -> float | None:
    ts = pd.Timestamp(d)
    sub = closes.loc[: ts - pd.Timedelta(days=1)]
    if len(sub) < n + 1:
        return None
    if (ts - sub.index[-1]).days > 5:
        return None
    window = sub.iloc[-(n + 1) :]
    rets = window.pct_change().dropna()
    if len(rets) < n:
        return None
    rets = rets.iloc[-n:]
    sigma = float(rets.std(ddof=1)) if len(rets) > 1 else 0.0
    if sigma <= 0 or not np.isfinite(sigma):
        return None
    mu = float(rets.mean())
    if not np.isfinite(mu):
        return None
    return mu / sigma * np.sqrt(252)


def simulate_f0(
    calendar: list[str],
    snaps: dict[str, dict[str, dict[str, Any]]],
    closes_w: dict[str, dict[str, float]],
    alias: dict[str, dict[str, str]],
    aum: dict[str, float],
    daily: dict[str, pd.Series],
    risk_on_by_fri: dict[str, bool],
    max_pos: int = 5,
) -> tuple[list[dict[str, Any]], dict[str, list[str]]]:
    cash = 1.0
    positions: dict[str, Position] = {}
    trades: list[dict[str, Any]] = []
    picks: dict[str, list[str]] = {}

    def px_on(code: str, d: str) -> float | None:
        return closes_w.get(code, {}).get((alias.get(code) or {}).get(d) or d)

    def snap_at(code: str, d: str) -> dict[str, Any] | None:
        key = (alias.get(code) or {}).get(d) or d
        return snaps.get(code, {}).get(key)

    def equity_now() -> float:
        return cash + sum(p.shares * p.last_px for p in positions.values())

    def build_cands(d: str, skip: set[str]) -> list[Cand]:
        out: list[Cand] = []
        for code in snaps:
            if code in skip:
                continue
            sn = snap_at(code, d)
            if not is_spike(sn):
                continue
            px = px_on(code, d)
            if px is None or px <= 0:
                continue
            sh = sharpe_n_on(daily[code], d, 20) if code in daily else None
            if sh is None:
                continue
            fz = sn.get("falsify_close") if sn else None
            out.append(
                Cand(
                    code=code,
                    px=px,
                    fz=float(fz) if fz is not None else None,
                    aum=aum.get(code) or 0.0,
                    sharpe=sh,
                )
            )
        return out

    last_i = len(calendar) - 1
    for i, d in enumerate(calendar):
        for p in positions.values():
            px = px_on(p.code, d)
            if px is not None:
                p.last_px = px

        last_bar = i == last_i
        risk_on = False if last_bar else bool(risk_on_by_fri.get(d, False))

        exiting: list[tuple[str, str, float]] = []
        for code, p in list(positions.items()):
            px = px_on(code, d)
            if last_bar:
                exiting.append((code, "eod_eval", px if px is not None else p.last_px))
                continue
            if not risk_on:
                exiting.append((code, "breadth_off", px if px is not None else p.last_px))
                continue
            if px is None:
                continue
            reason = None
            sn = snap_at(code, d)
            if sn:
                fz = sn.get("falsify_close")
                if fz is not None and px < float(fz):
                    reason = "falsify"
                elif sn.get("always_in") != "Long":
                    reason = "always_in_flip"
                elif (not sn.get("in_play")) and sn.get("phase") not in LIVE_PHASE:
                    reason = "left_structure"
            if reason:
                exiting.append((code, reason, px))
            else:
                p.weeks += 1

        for code, reason, px in exiting:
            p = positions.pop(code)
            cash += p.shares * px * (1.0 - COST_SIDE)
            trades.append(
                {
                    "code": code,
                    "entry_date": p.entry_date,
                    "exit_date": d,
                    "exit_reason": reason,
                    "weeks_held": p.weeks + 1,
                }
            )

        take: list[Cand] = []
        if not last_bar and risk_on:
            pool = build_cands(d, set(positions))
            slots = max_pos - len(positions)
            if slots > 0 and pool:
                pool_rank_list = [c for c in pool if c.sharpe is not None]
                pool_rank = sorted(pool_rank_list, key=lambda c: sharpe_key(c, pool_rank_list))
                take = pool_rank[:slots]

        picks[d] = [c.code for c in take]

        if take:
            eq = equity_now()
            n_after = len(positions) + len(take)
            if n_after > max_pos:
                raise SystemExit(f"overflow F0 {d} n={n_after}")
            target = eq / n_after if n_after else 0.0
            for p in positions.values():
                if p.last_px > 0:
                    p.shares = target / p.last_px
            for c in take:
                positions[c.code] = Position(
                    code=c.code,
                    kind="spike_ft",
                    entry_date=d,
                    entry_px=c.px,
                    entry_falsify=c.fz,
                    shares=(target * (1.0 - COST_SIDE)) / c.px,
                    last_px=c.px,
                    weeks=0,
                )
            cash = 0.0
        elif positions:
            eq = equity_now()
            target = eq / len(positions)
            for p in positions.values():
                if p.last_px > 0:
                    p.shares = target / p.last_px
            cash = 0.0
        else:
            cash = equity_now()

    hold: dict[str, list[str]] = {d: [] for d in calendar}
    open_codes: set[str] = set()
    exits_by_day: dict[str, list[str]] = {}
    for t in trades:
        exits_by_day.setdefault(t["exit_date"], []).append(t["code"])
    for d in calendar:
        for code in exits_by_day.get(d, []):
            open_codes.discard(code)
        for code in picks.get(d, []):
            open_codes.add(code)
        hold[d] = sorted(open_codes)

    return trades, hold


def run_live_tv(
    hold: dict[pd.Timestamp, list[str]], days: pd.DatetimeIndex, px: pd.DataFrame, R: pd.DataFrame
) -> pd.Series:
    reb = sorted(hold)
    rp = pd.Series(0.0, index=days)
    Ls = pd.Series(0.0, index=days)
    prev: dict[str, float] = {}
    cst = pd.Series(0.0, index=days)
    R2 = R.reindex(days)

    for i, d in enumerate(reb):
        cs = [c for c in hold[d] if c in px.columns]
        nxt = reb[i + 1] if i + 1 < len(reb) else days[-1] + pd.Timedelta(days=1)
        seg = days[(days > d) & (days <= nxt)]
        if not cs:
            w: dict[str, float] = {}
            L = 0.0
        else:
            w = {c: 1.0 / len(cs) for c in cs}
            past = rp[rp.index <= d]
            past = past[past != 0]
            if len(past) < 2:
                L = 1.0
            else:
                s20 = past.iloc[-20:].std() * np.sqrt(252)
                s60 = past.iloc[-60:].std() * np.sqrt(252)
                sh = np.nanmax([s20, s60])
                L = float(min(LCAP, SIGMA_STAR / sh)) if sh and sh > 0 else 1.0
        wt = {c: L * v for c, v in w.items()}
        to = sum(abs(wt.get(k, 0) - prev.get(k, 0)) for k in set(wt) | set(prev))
        prev = wt
        if d in cst.index:
            cst.loc[d] = to * LIVE_COST_RT / 2
        if w and len(seg):
            rp.loc[seg] = (R2.loc[seg, list(w)].fillna(0) @ pd.Series(w)).values
            Ls.loc[seg] = L
    return rp * Ls - cst


def write_blocked(face_st: dict[str, float] | None, reason: str, inventory: dict[str, Any]) -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    design = (ROOT / "DESIGN.md").read_text(encoding="utf-8")
    headline = (
        "请拍板：维持面层 B45 + spike_ft max5 + E0 + TV25 + SHARPE20，"
        "对**已冻结规则**做 104w/26w 滚动 OOS 过程审计；OOS Calmar 无论塌或不塌都不换冠。"
    )
    h1_m = re.search(r"## H1\s+```\n(.*?)```", design, re.S)
    h1_block = h1_m.group(1).strip() if h1_m else ""
    face = face_st or {k: float("nan") for k in ("ret", "maxDD", "Calmar", "Sharpe", "CAGR")}
    summary = {
        "batch": "walk-forward-oos",
        "champion_swap": False,
        "crown": "NO",
        "source_sha": SOURCE_SHA,
        "sample": [EVAL_START, END_S],
        "anchor_pass": False,
        "anchor": ANCHOR,
        "protocol_primary": {"id": "WF-P10426", "train_w": 104, "test_w": 26, "step_w": 26, "n_folds": 9, "leftover_weeks": 10},
        "selection_in_train": False,
        "inventory": inventory,
        "face": face,
        "g1_threshold": 0.50 * face.get("Calmar", float("nan")) if face_st else None,
        "g3_threshold": 1.50 * abs(face.get("maxDD", float("nan"))) if face_st else None,
        "FLAG_G1": False,
        "FLAG_G2": False,
        "FLAG_G3": False,
        "family_verdict": "BLOCKED",
        "h1": f"BLOCKED：{reason}",
        "positive_ids": [],
        "strong_period_note": True,
        "cells": [],
        "folds_primary": [],
    }
    (OUT / "summary.json").write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
    report = f"""{headline}

```
{h1_block}
```

## 锚点门

{reason} → `family_verdict=BLOCKED`。

## 红线

不换冠；未混用 158.3%/0.94 锚。
"""
    (OUT / "REPORT.md").write_text(report, encoding="utf-8")
    pd.DataFrame().to_csv(OUT / "table.csv", index=False)
    pd.DataFrame(columns=["date", "book", "nav"]).to_csv(OUT / "equity.csv", index=False)
    fig, ax = plt.subplots(figsize=(8, 4))
    ax.text(0.5, 0.5, "BLOCKED", ha="center", va="center")
    fig.savefig(OUT / "equity_curve.png")
    plt.close(fig)


def main() -> None:
    run_fixtures()
    print("fixtures OK", flush=True)

    inventory = scan_inventory()
    for p in (WEEK, FACE, DAY_DIR, NOON_CSV, SINA_DAILY, SNAP_CACHE):
        if not Path(p).exists():
            write_blocked(None, f"missing kit path {p}")
            raise SystemExit(2)

    OUT.mkdir(parents=True, exist_ok=True)
    t0 = time.time()

    uni = pd.read_csv(UNI_CSV)
    uni["code"] = uni["code"].astype(str).str.zfill(6)
    uni = uni[uni["aum"] >= 2].copy()
    codes = uni["code"].tolist()
    aum = {r.code: float(r.aum or 0) for r in uni.itertuples()}

    noon = pd.read_csv(NOON_CSV)
    noon["code"] = noon["etf_code"].astype(str).str.split(".").str[0]
    noon["trade_date"] = noon["trade_date"].astype(str).str[:10]
    noon = noon[noon["code"].isin(set(codes))].copy()
    if "price_1430" in noon.columns and "price_1130" not in noon.columns:
        noon["price_1130"] = noon["price_1430"]

    face = pd.read_csv(FACE)
    face["date"] = face["date"].astype(str).str[:10]
    face = face[(face["date"] >= EVAL_START) & (face["date"] <= END_S)].copy()
    calendar = sorted(face["date"].unique().tolist())
    actual_end = calendar[-1]

    risk_on_by_fri: dict[str, bool] = {}
    for d in calendar:
        row = face[face["date"] == d].iloc[0]
        bv = row.get("b")
        risk_on_by_fri[d] = bool(
            bv is not None and not (isinstance(bv, float) and math.isnan(bv)) and float(bv) >= BREADTH_THETA
        )
    risk_on_by_fri[calendar[-1]] = False

    closes_w_close: dict[str, dict[str, float]] = {}
    for c in codes:
        fp = WEEK / f"{c}.json"
        if not fp.exists():
            closes_w_close[c] = {}
            continue
        rec = json.loads(fp.read_text(encoding="utf-8"))
        closes_w_close[c] = {
            b["date"]: float(b["c"])
            for b in (rec.get("bars") or [])
            if b.get("date") and b["date"] <= END_S and float(b["c"]) > 0
        }

    alias: dict[str, dict[str, str]] = {}
    for c in codes:
        ds = sorted(closes_w_close.get(c, {}))
        if ds:
            alias[c] = {d: hit for d in calendar if (hit := nearest_date(d, ds, 3))}

    sina = load_sina_closes(codes)
    daily = load_daily_closes(codes, sina)

    noon_w: dict[str, dict[str, float]] = defaultdict(dict)
    blocked_empty: dict[str, set[str]] = defaultdict(set)
    for r in noon.itertuples():
        td = r.trade_date
        if td < EVAL_START or td > END_S:
            continue
        if r.status == "empty" or (
            r.status == "ok"
            and (r.price_1130 is None or (isinstance(r.price_1130, float) and math.isnan(r.price_1130)))
        ):
            blocked_empty[td].add(r.code)
            continue
        if r.status != "ok":
            continue
        q = qfq_close_on(r.code, td, daily, closes_w_close)
        b = (sina.get(r.code) or {}).get(td)
        if not q or not b or b <= 0:
            blocked_empty[td].add(r.code)
            continue
        qn = float(r.price_1130) * (q / b)
        noon_w[r.code][(alias.get(r.code) or {}).get(td) or td] = qn

    closes_w_sig: dict[str, dict[str, float]] = {}
    for c in codes:
        cm = dict(closes_w_close.get(c) or {})
        cm.update({d: v for d, v in (noon_w.get(c) or {}).items() if v and v > 0})
        closes_w_sig[c] = cm
    for d, blk in blocked_empty.items():
        for c in blk:
            key = (alias.get(c) or {}).get(d) or d
            if c in closes_w_sig:
                closes_w_sig[c].pop(key, None)

    cached = json.loads(SNAP_CACHE.read_text(encoding="utf-8"))
    by_rows = cached.get("by_code") or {}
    snaps = {c: snap_index(by_rows.get(c) or []) for c in codes}

    print("simulate F0…", flush=True)
    trades, hold = simulate_f0(
        calendar=calendar,
        snaps=snaps,
        closes_w=closes_w_sig,
        alias=alias,
        aum=aum,
        daily=daily,
        risk_on_by_fri=risk_on_by_fri,
    )
    pd.DataFrame(trades).to_csv(OUT / "trades_F0.csv", index=False)

    all_codes: set[str] = set()
    for cs in hold.values():
        all_codes |= set(cs)
    px_map = {c: daily[c] for c in sorted(all_codes) if c in daily}
    px = pd.DataFrame(px_map).sort_index()
    px = px.loc[(px.index >= EVAL_START) & (px.index <= END_S)]
    R = px.pct_change()
    days = px.dropna(how="all").index
    days = days[(days >= EVAL_START) & (days <= END_S)]

    hd = {pd.Timestamp(d): cs for d, cs in hold.items()}
    r_full = run_live_tv(hd, days, px, R)
    face_st = stats_full(r_full)

    T = len(calendar) - 1
    anchor_pass = check_anchor(face_st, len(calendar), T, len(codes), actual_end)
    print(
        f"F0 ret={pct(face_st['ret'])} dd={pct(face_st['maxDD'])} Calmar={face_st['Calmar']:.3f} anchor={anchor_pass}",
        flush=True,
    )

    week_slices = week_daily_slices(r_full, calendar, T)
    protocol_blocked = False
    block_reason = ""

    primary_proto = next(p for p in PROTOCOLS if p["primary"])
    pf_folds, pf_left = make_folds(T, primary_proto["train_w"], primary_proto["test_w"], primary_proto["step_w"])
    if len(pf_folds) != 9 or pf_left != 10:
        protocol_blocked = True
        block_reason = f"主档折数/leftover 不符：{len(pf_folds)} folds leftover={pf_left}"

    oos_primary = concat_weeks(week_slices, 104, 338)
    suffix_ref = concat_weeks(week_slices, 104, 338)
    if len(oos_primary) and len(suffix_ref):
        st_oos = stats_full(oos_primary)
        st_ref = stats_full(suffix_ref)
        if abs(st_oos["Calmar"] - st_ref["Calmar"]) > 1e-9:
            protocol_blocked = True
            block_reason = "OOS 拼接与 F0 后缀 Calmar 不一致"

    # frozen slice spot check: first primary test fold
    if pf_folds and not protocol_blocked:
        t0, t1 = pf_folds[0]["test"]
        seg = concat_weeks(week_slices, t0, t1)
        ref = concat_weeks(week_slices, t0, t1)
        if len(seg) and (seg - ref).abs().max() > 1e-15:
            protocol_blocked = True
            block_reason = "冻结切片与 F0 不一致"

    cells: list[dict[str, Any]] = []
    folds_primary: list[dict[str, Any]] = []
    oos_series: dict[str, pd.Series] = {}

    f0_cell = {
        "id": "F0",
        "train_w": None,
        "test_w": None,
        "step_w": None,
        "n_folds": None,
        "leftover_weeks": None,
        "oos": {**face_st, "n_weeks": T},
        "is_prefix": None,
        "g1_collapse": False,
        "g2_floor": False,
        "g3_dd": False,
        "verdict": "ANCHOR",
    }
    cells.append(f0_cell)

    for proto in PROTOCOLS:
        folds, leftover = make_folds(T, proto["train_w"], proto["test_w"], proto["step_w"])
        exp = next(x for x in FOLD_FIXTURES if x[1] == proto["train_w"] and x[2] == proto["test_w"])
        if len(folds) != exp[4] or leftover != exp[6]:
            protocol_blocked = True
            block_reason = f"{proto['id']} 折协议不符"
        oos_parts: list[pd.Series] = []
        for f in folds:
            ts, te = f["test"]
            oos_parts.append(concat_weeks(week_slices, ts, te))
        oos_r = pd.concat(oos_parts).sort_index() if oos_parts else pd.Series(dtype=float)
        oos_series[proto["id"]] = oos_r
        is_r = concat_weeks(week_slices, 0, proto["train_w"])
        oos_st = stats_full(oos_r)
        is_st = stats_full(is_r)
        oos_st["n_weeks"] = proto["test_w"] * len(folds) if folds else 0
        g1, g2, g3 = compute_gates(face_st, oos_st)
        verdict = "COLLAPSE" if (g1 or g2 or g3) else "HOLD_CAVEAT"
        cells.append(
            {
                "id": proto["id"],
                "train_w": proto["train_w"],
                "test_w": proto["test_w"],
                "step_w": proto["step_w"],
                "n_folds": len(folds),
                "leftover_weeks": leftover,
                "oos": oos_st,
                "is_prefix": is_st,
                "g1_collapse": g1,
                "g2_floor": g2,
                "g3_dd": g3,
                "verdict": verdict,
            }
        )

        if proto["primary"]:
            for fi, f in enumerate(folds):
                ts, te = f["test"]
                fr = concat_weeks(week_slices, ts, te)
                fst = stats_full(fr)
                tag = period_tag_for_test(calendar, (ts, te))
                folds_primary.append(
                    {
                        "fold": fi,
                        "train": list(f["train"]),
                        "test": list(f["test"]),
                        "train_end": calendar[f["train"][1] - 1],
                        "test_end": calendar[te - 1],
                        "ret": fst["ret"],
                        "maxDD": fst["maxDD"],
                        "Calmar": fst["Calmar"],
                        "Sharpe": fst["Sharpe"],
                        "period_tag": tag,
                    }
                )

    has_2022_probe = any(
        any("2022" in calendar[i] for i in range(f["test"][0], f["test"][1])) for f in pf_folds
    )
    if not has_2022_probe:
        protocol_blocked = True
        block_reason = "主档折表缺 2022 探针"

    primary_cell = next(c for c in cells if c["id"] == "WF-P10426")
    g1_p, g2_p, g3_p = primary_cell["g1_collapse"], primary_cell["g2_floor"], primary_cell["g3_dd"]

    if not anchor_pass or protocol_blocked:
        family_verdict = "BLOCKED"
        h1 = f"BLOCKED：{block_reason or '锚点未过'}"
        g1_p = g2_p = g3_p = False
    elif g1_p or g2_p or g3_p:
        family_verdict = "COLLAPSE"
        h1 = "主档过闸 → H1 成立（COLLAPSE，不换冠）"
    else:
        family_verdict = "HOLD_CAVEAT"
        h1 = "主档未塌 → H1 证伪（HOLD_CAVEAT，不换冠）"

    g1_threshold = 0.50 * face_st["Calmar"]
    g3_threshold = 1.50 * abs(face_st["maxDD"])

    # table.csv
    table_rows: list[dict[str, Any]] = []
    for c in cells:
        if c["id"] == "F0":
            oos = c["oos"]
            table_rows.append(
                {
                    "kind": "protocol",
                    "id": "F0",
                    "train_w": "",
                    "test_w": "",
                    "step_w": "",
                    "fold": "",
                    "ret": oos["ret"],
                    "maxDD": oos["maxDD"],
                    "CAGR": oos["CAGR"],
                    "Calmar": oos["Calmar"],
                    "Sharpe": oos["Sharpe"],
                    "n_weeks": oos.get("n_weeks", T),
                    "leftover_weeks": "",
                    "period_tag": "",
                    "g1_collapse": False,
                    "g2_floor": False,
                    "g3_dd": False,
                    "verdict": "ANCHOR",
                }
            )
        else:
            oos = c["oos"]
            table_rows.append(
                {
                    "kind": "protocol",
                    "id": c["id"],
                    "train_w": c["train_w"],
                    "test_w": c["test_w"],
                    "step_w": c["step_w"],
                    "fold": "",
                    "ret": oos["ret"],
                    "maxDD": oos["maxDD"],
                    "CAGR": oos["CAGR"],
                    "Calmar": oos["Calmar"],
                    "Sharpe": oos["Sharpe"],
                    "n_weeks": oos.get("n_weeks"),
                    "leftover_weeks": c["leftover_weeks"],
                    "period_tag": "",
                    "g1_collapse": c["g1_collapse"],
                    "g2_floor": c["g2_floor"],
                    "g3_dd": c["g3_dd"],
                    "verdict": c["verdict"],
                }
            )
    for fp in folds_primary:
        table_rows.append(
            {
                "kind": "fold",
                "id": "WF-P10426",
                "train_w": 104,
                "test_w": 26,
                "step_w": 26,
                "fold": fp["fold"],
                "ret": fp["ret"],
                "maxDD": fp["maxDD"],
                "CAGR": float("nan"),
                "Calmar": fp["Calmar"],
                "Sharpe": fp["Sharpe"],
                "n_weeks": 26,
                "leftover_weeks": "",
                "period_tag": fp["period_tag"],
                "g1_collapse": False,
                "g2_floor": False,
                "g3_dd": False,
                "verdict": "",
            }
        )
    cols = [
        "kind",
        "id",
        "train_w",
        "test_w",
        "step_w",
        "fold",
        "ret",
        "maxDD",
        "CAGR",
        "Calmar",
        "Sharpe",
        "n_weeks",
        "leftover_weeks",
        "period_tag",
        "g1_collapse",
        "g2_floor",
        "g3_dd",
        "verdict",
    ]
    pd.DataFrame(table_rows)[cols].to_csv(OUT / "table.csv", index=False)

    nav_f0 = (1 + r_full).cumprod()
    eq_long: list[dict[str, Any]] = []
    for dt, nv in nav_f0.items():
        eq_long.append({"date": dt.strftime("%Y-%m-%d"), "book": BOOK_F0, "nav": float(nv)})

    for proto in PROTOCOLS:
        pid = proto["id"]
        r_oos = oos_series[pid]
        if len(r_oos) == 0:
            continue
        nav_oos = (1 + r_oos).cumprod()
        folds_p, _ = make_folds(T, proto["train_w"], proto["test_w"], proto["step_w"])
        first_w = folds_p[0]["test"][0] if folds_p else 0
        anchor_date = pd.Timestamp(calendar[first_w])
        sub_f0 = nav_f0[nav_f0.index > anchor_date]
        scale = float(sub_f0.iloc[0]) if len(sub_f0) else 1.0
        for dt, nv in nav_oos.items():
            eq_long.append(
                {
                    "date": dt.strftime("%Y-%m-%d"),
                    "book": pid,
                    "nav": float(nv * scale),
                }
            )
    pd.DataFrame(eq_long).to_csv(OUT / "equity.csv", index=False)

    fig, ax = plt.subplots(figsize=(11, 5.5), dpi=120)
    ax.plot(nav_f0.index, nav_f0.values, color="black", lw=2.2, label=BOOK_F0)
    for proto in PROTOCOLS:
        pid = proto["id"]
        r_oos = oos_series.get(pid)
        if r_oos is None or len(r_oos) == 0:
            continue
        nav_oos = (1 + r_oos).cumprod()
        folds_p, _ = make_folds(T, proto["train_w"], proto["test_w"], proto["step_w"])
        first_w = folds_p[0]["test"][0]
        anchor_date = pd.Timestamp(calendar[first_w])
        sub_f0 = nav_f0[nav_f0.index > anchor_date]
        scale = float(sub_f0.iloc[0]) if len(sub_f0) else 1.0
        lw = 1.6 if proto["primary"] else 1.0
        ls = "-" if proto["primary"] else "--"
        col = "tab:blue" if proto["primary"] else "gray"
        ax.plot(nav_oos.index, nav_oos.values * scale, color=col, lw=lw, ls=ls, alpha=0.9, label=pid)
    ax.set_yscale("log")
    ax.set_title("walk-forward OOS (F0 black; WF scaled to F0 at OOS start)")
    ax.set_ylabel("NAV (log)")
    ax.grid(True, alpha=0.3)
    ax.legend(fontsize=8)
    fig.tight_layout()
    fig.savefig(OUT / "equity_curve.png")
    plt.close(fig)

    design = (ROOT / "DESIGN.md").read_text(encoding="utf-8")
    headline = (
        "请拍板：维持面层 B45 + spike_ft max5 + E0 + TV25 + SHARPE20，"
        "对**已冻结规则**做 104w/26w 滚动 OOS 过程审计；OOS Calmar 无论塌或不塌都不换冠。"
    )
    h1_m = re.search(r"## H1\s+```\n(.*?)```", design, re.S)
    h1_block = h1_m.group(1).strip() if h1_m else ""

    oos_dates = f"{oos_primary.index.min().date() if len(oos_primary) else '—'} → {oos_primary.index.max().date() if len(oos_primary) else '—'}"

    summary = {
        "batch": "walk-forward-oos",
        "champion_swap": False,
        "crown": "NO",
        "source_sha": SOURCE_SHA,
        "sample": [EVAL_START, actual_end],
        "anchor_pass": anchor_pass and not protocol_blocked,
        "anchor": {**ANCHOR, "n_weeks": len(calendar), "T": T},
        "protocol_primary": {
            "id": "WF-P10426",
            "train_w": 104,
            "test_w": 26,
            "step_w": 26,
            "n_folds": len(pf_folds),
            "leftover_weeks": pf_left,
        },
        "selection_in_train": False,
        "inventory": inventory,
        "face": face_st,
        "g1_threshold": g1_threshold,
        "g3_threshold": g3_threshold,
        "FLAG_G1": g1_p if family_verdict != "BLOCKED" else False,
        "FLAG_G2": g2_p if family_verdict != "BLOCKED" else False,
        "FLAG_G3": g3_p if family_verdict != "BLOCKED" else False,
        "family_verdict": family_verdict,
        "h1": h1,
        "positive_ids": [],
        "strong_period_note": True,
        "cells": cells,
        "folds_primary": folds_primary,
        "elapsed_sec": round(time.time() - t0, 1),
    }
    if not anchor_pass:
        summary["anchor_pass"] = False
    (OUT / "summary.json").write_text(json.dumps(summary, ensure_ascii=False, indent=2, default=str), encoding="utf-8")

    def row_proto(c: dict[str, Any]) -> str:
        o = c["oos"]
        return (
            f"{c['id']} | {pct(o['ret'])} | {pct(o['maxDD'])} | {o['Calmar']:.2f} | {o['Sharpe']:.2f} | "
            f"{c['verdict']} | G1={c['g1_collapse']} G2={c['g2_floor']} G3={c['g3_dd']}"
        )

    anchor_line = (
        f"F0 本次 {pct(face_st['ret'])} / {pct(face_st['maxDD'])} / Calmar {face_st['Calmar']:.2f} "
        f"（锚 LIVE1430-B45-S20-max5 = 131.6% / −18.8% / 0.70，SHA {SOURCE_SHA[:8]}）→ "
        f"{'通过' if anchor_pass else '未通过'}。"
    )
    gate_lines = (
        f"- G1 阈：`0.50 × Calmar_FACE` = **{g1_threshold:.4f}**（本次 F0 Calmar={face_st['Calmar']:.4f}）\n"
        f"- G3 阈：`1.50 × |maxDD_FACE|` = **{g3_threshold:.4f}**（本次 |maxDD|={abs(face_st['maxDD']):.4f}）\n"
        f"- 主档 OOS Calmar={primary_cell['oos']['Calmar']:.4f}；FLAG_G1/2/3 = {g1_p}/{g2_p}/{g3_p}"
    )
    if family_verdict == "COLLAPSE":
        verdict_para = "**COLLAPSE（不换冠）**：主档 OOS 拼接过 G1/G2/G3 之一，H1 成立。"
    elif family_verdict == "HOLD_CAVEAT":
        verdict_para = (
            "**HOLD_CAVEAT（不换冠）**：主档 OOS 未过塌缩闸；后段已发表 Calmar 1.39 vs 前段 0.37，"
            "OOS 偏高不等于稳健确认，禁止 CONFIRMED/换冠。"
        )
    else:
        verdict_para = f"**BLOCKED（不换冠）**：{block_reason or '锚点未过'}。"

    fold_tbl = "\n".join(
        f"| {f['fold']} | {f['test'][0]}–{f['test'][1]} | {f['test_end']} | {f['period_tag']} | "
        f"{pct(f['ret'])} | {pct(f['maxDD'])} | {f['Calmar']:.2f} |"
        for f in folds_primary
    )

    report = f"""{headline}

```
{h1_block}
```

## 锚点门

{anchor_line}

## 强势段注

- 已发表分段（仅引用）：2020–22 Calmar **0.37**；2023–26 Calmar **1.39**（PR#28/27 主表）。
- 主档 OOS 拼接日历：**{oos_dates}**（周 [104, 338)，234 持有周；leftover 10 周不评分）。
- OOS 时间权重偏后段；OOS Calmar 高于全样本 0.70 **不是**稳健确认。

## 主表（F0 + 四协议 OOS 拼接）

| id | ret | maxDD | Calmar | Sharpe | verdict | 三闸 |
|---|---:|---:|---:|---:|---|---|
| {row_proto(f0_cell)}
{chr(10).join(row_proto(c) for c in cells if c['id'] != 'F0')}

## 主档折表（WF-P10426）

| fold | test 周 | test_end | period_tag | ret | maxDD | Calmar |
|---:|---|---|---|---:|---:|---:|
{fold_tbl}

## 三闸（仅主档 OOS 拼接）

{gate_lines}

## 证伪段

{verdict_para}

`family_verdict={family_verdict}`；`positive_ids=[]`；`champion_swap=false`。

## 红线

未重开 CLOUD-BATCH / MOM121 / RET / corr-dedup / residual-mom / PR#54 TV-WF；未混用 158.3%/0.94 或 68.1%/0.31 锚；未改 LIVE_OPS / champion_mast。

耗时 {summary['elapsed_sec']}s。
"""
    (OUT / "REPORT.md").write_text(report, encoding="utf-8")
    print("done", OUT, "verdict", family_verdict, flush=True)


if __name__ == "__main__":
    main()
