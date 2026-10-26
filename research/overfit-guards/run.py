#!/usr/bin/env python3
"""Overfit guards: DSR + CPCV on the SPIKE-S20 B45 face.

Fork pin: 05f0f8a4 (SPIKE-S20-BTHETA-GRID-LIVE1430).
N=13 books. CPCV menu FACE/B40/B50/TV22/TV28/S4/S6.
Research only; no crown swap. Do not touch strategy_exec / LIVE / champion.
"""
from __future__ import annotations

import itertools
import json
import math
import subprocess
import sys
import time
from collections import defaultdict
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from scipy.stats import norm

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[1]
OUT = HERE / "out"
PIN_SHA = "05f0f8a4f778fde886f3e7b2976646ff4b7d777b"
PIN_ENGINE = "research/cloud_batch/SPIKE-S20-BTHETA-GRID-LIVE1430/run.py"

READONLY_KIT = HERE / "_readonly_kit"
KIT_CACHE = REPO / "research" / "cloud_batch" / "CLOUD-BATCH-2026-10-26"
SCRIPTS = READONLY_KIT / "scripts"


def _bootstrap_pin_kit() -> None:
    pairs = [
        (
            "research/cloud_batch/CLOUD-BATCH-2026-10-26/scripts/backtest.py",
            SCRIPTS / "backtest.py",
        ),
        (
            "research/cloud_batch/CLOUD-BATCH-2026-10-26/scripts/build_scan.py",
            SCRIPTS / "build_scan.py",
        ),
        (
            "research/cloud_batch/CLOUD-BATCH-2026-10-26/data/universe_replace_only_436.csv",
            READONLY_KIT / "data" / "universe_replace_only_436.csv",
        ),
    ]
    for src, dest in pairs:
        dest.parent.mkdir(parents=True, exist_ok=True)
        if dest.exists() and dest.stat().st_size > 0:
            continue
        dest.write_bytes(subprocess.check_output(["git", "show", f"{PIN_SHA}:{src}"], cwd=REPO))


_bootstrap_pin_kit()
sys.path.insert(0, str(SCRIPTS))

from backtest import LIVE_PHASE, Position, nearest_date, snap_index  # noqa: E402

CACHE = KIT_CACHE / "data" / "research_cache"
UNI_CSV = READONLY_KIT / "data" / "universe_replace_only_436.csv"
WEEK = CACHE / "week"
FACE_CSV = CACHE / "holdings_ro2_extended.csv"
DAY_DIR = CACHE / "day"
TEMA_PX = Path("/workspace/tema_etf_scan_2018/prices_daily")
NOON_CSV = CACHE / "fri_1430_through_20261023.csv"
SINA_DAILY = CACHE / "sina_daily"
SNAP_CACHE = KIT_CACHE / "data" / "cache_1430_snaps.json"

EVAL_START = "2020-01-03"
END_S = "2026-10-23"
COST_SIDE = 0.001
LCAP = 1.0
LIVE_COST_RT = 0.002
GAMMA_E = 0.5772156649015329

ANCHOR_RET = 1.316
ANCHOR_MDD = -0.188
ANCHOR_CAL = 0.70
ANCHOR_N_WEEKS = 349
ANCHOR_T = 348
ANCHOR_N_CODES = 324
RET_TOL = 0.005
MDD_TOL = 0.002
CAL_TOL = 0.02

# DESIGN table order. Do not add a 14th vector.
TRIALS: list[tuple[str, float, int, float]] = [
    ("B40", 0.40, 5, 0.25),
    ("FACE", 0.45, 5, 0.25),
    ("B50", 0.50, 5, 0.25),
    ("B55", 0.55, 5, 0.25),
    ("TV20", 0.45, 5, 0.20),
    ("TV22", 0.45, 5, 0.22),
    ("TV28", 0.45, 5, 0.28),
    ("TV30", 0.45, 5, 0.30),
    ("TV33", 0.45, 5, 0.33),
    ("S3", 0.45, 3, 0.25),
    ("S4", 0.45, 4, 0.25),
    ("S6", 0.45, 6, 0.25),
    ("S7", 0.45, 7, 0.25),
]
CPCV_MENU = ["FACE", "B40", "B50", "TV22", "TV28", "S4", "S6"]
CPCV_SET = set(CPCV_MENU)
GROUP_BOUNDS = [0, 50, 100, 150, 200, 250, 299, 348]
GROUP_SIZES = [50, 50, 50, 50, 50, 49, 49]
TABLE_COLS = [
    "kind",
    "id",
    "theta",
    "maxN",
    "sigma",
    "ret",
    "maxDD",
    "CAGR",
    "Calmar",
    "sr_week",
    "sr_ann_display",
    "gamma3",
    "gamma4",
    "in_dsr",
    "in_cpcv",
    "path",
    "train_pick",
    "split",
    "test_calmar_face",
    "test_calmar_selected",
]
BOARD_Q = "请拍板：维持面层 B45 + spike_ft max5 + TV25 + SHARPE20，DSR / CPCV 无论是否标过拟合都不换冠。"


@dataclass
class Cand:
    code: str
    px: float
    fz: float | None
    aum: float
    sharpe: float | None


RankFn = Callable[[Cand, list[Cand]], tuple]


def is_spike(snap: dict[str, Any] | None) -> bool:
    if not snap:
        return False
    if snap.get("pending_second_week") or snap.get("in_play_kind") == "box_pending":
        return False
    return bool(snap.get("in_play")) and snap.get("in_play_kind") == "spike_ft"


def sharpe_key(c: Cand, pool: list[Cand]) -> tuple:
    miss = 0 if c.sharpe is not None else 1
    return (miss, -(c.sharpe if c.sharpe is not None else 0.0), c.code)


def z_max(n: float) -> float:
    n = float(n)
    return (1.0 - GAMMA_E) * float(norm.ppf(1.0 - 1.0 / n)) + GAMMA_E * float(
        norm.ppf(1.0 - 1.0 / (n * math.e))
    )


def deflated_sharpe(
    sr: float, sigma_sr: float, t: int, n: float, gamma3: float, gamma4: float
) -> float | None:
    if t < 4 or not math.isfinite(sr) or not math.isfinite(sigma_sr):
        return None
    if not math.isfinite(gamma3) or not math.isfinite(gamma4):
        return None
    sr_star = sigma_sr * z_max(n)
    den2 = 1.0 - gamma3 * sr + ((gamma4 - 1.0) / 4.0) * sr * sr
    if den2 <= 0 or not math.isfinite(den2):
        return None
    z = (sr - sr_star) * math.sqrt(t - 1) / math.sqrt(den2)
    if not math.isfinite(z):
        return None
    return float(norm.cdf(z))


def run_dsr_fixtures() -> None:
    sr = 2.5 / math.sqrt(250.0)
    sigma = math.sqrt(0.5 / 250.0)
    cases = [
        ("论文 N=100", 100, -3.0, 10.0, 0.9003, 0.9005),
        ("论文 N=46", 46, -3.0, 10.0, 0.9504, 0.9506),
        ("正态 N=88", 88, 0.0, 3.0, 0.9504, 0.9506),
    ]
    for name, n, g3, g4, lo, hi in cases:
        val = deflated_sharpe(sr, sigma, 1250, n, g3, g4)
        if val is None or not (lo <= val <= hi):
            raise SystemExit(f"DSR fixture fail {name}: {val}")
        print(f"  fixture {name}: DSR={val:.6f}", flush=True)


def weekly_moments(rw: np.ndarray) -> tuple[float, float, float, float]:
    t = len(rw)
    mu = float(np.mean(rw))
    std = float(np.std(rw, ddof=1)) if t > 1 else float("nan")
    sr = mu / std if std and math.isfinite(std) and std > 0 else float("nan")
    centered = rw - mu
    m2 = float(np.sum(centered**2) / t)
    m3 = float(np.sum(centered**3) / t)
    m4 = float(np.sum(centered**4) / t)
    if m2 <= 0 or not math.isfinite(m2):
        return sr, std, float("nan"), float("nan")
    g3 = m3 / (m2 ** 1.5)
    g4 = m4 / (m2**2)
    return sr, std, float(g3), float(g4)


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
    return trades, hold, stats


def run_live_tv(
    hold: dict[pd.Timestamp, list[str]],
    days: pd.DatetimeIndex,
    px: pd.DataFrame,
    R: pd.DataFrame,
    sigma_star: float,
) -> tuple[pd.Series, pd.Series]:
    """btheta run_live_tv with per-book SIGMA_STAR. σ20/σ60 from this book's own past rp."""
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
                L = float(min(LCAP, sigma_star / sh)) if sh and sh > 0 else 1.0
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


def pct(x: float | None) -> str:
    if x is None or (isinstance(x, float) and (math.isnan(x) or math.isinf(x))):
        return "—"
    return f"{100 * x:.1f}%"


def resolve_pin() -> str:
    try:
        full = subprocess.check_output(
            ["git", "rev-parse", PIN_SHA], cwd=REPO, text=True
        ).strip()
    except Exception as exc:
        raise SystemExit(f"cannot resolve pin {PIN_SHA}: {exc}")
    if full != PIN_SHA:
        raise SystemExit(f"loaded sha {full} is not {PIN_SHA}")
    engine = subprocess.check_output(["git", "show", f"{PIN_SHA}:{PIN_ENGINE}"], cwd=REPO)
    if b"def run_live_tv" not in engine or b"def stats_full" not in engine:
        raise SystemExit(f"pin engine missing run_live_tv/stats_full at {PIN_ENGINE}")
    return full


def ensure_pin_kit() -> None:
    pairs = [
        (
            "research/cloud_batch/CLOUD-BATCH-2026-10-26/scripts/backtest.py",
            SCRIPTS / "backtest.py",
        ),
        (
            "research/cloud_batch/CLOUD-BATCH-2026-10-26/scripts/build_scan.py",
            SCRIPTS / "build_scan.py",
        ),
        (
            "research/cloud_batch/CLOUD-BATCH-2026-10-26/data/universe_replace_only_436.csv",
            UNI_CSV,
        ),
    ]
    for src, dest in pairs:
        dest.parent.mkdir(parents=True, exist_ok=True)
        dest.write_bytes(subprocess.check_output(["git", "show", f"{PIN_SHA}:{src}"], cwd=REPO))


def weekly_from_daily(r: pd.Series, fridays: list[pd.Timestamp]) -> np.ndarray:
    out = np.zeros(len(fridays) - 1, dtype=float)
    for i in range(len(fridays) - 1):
        seg = r[(r.index > fridays[i]) & (r.index <= fridays[i + 1])]
        if len(seg):
            out[i] = float((1.0 + seg).prod() - 1.0)
    return out


def days_in_weeks(
    days: pd.DatetimeIndex, fridays: list[pd.Timestamp], week_ids: list[int]
) -> pd.Series:
    mask = pd.Series(False, index=days)
    for i in week_ids:
        mask |= (days > fridays[i]) & (days <= fridays[i + 1])
    return mask


def group_weeks(g: int) -> list[int]:
    return list(range(GROUP_BOUNDS[g], GROUP_BOUNDS[g + 1]))


def train_weeks_for_split(split: tuple[int, int]) -> list[int]:
    test = set()
    for g in split:
        test.update(group_weeks(g))
    train = [w for w in range(ANCHOR_T) if w not in test]
    train_set = set(train)
    for g in split:
        weeks = group_weeks(g)
        a, b = weeks[0], weeks[-1]
        purge = [a - 1]
        embargo = list(range(b + 1, b + 5))
        for w in purge + embargo:
            if w in train_set:
                train_set.discard(w)
    return sorted(train_set)


def pick_cpcv_book(train_stats: dict[str, dict[str, float]]) -> str:
    finite_any = False
    for bid in CPCV_MENU:
        cal = train_stats[bid]["Calmar"]
        if isinstance(cal, (int, float)) and math.isfinite(cal):
            finite_any = True
            break
    if not finite_any:
        return "FACE"

    def key(bid: str) -> tuple:
        st = train_stats[bid]
        cal = st["Calmar"]
        ret = st["ret"]
        finite = isinstance(cal, (int, float)) and math.isfinite(cal)
        ret_f = ret if isinstance(ret, (int, float)) and math.isfinite(ret) else float("-inf")
        order = CPCV_MENU.index(bid)
        if not finite:
            return (1, 0.0, 0.0, order)
        return (0, -float(cal), -float(ret_f), order)

    return min(CPCV_MENU, key=key)


def path_median(cals: list[float]) -> float:
    keyed: list[float] = []
    for c in cals:
        if c is None or not isinstance(c, (int, float)) or not math.isfinite(c):
            keyed.append(float("-inf"))
        else:
            keyed.append(float(c))
    keyed.sort()
    a, b = keyed[2], keyed[3]
    if not math.isfinite(a) or not math.isfinite(b):
        return float("nan")
    return 0.5 * (a + b)


def jnum(x: float | None) -> float | None:
    if x is None:
        return None
    if isinstance(x, (int, float)) and math.isfinite(x):
        return float(x)
    return None


def empty_row() -> dict[str, Any]:
    return {c: "" for c in TABLE_COLS}


def write_outputs(
    summary: dict[str, Any],
    table_rows: list[dict[str, Any]],
    equity_rows: list[dict[str, Any]],
    series: dict[str, pd.Series],
    path_series: dict[str, pd.Series],
    report: str,
) -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / "REPORT.md").write_text(report, encoding="utf-8")
    (OUT / "summary.json").write_text(
        json.dumps(summary, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    pd.DataFrame(table_rows, columns=TABLE_COLS).to_csv(OUT / "table.csv", index=False)
    pd.DataFrame(equity_rows, columns=["date", "book", "nav"]).to_csv(
        OUT / "equity.csv", index=False
    )

    fig, ax = plt.subplots(figsize=(11.2, 6.2))
    for tid, *_rest in TRIALS:
        nav = (1.0 + series[tid]).cumprod()
        if tid == "FACE":
            ax.plot(nav.index, nav.values, color="black", lw=2.2, label="FACE", zorder=5)
        else:
            ax.plot(nav.index, nav.values, color="0.65", lw=0.8, alpha=0.85)
    for m in range(6):
        pid = f"P{m}"
        nav = (1.0 + path_series[pid]).cumprod()
        ax.plot(
            nav.index,
            nav.values,
            ls="--",
            lw=1.1,
            color=f"C{m}",
            label=pid,
            zorder=4,
        )
    ax.set_yscale("log")
    ax.set_title("overfit-guards equity (log) · FACE black · 12 trials gray · CPCV paths dashed")
    ax.set_ylabel("nav")
    ax.legend(loc="upper left", fontsize=8, ncol=4, frameon=False)
    ax.grid(True, which="both", ls=":", alpha=0.35)
    fig.tight_layout()
    fig.savefig(OUT / "equity_curve.png", dpi=130)
    plt.close(fig)


def build_report(
    ap: bool,
    face_st: dict[str, float],
    trial_rows: list[dict[str, Any]],
    dsr_txt: list[str],
    path_txt: list[str],
    split_txt: list[str],
    verdict: str,
    falsify: str,
    n_weeks: int,
    t_hold: int,
    n_codes: int,
    actual_end: str,
) -> str:
    closer_158 = abs(face_st["ret"] - 1.583) < abs(face_st["ret"] - 1.316)
    lines = [
        BOARD_Q,
        "",
        "## 锚点门",
        f"- 针 `source_sha={PIN_SHA}`；窗 {EVAL_START} → {actual_end}；日历周 {n_weeks}（要 349）；持有周 T={t_hold}（要 348）；AUM≥2 只数 {n_codes}（要 324）。",
        f"- 面 LIVE1430-B45-S20-max5：ret={face_st['ret']:.6f}（锚 1.316±0.005），maxDD={face_st['maxDD']:.6f}（锚 −0.188±0.002），Calmar={face_st['Calmar']:.6f}（锚 0.70±0.02）。",
        f"- 更接近 {'158.3%/0.94（TV 网格，跑错引擎）' if closer_158 else '131.6%/0.70（btheta 针）'}。",
        f"- anchor_pass={'true' if ap else 'false'}。",
        "",
        "## 13 本主表",
        "| id | θ | maxN | σ* | ret | maxDD | CAGR | Calmar | sr_week | in_cpcv |",
        "|----|---|------|----|-----|-------|------|--------|---------|---------|",
    ]
    for row in trial_rows:
        lines.append(
            f"| {row['id']} | {row['theta']} | {row['maxN']} | {row['sigma']} | "
            f"{row['ret']} | {row['maxDD']} | {row['CAGR']} | {row['Calmar']} | "
            f"{row['sr_week']} | {row['in_cpcv']} |"
        )
    lines += ["", "## DSR 输入与结果"] + dsr_txt
    lines += ["", "## 6 条选择路径 Calmar"] + path_txt
    lines += ["", "## 21 个 split 选择记录"] + split_txt
    lines += [
        "",
        "## 证伪段",
        falsify,
        "",
        "## 红线",
        "不写 strategy_exec / LIVE_OPS / champion_mast / 固收+ / 红利袖。不换冠。N=13，邻档仅 FACE/B40/B50/TV22/TV28/S4/S6。FLAG 只指向 OVERFIT/HOLD，都不换冠。",
        f"family_verdict={verdict}；champion_swap=false；crown=NO；positive_ids=[]。",
    ]
    return "\n".join(lines) + "\n"


def main() -> None:
    if len(TRIALS) != 13:
        raise SystemExit("N must be 13")
    if [t[0] for t in TRIALS].count("FACE") != 1:
        raise SystemExit("FACE must appear once")
    extra = [t[0] for t in TRIALS if t[0] not in {x[0] for x in TRIALS}]
    if extra:
        raise SystemExit(f"unknown trial {extra}")
    for bid in CPCV_MENU:
        if bid not in {t[0] for t in TRIALS}:
            raise SystemExit(f"CPCV menu id {bid} not in the 13")

    print("DSR fixtures…", flush=True)
    run_dsr_fixtures()

    source_sha = resolve_pin()
    ensure_pin_kit()
    if not UNI_CSV.exists():
        raise SystemExit("pin universe missing")

    t0 = time.time()
    for p in (WEEK, FACE_CSV, DAY_DIR, NOON_CSV, SINA_DAILY, SNAP_CACHE):
        if not Path(p).exists():
            raise SystemExit(f"missing research cache path {p}")

    print("load universe + extended 14:30 + week…", flush=True)
    uni = pd.read_csv(UNI_CSV)
    uni["code"] = uni["code"].astype(str).str.zfill(6)
    uni = uni[uni["aum"] >= 2].copy()
    codes = uni["code"].tolist()
    aum = {r.code: float(r.aum or 0) for r in uni.itertuples()}
    code_set = set(codes)
    n_codes = len(codes)

    noon = pd.read_csv(NOON_CSV)
    noon["code"] = noon["etf_code"].astype(str).str.split(".").str[0]
    noon["trade_date"] = noon["trade_date"].astype(str).str[:10]
    noon["friday_week_date"] = noon["friday_week_date"].astype(str).str[:10]
    noon = noon[noon["code"].isin(code_set)].copy()
    if "price_1430" in noon.columns and "price_1130" not in noon.columns:
        noon["price_1130"] = noon["price_1430"]

    face = pd.read_csv(FACE_CSV)
    face["date"] = face["date"].astype(str).str[:10]
    face = face[(face["date"] >= EVAL_START) & (face["date"] <= END_S)].copy()
    calendar = sorted(face["date"].unique().tolist())
    if not calendar:
        raise SystemExit("empty calendar")
    actual_end = calendar[-1]
    n_weeks = len(calendar)
    print(f"calendar {calendar[0]} → {actual_end} n={n_weeks} codes={n_codes}", flush=True)

    breadth_b: dict[str, float] = {}
    for _, row in face.iterrows():
        d = str(row["date"])[:10]
        bv = row.get("b")
        if bv is not None and not (isinstance(bv, float) and math.isnan(bv)):
            breadth_b[d] = float(bv)

    thetas = sorted({th for _i, th, _m, _s in TRIALS})

    def risk_map_for_theta(theta: float) -> dict[str, bool]:
        rmap: dict[str, bool] = {}
        for d in calendar:
            b = breadth_b.get(d)
            rmap[d] = bool(b is not None and b >= theta)
        rmap[calendar[-1]] = False
        return rmap

    risk_by_theta = {th: risk_map_for_theta(th) for th in thetas}

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
        if not ds:
            continue
        alias[c] = {d: hit for d in calendar if (hit := nearest_date(d, ds, 3))}

    print("load sina + daily qfq…", flush=True)
    sina = load_sina_closes(codes)
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
    print(f"mapped qfq_1430={n_map} skip={n_skip} empty={n_empty}", flush=True)

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
    sim_keys: dict[tuple[float, int], str] = {}
    for tid, theta, maxn, _sig in TRIALS:
        key = (theta, maxn)
        if key in sim_keys:
            hold_by[tid] = hold_by[sim_keys[key]]
            continue
        print(f"simulate {tid} θ={theta} maxN={maxn}…", flush=True)
        _trades, hold, st = simulate(
            calendar,
            snaps,
            closes_w_sig,
            alias,
            aum,
            daily,
            risk_by_theta[theta],
            sharpe_key,
            tid,
            True,
            20,
            maxn,
        )
        hold_by[tid] = hold
        sim_keys[key] = tid
        rows_h = []
        for d in calendar[:-1]:
            codes_h = hold.get(d) or []
            rows_h.append({"date": d, "n_held": len(codes_h), "codes": ",".join(codes_h)})
        OUT.mkdir(parents=True, exist_ok=True)
        pd.DataFrame(rows_h).to_csv(OUT / f"holdings_{tid}.csv", index=False)
        print(f"  entries={st['n_entries']} cash_weeks={st['n_cash_weeks']}", flush=True)

    all_codes: set[str] = set()
    for h in hold_by.values():
        for cs in h.values():
            all_codes |= set(cs)
    px_map = {c: daily[c] for c in sorted(all_codes) if c in daily}
    px = pd.DataFrame(px_map).sort_index()
    px = px.loc[(px.index >= EVAL_START) & (px.index <= END_S)]
    Rmat = px.pct_change()
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

    series: dict[str, pd.Series] = {}
    metrics: dict[str, dict[str, float]] = {}
    for tid, _th, _mn, sigma in TRIALS:
        hd = {pd.Timestamp(d): cs for d, cs in hold_by[tid].items()}
        r, _L = run_live_tv(hd, days, px, Rmat, sigma)
        series[tid] = r
        metrics[tid] = stats_full(r)
        print(
            f"  {tid}: ret={pct(metrics[tid]['ret'])} dd={pct(metrics[tid]['maxDD'])} "
            f"Calmar={metrics[tid]['Calmar']:.3f}",
            flush=True,
        )

    face_st = metrics["FACE"]
    ap = (
        actual_end == END_S
        and n_weeks == ANCHOR_N_WEEKS
        and n_codes == ANCHOR_N_CODES
        and abs(face_st["ret"] - ANCHOR_RET) <= RET_TOL
        and abs(face_st["maxDD"] - ANCHOR_MDD) <= MDD_TOL
        and abs(face_st["Calmar"] - ANCHOR_CAL) <= CAL_TOL
    )
    print(f"anchor_pass={ap}", flush=True)

    fridays = [pd.Timestamp(d) for d in calendar]
    week_rets: dict[str, np.ndarray] = {}
    t_hold = None
    for tid, *_rest in TRIALS:
        wr = weekly_from_daily(series[tid], fridays)
        week_rets[tid] = wr
        if t_hold is None:
            t_hold = len(wr)
        elif len(wr) != t_hold:
            # aligned week index required
            summary_blocked = True
            t_hold = -1
            break
    if t_hold != ANCHOR_T:
        # still write four-piece if we have books; mark blocked
        ap = False
        formula_ok = False
    else:
        formula_ok = True
        for tid, *_rest in TRIALS:
            std = float(np.std(week_rets[tid], ddof=1))
            if not math.isfinite(std) or std <= 0:
                formula_ok = False
                break

    sr_map: dict[str, float] = {}
    g3_map: dict[str, float] = {}
    g4_map: dict[str, float] = {}
    for tid, *_rest in TRIALS:
        if t_hold == ANCHOR_T:
            sr, _std, g3, g4 = weekly_moments(week_rets[tid])
        else:
            sr = g3 = g4 = float("nan")
        sr_map[tid] = sr
        g3_map[tid] = g3
        g4_map[tid] = g4

    dsr_undefined = (not formula_ok) or t_hold != ANCHOR_T
    V = sigma_sr = sr_star = dsr_face = psr0 = rho_bar = n_eff = dsr_eff = dsr_max = None
    dsr_max_id = "FACE"
    flag_dsr = False
    if not dsr_undefined and ap:
        srs = np.array([sr_map[t[0]] for t in TRIALS], dtype=float)
        if np.any(~np.isfinite(srs)):
            dsr_undefined = True
        else:
            V = float(np.var(srs, ddof=1))
            sigma_sr = math.sqrt(V)
            sr_star = sigma_sr * z_max(13)
            dsr_face = deflated_sharpe(
                sr_map["FACE"], sigma_sr, ANCHOR_T, 13, g3_map["FACE"], g4_map["FACE"]
            )
            psr0 = deflated_sharpe(
                sr_map["FACE"], 0.0, ANCHOR_T, 13, g3_map["FACE"], g4_map["FACE"]
            )
            mat = np.vstack([week_rets[t[0]] for t in TRIALS])
            corr = np.corrcoef(mat)
            off = corr[~np.eye(13, dtype=bool)]
            rho_bar = float(np.nanmean(off))
            n_eff = 1.0 + (1.0 - rho_bar) * 12.0
            if n_eff is not None and n_eff >= 2:
                dsr_eff = deflated_sharpe(
                    sr_map["FACE"], sigma_sr, ANCHOR_T, n_eff, g3_map["FACE"], g4_map["FACE"]
                )
            best_sr = float("-inf")
            for tid, *_r in TRIALS:
                if sr_map[tid] > best_sr:
                    best_sr = sr_map[tid]
                    dsr_max_id = tid
            dsr_max = deflated_sharpe(
                sr_map[dsr_max_id],
                sigma_sr,
                ANCHOR_T,
                13,
                g3_map[dsr_max_id],
                g4_map[dsr_max_id],
            )
            if dsr_face is None:
                dsr_undefined = True
            else:
                flag_dsr = bool(dsr_face < 0.95)

    # CPCV (always compute real numbers for the four-piece when T=348)
    splits = list(itertools.combinations(range(7), 2))
    if [GROUP_BOUNDS[i + 1] - GROUP_BOUNDS[i] for i in range(7)] != GROUP_SIZES:
        raise SystemExit("group sizes drifted")
    if t_hold != ANCHOR_T or len(fridays) != ANCHOR_N_WEEKS:
        print(f"T={t_hold} n_fridays={len(fridays)}; CPCV groups stay frozen, mark BLOCKED", flush=True)
        dsr_undefined = True
    split_picks: list[str] = []
    split_test_face: list[float] = []
    split_test_sel: list[float] = []
    split_labels: list[str] = []
    cpcv_blocked_short = False
    for si, split in enumerate(splits):
        tw = train_weeks_for_split(split)
        if len(tw) < 52:
            cpcv_blocked_short = True
        train_stats = {}
        for bid in CPCV_MENU:
            mask = days_in_weeks(days, fridays, tw)
            train_stats[bid] = stats_full(series[bid][mask])
        pick = pick_cpcv_book(train_stats)
        test_w: list[int] = []
        for g in split:
            test_w.extend(group_weeks(g))
        tmask = days_in_weeks(days, fridays, test_w)
        split_picks.append(pick)
        split_test_face.append(stats_full(series["FACE"][tmask])["Calmar"])
        split_test_sel.append(stats_full(series[pick][tmask])["Calmar"])
        split_labels.append(f"{split[0]},{split[1]}")

    n_face_sel = sum(1 for p in split_picks if p == "FACE")
    path_series: dict[str, pd.Series] = {}
    path_calmars: list[float] = []
    for m in range(6):
        parts = []
        for g in range(7):
            containing = [s for s in splits if g in s]
            pick = split_picks[splits.index(containing[m])]
            gmask = days_in_weeks(days, fridays, group_weeks(g))
            if g == 0:
                gmask = gmask | (days <= fridays[0])
            parts.append(series[pick][gmask])
        pr = pd.concat(parts).sort_index()
        if pr.index.has_duplicates:
            raise SystemExit(f"path P{m} has duplicate days")
        path_series[f"P{m}"] = pr
        path_calmars.append(stats_full(pr)["Calmar"])

    if n_face_sel == 21:
        for m, pc in enumerate(path_calmars):
            if not (isinstance(pc, float) and math.isfinite(pc) and abs(pc - face_st["Calmar"]) <= 1e-9):
                raise SystemExit(
                    f"FACE selected on all 21 splits but P{m} Calmar {pc} != FACE {face_st['Calmar']}"
                )

    med = path_median(path_calmars)
    flag_cpcv = False
    if ap and not dsr_undefined and not cpcv_blocked_short:
        half = 0.5 * face_st["Calmar"]
        flag_cpcv = (not math.isfinite(med)) or (med < half)

    if (not ap) or dsr_undefined or cpcv_blocked_short:
        verdict = "BLOCKED"
        flag_dsr = False
        flag_cpcv = False
        falsify = "锚点未过。家族结论 BLOCKED。不换冠。"
    elif flag_dsr or flag_cpcv:
        verdict = "OVERFIT"
        who = []
        if flag_dsr:
            who.append("DSR")
        if flag_cpcv:
            who.append("CPCV")
        named = "、".join(who)
        falsify = f"护栏标过拟合：点名 {named}。不换冠。"
    else:
        verdict = "HOLD"
        falsify = "两道护栏都未标。不换冠。"

    # Cleaner BLOCKED falsify: DESIGN allows only the three sentences.
    if verdict == "BLOCKED":
        falsify = "锚点未过。家族结论 BLOCKED。不换冠。"

    null_dsr = (not ap) or dsr_undefined
    summary = {
        "batch": "overfit-guards",
        "champion_swap": False,
        "crown": "NO",
        "source_sha": source_sha,
        "sample": [EVAL_START, END_S],
        "anchor_pass": bool(ap),
        "anchor": {
            "ret": ANCHOR_RET,
            "maxDD": ANCHOR_MDD,
            "Calmar": ANCHOR_CAL,
            "n_weeks": ANCHOR_N_WEEKS,
            "T": ANCHOR_T,
            "n_codes": ANCHOR_N_CODES,
        },
        "N": 13,
        "N_assumption": "BTHETA 4 + TV 6 + MAXSEAT 5, face counted once",
        "V_sr_week": None if null_dsr else jnum(V),
        "sigma_sr_week": None if null_dsr else jnum(sigma_sr),
        "sr_star": None if null_dsr else jnum(sr_star),
        "sr_week_face": None if null_dsr else jnum(sr_map["FACE"]),
        "sr_ann_face_display": None if null_dsr else jnum(sr_map["FACE"] * math.sqrt(52.0)),
        "gamma3": None if null_dsr else jnum(g3_map["FACE"]),
        "gamma4": None if null_dsr else jnum(g4_map["FACE"]),
        "DSR": None if null_dsr else jnum(dsr_face),
        "PSR0": None if null_dsr else jnum(psr0),
        "rho_bar": None if null_dsr else jnum(rho_bar),
        "N_eff": None if null_dsr else jnum(n_eff),
        "DSR_eff": None if null_dsr else jnum(dsr_eff),
        "DSR_max": None if null_dsr else jnum(dsr_max),
        "dsr_max_id": None if null_dsr else dsr_max_id,
        "FLAG_DSR": False if (not ap or dsr_undefined) else bool(flag_dsr),
        "cpcv": {
            "G": 7,
            "k": 2,
            "splits": 21,
            "paths": 6,
            "purge_weeks": 1,
            "embargo_weeks": 4,
        },
        "group_sizes": GROUP_SIZES,
        "path_calmars": [jnum(x) for x in path_calmars],
        "path_calmar_median": jnum(med),
        "calmar_face": jnum(face_st["Calmar"]),
        "FLAG_CPCV": False if (not ap or dsr_undefined or cpcv_blocked_short) else bool(flag_cpcv),
        "n_splits_face_selected": n_face_sel,
        "family_verdict": verdict,
        "positive_ids": [],
    }

    table_rows: list[dict[str, Any]] = []
    trial_report_rows: list[dict[str, Any]] = []
    for tid, theta, maxn, sigma in TRIALS:
        st = metrics[tid]
        row = empty_row()
        row.update(
            {
                "kind": "trial",
                "id": tid,
                "theta": f"{theta:.2f}",
                "maxN": maxn,
                "sigma": f"{sigma:.2f}",
                "ret": f"{st['ret']:.10g}",
                "maxDD": f"{st['maxDD']:.10g}",
                "CAGR": f"{st['CAGR']:.10g}",
                "Calmar": f"{st['Calmar']:.10g}",
                "sr_week": f"{sr_map[tid]:.10g}" if math.isfinite(sr_map[tid]) else "",
                "sr_ann_display": f"{sr_map[tid] * math.sqrt(52):.10g}"
                if math.isfinite(sr_map[tid])
                else "",
                "gamma3": f"{g3_map[tid]:.10g}" if math.isfinite(g3_map[tid]) else "",
                "gamma4": f"{g4_map[tid]:.10g}" if math.isfinite(g4_map[tid]) else "",
                "in_dsr": "true",
                "in_cpcv": "true" if tid in CPCV_SET else "false",
            }
        )
        table_rows.append(row)
        trial_report_rows.append(row)

    for m in range(6):
        row = empty_row()
        pc = path_calmars[m]
        row.update(
            {
                "kind": "path",
                "id": f"P{m}",
                "Calmar": f"{pc:.10g}" if isinstance(pc, float) and math.isfinite(pc) else "",
                "path": m,
            }
        )
        table_rows.append(row)

    for si, split in enumerate(splits):
        row = empty_row()
        tf, ts_ = split_test_face[si], split_test_sel[si]
        row.update(
            {
                "kind": "split",
                "id": f"S{si:02d}",
                "train_pick": split_picks[si],
                "split": split_labels[si],
                "test_calmar_face": f"{tf:.10g}" if isinstance(tf, float) and math.isfinite(tf) else "",
                "test_calmar_selected": f"{ts_:.10g}"
                if isinstance(ts_, float) and math.isfinite(ts_)
                else "",
            }
        )
        table_rows.append(row)

    equity_rows: list[dict[str, Any]] = []
    for book, r in list(series.items()) + [(f"P{m}", path_series[f"P{m}"]) for m in range(6)]:
        nav = (1.0 + r).cumprod()
        for ts, v in nav.items():
            equity_rows.append(
                {"date": pd.Timestamp(ts).strftime("%Y-%m-%d"), "book": book, "nav": float(v)}
            )

    if null_dsr:
        dsr_txt = [
            "- DSR 字段为 null（锚不过或公式无定义）。FLAG_DSR=false。",
            f"- 面周频 SR（若可算）={jnum(sr_map.get('FACE'))}；T={t_hold}。",
        ]
    else:
        dsr_txt = [
            f"- T={ANCHOR_T}；面 sr_week={sr_map['FACE']:.6f}；展示年化 sr_week×√52={sr_map['FACE'] * math.sqrt(52):.4f}。",
            f"- γ3={g3_map['FACE']:.4f}（面，除数 T）；γ4={g4_map['FACE']:.4f}（Pearson，正态=3）。",
            f"- V={V:.8f}；σ_SR={sigma_sr:.6f}；SR*={sr_star:.6f}（零假设均值=0，N=13）。",
            f"- DSR={dsr_face:.6f}；PSR0={psr0:.6f}；FLAG_DSR={str(flag_dsr).lower()}（阈值 0.95）。",
            f"- ρ̄={rho_bar:.4f}；N_eff={n_eff:.4f}；DSR_eff={'null' if dsr_eff is None else dsr_eff}（披露，不改旗）。",
            f"- DSR_max={dsr_max} @ {dsr_max_id}（同一 V、N，打在周频 SR 最大的书上，不改旗）。",
        ]
    path_txt = [
        f"- path_calmars={[round(x, 4) if isinstance(x, float) and math.isfinite(x) else None for x in path_calmars]}",
        f"- median(第3与第4的算术平均)={med:.6f}；0.5×Calmar_FACE={0.5 * face_st['Calmar']:.6f}；FLAG_CPCV={str(summary['FLAG_CPCV']).lower()}。",
        f"- n_splits_face_selected={n_face_sel} / 21。",
    ]
    split_txt = [
        "| id | split | train_pick | test_calmar_face | test_calmar_selected |",
        "|----|-------|------------|------------------|----------------------|",
    ]
    for si, _sp in enumerate(splits):
        split_txt.append(
            f"| S{si:02d} | {split_labels[si]} | {split_picks[si]} | "
            f"{split_test_face[si]:.4f} | {split_test_sel[si]:.4f} |"
        )

    report = build_report(
        ap,
        face_st,
        trial_report_rows,
        dsr_txt,
        path_txt,
        split_txt,
        verdict,
        falsify,
        n_weeks,
        t_hold if t_hold is not None else -1,
        n_codes,
        actual_end,
    )
    write_outputs(summary, table_rows, equity_rows, series, path_series, report)
    print(
        f"done verdict={verdict} FLAG_DSR={summary['FLAG_DSR']} FLAG_CPCV={summary['FLAG_CPCV']} "
        f"elapsed={time.time() - t0:.1f}s",
        flush=True,
    )


if __name__ == "__main__":
    main()
