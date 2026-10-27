#!/usr/bin/env python3
"""clenow-slope-r2-fill: B45 spike_ft max5 + E0 + TV25; F0 SHARPE20 vs Clenow slope×R² seat fill.

Four books: F0 (S20), SR90, SR60, SR90K2. Engine fork pin 05f0f8a4 (btheta LIVE1430).
Research pool only — no crown swap.
"""
from __future__ import annotations

import json
import math
import subprocess
import sys
import time
from collections import defaultdict
from concurrent.futures import ThreadPoolExecutor, as_completed
from copy import deepcopy
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

KIT = Path(__file__).resolve().parent.parent / "cloud_batch" / "CLOUD-BATCH-2026-10-26"
SCRIPTS = KIT / "scripts"
sys.path.insert(0, str(SCRIPTS))

from backtest import KEEP, LIVE_PHASE, MIN_BARS, Position, nearest_date, snap_index  # noqa: E402
from build_scan import Bar, classify  # noqa: E402

OUT = Path(__file__).resolve().parent / "out"
CACHE = KIT / "data" / "research_cache"
UNI_CSV = KIT / "data" / "universe_replace_only_436.csv"
WEEK = CACHE / "week"
FACE = CACHE / "holdings_ro2_extended.csv"
DAY_DIR = CACHE / "day"
TEMA_PX = Path("/workspace/tema_etf_scan_2018/prices_daily")  # optional overlay
NOON_CSV = CACHE / "fri_1430_through_20261023.csv"
SINA_DAILY = CACHE / "sina_daily"
CLASSIFY_FROM = "2019-07-01"
SNAP_CACHE = KIT / "data" / "cache_1430_snaps.json"
SOURCE_SHA = "05f0f8a4f778fde886f3e7b2976646ff4b7d777b"
BREADTH_THETA = 0.45
ANCHOR = {"ret": 1.316, "maxDD": -0.188, "Calmar": 0.70, "n_weeks": 349, "T": 348, "n_codes": 324}
ANCH_TOL = {"ret": 0.005, "maxDD": 0.002, "Calmar": 0.02}

PIN_RUN_PATH = "research/cloud_batch/SPIKE-S20-BTHETA-GRID-LIVE1430/run.py"

BOOK_SPECS = [
    {"id": "F0", "book": "LIVE1430-B45-S20-max5", "mode": "sharpe", "n": 20, "k": 0},
    {"id": "SR90", "book": "LIVE1430-B45-SR90-max5", "mode": "clenow", "n": 90, "k": 1},
    {"id": "SR60", "book": "LIVE1430-B45-SR60-max5", "mode": "clenow", "n": 60, "k": 1},
    {"id": "SR90K2", "book": "LIVE1430-B45-SR90K2-max5", "mode": "clenow", "n": 90, "k": 2},
]

SKIPPED_FILLS = [
    "RET8",
    "RET12",
    "MOM121",
    "Z121",
    "R4W",
    "SORTINO20",
    "residual-mom",
    "corr-dedup",
]

EVAL_START = "2020-01-03"
END_S = "2026-10-23"
COST_SIDE = 0.001
SIGMA_STAR = 0.25
LCAP = 1.0
LIVE_COST_RT = 0.002
CLASSIFY_WORKERS = 8


@dataclass
class Cand:
    code: str
    px: float
    fz: float | None
    aum: float
    sharpe: float | None = None
    score: float | None = None
    r2: float | None = None


def is_spike(snap: dict[str, Any] | None) -> bool:
    if not snap:
        return False
    if snap.get("pending_second_week") or snap.get("in_play_kind") == "box_pending":
        return False
    return bool(snap.get("in_play")) and snap.get("in_play_kind") == "spike_ft"


RankFn = Callable[[Cand, list[Cand]], tuple]


def sharpe_key(c: Cand, pool: list[Cand]) -> tuple:
    miss = 0 if c.sharpe is not None else 1
    return (miss, -(c.sharpe if c.sharpe is not None else 0.0), c.code)


def clenow_key(c: Cand, pool: list[Cand]) -> tuple:
    miss = 0 if c.score is not None else 1
    return (miss, -(c.score if c.score is not None else 0.0), c.code)


def clenow_score_on(closes: pd.Series, d: str, n: int, k: int) -> tuple[float | None, float | None]:
    """Return (score, r2). Both None if not rankable."""
    ts = pd.Timestamp(d)
    sub = closes.loc[: ts - pd.Timedelta(days=1)]
    if len(sub) < n:
        return None, None
    if (ts - sub.index[-1]).days > 5:
        return None, None
    window = sub.iloc[-n:]
    if len(window) < n:
        return None, None
    px = window.to_numpy(dtype=float)
    if np.any(~np.isfinite(px)) or np.any(px <= 0):
        return None, None
    y = np.log(px)
    t = np.arange(n, dtype=float)
    t0 = t - t.mean()
    y0 = y - y.mean()
    sxx = float(np.dot(t0, t0))
    syy = float(np.dot(y0, y0))
    sxy = float(np.dot(t0, y0))
    if sxx <= 0 or syy <= 1e-20 or not np.isfinite(sxx + syy + sxy):
        return None, None
    beta = sxy / sxx
    r2 = (sxy * sxy) / (sxx * syy)
    if (not np.isfinite(beta)) or (not np.isfinite(r2)):
        return None, None
    if r2 < -1e-12 or r2 > 1.0 + 1e-12:
        return None, None
    r2 = float(min(1.0, max(0.0, r2)))
    slope_ann = float(np.exp(beta * 252.0) - 1.0)
    if not np.isfinite(slope_ann):
        return None, None
    score = float(slope_ann * (r2 ** k))
    if not np.isfinite(score):
        return None, None
    return score, r2


def run_fixtures() -> None:
    idx = pd.date_range("2024-01-02", periods=90, freq="B")
    px = np.exp(0.001 * np.arange(90))
    ser = pd.Series(px, index=idx)
    sig_d = (idx[-1] + pd.Timedelta(days=2)).strftime("%Y-%m-%d")
    sc, r2 = clenow_score_on(ser, sig_d, 90, 1)
    assert sc is not None and r2 is not None
    beta = 0.001
    assert abs(beta - 0.001) < 1e-12  # checked via regression below
    t = np.arange(90, dtype=float)
    t0 = t - t.mean()
    y = np.log(px)
    y0 = y - y.mean()
    sxx = float(np.dot(t0, t0))
    sxy = float(np.dot(t0, y0))
    beta_hat = sxy / sxx
    assert abs(beta_hat - 0.001) < 1e-12
    assert abs(r2 - 1.0) < 1e-12
    exp_ann = float(np.exp(0.001 * 252) - 1)
    assert abs(sc - exp_ann) < 1e-12
    sc2, _ = clenow_score_on(ser, sig_d, 90, 2)
    assert sc2 is not None and abs(sc2 - exp_ann) < 1e-12
    alt = float(np.exp(beta_hat) ** 252 - 1)
    assert abs(exp_ann - alt) < 1e-12
    flat = pd.Series([10.0] * 90, index=idx)
    assert clenow_score_on(flat, sig_d, 90, 1) == (None, None)
    gap_d = (idx[-1] + pd.Timedelta(days=10)).strftime("%Y-%m-%d")
    assert clenow_score_on(ser, gap_d, 90, 1) == (None, None)
    short = ser.iloc[:89]
    assert clenow_score_on(short, sig_d, 90, 1) == (None, None)
    bad = ser.copy()
    bad.iloc[10] = -1.0
    assert clenow_score_on(bad, sig_d, 90, 1) == (None, None)
    teddy = float((1 + 0.001) ** 252)
    ours = float(np.exp(0.001 * 252) - 1)
    assert abs(teddy - ours) > 0.9
    sa, r2a = 0.40, 0.50
    sb, r2b = 0.22, 0.90
    assert sa * r2a > sb * r2b
    assert sa * (r2a ** 2) < sb * (r2b ** 2)


def assert_pin_and_kit() -> None:
    r = subprocess.run(
        ["git", "cat-file", "-e", f"{SOURCE_SHA}:{PIN_RUN_PATH}"],
        capture_output=True,
        text=True,
    )
    if r.returncode != 0:
        sys.stderr.write(f"BLOCKED: missing pin SHA {SOURCE_SHA} path {PIN_RUN_PATH}\n")
        raise SystemExit(1)
    for p in (KIT, SCRIPTS / "backtest.py", CACHE, UNI_CSV, SNAP_CACHE):
        if not Path(p).exists():
            sys.stderr.write(f"BLOCKED: missing kit path {p}\n")
            raise SystemExit(1)


def load_daily_closes(
    codes: list[str], sina: dict[str, dict[str, float]] | None = None
) -> dict[str, pd.Series]:
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
                if s is None:
                    s = px
                else:
                    s = px.combine_first(s).sort_index()
        if s is None and sina and c in sina and len(sina[c]) >= 10:
            idx = pd.to_datetime(sorted(sina[c]))
            s = pd.Series([sina[c][d.strftime("%Y-%m-%d")] for d in idx], index=idx, dtype=float)
        if s is not None and len(s) >= 10:
            out[c] = s
    return out


def qfq_close_on(
    code: str,
    td: str,
    daily: dict[str, pd.Series],
    closes_w: dict[str, dict[str, float]],
) -> float | None:
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
        out[c] = {
            str(r.date)[:10]: float(r.close)
            for r in df.itertuples()
            if r.close and float(r.close) > 0
        }
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


def classify_modified(
    raws_w: dict[str, dict[str, Any]], noon_w: dict[str, dict[str, float]]
) -> dict[str, list[dict[str, Any]]]:
    def one(code: str) -> list[dict[str, Any]]:
        rec = deepcopy(raws_w.get(code) or {})
        nm = noon_w.get(code) or {}
        bars: list[Bar] = []
        for b in rec.get("bars") or []:
            d = b["date"]
            o, h, l, c = float(b["o"]), float(b["h"]), float(b["l"]), float(b["c"])
            if d in nm:
                c = float(nm[d])
                h = max(h, c)
                l = min(l, c)
            if min(o, h, l, c) <= 0:
                continue
            bars.append(Bar(d, o, h, l, c))
        snaps: list[dict[str, Any]] = []
        for i in range(len(bars)):
            if bars[i].date < CLASSIFY_FROM or i + 1 < MIN_BARS:
                continue
            try:
                cl = classify(bars[: i + 1])
            except Exception:
                continue
            snap = {k: cl.get(k) for k in KEEP}
            snap["code"] = code
            snap["last_bar_date"] = bars[i].date
            snaps.append(snap)
        return snaps

    by: dict[str, list[dict[str, Any]]] = {}
    codes = list(raws_w)
    t0 = time.time()
    with ThreadPoolExecutor(max_workers=CLASSIFY_WORKERS) as ex:
        futs = {ex.submit(one, c): c for c in codes}
        done = 0
        for fut in as_completed(futs):
            c = futs[fut]
            by[c] = fut.result()
            done += 1
            if done % 80 == 0 or done == len(codes):
                print(f"  classify {done}/{len(codes)} {time.time() - t0:.0f}s", flush=True)
    return by


def simulate(
    calendar: list[str],
    snaps: dict[str, dict[str, dict[str, Any]]],
    closes_w: dict[str, dict[str, float]],
    alias: dict[str, dict[str, str]],
    aum: dict[str, float],
    daily: dict[str, pd.Series],
    risk_on_by_fri: dict[str, bool],
    variant: str,
    mode: str,
    max_pos: int,
    sharpe_n: int | None = 20,
    clenow_n: int | None = None,
    clenow_k: int | None = None,
) -> tuple[
    list[dict[str, Any]],
    dict[str, list[str]],
    dict[str, Any],
    list[tuple[str, str, float, float | None, float | None]],
]:
    cash = 1.0
    positions: dict[str, Position] = {}
    trades: list[dict[str, Any]] = []
    picks: dict[str, list[str]] = {}
    n_tight = 0
    n_feat = 0
    n_entries = 0
    n_miss_sharpe = 0
    n_miss_clenow = 0
    abs_d_sizes: list[int] = []
    entry_log: list[tuple[str, str, float, float | None, float | None]] = []
    rank_rows: list[dict[str, Any]] = []

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
            sh = None
            if sharpe_n is not None and code in daily:
                sh = sharpe_n_on(daily[code], d, sharpe_n)
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
                    "variant": variant,
                    "code": code,
                    "entry_date": p.entry_date,
                    "exit_date": d,
                    "exit_reason": reason,
                    "weeks_held": p.weeks + 1,
                }
            )

        take: list[Cand] = []
        if not last_bar:
            score_map: dict[str, tuple[float, float]] = {}
            if mode == "clenow":
                if clenow_n is None or clenow_k is None:
                    raise SystemExit("clenow mode needs clenow_n/clenow_k")
                for code in snaps:
                    sn = snap_at(code, d)
                    if not is_spike(sn):
                        continue
                    px = px_on(code, d)
                    if px is None or px <= 0:
                        continue
                    if code not in daily:
                        n_miss_clenow += 1
                        continue
                    sc, r2 = clenow_score_on(daily[code], d, clenow_n, clenow_k)
                    if sc is None:
                        n_miss_clenow += 1
                    else:
                        score_map[code] = (sc, r2)
                if risk_on and len(score_map) >= 1:
                    abs_d_sizes.append(len(score_map))

        if not last_bar and risk_on:
            pool = build_cands(d, set(positions))
            if mode == "clenow":
                for c in pool:
                    if c.code in score_map:
                        sc, r2 = score_map[c.code]
                        c.score = sc
                        c.r2 = r2

            slots = max_pos - len(positions)
            if pool:
                n_feat += 1
            if slots > 0 and len(pool) > slots:
                n_tight += 1
            if slots > 0 and pool:
                if mode == "sharpe":
                    pool_rank = [c for c in pool if c.sharpe is not None]
                    take = sorted(pool_rank, key=lambda c: sharpe_key(c, pool_rank))[:slots]
                    for c in take:
                        n_entries += 1
                        entry_log.append((d, c.code, c.px, None, None))
                        if c.sharpe is None:
                            n_miss_sharpe += 1
                        rank_rows.append(
                            {
                                "date": d,
                                "variant": variant,
                                "code": c.code,
                                "aum": c.aum,
                                "sharpe": c.sharpe,
                                "rank_slot": True,
                            }
                        )
                else:
                    pool_rank = [c for c in pool if c.score is not None]
                    take = sorted(pool_rank, key=lambda c: clenow_key(c, pool_rank))[:slots]
                    for c in take:
                        n_entries += 1
                        entry_log.append((d, c.code, c.px, c.score, c.r2))
                        rank_rows.append(
                            {
                                "date": d,
                                "variant": variant,
                                "code": c.code,
                                "aum": c.aum,
                                "score": c.score,
                                "r2": c.r2,
                                "rank_slot": True,
                            }
                        )

        picks[d] = [c.code for c in take]

        if take:
            eq = equity_now()
            n_after = len(positions) + len(take)
            if n_after > max_pos:
                raise SystemExit(f"overflow {variant} {d} n={n_after}")
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
    entries_by_day = picks
    for d in calendar:
        for code in exits_by_day.get(d, []):
            open_codes.discard(code)
        for code in entries_by_day.get(d, []):
            open_codes.add(code)
        hold[d] = sorted(open_codes)

    # cash weeks = risk_off OR empty hold (for reporting use risk_on + hold)
    n_cash = sum(1 for d in calendar[:-1] if not (hold.get(d) or []))
    stats = {
        "n_fridays_queue_gt_seats": n_tight,
        "n_fridays_with_cands": n_feat,
        "n_entries": n_entries,
        "n_entries_missing_sharpe": n_miss_sharpe,
        "n_miss_clenow": n_miss_clenow,
        "mean_abs_D": float(np.mean(abs_d_sizes)) if abs_d_sizes else 0.0,
        "n_trades": len(trades),
        "max_pos": max_pos,
        "n_cash_weeks": n_cash,
        "n_calendar_weeks_ex_last": max(0, len(calendar) - 1),
        "cash_week_pct": n_cash / max(1, len(calendar) - 1),
        "n_risk_on_weeks": sum(1 for d in calendar[:-1] if risk_on_by_fri.get(d)),
        "risk_on_week_pct": sum(1 for d in calendar[:-1] if risk_on_by_fri.get(d))
        / max(1, len(calendar) - 1),
    }
    if rank_rows:
        pd.DataFrame(rank_rows).to_csv(OUT / f"entries_{variant}.csv", index=False)
    return trades, hold, stats, entry_log


def run_live_tv(
    hold: dict[pd.Timestamp, list[str]], days: pd.DatetimeIndex, px: pd.DataFrame, R: pd.DataFrame
) -> tuple[pd.Series, pd.Series, float]:
    reb = sorted(hold)
    rp = pd.Series(0.0, index=days)
    Ls = pd.Series(0.0, index=days)
    prev: dict[str, float] = {}
    cst = pd.Series(0.0, index=days)
    R2 = R.reindex(days)
    to_sum = 0.0
    to_n = 0

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
        to_sum += to
        to_n += 1
        prev = wt
        if d in cst.index:
            cst.loc[d] = to * LIVE_COST_RT / 2
        if w and len(seg):
            rp.loc[seg] = (R2.loc[seg, list(w)].fillna(0) @ pd.Series(w)).values
            Ls.loc[seg] = L
    r = rp * Ls - cst
    avg_to = (to_sum / to_n / 2.0) if to_n else 0.0
    return r, Ls, avg_to


def stats_full(s: pd.Series) -> dict[str, float]:
    if s is None or len(s) < 2:
        return {"ret": float("nan"), "maxDD": float("nan"), "CAGR": float("nan"), "Calmar": float("nan")}
    q = (1 + s).cumprod()
    ret = float(q.iloc[-1] - 1)
    dd = float((q / q.cummax().clip(lower=1e-12) - 1).min())
    n = (s.index[-1] - s.index[0]).days
    cagr = (1 + ret) ** (365.25 / n) - 1 if n > 0 and (1 + ret) > 0 else float("nan")
    cal = cagr / abs(dd) if dd < 0 else float("nan")
    return {"ret": ret, "maxDD": dd, "CAGR": cagr, "Calmar": cal}


def yearly_table(r: pd.Series) -> pd.DataFrame:
    rows = []
    for y in sorted(set(r.index.year)):
        sy = r[r.index.year == y]
        if len(sy) < 2:
            continue
        qy = (1 + sy).cumprod()
        ret = float(qy.iloc[-1] - 1)
        mdd = float((qy / qy.cummax().clip(lower=1e-12) - 1).min())
        vol = float(sy.std() * np.sqrt(252)) if len(sy) > 1 else float("nan")
        sharpe = float(sy.mean() / sy.std() * np.sqrt(252)) if sy.std() > 0 else float("nan")
        calmar = ret / abs(mdd) if mdd < 0 else float("nan")
        rows.append({"year": y, "ret": ret, "mdd": mdd, "vol": vol, "sharpe": sharpe, "calmar": calmar})
    return pd.DataFrame(rows)


def pct(x: float | None) -> str:
    if x is None or (isinstance(x, float) and (math.isnan(x) or math.isinf(x))):
        return "—"
    return f"{100 * x:.1f}%"


def entry_quality(
    entry_log: list[tuple[str, str, float]],
    calendar: list[str],
    closes_w: dict[str, dict[str, float]],
    alias: dict[str, dict[str, str]],
) -> tuple[float, float]:
    rets: list[float] = []
    for ent_d, code, px0, *_ in entry_log:
        if ent_d not in calendar:
            continue
        idx = calendar.index(ent_d)
        if idx + 1 >= len(calendar) - 1:
            continue
        nxt = calendar[idx + 1]
        key = (alias.get(code) or {}).get(nxt) or nxt
        px1 = (closes_w.get(code) or {}).get(key)
        if px1 is None or px0 <= 0:
            continue
        rets.append(float(px1) / float(px0) - 1.0)
    if not rets:
        return 0.0, 0.0
    wins = [r for r in rets if r > 0]
    losses = [r for r in rets if r <= 0]
    hit = len(wins) / len(rets)
    if losses:
        win_size = (float(np.mean(wins)) if wins else 0.0) / abs(float(np.mean(losses)))
    else:
        win_size = float(np.mean(wins)) if wins else 0.0
    return hit, win_size


def check_anchor(st: dict[str, float], n_weeks: int, n_codes: int, end_s: str) -> bool:
    if end_s != END_S:
        return False
    if n_weeks != ANCHOR["n_weeks"]:
        return False
    if n_codes != ANCHOR["n_codes"]:
        return False
    if abs(st["ret"] - ANCHOR["ret"]) > ANCH_TOL["ret"]:
        return False
    if abs(st["maxDD"] - ANCHOR["maxDD"]) > ANCH_TOL["maxDD"]:
        return False
    if abs(st["Calmar"] - ANCHOR["Calmar"]) > ANCH_TOL["Calmar"]:
        return False
    return True


def entry_set(entry_log: list[tuple[str, str, float, float | None, float | None]]) -> set[tuple[str, str]]:
    return {(d, c) for d, c, *_ in entry_log}


def jaccard_vs(a: set[tuple[str, str]], b: set[tuple[str, str]], self_id: str) -> float:
    if self_id == "F0":
        return 1.0
    if not a or not b:
        return 0.0
    inter = len(a & b)
    union = len(a | b)
    return inter / union if union else 0.0


def judge_vs_f0(cell: dict[str, Any], f0: dict[str, Any]) -> None:
    if cell["id"] == "F0":
        cell["delta_ret"] = 0.0
        cell["delta_abs_mdd"] = 0.0
        cell["covers"] = True
        cell["window_2020_22"] = True
        cell["window_2023_26"] = True
        cell["verdict"] = "ANCHOR"
        return
    dret = cell["ret"] - f0["ret"]
    d_abs = abs(cell["maxDD"]) - abs(f0["maxDD"])
    cell["delta_ret"] = dret
    cell["delta_abs_mdd"] = d_abs
    covers = dret >= d_abs
    w22 = cell["w2020_22"]["ret"] >= f0["w2020_22"]["ret"]
    w26 = cell["w2023_26"]["ret"] >= f0["w2023_26"]["ret"]
    cell["covers"] = covers
    cell["window_2020_22"] = w22
    cell["window_2023_26"] = w26
    if any(math.isnan(x) for x in (cell["ret"], cell["maxDD"], dret, d_abs)):
        cell["verdict"] = "证伪"
    elif covers and w22 and w26:
        cell["verdict"] = "记正"
    else:
        cell["verdict"] = "证伪"


def main() -> None:
    assert_pin_and_kit()
    run_fixtures()
    print("fixtures OK", flush=True)
    OUT.mkdir(parents=True, exist_ok=True)
    t0 = time.time()
    for p in (WEEK, FACE, DAY_DIR, NOON_CSV, SINA_DAILY):
        if not Path(p).exists():
            raise SystemExit(f"missing research cache path {p}; run extend_research_data.py first")

    print("load universe + extended 14:30 + week…", flush=True)
    uni = pd.read_csv(UNI_CSV)
    uni["code"] = uni["code"].astype(str).str.zfill(6)
    uni = uni[uni["aum"] >= 2].copy()
    codes = uni["code"].tolist()
    aum = {r.code: float(r.aum or 0) for r in uni.itertuples()}
    code_set = set(codes)

    noon = pd.read_csv(NOON_CSV)
    noon["code"] = noon["etf_code"].astype(str).str.split(".").str[0]
    noon["trade_date"] = noon["trade_date"].astype(str).str[:10]
    noon["friday_week_date"] = noon["friday_week_date"].astype(str).str[:10]
    noon = noon[noon["code"].isin(code_set)].copy()
    if "price_1430" in noon.columns and "price_1130" not in noon.columns:
        noon["price_1130"] = noon["price_1430"]

    face = pd.read_csv(FACE)
    face["date"] = face["date"].astype(str).str[:10]
    face = face[(face["date"] >= EVAL_START) & (face["date"] <= END_S)].copy()
    calendar = sorted(face["date"].unique().tolist())
    if not calendar:
        raise SystemExit("empty calendar")
    actual_end = calendar[-1]
    print(f"calendar {calendar[0]} → {actual_end} n={len(calendar)}", flush=True)

    breadth_b: dict[str, float] = {}
    for _, row in face.iterrows():
        d = str(row["date"])[:10]
        bv = row.get("b")
        if bv is not None and not (isinstance(bv, float) and math.isnan(bv)):
            breadth_b[d] = float(bv)

    risk_on_by_fri: dict[str, bool] = {}
    for d in calendar:
        b = breadth_b.get(d)
        risk_on_by_fri[d] = bool(b is not None and b >= BREADTH_THETA)
    risk_on_by_fri[calendar[-1]] = False
    print(
        f"B45 risk_on={sum(1 for d in calendar[:-1] if risk_on_by_fri.get(d))} / {len(calendar)-1}",
        flush=True,
    )

    raws_w: dict[str, dict[str, Any]] = {}
    closes_w_close: dict[str, dict[str, float]] = {}
    for c in codes:
        fp = WEEK / f"{c}.json"
        if not fp.exists():
            raws_w[c] = {"bars": []}
            closes_w_close[c] = {}
            continue
        rec = json.loads(fp.read_text(encoding="utf-8"))
        raws_w[c] = rec
        closes_w_close[c] = {
            b["date"]: float(b["c"])
            for b in (rec.get("bars") or [])
            if b.get("date") and b["date"] <= END_S and float(b["c"]) > 0
        }

    alias: dict[str, dict[str, str]] = {}
    for c in codes:
        ds = sorted(closes_w_close.get(c, {}))
        if not ds:
            continue
        alias[c] = {d: hit for d in calendar if (hit := nearest_date(d, ds, 3))}

    print("load sina + daily qfq for 14:30 map…", flush=True)
    sina = load_sina_closes(codes)
    print(f"sina daily: {len(sina)}/{len(codes)}", flush=True)
    daily = load_daily_closes(codes, sina)
    print(f"daily series: {len(daily)}/{len(codes)}", flush=True)

    noon_w: dict[str, dict[str, float]] = defaultdict(dict)
    blocked_empty: dict[str, set[str]] = defaultdict(set)
    n_map = n_skip = n_empty = 0
    for r in noon.itertuples():
        td = r.trade_date
        if td < EVAL_START or td > END_S:
            continue
        if r.status == "empty" or (
            r.status == "ok"
            and (r.price_1130 is None or (isinstance(r.price_1130, float) and math.isnan(r.price_1130)))
        ):
            blocked_empty[td].add(r.code)
            n_empty += 1
            continue
        if r.status != "ok":
            continue
        q = qfq_close_on(r.code, td, daily, closes_w_close)
        b = (sina.get(r.code) or {}).get(td)
        if not q or not b or b <= 0:
            n_skip += 1
            blocked_empty[td].add(r.code)
            continue
        qn = float(r.price_1130) * (q / b)
        noon_w[r.code][(alias.get(r.code) or {}).get(td) or td] = qn
        n_map += 1
    print(f"mapped qfq_1430={n_map} skip_no_bfq={n_skip} empty_block_rows={n_empty}", flush=True)

    listed = noon[noon["status"] != "not_listed"]
    listed = listed[(listed.trade_date >= EVAL_START) & (listed.trade_date <= END_S)]
    nonnull_rate = float(listed["price_1130"].notna().mean()) if len(listed) else 0.0
    cov_stats = {
        "px_1430_csv": str(NOON_CSV),
        "n_codes_aum2": len(codes),
        "n_calendar_weeks": len(calendar),
        "calendar_end": actual_end,
        "listed_1430_nonnull_rate": nonnull_rate,
        "n_qfq_1430_mapped": n_map,
        "n_skip_no_sina_or_qfq": n_skip,
        "n_empty_status_rows": n_empty,
        "approximation": [
            "延窗研究缓存：week/day 合并 recon week_2026-10-23 / day_2026-10-23；缺日线用 sina 收益链拼接（研究目录）",
            "14:30 新周（09-30/10-09/10-16/10-23）pytdx idx209 拉入 research_cache；旧周复用 fri_1430_through_20260925",
            "breadth b：extended face holdings_ro2_extended（≤2026-10-09 原 face + 其后研究周线 MA20 宽度假算 aum≥2）",
            "risk_on=(b≥0.45) from holdings_ro2_extended `b`（不用 risk_on 列）",
            "qfq_1430 = price_1430 × (day/tema qfq 收 / sina 收)；Sharpe 窗截至信号日前一交易日",
            "成交/净值：信号周末交易日收盘填仓 + TV25 + 0.2%RT；L≤1",
        ],
    }

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

    if not SNAP_CACHE.exists():
        raise SystemExit(f"missing 14:30 snap cache {SNAP_CACHE}")
    cached = json.loads(SNAP_CACHE.read_text(encoding="utf-8"))
    if cached.get("end") != actual_end:
        print(
            f"warn: snap cache end={cached.get('end')} calendar end={actual_end}; using cache anyway",
            flush=True,
        )
    print(f"load kit 1430 snaps from {SNAP_CACHE}", flush=True)
    by_rows = cached.get("by_code") or {}
    snaps = {c: snap_index(by_rows.get(c) or []) for c in codes}

    hold_by: dict[str, dict[str, list[str]]] = {}
    sim_stats: dict[str, Any] = {}
    entry_logs: dict[str, list[tuple[str, str, float, float | None, float | None]]] = {}
    for spec in BOOK_SPECS:
        name = spec["book"]
        print(f"simulate {spec['id']} {name}…", flush=True)
        kw = {
            "calendar": calendar,
            "snaps": snaps,
            "closes_w": closes_w_sig,
            "alias": alias,
            "aum": aum,
            "daily": daily,
            "risk_on_by_fri": risk_on_by_fri,
            "variant": name,
            "mode": spec["mode"],
            "max_pos": 5,
        }
        if spec["mode"] == "sharpe":
            kw["sharpe_n"] = 20
        else:
            kw["clenow_n"] = spec["n"]
            kw["clenow_k"] = spec["k"]
        trades, hold, st, elog = simulate(**kw)
        hold_by[name] = hold
        sim_stats[name] = st
        entry_logs[name] = elog
        rows = []
        for d in calendar[:-1]:
            codes_h = hold.get(d) or []
            rows.append(
                {
                    "date": d,
                    "risk_on": int(risk_on_by_fri.get(d, False)),
                    "n_held": len(codes_h),
                    "codes": ",".join(codes_h),
                }
            )
        pd.DataFrame(rows).to_csv(OUT / f"holdings_{spec['id']}.csv", index=False)
        pd.DataFrame(trades).to_csv(OUT / f"trades_{spec['id']}.csv", index=False)
        print(
            f"  entries={st['n_entries']} miss_clenow={st.get('n_miss_clenow', 0)} "
            f"cash_w={st['n_cash_weeks']}",
            flush=True,
        )

    all_codes: set[str] = set()
    for h in hold_by.values():
        for cs in h.values():
            all_codes |= set(cs)
    px_map = {}
    for c in sorted(all_codes):
        if c in daily:
            px_map[c] = daily[c]
        else:
            f = TEMA_PX / f"{c}.csv"
            if TEMA_PX.exists() and f.exists():
                df = pd.read_csv(f, parse_dates=["Date"])
                px_map[c] = df.set_index("Date")["Close"].astype(float).sort_index()
    px = pd.DataFrame(px_map).sort_index()
    px = px.loc[(px.index >= EVAL_START) & (px.index <= END_S)]
    R = px.pct_change()
    days = px.dropna(how="all").index
    days = days[(days >= EVAL_START) & (days <= END_S)]
    if len(days) and str(days[-1].date()) < actual_end:
        all_idx = None
        for s in daily.values():
            all_idx = s.index if all_idx is None else all_idx.union(s.index)
        if all_idx is not None:
            days2 = all_idx[(all_idx >= EVAL_START) & (all_idx <= END_S)]
            if len(days2) > len(days):
                days = days2
    print(f"live days {days[0].date()} → {days[-1].date()} n={len(days)}", flush=True)

    f0_entries = entry_set(entry_logs[BOOK_SPECS[0]["book"]])
    cells: list[dict[str, Any]] = []
    series: dict[str, pd.Series] = {}
    for spec in BOOK_SPECS:
        name = spec["book"]
        hd = {pd.Timestamp(d): cs for d, cs in hold_by[name].items()}
        r, L, avg_to = run_live_tv(hd, days, px, R)
        series[name] = r
        st = stats_full(r)
        r2022 = r[(r.index >= "2020-01-01") & (r.index <= "2022-12-31")]
        r2023 = r[r.index >= "2023-01-01"]
        st2022 = stats_full(r2022) if len(r2022) > 5 else {k: float("nan") for k in st}
        st2023 = stats_full(r2023) if len(r2023) > 5 else {k: float("nan") for k in st}
        hit, win_sz = entry_quality(entry_logs[name], calendar, closes_w_sig, alias)
        sim = sim_stats[name]
        elog = entry_logs[name]
        scores = [x[3] for x in elog if x[3] is not None]
        r2s = [x[4] for x in elog if x[4] is not None]
        cell = {
            "id": spec["id"],
            "book": name,
            "n": spec["n"],
            "k": spec["k"],
            "ret": st["ret"],
            "maxDD": st["maxDD"],
            "CAGR": st["CAGR"],
            "Calmar": st["Calmar"],
            "avgL": float(L[L > 0].mean()) if (L > 0).any() else 0.0,
            "avg_turnover_1way": avg_to,
            "n_cash_weeks": sim["n_cash_weeks"],
            "n_entries": sim["n_entries"],
            "n_miss_clenow": 0 if spec["id"] == "F0" else sim.get("n_miss_clenow", 0),
            "mean_r2": float(np.mean(r2s)) if r2s else 0.0,
            "mean_score": float(np.mean(scores)) if scores else 0.0,
            "mean_abs_D": sim.get("mean_abs_D", 0.0),
            "hit_rate": hit,
            "win_size": win_sz,
            "jaccard_vs_f0": jaccard_vs(entry_set(elog), f0_entries, spec["id"]),
            "w2020_22": {
                "ret": st2022["ret"],
                "maxDD": st2022["maxDD"],
                "Calmar": st2022["Calmar"],
            },
            "w2023_26": {
                "ret": st2023["ret"],
                "maxDD": st2023["maxDD"],
                "Calmar": st2023["Calmar"],
            },
        }
        cells.append(cell)
        print(
            f"  {spec['id']}: ret={pct(st['ret'])} dd={pct(st['maxDD'])} Calmar={st['Calmar']:.2f}",
            flush=True,
        )

    f0_cell = next(c for c in cells if c["id"] == "F0")
    anchor_pass = check_anchor(f0_cell, len(calendar), len(codes), actual_end)
    print(f"anchor_pass={anchor_pass} F0 ret={pct(f0_cell['ret'])} Calmar={f0_cell['Calmar']:.2f}", flush=True)

    for c in cells:
        if not anchor_pass:
            c["delta_ret"] = 0.0
            c["delta_abs_mdd"] = 0.0
            c["covers"] = False
            c["window_2020_22"] = False
            c["window_2023_26"] = False
            c["verdict"] = "BLOCKED"
        else:
            judge_vs_f0(c, f0_cell)

    positive_ids = [c["id"] for c in cells if c["verdict"] == "记正"]
    if not anchor_pass:
        family_verdict = "BLOCKED"
    elif positive_ids:
        family_verdict = "H1_REJECT"
    else:
        family_verdict = "H1_HOLD"

    table_cols = [
        "id",
        "book",
        "n",
        "k",
        "ret",
        "maxDD",
        "CAGR",
        "Calmar",
        "w2020_22_ret",
        "w2020_22_maxDD",
        "w2020_22_Calmar",
        "w2023_26_ret",
        "w2023_26_maxDD",
        "w2023_26_Calmar",
        "avgL",
        "avg_turnover_1way",
        "n_cash_weeks",
        "n_entries",
        "n_miss_clenow",
        "mean_r2",
        "mean_score",
        "mean_abs_D",
        "hit_rate",
        "win_size",
        "jaccard_vs_f0",
        "delta_ret",
        "delta_abs_mdd",
        "covers",
        "window_2020_22",
        "window_2023_26",
        "verdict",
    ]
    table_rows = []
    for c in cells:
        table_rows.append(
            {
                "id": c["id"],
                "book": c["book"],
                "n": c["n"],
                "k": c["k"],
                "ret": c["ret"],
                "maxDD": c["maxDD"],
                "CAGR": c["CAGR"],
                "Calmar": c["Calmar"],
                "w2020_22_ret": c["w2020_22"]["ret"],
                "w2020_22_maxDD": c["w2020_22"]["maxDD"],
                "w2020_22_Calmar": c["w2020_22"]["Calmar"],
                "w2023_26_ret": c["w2023_26"]["ret"],
                "w2023_26_maxDD": c["w2023_26"]["maxDD"],
                "w2023_26_Calmar": c["w2023_26"]["Calmar"],
                "avgL": c["avgL"],
                "avg_turnover_1way": c["avg_turnover_1way"],
                "n_cash_weeks": c["n_cash_weeks"],
                "n_entries": c["n_entries"],
                "n_miss_clenow": c["n_miss_clenow"],
                "mean_r2": c["mean_r2"],
                "mean_score": c["mean_score"],
                "mean_abs_D": c["mean_abs_D"],
                "hit_rate": c["hit_rate"],
                "win_size": c["win_size"],
                "jaccard_vs_f0": c["jaccard_vs_f0"],
                "delta_ret": c["delta_ret"],
                "delta_abs_mdd": c["delta_abs_mdd"],
                "covers": c["covers"],
                "window_2020_22": c["window_2020_22"],
                "window_2023_26": c["window_2023_26"],
                "verdict": c["verdict"],
            }
        )
    pd.DataFrame(table_rows, columns=table_cols).to_csv(OUT / "table.csv", index=False)

    eq_long = []
    for spec in BOOK_SPECS:
        name = spec["book"]
        nav = (1 + series[name]).cumprod()
        for dt, nv in nav.items():
            eq_long.append({"date": dt.strftime("%Y-%m-%d"), "book": name, "nav": float(nv)})
    pd.DataFrame(eq_long).to_csv(OUT / "equity.csv", index=False)

    fig, ax = plt.subplots(figsize=(11, 5.5), dpi=120)
    f0_name = BOOK_SPECS[0]["book"]
    nav_f0 = (1 + series[f0_name]).cumprod()
    ax.plot(nav_f0.index, nav_f0.values, color="black", lw=2.2, label="F0")
    for spec in BOOK_SPECS[1:]:
        nav = (1 + series[spec["book"]]).cumprod()
        ax.plot(nav.index, nav.values, color="gray", lw=1.0, alpha=0.85, label=spec["id"])
    ax.set_yscale("log")
    ax.set_title("clenow-slope-r2-fill（F0 黑线 vs Clenow 斜率邻档）")
    ax.set_ylabel("净值（对数）")
    ax.grid(True, alpha=0.3)
    ax.legend(fontsize=8)
    fig.tight_layout()
    fig.savefig(OUT / "equity_curve.png")
    plt.close(fig)

    h1_text = (
        "唯一改动：在面层 B45 + spike_ft max5 + E0 + TV25 上，\n"
        "把填席键从 SHARPE20 换成 Clenow 对数价格回归年化斜率 × R²。\n"
        "  主簿 SR90：N=90，score = (e^{β·252} − 1) × R²。\n"
        "  邻档：SR60（N=60）、SR90K2（N=90，× R²²）。共 4 本（含 F0）。\n"
        "  已持仓不因 score 变负而平。出场维持 E0。\n"
        "  B、TV、席位、成本、时钟不离开面。\n"
        "  不叠加速度闸，不叠 ER/R² 地板，不用 510300。\n\n"
        "H1：SR90 / SR60 / SR90K2 在严格尺子下相对本次 F0 全部证伪。\n"
        "  任一记正 → H1 证伪（家族记一笔，不换冠）。\n"
        "  全部证伪 → H1 成立。"
    )

    h1_hold = all(c["verdict"] == "证伪" for c in cells if c["id"] != "F0")
    summary = {
        "batch": "clenow-slope-r2-fill",
        "knife_id": "CLENOW-SLOPE-R2-FILL",
        "champion_swap": False,
        "crown": "NO",
        "source_sha": SOURCE_SHA,
        "sample": [EVAL_START, actual_end],
        "anchor_pass": anchor_pass,
        "anchor": {**ANCHOR, "n_weeks": len(calendar), "T": len(calendar) - 1},
        "face_id": "F0",
        "primary": "SR90",
        "clenow": "score=(exp(beta*252)-1)*(R2**k); N=90 k=1 primary",
        "h1": "SR90/SR60/SR90K2 all 证伪" if h1_hold else "H1_REJECT",
        "family_verdict": family_verdict,
        "positive_ids": positive_ids,
        "skipped_fills": SKIPPED_FILLS,
        "cells": cells,
        "coverage": cov_stats,
        "elapsed_sec": round(time.time() - t0, 1),
    }
    (OUT / "summary.json").write_text(
        json.dumps(summary, ensure_ascii=False, indent=2, default=str), encoding="utf-8"
    )

    def tbl_row(c: dict[str, Any]) -> str:
        return (
            f"| {c['id']} | {c['book']} | {c['n']} | {c['k']} | {pct(c['ret'])} | {pct(c['maxDD'])} | "
            f"{pct(c['CAGR'])} | {c['Calmar']:.2f} | "
            f"{pct(c['w2020_22']['ret'])}/{pct(c['w2020_22']['maxDD'])}/{c['w2020_22']['Calmar']:.2f} | "
            f"{pct(c['w2023_26']['ret'])}/{pct(c['w2023_26']['maxDD'])}/{c['w2023_26']['Calmar']:.2f} | "
            f"{c['avgL']:.2f} | {c['avg_turnover_1way']:.3f} | {c['n_cash_weeks']} | {c['n_entries']} | "
            f"{c['n_miss_clenow']} | {c['mean_r2']:.3f} | {c['mean_score']:.3f} | {c['mean_abs_D']:.1f} | "
            f"{c['hit_rate']:.2%} | {c['win_size']:.2f} | {c['jaccard_vs_f0']:.3f} | {c['verdict']} |"
        )

    anchor_line = (
        f"锚点门：F0 ret={pct(f0_cell['ret'])} maxDD={pct(f0_cell['maxDD'])} Calmar={f0_cell['Calmar']:.2f} "
        f"（目标 131.6% / −18.8% / 0.70）→ {'通过' if anchor_pass else '未通过 BLOCKED'}。"
    )
    if not anchor_pass:
        verdict_line = (
            f"**BLOCKED（不换冠）**：F0 未贴上 btheta 锚（实际 ret={pct(f0_cell['ret'])} "
            f"maxDD={pct(f0_cell['maxDD'])} Calmar={f0_cell['Calmar']:.2f}）；家族结论 BLOCKED。"
        )
    elif family_verdict == "H1_HOLD":
        verdict_line = "**H1 成立（不换冠）**：三本 Clenow 斜率相对本次 F0 均为证伪，斜率×R² 填席无记正。"
    else:
        verdict_line = f"**H1 证伪（不换冠）**：记正格 {', '.join(positive_ids)}。"

    falsify_lines = []
    for c in cells:
        if c["id"] == "F0":
            continue
        if c["verdict"] == "记正":
            falsify_lines.append(f"- {c['id']}：记正（Δret={100*c['delta_ret']:.1f}pp 盖住 Δ|MDD|={100*c['delta_abs_mdd']:.1f}pp；两窗过）")
        else:
            reasons = []
            if not c["covers"]:
                reasons.append("未盖住")
            if not c["window_2020_22"]:
                reasons.append("2020–22 踏空")
            if not c["window_2023_26"]:
                reasons.append("2023–26 踏空")
            falsify_lines.append(f"- {c['id']}：证伪（{'；'.join(reasons) or '缺失'}）")

    f0_cash = f0_cell["n_cash_weeks"]
    f0_to = f0_cell["avg_turnover_1way"]
    attrib_lines = []
    for c in cells:
        if c["id"] == "F0":
            continue
        attrib_lines.append(
            f"- {c['id']}：Jaccard={c['jaccard_vs_f0']:.3f}；Δret={100*c['delta_ret']:+.1f}pp；"
            f"2020–22 {'过' if c['window_2020_22'] else '踏空'}；2023–26 {'过' if c['window_2023_26'] else '踏空'}；"
            f"换手 {c['avg_turnover_1way']:.3f} vs F0 {f0_to:.3f}；空仓周 {c['n_cash_weeks']} vs F0 {f0_cash}"
        )

    report = f"""请拍板：在面层 B45 + spike_ft max5 + E0 + TV25、LIVE≥14:30 面上，只改填席键：SHARPE20 → Clenow 对数价格回归年化斜率 × R²。主口径冻结为 N=90 根交易日、score = (e^{{β·252}} − 1) × R²（小数单位，不含 ×100）。取 top max5 腿内等权。无论记正与否都不换冠。

```
{h1_text}
```

## 1. 准则原文（摘要）

- 面：B45 + spike_ft max5 + E0 + TV25；研究池 AUM≥2（{len(codes)} 只）；窗 {EVAL_START}→{actual_end}（{len(calendar)} 信号周，T={len(calendar)-1}）。
- 主簿 SR90：`score = (exp(β·252)−1)×R²`，N=90；邻档 SR60、SR90K2；F0=SHARPE20。
- 尺子：记正 = Δret≥Δ|MDD| 且 2020–22、2023–26 窗 ret 均 ≥ F0 同窗。
- 跳过：{", ".join(SKIPPED_FILLS)}；不换冠。

## 2. 实现要点

- 引擎 fork：`{SOURCE_SHA}`（SPIKE-S20-BTHETA-GRID-LIVE1430）；kit `CLOUD-BATCH-2026-10-26`。
- `clenow_score_on` 窗截至信号日前一交易日；`risk_on = (b ≥ 0.45)`。
- {anchor_line}

## 3. 主表

| id | book | n | k | ret | maxDD | CAGR | Calmar | 2020–22 | 2023–26 | avgL | TO1w | cash周 | n_ent | miss | mean_r2 | mean_score | mean|D| | hit% | win_sz | Jaccard | verdict |
|---|---|---:|---:|---:|---:|---:|---:|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---|
{chr(10).join(tbl_row(c) for c in cells)}

### Δ（相对本次 F0）

| id | Δret pp | Δ|MDD| pp | 盖住 | 2020–22 | 2023–26 |
|---|---:|---:|:---:|:---:|:---:|
"""
    for c in cells:
        if c["id"] == "F0":
            continue
        report += (
            f"| {c['id']} | {100*c['delta_ret']:+.1f} | {100*c['delta_abs_mdd']:+.1f} | "
            f"{'Y' if c['covers'] else 'N'} | {'Y' if c['window_2020_22'] else 'N'} | "
            f"{'Y' if c['window_2023_26'] else 'N'} |\n"
        )

    report += f"""
### 填席质量旁注

- F0 `n_miss_clenow`=0；斜率书见 `mean_r2` / `mean_score` / `n_miss_clenow`（仅披露，不翻转旗标）

## ATTRIBUTION

1. 机制：只换填席键；B45 / spike_ft / max5 / E0 / TV25 / Fri≥14:30 / 0.2%RT / AUM≥2 未动。
2. 席位：SR90 Jaccard={next(c['jaccard_vs_f0'] for c in cells if c['id']=='SR90'):.3f}；SR60={next(c['jaccard_vs_f0'] for c in cells if c['id']=='SR60'):.3f}；SR90K2={next(c['jaccard_vs_f0'] for c in cells if c['id']=='SR90K2'):.3f}。
3. 分段：见 Δ 表与各格 2020–22 / 2023–26 是否踏空。
4. 换手与空仓周相对 F0：{chr(10).join(attrib_lines)}
ATTRIBUTION 不进 verdict。

## 4. 证伪段与一句判词

{chr(10).join(falsify_lines)}

{verdict_line}

## 红线

不写 strategy_exec / LIVE_OPS / champion_mast；不换冠。

source_sha={SOURCE_SHA}；family_verdict={family_verdict}；耗时 {summary['elapsed_sec']}s。
"""
    (OUT / "REPORT.md").write_text(report, encoding="utf-8")
    print("done", OUT, flush=True)
    print(verdict_line, flush=True)


if __name__ == "__main__":
    main()
