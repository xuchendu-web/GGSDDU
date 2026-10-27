#!/usr/bin/env python3
"""R2-ER-SECONDARY: S20 band secondary sort by R² / ER / COMBOS (research only).

Four books: F0 + R290S + ER20S + COMBOS. Engine pin 05f0f8a4 (btheta LIVE1430).
champion_swap=false, crown=NO.
"""
from __future__ import annotations

import json
import math
import re
import sys
import time
from collections import Counter, defaultdict
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parent
OUT = ROOT / "out"
KIT = ROOT.parent / "cloud_batch" / "CLOUD-BATCH-2026-10-26"
SCRIPTS = KIT / "scripts"
sys.path.insert(0, str(SCRIPTS))

from backtest import LIVE_PHASE, MIN_BARS, Position, nearest_date, snap_index  # noqa: E402
from build_scan import Bar, classify  # noqa: E402

CACHE = KIT / "data" / "research_cache"
UNI_CSV = KIT / "data" / "universe_replace_only_436.csv"
WEEK = CACHE / "week"
FACE = CACHE / "holdings_ro2_extended.csv"
DAY_DIR = CACHE / "day"
NOON_CSV = CACHE / "fri_1430_through_20261023.csv"
SINA_DAILY = CACHE / "sina_daily"
SNAP_CACHE = KIT / "data" / "cache_1430_snaps.json"
TEMA_PX = Path("/workspace/tema_etf_scan_2018/prices_daily")

SOURCE_SHA = "05f0f8a4f778fde886f3e7b2976646ff4b7d777b"
EVAL_START = "2020-01-03"
END_S = "2026-10-23"
COST_SIDE = 0.001
SIGMA_STAR = 0.25
LCAP = 1.0
LIVE_COST_RT = 0.002
BREADTH_THETA = 0.45
SHARPE_N = 20
MAX_POS = 5

SPEC = json.loads((ROOT / "SPEC.json").read_text(encoding="utf-8"))
ANCHOR = SPEC["anchor"]
ANCH_TOL = SPEC["anchor_tol"]
BOOK_SPECS = SPEC["books"]

NEEDLE = ROOT.parent / "cloud_batch" / "SPIKE-S20-BTHETA-GRID-LIVE1430" / "run.py"


@dataclass
class Cand:
    code: str
    px: float
    fz: float | None
    aum: float
    sharpe: float | None
    r2: float | None = None
    er: float | None = None


def is_spike(snap: dict[str, Any] | None) -> bool:
    if not snap:
        return False
    if snap.get("pending_second_week") or snap.get("in_play_kind") == "box_pending":
        return False
    return bool(snap.get("in_play")) and snap.get("in_play_kind") == "spike_ft"


def sharpe_key(c: Cand) -> tuple:
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
    if sxx <= 0 or syy <= 1e-24 or not np.isfinite(sxx + syy + sxy):
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
    return float(er) if np.isfinite(er) else None


def sort_tuple(value: float | None, s20_index: int, code: str) -> tuple:
    miss = 0 if value is not None else 1
    mag = -(value if value is not None else 0.0)
    return (miss, mag, s20_index, code)


def combo_on_band(r2s: list[float | None], ers: list[float | None]) -> list[float | None] | None:
    idx = [i for i, (r, e) in enumerate(zip(r2s, ers)) if r is not None and e is not None]
    if len(idx) < 2:
        return None

    def _z(vals: list[float]) -> list[float]:
        n = len(vals)
        mu = sum(vals) / n
        var = sum((v - mu) ** 2 for v in vals) / n
        if not (var > 0):
            return [0.0] * n
        sd = var ** 0.5
        return [(v - mu) / sd for v in vals]

    zr = _z([r2s[i] for i in idx])
    ze = _z([ers[i] for i in idx])
    if all(z == 0.0 for z in zr) and all(z == 0.0 for z in ze):
        return None
    out: list[float | None] = [None] * len(r2s)
    for k, i in enumerate(idx):
        out[i] = 0.5 * zr[k] + 0.5 * ze[k]
    return out


def pick(band: list[Cand], slots: int, mode: str) -> tuple[list[Cand], str]:
    if slots <= 0 or not band:
        return [], "fallback"
    band = list(band)
    n_take = min(slots, len(band))
    if mode == "off":
        return band[:n_take], "sorted"
    if mode == "r2_sort":
        if all(c.r2 is None for c in band):
            return band[:n_take], "fallback"
        order = sorted(range(len(band)), key=lambda i: sort_tuple(band[i].r2, i, band[i].code))
        return [band[i] for i in order[:n_take]], "sorted"
    if mode == "er_sort":
        if all(c.er is None for c in band):
            return band[:n_take], "fallback"
        order = sorted(range(len(band)), key=lambda i: sort_tuple(band[i].er, i, band[i].code))
        return [band[i] for i in order[:n_take]], "sorted"
    if mode == "combo_sort":
        scores = combo_on_band([c.r2 for c in band], [c.er for c in band])
        if scores is None or all(s is None for s in scores):
            return band[:n_take], "fallback"
        order = sorted(range(len(band)), key=lambda i: sort_tuple(scores[i], i, band[i].code))
        return [band[i] for i in order[:n_take]], "sorted"
    raise ValueError(mode)


def run_fixtures() -> None:
    px = np.exp(0.01 * np.arange(90))
    assert ols_r2(px) == 1.0
    assert ols_r2(np.full(90, 10.0)) is None
    assert ols_r2(np.concatenate([px[:45], [0.0], px[46:]])) is None
    short_idx = pd.date_range("2020-01-03", periods=89, freq="D")
    assert r2_on(pd.Series(px[:89], index=short_idx), "2020-04-01", 90) is None

    daily_idx = pd.date_range("2019-01-01", periods=200, freq="B")
    closes = pd.Series(np.linspace(10, 20, len(daily_idx)), index=daily_idx)
    signal = "2020-06-15"
    assert r2_on(closes.iloc[:-10], signal, 90) is None

    er_px = pd.Series([10, 11, 12, 13, 14], index=pd.date_range("2020-01-01", periods=5, freq="D"))
    assert abs(kaufman_er(er_px, "2020-01-06", 4) - 1.0) < 1e-12
    zig = pd.Series([10, 12, 11, 13, 12], index=pd.date_range("2020-01-01", periods=5, freq="D"))
    assert abs(kaufman_er(zig, "2020-01-06", 4) - 1 / 3) < 1e-12
    flat = pd.Series([5.0] * 21, index=pd.date_range("2020-01-01", periods=21, freq="D"))
    assert kaufman_er(flat, "2020-01-22", 20) is None

    def mk(code: str, sh: float, r2: float | None = None, er: float | None = None) -> Cand:
        return Cand(code=code, px=1.0, fz=None, aum=1.0, sharpe=sh, r2=r2, er=er)

    band = [mk("A", 3, 0.2), mk("B", 2, 0.4), mk("C", 1, 0.9)]
    take, _ = pick(band, 1, "r2_sort")
    assert [c.code for c in take] == ["C"]

    band2 = [mk("A", 1, None)]
    take2, _ = pick(band2, 1, "r2_sort")
    assert [c.code for c in take2] == ["A"]

    band3 = [mk("A", 3, 0.9), mk("B", 2, 0.01), mk("C", 1, None)]
    take3, _ = pick(band3, 2, "r2_sort")
    assert [c.code for c in take3] == ["A", "B"]

    band4 = [mk("A", 3, None), mk("B", 2, None)]
    take4, how4 = pick(band4, 2, "r2_sort")
    assert how4 == "fallback" and [c.code for c in take4] == ["A", "B"]

    band5 = [mk("A", 3, 0.1), mk("B", 2, 0.2), mk("C", 1, 0.9), mk("D", 0, 0.99)]
    take5, _ = pick(band5[:3], 1, "r2_sort")
    assert take5[0].code != "D"

    band6 = [
        mk("A", 3, 0.95, 0.10),
        mk("B", 2, 0.20, 0.90),
        mk("C", 1, 0.70, 0.70),
    ]
    take6, _ = pick(band6, 1, "combo_sort")
    assert take6[0].code == "C"
    take6a, _ = pick(band6, 1, "r2_sort")
    take6b, _ = pick(band6, 1, "er_sort")
    assert take6a[0].code == "A" and take6b[0].code == "B"

    band7 = band6 + [mk("D", 0, None, 0.99)]
    scores = combo_on_band([c.r2 for c in band7], [c.er for c in band7])
    assert scores is not None
    exp = [-0.151883989, -0.177862767, 0.329746756]
    for i in range(3):
        assert abs(scores[i] - exp[i]) < 1e-9
    assert scores[3] is None
    take7, _ = pick(band7, 1, "combo_sort")
    assert take7[0].code == "C"

    band8 = [mk("A", 2, 0.5, 0.5), mk("B", 1, 0.5, 0.9)]
    take8, _ = pick(band8, 2, "combo_sort")
    assert take8[0].code == "B"

    band9 = [mk("A", 1, 0.5, 0.5)]
    take9, how9 = pick(band9, 1, "combo_sort")
    assert how9 == "fallback"

    band10 = [mk("A", 1, 0.01), mk("B", 0, None)]
    take10, _ = pick(band10, 1, "r2_sort")
    assert take10[0].code == "A"


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
    spec: dict[str, Any],
) -> tuple[list[dict[str, Any]], dict[str, list[str]], dict[str, Any], list[dict[str, Any]]]:
    mode = spec["mode"]
    r2_n = int(spec.get("r2_n") or 0)
    er_n = int(spec.get("er_n") or 0)
    variant = spec["book"]
    max_pos = MAX_POS

    cash = 1.0
    positions: dict[str, Position] = {}
    trades: list[dict[str, Any]] = []
    picks: dict[str, list[str]] = {}
    entry_rows: list[dict[str, Any]] = []

    n_tight = 0
    n_feat = 0
    n_entries = 0
    n_rerank = 0
    n_miss_r2 = 0
    n_miss_er = 0
    n_empty_slots = 0
    n_short_fills = 0
    n_fallback_weeks = 0
    mean_r2_vals: list[float] = []
    mean_er_vals: list[float] = []
    mean_combo_vals: list[float] = []
    pool_sizes: list[int] = []

    def px_on(code: str, d: str) -> float | None:
        return closes_w.get(code, {}).get((alias.get(code) or {}).get(d) or d)

    def snap_at(code: str, d: str) -> dict[str, Any] | None:
        key = (alias.get(code) or {}).get(d) or d
        return snaps.get(code, {}).get(key)

    def equity_now() -> float:
        return cash + sum(p.shares * p.last_px for p in positions.values())

    def build_cands(d: str, skip: set[str]) -> list[Cand]:
        nonlocal n_miss_r2, n_miss_er
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
            c = Cand(
                code=code,
                px=px,
                fz=float(sn.get("falsify_close")) if sn and sn.get("falsify_close") is not None else None,
                aum=aum.get(code) or 0.0,
                sharpe=sh,
            )
            if r2_n > 0 and code in daily:
                c.r2 = r2_on(daily[code], d, r2_n)
                if c.r2 is None:
                    n_miss_r2 += 1
            if er_n > 0 and code in daily:
                c.er = kaufman_er(daily[code], d, er_n)
                if c.er is None:
                    n_miss_er += 1
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
        how = "sorted"
        if not last_bar and risk_on:
            pool = build_cands(d, set(positions))
            slots = max_pos - len(positions)
            if pool:
                n_feat += 1
                if risk_on:
                    pool_sizes.append(len(pool))
            if slots > 0 and len(pool) > slots:
                n_tight += 1
            if slots > 0 and pool:
                pool_rank = sorted([c for c in pool if c.sharpe is not None], key=sharpe_key)
                band_k = max(2 * slots, slots + 2)
                band = pool_rank[:band_k]
                if mode == "combo_sort" and r2_n > 0 and er_n > 0:
                    for c in band:
                        if c.r2 is None and c.code in daily:
                            c.r2 = r2_on(daily[c.code], d, r2_n)
                        if c.er is None and c.code in daily:
                            c.er = kaufman_er(daily[c.code], d, er_n)
                take, how = pick(band, slots, mode)
                if how == "fallback" and slots > 0:
                    n_fallback_weeks += 1
                if len(take) < min(slots, len(band)):
                    n_short_fills += 1
                n_empty_slots += max(0, slots - len(take))
                s20_head = {c.code for c in pool_rank[:slots]}
                take_codes = {c.code for c in take}
                n_rerank += len(take_codes - s20_head)
                for c in take:
                    n_entries += 1
                    entry_rows.append({"date": d, "code": c.code})
                    if c.r2 is not None and r2_n > 0:
                        mean_r2_vals.append(c.r2)
                    if c.er is not None and er_n > 0:
                        mean_er_vals.append(c.er)
                    if mode == "combo_sort":
                        scores = combo_on_band([x.r2 for x in band], [x.er for x in band])
                        if scores:
                            bi = next(j for j, x in enumerate(band) if x.code == c.code)
                            if scores[bi] is not None:
                                mean_combo_vals.append(scores[bi])

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
    exits_by_day: dict[str, list[str]] = defaultdict(list)
    for t in trades:
        exits_by_day[t["exit_date"]].append(t["code"])
    for d in calendar:
        for code in exits_by_day.get(d, []):
            open_codes.discard(code)
        for code in picks.get(d, []):
            open_codes.add(code)
        hold[d] = sorted(open_codes)

    n_cash = sum(1 for d in calendar[:-1] if not (hold.get(d) or []))
    mean_abs_D = float(np.mean(pool_sizes)) if pool_sizes else 0.0
    stats = {
        "n_fridays_queue_gt_seats": n_tight,
        "n_fridays_with_cands": n_feat,
        "n_entries": n_entries,
        "n_trades": len(trades),
        "n_cash_weeks": n_cash,
        "n_rerank": n_rerank if mode != "off" else 0,
        "n_miss_r2": n_miss_r2 if r2_n > 0 else 0,
        "n_miss_er": n_miss_er if er_n > 0 else 0,
        "n_empty_slots": n_empty_slots,
        "n_short_fills": n_short_fills,
        "n_fallback_weeks": n_fallback_weeks if mode != "off" else 0,
        "mean_r2": float(np.mean(mean_r2_vals)) if mean_r2_vals else 0.0,
        "mean_er": float(np.mean(mean_er_vals)) if mean_er_vals else 0.0,
        "mean_combo": float(np.mean(mean_combo_vals)) if mean_combo_vals else 0.0,
        "mean_abs_D": mean_abs_D,
    }
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


def pct(x: float | None) -> str:
    if x is None or (isinstance(x, float) and (math.isnan(x) or math.isinf(x))):
        return "—"
    return f"{100 * x:.1f}%"


def check_anchor(st: dict[str, Any], n_weeks: int, T: int, n_codes: int, end_s: str) -> bool:
    if end_s != END_S:
        return False
    if n_weeks != ANCHOR["n_weeks"]:
        return False
    if T != ANCHOR["T"]:
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


def entry_quality(
    entry_rows: list[dict[str, Any]], calendar: list[str], closes_w: dict[str, dict[str, float]]
) -> tuple[float, float]:
    cal_idx = {d: i for i, d in enumerate(calendar)}
    wins: list[float] = []
    losses: list[float] = []
    for row in entry_rows:
        d0 = row["date"]
        i0 = cal_idx.get(d0)
        if i0 is None or i0 + 1 >= len(calendar):
            continue
        d1 = calendar[i0 + 1]
        p0 = closes_w.get(row["code"], {}).get(d0)
        p1 = closes_w.get(row["code"], {}).get(d1)
        if p0 is None or p1 is None or p0 <= 0:
            continue
        r = p1 / p0 - 1.0
        if r > 0:
            wins.append(r)
        else:
            losses.append(r)
    hit = len(wins) / (len(wins) + len(losses)) if (wins or losses) else 0.0
    if not losses:
        win_size = float("nan") if not wins else float("inf")
    elif not wins:
        win_size = 0.0
    else:
        win_size = float(np.mean(wins) / abs(np.mean(losses)))
    return hit, win_size


def jaccard_entries(a: set[tuple[str, str]], b: set[tuple[str, str]]) -> float:
    if not a and not b:
        return 1.0
    if not a or not b:
        return 0.0
    inter = len(a & b)
    union = len(a | b)
    return inter / union if union else 0.0


def weekly_hold_sets(hold: dict[str, list[str]], calendar: list[str]) -> list[frozenset[str]]:
    return [frozenset(hold.get(d) or []) for d in calendar[:-1]]


def judge_cell(cell: dict[str, Any], f0: dict[str, Any]) -> None:
    if cell["id"] == "F0":
        cell["delta_ret"] = 0.0
        cell["delta_abs_mdd"] = 0.0
        cell["covers"] = True
        cell["window_2020_22"] = True
        cell["window_2023_26"] = True
        cell["verdict"] = "ANCHOR"
        return
    if cell.get("inert"):
        cell["delta_ret"] = cell["ret"] - f0["ret"]
        cell["delta_abs_mdd"] = abs(cell["maxDD"]) - abs(f0["maxDD"])
        cell["covers"] = cell["delta_ret"] >= cell["delta_abs_mdd"]
        cell["window_2020_22"] = cell["w2020_22"]["ret"] >= f0["w2020_22"]["ret"]
        cell["window_2023_26"] = cell["w2023_26"]["ret"] >= f0["w2023_26"]["ret"]
        cell["verdict"] = "证伪·惰性"
        return
    dret = cell["ret"] - f0["ret"]
    d_abs = abs(cell["maxDD"]) - abs(f0["maxDD"])
    cell["delta_ret"] = dret
    cell["delta_abs_mdd"] = d_abs
    covers = dret >= d_abs
    w22 = cell["w2020_22"]["ret"] >= f0["w2020_22"]["ret"]
    w23 = cell["w2023_26"]["ret"] >= f0["w2023_26"]["ret"]
    cell["covers"] = covers
    cell["window_2020_22"] = w22
    cell["window_2023_26"] = w23
    if any(math.isnan(x) for x in (cell["ret"], cell["maxDD"], dret, d_abs)):
        cell["verdict"] = "证伪"
    elif covers and w22 and w23:
        cell["verdict"] = "记正"
    else:
        cell["verdict"] = "证伪"


def best_segment(ex: pd.Series, find_max: bool) -> tuple[pd.Timestamp, pd.Timestamp, float]:
    if ex.empty:
        t0 = ex.index[0] if len(ex) else pd.Timestamp(EVAL_START)
        return t0, t0, 0.0
    cum = ex.cumsum()
    best_val = -float("inf") if find_max else float("inf")
    best_i, best_j = 0, 0
    idx = list(cum.index)
    for i in range(len(idx)):
        for j in range(i + 1, len(idx)):
            val = float(cum.iloc[j] - cum.iloc[i])
            if find_max:
                if val > best_val or (val == best_val and (i < best_i or (i == best_i and j - i < best_j - best_i))):
                    best_val, best_i, best_j = val, i, j
            else:
                if val < best_val or (val == best_val and (i < best_i or (i == best_i and j - i < best_j - best_i))):
                    best_val, best_i, best_j = val, i, j
    if not find_max and best_val == float("inf"):
        best_val = 0.0
    if find_max and best_val == -float("inf"):
        best_val = 0.0
    return idx[best_i], idx[best_j], best_val


def top_codes_in_segment(
    hold: dict[str, list[str]], calendar: list[str], start: pd.Timestamp, end: pd.Timestamp, limit: int = 8
) -> list[str]:
    counts: Counter[str] = Counter()
    for d in calendar:
        ts = pd.Timestamp(d)
        if ts < start or ts > end:
            continue
        for c in hold.get(d) or []:
            counts[c] += 1
    return [c for c, _ in counts.most_common(limit)]


def ensure_needle() -> None:
    if not NEEDLE.exists():
        raise SystemExit(f"missing needle path {NEEDLE}; need commit {SOURCE_SHA}")
    for p in (WEEK, FACE, DAY_DIR, NOON_CSV, SINA_DAILY, SNAP_CACHE, UNI_CSV):
        if not Path(p).exists():
            raise SystemExit(f"missing kit path {p} from {SOURCE_SHA}")


def main() -> None:
    run_fixtures()
    print("fixtures OK", flush=True)
    ensure_needle()

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
    T = len(calendar) - 1

    risk_on_by_fri: dict[str, bool] = {}
    for d in calendar:
        row = face.loc[face["date"] == d]
        b = row["b"].iloc[0] if len(row) else None
        risk_on_by_fri[d] = bool(b is not None and not (isinstance(b, float) and math.isnan(b)) and float(b) >= BREADTH_THETA)
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
    snaps = {c: snap_index((cached.get("by_code") or {}).get(c) or []) for c in codes}

    hold_by: dict[str, dict[str, list[str]]] = {}
    sim_stats: dict[str, Any] = {}
    entry_by: dict[str, list[dict[str, Any]]] = {}
    for spec in BOOK_SPECS:
        print(f"simulate {spec['id']}…", flush=True)
        trades, hold, st, ent = simulate(
            calendar, snaps, closes_w_sig, alias, aum, daily, risk_on_by_fri, spec
        )
        hold_by[spec["book"]] = hold
        sim_stats[spec["book"]] = st
        entry_by[spec["book"]] = ent

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
        sim = sim_stats[name]
        hit, win_size = entry_quality(entry_by[name], calendar, closes_w_sig)
        cell = {
            "id": spec["id"],
            "book": name,
            "mode": spec["mode"],
            "r2_n": spec["r2_n"],
            "er_n": spec["er_n"],
            "ret": st["ret"],
            "maxDD": st["maxDD"],
            "CAGR": st["CAGR"],
            "Calmar": st["Calmar"],
            "avgL": float(L[L > 0].mean()) if (L > 0).any() else 0.0,
            "avg_turnover_1way": avg_to,
            "n_cash_weeks": sim["n_cash_weeks"],
            "n_entries": sim["n_entries"],
            "n_rerank": sim["n_rerank"],
            "n_miss_r2": sim["n_miss_r2"],
            "n_miss_er": sim["n_miss_er"],
            "n_empty_slots": sim["n_empty_slots"],
            "n_short_fills": sim["n_short_fills"],
            "n_fallback_weeks": sim["n_fallback_weeks"],
            "mean_r2": sim["mean_r2"],
            "mean_er": sim["mean_er"],
            "mean_combo": sim["mean_combo"],
            "mean_abs_D": sim["mean_abs_D"],
            "hit_rate": hit,
            "win_size": win_size,
            "w2020_22": {"ret": st2022["ret"], "maxDD": st2022["maxDD"], "Calmar": st2022["Calmar"]},
            "w2023_26": {"ret": st2023["ret"], "maxDD": st2023["maxDD"], "Calmar": st2023["Calmar"]},
        }
        cells.append(cell)
        print(
            f"  {spec['id']}: ret={pct(st['ret'])} dd={pct(st['maxDD'])} Calmar={st['Calmar']:.2f}",
            flush=True,
        )

    f0_cell = next(c for c in cells if c["id"] == "F0")
    f0_hold = hold_by[f0_cell["book"]]
    f0_weekly = weekly_hold_sets(f0_hold, calendar)
    f0_entries = {(r["date"], r["code"]) for r in entry_by[f0_cell["book"]]}

    for c in cells:
        if c["id"] == "F0":
            c["jaccard_vs_f0"] = 1.0
            c["inert"] = False
            continue
        ent_set = {(r["date"], r["code"]) for r in entry_by[c["book"]]}
        c["jaccard_vs_f0"] = jaccard_entries(ent_set, f0_entries)
        c["inert"] = weekly_hold_sets(hold_by[c["book"]], calendar) == f0_weekly

    anchor_pass = check_anchor(f0_cell, len(calendar), T, len(codes), actual_end)
    impl_pass = all(c["n_short_fills"] == 0 for c in cells)
    for spec in BOOK_SPECS:
        cell = next(c for c in cells if c["id"] == spec["id"])
        if (
            cell["mode"] != spec["mode"]
            or cell["r2_n"] != spec["r2_n"]
            or cell["er_n"] != spec["er_n"]
        ):
            impl_pass = False

    print(f"anchor_pass={anchor_pass} impl_pass={impl_pass}", flush=True)

    for c in cells:
        if not anchor_pass:
            c["verdict"] = "BLOCKED"
        elif not impl_pass:
            c["verdict"] = "BLOCKED" if c["id"] != "F0" else "ANCHOR"
        else:
            judge_cell(c, f0_cell)

    positive_ids = [c["id"] for c in cells if c["verdict"] == "记正"]

    # Attribution CSVs
    diff_rows: list[dict[str, Any]] = []
    seg_rows: list[dict[str, Any]] = []
    r_f0 = series[f0_cell["book"]]
    for c in cells:
        if c["id"] == "F0":
            continue
        ent_set = {(r["date"], r["code"]) for r in entry_by[c["book"]]}
        adds = ent_set - f0_entries
        drops = f0_entries - ent_set
        by_year_add: Counter[tuple[int, str]] = Counter()
        by_year_drop: Counter[tuple[int, str]] = Counter()
        first_last_add: dict[tuple[int, str], tuple[str, str]] = {}
        first_last_drop: dict[tuple[int, str], tuple[str, str]] = {}
        for d, code in adds:
            y = int(d[:4])
            by_year_add[(y, code)] += 1
            fl = first_last_add.setdefault((y, code), (d, d))
            first_last_add[(y, code)] = (min(fl[0], d), max(fl[1], d))
        for d, code in drops:
            y = int(d[:4])
            by_year_drop[(y, code)] += 1
            fl = first_last_drop.setdefault((y, code), (d, d))
            first_last_drop[(y, code)] = (min(fl[0], d), max(fl[1], d))
        for (y, code), n in by_year_add.most_common():
            if sum(1 for (yy, _) in by_year_add if yy == y and by_year_add[(yy, _)] > 0) > 5:
                pass
        for y in sorted({yy for yy, _ in by_year_add} | {yy for yy, _ in by_year_drop}):
            add_codes = [(code, by_year_add[(y, code)]) for (yy, code) in by_year_add if yy == y]
            add_codes.sort(key=lambda x: (-x[1], x[0]))
            for code, n in add_codes[:5]:
                fd, ld = first_last_add[(y, code)]
                diff_rows.append(
                    {"year": y, "id": c["id"], "side": "ADD", "code": code, "n_events": n, "first_date": fd, "last_date": ld}
                )
            drop_codes = [(code, by_year_drop[(y, code)]) for (yy, code) in by_year_drop if yy == y]
            drop_codes.sort(key=lambda x: (-x[1], x[0]))
            for code, n in drop_codes[:5]:
                fd, ld = first_last_drop[(y, code)]
                diff_rows.append(
                    {"year": y, "id": c["id"], "side": "DROP", "code": code, "n_events": n, "first_date": fd, "last_date": ld}
                )

        ex = series[c["book"]] - r_f0
        ex = ex.reindex(days).fillna(0.0)
        if c["inert"]:
            seg_rows.append(
                {
                    "id": c["id"],
                    "kind": "BIGWIN",
                    "start": str(days[0].date()),
                    "end": str(days[-1].date()),
                    "years": "",
                    "delta_cum_ex": 0.0,
                    "n_weeks": 0,
                    "uniq_book": "",
                    "uniq_f0": "",
                    "n_shared": 0,
                }
            )
            seg_rows.append(
                {
                    "id": c["id"],
                    "kind": "BIGLOSS",
                    "start": str(days[0].date()),
                    "end": str(days[-1].date()),
                    "years": "",
                    "delta_cum_ex": 0.0,
                    "n_weeks": 0,
                    "uniq_book": "",
                    "uniq_f0": "",
                    "n_shared": 0,
                }
            )
        else:
            s_win, e_win, d_win = best_segment(ex, True)
            s_loss, e_loss, d_loss = best_segment(ex, False)
            hold_b = hold_by[c["book"]]
            ub = ";".join(top_codes_in_segment(hold_b, calendar, s_win, e_win))
            uf = ";".join(top_codes_in_segment(f0_hold, calendar, s_win, e_win))
            seg_rows.append(
                {
                    "id": c["id"],
                    "kind": "BIGWIN",
                    "start": str(s_win.date()),
                    "end": str(e_win.date()),
                    "years": f"{s_win.year}" if s_win.year == e_win.year else f"{s_win.year}-{e_win.year}",
                    "delta_cum_ex": d_win,
                    "n_weeks": int((e_win - s_win).days / 7),
                    "uniq_book": ub,
                    "uniq_f0": uf,
                    "n_shared": len(set(ub.split(";")) & set(uf.split(";"))) if ub and uf else 0,
                }
            )
            ub2 = ";".join(top_codes_in_segment(hold_b, calendar, s_loss, e_loss))
            uf2 = ";".join(top_codes_in_segment(f0_hold, calendar, s_loss, e_loss))
            seg_rows.append(
                {
                    "id": c["id"],
                    "kind": "BIGLOSS",
                    "start": str(s_loss.date()),
                    "end": str(e_loss.date()),
                    "years": f"{s_loss.year}" if s_loss.year == e_loss.year else f"{s_loss.year}-{e_loss.year}",
                    "delta_cum_ex": d_loss,
                    "n_weeks": int((e_loss - s_loss).days / 7),
                    "uniq_book": ub2,
                    "uniq_f0": uf2,
                    "n_shared": len(set(ub2.split(";")) & set(uf2.split(";"))) if ub2 and uf2 else 0,
                }
            )

    pd.DataFrame(diff_rows).to_csv(OUT / "entries_diff_by_year.csv", index=False)
    pd.DataFrame(seg_rows).to_csv(OUT / "segment_attribution.csv", index=False)

    # table.csv
    cols = [
        "id", "book", "mode", "r2_n", "er_n", "ret", "maxDD", "CAGR", "Calmar",
        "w2020_22_ret", "w2020_22_maxDD", "w2020_22_Calmar",
        "w2023_26_ret", "w2023_26_maxDD", "w2023_26_Calmar",
        "avgL", "avg_turnover_1way", "n_cash_weeks", "n_entries", "n_rerank",
        "n_miss_r2", "n_miss_er", "n_empty_slots", "n_short_fills", "n_fallback_weeks",
        "mean_r2", "mean_er", "mean_combo", "mean_abs_D", "hit_rate", "win_size",
        "jaccard_vs_f0", "inert", "delta_ret", "delta_abs_mdd", "covers",
        "window_2020_22", "window_2023_26", "verdict",
    ]
    table_rows = []
    for c in cells:
        table_rows.append(
            {
                "id": c["id"],
                "book": c["book"],
                "mode": c["mode"],
                "r2_n": c["r2_n"],
                "er_n": c["er_n"],
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
                "n_miss_r2": c["n_miss_r2"],
                "n_miss_er": c["n_miss_er"],
                "n_empty_slots": c["n_empty_slots"],
                "n_short_fills": c["n_short_fills"],
                "n_fallback_weeks": c["n_fallback_weeks"],
                "mean_r2": c["mean_r2"],
                "mean_er": c["mean_er"],
                "mean_combo": c["mean_combo"],
                "mean_abs_D": c["mean_abs_D"],
                "hit_rate": c["hit_rate"],
                "win_size": c["win_size"],
                "jaccard_vs_f0": c["jaccard_vs_f0"],
                "inert": c["inert"],
                "delta_ret": c.get("delta_ret", 0.0),
                "delta_abs_mdd": c.get("delta_abs_mdd", 0.0),
                "covers": c.get("covers", False),
                "window_2020_22": c.get("window_2020_22", False),
                "window_2023_26": c.get("window_2023_26", False),
                "verdict": c["verdict"],
            }
        )
    pd.DataFrame(table_rows, columns=cols).to_csv(OUT / "table.csv", index=False)

    eq_long = []
    for spec in BOOK_SPECS:
        name = spec["book"]
        nav = (1 + series[name]).cumprod()
        for dt, nv in nav.items():
            eq_long.append({"date": dt.strftime("%Y-%m-%d"), "book": name, "nav": float(nv)})
    pd.DataFrame(eq_long).to_csv(OUT / "equity.csv", index=False)

    fig, ax = plt.subplots(figsize=(11, 5.5), dpi=120)
    f0_name = f0_cell["book"]
    nav_f0 = (1 + series[f0_name]).cumprod()
    ax.plot(nav_f0.index, nav_f0.values, color="black", lw=2.2, label="F0")
    for spec in BOOK_SPECS[1:]:
        nav = (1 + series[spec["book"]]).cumprod()
        ax.plot(nav.index, nav.values, color="gray", lw=1.0, alpha=0.85, label=spec["id"])
    ax.set_yscale("log")
    ax.set_title("R2-ER-SECONDARY（F0 黑线 vs 次级排序）")
    ax.set_ylabel("净值（对数）")
    ax.grid(True, alpha=0.3)
    ax.legend(fontsize=8)
    fig.tight_layout()
    fig.savefig(OUT / "equity_curve.png")
    plt.close(fig)

    design = (ROOT / "DESIGN.md").read_text(encoding="utf-8")
    headline = design.split("\n")[2].strip()
    h1_m = re.search(r"## H1\s+```\n(.*?)```", design, re.S)
    h1_block = h1_m.group(1).strip() if h1_m else ""

    attrib_pass = all(
        any(r["id"] == bid and r["kind"] == "BIGWIN" for r in seg_rows)
        and any(r["id"] == bid and r["kind"] == "BIGLOSS" for r in seg_rows)
        for bid in ("R290S", "ER20S", "COMBOS")
    )

    if not anchor_pass or not impl_pass or not attrib_pass:
        family_verdict = "BLOCKED"
    elif positive_ids:
        family_verdict = "H1_REJECT"
    else:
        family_verdict = "H1_HOLD"

    h1_sentence = (
        "H1 成立：S20 短名单上的 R²/ER 次级排序无记正。"
        if family_verdict == "H1_HOLD"
        else (
            f"H1 证伪：{', '.join(positive_ids)} 记正。"
            if family_verdict == "H1_REJECT"
            else "家族 BLOCKED，不得判卷。"
        )
    )

    attrib_b = "\n".join(
        f"- **{c['id']}** vs F0 Jaccard = {c['jaccard_vs_f0']:.3f}"
        for c in cells
        if c["id"] != "F0"
    )
    attrib_c = "\n".join(
        f"- **{c['id']}**：Δret 2020–22 = {100*(c['w2020_22']['ret']-f0_cell['w2020_22']['ret']):+.1f}pp "
        f"({'窗过' if c.get('window_2020_22') else '踏空'})；2023–26 = "
        f"{100*(c['w2023_26']['ret']-f0_cell['w2023_26']['ret']):+.1f}pp "
        f"({'窗过' if c.get('window_2023_26') else '踏空'})"
        for c in cells
        if c["id"] != "F0"
    )
    attrib_d = "\n".join(
        f"- **{c['id']}**：换手 {c['avg_turnover_1way']:.4f} vs F0 {f0_cell['avg_turnover_1way']:.4f}；"
        f"空仓周 {c['n_cash_weeks']} vs F0 {f0_cell['n_cash_weeks']}；n_empty_slots={c['n_empty_slots']}"
        for c in cells
        if c["id"] != "F0"
    )
    attrib_e_parts = []
    for c in cells:
        if c["id"] == "F0":
            continue
        if c["inert"]:
            attrib_e_parts.append(f"- **{c['id']}**：与 F0 席位逐周相同，无名字可列。")
        else:
            yrs = sorted({r["year"] for r in diff_rows if r["id"] == c["id"]})
            attrib_e_parts.append(f"- **{c['id']}**：有 diff 年份 {yrs}；详见 entries_diff_by_year.csv / segment_attribution.csv。")
    attrib_e = "\n".join(attrib_e_parts)

    report = f"""{headline}

```
{h1_block}
```

## 准则原文

S20 短名单 `band_k=max(2·slots, slots+2)` 内按 R²(N=90) / ER(N=20) / COMBOS 次级排序；无硬闸、不替 S20、无 θ。面层 B45 + spike_ft max5 + E0 + TV25 + Fri≥14:30 + 0.2% RT + L≤1 + AUM≥2 亿。

## 实现要点

针 `{SOURCE_SHA}`；`n_short_fills` 全为 0 则 `impl_pass=true`。F0 锚 {pct(ANCHOR['ret'])} / {pct(ANCHOR['maxDD'])} / Calmar {ANCHOR['Calmar']:.2f}。

## 主表

| id | ret | maxDD | Calmar | w2020-22 | w2023-26 | n_rerank | Jaccard | verdict |
|---|---:|---:|---:|---:|---:|---:|---:|---|
"""
    for c in cells:
        report += (
            f"| {c['id']} | {pct(c['ret'])} | {pct(c['maxDD'])} | {c['Calmar']:.2f} | "
            f"{pct(c['w2020_22']['ret'])} | {pct(c['w2023_26']['ret'])} | {c['n_rerank']} | "
            f"{c['jaccard_vs_f0']:.3f} | {c['verdict']} |\n"
        )

    report += f"""
## ATTRIBUTION

(a) 机制：只在 S20 短名单内做了路径质量次级排序；未动 B45 / spike_ft / max5 / E0 / TV25 / SHARPE20 宇宙 / Fri≥14:30 / 0.2%RT / AUM≥2；无硬闸、无替换 S20、无 θ；第三本 COMBOS。

(b) 席位重叠：
{attrib_b}

(c) 两窗 Δ：
{attrib_c}

(d) 换手与空仓周：
{attrib_d}

(e) 名字·年份与大赢/大亏段：
{attrib_e}

ATTRIBUTION 不进 verdict。

## 一句判词

锚 `anchor_pass={anchor_pass}`；实现 `impl_pass={impl_pass}`；ATTRIBUTION `attrib_pass={attrib_pass}`。
**{h1_sentence}** `family_verdict={family_verdict}`。不换冠。
"""
    (OUT / "REPORT.md").write_text(report, encoding="utf-8")

    summary = {
        "batch": "r2-er-secondary",
        "knife_id": "R2-ER-SECONDARY",
        "champion_swap": False,
        "crown": "NO",
        "source_sha": SOURCE_SHA,
        "sample": [EVAL_START, actual_end],
        "anchor_pass": anchor_pass,
        "impl_pass": impl_pass,
        "attrib_pass": attrib_pass,
        "anchor": {**ANCHOR, "n_weeks": len(calendar), "T": T},
        "face_id": "F0",
        "primary": "R290S",
        "third_book": "COMBOS",
        "mechanism": SPEC.get("mechanism", ""),
        "h1": h1_sentence,
        "family_verdict": family_verdict,
        "positive_ids": positive_ids if family_verdict == "H1_REJECT" else [],
        "skipped_ids": SPEC.get("forbidden_ids", []),
        "side_note": {"AG40S": "235.6%/-14.8%/1.32 mechanism template only; not a cell; not the ruler RHS"},
        "cells": cells,
        "elapsed_sec": round(time.time() - t0, 1),
    }
    (OUT / "summary.json").write_text(json.dumps(summary, ensure_ascii=False, indent=2, default=str), encoding="utf-8")
    print(f"done family_verdict={family_verdict} anchor_pass={anchor_pass}", flush=True)


if __name__ == "__main__":
    main()
