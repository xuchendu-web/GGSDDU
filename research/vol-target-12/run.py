#!/usr/bin/env python3
"""VOL-TARGET-12-B45: 12% ann vol-target (20w weekly σ̂) on frozen B45 research face.

Frozen weekly book: B45 + spike_ft max5 + SHARPE20-fill + E0 + Fri≥14:30/close + 0.2%RT.
Overlays (holdings identical):
  RESEARCH-B45-FACE — TV25 (σ*=25%, daily max(σ20,σ60)); anchor inventory
  RESEARCH-B45-VT12 — σ*=12%, Fri scale L=min(1,0.12/σ̂_w20), σ̂_w20=std(20 weekly rets)×√52

Research only; no strategy_exec / LIVE_OPS / crown change.
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

KIT = Path(__file__).resolve().parents[1] / "cloud_batch" / "CLOUD-BATCH-2026-10-26"
if not KIT.exists():
    KIT = Path("/workspace/research/cloud_batch/CLOUD-BATCH-2026-10-26")
SCRIPTS = KIT / "scripts"
sys.path.insert(0, str(SCRIPTS))

from backtest import KEEP, LIVE_PHASE, MIN_BARS, Position, nearest_date, snap_index  # noqa: E402
from build_scan import Bar, classify, http_get_retry, market  # noqa: E402

OUT = Path(__file__).resolve().parent
CACHE = KIT / "data" / "research_cache"
UNI_CSV = KIT / "data" / "universe_replace_only_436.csv"
WEEK = CACHE / "week"
FACE = CACHE / "holdings_ro2_extended.csv"
DAY_DIR = CACHE / "day"
TEMA_PX = KIT / "data" / "tema_prices"  # optional; day cache primary
NOON_CSV = CACHE / "fri_1430_through_20261023.csv"
SINA_DAILY = CACHE / "sina_daily"
CLASSIFY_FROM = "2019-07-01"
SNAP_CACHE = KIT / "data" / "cache_1430_snaps.json"
MAX_POS = 5

EVAL_START = "2020-01-03"
END_S = "2026-10-23"
COST_SIDE = 0.001
SIGMA_STAR_FACE = 0.25
SIGMA_STAR_VT12 = 0.12
LCAP = 1.0
LIVE_COST_RT = 0.002
CLASSIFY_WORKERS = 8

# Inventory anchor (SPIKE-S20-EXTEND-REBASE / RESEARCH-WF-OOS-B45-FACE main_table)
ANCHOR_RET = 1.3163485737878418
ANCHOR_MDD = -0.18799993761556133
ANCHOR_CALMAR = 0.6989834460989939
ANCHOR_TOL_RET = 0.008
ANCHOR_TOL_MDD = 0.008
ANCHOR_TOL_CALMAR = 0.04

BOOK_FACE = "RESEARCH-B45-FACE"
BOOK_VT12 = "RESEARCH-B45-VT12"


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
        if ftema.exists():
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
        if (s is None or len(s) < 10) and sina and c in sina and sina[c]:
            idx = pd.to_datetime(sorted(sina[c].keys()))
            s = pd.Series([sina[c][k.strftime("%Y-%m-%d")] for k in idx], index=idx, dtype=float)
        if s is not None and len(s) >= 10:
            out[c] = s
    return out


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
    rank_fn: RankFn,
    variant: str,
    require_sharpe: bool,
    sharpe_n: int | None,
    max_pos: int,
) -> tuple[list[dict[str, Any]], dict[str, list[str]], dict[str, Any]]:
    cash = 1.0
    positions: dict[str, Position] = {}
    trades: list[dict[str, Any]] = []
    picks: dict[str, list[str]] = {}
    n_tight = 0
    n_feat = 0
    n_entries = 0
    n_miss_sharpe = 0
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
            pool = build_cands(d, set(positions))
            slots = max_pos - len(positions)
            if pool:
                n_feat += 1
            if slots > 0 and len(pool) > slots:
                n_tight += 1
            if slots > 0 and pool:
                pool_rank = pool
                if require_sharpe:
                    pool_rank = [c for c in pool if c.sharpe is not None]
                take = sorted(pool_rank, key=lambda c: rank_fn(c, pool_rank))[:slots]
                for c in take:
                    n_entries += 1
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
    return trades, hold, stats



def simulate_hyst(
    calendar: list[str],
    snaps: dict[str, dict[str, dict[str, Any]]],
    closes_w: dict[str, dict[str, float]],
    alias: dict[str, dict[str, str]],
    aum: dict[str, float],
    daily: dict[str, pd.Series],
    risk_on_by_fri: dict[str, bool],
    rank_fn: RankFn,
    variant: str,
    require_sharpe: bool,
    sharpe_n: int | None,
    hyst_m: int | None = None,
) -> tuple[list[dict[str, Any]], dict[str, list[str]], dict[str, Any]]:
    """hyst_m=None → baseline fill-only.
    hyst_m=M≥0 → after forced exits, kick held spike names with 1-based rank > 5+M;
    then fill empty seats from Top5 only (never open rank 6..5+M as new entries).
    Held names not in spike ranking this week are NOT hysteretically kicked
    (leave to structure/risk — already applied).
    """
    cash = 1.0
    positions: dict[str, Position] = {}
    trades: list[dict[str, Any]] = []
    picks: dict[str, list[str]] = {}
    n_tight = 0
    n_feat = 0
    n_entries = 0
    n_miss_sharpe = 0
    n_cand_weeks = 0
    n_forced_exits = 0
    n_hyst_exits = 0
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

    def do_exit(code: str, reason: str, px: float, d: str) -> None:
        nonlocal cash, n_forced_exits, n_hyst_exits
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
        if reason.startswith("hyst"):
            n_hyst_exits += 1
        else:
            n_forced_exits += 1

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
            do_exit(code, reason, px, d)

        take: list[Cand] = []
        if not last_bar and risk_on:
            # Full ranking L among spike_ft (incl. held spikes)
            pool_all = build_cands(d, skip=set())
            if pool_all:
                n_feat += 1
                n_cand_weeks += 1
            pool_rank = pool_all
            if require_sharpe:
                pool_rank = [c for c in pool_all if c.sharpe is not None]
            L = sorted(pool_rank, key=lambda c: rank_fn(c, pool_rank))
            if len(L) > MAX_POS:
                n_tight += 1
            rank_of = {c.code: i + 1 for i, c in enumerate(L)}  # 1-based
            by_code = {c.code: c for c in L}
            keep_upto = MAX_POS + (hyst_m if hyst_m is not None else 10**9)

            if hyst_m is not None:
                # hysteresis rank-kick: only if ranked and rank > 5+M
                hyst_out: list[tuple[str, float, int]] = []
                for code in list(positions.keys()):
                    if code not in rank_of:
                        continue  # non-spike survivor: structure already kept
                    rk = rank_of[code]
                    if rk > keep_upto:
                        px = px_on(code, d)
                        if px is None:
                            px = positions[code].last_px
                        hyst_out.append((code, px, rk))
                # kick worst ranks first (highest rank number)
                hyst_out.sort(key=lambda x: -x[2])
                for code, px, rk in hyst_out:
                    do_exit(code, f"hyst_rank_{rk}", px, d)
                    rank_rows.append(
                        {
                            "date": d,
                            "variant": variant,
                            "code": code,
                            "sharpe": by_code[code].sharpe if code in by_code else None,
                            "rank": rk,
                            "kind": "hyst_exit",
                            "keep_upto": keep_upto,
                        }
                    )

            # fill empty seats from Top5 only
            top5 = L[:MAX_POS]
            slots = MAX_POS - len(positions)
            if slots > 0 and top5:
                held = set(positions.keys())
                fillers = [c for c in top5 if c.code not in held]
                take = fillers[:slots]
                for c in take:
                    n_entries += 1
                    if c.sharpe is None:
                        n_miss_sharpe += 1
                    rank_rows.append(
                        {
                            "date": d,
                            "variant": variant,
                            "code": c.code,
                            "aum": c.aum,
                            "sharpe": c.sharpe,
                            "rank": rank_of.get(c.code),
                            "kind": "top5_fill",
                            "hyst_m": hyst_m,
                        }
                    )

        picks[d] = [c.code for c in take]

        if take:
            eq = equity_now()
            n_after = len(positions) + len(take)
            if n_after > MAX_POS:
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
    for d in calendar:
        for code in exits_by_day.get(d, []):
            open_codes.discard(code)
        for code in picks.get(d, []):
            open_codes.add(code)
        hold[d] = sorted(open_codes)

    to_vals = []
    prev: set[str] = set()
    for d in calendar[:-1]:
        cur = set(hold.get(d) or [])
        if prev or cur:
            to_vals.append(len(prev.symmetric_difference(cur)) / (2.0 * MAX_POS))
        prev = cur
    avg_to = float(np.mean(to_vals)) if to_vals else 0.0

    stats = {
        "n_fridays_queue_gt_seats": n_tight,
        "n_fridays_with_cands": n_feat,
        "n_entries": n_entries,
        "n_entries_missing_sharpe": n_miss_sharpe,
        "n_trades": len(trades),
        "n_forced_exits": n_forced_exits,
        "n_hyst_exits": n_hyst_exits,
        "avgTO": avg_to,
        "hyst_m": hyst_m,
    }
    if rank_rows:
        pd.DataFrame(rank_rows).to_csv(OUT / f"entries_{variant}.csv", index=False)
    return trades, hold, stats


def run_live_tv(
    hold: dict[pd.Timestamp, list[str]],
    days: pd.DatetimeIndex,
    px: pd.DataFrame,
    R: pd.DataFrame,
    sigma_star: float = SIGMA_STAR_FACE,
    cash_fill: str | None = None,
    vol_mode: str = "daily_max2060",
    scale_log: list[dict[str, Any]] | None = None,
) -> tuple[pd.Series, pd.Series, pd.Series, pd.Series]:
    reb = sorted(hold)
    rp = pd.Series(0.0, index=days)
    Ls = pd.Series(0.0, index=days)
    prev: dict[str, float] = {}
    cst = pd.Series(0.0, index=days)
    R2 = R.reindex(days)
    weekly_rets: list[float] = []
    prev_fri: pd.Timestamp | None = None

    for i, d in enumerate(reb):
        cs = [c for c in hold[d] if c in px.columns]
        nxt = reb[i + 1] if i + 1 < len(reb) else days[-1] + pd.Timedelta(days=1)
        seg = days[(days > d) & (days <= nxt)]
        w: dict[str, float] = {}
        L = 0.0
        sh = s20 = s60 = sw20 = sw12 = sw40 = float("nan")
        if not cs:
            if cash_fill and cash_fill in px.columns:
                cs = [cash_fill]
                w = {cash_fill: 1.0}
        if cs:
            if not w:
                w = {c: 1.0 / len(cs) for c in cs}
            if vol_mode == "weekly_w20":
                if len(weekly_rets) >= 2:
                    tail20 = weekly_rets[-20:]
                    sw20 = float(np.std(tail20, ddof=1) * np.sqrt(52))
                    if len(weekly_rets) >= 12:
                        sw12 = float(np.std(weekly_rets[-12:], ddof=1) * np.sqrt(52))
                    if len(weekly_rets) >= 40:
                        sw40 = float(np.std(weekly_rets[-40:], ddof=1) * np.sqrt(52))
                    sh = sw20
                else:
                    sh = float("nan")
                L = (
                    float(min(LCAP, sigma_star / sh))
                    if sh and sh > 0 and np.isfinite(sh)
                    else 1.0
                )
            else:
                past = rp[rp.index <= d]
                past = past[past != 0]
                if len(past) < 2:
                    L = 1.0
                else:
                    s20 = float(past.iloc[-20:].std() * np.sqrt(252))
                    s60 = float(past.iloc[-60:].std() * np.sqrt(252))
                    sh = float(np.nanmax([s20, s60]))
                    L = float(min(LCAP, sigma_star / sh)) if sh and sh > 0 else 1.0
        if scale_log is not None:
            scale_log.append(
                {
                    "date": pd.Timestamp(d).date().isoformat(),
                    "sigma_star": sigma_star,
                    "vol_mode": vol_mode,
                    "n_held": len(cs),
                    "s20d": s20,
                    "s60d": s60,
                    "sw20": sw20,
                    "sw12": sw12,
                    "sw40": sw40,
                    "sh": sh,
                    "L": L,
                }
            )
        wt = {c: L * v for c, v in w.items()}
        to = sum(abs(wt.get(k, 0) - prev.get(k, 0)) for k in set(wt) | set(prev))
        prev = wt
        if d in cst.index:
            cst.loc[d] = to * LIVE_COST_RT / 2
        if w and len(seg):
            rp.loc[seg] = (R2.loc[seg, list(w)].fillna(0) @ pd.Series(w)).values
            Ls.loc[seg] = L
        if prev_fri is not None and vol_mode == "weekly_w20":
            seg_w = rp[(rp.index > prev_fri) & (rp.index <= d)]
            if len(seg_w):
                weekly_rets.append(float((1 + seg_w).prod() - 1.0))
        prev_fri = d
    r = rp * Ls - cst
    return r, Ls, rp, cst


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


def fetch_tencent_day(code: str) -> pd.Series:
    """Download qfq daily closes for bond/aux codes (research-only)."""
    m = market(code)
    url = (
        "https://web.ifzq.gtimg.cn/appstock/app/fqkline/get"
        f"?param={m}{code},day,2019-01-01,{END_S},2000,qfq"
    )
    payload = json.loads(http_get_retry(url))
    data = payload.get("data") or {}
    key = f"{m}{code}"
    node = data.get(key) or (next(iter(data.values())) if data else None)
    rows = (node or {}).get("qfqday") or (node or {}).get("day") or []
    idx = []
    vals = []
    for row in rows:
        if not row:
            continue
        d = str(row[0])[:10]
        c = float(row[2])
        if c > 0 and EVAL_START <= d <= END_S:
            idx.append(pd.Timestamp(d))
            vals.append(c)
    if not vals:
        raise SystemExit(f"tencent_empty for {code}")
    s = pd.Series(vals, index=idx, dtype=float)
    return s[~s.index.duplicated(keep="last")].sort_index()


def metrics_row(name: str, r: pd.Series, L: pd.Series, sim_st: dict[str, Any]) -> dict[str, Any]:
    st = stats_full(r)
    r2022 = r[(r.index >= "2020-01-01") & (r.index <= "2022-12-31")]
    r2023 = r[r.index >= "2023-01-01"]
    st2022 = stats_full(r2022) if len(r2022) > 5 else {k: float("nan") for k in st}
    st2023 = stats_full(r2023) if len(r2023) > 5 else {k: float("nan") for k in st}
    vol = float(r.std(ddof=1) * np.sqrt(252)) if len(r) > 1 else float("nan")
    return {
        "book": name,
        **st,
        "vol": vol,
        "2020-22_ret": st2022["ret"],
        "2020-22_DD": st2022["maxDD"],
        "2020-22_Calmar": st2022["Calmar"],
        "2023-26_ret": st2023["ret"],
        "2023-26_DD": st2023["maxDD"],
        "2023-26_Calmar": st2023["Calmar"],
        "avgL": float(L[L > 0].mean()) if (L > 0).any() else 0.0,
        "cash_week_pct": sim_st.get("cash_week_pct", float("nan")),
        "risk_on_week_pct": sim_st.get("risk_on_week_pct", float("nan")),
    }


def truncate_metrics(r: pd.Series, end: str) -> dict[str, float]:
    sub = r[r.index <= pd.Timestamp(end)]
    return stats_full(sub) if len(sub) > 5 else stats_full(r)


def metrics_through_calendar_weeks(
    r: pd.Series, calendar: list[str], end_friday: str
) -> dict[str, float]:
    """Old-window metrics: last daily return on or before end_friday."""
    if end_friday not in calendar:
        end_friday = max(d for d in calendar if d <= end_friday)
    sub = r[r.index <= pd.Timestamp(end_friday)]
    return stats_full(sub) if len(sub) > 5 else stats_full(r)


def main() -> None:
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

    # B45 risk_on from face
    risk_b45: dict[str, bool] = {}
    for _, row in face.iterrows():
        d = str(row["date"])[:10]
        v = row["risk_on"]
        if isinstance(v, (bool, np.bool_)):
            risk_b45[d] = bool(v)
        else:
            risk_b45[d] = str(v).lower() in {"1", "true", "True"}
    for d in calendar:
        risk_b45.setdefault(d, False)
    risk_b45[calendar[-1]] = False

    risk_b50: dict[str, bool] = {}
    for _, row in face.iterrows():
        d = str(row["date"])[:10]
        b = row.get("b")
        try:
            risk_b50[d] = float(b) >= 0.50 if b is not None and str(b) != "" else False
        except (TypeError, ValueError):
            risk_b50[d] = False
    for d in calendar:
        risk_b50.setdefault(d, False)
    risk_b50[calendar[-1]] = False

    print(
        f"B45 risk_on={sum(1 for d in calendar[:-1] if risk_b45.get(d))} / {len(calendar)-1}; "
        f"B50 risk_on={sum(1 for d in calendar[:-1] if risk_b50.get(d))} / {len(calendar)-1}",
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
    print(f"daily price series: {len(daily)}/{len(codes)}", flush=True)

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
        q = None
        if r.code in daily:
            ser = daily[r.code]
            ts = pd.Timestamp(td)
            if ts in ser.index:
                q = float(ser.loc[ts])
            else:
                sub = ser.loc[:ts]
                if len(sub) and (ts - sub.index[-1]).days <= 3:
                    q = float(sub.iloc[-1])
        b = (sina.get(r.code) or {}).get(td)
        if not b or b <= 0:
            n_skip += 1
            blocked_empty[td].add(r.code)
            continue
        if not q or q <= 0:
            q = float(b)
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
            "B45/B50 breadth/risk_on：face holdings_ro2_extended 列 b / risk_on（B50: b≥0.50）",
            "HYST-M3：滞回 M=3；TV33：σ*=0.33 同 B45 持仓；CASH-511010：空仓周 TV25 持 511010",
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
        raise SystemExit(f"missing SNAP_CACHE {SNAP_CACHE}")
    print(f"load cached 1430 snaps {SNAP_CACHE}", flush=True)
    cached = json.loads(SNAP_CACHE.read_text(encoding="utf-8"))
    by_rows = cached.get("by_code") or {}
    snaps = {c: snap_index(by_rows.get(c) or []) for c in codes}

    print(f"simulate shared {BOOK_FACE}…", flush=True)
    trades, hold, sim_st = simulate(
        calendar,
        snaps,
        closes_w_sig,
        alias,
        aum,
        daily,
        risk_b45,
        sharpe_key,
        BOOK_FACE,
        True,
        20,
        MAX_POS,
    )
    rows = []
    for d in calendar[:-1]:
        codes_h = hold.get(d) or []
        rows.append(
            {
                "date": d,
                "risk_on": int(risk_b45.get(d, False)),
                "n_held": len(codes_h),
                "codes": ",".join(codes_h),
            }
        )
    pd.DataFrame(rows).to_csv(OUT / f"holdings_{BOOK_FACE}.csv", index=False)
    pd.DataFrame(trades).to_csv(OUT / f"trades_{BOOK_FACE}.csv", index=False)
    print(
        f"  entries={sim_st['n_entries']} trades={sim_st['n_trades']} "
        f"cash_weeks={sim_st['n_cash_weeks']}",
        flush=True,
    )

    all_codes: set[str] = set()
    for cs in hold.values():
        all_codes |= set(cs)
    px_map = {}
    for c in sorted(all_codes):
        if c in daily:
            px_map[c] = daily[c]
        else:
            fday = DAY_DIR / f"{c}.json"
            if fday.exists():
                j = json.loads(fday.read_text(encoding="utf-8"))
                bars = j.get("bars") if isinstance(j, dict) else j
                if bars:
                    idx = pd.to_datetime([b["date"] for b in bars])
                    px_map[c] = pd.Series(
                        [float(b["c"]) for b in bars], index=idx, dtype=float
                    ).sort_index()
            elif (TEMA_PX / f"{c}.csv").exists():
                df = pd.read_csv(TEMA_PX / f"{c}.csv", parse_dates=["Date"])
                px_map[c] = df.set_index("Date")["Close"].astype(float).sort_index()
    px = pd.DataFrame(px_map).sort_index()
    px = px.loc[(px.index >= EVAL_START) & (px.index <= END_S)]
    R = px.pct_change()
    if "510300" in px.columns:
        days = px["510300"].dropna().index
    else:
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

    hd = {pd.Timestamp(d): (hold.get(d) or []) for d in calendar}
    scale_face: list[dict[str, Any]] = []
    scale_vt12: list[dict[str, Any]] = []
    r_face, L_face, rp_u, cst_face = run_live_tv(
        hd, days, px, R, sigma_star=SIGMA_STAR_FACE, vol_mode="daily_max2060", scale_log=scale_face
    )
    r_vt12, L_vt12, _rp2, cst_vt12 = run_live_tv(
        hd,
        days,
        px,
        R,
        sigma_star=SIGMA_STAR_VT12,
        vol_mode="weekly_w20",
        scale_log=scale_vt12,
    )

    st_face = stats_full(r_face)
    anchor_ok = (
        abs(st_face["ret"] - ANCHOR_RET) <= ANCHOR_TOL_RET
        and abs(st_face["maxDD"] - ANCHOR_MDD) <= ANCHOR_TOL_MDD
        and abs(st_face["Calmar"] - ANCHOR_CALMAR) <= ANCHOR_TOL_CALMAR
    )
    if not anchor_ok:
        msg = (
            f"ANCHOR FAIL: FACE ret={pct(st_face['ret'])} MDD={pct(st_face['maxDD'])} "
            f"Calmar={st_face['Calmar']:.2f}; expected ~{pct(ANCHOR_RET)}/{pct(ANCHOR_MDD)}/"
            f"C{ANCHOR_CALMAR:.2f} (inventory SPIKE-S20-EXTEND-REBASE / WF-OOS)"
        )
        (OUT / "ANCHOR_FAIL.txt").write_text(msg + "\n", encoding="utf-8")
        raise SystemExit(msg)

    series = {BOOK_FACE: r_face, BOOK_VT12: r_vt12}
    Ls_map = {BOOK_FACE: L_face, BOOK_VT12: L_vt12}
    table_rows = []
    for name, r, L in (
        (BOOK_FACE, r_face, L_face),
        (BOOK_VT12, r_vt12, L_vt12),
    ):
        row = metrics_row(name, r, L, sim_st)
        table_rows.append(row)
        (1 + r).cumprod().to_csv(OUT / f"nav_{name}.csv", header=["nav"])
        st = stats_full(r)
        print(
            f"  {name}: ret={pct(st['ret'])} dd={pct(st['maxDD'])} "
            f"Calmar={st['Calmar']:.2f} vol={pct(row.get('vol', float('nan')))}",
            flush=True,
        )

    df = pd.DataFrame(table_rows)
    df.to_csv(OUT / "table.csv", index=False)
    pd.DataFrame([{**x, "book": BOOK_FACE} for x in scale_face]).to_csv(
        OUT / "scale_log_face.csv", index=False
    )
    pd.DataFrame([{**x, "book": BOOK_VT12} for x in scale_vt12]).to_csv(
        OUT / "scale_log_vt12.csv", index=False
    )

    y = yearly_table(r_face).rename(columns=lambda c: f"face_{c}" if c != "year" else c)
    yv = yearly_table(r_vt12).rename(columns=lambda c: f"vt12_{c}" if c != "year" else c)
    y = y.merge(yv, on="year", how="outer")
    y.to_csv(OUT / "yearly.csv", index=False)

    eq = pd.DataFrame({k: (1 + series[k]).cumprod() for k in series})
    eq.to_csv(OUT / "equity.csv")

    fig, ax = plt.subplots(figsize=(11, 5.5), dpi=120)
    ax.plot(eq.index, eq[BOOK_FACE], label="FACE TV25", lw=2.0)
    ax.plot(eq.index, eq[BOOK_VT12], label="VT12 (20w weekly σ̂)", lw=1.6, ls="--")
    ax.set_yscale("log")
    ax.set_title("VOL-TARGET-12-B45  FACE vs VT12")
    ax.set_ylabel("NAV (log)")
    ax.grid(True, alpha=0.3)
    ax.legend(fontsize=9)
    fig.tight_layout()
    fig.savefig(OUT / "equity_curve.png")
    plt.close(fig)

    # Attribution: timing (leverage) vs cost vs selection (0, shared book)
    timing = rp_u * (L_vt12 - L_face)
    cost_delta = -(cst_vt12 - cst_face)
    delta_r = r_vt12 - r_face
    resid = delta_r - timing - cost_delta
    attr_y = []
    for y in sorted(set(delta_r.index.year)):
        mask = delta_r.index.year == y
        attr_y.append(
            {
                "year": y,
                "timing": float(timing[mask].sum()),
                "cost": float(cost_delta[mask].sum()),
                "selection": float(resid[mask].sum()),
                "total_delta": float(delta_r[mask].sum()),
            }
        )
    pd.DataFrame(attr_y).to_csv(OUT / "attribution_yearly.csv", index=False)

    # By name / year (gross hold PnL share under FACE L)
    name_rows = []
    tr = pd.DataFrame(trades)
    for _, t in tr.iterrows():
        code = t["code"]
        if code not in px.columns:
            continue
        ent, ext = pd.Timestamp(t["entry_date"]), pd.Timestamp(t["exit_date"])
        seg = px[code].loc[ent:ext].pct_change().dropna()
        if len(seg) == 0:
            continue
        gross = float((1 + seg).prod() - 1.0)
        yr = ext.year
        name_rows.append({"year": yr, "code": code, "gross_hold_ret": gross})
    if name_rows:
        ny = pd.DataFrame(name_rows).groupby(["year", "code"], as_index=False)["gross_hold_ret"].mean()
        ny.to_csv(OUT / "attribution_by_name_year.csv", index=False)
    (OUT / "ATTRIBUTION.md").write_text(
        "## 归因（VT12 − FACE）\n\n"
        "- **选股 selection**：持仓路径冻结，残差计入 `attribution_yearly.selection`（应≈0）。\n"
        "- **择时 timing**：未杠杆组合日收益 × (L_VT12 − L_FACE) 按年汇总。\n"
        "- **成本 cost**：换手差异导致的额外 0.2%RT（`cst_vt12 − cst_face`）。\n"
        "- **按标的/年**：`attribution_by_name_year.csv` 为各次持仓段毛收益（未分 L）。\n",
        encoding="utf-8",
    )

    face_row = df[df.book == BOOK_FACE].iloc[0]
    vt_row = df[df.book == BOOK_VT12].iloc[0]
    dret = (float(vt_row["ret"]) - float(face_row["ret"])) * 100
    ddd = (abs(float(vt_row["maxDD"])) - abs(float(face_row["maxDD"]))) * 100
    covers = dret >= ddd - 1e-9
    rear_ok = float(vt_row["2023-26_ret"]) >= float(face_row["2023-26_ret"]) - 0.03
    falsify = not (covers and rear_ok and float(vt_row["Calmar"]) >= float(face_row["Calmar"]))

    if falsify:
        verdict = (
            f"**证伪（不换冠）**：VT12 相对 FACE 未同时满足 Calmar/ret/|MDD| 探索尺子或 2023–26 踏空；"
            f"Δret={dret:+.1f}pp Δ|MDD|={ddd:+.1f}pp covers={covers} rear_ok={rear_ok}。"
        )
    else:
        verdict = (
            f"**通过探索记账（不换冠）**：VT12 相对 FACE 满足尺子（unlikely）；"
            f"Δret={dret:+.1f}pp。"
        )

    cov_stats["approximation"] = [
        *cov_stats["approximation"],
        "VT12：σ̂_w=std(近20个 Fri–Fri 未杠杆周收益)×√52；每周五调 L=min(1,0.12/σ̂_w)",
        "FACE 锚：TV25 daily max(σ20,σ60) 与 SPIKE-S20-EXTEND-REBASE LIVE1430-B45-S20 一致",
        "邻居 VT10/VT15 见 PR#73 research/vol-target-10-15-b45（不重跑网格）",
    ]

    summary = {
        "title": "VOL-TARGET-12-B45",
        "anchor_inventory": "SPIKE-S20-EXTEND-REBASE LIVE1430-B45-S20 / RESEARCH-WF-OOS main_table TV25",
        "anchor_expected": {"ret": ANCHOR_RET, "maxDD": ANCHOR_MDD, "Calmar": ANCHOR_CALMAR},
        "anchor_actual": st_face,
        "anchor_ok": anchor_ok,
        "sample": f"{EVAL_START} → {actual_end}",
        "coverage": cov_stats,
        "sim_stats": sim_st,
        "table": table_rows,
        "delta_vt12_vs_face": {"dret_pp": dret, "d_abs_mdd_pp": ddd, "covers": covers, "rear_2023_26_ok": rear_ok},
        "falsify": falsify,
        "verdict": verdict,
        "elapsed_sec": round(time.time() - t0, 1),
    }
    (OUT / "summary.json").write_text(
        json.dumps(summary, ensure_ascii=False, indent=2, default=str), encoding="utf-8"
    )

    (OUT / "criterion.md").write_text(
        f"""# 准则 · VOL-TARGET-12-B45

- **冻结面**：B45 + spike_ft max5 + E0 + TV25 + SHARPE20-fill + Fri≥14:30/收盘 + 0.2%RT + L≤1。
- **唯一改动**：叠加 **VT12**（σ*=12%，20 周周收益 σ̂，每周五调杠杆）。
- **锚**：FACE（TV25）须复现延窗 inventory **{pct(ANCHOR_RET)} / {pct(ANCHOR_MDD)} / C{ANCHOR_CALMAR:.2f}**。
- **证伪**：VT12 vs FACE — Calmar / ret / |MDD|；2023–26 相对 FACE 不踏空。
- **样本**：{EVAL_START}→{END_S}。研究池 only。
""",
        encoding="utf-8",
    )

    approx_md = "\n".join(f"- {a}" for a in cov_stats["approximation"])
    sw12_med = float(pd.Series([x.get("sw12") for x in scale_vt12 if x.get("sw12") == x.get("sw12")]).median())
    sw40_med = float(pd.Series([x.get("sw40") for x in scale_vt12 if x.get("sw40") == x.get("sw40")]).median())
    neighbor_note = (
        f"邻居 σ̂ 中位数（仅记账）：12w≈{pct(sw12_med) if sw12_med == sw12_med else '—'}，"
        f"40w≈{pct(sw40_med) if sw40_med == sw40_med else '—'}；主口径 20w。"
    )

    report = f"""# REPORT · VOL-TARGET-12-B45

## 锚（FACE · TV25，无 VT12 叠加）

| | ret | maxDD | Calmar |
|---|---:|---:|---:|
| inventory | {pct(ANCHOR_RET)} | {pct(ANCHOR_MDD)} | {ANCHOR_CALMAR:.2f} |
| 本跑 FACE | {pct(st_face['ret'])} | {pct(st_face['maxDD'])} | {st_face['Calmar']:.2f} |

锚复现：**{'OK' if anchor_ok else 'FAIL'}**

## 主表

| book | ret | maxDD | Calmar | vol | 2023–26 ret | avgL |
|---|---:|---:|---:|---:|---:|---:|
| FACE | {pct(face_row['ret'])} | {pct(face_row['maxDD'])} | {face_row['Calmar']:.2f} | {pct(face_row.get('vol', float('nan')))} | {pct(face_row['2023-26_ret'])} | {face_row['avgL']:.2f} |
| VT12 | {pct(vt_row['ret'])} | {pct(vt_row['maxDD'])} | {vt_row['Calmar']:.2f} | {pct(vt_row.get('vol', float('nan')))} | {pct(vt_row['2023-26_ret'])} | {vt_row['avgL']:.2f} |

Δret={dret:+.1f}pp；Δ|MDD|={ddd:+.1f}pp；盖住={covers}；2023–26 不差={rear_ok}。

交叉引用：VT10/VT15 见 **PR#73** `research/vol-target-10-15-b45`（日频 σ̂ 网格，本刀仅 12% + 周频 σ̂）。

## 波动口径

- **VT12 主口径**：{neighbor_note}
- **FACE**：日频 max(σ20,σ60)×√252，σ*=25%。

## 近似

{approx_md}

## 归因

见 `ATTRIBUTION.md`、`attribution_yearly.csv`、`attribution_by_name_year.csv`。

## 结论

{verdict}

耗时约 {summary['elapsed_sec']}s。
"""
    (OUT / "REPORT.md").write_text(report, encoding="utf-8")
    print("done", OUT, flush=True)
    print(verdict, flush=True)


if __name__ == "__main__":
    main()
