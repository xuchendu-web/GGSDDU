#!/usr/bin/env python3
"""SPIKE-S20-EXTEND-REBASE-LIVE1430: extend sample end only (≥2026-10-23); rules frozen.

Books (same engine, extended window):
  LIVE1430-B45-S20, LIVE1430-B50-S20, LIVE1430-TV33-S20,
  LIVE1430-HYST-M3-S20, LIVE1430-CASH-511010

Fri≥14:30/close; 0.2%RT; L≤1; spike_ft+S20+E0+TV25 base; research pool only.
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

KIT = Path(__file__).resolve().parents[3] / "CLOUD-BATCH-2026-10-26"
if not KIT.exists():
    KIT = Path("/workspace/CLOUD-BATCH-2026-10-26")
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
OLD_WINDOW_END = "2026-09-24"
CASH_CODE = "511010"
MAX_POS = 5

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
    sigma_star: float = SIGMA_STAR,
    cash_fill: str | None = None,
) -> tuple[pd.Series, pd.Series]:
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
        w: dict[str, float] = {}
        if not cs:
            if cash_fill and cash_fill in px.columns:
                cs = [cash_fill]
                w = {cash_fill: 1.0}
            else:
                L = 0.0
        if cs:
            if not w:
                w = {c: 1.0 / len(cs) for c in cs}
            past = rp[rp.index <= d]
            past = past[past != 0]
            if len(past) < 2:
                L = 1.0
            else:
                s20 = past.iloc[-20:].std() * np.sqrt(252)
                s60 = past.iloc[-60:].std() * np.sqrt(252)
                sh = np.nanmax([s20, s60])
                L = float(min(LCAP, sigma_star / sh)) if sh and sh > 0 else 1.0
        else:
            L = 0.0
        wt = {c: L * v for c, v in w.items()}
        to = sum(abs(wt.get(k, 0) - prev.get(k, 0)) for k in set(wt) | set(prev))
        prev = wt
        if d in cst.index:
            cst.loc[d] = to * LIVE_COST_RT / 2
        if w and len(seg):
            rp.loc[seg] = (R2.loc[seg, list(w)].fillna(0) @ pd.Series(w)).values
            Ls.loc[seg] = L
    r = rp * Ls - cst
    return r, Ls


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
    return {
        "book": name,
        **st,
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

    # classify: reuse ref cache if end matches old, else rebuild into OUT cache
    need_rebuild = True
    if SNAP_CACHE.exists():
        cached = json.loads(SNAP_CACHE.read_text(encoding="utf-8"))
        if cached.get("end") == actual_end:
            print(f"load OUT cached 1430 snaps end={actual_end}", flush=True)
            by_rows = cached.get("by_code") or {}
            snaps = {c: snap_index(by_rows.get(c) or []) for c in codes}
            need_rebuild = False
    if need_rebuild:
        print("14:30 classify_modified (extended window)…", flush=True)
        by = classify_modified(raws_w, dict(noon_w))
        by_rows = {c: by.get(c) or [] for c in codes}
        out_snap = OUT / "cache_1430_snaps.json"
        out_snap.write_text(
            json.dumps({"by_code": by_rows, "end": actual_end, "start": EVAL_START}, ensure_ascii=False),
            encoding="utf-8",
        )
        snaps = {c: snap_index(by_rows.get(c) or []) for c in codes}
        print(f"  wrote {out_snap}", flush=True)

    book_defs = [
        ("LIVE1430-B45-S20", "b45", risk_b45, 5, None),
        ("LIVE1430-B50-S20", "b50", risk_b50, 5, None),
        ("LIVE1430-HYST-M3-S20", "hyst", risk_b45, 5, 3),
    ]
    hold_by: dict[str, dict[str, list[str]]] = {}
    sim_stats: dict[str, Any] = {}
    for name, _slug, rmap, mp, hyst_m in book_defs:
        print(f"simulate {name} (max_pos={mp}, hyst_m={hyst_m})…", flush=True)
        if hyst_m is not None:
            trades, hold, st = simulate_hyst(
                calendar,
                snaps,
                closes_w_sig,
                alias,
                aum,
                daily,
                rmap,
                sharpe_key,
                name,
                True,
                20,
                hyst_m,
            )
            n_cash = sum(1 for d in calendar[:-1] if not (hold.get(d) or []))
            st = {
                **st,
                "max_pos": mp,
                "n_cash_weeks": n_cash,
                "n_calendar_weeks_ex_last": max(0, len(calendar) - 1),
                "cash_week_pct": n_cash / max(1, len(calendar) - 1),
                "n_risk_on_weeks": sum(1 for d in calendar[:-1] if rmap.get(d)),
                "risk_on_week_pct": sum(1 for d in calendar[:-1] if rmap.get(d))
                / max(1, len(calendar) - 1),
            }
        else:
            trades, hold, st = simulate(
                calendar,
                snaps,
                closes_w_sig,
                alias,
                aum,
                daily,
                rmap,
                sharpe_key,
                name,
                True,
                20,
                mp,
            )
        hold_by[name] = hold
        sim_stats[name] = st
        rows = []
        for d in calendar[:-1]:
            codes_h = hold.get(d) or []
            rows.append(
                {
                    "date": d,
                    "risk_on": int(rmap.get(d, False)),
                    "n_held": len(codes_h),
                    "codes": ",".join(codes_h),
                }
            )
        pd.DataFrame(rows).to_csv(OUT / f"holdings_{name}.csv", index=False)
        pd.DataFrame(trades).to_csv(OUT / f"trades_{name}.csv", index=False)
        # nav placeholder filled later
        print(
            f"  entries={st['n_entries']} trades={st['n_trades']} "
            f"cands_weeks={st['n_fridays_with_cands']} cash_weeks={st['n_cash_weeks']} "
            f"({100*st['cash_week_pct']:.1f}%)",
            flush=True,
        )

    all_codes: set[str] = set()
    for h in hold_by.values():
        for cs in h.values():
            all_codes |= set(cs)
    all_codes.add(CASH_CODE)
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
    if CASH_CODE not in px_map:
        print(f"fetch tencent daily for {CASH_CODE}…", flush=True)
        px_map[CASH_CODE] = fetch_tencent_day(CASH_CODE)
        DAY_DIR.mkdir(parents=True, exist_ok=True)
        bars = [
            {"date": d.strftime("%Y-%m-%d"), "c": float(v)}
            for d, v in px_map[CASH_CODE].items()
        ]
        (DAY_DIR / f"{CASH_CODE}.json").write_text(
            json.dumps({"bars": bars}, ensure_ascii=False), encoding="utf-8"
        )
    px = pd.DataFrame(px_map).sort_index()
    px = px.loc[(px.index >= EVAL_START) & (px.index <= END_S)]
    R = px.pct_change()
    if "510300" in px.columns:
        days = px["510300"].dropna().index
    else:
        days = px.dropna(how="all").index
    # also allow days from any column if 510300 short
    days = days[(days >= EVAL_START) & (days <= END_S)]
    # extend calendar days using union if needed
    if len(days) and str(days[-1].date()) < actual_end:
        # try use sina/day union index from all daily
        all_idx = None
        for s in daily.values():
            all_idx = s.index if all_idx is None else all_idx.union(s.index)
        if all_idx is not None:
            days2 = all_idx[(all_idx >= EVAL_START) & (all_idx <= END_S)]
            if len(days2) > len(days):
                days = days2
    print(f"live days {days[0].date()} → {days[-1].date()} n={len(days)}", flush=True)

    hold_by["LIVE1430-TV33-S20"] = hold_by["LIVE1430-B45-S20"]
    hold_by["LIVE1430-CASH-511010"] = hold_by["LIVE1430-B45-S20"]
    sim_stats["LIVE1430-TV33-S20"] = sim_stats["LIVE1430-B45-S20"]
    sim_stats["LIVE1430-CASH-511010"] = sim_stats["LIVE1430-B45-S20"]

    nav_specs: list[tuple[str, float, str | None]] = [
        ("LIVE1430-B45-S20", SIGMA_STAR, None),
        ("LIVE1430-B50-S20", SIGMA_STAR, None),
        ("LIVE1430-TV33-S20", 0.33, None),
        ("LIVE1430-HYST-M3-S20", SIGMA_STAR, None),
        ("LIVE1430-CASH-511010", SIGMA_STAR, CASH_CODE),
    ]

    table_rows = []
    series: dict[str, pd.Series] = {}
    old_window: dict[str, dict[str, float]] = {}
    for name, sig, cash_fill in nav_specs:
        hd = {pd.Timestamp(d): cs for d, cs in hold_by[name].items()}
        r, L = run_live_tv(hd, days, px, R, sigma_star=sig, cash_fill=cash_fill)
        series[name] = r
        row = metrics_row(name, r, L, sim_stats[name])
        table_rows.append(row)
        old_window[name] = metrics_through_calendar_weeks(r, calendar, OLD_WINDOW_END)
        nav = (1 + r).cumprod()
        nav.to_csv(OUT / f"nav_{name}.csv", header=["nav"])
        st = stats_full(r)
        print(
            f"  {name}: ret={pct(st['ret'])} dd={pct(st['maxDD'])} "
            f"CAGR={pct(st['CAGR'])} Calmar={st['Calmar']:.2f} cash%={100*row['cash_week_pct']:.1f}",
            flush=True,
        )

    df = pd.DataFrame(table_rows)
    df.to_csv(OUT / "table.csv", index=False)
    (OUT / "metrics.csv").write_text(df.to_csv(index=False), encoding="utf-8")

    book_names = [n for n, _, _ in nav_specs]
    y = yearly_table(series["LIVE1430-B45-S20"]).rename(
        columns=lambda c: f"b45_{c}" if c != "year" else c
    )
    y.to_csv(OUT / "yearly.csv", index=False)

    eq = pd.DataFrame({k: (1 + series[k]).cumprod() for k in book_names})
    eq.to_csv(OUT / "equity.csv")
    eq.to_csv(OUT / "metrics_nav.csv")

    fig, ax = plt.subplots(figsize=(11, 5.5), dpi=120)
    for name in book_names:
        ax.plot(eq.index, eq[name], label=name, lw=1.6)
    ax.set_yscale("log")
    ax.set_title("SPIKE-S20-EXTEND-REBASE-LIVE1430（延窗复核）")
    ax.set_ylabel("净值（对数）")
    ax.grid(True, alpha=0.3)
    ax.legend(fontsize=7)
    fig.tight_layout()
    fig.savefig(OUT / "equity_curve.png")
    plt.close(fig)

    b45 = df[df.book == "LIVE1430-B45-S20"].iloc[0]
    b45_old = old_window["LIVE1430-B45-S20"]
    nob_ref_ret = 1.3399609137897461
    nob_ref_mdd = -0.18879764614342198
    nob_ref_cal = 0.704970180111173

    def leg_delta(row: pd.Series) -> dict[str, float]:
        dret = (row["ret"] - b45["ret"]) * 100
        ddd_abs = (abs(row["maxDD"]) - abs(b45["maxDD"])) * 100
        return {"dret_pp": dret, "d_absMDD_pp": ddd_abs, "covers": dret >= ddd_abs - 1e-9}

    leg_rows = {}
    falsify_legs = []
    for leg in ["LIVE1430-B50-S20", "LIVE1430-TV33-S20", "LIVE1430-HYST-M3-S20", "LIVE1430-CASH-511010"]:
        r = df[df.book == leg].iloc[0]
        d = leg_delta(r)
        leg_rows[leg] = d
        rear_ok = (
            not math.isnan(r["2023-26_ret"])
            and not math.isnan(b45["2023-26_ret"])
            and r["2023-26_ret"] >= b45["2023-26_ret"] - 0.03
        )
        if not (d["covers"] and rear_ok):
            falsify_legs.append(leg)

    b45_align = (
        abs(b45["ret"] - nob_ref_ret) < 0.03
        and abs(b45["maxDD"] - nob_ref_mdd) < 0.015
        and abs(b45["Calmar"] - nob_ref_cal) < 0.03
    )
    d_ext_ret = (b45["ret"] - b45_old["ret"]) * 100
    d_ext_mdd = (b45["maxDD"] - b45_old["maxDD"]) * 100

    if falsify_legs:
        verdict = (
            f"**延窗翻脸（不换冠）**：记正腿 {', '.join(falsify_legs)} 相对同窗 B45 "
            f"未同时满足 Δret 盖住 Δ|MDD| 与 2023–26 不塌；基线延窗 B45 ret={pct(float(b45['ret']))} "
            f"（旧窗止 {OLD_WINDOW_END} ret={pct(b45_old['ret'])}，Δ{d_ext_ret:+.1f}pp）。"
        )
        falsify = True
    else:
        verdict = (
            f"**延窗未翻脸（不换冠）**：B50/TV33/HYST-M3/CASH-511010 相对同窗 B45 仍满足探索尺子；"
            f"基线 B45 ret={pct(float(b45['ret']))} MDD={pct(float(b45['maxDD']))} Calmar={b45['Calmar']:.2f} "
            f"（对齐 nob_ref ~{pct(nob_ref_ret)}/{pct(nob_ref_mdd)}/C{nob_ref_cal:.2f}：{'OK' if b45_align else '偏离'}）；"
            f"旧窗止 {OLD_WINDOW_END} Δret={d_ext_ret:+.1f}pp ΔMDD={d_ext_mdd:+.1f}pp。"
        )
        falsify = False

    knife = KIT / "knives" / "SPIKE-S20-EXTEND-REBASE-LIVE1430.md"
    criterion_src = knife.read_text(encoding="utf-8") if knife.exists() else ""

    summary = {
        "title": "SPIKE-S20-EXTEND-REBASE-LIVE1430",
        "unique_change": "sample end extended to ≥2026-10-23 only; rules frozen",
        "sample": f"{EVAL_START} → {actual_end}",
        "old_window_end": OLD_WINDOW_END,
        "coverage": cov_stats,
        "sim_stats": sim_stats,
        "table": table_rows,
        "old_window_metrics": old_window,
        "b45_vs_nob_ref": {
            "ret": float(b45["ret"]),
            "maxDD": float(b45["maxDD"]),
            "Calmar": float(b45["Calmar"]),
            "nob_ref_ret": nob_ref_ret,
            "nob_ref_mdd": nob_ref_mdd,
            "nob_ref_calmar": nob_ref_cal,
            "aligned": b45_align,
        },
        "delta_legs_vs_b45": leg_rows,
        "falsify": falsify,
        "verdict": verdict,
        "elapsed_sec": round(time.time() - t0, 1),
    }
    (OUT / "summary.json").write_text(
        json.dumps(summary, ensure_ascii=False, indent=2, default=str), encoding="utf-8"
    )

    def row_md(name: str) -> str:
        r = df[df.book == name].iloc[0]
        return (
            f"| {name} | {pct(r['ret'])} | {pct(r['maxDD'])} | {pct(r['CAGR'])} | {r['Calmar']:.2f} | "
            f"{pct(r['2020-22_ret'])}/{pct(r['2020-22_DD'])}/{r['2020-22_Calmar']:.2f} | "
            f"{pct(r['2023-26_ret'])}/{pct(r['2023-26_DD'])}/{r['2023-26_Calmar']:.2f} | "
            f"{r['avgL']:.2f} | {100*r['cash_week_pct']:.1f}% |"
        )

    delta_lines = []
    for leg in ["LIVE1430-B50-S20", "LIVE1430-TV33-S20", "LIVE1430-HYST-M3-S20", "LIVE1430-CASH-511010"]:
        d = leg_rows[leg]
        delta_lines.append(
            f"- {leg}: Δret vs B45 {d['dret_pp']:+.1f}pp；Δ|MDD| {d['d_absMDD_pp']:+.1f}pp；"
            f"{'盖住' if d['covers'] else '未盖住'}"
        )

    approx_md = "\n".join(f"- {a}" for a in cov_stats["approximation"])
    report = f"""# REPORT · SPIKE-S20-EXTEND-REBASE-LIVE1430

## 1. 准则原文

```
{criterion_src.strip()}
```

## 2. 实现要点

- **唯一改动**：样本终点延至 **{actual_end}**（≥2026-10-23）；规则零改。
- **冻结**：Fri≥14:30/收盘；0.2%RT；L≤1；spike_ft max5 + SHARPE20 + E0 + TV25 基座；研究池。
- **引擎**：`CLOUD-BATCH-2026-10-26` kit + `scripts/` classify；研究缓存 week/day/sina/14:30/face。
- **红线**：不换冠；不写 strategy_exec / LIVE_OPS / 实盘池。

## 近似与覆盖

{approx_md}

| 覆盖 | 值 |
|---|---|
| 可投池（AUM≥2亿） | {len(codes)} |
| 日历周 | {len(calendar)}（{calendar[0]}→{actual_end}） |
| listed 行 14:30 非空率 | {100*nonnull_rate:.1f}% |
| 成功映射 qfq_1430 | {n_map} |
| B45 risk_on 周占比 | {100*float(b45['risk_on_week_pct']):.1f}% |

## 3. 主表（延窗 LIVE1430）

| book | ret | maxDD | CAGR | Calmar | 2020–22 ret/DD/C | 2023–26 ret/DD/C | avgL | cash周% |
|---|---:|---:|---:|---:|---|---|---:|---:|
{row_md("LIVE1430-B45-S20")}
{row_md("LIVE1430-B50-S20")}
{row_md("LIVE1430-TV33-S20")}
{row_md("LIVE1430-HYST-M3-S20")}
{row_md("LIVE1430-CASH-511010")}

### Δ · 记正腿 vs 同窗 B45

{chr(10).join(delta_lines)}

### Δ · B45 延窗 vs 旧窗（止 {OLD_WINDOW_END}）

| | 延窗 | 旧窗截断 | Δ |
|---|---:|---:|---:|
| ret | {pct(float(b45['ret']))} | {pct(b45_old['ret'])} | {d_ext_ret:+.1f}pp |
| maxDD | {pct(float(b45['maxDD']))} | {pct(b45_old['maxDD'])} | {d_ext_mdd:+.1f}pp |

旁注：nob_ref 同窗基线 ret={pct(nob_ref_ret)} MDD={pct(nob_ref_mdd)} Calmar={nob_ref_cal:.2f}；本跑 B45 对齐={'是' if b45_align else '否'}。

## 4. 一句证伪或通过

{verdict}

耗时约 {summary['elapsed_sec']}s。
"""
    (OUT / "REPORT.md").write_text(report, encoding="utf-8")
    print("done", OUT, flush=True)
    print(verdict, flush=True)
    print(f"FALSIFY={falsify} END={actual_end} B45_align={b45_align}", flush=True)


if __name__ == "__main__":
    main()
