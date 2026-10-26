#!/usr/bin/env python3
"""skip-month-csmom: B45 spike_ft max5 + E0 + TV25; F0 SHARPE20 vs skip-month CSMOM seat fill.

Five books: F0 + CSM12-S4/S2/S8 + CSM26-S4. Engine fork pin 05f0f8a4.
Research pool only — no crown swap.
"""
from __future__ import annotations

import json
import math
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

BOOK_SPECS = [
    {"id": "F0", "book": "LIVE1430-B45-S20-max5", "mode": "sharpe", "lookback": "S20", "skip": "off"},
    {
        "id": "CSM12-S4",
        "book": "LIVE1430-B45-CSM12S4-max5",
        "mode": "csmom",
        "lookback": "R52w",
        "skip": "S4w",
        "long_cal": 364,
        "skip_cal": 28,
        "min_long": 160,
        "min_skip": 15,
    },
    {
        "id": "CSM12-S2",
        "book": "LIVE1430-B45-CSM12S2-max5",
        "mode": "csmom",
        "lookback": "R52w",
        "skip": "S2w",
        "long_cal": 364,
        "skip_cal": 14,
        "min_long": 160,
        "min_skip": 8,
    },
    {
        "id": "CSM12-S8",
        "book": "LIVE1430-B45-CSM12S8-max5",
        "mode": "csmom",
        "lookback": "R52w",
        "skip": "S8w",
        "long_cal": 364,
        "skip_cal": 56,
        "min_long": 160,
        "min_skip": 28,
    },
    {
        "id": "CSM26-S4",
        "book": "LIVE1430-B45-CSM26S4-max5",
        "mode": "csmom",
        "lookback": "R26w",
        "skip": "S4w",
        "long_cal": 182,
        "skip_cal": 28,
        "min_long": 80,
        "min_skip": 15,
    },
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
    skip_mom: float | None = None


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


def csmom_key(c: Cand, pool: list[Cand]) -> tuple:
    miss = 0 if c.skip_mom is not None else 1
    return (miss, -(c.skip_mom if c.skip_mom is not None else 0.0), c.code)


def skip_mom_score(
    closes: pd.Series,
    d: str,
    long_cal: int,
    skip_cal: int,
    min_long: int,
    min_skip: int,
) -> float | None:
    r_long = lookback_ret(closes, d, long_cal, min_long)
    r_skip = lookback_ret(closes, d, skip_cal, min_skip)
    if r_long is None or r_skip is None:
        return None
    if (not np.isfinite(r_skip)) or r_skip <= -1.0:
        return None
    return (1.0 + r_long) / (1.0 + r_skip) - 1.0


def lookback_ret(closes: pd.Series, d: str, cal_days: int, min_bars: int) -> float | None:
    ts = pd.Timestamp(d)
    sub = closes.loc[: ts - pd.Timedelta(days=1)]
    if len(sub) < 2:
        return None
    if (ts - sub.index[-1]).days > 5:
        return None
    p1 = float(sub.iloc[-1])
    t0 = sub.index[-1] - pd.Timedelta(days=cal_days)
    past = sub.loc[:t0]
    if len(past) == 0:
        return None
    if (t0 - past.index[-1]).days > 5:
        return None
    p0 = float(past.iloc[-1])
    n_bars = int(sub.loc[past.index[-1] : sub.index[-1]].shape[0])
    if n_bars < min_bars or p0 <= 0 or not np.isfinite(p0) or not np.isfinite(p1):
        return None
    return p1 / p0 - 1.0


def run_fixtures() -> None:
    p_now, p_skip, p_long = 110.0, 100.0, 80.0
    r52 = p_now / p_long - 1.0
    r4 = p_now / p_skip - 1.0
    compound = (1.0 + r52) / (1.0 + r4) - 1.0
    price_ratio = p_skip / p_long - 1.0
    assert abs(compound - 0.25) < 1e-12 and abs(price_ratio - 0.25) < 1e-12

    def sm_from_rs(r_long: float, r_skip: float) -> float:
        return (1.0 + r_long) / (1.0 + r_skip) - 1.0

    assert abs(sm_from_rs(0.50, 0.50) - 0.0) < 1e-12
    assert abs(sm_from_rs(0.40, 0.00) - 0.40) < 1e-12
    assert abs((0.50 - 0.20) - (0.40 - 0.10)) < 1e-12
    assert sm_from_rs(0.40, 0.10) > sm_from_rs(0.50, 0.20)
    assert skip_mom_score(pd.Series([1.0], index=[pd.Timestamp("2024-01-02")]), "2024-01-10", 364, 28, 1, 1) is None

    idx = pd.date_range("2024-01-02", periods=10, freq="B")
    ser = pd.Series(np.linspace(1.0, 1.1, len(idx)), index=idx)
    gap_d = (idx[-1] + pd.Timedelta(days=10)).strftime("%Y-%m-%d")
    assert lookback_ret(ser, gap_d, 84, 40) is None


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
    long_cal: int | None = None,
    skip_cal: int | None = None,
    min_long: int | None = None,
    min_skip: int | None = None,
) -> tuple[list[dict[str, Any]], dict[str, list[str]], dict[str, Any], list[tuple[str, str, float]]]:
    cash = 1.0
    positions: dict[str, Position] = {}
    trades: list[dict[str, Any]] = []
    picks: dict[str, list[str]] = {}
    n_tight = 0
    n_feat = 0
    n_entries = 0
    n_miss_sharpe = 0
    n_miss_csmom = 0
    abs_d_sizes: list[int] = []
    entry_log: list[tuple[str, str, float]] = []
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
        if not last_bar and risk_on:
            csmom_map: dict[str, float] = {}
            if mode == "csmom":
                if long_cal is None or skip_cal is None or min_long is None or min_skip is None:
                    raise SystemExit("csmom mode needs long_cal/skip_cal/min_long/min_skip")
                for code in snaps:
                    sn = snap_at(code, d)
                    if not is_spike(sn):
                        continue
                    px = px_on(code, d)
                    if px is None or px <= 0:
                        continue
                    if code not in daily:
                        n_miss_csmom += 1
                        continue
                    sm = skip_mom_score(daily[code], d, long_cal, skip_cal, min_long, min_skip)
                    if sm is None:
                        n_miss_csmom += 1
                    else:
                        csmom_map[code] = float(sm)
                if len(csmom_map) >= 1:
                    abs_d_sizes.append(len(csmom_map))

            pool = build_cands(d, set(positions))
            if mode == "csmom":
                for c in pool:
                    c.skip_mom = csmom_map.get(c.code)

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
                        entry_log.append((d, c.code, c.px))
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
                    pool_rank = [c for c in pool if c.skip_mom is not None]
                    take = sorted(pool_rank, key=lambda c: csmom_key(c, pool_rank))[:slots]
                    for c in take:
                        n_entries += 1
                        entry_log.append((d, c.code, c.px))
                        rank_rows.append(
                            {
                                "date": d,
                                "variant": variant,
                                "code": c.code,
                                "aum": c.aum,
                                "skip_mom": c.skip_mom,
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
        "n_miss_csmom": n_miss_csmom,
        "n_skip_fallback_blocked": 0,
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
    for ent_d, code, px0 in entry_log:
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
    if (n_weeks - 1) != ANCHOR["T"]:
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
    entry_logs: dict[str, list[tuple[str, str, float]]] = {}
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
            kw["long_cal"] = spec["long_cal"]
            kw["skip_cal"] = spec["skip_cal"]
            kw["min_long"] = spec["min_long"]
            kw["min_skip"] = spec["min_skip"]
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
            f"  entries={st['n_entries']} miss_csmom={st.get('n_miss_csmom', 0)} "
            f"mean|D|={st.get('mean_abs_D', 0):.1f} cash_w={st['n_cash_weeks']}",
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
        cell = {
            "id": spec["id"],
            "book": name,
            "lookback": spec["lookback"],
            "skip": spec["skip"],
            "ret": st["ret"],
            "maxDD": st["maxDD"],
            "CAGR": st["CAGR"],
            "Calmar": st["Calmar"],
            "avgL": float(L[L > 0].mean()) if (L > 0).any() else 0.0,
            "avg_turnover_1way": avg_to,
            "n_cash_weeks": sim["n_cash_weeks"],
            "n_entries": sim["n_entries"],
            "n_miss_csmom": 0 if spec["id"] == "F0" else sim.get("n_miss_csmom", 0),
            "n_skip_fallback_blocked": sim.get("n_skip_fallback_blocked", 0),
            "mean_abs_D": sim.get("mean_abs_D", 0.0),
            "hit_rate": hit,
            "win_size": win_sz,
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

    table_rows = []
    for c in cells:
        table_rows.append(
            {
                "id": c["id"],
                "book": c["book"],
                "lookback": c["lookback"],
                "skip": c["skip"],
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
                "n_miss_csmom": c["n_miss_csmom"],
                "n_skip_fallback_blocked": c["n_skip_fallback_blocked"],
                "mean_abs_D": c["mean_abs_D"],
                "hit_rate": c["hit_rate"],
                "win_size": c["win_size"],
                "delta_ret": c["delta_ret"],
                "delta_abs_mdd": c["delta_abs_mdd"],
                "covers": c["covers"],
                "window_2020_22": c["window_2020_22"],
                "window_2023_26": c["window_2023_26"],
                "verdict": c["verdict"],
            }
        )
    pd.DataFrame(table_rows).to_csv(OUT / "table.csv", index=False)

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
    ax.set_title("skip-month-csmom（F0 黑线 vs 跳月邻档）")
    ax.set_ylabel("净值（对数）")
    ax.grid(True, alpha=0.3)
    ax.legend(fontsize=8)
    fig.tight_layout()
    fig.savefig(OUT / "equity_curve.png")
    plt.close(fig)

    design_md = Path(__file__).resolve().parent / "DESIGN.md"
    h1_block = (
        "唯一改动：在面层 B45 + spike_ft max5 + E0 + TV25 上，\n"
        "把填席键从 SHARPE20 换成跳月截面动量。\n"
        "  主簿 CSM12-S4：skip_mom = P_{t−4w} / P_{t−52w} − 1\n"
        "                （≡ (1+R52w)/(1+R4w) − 1）。\n"
        "  邻档：CSM12-S2、CSM12-S8、CSM26-S4。共 5 本（含 F0）。\n"
        "  已持仓不因 skip_mom 变负而平。出场维持 E0。\n"
        "  B、TV、席位、成本、时钟不离开面。\n\n"
        "H1：CSM12-S4 / CSM12-S2 / CSM12-S8 / CSM26-S4\n"
        "  在严格尺子下相对本次 F0 全部证伪。\n"
        "  任一记正 → H1 证伪（家族记一笔，不换冠）。\n"
        "  全部证伪 → H1 成立。"
    )
    if design_md.exists():
        txt = design_md.read_text(encoding="utf-8")
        start = txt.find("```\n唯一改动")
        if start >= 0:
            start += 4
            end = txt.find("\n```", start)
            if end > start:
                h1_block = txt[start:end].strip()

    summary = {
        "batch": "skip-month-csmom",
        "champion_swap": False,
        "crown": "NO",
        "source_sha": SOURCE_SHA,
        "sample": [EVAL_START, actual_end],
        "anchor_pass": anchor_pass,
        "anchor": {**ANCHOR, "n_weeks": len(calendar), "T": len(calendar) - 1},
        "face_id": "F0",
        "primary": "CSM12-S4",
        "csmom": "P(t-4w)/P(t-52w)-1 == (1+R52w)/(1+R4w)-1",
        "h1": "CSM12-S4/CSM12-S2/CSM12-S8/CSM26-S4 all 证伪",
        "family_verdict": family_verdict,
        "positive_ids": positive_ids,
        "skipped_fills": [
            "RET8",
            "RET12",
            "MOM121",
            "SOFT",
            "Z121",
            "R4W",
            "residual-mom",
            "corr-dedup",
        ],
        "cells": cells,
        "coverage": cov_stats,
        "elapsed_sec": round(time.time() - t0, 1),
    }
    (OUT / "summary.json").write_text(
        json.dumps(summary, ensure_ascii=False, indent=2, default=str), encoding="utf-8"
    )

    def tbl_row(c: dict[str, Any]) -> str:
        return (
            f"| {c['id']} | {c['book']} | {pct(c['ret'])} | {pct(c['maxDD'])} | {pct(c['CAGR'])} | "
            f"{c['Calmar']:.2f} | {pct(c['w2020_22']['ret'])}/{pct(c['w2020_22']['maxDD'])}/{c['w2020_22']['Calmar']:.2f} | "
            f"{pct(c['w2023_26']['ret'])}/{pct(c['w2023_26']['maxDD'])}/{c['w2023_26']['Calmar']:.2f} | "
            f"{c['avgL']:.2f} | {c['avg_turnover_1way']:.3f} | {c['n_cash_weeks']} | {c['n_entries']} | "
            f"{c['n_miss_csmom']} | {c['mean_abs_D']:.1f} | {c['hit_rate']:.2%} | "
            f"{c['win_size']:.2f} | {c['verdict']} |"
        )

    anchor_line = (
        f"锚点门：F0 ret={pct(f0_cell['ret'])} maxDD={pct(f0_cell['maxDD'])} Calmar={f0_cell['Calmar']:.2f} "
        f"（目标 131.6% / −18.8% / 0.70）→ {'通过' if anchor_pass else '未通过 BLOCKED'}。"
    )
    if not anchor_pass:
        verdict_line = "**BLOCKED（不换冠）**：F0 未贴上 btheta 锚；家族结论 BLOCKED，不解读跳月格。"
    elif family_verdict == "H1_HOLD":
        verdict_line = "**H1 成立（不换冠）**：四本跳月相对本次 F0 均为证伪，跳月 CSMOM 填席无记正。"
    else:
        verdict_line = f"**H1 证伪（不换冠）**：记正格 {', '.join(positive_ids)}。"

    falsify_lines = []
    for c in cells:
        if c["id"] == "F0":
            continue
        if c["verdict"] == "记正":
            falsify_lines.append(
                f"- {c['id']}：记正（Δret={100*c['delta_ret']:.1f}pp 盖住 Δ|MDD|={100*c['delta_abs_mdd']:.1f}pp；两窗过）"
            )
        else:
            reasons = []
            if not c["covers"]:
                reasons.append("未盖住")
            if not c["window_2020_22"]:
                reasons.append("2020–22 踏空")
            if not c["window_2023_26"]:
                reasons.append("2023–26 踏空")
            falsify_lines.append(f"- {c['id']}：证伪（{'；'.join(reasons) or '缺失'}）")

    report_head = (
        "请拍板：在面层 B45 + spike_ft max5 + E0 + TV25、LIVE≥14:30 面上，只改填席键："
        "SHARPE20 → 跳月截面动量。主口径冻结为 R11m、截止 t−4w（价格比 P_{t−4w}/P_{t−52w}−1；"
        "与复利 (1+R52w)/(1+R4w)−1 恒等）。取 top max5 腿内等权。无论记正与否都不换冠。"
    )
    report = f"""{report_head}

```
{h1_block}
```

## 1. 准则原文（摘要）

- 面：B45 + spike_ft max5 + E0 + TV25；研究池 AUM≥2（{len(codes)} 只）；窗 {EVAL_START}→{actual_end}（{len(calendar)} 信号周，T={len(calendar)-1}）。
- 主簿 CSM12-S4：skip_mom = P_{{t−4w}}/P_{{t−52w}}−1；邻档 CSM12-S2/S8、CSM26-S4；F0=SHARPE20。
- 尺子：记正 = Δret≥Δ|MDD| 且 2020–22、2023–26 窗 ret 均 ≥ F0 同窗。
- 跳过：RET8/12、MOM121、Z121、R4W、SOFT、residual-mom、corr-dedup；不换冠。

## 2. 实现要点

- 引擎 fork：`{SOURCE_SHA[:12]}`；kit CLOUD-BATCH-2026-10-26。
- {anchor_line}

## 3. 主表

| id | book | ret | maxDD | CAGR | Calmar | 2020–22 | 2023–26 | avgL | TO1w | cash周 | n_ent | miss_csmom | mean|D| | hit% | win_sz | verdict |
|---|---|---:|---:|---:|---:|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---|
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

- F0 hit_rate={f0_cell['hit_rate']:.2%} win_size={f0_cell['win_size']:.2f}（仅披露，不翻转旗标）

## 4. 证伪段与一句判词

{chr(10).join(falsify_lines)}

{verdict_line}

source_sha={SOURCE_SHA}；family_verdict={family_verdict}；耗时 {summary['elapsed_sec']}s。
"""
    (OUT / "REPORT.md").write_text(report, encoding="utf-8")
    print("done", OUT, flush=True)
    print(verdict_line, flush=True)


if __name__ == "__main__":
    main()
