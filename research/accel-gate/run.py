#!/usr/bin/env python3
"""accel-gate: B45 spike_ft max5 + E0 + TV25; F0 SHARPE20 vs acceleration gate neighbors.

Four books: F0, AG40 (veto n=40), AG20 (veto n=20), AG40S (S20 band + accel sort).
Engine fork pin 05f0f8a4 (SPIKE-S20-BTHETA-GRID-LIVE1430). Research pool only.
"""
from __future__ import annotations

import json
import math
import subprocess
import sys
import time
from collections import defaultdict
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

REPO = Path(__file__).resolve().parents[2]
KIT = Path(__file__).resolve().parent.parent / "cloud_batch" / "CLOUD-BATCH-2026-10-26"
SCRIPTS = KIT / "scripts"
sys.path.insert(0, str(SCRIPTS))

from backtest import LIVE_PHASE, Position, nearest_date, snap_index  # noqa: E402

OUT = Path(__file__).resolve().parent / "out"
CACHE = KIT / "data" / "research_cache"
UNI_CSV = KIT / "data" / "universe_replace_only_436.csv"
WEEK = CACHE / "week"
FACE = CACHE / "holdings_ro2_extended.csv"
DAY_DIR = CACHE / "day"
TEMA_PX = Path("/workspace/tema_etf_scan_2018/prices_daily")
NOON_CSV = CACHE / "fri_1430_through_20261023.csv"
SINA_DAILY = CACHE / "sina_daily"
SNAP_CACHE = KIT / "data" / "cache_1430_snaps.json"
SOURCE_SHA = "05f0f8a4f778fde886f3e7b2976646ff4b7d777b"
PIN_REL = "research/cloud_batch/SPIKE-S20-BTHETA-GRID-LIVE1430/run.py"
BREADTH_THETA = 0.45
ANCHOR = {"ret": 1.316, "maxDD": -0.188, "Calmar": 0.70, "n_weeks": 349, "T": 348, "n_codes": 324}
ANCH_TOL = {"ret": 0.005, "maxDD": 0.002, "Calmar": 0.02}

BOOK_SPECS = [
    {"id": "F0", "book": "LIVE1430-B45-S20-max5", "n": 0, "mode": "off"},
    {"id": "AG40", "book": "LIVE1430-B45-S20-AG40-max5", "n": 40, "mode": "veto"},
    {"id": "AG20", "book": "LIVE1430-B45-S20-AG20-max5", "n": 20, "mode": "veto"},
    {"id": "AG40S", "book": "LIVE1430-B45-S20-AG40S-max5", "n": 40, "mode": "sort"},
]

EVAL_START = "2020-01-03"
END_S = "2026-10-23"
COST_SIDE = 0.001
SIGMA_STAR = 0.25
LCAP = 1.0
LIVE_COST_RT = 0.002
SHARPE_N = 20
MAX_POS = 5

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
]

DESIGN_QUESTION = (
    "请拍板：在面层 B45 + spike_ft max5 + E0 + TV25、LIVE≥14:30 面上，"
    "填席键仍是 SHARPE20，只对新开/换入加一道相邻窗 OLS 对数价格斜率差（加速度）闸。"
    "主口径冻结为 N=40+40 根交易日、accel = β_new − β_old、硬闸 accel > 0。"
    "已持仓不因 accel 变号而平。无论记正与否都不换冠。"
)


@dataclass
class Cand:
    code: str
    px: float
    fz: float | None
    aum: float
    sharpe: float | None
    accel: float | None = None
    beta_old: float | None = None
    beta_new: float | None = None


def verify_pin() -> None:
    r = subprocess.run(
        ["git", "-C", str(REPO), "cat-file", "-e", f"{SOURCE_SHA}:{PIN_REL}"],
        capture_output=True,
        text=True,
    )
    if r.returncode != 0:
        print(f"BLOCKED: missing pin {SOURCE_SHA}:{PIN_REL}", file=sys.stderr)
        sys.exit(1)
    for p in (KIT, SCRIPTS, WEEK, FACE, DAY_DIR, NOON_CSV, SINA_DAILY, SNAP_CACHE):
        if not Path(p).exists():
            print(f"BLOCKED: missing path {p}", file=sys.stderr)
            sys.exit(1)


def is_spike(snap: dict[str, Any] | None) -> bool:
    if not snap:
        return False
    if snap.get("pending_second_week") or snap.get("in_play_kind") == "box_pending":
        return False
    return bool(snap.get("in_play")) and snap.get("in_play_kind") == "spike_ft"


def sharpe_key(c: Cand) -> tuple:
    miss = 0 if c.sharpe is not None else 1
    return (miss, -(c.sharpe if c.sharpe is not None else 0.0), c.code)


def accel_key(c: Cand) -> tuple:
    miss = 0 if c.accel is not None else 1
    return (miss, -(c.accel if c.accel is not None else 0.0), c.code)


def ols_beta(px: np.ndarray) -> float | None:
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
    sxy = float(np.dot(t0, y0))
    if sxx <= 0 or not np.isfinite(sxx + sxy):
        return None
    beta = sxy / sxx
    if not np.isfinite(beta):
        return None
    return float(beta)


def accel_on(closes: pd.Series, d: str, n: int) -> tuple[float | None, float | None, float | None]:
    ts = pd.Timestamp(d)
    sub = closes.loc[: ts - pd.Timedelta(days=1)]
    if len(sub) < 2 * n:
        return None, None, None
    if (ts - sub.index[-1]).days > 5:
        return None, None, None
    window = sub.iloc[-(2 * n) :]
    if len(window) < 2 * n:
        return None, None, None
    px = window.to_numpy(dtype=float)
    b_old = ols_beta(px[:n])
    b_new = ols_beta(px[n:])
    if b_old is None or b_new is None:
        return None, None, None
    accel = float(b_new - b_old)
    if not np.isfinite(accel):
        return None, None, None
    return accel, b_old, b_new


def pick_accel_band(cands: list[Cand], slots: int) -> list[Cand]:
    if slots <= 0:
        return []
    band_k = max(2 * slots, slots + 2)
    band = list(cands[:band_k])
    if not band:
        return []
    if all(c.accel is None for c in band):
        return band[:slots]
    band_sorted = sorted(band, key=accel_key)
    return band_sorted[:slots]


def run_fixtures() -> None:
    n = 4
    old_flat = np.full(n, 10.0)
    new_acc = np.array([10.0 * math.exp(0.001 * i) for i in range(n)])
    b_old = ols_beta(old_flat)
    b_new = ols_beta(new_acc)
    assert b_old is not None and abs(b_old) < 1e-12
    assert b_new is not None and abs(b_new - 0.001) < 1e-12
    accel = b_new - b_old
    assert abs(accel - 0.001) < 1e-12

    b_old2 = ols_beta(new_acc)
    b_new2 = ols_beta(old_flat)
    assert b_old2 is not None and b_new2 is not None
    assert abs((b_new2 - b_old2) + 0.001) < 1e-12

    seg = np.array([math.exp(0.001 * i) for i in range(n)])
    b1 = ols_beta(seg)
    b2 = ols_beta(seg)
    assert b1 is not None and b2 is not None
    assert abs(b2 - b1) < 1e-12

    flat8 = np.full(8, 10.0)
    assert ols_beta(flat8[:4]) == 0.0 and ols_beta(flat8[4:]) == 0.0

    idx = pd.date_range("2024-01-02", periods=10, freq="B")
    ser = pd.Series(np.linspace(10, 11, len(idx)), index=idx)
    gap_d = (idx[-1] + pd.Timedelta(days=10)).strftime("%Y-%m-%d")
    a, _, _ = accel_on(ser, gap_d, 4)
    assert a is None

    short = pd.Series(np.linspace(1, 2, 79), index=pd.date_range("2023-01-02", periods=79, freq="B"))
    assert accel_on(short, short.index[-1].strftime("%Y-%m-%d"), 40)[0] is None

    bad = pd.Series([1.0, -1.0, 1.0, 1.0], index=pd.date_range("2024-01-02", periods=4, freq="B"))
    assert accel_on(bad, bad.index[-1].strftime("%Y-%m-%d"), 2)[0] is None

    idx80 = pd.date_range("2020-01-02", periods=80, freq="B")
    p1 = np.exp(0.002 * np.arange(40))
    p2 = np.exp(0.002 * 40 + 0.0004 * np.arange(40))
    ser80 = pd.Series(np.concatenate([p1, p2]), index=idx80)
    d_sig = (idx80[-1] + pd.Timedelta(days=1)).strftime("%Y-%m-%d")
    adj_a, _, _ = accel_on(ser80, d_sig, 40)
    assert adj_a is not None and adj_a < 0

    idx40 = pd.date_range("2020-06-01", periods=40, freq="B")
    px_clean = np.concatenate(
        [np.exp(0.001 * np.arange(20)), np.exp(0.001 * 19 + 0.002 * np.arange(20))]
    )
    ser_clean = pd.Series(px_clean, index=idx40)
    d_sig = (idx40[-1] + pd.Timedelta(days=1)).strftime("%Y-%m-%d")
    a0, bo0, bn0 = accel_on(ser_clean, d_sig, 20)
    assert a0 is not None and abs(a0 - (bn0 - bo0)) < 1e-12
    rng = np.random.default_rng(42)
    y_noisy = np.log(px_clean) + rng.normal(0, 0.05, 40)
    ser_noisy = pd.Series(np.exp(y_noisy), index=idx40)
    a1, bo1, bn1 = accel_on(ser_noisy, d_sig, 20)
    assert a1 is not None and abs(a1 - (bn1 - bo1)) < 1e-12

    cands = [
        Cand("A", 1, None, 1, 3.0, 0.1),
        Cand("B", 1, None, 1, 2.0, 0.2),
        Cand("C", 1, None, 1, 1.0, 0.3),
    ]
    take = pick_accel_band(sorted(cands, key=sharpe_key), 1)
    assert take[0].code == "C"


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
    variant: str,
    accel_mode: str,
    accel_n: int,
    max_pos: int,
) -> tuple[list[dict[str, Any]], dict[str, list[str]], dict[str, Any], list[tuple[str, str]]]:
    cash = 1.0
    positions: dict[str, Position] = {}
    trades: list[dict[str, Any]] = []
    picks: dict[str, list[str]] = {}
    n_tight = 0
    n_feat = 0
    n_entries = 0
    n_miss_sharpe = 0
    n_accel_blocked = 0
    n_accel_rerank = 0
    n_miss_accel = 0
    n_empty_slots = 0
    abs_d_sizes: list[int] = []
    entry_pairs: list[tuple[str, str]] = []
    accel_vals: list[float] = []
    dslope_vals: list[float] = []

    def px_on(code: str, d: str) -> float | None:
        return closes_w.get(code, {}).get((alias.get(code) or {}).get(d) or d)

    def snap_at(code: str, d: str) -> dict[str, Any] | None:
        key = (alias.get(code) or {}).get(d) or d
        return snaps.get(code, {}).get(key)

    def equity_now() -> float:
        return cash + sum(p.shares * p.last_px for p in positions.values())

    def attach_accel(c: Cand, d: str) -> None:
        if accel_mode == "off" or c.code not in daily:
            return
        a, bo, bn = accel_on(daily[c.code], d, accel_n)
        c.accel = a
        c.beta_old = bo
        c.beta_new = bn

    def build_cands(d: str, skip: set[str]) -> list[Cand]:
        nonlocal n_miss_accel, n_accel_blocked
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
            sh = sharpe_n_on(daily[code], d, SHARPE_N) if code in daily else None
            fz = sn.get("falsify_close") if sn else None
            c = Cand(
                code=code,
                px=px,
                fz=float(fz) if fz is not None else None,
                aum=aum.get(code) or 0.0,
                sharpe=sh,
            )
            if accel_mode != "off":
                attach_accel(c, d)
                if c.accel is None:
                    n_miss_accel += 1
                if c.sharpe is not None and (c.accel is None or c.accel <= 0):
                    if accel_mode == "veto":
                        n_accel_blocked += 1
            out.append(c)
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
            if risk_on and len(pool) >= 1:
                abs_d_sizes.append(len(pool))
            slots = max_pos - len(positions)
            if pool:
                n_feat += 1
            if slots > 0 and len(pool) > slots:
                n_tight += 1
            if slots > 0 and pool:
                pool_rank = [c for c in pool if c.sharpe is not None]
                pool_rank = sorted(pool_rank, key=sharpe_key)
                if accel_mode == "off":
                    take = pool_rank[:slots]
                elif accel_mode == "veto":
                    gated = [c for c in pool_rank if c.accel is not None and c.accel > 0]
                    take = gated[:slots]
                elif accel_mode == "sort":
                    take = pick_accel_band(pool_rank, slots)
                    pure = set(c.code for c in pool_rank[:slots])
                    actual = set(c.code for c in take)
                    n_accel_rerank += len(actual - pure)
                else:
                    raise SystemExit(f"unknown accel_mode {accel_mode}")
                n_empty_slots += max(0, slots - len(take))
                for c in take:
                    n_entries += 1
                    entry_pairs.append((d, c.code))
                    if c.sharpe is None:
                        n_miss_sharpe += 1
                    if c.accel is not None:
                        accel_vals.append(c.accel)
                        if c.beta_old is not None and c.beta_new is not None:
                            dslope_vals.append(
                                (math.exp(c.beta_new * 252) - 1) - (math.exp(c.beta_old * 252) - 1)
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
    for d in calendar:
        for code in exits_by_day.get(d, []):
            open_codes.discard(code)
        for code in picks.get(d, []):
            open_codes.add(code)
        hold[d] = sorted(open_codes)

    n_cash = sum(1 for d in calendar[:-1] if not (hold.get(d) or []))
    stats = {
        "n_entries": n_entries,
        "n_accel_blocked": 0 if accel_mode in ("off", "sort") else n_accel_blocked,
        "n_accel_rerank": n_accel_rerank if accel_mode == "sort" else 0,
        "n_miss_accel": 0 if accel_mode == "off" else n_miss_accel,
        "n_empty_slots": n_empty_slots,
        "mean_accel": float(np.mean(accel_vals)) if accel_vals else 0.0,
        "mean_dslope_ann": float(np.mean(dslope_vals)) if dslope_vals else 0.0,
        "mean_abs_D": float(np.mean(abs_d_sizes)) if abs_d_sizes else 0.0,
        "n_cash_weeks": n_cash,
        "n_trades": len(trades),
    }
    return trades, hold, stats, entry_pairs


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


def pct(x: float | None) -> str:
    if x is None or (isinstance(x, float) and (math.isnan(x) or math.isinf(x))):
        return "—"
    return f"{100 * x:.1f}%"


def entry_quality(
    entry_pairs: list[tuple[str, str]],
    calendar: list[str],
    closes_w: dict[str, dict[str, float]],
    alias: dict[str, dict[str, str]],
) -> tuple[float, float]:
    rets: list[float] = []
    for ent_d, code in entry_pairs:
        if ent_d not in calendar:
            continue
        idx = calendar.index(ent_d)
        if idx + 1 >= len(calendar) - 1:
            continue
        nxt = calendar[idx + 1]
        key = (alias.get(code) or {}).get(nxt) or nxt
        px0 = (closes_w.get(code) or {}).get((alias.get(code) or {}).get(ent_d) or ent_d)
        px1 = (closes_w.get(code) or {}).get(key)
        if px1 is None or px0 is None or px0 <= 0:
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


def jaccard_entries(a: set[tuple[str, str]], b: set[tuple[str, str]]) -> float:
    if not a and not b:
        return 1.0
    u = a | b
    if not u:
        return 0.0
    return len(a & b) / len(u)


def check_anchor(st: dict[str, float], n_weeks: int, n_codes: int, end_s: str, t_weeks: int) -> bool:
    if end_s != END_S:
        return False
    if n_weeks != ANCHOR["n_weeks"]:
        return False
    if t_weeks != ANCHOR["T"]:
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
        cell["inert"] = False
        return
    if cell.get("inert"):
        cell["verdict"] = "证伪"
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


def weekly_signal_returns(nav: pd.Series, calendar: list[str]) -> pd.Series:
    sigs = calendar[:-1]
    out: dict[str, float] = {}
    nav = nav.sort_index()
    for i, d in enumerate(sigs):
        ts = pd.Timestamp(d)
        nxt = pd.Timestamp(sigs[i + 1]) if i + 1 < len(sigs) else None
        if nxt is None:
            continue
        sub = nav.loc[:ts]
        sub2 = nav.loc[:nxt]
        if len(sub) < 1 or len(sub2) < 1:
            continue
        v0, v1 = float(sub.iloc[-1]), float(sub2.iloc[-1])
        if v0 > 0:
            out[d] = v1 / v0 - 1.0
    return pd.Series(out)


def find_best_segment(cum_ex: np.ndarray, maximize: bool) -> tuple[int, int, float]:
    best_i, best_j, best_val = 0, 0, 0.0 if maximize else 0.0
    found = False
    n = len(cum_ex)
    for i in range(n):
        for j in range(i + 1, n):
            val = cum_ex[j] - cum_ex[i]
            if not found:
                best_i, best_j, best_val, found = i, j, val, True
                continue
            better = val > best_val if maximize else val < best_val
            if better:
                best_i, best_j, best_val = i, j, val
            elif val == best_val:
                if i < best_i or (i == best_i and (j - i) < (best_j - best_i)):
                    best_i, best_j, best_val = i, j, val
    return best_i, best_j, best_val


def years_label(d0: str, d1: str) -> str:
    y0, y1 = int(d0[:4]), int(d1[:4])
    return str(y0) if y0 == y1 else f"{y0}-{y1}"


def top_codes_in_segment(hold: dict[str, list[str]], dates: list[str], book: str, f0_hold: dict[str, list[str]], kind: str) -> tuple[str, str]:
    book_cnt: dict[str, int] = defaultdict(int)
    f0_cnt: dict[str, int] = defaultdict(int)
    for d in dates:
        for c in hold.get(d) or []:
            book_cnt[c] += 1
        for c in f0_hold.get(d) or []:
            f0_cnt[c] += 1
    uniq_book = ";".join([c for c, _ in sorted(book_cnt.items(), key=lambda x: -x[1])[:8]])
    uniq_f0 = ";".join([c for c, _ in sorted(f0_cnt.items(), key=lambda x: -x[1])[:8]])
    return uniq_book, uniq_f0


def build_entries_diff(f0_entries: set[tuple[str, str]], by_id: dict[str, set[tuple[str, str]]]) -> pd.DataFrame:
    rows: list[dict[str, Any]] = []
    for spec in BOOK_SPECS:
        if spec["id"] == "F0":
            continue
        bid = spec["id"]
        eb = by_id[bid]
        for side, diff in (("ADD", eb - f0_entries), ("DROP", f0_entries - eb)):
            agg: dict[tuple[int, str], list[str]] = defaultdict(list)
            for d, code in diff:
                y = int(d[:4])
                agg[(y, code)].append(d)
            for (year, code), ds in sorted(agg.items()):
                rows.append(
                    {
                        "year": year,
                        "id": bid,
                        "side": side,
                        "code": code,
                        "n_events": len(ds),
                        "first_date": min(ds),
                        "last_date": max(ds),
                    }
                )
    return pd.DataFrame(rows)


def extract_h1_block() -> str:
    design = Path(__file__).resolve().parent / "DESIGN.md"
    if not design.exists():
        return ""
    txt = design.read_text(encoding="utf-8")
    marker = "## H1"
    if marker not in txt:
        return ""
    part = txt.split(marker, 1)[1]
    if "```" not in part:
        return ""
    return part.split("```", 2)[1].strip()


def main() -> None:
    verify_pin()
    run_fixtures()
    print("fixtures OK", flush=True)
    OUT.mkdir(parents=True, exist_ok=True)
    t0 = time.time()

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
    sim_stats: dict[str, dict[str, Any]] = {}
    entry_by: dict[str, list[tuple[str, str]]] = {}
    for spec in BOOK_SPECS:
        print(f"simulate {spec['id']}…", flush=True)
        trades, hold, st, ep = simulate(
            calendar,
            snaps,
            closes_w_sig,
            alias,
            aum,
            daily,
            risk_on_by_fri,
            spec["book"],
            spec["mode"] if spec["mode"] != "off" else "off",
            spec["n"] if spec["n"] else 40,
            MAX_POS,
        )
        hold_by[spec["book"]] = hold
        sim_stats[spec["book"]] = st
        entry_by[spec["book"]] = ep
        pd.DataFrame(trades).to_csv(OUT / f"trades_{spec['id']}.csv", index=False)

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

    cells: list[dict[str, Any]] = []
    series: dict[str, pd.Series] = {}
    nav_by_book: dict[str, pd.Series] = {}
    f0_book = BOOK_SPECS[0]["book"]
    f0_entries = set(entry_by[f0_book])
    f0_hold = hold_by[f0_book]
    f0_week_sets = {d: frozenset(f0_hold.get(d) or []) for d in calendar[:-1]}

    for spec in BOOK_SPECS:
        name = spec["book"]
        hd = {pd.Timestamp(d): cs for d, cs in hold_by[name].items()}
        r, L, avg_to = run_live_tv(hd, days, px, R)
        series[name] = r
        nav = (1 + r).cumprod()
        nav_by_book[name] = nav
        st = stats_full(r)
        r2022 = r[(r.index >= "2020-01-01") & (r.index <= "2022-12-31")]
        r2023 = r[r.index >= "2023-01-01"]
        st2022 = stats_full(r2022) if len(r2022) > 5 else {k: float("nan") for k in st}
        st2023 = stats_full(r2023) if len(r2023) > 5 else {k: float("nan") for k in st}
        hit, win_sz = entry_quality(entry_by[name], calendar, closes_w_sig, alias)
        sim = sim_stats[name]
        entries_set = set(entry_by[name])
        jacc = 1.0 if spec["id"] == "F0" else jaccard_entries(entries_set, f0_entries)
        week_sets = {d: frozenset(hold_by[name].get(d) or []) for d in calendar[:-1]}
        same_weeks = all(week_sets[d] == f0_week_sets[d] for d in calendar[:-1])
        inert = False
        if spec["id"] != "F0":
            hard = spec["mode"] == "veto"
            inert = same_weeks or (
                hard and sim["n_accel_blocked"] == 0 and sim["n_empty_slots"] == sim_stats[f0_book]["n_empty_slots"]
            )
        cell = {
            "id": spec["id"],
            "book": name,
            "n": spec["n"],
            "mode": "off" if spec["mode"] == "off" else ("sort" if spec["mode"] == "sort" else "veto"),
            "ret": st["ret"],
            "maxDD": st["maxDD"],
            "CAGR": st["CAGR"],
            "Calmar": st["Calmar"],
            "avgL": float(L[L > 0].mean()) if (L > 0).any() else 0.0,
            "avg_turnover_1way": avg_to,
            "n_cash_weeks": sim["n_cash_weeks"],
            "n_entries": sim["n_entries"],
            "n_accel_blocked": sim["n_accel_blocked"],
            "n_accel_rerank": sim["n_accel_rerank"],
            "n_miss_accel": sim["n_miss_accel"],
            "n_empty_slots": sim["n_empty_slots"],
            "mean_accel": sim["mean_accel"],
            "mean_dslope_ann": sim["mean_dslope_ann"],
            "mean_abs_D": sim["mean_abs_D"],
            "hit_rate": hit,
            "win_size": win_sz,
            "jaccard_vs_f0": jacc,
            "inert": inert,
            "w2020_22": {"ret": st2022["ret"], "maxDD": st2022["maxDD"], "Calmar": st2022["Calmar"]},
            "w2023_26": {"ret": st2023["ret"], "maxDD": st2023["maxDD"], "Calmar": st2023["Calmar"]},
        }
        cells.append(cell)
        print(f"  {spec['id']}: ret={pct(st['ret'])} dd={pct(st['maxDD'])} Calmar={st['Calmar']:.2f}", flush=True)

    f0_cell = next(c for c in cells if c["id"] == "F0")
    anchor_pass = check_anchor(f0_cell, len(calendar), len(codes), actual_end, len(calendar) - 1)
    print(f"anchor_pass={anchor_pass}", flush=True)

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

    wr_f0 = weekly_signal_returns(nav_by_book[f0_book], calendar)
    seg_rows: list[dict[str, Any]] = []
    for spec in BOOK_SPECS:
        if spec["id"] == "F0":
            continue
        wr = weekly_signal_returns(nav_by_book[spec["book"]], calendar)
        aligned = sorted(set(wr.index) & set(wr_f0.index))
        if len(aligned) < 2:
            aligned = (aligned + [calendar[1], calendar[2]])[:2]
        ex = pd.Series({d: wr.get(d, 0.0) - wr_f0.get(d, 0.0) for d in aligned})
        cum_ex = ex.cumsum().values
        cell_ref = next(c for c in cells if c["id"] == spec["id"])
        if cell_ref["inert"]:
            bi, bj, bw = 0, 1, 0.0
            li, lj, bl = 0, 1, 0.0
        else:
            bi, bj, bw = find_best_segment(cum_ex, True)
            li, lj, bl = find_best_segment(cum_ex, False)
        hold = hold_by[spec["book"]]
        for kind, i, j, val in (("BIGWIN", bi, bj, bw), ("BIGLOSS", li, lj, bl)):
            d0, d1 = aligned[i], aligned[j]
            seg_dates = [d for d in aligned if d0 <= d <= d1]
            ub, uf = top_codes_in_segment(hold, seg_dates, spec["book"], f0_hold, kind)
            seg_rows.append(
                {
                    "id": spec["id"],
                    "kind": kind,
                    "start": d0,
                    "end": d1,
                    "years": years_label(d0, d1),
                    "delta_cum_ex": float(val),
                    "n_weeks": j - i,
                    "uniq_book": ub,
                    "uniq_f0": uf,
                    "n_shared": len(set((hold.get(d) or [])) & set(f0_hold.get(d) or [])),
                }
            )

    entries_by_id = {spec["id"]: set(entry_by[spec["book"]]) for spec in BOOK_SPECS}
    diff_df = build_entries_diff(f0_entries, entries_by_id)
    seg_df = pd.DataFrame(seg_rows)
    diff_df.to_csv(OUT / "entries_diff_by_year.csv", index=False)
    seg_df.to_csv(OUT / "segment_attribution.csv", index=False)

    positive_ids = [c["id"] for c in cells if c["verdict"] == "记正"]
    attrib_pass = True
    if seg_df.empty or len(seg_df) < 6:
        attrib_pass = False
    for bid in ("AG40", "AG20", "AG40S"):
        sub = seg_df[seg_df["id"] == bid]
        if not {"BIGWIN", "BIGLOSS"}.issubset(set(sub["kind"])):
            attrib_pass = False

    if not anchor_pass:
        family_verdict = "BLOCKED"
    elif not attrib_pass:
        family_verdict = "BLOCKED"
    elif positive_ids:
        family_verdict = "H1_REJECT"
    else:
        family_verdict = "H1_HOLD"

    table_cols = [
        "id",
        "book",
        "n",
        "mode",
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
        "n_accel_blocked",
        "n_accel_rerank",
        "n_miss_accel",
        "n_empty_slots",
        "mean_accel",
        "mean_dslope_ann",
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
    trows = []
    for c in cells:
        trows.append(
            {
                "id": c["id"],
                "book": c["book"],
                "n": c["n"],
                "mode": c["mode"],
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
                "n_accel_blocked": c["n_accel_blocked"],
                "n_accel_rerank": c["n_accel_rerank"],
                "n_miss_accel": c["n_miss_accel"],
                "n_empty_slots": c["n_empty_slots"],
                "mean_accel": c["mean_accel"],
                "mean_dslope_ann": c["mean_dslope_ann"],
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
    pd.DataFrame(trows)[table_cols].to_csv(OUT / "table.csv", index=False)

    eq_long = []
    for spec in BOOK_SPECS:
        nav = nav_by_book[spec["book"]]
        for dt, nv in nav.items():
            eq_long.append({"date": dt.strftime("%Y-%m-%d"), "book": spec["book"], "nav": float(nv)})
    pd.DataFrame(eq_long).to_csv(OUT / "equity.csv", index=False)

    fig, ax = plt.subplots(figsize=(11, 5.5), dpi=120)
    nav_f0 = nav_by_book[f0_book]
    ax.plot(nav_f0.index, nav_f0.values, color="black", lw=2.2, label="F0")
    for spec in BOOK_SPECS[1:]:
        nav = nav_by_book[spec["book"]]
        ax.plot(nav.index, nav.values, color="gray", lw=1.0, alpha=0.85, label=spec["id"])
    ax.set_yscale("log")
    ax.set_title("accel-gate: F0 (black) vs AG40/AG20/AG40S")
    ax.set_ylabel("NAV (log)")
    ax.grid(True, alpha=0.3)
    ax.legend(fontsize=8)
    fig.tight_layout()
    fig.savefig(OUT / "equity_curve.png")
    plt.close(fig)

    h1_block = extract_h1_block()
    summary = {
        "batch": "accel-gate",
        "knife_id": "ACCEL-GATE",
        "champion_swap": False,
        "crown": "NO",
        "source_sha": SOURCE_SHA,
        "sample": [EVAL_START, actual_end],
        "anchor_pass": anchor_pass,
        "attrib_pass": attrib_pass,
        "anchor": {**ANCHOR, "n_weeks": len(calendar), "T": len(calendar) - 1},
        "face_id": "F0",
        "primary": "AG40",
        "accel": "adjacent OLS dbeta; n=40+40; hard veto accel>0 on new entries; fill=SHARPE20",
        "h1": "AG40/AG20/AG40S all 证伪",
        "family_verdict": family_verdict,
        "positive_ids": positive_ids,
        "skipped_fills": SKIPPED_FILLS,
        "cells": cells,
        "elapsed_sec": round(time.time() - t0, 1),
    }
    (OUT / "summary.json").write_text(json.dumps(summary, ensure_ascii=False, indent=2, default=str), encoding="utf-8")

    def tbl_row(c: dict[str, Any]) -> str:
        return (
            f"| {c['id']} | {c['book']} | {pct(c['ret'])} | {pct(c['maxDD'])} | {pct(c['CAGR'])} | "
            f"{c['Calmar']:.2f} | {pct(c['w2020_22']['ret'])}/{pct(c['w2020_22']['maxDD'])}/{c['w2020_22']['Calmar']:.2f} | "
            f"{pct(c['w2023_26']['ret'])}/{pct(c['w2023_26']['maxDD'])}/{c['w2023_26']['Calmar']:.2f} | "
            f"{c['avgL']:.2f} | {c['avg_turnover_1way']:.3f} | {c['n_cash_weeks']} | {c['n_entries']} | "
            f"{c['n_accel_blocked']} | {c['n_accel_rerank']} | {c['n_miss_accel']} | {c['n_empty_slots']} | "
            f"{c['mean_accel']:.4f} | {c['jaccard_vs_f0']:.3f} | {c['verdict']} |"
        )

    anchor_line = (
        f"锚点门：F0 ret={pct(f0_cell['ret'])} maxDD={pct(f0_cell['maxDD'])} Calmar={f0_cell['Calmar']:.2f} "
        f"（目标 131.6% / −18.8% / 0.70）→ {'通过' if anchor_pass else '未通过 BLOCKED'}。"
    )
    if not anchor_pass:
        verdict_line = "**BLOCKED（不换冠）**：F0 未贴上 btheta 锚；家族结论 BLOCKED。"
    elif not attrib_pass:
        verdict_line = "**BLOCKED（不换冠）**：ATTRIBUTION 未齐，不得判卷。"
    elif family_verdict == "H1_HOLD":
        verdict_line = "**H1 成立（不换冠）**：三本加速度相对本次 F0 均为证伪，加速度闸无记正。"
    else:
        verdict_line = f"**H1 证伪（不换冠）**：记正格 {', '.join(positive_ids)}。"

    attrib_a = (
        "(a) 机制：在 B45 + spike_ft max5 + E0 + TV25 + SHARPE20 填席 + Fri≥14:30 + 0.2%RT + AUM≥2 面上，"
        "仅对新开/换入加相邻窗 OLS 加速度硬闸（AG40/AG20）或 S20 短名单内 accel 次级排序（AG40S）；已持仓不因 accel 变号而平。"
    )
    attrib_b = "(b) 席位 Jaccard vs F0：" + ", ".join(
        f"{c['id']}={c['jaccard_vs_f0']:.3f}" for c in cells if c["id"] != "F0"
    )
    attrib_c = "(c) 分段 Δret / 踏空：见下表 Δ；2023–26 需 ≥ F0 同窗才记正。"
    f0_to = f0_cell["avg_turnover_1way"]
    f0_cash = f0_cell["n_cash_weeks"]
    attrib_d = "(d) 换手与空仓周相对 F0："
    for c in cells:
        if c["id"] == "F0":
            continue
        attrib_d += (
            f" {c['id']} TO1w {c['avg_turnover_1way']:.3f}（F0 {f0_to:.3f}），"
            f"空仓周 {c['n_cash_weeks']}（F0 {f0_cash}），n_empty_slots={c['n_empty_slots']}（F0 {f0_cell['n_empty_slots']}）；"
        )
    attrib_e_lines = ["(e) 名字·年份与大赢/大亏段："]
    for spec in BOOK_SPECS:
        if spec["id"] == "F0":
            continue
        cid = spec["id"]
        cell = next(c for c in cells if c["id"] == cid)
        if cell["inert"]:
            attrib_e_lines.append(f"- {cid}：与 F0 席位逐周相同，无名字可列。")
            continue
        sub = diff_df[diff_df["id"] == cid]
        for year in sorted(sub["year"].unique()):
            ydf = sub[sub["year"] == year]
            for side in ("ADD", "DROP"):
                sdf = ydf[ydf["side"] == side].sort_values("n_events", ascending=False).head(5)
                if len(sdf):
                    parts = [f"{r.code}({int(r.n_events)})" for r in sdf.itertuples()]
                    attrib_e_lines.append(f"  - {cid} {year} {side}: " + ", ".join(parts))
        for kind in ("BIGWIN", "BIGLOSS"):
            row = seg_df[(seg_df["id"] == cid) & (seg_df["kind"] == kind)].iloc[0]
            attrib_e_lines.append(
                f"  - {cid} {kind}: {row['start']}→{row['end']} ({row['years']}) Δcum_ex={row['delta_cum_ex']:.4f}; "
                f"uniq_book={row['uniq_book'] or '—'}; uniq_f0={row['uniq_f0'] or '—'}"
            )
    attrib_e = "\n".join(attrib_e_lines)
    attrib_footer = "ATTRIBUTION 不进 verdict。"

    report = f"""{DESIGN_QUESTION}

```
{h1_block}
```

## 1. 准则原文（摘要）

- 面：B45 + spike_ft max5 + E0 + TV25；SHARPE20 填席不变；加速度闸仅作用于 C_t 新开/换入。
- 四本：F0 / AG40（40+40 硬闸）/ AG20（20+20 硬闸）/ AG40S（短名单 accel 排序）。
- 尺子：记正 = Δret≥Δ|MDD| 且 2020–22、2023–26 窗 ret 均 ≥ F0，且非惰性。无 0.9× / −2pp。
- 跳过：{', '.join(SKIPPED_FILLS)} 等；SHARPE12/40、RET52、SOFT、skip-month、Kaufman-ER、MA200 见 REPORT 跳过段。

## 2. 实现要点

- 引擎 fork：`{SOURCE_SHA}`；kit `CLOUD-BATCH-2026-10-26`；`risk_on=(b≥0.45)`。
- accel = β_new − β_old（相邻 OLS ln P）；截止信号日前一交易日。
- {anchor_line}
- ATTRIBUTION 门：{'通过' if attrib_pass else '未通过'}。

## 3. 主表

| id | book | ret | maxDD | CAGR | Calmar | 2020–22 | 2023–26 | avgL | TO1w | cash周 | n_ent | blocked | rerank | miss | empty | mean_acc | Jacc | verdict |
|---|---|---:|---:|---:|---:|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---|
{chr(10).join(tbl_row(c) for c in cells)}

### Δ（相对本次 F0）

| id | Δret pp | Δ|MDD| pp | 盖住 | 2020–22 | 2023–26 | 惰性 |
|---|---:|---:|:---:|:---:|:---:|:---:|
"""
    for c in cells:
        if c["id"] == "F0":
            continue
        report += (
            f"| {c['id']} | {100*c['delta_ret']:+.1f} | {100*c['delta_abs_mdd']:+.1f} | "
            f"{'Y' if c['covers'] else 'N'} | {'Y' if c['window_2020_22'] else 'N'} | "
            f"{'Y' if c['window_2023_26'] else 'N'} | {'Y' if c['inert'] else 'N'} |\n"
        )

    report += f"""
### 闸质量旁注

- F0：n_accel_blocked=0；hit_rate={f0_cell['hit_rate']:.2%} win_size={f0_cell['win_size']:.2f}（仅披露）

## ATTRIBUTION

{attrib_a}

{attrib_b}

{attrib_c}

{attrib_d}

{attrib_e}

{attrib_footer}

## 4. 证伪段与一句判词

"""
    for c in cells:
        if c["id"] == "F0":
            continue
        if c["verdict"] == "记正":
            report += f"- {c['id']}：记正\n"
        elif c["verdict"] == "BLOCKED":
            report += f"- {c['id']}：BLOCKED\n"
        else:
            rs = []
            if c.get("inert"):
                rs.append("惰性")
            if not c["covers"]:
                rs.append("未盖住")
            if not c["window_2020_22"]:
                rs.append("2020–22 踏空")
            if not c["window_2023_26"]:
                rs.append("2023–26 踏空")
            report += f"- {c['id']}：证伪（{'；'.join(rs) or '缺失'}）\n"

    report += f"\n{verdict_line}\n\nfamily_verdict={family_verdict}; attrib_pass={attrib_pass}; 耗时 {summary['elapsed_sec']}s。\n"
    (OUT / "REPORT.md").write_text(report, encoding="utf-8")
    print("done", OUT, flush=True)
    print(verdict_line, flush=True)


if __name__ == "__main__":
    main()
