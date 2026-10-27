#!/usr/bin/env python3
"""residual-mom-fill: B45 spike_ft max5 + E0 + TV25; F0 SHARPE20 vs residual seat fill.

Four books: F0 (S20), RES12-EW, RES8-EW, RES12-MED. Engine fork pin 05f0f8a4 (btheta LIVE1430).
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

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
from band import ols_clenow, pick as seat_pick, take_band  # noqa: E402

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
    {"id": "F0", "book": "LIVE1430-B45-S20-max5", "mode": "off", "n": 0, "miss_n": 0},
    {"id": "CS90S", "book": "LIVE1430-B45-S20-CS90S-max5", "mode": "clenow_sort", "n": 90, "miss_n": 90},
    {"id": "CS60S", "book": "LIVE1430-B45-S20-CS60S-max5", "mode": "clenow_sort", "n": 60, "miss_n": 60},
    {"id": "CS90R", "book": "LIVE1430-B45-S20-CS90R-max5", "mode": "slope_ann_sort", "n": 90, "miss_n": 90},
]

EVAL_START = "2020-01-03"
END_S = "2026-10-23"
COST_SIDE = 0.001
SIGMA_STAR = 0.25
LCAP = 1.0
LIVE_COST_RT = 0.002
CLASSIFY_WORKERS = 8

TABLE_COLS = [
    "id", "book", "mode", "n", "ret", "maxDD", "CAGR", "Calmar",
    "w2020_22_ret", "w2020_22_maxDD", "w2020_22_Calmar",
    "w2023_26_ret", "w2023_26_maxDD", "w2023_26_Calmar",
    "avgL", "avg_turnover_1way", "n_cash_weeks", "n_entries", "n_rerank",
    "n_miss_clenow", "n_empty_slots", "n_short_fills", "n_fallback_weeks",
    "mean_score", "mean_slope_ann", "mean_r2", "mean_abs_D", "hit_rate", "win_size",
    "jaccard_vs_f0", "inert", "delta_ret", "delta_abs_mdd", "covers",
    "window_2020_22", "window_2023_26", "verdict",
]


@dataclass
class Cand:
    code: str
    px: float
    fz: float | None
    aum: float
    sharpe: float | None = None
    score: float | None = None
    slope_ann: float | None = None
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


def clenow_on_series(closes: pd.Series, d: str, n: int) -> dict | None:
    ts = pd.Timestamp(d)
    sub = closes.loc[: ts - pd.Timedelta(days=1)]
    if len(sub) < n:
        return None
    if (ts - pd.Timestamp(sub.index[-1])).days > 5:
        return None
    window = sub.iloc[-n:]
    if len(window) < n:
        return None
    return ols_clenow(window.to_numpy(dtype=float))


def attach_clenow(c: Cand, daily: dict[str, pd.Series], d: str, n: int) -> None:
    if n < 2 or c.code not in daily:
        return
    got = clenow_on_series(daily[c.code], d, n)
    if got:
        c.score = got["score"]
        c.slope_ann = got["slope_ann"]
        c.r2 = got["r2"]


def run_fixtures() -> None:
    import unittest

    loader = unittest.TestLoader()
    suite = loader.discover(str(HERE), pattern="test_band.py")
    result = unittest.TextTestRunner(verbosity=0).run(suite)
    if not result.wasSuccessful():
        raise SystemExit("test_band.py fixtures failed")


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
    clenow_n: int,
    miss_n: int,
    max_pos: int,
    sharpe_n: int = 20,
) -> tuple[list[dict[str, Any]], dict[str, list[str]], dict[str, Any], list[tuple[str, str, float]]]:
    cash = 1.0
    positions: dict[str, Position] = {}
    trades: list[dict[str, Any]] = []
    picks: dict[str, list[str]] = {}
    n_tight = 0
    n_feat = 0
    n_entries = 0
    n_miss_sharpe = 0
    n_miss_clenow = 0
    n_rerank = 0
    n_empty_slots = 0
    n_short_fills = 0
    n_fallback_weeks = 0
    abs_d_sizes: list[int] = []
    entry_log: list[tuple[str, str, float, float | None, float | None, float | None]] = []
    score_vals: list[float] = []
    slope_vals: list[float] = []
    r2_vals: list[float] = []
    from band import Cand as BCand

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
        how = "empty"
        if not last_bar and risk_on:
            pool = build_cands(d, set(positions))
            pool_rank = [c for c in pool if c.sharpe is not None]
            pool_rank.sort(key=lambda c: sharpe_key(c, pool_rank))
            if risk_on and len(pool_rank) >= 1:
                abs_d_sizes.append(len(pool_rank))

            if mode != "off" and miss_n >= 2:
                for c in pool_rank:
                    if c.code not in daily or clenow_on_series(daily[c.code], d, miss_n) is None:
                        n_miss_clenow += 1

            slots = max_pos - len(positions)
            if pool:
                n_feat += 1
            if slots > 0 and len(pool_rank) > slots:
                n_tight += 1
            if slots > 0 and pool_rank:
                if mode == "off":
                    take = pool_rank[:slots]
                    how = "sorted"
                else:
                    band_list = take_band(pool_rank, slots)
                    for c in band_list:
                        attach_clenow(c, daily, d, clenow_n)
                    band_c = [
                        BCand(c.code, score=c.score, slope_ann=c.slope_ann) for c in band_list
                    ]
                    picked, how = seat_pick(band_c, slots, mode)
                    by_code = {c.code: c for c in band_list}
                    take = [by_code[p.code] for p in picked]
                    expect = min(slots, len(band_list))
                    if len(take) < expect:
                        n_short_fills += 1
                    if how == "fallback":
                        n_fallback_weeks += 1
                    s20_top = {c.code for c in pool_rank[:slots]}
                    for c in take:
                        if c.code not in s20_top:
                            n_rerank += 1
                n_empty_slots += max(0, slots - len(take))
                for c in take:
                    n_entries += 1
                    entry_log.append((d, c.code, c.px, c.score, c.slope_ann, c.r2))
                    if c.sharpe is None:
                        n_miss_sharpe += 1
                    sort_key = c.slope_ann if mode == "slope_ann_sort" else c.score
                    if sort_key is not None and math.isfinite(sort_key):
                        score_vals.append(float(sort_key))
                    if c.slope_ann is not None and math.isfinite(c.slope_ann):
                        slope_vals.append(float(c.slope_ann))
                    if c.r2 is not None and math.isfinite(c.r2):
                        r2_vals.append(float(c.r2))

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

    n_cash = sum(1 for d in calendar[:-1] if not (hold.get(d) or []))
    stats = {
        "n_fridays_queue_gt_seats": n_tight,
        "n_fridays_with_cands": n_feat,
        "n_entries": n_entries,
        "n_entries_missing_sharpe": n_miss_sharpe,
        "n_miss_clenow": n_miss_clenow,
        "n_rerank": n_rerank,
        "n_empty_slots": n_empty_slots,
        "n_short_fills": n_short_fills,
        "n_fallback_weeks": n_fallback_weeks,
        "mean_score": float(np.mean(score_vals)) if score_vals else 0.0,
        "mean_slope_ann": float(np.mean(slope_vals)) if slope_vals else 0.0,
        "mean_r2": float(np.mean(r2_vals)) if r2_vals else 0.0,
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
    elog_simple = [(a, b, c) for a, b, c, *_ in entry_log]
    return trades, hold, stats, elog_simple


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
    if n_codes != ANCHOR["n_codes"]:
        return False
    if abs(st["ret"] - ANCHOR["ret"]) > ANCH_TOL["ret"]:
        return False
    if abs(st["maxDD"] - ANCHOR["maxDD"]) > ANCH_TOL["maxDD"]:
        return False
    if abs(st["Calmar"] - ANCHOR["Calmar"]) > ANCH_TOL["Calmar"]:
        return False
    return True


def weekly_hold_sets(hold: dict[str, list[str]], calendar: list[str]) -> list[tuple[str, frozenset]]:
    return [(d, frozenset(hold.get(d) or [])) for d in calendar[:-1]]


def holdings_inert(hold_a: dict[str, list[str]], hold_b: dict[str, list[str]], calendar: list[str]) -> bool:
    return weekly_hold_sets(hold_a, calendar) == weekly_hold_sets(hold_b, calendar)


def entry_set(entry_log: list[tuple[str, str, float]]) -> set[tuple[str, str]]:
    return {(d, c) for d, c, *_ in entry_log}


def jaccard_entries(a: set[tuple[str, str]], b: set[tuple[str, str]]) -> float:
    if not a and not b:
        return 1.0
    u = a | b
    if not u:
        return 0.0
    return len(a & b) / len(u)


def weekly_excess(r_book: pd.Series, r_f0: pd.Series, reb_dates: list[pd.Timestamp]) -> pd.Series:
    idx = sorted(set(r_book.index) & set(r_f0.index))
    ex = pd.Series(0.0, index=idx)
    for i, d in enumerate(reb_dates):
        if d not in ex.index:
            continue
        nxt = reb_dates[i + 1] if i + 1 < len(reb_dates) else ex.index[-1]
        seg = ex.index[(ex.index > d) & (ex.index <= nxt)]
        if len(seg):
            ex.loc[seg] = (r_book.reindex(seg).fillna(0) - r_f0.reindex(seg).fillna(0)).values
    return ex.cumsum()


def best_segment(cum_ex: pd.Series, kind: str) -> tuple[pd.Timestamp, pd.Timestamp, float]:
    idx = list(cum_ex.index)
    best_i, best_j, best_val = 0, 0, 0.0
    for i in range(len(idx)):
        for j in range(i + 1, len(idx)):
            val = float(cum_ex.iloc[j] - cum_ex.iloc[i])
            if kind == "BIGWIN":
                if val > best_val or (val == best_val and (i < best_i or (i == best_i and j - i < best_j - best_i))):
                    best_val, best_i, best_j = val, i, j
            else:
                if val < best_val or (val == best_val and (i < best_i or (i == best_i and j - i < best_j - best_i))):
                    best_val, best_i, best_j = val, i, j
    return idx[best_i], idx[best_j], best_val


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
    if cell.get("inert"):
        cell["verdict"] = "证伪·惰性"
    elif any(math.isnan(x) for x in (cell["ret"], cell["maxDD"], dret, d_abs)):
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
        trades, hold, st, elog = simulate(
            calendar=calendar,
            snaps=snaps,
            closes_w=closes_w_sig,
            alias=alias,
            aum=aum,
            daily=daily,
            risk_on_by_fri=risk_on_by_fri,
            variant=name,
            mode=spec["mode"],
            clenow_n=int(spec["n"]),
            miss_n=int(spec["miss_n"]),
            max_pos=5,
            sharpe_n=20,
        )
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
            f"rerank={st.get('n_rerank', 0)} short={st.get('n_short_fills', 0)} cash_w={st['n_cash_weeks']}",
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
            "mode": spec["mode"],
            "n": spec["n"],
            "ret": st["ret"],
            "maxDD": st["maxDD"],
            "CAGR": st["CAGR"],
            "Calmar": st["Calmar"],
            "avgL": float(L[L > 0].mean()) if (L > 0).any() else 0.0,
            "avg_turnover_1way": avg_to,
            "n_cash_weeks": sim["n_cash_weeks"],
            "n_entries": sim["n_entries"],
            "n_rerank": sim.get("n_rerank", 0),
            "n_miss_clenow": sim.get("n_miss_clenow", 0),
            "n_empty_slots": sim.get("n_empty_slots", 0),
            "n_short_fills": sim.get("n_short_fills", 0),
            "n_fallback_weeks": sim.get("n_fallback_weeks", 0),
            "mean_score": sim.get("mean_score", 0.0),
            "mean_slope_ann": sim.get("mean_slope_ann", 0.0),
            "mean_r2": sim.get("mean_r2", 0.0),
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

    f0_hold = hold_by[BOOK_SPECS[0]["book"]]
    f0_entries = entry_set(entry_logs[BOOK_SPECS[0]["book"]])
    for c in cells:
        if c["id"] == "F0":
            c["jaccard_vs_f0"] = 1.0
            c["inert"] = False
            continue
        hb = hold_by[c["book"]]
        c["inert"] = holdings_inert(hb, f0_hold, calendar)
        c["jaccard_vs_f0"] = jaccard_entries(entry_set(entry_logs[c["book"]]), f0_entries)

    f0_cell = next(c for c in cells if c["id"] == "F0")
    anchor_pass = check_anchor(f0_cell, len(calendar), len(codes), actual_end)
    impl_pass = True
    cs90s_miss = next(c["n_miss_clenow"] for c in cells if c["id"] == "CS90S")
    cs90r_miss = next(c["n_miss_clenow"] for c in cells if c["id"] == "CS90R")
    if cs90s_miss != cs90r_miss:
        impl_pass = False
    for c in cells:
        if c.get("n_short_fills", 0) > 0:
            impl_pass = False
    for spec in BOOK_SPECS:
        cell = next(x for x in cells if x["id"] == spec["id"])
        if cell.get("mode") != spec["mode"] or cell.get("n") != spec["n"]:
            impl_pass = False

    print(f"anchor_pass={anchor_pass} impl_pass={impl_pass} F0 ret={pct(f0_cell['ret'])} Calmar={f0_cell['Calmar']:.2f}", flush=True)

    for c in cells:
        if not anchor_pass:
            c["delta_ret"] = 0.0
            c["delta_abs_mdd"] = 0.0
            c["covers"] = False
            c["window_2020_22"] = False
            c["window_2023_26"] = False
            c["verdict"] = "BLOCKED"
        elif not impl_pass and c["id"] != "F0":
            judge_vs_f0(c, f0_cell)
            c["verdict"] = "BLOCKED"
        else:
            judge_vs_f0(c, f0_cell)

    positive_ids = [c["id"] for c in cells if c["verdict"] == "记正"]
    attrib_pass = True
    if not anchor_pass or not impl_pass:
        family_verdict = "BLOCKED"
        if not anchor_pass:
            for c in cells:
                c["verdict"] = "BLOCKED"
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
                "mode": c["mode"],
                "n": c["n"],
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
                "n_rerank": c["n_rerank"],
                "n_miss_clenow": c["n_miss_clenow"],
                "n_empty_slots": c["n_empty_slots"],
                "n_short_fills": c["n_short_fills"],
                "n_fallback_weeks": c["n_fallback_weeks"],
                "mean_score": c["mean_score"],
                "mean_slope_ann": c["mean_slope_ann"],
                "mean_r2": c["mean_r2"],
                "mean_abs_D": c["mean_abs_D"],
                "hit_rate": c["hit_rate"],
                "win_size": c["win_size"],
                "jaccard_vs_f0": c["jaccard_vs_f0"],
                "inert": c["inert"],
                "delta_ret": c["delta_ret"],
                "delta_abs_mdd": c["delta_abs_mdd"],
                "covers": c["covers"],
                "window_2020_22": c["window_2020_22"],
                "window_2023_26": c["window_2023_26"],
                "verdict": c["verdict"],
            }
        )
    pd.DataFrame(table_rows)[TABLE_COLS].to_csv(OUT / "table.csv", index=False)

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
    ax.set_title("CLENOW-S20-SECONDARY（F0 黑线 vs Clenow 次级排序）")
    ax.set_ylabel("净值（对数）")
    ax.grid(True, alpha=0.3)
    ax.legend(fontsize=8)
    fig.tight_layout()
    fig.savefig(OUT / "equity_curve.png")
    plt.close(fig)

    # entries diff by year
    diff_rows: list[dict[str, Any]] = []
    f0_ent = entry_set(entry_logs[f0_name])
    for spec in BOOK_SPECS[1:]:
        bid = spec["id"]
        ent = entry_set(entry_logs[spec["book"]])
        for side, pairs in (("ADD", ent - f0_ent), ("DROP", f0_ent - ent)):
            by_code: dict[str, list[str]] = defaultdict(list)
            for d, code in pairs:
                by_code[code].append(d)
            for code, dates in by_code.items():
                dates = sorted(dates)
                diff_rows.append(
                    {
                        "year": int(dates[0][:4]),
                        "id": bid,
                        "side": side,
                        "code": code,
                        "n_events": len(dates),
                        "first_date": dates[0],
                        "last_date": dates[-1],
                    }
                )
    pd.DataFrame(diff_rows).to_csv(OUT / "entries_diff_by_year.csv", index=False)

    seg_rows: list[dict[str, Any]] = []
    r_f0 = series[f0_name]
    for spec in BOOK_SPECS[1:]:
        bid = spec["id"]
        r_b = series[spec["book"]]
        ex = (r_b.reindex(days).fillna(0) - r_f0.reindex(days).fillna(0))
        cum_ex = ex.cumsum()
        inert = next(c["inert"] for c in cells if c["id"] == bid)
        for kind in ("BIGWIN", "BIGLOSS"):
            if inert or len(cum_ex) < 3:
                seg_rows.append(
                    {
                        "id": bid,
                        "kind": kind,
                        "start": "",
                        "end": "",
                        "years": "",
                        "delta_cum_ex": 0.0,
                        "n_weeks": 0,
                        "uniq_book": "",
                        "uniq_f0": "",
                        "n_shared": 0,
                    }
                )
                continue
            st_d, en_d, dval = best_segment(cum_ex, kind)
            ys = sorted({st_d.year, en_d.year})
            years = f"{ys[0]}" if len(ys) == 1 else f"{ys[0]}-{ys[-1]}"
            hb = hold_by[spec["book"]]
            codes_book: dict[str, int] = defaultdict(int)
            codes_f0: dict[str, int] = defaultdict(int)
            for d in calendar[:-1]:
                if pd.Timestamp(d) < st_d or pd.Timestamp(d) > en_d:
                    continue
                for ccode in hb.get(d) or []:
                    codes_book[ccode] += 1
                for ccode in f0_hold.get(d) or []:
                    codes_f0[ccode] += 1
            ub = ";".join([c for c, _ in sorted(codes_book.items(), key=lambda x: -x[1])[:8]])
            uf = ";".join([c for c, _ in sorted(codes_f0.items(), key=lambda x: -x[1])[:8]])
            shared = len(set(codes_book) & set(codes_f0))
            seg_rows.append(
                {
                    "id": bid,
                    "kind": kind,
                    "start": st_d.strftime("%Y-%m-%d"),
                    "end": en_d.strftime("%Y-%m-%d"),
                    "years": years,
                    "delta_cum_ex": float(dval),
                    "n_weeks": int((en_d - st_d).days // 7) + 1,
                    "uniq_book": ub,
                    "uniq_f0": uf,
                    "n_shared": shared,
                }
            )
    pd.DataFrame(seg_rows).to_csv(OUT / "segment_attribution.csv", index=False)

    attrib_pass = bool(diff_rows or all(c["inert"] for c in cells if c["id"] != "F0"))
    if not (OUT / "entries_diff_by_year.csv").exists() or not (OUT / "segment_attribution.csv").exists():
        attrib_pass = False
    if not attrib_pass:
        family_verdict = "BLOCKED"

    design_md = HERE / "DESIGN.md"
    h1_block = ""
    if design_md.exists():
        txt = design_md.read_text(encoding="utf-8")
        i = txt.find("```\n唯一改动")
        if i >= 0:
            j = txt.find("```", i + 4)
            h1_block = txt[i + 4 : j].strip()
    if not h1_block:
        h1_block = "见 DESIGN.md H1 块"

    pitch = (
        "请拍板：在面层 B45 + spike_ft max5 + E0 + TV25、LIVE≥14:30 面上，"
        "**填席宇宙仍是 SHARPE20 短名单**，只在短名单内按 Clenow score 次级排序取席。"
        "主口径冻结为 **N=90、`score = (e^{β·252} − 1) × R²` 降序（CS90S）**。"
        "四本锁定为 `F0/CS90S/CS60S/CS90R`。不替 S20，不设硬闸，不扫 θ/N/k。已持仓不因排序键变差而平。无论记正与否都不换冠。"
    )

    h1_sentence = (
        "H1 成立" if family_verdict == "H1_HOLD" else ("H1 证伪" if family_verdict == "H1_REJECT" else "BLOCKED")
    )

    summary = {
        "batch": "clenow-s20-secondary",
        "knife_id": "CLENOW-S20-SECONDARY",
        "champion_swap": False,
        "crown": "NO",
        "source_sha": SOURCE_SHA,
        "sample": [EVAL_START, actual_end],
        "anchor_pass": anchor_pass,
        "impl_pass": impl_pass,
        "attrib_pass": attrib_pass,
        "anchor": {**ANCHOR, "n_weeks": len(calendar), "T": len(calendar) - 1},
        "face_id": "F0",
        "primary": "CS90S",
        "third_book": "CS90R",
        "books_locked": "F0/CS90S/CS60S/CS90R",
        "mechanism": (
            "S20 band secondary sort; CS90S=Clenow(N=90); CS60S=Clenow(N=60); "
            "CS90R=slope_ann(N=90) without R^2; no hard gate"
        ),
        "h1": h1_sentence,
        "family_verdict": family_verdict,
        "positive_ids": positive_ids,
        "skipped_ids": [
            "CS90K2", "CS90xACCEL", "CS90S-top", "SR90", "SR60", "SR90K2",
            "R290S", "ER20S", "COMBOS", "AG40", "AG20", "AG40S",
        ],
        "side_note": {
            "AG40S": "235.6%/-14.8%/1.32 mechanism template only; not a cell; not the ruler RHS"
        },
        "cells": cells,
        "coverage": cov_stats,
        "elapsed_sec": round(time.time() - t0, 1),
    }
    (OUT / "summary.json").write_text(
        json.dumps(summary, ensure_ascii=False, indent=2, default=str), encoding="utf-8"
    )

    def tbl_row(c: dict[str, Any]) -> str:
        return (
            f"| {c['id']} | {c['book']} | {pct(c['ret'])} | {pct(c['maxDD'])} | {c['Calmar']:.2f} | "
            f"{pct(c['w2020_22']['ret'])}/{pct(c['w2023_26']['ret'])} | "
            f"{c['n_rerank']} | {c['n_miss_clenow']} | {c['jaccard_vs_f0']:.3f} | {c['verdict']} |"
        )

    anchor_line = (
        f"锚点门：F0 ret={pct(f0_cell['ret'])} maxDD={pct(f0_cell['maxDD'])} Calmar={f0_cell['Calmar']:.2f} "
        f"（目标 131.6% / −18.8% / 0.70）→ {'通过' if anchor_pass else '未通过'}。"
    )
    impl_line = f"实现门：n_short_fills 全 0、CS90S/CS90R miss 相等 → {'通过' if impl_pass else '未通过'}。"

    mech_books = [c for c in cells if c["id"] != "F0"]
    attrib_b = "; ".join(f"{c['id']} Jaccard={c['jaccard_vs_f0']:.3f}" for c in mech_books)
    attrib_c = "; ".join(
        f"{c['id']} Δret={100*c['delta_ret']:+.1f}pp 2020–22={'过' if c['window_2020_22'] else '踏空'} "
        f"2023–26={'过' if c['window_2023_26'] else '踏空'}"
        for c in mech_books
    )
    attrib_d = "; ".join(
        f"{c['id']} TO1w Δ={c['avg_turnover_1way']-f0_cell['avg_turnover_1way']:+.3f} "
        f"cash周={c['n_cash_weeks']} n_empty_slots={c['n_empty_slots']}"
        for c in mech_books
    )

    if family_verdict == "BLOCKED":
        verdict_line = f"**BLOCKED（不换冠）**：anchor={anchor_pass} impl={impl_pass} attrib={attrib_pass}。"
    elif family_verdict == "H1_HOLD":
        verdict_line = "**H1 成立（不换冠）**：三本 Clenow 次级排序相对本次 F0 均为证伪/惰性，无记正。"
    else:
        verdict_line = f"**H1 证伪（不换冠）**：记正格 {', '.join(positive_ids)}。"

    report = f"""{pitch}

```
{h1_block}
```

## 1. 准则原文（摘要）

- 面：B45 + spike_ft max5 + E0 + TV25 + SHARPE20 短名单次级 Clenow 排序；研究池 AUM≥2（{len(codes)} 只）；窗 {EVAL_START}→{actual_end}（{len(calendar)} 周，T={len(calendar)-1}）。
- 四本：F0 / CS90S（主）/ CS60S / CS90R；第三本只按 slope_ann，不乘 R²。
- 尺子：记正 = Δret≥Δ|MDD| 且两窗 ret ≥ F0 且非惰性。

## 2. 实现要点

- 引擎 fork `{SOURCE_SHA[:12]}`；`band_k=max(2·slots, slots+2)`；缺失置底不删名。
- {anchor_line} {impl_line}
- F0 n_rerank=0；CS90S/CS90R n_miss_clenow={cs90s_miss}（须相等）。

## 3. 主表

| id | book | ret | maxDD | Calmar | 2020–22 / 2023–26 ret | n_rerank | n_miss | Jaccard | verdict |
|---|---|---:|---:|---:|---|---:|---:|---:|---|
{chr(10).join(tbl_row(c) for c in cells)}

## ATTRIBUTION

(a) 机制：仅在 S20 短名单（band_k）内做 Clenow 次级排序；B45/spike_ft/max5/E0/TV25/SHARPE20 宇宙/Fri≥14:30/0.2%RT/AUM≥2 未动；无替席、无硬闸、无 θ/N/k；第三本 CS90R；四本 F0/CS90S/CS60S/CS90R。

(b) 席位重叠（入场 Jaccard vs F0）：{attrib_b}

(c) 窗 Δ：{attrib_c}

(d) 换手与空仓周：{attrib_d}；F0 n_cash_weeks={f0_cell['n_cash_weeks']}。

(e) 名字·年份：见 `entries_diff_by_year.csv`；大赢/大亏段见 `segment_attribution.csv`（惰性格 delta=0）。

ATTRIBUTION 不进 verdict。

## 5. 一句判词

{verdict_line}

family_verdict={family_verdict}；anchor_pass={anchor_pass}；impl_pass={impl_pass}；attrib_pass={attrib_pass}；耗时 {summary['elapsed_sec']}s。
"""
    (OUT / "REPORT.md").write_text(report, encoding="utf-8")
    print("done", OUT, flush=True)
    print(verdict_line, flush=True)


if __name__ == "__main__":
    main()
