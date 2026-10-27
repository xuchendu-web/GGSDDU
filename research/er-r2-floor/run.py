#!/usr/bin/env python3
"""ER-R2-FLOOR: R² / ER hard floor on B45+spike_ft max5+S20+E0+TV25 (btheta fork).

Four books: F0 + RF50 + ER20 + AND50. Research only — champion_swap=false.
Fork pin: 05f0f8a4 SPIKE-S20-BTHETA-GRID-LIVE1430/run.py
"""
from __future__ import annotations

import hashlib
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

ROOT = Path(__file__).resolve().parent
REPO = ROOT.parent.parent
KIT = ROOT.parent / "cloud_batch" / "CLOUD-BATCH-2026-10-26"
PIN_RUN = ROOT.parent / "cloud_batch" / "SPIKE-S20-BTHETA-GRID-LIVE1430" / "run.py"
SCRIPTS = KIT / "scripts"
sys.path.insert(0, str(SCRIPTS))

from backtest import KEEP, LIVE_PHASE, MIN_BARS, Position, nearest_date, snap_index  # noqa: E402
from build_scan import Bar, classify  # noqa: E402

OUT = ROOT / "out"
DESIGN_MD = ROOT / "DESIGN.md"
SOURCE_SHA = "05f0f8a4f778fde886f3e7b2976646ff4b7d777b"
BREADTH_B = 0.45

BOOKS: list[tuple[str, str, str]] = [
    ("F0", "LIVE1430-B45-S20-max5", "off"),
    ("RF50", "LIVE1430-B45-S20-RF50-max5", "r2"),
    ("ER20", "LIVE1430-B45-S20-ER20-max5", "er"),
    ("AND50", "LIVE1430-B45-S20-AND50-max5", "and"),
]

ANCHOR = {
    "ret": 1.316,
    "maxDD": -0.188,
    "Calmar": 0.70,
    "n_weeks": 349,
    "T": 348,
    "n_codes": 324,
    "end": "2026-10-23",
}
ANCHOR_TOL = {"ret": 0.005, "maxDD": 0.002, "Calmar": 0.02}

SKIPPED_FILLS = [
    "RET8",
    "RET12",
    "MOM121",
    "Z121",
    "R4W",
    "SORTINO20",
    "residual-mom",
    "corr-dedup",
    "Clenow-SR90",
    "Clenow-SR60",
    "Clenow-SR90K2",
    "AG40",
    "AG20",
    "Kaufman-ER10",
]

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
EVAL_START = "2020-01-03"
END_S = "2026-10-23"
COST_SIDE = 0.001
SIGMA_STAR = 0.25
LCAP = 1.0
LIVE_COST_RT = 0.002
CLASSIFY_WORKERS = 8
R2_N = 90
R2_THETA = 0.50
ER_N = 20
ER_THETA = 0.40


@dataclass
class Cand:
    code: str
    px: float
    fz: float | None
    aum: float
    sharpe: float | None
    r2: float | None = None
    er: float | None = None


RankFn = Callable[[Cand, list[Cand]], tuple]


def verify_pin_and_kit() -> None:
    if not PIN_RUN.is_file():
        raise SystemExit(f"BLOCKED: missing pin run.py at {PIN_RUN}", file=sys.stderr)
    try:
        expected = subprocess.check_output(
            ["git", "show", f"{SOURCE_SHA}:research/cloud_batch/SPIKE-S20-BTHETA-GRID-LIVE1430/run.py"],
            cwd=REPO,
        )
    except subprocess.CalledProcessError as exc:
        raise SystemExit(f"BLOCKED: cannot load pin SHA {SOURCE_SHA}: {exc}", file=sys.stderr)
    if hashlib.sha256(PIN_RUN.read_bytes()).digest() != hashlib.sha256(expected).digest():
        raise SystemExit(f"BLOCKED: pin run.py on disk != {SOURCE_SHA}", file=sys.stderr)
    for p in (KIT, SCRIPTS, WEEK, FACE, DAY_DIR, NOON_CSV, SINA_DAILY, SNAP_CACHE):
        if not Path(p).exists():
            raise SystemExit(f"BLOCKED: missing path {p}", file=sys.stderr)


def is_spike(snap: dict[str, Any] | None) -> bool:
    if not snap:
        return False
    if snap.get("pending_second_week") or snap.get("in_play_kind") == "box_pending":
        return False
    return bool(snap.get("in_play")) and snap.get("in_play_kind") == "spike_ft"


def sharpe_key(c: Cand, pool: list[Cand]) -> tuple:
    miss = 0 if c.sharpe is not None else 1
    return (miss, -(c.sharpe if c.sharpe is not None else 0.0), c.code)


def ols_r2(px: np.ndarray) -> float | None:
    n = int(px.size)
    if n < 2:
        return None
    if np.any(~np.isfinite(px)) or np.any(px <= 0):
        return None
    y = np.log(px.astype(float))
    t = np.arange(n, dtype=float)
    t0 = t - t.mean()
    y0 = y - y.mean()
    sxx = float(np.dot(t0, t0))
    syy = float(np.dot(y0, y0))
    sxy = float(np.dot(t0, y0))
    if sxx <= 0 or syy <= max(1e-24, 1e-14 * sxx) or not np.isfinite(sxx + syy + sxy):
        return None
    r2 = (sxy * sxy) / (sxx * syy)
    if not np.isfinite(r2):
        return None
    if r2 < -1e-12 or r2 > 1.0 + 1e-12:
        return None
    return float(min(1.0, max(0.0, r2)))


def r2_on(closes: pd.Series, d: str, n: int = 90) -> float | None:
    ts = pd.Timestamp(d)
    sub = closes.loc[: ts - pd.Timedelta(days=1)]
    if len(sub) < n:
        return None
    if (ts - sub.index[-1]).days > 5:
        return None
    window = sub.iloc[-n:]
    if len(window) < n:
        return None
    return ols_r2(window.to_numpy(dtype=float))


def kaufman_er(closes: pd.Series, d: str, n: int = 20) -> float | None:
    ts = pd.Timestamp(d)
    sub = closes.loc[: ts - pd.Timedelta(days=1)]
    if len(sub) < n + 1:
        return None
    if (ts - sub.index[-1]).days > 5:
        return None
    window = sub.iloc[-(n + 1) :]
    diffs = window.diff().abs().iloc[1:]
    if len(diffs) != n:
        return None
    denom = float(diffs.sum())
    if denom <= 0 or not np.isfinite(denom):
        return None
    num = abs(float(window.iloc[-1]) - float(window.iloc[0]))
    if not np.isfinite(num):
        return None
    er = num / denom
    if not np.isfinite(er):
        return None
    return float(er)


def floor_pass(mode: str, r2: float | None, er: float | None) -> bool:
    if mode == "r2":
        return r2 is not None and r2 >= R2_THETA
    if mode == "er":
        return er is not None and er >= ER_THETA
    if mode == "and":
        return (r2 is not None and r2 >= R2_THETA) and (er is not None and er >= ER_THETA)
    if mode == "off":
        return True
    raise ValueError(mode)


def run_fixtures() -> None:
    idx90 = pd.date_range("2020-01-01", periods=90, freq="B")
    sig = (idx90[-1] + pd.Timedelta(days=2)).strftime("%Y-%m-%d")
    p_up = np.exp(0.001 * np.arange(90))
    s_up = pd.Series(p_up, index=idx90)
    r2_up = r2_on(s_up, sig, 90)
    if r2_up is None or abs(r2_up - 1.0) >= 1e-12:
        raise SystemExit(f"fixture perfect up R2 fail {r2_up}")
    if not floor_pass("r2", r2_up, None):
        raise SystemExit("fixture RF50 should pass perfect up")

    p_dn = np.exp(-0.001 * np.arange(90))
    s_dn = pd.Series(p_dn, index=idx90)
    r2_dn = r2_on(s_dn, sig, 90)
    if r2_dn is None or abs(r2_dn - 1.0) >= 1e-12:
        raise SystemExit(f"fixture perfect down R2 fail {r2_dn}")

    flat90 = pd.Series([10.0] * 90, index=idx90)
    if r2_on(flat90, sig, 90) is not None:
        raise SystemExit("fixture flat R2 should be None")

    gap_idx = pd.date_range("2020-01-01", periods=90, freq="B")
    gap_sig = (gap_idx[-1] + pd.Timedelta(days=10)).strftime("%Y-%m-%d")
    if r2_on(s_up, gap_sig, 90) is not None:
        raise SystemExit("fixture R2 gap should be None")

    short = pd.Series(p_up[:89], index=gap_idx[:89])
    if r2_on(short, sig, 90) is not None:
        raise SystemExit("fixture R2 short should be None")

    bad = pd.Series(p_up.copy(), index=idx90)
    bad.iloc[10] = -1.0
    if r2_on(bad, sig, 90) is not None:
        raise SystemExit("fixture nonpositive should be None")

    amp = 0.08
    zig = np.exp(0.001 * np.arange(90) + amp * ((-1) ** np.arange(90)))
    r2_zig = r2_on(pd.Series(zig, index=idx90), sig, 90)
    if r2_zig is None or r2_zig >= 0.50:
        amp = 0.12
        zig = np.exp(0.001 * np.arange(90) + amp * ((-1) ** np.arange(90)))
        r2_zig = r2_on(pd.Series(zig, index=idx90), sig, 90)
    if r2_zig is None or r2_zig >= 0.50:
        raise SystemExit(f"fixture zigzag R2 fail {r2_zig}")

    shape_a = np.exp(0.001 * np.arange(90))
    shape_b = np.exp(0.002 * np.arange(90))
    r2_a = ols_r2(shape_a)
    r2_b = ols_r2(shape_b)
    if r2_a is None or r2_b is None or abs(r2_a - r2_b) >= 1e-12:
        raise SystemExit(f"fixture shape invariance fail {r2_a} {r2_b}")

    er_idx = pd.date_range("2020-01-01", periods=21, freq="B")
    er_sig = (er_idx[-1] + pd.Timedelta(days=2)).strftime("%Y-%m-%d")
    er_up = pd.Series(np.arange(10, 31, dtype=float), index=er_idx)
    er_u = kaufman_er(er_up, er_sig, 20)
    if er_u is None or not (0.999999 <= er_u <= 1.000001):
        raise SystemExit(f"fixture ER monotonic fail {er_u}")

    chop_vals = [10.0, 11.0] * 10 + [10.0]
    er_chop = pd.Series(chop_vals, index=er_idx)
    er_c = kaufman_er(er_chop, er_sig, 20)
    if er_c is None or not (-1e-12 <= er_c <= 1e-12):
        raise SystemExit(f"fixture ER chop fail {er_c}")

    er_flat = pd.Series([10.0] * 21, index=er_idx)
    if kaufman_er(er_flat, er_sig, 20) is not None:
        raise SystemExit("fixture ER flat should be None")

    mix_vals = [10.0, 20.0] * 5 + list(range(21, 32))
    mix = pd.Series([float(x) for x in mix_vals], index=er_idx)
    er10 = kaufman_er(mix, er_sig, 10)
    er20 = kaufman_er(mix, er_sig, 20)
    if er10 is None or abs(er10 - 1.0) >= 1e-12:
        raise SystemExit(f"fixture ER10 should be 1 got {er10}")
    if er20 is None or not (0.20 < er20 < 0.22):
        raise SystemExit(f"fixture ER20 window fail {er20}")

    if floor_pass("and", 1.0, 0.0):
        raise SystemExit("AND fixture 1 fail")
    if floor_pass("and", None, 1.0):
        raise SystemExit("AND fixture 2 fail")
    if not floor_pass("and", 1.0, 1.0):
        raise SystemExit("AND fixture 3 fail")


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
                s = px if s is None else px.combine_first(s).sort_index()
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
    floor_mode: str,
    require_sharpe: bool,
    sharpe_n: int | None,
    max_pos: int,
) -> tuple[list[dict[str, Any]], dict[str, list[str]], dict[str, Any], list[dict[str, Any]]]:
    cash = 1.0
    positions: dict[str, Position] = {}
    trades: list[dict[str, Any]] = []
    picks: dict[str, list[str]] = {}
    n_tight = 0
    n_feat = 0
    n_entries = 0
    n_miss_sharpe = 0
    n_r2_blocked = 0
    n_er_blocked = 0
    n_floor_blocked = 0
    n_miss_r2 = 0
    n_miss_er = 0
    n_empty_slots = 0
    abs_d_vals: list[int] = []
    r2_fills: list[float] = []
    er_fills: list[float] = []
    rank_rows: list[dict[str, Any]] = []
    entry_rows: list[dict[str, Any]] = []

    def px_on(code: str, d: str) -> float | None:
        return closes_w.get(code, {}).get((alias.get(code) or {}).get(d) or d)

    def snap_at(code: str, d: str) -> dict[str, Any] | None:
        key = (alias.get(code) or {}).get(d) or d
        return snaps.get(code, {}).get(key)

    def equity_now() -> float:
        return cash + sum(p.shares * p.last_px for p in positions.values())

    def dt_count(d: str) -> int:
        n = 0
        for code in snaps:
            sn = snap_at(code, d)
            if not is_spike(sn):
                continue
            px = px_on(code, d)
            if px is None or px <= 0:
                continue
            sh = None
            if sharpe_n is not None and code in daily:
                sh = sharpe_n_on(daily[code], d, sharpe_n)
            if require_sharpe and sh is None:
                continue
            n += 1
        return n

    def build_cands(d: str, skip: set[str]) -> list[Cand]:
        nonlocal n_r2_blocked, n_er_blocked, n_floor_blocked, n_miss_r2, n_miss_er
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
            if require_sharpe and sh is None:
                continue

            r2 = er = None
            if floor_mode == "r2":
                if code not in daily:
                    n_r2_blocked += 1
                    continue
                r2 = r2_on(daily[code], d, R2_N)
                if r2 is None:
                    n_miss_r2 += 1
                if r2 is None or r2 < R2_THETA:
                    n_r2_blocked += 1
                    continue
            elif floor_mode == "er":
                if code not in daily:
                    n_er_blocked += 1
                    continue
                er = kaufman_er(daily[code], d, ER_N)
                if er is None:
                    n_miss_er += 1
                if er is None or er < ER_THETA:
                    n_er_blocked += 1
                    continue
            elif floor_mode == "and":
                if code not in daily:
                    n_r2_blocked += 1
                    n_er_blocked += 1
                    n_floor_blocked += 1
                    continue
                r2 = r2_on(daily[code], d, R2_N)
                er = kaufman_er(daily[code], d, ER_N)
                r2_fail = r2 is None or r2 < R2_THETA
                er_fail = er is None or er < ER_THETA
                if r2 is None:
                    n_miss_r2 += 1
                if er is None:
                    n_miss_er += 1
                if r2_fail:
                    n_r2_blocked += 1
                if er_fail:
                    n_er_blocked += 1
                if r2_fail or er_fail:
                    n_floor_blocked += 1
                    continue
            fz = sn.get("falsify_close") if sn else None
            out.append(
                Cand(
                    code=code,
                    px=px,
                    fz=float(fz) if fz is not None else None,
                    aum=aum.get(code) or 0.0,
                    sharpe=sh,
                    r2=r2,
                    er=er,
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
            ndt = dt_count(d)
            if ndt >= 1:
                abs_d_vals.append(ndt)
            pool = build_cands(d, set(positions))
            slots = max_pos - len(positions)
            if pool:
                n_feat += 1
            if slots > 0 and len(pool) > slots:
                n_tight += 1
            if slots > 0 and pool:
                pool_rank = [c for c in pool if c.sharpe is not None] if require_sharpe else pool
                take = sorted(pool_rank, key=lambda c: rank_fn(c, pool_rank))[:slots]
                n_empty_slots += max(0, slots - len(take))
                for c in take:
                    n_entries += 1
                    if c.sharpe is None:
                        n_miss_sharpe += 1
                    if c.r2 is not None:
                        r2_fills.append(c.r2)
                    if c.er is not None:
                        er_fills.append(c.er)
                    entry_rows.append({"date": d, "code": c.code, "px": c.px})
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
            elif slots > 0:
                n_empty_slots += slots

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
    for d in calendar:
        for code in exits_by_day.get(d, []):
            open_codes.discard(code)
        for code in picks.get(d, []):
            open_codes.add(code)
        hold[d] = sorted(open_codes)

    n_cash = sum(1 for d in calendar[:-1] if not (hold.get(d) or []))
    if floor_mode == "r2":
        n_floor_blocked = n_r2_blocked
    elif floor_mode == "er":
        n_floor_blocked = n_er_blocked

    stats = {
        "n_fridays_queue_gt_seats": n_tight,
        "n_fridays_with_cands": n_feat,
        "n_entries": n_entries,
        "n_entries_missing_sharpe": n_miss_sharpe,
        "n_trades": len(trades),
        "max_pos": max_pos,
        "n_cash_weeks": n_cash,
        "n_calendar_weeks_ex_last": max(0, len(calendar) - 1),
        "n_r2_blocked": n_r2_blocked if floor_mode in ("r2", "and") else 0,
        "n_er_blocked": n_er_blocked if floor_mode in ("er", "and") else 0,
        "n_floor_blocked": n_floor_blocked if floor_mode != "off" else 0,
        "n_miss_r2": n_miss_r2 if floor_mode in ("r2", "and") else 0,
        "n_miss_er": n_miss_er if floor_mode in ("er", "and") else 0,
        "n_empty_slots": n_empty_slots,
        "mean_r2": float(np.mean(r2_fills)) if r2_fills else 0.0,
        "mean_er": float(np.mean(er_fills)) if er_fills else 0.0,
        "mean_abs_D": float(np.mean(abs_d_vals)) if abs_d_vals else 0.0,
    }
    if rank_rows:
        pd.DataFrame(rank_rows).to_csv(OUT / f"entries_{variant}.csv", index=False)
    return trades, hold, stats, entry_rows


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


def window_stats(r: pd.Series, start: str, end: str | None = None) -> dict[str, float]:
    sub = r[r.index >= pd.Timestamp(start)]
    if end:
        sub = sub[sub.index <= pd.Timestamp(end)]
    return stats_full(sub) if len(sub) > 5 else {k: float("nan") for k in ("ret", "maxDD", "CAGR", "Calmar")}


def pct(x: float | None) -> str:
    if x is None or (isinstance(x, float) and (math.isnan(x) or math.isinf(x))):
        return "—"
    return f"{100 * x:.1f}%"


def entry_quality(
    entry_rows: list[dict[str, Any]], calendar: list[str], closes_w: dict[str, dict[str, float]]
) -> tuple[float, float]:
    cal_idx = {d: i for i, d in enumerate(calendar)}
    rets: list[float] = []
    for row in entry_rows:
        d = row["date"]
        code = row["code"]
        i = cal_idx.get(d)
        if i is None or i + 1 >= len(calendar):
            continue
        d2 = calendar[i + 1]
        p0 = closes_w.get(code, {}).get(d)
        p1 = closes_w.get(code, {}).get(d2)
        if p0 is None or p1 is None or p0 <= 0:
            continue
        rets.append(float(p1 / p0 - 1))
    if not rets:
        return float("nan"), float("nan")
    wins = [x for x in rets if x > 0]
    losses = [x for x in rets if x <= 0]
    hit = len(wins) / len(rets)
    win_size = float(np.mean(wins) / abs(np.mean(losses))) if wins and losses else float("nan")
    return hit, win_size


def jaccard_entries(a: list[dict[str, Any]], b: list[dict[str, Any]]) -> float:
    sa = {(e["date"], e["code"]) for e in a}
    sb = {(e["date"], e["code"]) for e in b}
    if not sa and not sb:
        return 1.0
    if not sa or not sb:
        return 0.0
    return len(sa & sb) / len(sa | sb)


def weekly_hold_sets(hold: dict[str, list[str]], calendar: list[str]) -> list[frozenset[str]]:
    return [frozenset(hold.get(d) or []) for d in calendar[:-1]]


def is_inert(
    bid: str,
    hold: dict[str, list[str]],
    f0_hold: dict[str, list[str]],
    calendar: list[str],
    n_floor_blocked: int,
    n_empty_slots: int,
    f0_empty: int,
) -> bool:
    if bid == "F0":
        return False
    if weekly_hold_sets(hold, calendar) == weekly_hold_sets(f0_hold, calendar):
        return True
    return n_floor_blocked == 0 and n_empty_slots == f0_empty


def check_anchor(f0: dict[str, Any], n_weeks: int, n_codes: int, end: str) -> bool:
    if end != ANCHOR["end"]:
        return False
    if n_weeks != ANCHOR["n_weeks"] or f0.get("T") != ANCHOR["T"] or n_codes != ANCHOR["n_codes"]:
        return False
    if abs(f0["ret"] - ANCHOR["ret"]) > ANCHOR_TOL["ret"]:
        return False
    if abs(f0["maxDD"] - ANCHOR["maxDD"]) > ANCHOR_TOL["maxDD"]:
        return False
    if abs(f0["Calmar"] - ANCHOR["Calmar"]) > ANCHOR_TOL["Calmar"]:
        return False
    return True


def ruler_cell(f0: dict[str, Any], row: dict[str, Any], blocked: bool) -> dict[str, Any]:
    if blocked:
        row.update(
            {
                "delta_ret": 0.0,
                "delta_abs_mdd": 0.0,
                "covers": False,
                "window_2020_22": False,
                "window_2023_26": False,
                "verdict": "BLOCKED",
            }
        )
        return row
    if row["id"] == "F0":
        row.update(
            {
                "delta_ret": 0.0,
                "delta_abs_mdd": 0.0,
                "covers": True,
                "window_2020_22": True,
                "window_2023_26": True,
                "verdict": "ANCHOR",
            }
        )
        return row
    dret = row["ret"] - f0["ret"]
    d_abs = abs(row["maxDD"]) - abs(f0["maxDD"])
    w22 = row["w2020_22"]["ret"] >= f0["w2020_22"]["ret"]
    w23 = row["w2023_26"]["ret"] >= f0["w2023_26"]["ret"]
    covers = dret >= d_abs
    positive = covers and w22 and w23 and not row.get("inert", False)
    row["delta_ret"] = dret
    row["delta_abs_mdd"] = d_abs
    row["covers"] = covers
    row["window_2020_22"] = w22
    row["window_2023_26"] = w23
    row["verdict"] = "记正" if positive else "证伪"
    return row


def nav_at(nav: pd.Series, d: str) -> float:
    ts = pd.Timestamp(d)
    sub = nav.loc[:ts]
    if len(sub) == 0:
        return 1.0
    return float(sub.iloc[-1])


def weekly_excess(nav_book: pd.Series, nav_f0: pd.Series, calendar: list[str]) -> tuple[list[str], list[float], list[float]]:
    weeks = calendar[:-1]
    ex: list[float] = []
    for i in range(len(weeks) - 1):
        d0, d1 = weeks[i], weeks[i + 1]
        r_b = nav_at(nav_book, d1) / nav_at(nav_book, d0) - 1
        r_f = nav_at(nav_f0, d1) / nav_at(nav_f0, d0) - 1
        ex.append(r_b - r_f)
    cum = list(np.cumsum(ex))
    return weeks[1:], ex, cum


def best_segment(cum: list[float], maximize: bool) -> tuple[int, int, float]:
    best_val = -math.inf if maximize else math.inf
    best_i, best_j = 0, 0
    n = len(cum)
    for i in range(n):
        for j in range(i + 1, n):
            val = cum[j] - cum[i]
            if maximize:
                if val > best_val or (
                    abs(val - best_val) < 1e-15 and (i < best_i or (i == best_i and (j - i) < (best_j - best_i)))
                ):
                    if val > best_val or (abs(val - best_val) < 1e-15 and i < best_i):
                        best_val = val
                        best_i, best_j = i, j
            else:
                if val < best_val or (
                    abs(val - best_val) < 1e-15 and (i < best_i or (i == best_i and (j - i) < (best_j - best_i)))
                ):
                    if val < best_val or (abs(val - best_val) < 1e-15 and i < best_i):
                        best_val = val
                        best_i, best_j = i, j
    if not cum:
        return 0, 0, 0.0
    return best_i, best_j, best_val


def top_codes_in_segment(
    hold: dict[str, list[str]], calendar: list[str], start: str, end: str, limit: int = 8
) -> str:
    counts: dict[str, int] = defaultdict(int)
    for d in calendar:
        if d < start or d > end:
            continue
        for c in hold.get(d) or []:
            counts[c] += 1
    ordered = sorted(counts.items(), key=lambda x: (-x[1], x[0]))
    return ";".join(c for c, _ in ordered[:limit])


def build_entries_diff_csv(f0_entries: list[dict[str, Any]], entry_by: dict[str, list[dict[str, Any]]]) -> pd.DataFrame:
    rows: list[dict[str, Any]] = []
    f0_set = {(e["date"], e["code"]) for e in f0_entries}
    for bid, _, _ in BOOKS:
        if bid == "F0":
            continue
        book_set = {(e["date"], e["code"]) for e in entry_by[bid]}
        adds = book_set - f0_set
        drops = f0_set - book_set
        events: dict[tuple[int, str, str, str], list[str]] = defaultdict(list)
        for d, code in adds:
            events[(int(d[:4]), bid, "ADD", code)].append(d)
        for d, code in drops:
            events[(int(d[:4]), bid, "DROP", code)].append(d)
        for (year, bid2, side, code), dates in sorted(events.items()):
            rows.append(
                {
                    "year": year,
                    "id": bid2,
                    "side": side,
                    "code": code,
                    "n_events": len(dates),
                    "first_date": min(dates),
                    "last_date": max(dates),
                }
            )
    return pd.DataFrame(rows)


def build_segment_attribution(
    nav_by_book: dict[str, pd.Series],
    hold_by: dict[str, dict[str, list[str]]],
    f0_book: str,
    calendar: list[str],
    inert_ids: set[str],
) -> pd.DataFrame:
    rows: list[dict[str, Any]] = []
    nav_f0 = nav_by_book[f0_book]
    hold_f0 = hold_by[f0_book]
    for bid, book, _ in BOOKS:
        if bid == "F0":
            continue
        week_ends, _, cum = weekly_excess(nav_by_book[book], nav_f0, calendar)
        if inert_ids.intersection({bid}) or not cum:
            for kind in ("BIGWIN", "BIGLOSS"):
                rows.append(
                    {
                        "id": bid,
                        "kind": kind,
                        "start": calendar[0],
                        "end": calendar[-2] if len(calendar) > 1 else calendar[0],
                        "years": f"{calendar[0][:4]}-{calendar[-2][:4]}",
                        "delta_cum_ex": 0.0,
                        "n_weeks": 0,
                        "uniq_book": "",
                        "uniq_f0": "",
                        "n_shared": 0,
                    }
                )
            continue
        i_w, j_w, d_win = best_segment(cum, True)
        i_l, j_l, d_loss = best_segment(cum, False)
        for kind, i, j, delta in (("BIGWIN", i_w, j_w, d_win), ("BIGLOSS", i_l, j_l, d_loss)):
            start = week_ends[i] if i < len(week_ends) else calendar[0]
            end = week_ends[j] if j < len(week_ends) else calendar[-2]
            y0, y1 = start[:4], end[:4]
            years = y0 if y0 == y1 else f"{y0}-{y1}"
            ub = top_codes_in_segment(hold_by[book], calendar, start, end)
            uf = top_codes_in_segment(hold_f0, calendar, start, end)
            shared = len(set(ub.split(";")) & set(uf.split(";"))) if ub and uf else 0
            rows.append(
                {
                    "id": bid,
                    "kind": kind,
                    "start": start,
                    "end": end,
                    "years": years,
                    "delta_cum_ex": float(delta),
                    "n_weeks": j - i,
                    "uniq_book": ub,
                    "uniq_f0": uf,
                    "n_shared": shared,
                }
            )
    return pd.DataFrame(rows)


def mode_params(mode: str) -> dict[str, Any]:
    if mode == "off":
        return {"r2_n": 0, "r2_theta": 0.0, "er_n": 0, "er_theta": 0.0}
    if mode == "r2":
        return {"r2_n": R2_N, "r2_theta": R2_THETA, "er_n": 0, "er_theta": 0.0}
    if mode == "er":
        return {"r2_n": 0, "r2_theta": 0.0, "er_n": ER_N, "er_theta": ER_THETA}
    if mode == "and":
        return {"r2_n": R2_N, "r2_theta": R2_THETA, "er_n": ER_N, "er_theta": ER_THETA}
    raise ValueError(mode)


def write_attribution_report(
    cells: list[dict[str, Any]],
    f0: dict[str, Any],
    diff_df: pd.DataFrame,
    seg_df: pd.DataFrame,
    inert_ids: set[str],
) -> str:
    lines = ["## ATTRIBUTION", ""]
    lines.append(
        "**(a) 机制**：仅对新开/换入加 R²(N=90)≥0.50 / ER(N=20)≥0.40 硬闸；"
        "B45、spike_ft、max5、E0、TV25、SHARPE20 填席、周五≥14:30、0.2%RT、AUM≥2 未动。"
    )
    lines.append("")
    lines.append("**(b) 席位**：Jaccard vs F0 — " + ", ".join(f"{c['id']}={c['jaccard_vs_f0']:.3f}" for c in cells if c["id"] != "F0"))
    lines.append("")
    lines.append("**(c) 分段**：Δret 与踏空（见 Δ 表）；2020–22 / 2023–26 均以 F0 同窗 ret 为尺。")
    for c in cells:
        if c["id"] == "F0":
            continue
        lines.append(
            f"- {c['id']}: Δret={100*c['delta_ret']:+.1f}pp；2020–22 {'过' if c['window_2020_22'] else '踏空'}；"
            f"2023–26 {'过' if c['window_2023_26'] else '踏空'}"
        )
    lines.append("")
    lines.append("**(d) 换手与空仓周**（相对 F0）：")
    for c in cells:
        if c["id"] == "F0":
            continue
        lines.append(
            f"- {c['id']}: Δ换手={c['avg_turnover_1way']-f0['avg_turnover_1way']:+.4f}；"
            f"Δ空仓周={c['n_cash_weeks']-f0['n_cash_weeks']:+d}；n_empty_slots={c['n_empty_slots']} (F0={f0['n_empty_slots']})"
        )
    lines.append("")
    lines.append("**(e) 名字·年份与大赢/大亏段**：")
    for bid, _, _ in BOOKS:
        if bid == "F0":
            continue
        if bid in inert_ids:
            lines.append(f"- {bid}：与 F0 席位逐周相同，无名字可列（segment CSV 仍含 BIGWIN/BIGLOSS 占位）。")
            continue
        sub = diff_df[diff_df["id"] == bid]
        for year in sorted(sub["year"].unique()):
            ysub = sub[sub["year"] == year]
            adds = ysub[ysub["side"] == "ADD"].sort_values("n_events", ascending=False).head(5)
            drops = ysub[ysub["side"] == "DROP"].sort_values("n_events", ascending=False).head(5)
            if len(adds) or len(drops):
                lines.append(f"- {bid} {year} ADD: " + ", ".join(f"{r.code}({r.n_events})" for r in adds.itertuples()) or "—")
                lines.append(f"  DROP: " + ", ".join(f"{r.code}({r.n_events})" for r in drops.itertuples()) or "—")
        for kind in ("BIGWIN", "BIGLOSS"):
            row = seg_df[(seg_df["id"] == bid) & (seg_df["kind"] == kind)].iloc[0]
            lines.append(
                f"- {bid} {kind}: {row['start']}→{row['end']} ({row['years']}) Δcum_ex={row['delta_cum_ex']:.4f}；"
                f"uniq_book={row['uniq_book'] or '—'}；uniq_f0={row['uniq_f0'] or '—'}"
            )
    lines.append("")
    lines.append("ATTRIBUTION 不进 verdict。")
    return "\n".join(lines)


def main() -> None:
    run_fixtures()
    verify_pin_and_kit()
    OUT.mkdir(parents=True, exist_ok=True)
    t0 = time.time()

    print("load universe + extended 14:30 + week...", flush=True)
    uni = pd.read_csv(UNI_CSV)
    uni["code"] = uni["code"].astype(str).str.zfill(6)
    uni = uni[uni["aum"] >= 2].copy()
    codes = uni["code"].tolist()
    aum = {r.code: float(r.aum or 0) for r in uni.itertuples()}
    code_set = set(codes)

    noon = pd.read_csv(NOON_CSV)
    noon["code"] = noon["etf_code"].astype(str).str.split(".").str[0]
    noon["trade_date"] = noon["trade_date"].astype(str).str[:10]
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

    breadth_b: dict[str, float] = {}
    for _, row in face.iterrows():
        d = str(row["date"])[:10]
        bv = row.get("b")
        if bv is not None and not (isinstance(bv, float) and math.isnan(bv)):
            breadth_b[d] = float(bv)

    risk_on_map: dict[str, bool] = {}
    for d in calendar:
        b = breadth_b.get(d)
        risk_on_map[d] = bool(b is not None and b >= BREADTH_B)
    risk_on_map[calendar[-1]] = False

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

    hold_by: dict[str, dict[str, list[str]]] = {}
    sim_stats: dict[str, Any] = {}
    entry_by: dict[str, list[dict[str, Any]]] = {}
    for bid, book, mode in BOOKS:
        print(f"simulate {bid} {book}...", flush=True)
        trades, hold, st, ent = simulate(
            calendar,
            snaps,
            closes_w_sig,
            alias,
            aum,
            daily,
            risk_on_map,
            sharpe_key,
            bid,
            mode,
            True,
            20,
            5,
        )
        hold_by[book] = hold
        sim_stats[book] = st
        entry_by[bid] = ent
        pd.DataFrame(trades).to_csv(OUT / f"trades_{bid}.csv", index=False)

    all_codes: set[str] = set()
    for h in hold_by.values():
        for cs in h.values():
            all_codes |= set(cs)
    px_map = {c: daily[c] for c in sorted(all_codes) if c in daily}
    px = pd.DataFrame(px_map).sort_index()
    px = px.loc[(px.index >= EVAL_START) & (px.index <= END_S)]
    R = px.pct_change()
    days = px.dropna(how="all").index
    days = days[(days >= EVAL_START) & (days <= END_S)]

    f0_book = BOOKS[0][1]
    f0_hold = hold_by[f0_book]
    f0_empty = sim_stats[f0_book]["n_empty_slots"]

    cells: list[dict[str, Any]] = []
    nav_by_book: dict[str, pd.Series] = {}
    for bid, book, mode in BOOKS:
        hd = {pd.Timestamp(d): cs for d, cs in hold_by[book].items()}
        r, L, avg_to = run_live_tv(hd, days, px, R)
        nav = (1 + r).cumprod()
        nav_by_book[book] = nav
        st_nav = stats_full(r)
        w22 = window_stats(r, "2020-01-01", "2022-12-31")
        w23 = window_stats(r, "2023-01-01")
        hit, win_size = entry_quality(entry_by[bid], calendar, closes_w_sig)
        sim = sim_stats[book]
        mp = mode_params(mode)
        jac = 1.0 if bid == "F0" else jaccard_entries(entry_by[bid], entry_by["F0"])
        inert = is_inert(
            bid,
            hold_by[book],
            f0_hold,
            calendar,
            sim["n_floor_blocked"],
            sim["n_empty_slots"],
            f0_empty,
        )
        cells.append(
            {
                "id": bid,
                "book": book,
                "mode": mode,
                **mp,
                "ret": st_nav["ret"],
                "maxDD": st_nav["maxDD"],
                "CAGR": st_nav["CAGR"],
                "Calmar": st_nav["Calmar"],
                "avgL": float(L[L > 0].mean()) if (L > 0).any() else 0.0,
                "avg_turnover_1way": avg_to,
                "n_cash_weeks": sim["n_cash_weeks"],
                "n_entries": sim["n_entries"],
                "n_r2_blocked": sim["n_r2_blocked"],
                "n_er_blocked": sim["n_er_blocked"],
                "n_floor_blocked": sim["n_floor_blocked"],
                "n_miss_r2": sim["n_miss_r2"],
                "n_miss_er": sim["n_miss_er"],
                "n_empty_slots": sim["n_empty_slots"],
                "mean_r2": sim["mean_r2"],
                "mean_er": sim["mean_er"],
                "mean_abs_D": sim["mean_abs_D"],
                "hit_rate": hit,
                "win_size": win_size,
                "jaccard_vs_f0": jac,
                "inert": inert,
                "w2020_22": w22,
                "w2023_26": w23,
                "T": max(0, len(calendar) - 1),
            }
        )
        print(f"  {bid}: ret={pct(st_nav['ret'])} dd={pct(st_nav['maxDD'])} Calmar={st_nav['Calmar']:.2f}", flush=True)

    f0 = next(c for c in cells if c["id"] == "F0")
    anchor_pass = check_anchor(f0, len(calendar), len(codes), actual_end)
    blocked_anchor = not anchor_pass
    for c in cells:
        ruler_cell(f0, c, blocked_anchor)

    inert_ids = {c["id"] for c in cells if c.get("inert")}

    diff_df = build_entries_diff_csv(entry_by["F0"], entry_by)
    diff_df.to_csv(OUT / "entries_diff_by_year.csv", index=False)
    seg_df = build_segment_attribution(nav_by_book, hold_by, f0_book, calendar, inert_ids)
    seg_df.to_csv(OUT / "segment_attribution.csv", index=False)

    attrib_pass = True
    design_text = DESIGN_MD.read_text(encoding="utf-8") if DESIGN_MD.exists() else ""
    qline = design_text.splitlines()[2] if len(design_text.splitlines()) > 2 else ""
    h1_block = ""
    if "## H1" in design_text:
        part = design_text.split("## H1", 1)[1].split("## ", 1)[0]
        if "```" in part:
            inner = part.split("```", 2)[1]
            h1_block = "```\n" + inner.strip() + "\n```"

    attrib_body = write_attribution_report(cells, f0, diff_df, seg_df, inert_ids)

    positive_ids = [c["id"] for c in cells if c["verdict"] == "记正"]
    if not anchor_pass:
        family_verdict = "BLOCKED"
        h1_line = "锚点未过 — family BLOCKED"
    elif not attrib_pass:
        family_verdict = "BLOCKED"
        h1_line = "ATTRIBUTION 未齐 — family BLOCKED"
    elif positive_ids:
        family_verdict = "H1_REJECT"
        h1_line = f"记正: {', '.join(positive_ids)}"
    else:
        family_verdict = "H1_HOLD"
        h1_line = "RF50/ER20/AND50 all 证伪"

    table_cols = [
        "id",
        "book",
        "mode",
        "r2_n",
        "r2_theta",
        "er_n",
        "er_theta",
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
        "n_r2_blocked",
        "n_er_blocked",
        "n_floor_blocked",
        "n_miss_r2",
        "n_miss_er",
        "n_empty_slots",
        "mean_r2",
        "mean_er",
        "mean_abs_D",
        "hit_rate",
        "win_size",
        "jaccard_vs_f0",
        "inert",
        "delta_ret",
        "delta_abs_mdd",
        "covers",
        "window_2020_22",
        "window_2023_26",
        "verdict",
    ]
    csv_rows = []
    for c in cells:
        csv_rows.append(
            {
                **{k: c[k] for k in table_cols if k in c},
                "w2020_22_ret": c["w2020_22"]["ret"],
                "w2020_22_maxDD": c["w2020_22"]["maxDD"],
                "w2020_22_Calmar": c["w2020_22"]["Calmar"],
                "w2023_26_ret": c["w2023_26"]["ret"],
                "w2023_26_maxDD": c["w2023_26"]["maxDD"],
                "w2023_26_Calmar": c["w2023_26"]["Calmar"],
                "covers": str(c["covers"]).lower(),
                "window_2020_22": str(c["window_2020_22"]).lower(),
                "window_2023_26": str(c["window_2023_26"]).lower(),
                "inert": str(c["inert"]).lower(),
            }
        )
    pd.DataFrame(csv_rows)[table_cols].to_csv(OUT / "table.csv", index=False)

    eq_long = []
    for _, book, _ in BOOKS:
        nav = nav_by_book[book]
        for dt, nv in nav.items():
            eq_long.append({"date": dt.strftime("%Y-%m-%d"), "book": book, "nav": float(nv)})
    pd.DataFrame(eq_long).to_csv(OUT / "equity.csv", index=False)

    fig, ax = plt.subplots(figsize=(11, 5.5), dpi=120)
    ax.plot(nav_by_book[f0_book].index, nav_by_book[f0_book].values, color="black", lw=2.2, label="F0")
    for bid, book, _ in BOOKS[1:]:
        ax.plot(nav_by_book[book].index, nav_by_book[book].values, color="gray", lw=1.0, alpha=0.85, label=bid)
    ax.set_yscale("log")
    ax.set_title("ER-R2-FLOOR (Fri 14:30 / close)")
    ax.set_ylabel("净值（对数）")
    ax.grid(True, alpha=0.3)
    ax.legend(fontsize=8)
    fig.tight_layout()
    fig.savefig(OUT / "equity_curve.png")
    plt.close(fig)

    summary_cells = []
    for c in cells:
        summary_cells.append({k: c.get(k) for k in c if k not in ("w2020_22", "w2023_26")})
        summary_cells[-1]["w2020_22"] = c["w2020_22"]
        summary_cells[-1]["w2023_26"] = c["w2023_26"]

    summary = {
        "batch": "er-r2-floor",
        "knife_id": "ER-R2-FLOOR",
        "champion_swap": False,
        "crown": "NO",
        "source_sha": SOURCE_SHA,
        "sample": [EVAL_START, actual_end],
        "anchor_pass": anchor_pass,
        "attrib_pass": attrib_pass,
        "anchor": {
            "ret": ANCHOR["ret"],
            "maxDD": ANCHOR["maxDD"],
            "Calmar": ANCHOR["Calmar"],
            "n_weeks": len(calendar),
            "T": f0["T"],
            "n_codes": len(codes),
        },
        "face_id": "F0",
        "primary": "RF50",
        "floor": "R2(N=90)>=0.50 hard veto on new entries; fill=SHARPE20",
        "h1": h1_line,
        "family_verdict": family_verdict,
        "positive_ids": positive_ids,
        "skipped_fills": SKIPPED_FILLS,
        "cells": summary_cells,
        "elapsed_sec": round(time.time() - t0, 1),
    }
    (OUT / "summary.json").write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")

    report_lines = [
        qline,
        "",
        h1_block,
        "",
        "## 锚点门",
        "",
        "| 项 | 锚 | F0 本跑 | 过? |",
        "|---|---:|---:|:---:|",
        f"| ret | {ANCHOR['ret']:.3f} | {f0['ret']:.4f} | {'Y' if anchor_pass else 'N'} |",
        f"| maxDD | {ANCHOR['maxDD']:.3f} | {f0['maxDD']:.4f} | |",
        f"| Calmar | {ANCHOR['Calmar']:.2f} | {f0['Calmar']:.2f} | |",
        f"| 日历周 | {ANCHOR['n_weeks']} | {len(calendar)} | |",
        f"| T | {ANCHOR['T']} | {f0['T']} | |",
        f"| n_codes | {ANCHOR['n_codes']} | {len(codes)} | |",
        "",
        f"**anchor_pass={anchor_pass}** · **attrib_pass={attrib_pass}** · **family_verdict={family_verdict}** · 不换冠。",
        "",
        "## 主表",
        "",
        "| id | ret | maxDD | Calmar | w2020-22 | w2023-26 | n_floor_blocked | jaccard | inert | verdict |",
        "|---|---:|---:|---:|---:|---:|---:|---:|:---:|:---:|",
    ]
    for c in cells:
        report_lines.append(
            f"| {c['id']} | {pct(c['ret'])} | {pct(c['maxDD'])} | {c['Calmar']:.2f} | "
            f"{pct(c['w2020_22']['ret'])} | {pct(c['w2023_26']['ret'])} | {c['n_floor_blocked']} | "
            f"{c['jaccard_vs_f0']:.3f} | {c['inert']} | {c['verdict']} |"
        )
    report_lines.extend(["", "## Δ 表", "", "| id | Δret | Δ|MDD| | 盖住 | 2020-22 | 2023-26 |", "|---|---:|---:|:---:|:---:|:---:|"])
    for c in cells:
        if c["id"] == "F0":
            continue
        report_lines.append(
            f"| {c['id']} | {100*c['delta_ret']:+.1f}pp | {100*c['delta_abs_mdd']:+.1f}pp | "
            f"{c['covers']} | {c['window_2020_22']} | {c['window_2023_26']} |"
        )
    report_lines.extend(
        [
            "",
            "## 闸质量旁注",
            "",
            "n_r2_blocked / n_er_blocked / mean_r2 / mean_er / hit_rate / win_size 见 table.csv；"
            "AG40S 235.6% 仅旁注，不进尺子。",
            "",
            attrib_body,
            "",
            "## 证伪段",
            "",
            f"- {h1_line}",
            f"- positive_ids: {positive_ids or '[]'}",
        ]
    )
    if not anchor_pass:
        report_lines.append(
            f"- F0 实际 ret={pct(f0['ret'])} maxDD={pct(f0['maxDD'])} Calmar={f0['Calmar']:.2f}；"
            "对照 131.6/0.70、158.3/0.94、nob_ref 134.0/0.70、KB 135.0/0.74、PR#67 131.9/0.70。"
        )
    report_lines.extend(["", "## 红线", "", "研究池 only；champion_swap=false；未改 LIVE/实盘。", ""])
    (OUT / "REPORT.md").write_text("\n".join(report_lines), encoding="utf-8")
    print("done", OUT, family_verdict, flush=True)


if __name__ == "__main__":
    main()
