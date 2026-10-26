#!/usr/bin/env python3
"""EXIT-ATR-CHANDELIER: FACE replay + entry-path chandelier stop (HH 鈭?k路Wilder ATR).

Books: FACE (E0 only), CH-ATR14脳3 (main), CH-ATR14脳2.5 / 脳3.5 / CH-ATR22脳3 neighbors.
Frozen: B45 + spike_ft max5 + SHARPE20 + E0 + TV25 + Fri鈮?4:30/close + 0.2%RT + L鈮?.
Exploration 鈥?no crown swap. Engine pin: SPIKE-S20-BTHETA-GRID-LIVE1430 @ 05f0f8a4.
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
DESIGN_MD = Path(__file__).resolve().parent / "DESIGN.md"
KNIFE_MD = Path(__file__).resolve().parent / "knife.md"
SOURCE_SHA = "05f0f8a4f778fde886f3e7b2976646ff4b7d777b"
ANCHOR_RET = 1.316
ANCHOR_MDD = -0.188
ANCHOR_SHARPE = 0.82
ANCHOR_RET_TOL = 0.02
ANCHOR_MDD_TOL = 0.01
ANCHOR_SHARPE_TOL = 0.03
TV_GRID_RET_TRAP = 1.583  # wrong engine 鈥?BLOCKED if in-run FACE lands here

BOOKS: list[tuple[str, str, int | None, float | None]] = [
    ("FACE", "FACE", None, None),
    ("CH-ATR14x3", "CH-ATR14x3", 14, 3.0),
    ("CH-ATR14x2.5", "CH-ATR14x2.5", 14, 2.5),
    ("CH-ATR14x3.5", "CH-ATR14x3.5", 14, 3.5),
    ("CH-ATR22x3", "CH-ATR22x3", 22, 3.0),
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


@dataclass
class OhlcSeries:
    dates: list[str]
    highs: np.ndarray
    lows: np.ndarray
    closes: np.ndarray
    date_to_i: dict[str, int]
    atr_by_n: dict[int, np.ndarray]


def _ohlc_from_bars(bars: list[dict[str, Any]]) -> OhlcSeries | None:
    dates: list[str] = []
    highs: list[float] = []
    lows: list[float] = []
    closes: list[float] = []
    for b in bars:
        d = b.get("date")
        if not d or d > END_S:
            continue
        o, h, l, cl = float(b["o"]), float(b["h"]), float(b["l"]), float(b["c"])
        if min(o, h, l, cl) <= 0:
            continue
        dates.append(str(d)[:10])
        highs.append(h)
        lows.append(l)
        closes.append(cl)
    if len(dates) < 10:
        return None
    return OhlcSeries(
        dates=dates,
        highs=np.array(highs, dtype=float),
        lows=np.array(lows, dtype=float),
        closes=np.array(closes, dtype=float),
        date_to_i={d: i for i, d in enumerate(dates)},
        atr_by_n={},
    )


def load_ohlc(
    codes: list[str],
    daily: dict[str, pd.Series],
    sina: dict[str, dict[str, float]],
) -> dict[str, OhlcSeries]:
    """Day-cache qfq OHLC; missing codes: sina OHLC scaled by qfq_close/sina_close (same chain as qfq_1430)."""
    out: dict[str, OhlcSeries] = {}

    def load_sina_scaled(code: str) -> OhlcSeries | None:
        fp = SINA_DAILY / f"{code}.csv"
        if not fp.exists() or code not in daily:
            return None
        df = pd.read_csv(fp)
        if not {"date", "open", "high", "low", "close"}.issubset(df.columns):
            return None
        qfq = daily[code]
        bars: list[dict[str, Any]] = []
        for row in df.itertuples():
            d = str(row.date)[:10]
            if d < EVAL_START or d > END_S:
                continue
            b = float(row.close)
            if b <= 0:
                continue
            ts = pd.Timestamp(d)
            if ts not in qfq.index:
                sub = qfq.loc[:ts]
                if len(sub) == 0 or (ts - sub.index[-1]).days > 3:
                    continue
                q = float(sub.iloc[-1])
            else:
                q = float(qfq.loc[ts])
            if q <= 0:
                continue
            scale = q / b
            o, h, l, c = float(row.open), float(row.high), float(row.low), b
            bars.append(
                {
                    "date": d,
                    "o": o * scale,
                    "h": h * scale,
                    "l": l * scale,
                    "c": c * scale,
                }
            )
        return _ohlc_from_bars(bars)

    for c in codes:
        fp = DAY_DIR / f"{c}.json"
        ser = None
        if fp.exists():
            j = json.loads(fp.read_text(encoding="utf-8"))
            bars = j.get("bars") if isinstance(j, dict) else j
            if bars:
                ser = _ohlc_from_bars(bars)
        if ser is None:
            ser = load_sina_scaled(c)
        if ser is not None:
            out[c] = ser
    return out


def _wilder_atr_arrays(highs: np.ndarray, lows: np.ndarray, closes: np.ndarray, n: int) -> np.ndarray:
    m = len(highs)
    atr = np.full(m, np.nan)
    if m < n:
        return atr
    tr = np.empty(m)
    tr[0] = highs[0] - lows[0]
    for i in range(1, m):
        tr[i] = max(highs[i] - lows[i], abs(highs[i] - closes[i - 1]), abs(lows[i] - closes[i - 1]))
    atr[n - 1] = float(np.mean(tr[:n]))
    for i in range(n, m):
        atr[i] = (atr[i - 1] * (n - 1) + tr[i]) / n
    return atr


def atr_on_signal(ser: OhlcSeries | None, n: int, signal_friday: str) -> float | None:
    if ser is None:
        return None
    if n not in ser.atr_by_n:
        ser.atr_by_n[n] = _wilder_atr_arrays(ser.highs, ser.lows, ser.closes, n)
    atr_arr = ser.atr_by_n[n]
    prev_idx = -1
    for i, d in enumerate(ser.dates):
        if d < signal_friday:
            prev_idx = i
        else:
            break
    if prev_idx < n - 1:
        return None
    v = float(atr_arr[prev_idx])
    if not np.isfinite(v) or v <= 0:
        return None
    return v


def hh_since_entry(ser: OhlcSeries | None, entry_date: str, signal_friday: str) -> float | None:
    if ser is None:
        return None
    hi = None
    for i, d in enumerate(ser.dates):
        if d < entry_date or d >= signal_friday:
            continue
        h = float(ser.highs[i])
        hi = h if hi is None else max(hi, h)
    return hi


def chandelier_trigger(*, hh_done: float | None, px_1430: float, atr: float | None, k: float) -> bool:
    if hh_done is None or atr is None or atr <= 0 or px_1430 is None:
        return False
    hh = max(hh_done, px_1430)
    return px_1430 < (hh - k * atr)


def e0_reason(sn: dict[str, Any] | None, px: float) -> str | None:
    if not sn:
        return None
    fz = sn.get("falsify_close")
    if fz is not None and px < float(fz):
        return "falsify"
    if sn.get("always_in") != "Long":
        return "always_in_flip"
    if (not sn.get("in_play")) and sn.get("phase") not in LIVE_PHASE:
        return "left_structure"
    return None


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
    ohlc: dict[str, OhlcSeries] | None = None,
    chandelier_n: int | None = None,
    chandelier_k: float | None = None,
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
    n_chandelier = 0
    n_e0 = 0
    n_atr_weeks = 0
    n_atr_skip = 0
    chandelier_log: list[dict[str, Any]] = []

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

        exiting: list[tuple[str, str, float, str | None]] = []
        for code, p in list(positions.items()):
            px = px_on(code, d)
            if last_bar:
                exiting.append((code, "eod_eval", px if px is not None else p.last_px, None))
                continue
            if not risk_on:
                exiting.append((code, "breadth_off", px if px is not None else p.last_px, None))
                continue
            if px is None:
                continue
            sn = snap_at(code, d)
            e0 = e0_reason(sn, px)
            reason = None
            e0_also = None
            if chandelier_n is not None and chandelier_k is not None and p.entry_date != d:
                n_atr_weeks += 1
                ser = (ohlc or {}).get(code)
                atr_v = atr_on_signal(ser, chandelier_n, d)
                hh_d = hh_since_entry(ser, p.entry_date, d)
                if atr_v is None or hh_d is None:
                    n_atr_skip += 1
                elif chandelier_trigger(hh_done=hh_d, px_1430=px, atr=atr_v, k=chandelier_k):
                    reason = "chandelier"
                    if e0:
                        e0_also = e0
                        n_e0 += 1
                    n_chandelier += 1
                    chandelier_log.append(
                        {
                            "date": d,
                            "code": code,
                            "hh_done": hh_d,
                            "px_on": px,
                            "atr": atr_v,
                            "k": chandelier_k,
                            "N": chandelier_n,
                            "e0_also": e0_also,
                        }
                    )
            if reason is None:
                reason = e0
            if reason:
                exiting.append((code, reason, px, e0_also))
            else:
                p.weeks += 1

        for code, reason, px, e0_also in exiting:
            p = positions.pop(code)
            cash += p.shares * px * (1.0 - COST_SIDE)
            if reason in ("falsify", "always_in_flip", "left_structure"):
                n_e0 += 1
            trades.append(
                {
                    "variant": variant,
                    "code": code,
                    "entry_date": p.entry_date,
                    "exit_date": d,
                    "exit_reason": reason,
                    "e0_also": e0_also,
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

    to_vals: list[float] = []
    prev_h: set[str] = set()
    for d in calendar[:-1]:
        cur = set(hold.get(d) or [])
        if prev_h or cur:
            to_vals.append(len(prev_h.symmetric_difference(cur)) / (2.0 * max_pos))
        prev_h = cur
    avg_to = float(np.mean(to_vals)) if to_vals else 0.0

    n_cash = sum(1 for d in calendar[:-1] if not (hold.get(d) or []))
    atr_skip_pct = (n_atr_skip / n_atr_weeks) if n_atr_weeks else 0.0
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
        "avgTO": avg_to,
        "n_chandelier": n_chandelier,
        "n_e0": n_e0,
        "atr_skip_name_week_pct": atr_skip_pct,
    }
    if rank_rows:
        pd.DataFrame(rank_rows).to_csv(OUT / f"entries_{variant}.csv", index=False)
    if chandelier_log:
        pd.DataFrame(chandelier_log).to_csv(OUT / f"chandelier_log_{variant}.csv", index=False)
    return trades, hold, stats


def run_live_tv(
    hold: dict[pd.Timestamp, list[str]], days: pd.DatetimeIndex, px: pd.DataFrame, R: pd.DataFrame
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
        return "-"
    return f"{100 * x:.1f}%"


def sharpe_daily(r: pd.Series) -> float:
    if r is None or len(r) < 2 or r.std(ddof=1) <= 0:
        return float("nan")
    return float(r.mean() / r.std(ddof=1) * np.sqrt(252))


def write_blocked_report(reason: str, cov: dict[str, Any] | None = None) -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    headline = "请拍板：维持面层 B45 + spike_ft max5 + E0 + TV25 + SHARPE20，吊灯主簿无论记正或证伪都不换冠。"
    summary = {
        "batch": "EXIT-ATR-CHANDELIER",
        "champion_swap": False,
        "crown": "NO",
        "source_sha": SOURCE_SHA,
        "sample": [EVAL_START, END_S],
        "anchor_pass": False,
        "anchor": {"ret": ANCHOR_RET, "maxDD": ANCHOR_MDD, "Calmar": 0.70},
        "h1": "CH-ATR14x3 vs FACE: G1 Δret>=Δ|MDD| and G2 2023-26 not missed",
        "family_verdict": "BLOCKED",
        "positive_ids": [],
        "books": [b[0] for b in BOOKS],
        "blocked_reason": reason,
    }
    (OUT / "summary.json").write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
    (OUT / "table.csv").write_text("id,book,blocked\nFACE,FACE,true\n", encoding="utf-8")
    (OUT / "equity.csv").write_text("date,book,nav\n", encoding="utf-8")
    report = f"""{headline}

# REPORT · EXIT-ATR-CHANDELIER

## 1. 准则原文

见 `DESIGN.md` / `knife.md`（H1 两闸相对 in-run FACE）。

## 2. 实现要点

**BLOCKED**：{reason}

## 3. 主表

（未跑通）

## 4. 一句判词

BLOCKED（不换冠）：{reason}
"""
    (OUT / "REPORT.md").write_text(report, encoding="utf-8")
    raise SystemExit(reason)


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    t0 = time.time()
    for p in (WEEK, FACE, DAY_DIR, NOON_CSV, SINA_DAILY):
        if not Path(p).exists():
            write_blocked_report(f"missing research cache path {p}")

    print("EXIT-ATR-CHANDELIER: load universe + 14:30 + week…", flush=True)
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
        write_blocked_report("empty calendar")
    actual_end = calendar[-1]
    print(f"calendar {calendar[0]} → {actual_end} n={len(calendar)}", flush=True)

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

    print("load sina + daily qfq + day OHLC…", flush=True)
    sina = load_sina_closes(codes)
    daily = load_daily_closes(codes, sina)
    ohlc = load_ohlc(codes, daily, sina)
    print(f"daily={len(daily)} ohlc={len(ohlc)} sina={len(sina)}", flush=True)

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

    if not SNAP_CACHE.exists():
        write_blocked_report(f"missing snap cache {SNAP_CACHE}")
    cached = json.loads(SNAP_CACHE.read_text(encoding="utf-8"))
    if cached.get("end") != actual_end:
        print(f"warn snap end {cached.get('end')} vs calendar {actual_end}", flush=True)
    by_rows = cached.get("by_code") or {}
    snaps = {c: snap_index(by_rows.get(c) or []) for c in codes}

    hold_by: dict[str, dict[str, list[str]]] = {}
    sim_stats: dict[str, Any] = {}
    trades_by: dict[str, list[dict[str, Any]]] = {}
    for bid, label, cn, ck in BOOKS:
        print(f"simulate {label}…", flush=True)
        trades, hold, st = simulate(
            calendar,
            snaps,
            closes_w_sig,
            alias,
            aum,
            daily,
            risk_b45,
            sharpe_key,
            bid,
            True,
            20,
            5,
            ohlc=ohlc,
            chandelier_n=cn,
            chandelier_k=ck,
        )
        hold_by[bid] = hold
        sim_stats[bid] = st
        trades_by[bid] = trades
        pd.DataFrame(trades).to_csv(OUT / f"trades_{bid}.csv", index=False)
        if st.get("n_chandelier", 0) and bid == "FACE":
            raise SystemExit("FACE row has chandelier exits — overlay leak")

    max_skip = max(st.get("atr_skip_name_week_pct", 0) for st in sim_stats.values() if st.get("n_atr_weeks", 0) or True)
    # only chandelier books have atr weeks
    ch_skip = max(
        sim_stats[b[0]].get("atr_skip_name_week_pct", 0) for b in BOOKS if b[2] is not None
    )
    if ch_skip > 0.05:
        write_blocked_report(f"atr_skip_name_week_pct={100*ch_skip:.1f}% > 5%")

    all_codes: set[str] = set()
    for h in hold_by.values():
        for cs in h.values():
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
                    px_map[c] = pd.Series([float(b["c"]) for b in bars], index=idx, dtype=float).sort_index()
    px = pd.DataFrame(px_map).sort_index()
    px = px.loc[(px.index >= EVAL_START) & (px.index <= END_S)]
    R = px.pct_change()
    days = px["510300"].dropna().index if "510300" in px.columns else px.dropna(how="all").index
    days = days[(days >= EVAL_START) & (days <= END_S)]
    if len(days) and str(days[-1].date()) < actual_end:
        all_idx = None
        for s in daily.values():
            all_idx = s.index if all_idx is None else all_idx.union(s.index)
        if all_idx is not None:
            days2 = all_idx[(all_idx >= EVAL_START) & (all_idx <= END_S)]
            if len(days2) > len(days):
                days = days2

    series: dict[str, pd.Series] = {}
    Ls_map: dict[str, pd.Series] = {}
    metrics: dict[str, dict[str, Any]] = {}
    for bid, label, _, _ in BOOKS:
        hd = {pd.Timestamp(d): cs for d, cs in hold_by[bid].items()}
        r, L = run_live_tv(hd, days, px, R)
        series[bid] = r
        Ls_map[bid] = L
        st = stats_full(r)
        r2022 = r[(r.index >= "2020-01-01") & (r.index <= "2022-12-31")]
        r2023 = r[r.index >= "2023-01-01"]
        st2022 = stats_full(r2022) if len(r2022) > 5 else {k: float("nan") for k in st}
        st2023 = stats_full(r2023) if len(r2023) > 5 else {k: float("nan") for k in st}
        metrics[bid] = {
            **st,
            "Sharpe": sharpe_daily(r),
            "w2020_22_ret": st2022["ret"],
            "w2020_22_maxDD": st2022["maxDD"],
            "w2020_22_Calmar": st2022["Calmar"],
            "w2023_26_ret": st2023["ret"],
            "w2023_26_maxDD": st2023["maxDD"],
            "w2023_26_Calmar": st2023["Calmar"],
            "avgTO": sim_stats[bid].get("avgTO", float("nan")),
            "avgL": float(L[L > 0].mean()) if (L > 0).any() else 0.0,
            "n_chandelier": sim_stats[bid].get("n_chandelier", 0),
            "n_e0": sim_stats[bid].get("n_e0", 0),
            "atr_skip_name_week_pct": sim_stats[bid].get("atr_skip_name_week_pct", 0.0),
        }

    face_m = metrics["FACE"]
    anchor_pass = (
        abs(face_m["ret"] - ANCHOR_RET) <= ANCHOR_RET_TOL
        and abs(abs(face_m["maxDD"]) - abs(ANCHOR_MDD)) <= ANCHOR_MDD_TOL
        and abs(face_m["Sharpe"] - ANCHOR_SHARPE) <= ANCHOR_SHARPE_TOL
    )
    if abs(face_m["ret"] - TV_GRID_RET_TRAP) < 0.03:
        write_blocked_report("in-run FACE matches TV-grid engine (~158.3%) — wrong pin")
    if not anchor_pass:
        write_blocked_report(
            f"FACE anchor miss ret={pct(face_m['ret'])} MDD={pct(face_m['maxDD'])} "
            f"Sharpe={face_m['Sharpe']:.2f} (want 131.6%/-18.8%/0.82)"
        )

    main_id = "CH-ATR14x3"
    main_m = metrics[main_id]
    d_ret = main_m["ret"] - face_m["ret"]
    d_abs_mdd = abs(main_m["maxDD"]) - abs(face_m["maxDD"])
    g1 = d_ret >= d_abs_mdd
    g2 = (
        main_m["w2023_26_ret"] >= face_m["w2023_26_ret"]
        and main_m["w2023_26_ret"] > 0
    )
    if g1 and g2:
        family_verdict = "记正"
        positive_ids = [main_id]
        verdict = (
            f"记正（不换冠）：CH-ATR14×3 两闸全过。Δret={100*d_ret:+.1f}pp Δ|MDD|={100*d_abs_mdd:+.1f}pp；"
            f"2023–26 {pct(main_m['w2023_26_ret'])} vs FACE {pct(face_m['w2023_26_ret'])}；"
            f"吊灯 {main_m['n_chandelier']} 次，一手换手均 {main_m['avgTO']:.3f}。邻档只旁注。"
        )
    else:
        family_verdict = "证伪"
        positive_ids = []
        fail = []
        if not g1:
            fail.append("G1")
        if not g2:
            fail.append("G2")
        verdict = (
            f"证伪（不换冠）：CH-ATR14×3 未过闸 {'/'.join(fail)}。"
            f"Δret={100*d_ret:+.1f}pp Δ|MDD|={100*d_abs_mdd:+.1f}pp；"
            f"2023–26 {pct(main_m['w2023_26_ret'])} vs FACE {pct(face_m['w2023_26_ret'])}。"
            f"邻档即使全过也不升格。"
        )

    table_rows = []
    for bid, label, cn, ck in BOOKS:
        m = metrics[bid]
        dr = m["ret"] - face_m["ret"]
        dm = abs(m["maxDD"]) - abs(face_m["maxDD"])
        covers = dr >= dm
        w23 = m["w2023_26_ret"] >= face_m["w2023_26_ret"] and m["w2023_26_ret"] > 0
        if bid == "FACE":
            v = "ANCHOR"
            n_s = "off"
            k_s = "off"
        else:
            v = "—"
            n_s = str(cn)
            k_s = str(ck)
        table_rows.append(
            {
                "id": bid,
                "book": label,
                "N": n_s,
                "k": k_s,
                "ret": m["ret"],
                "maxDD": m["maxDD"],
                "CAGR": m["CAGR"],
                "Calmar": m["Calmar"],
                "Sharpe": m["Sharpe"],
                "avgTO": m["avgTO"],
                "avgL": m["avgL"],
                "w2020_22_ret": m["w2020_22_ret"],
                "w2020_22_maxDD": m["w2020_22_maxDD"],
                "w2020_22_Calmar": m["w2020_22_Calmar"],
                "w2023_26_ret": m["w2023_26_ret"],
                "w2023_26_maxDD": m["w2023_26_maxDD"],
                "w2023_26_Calmar": m["w2023_26_Calmar"],
                "n_chandelier": m["n_chandelier"],
                "n_e0": m["n_e0"],
                "atr_skip_name_week_pct": m["atr_skip_name_week_pct"],
                "delta_ret": dr if bid != "FACE" else 0.0,
                "delta_abs_mdd": dm if bid != "FACE" else 0.0,
                "covers": "true" if (bid == "FACE" or covers) else "false",
                "window_2023_26": "true" if (bid == "FACE" or w23) else "false",
                "verdict": v,
            }
        )

    cols = (
        "id,book,N,k,ret,maxDD,CAGR,Calmar,Sharpe,avgTO,avgL,w2020_22_ret,w2020_22_maxDD,"
        "w2020_22_Calmar,w2023_26_ret,w2023_26_maxDD,w2023_26_Calmar,n_chandelier,n_e0,"
        "atr_skip_name_week_pct,delta_ret,delta_abs_mdd,covers,window_2023_26,verdict"
    ).split(",")
    pd.DataFrame(table_rows)[cols].to_csv(OUT / "table.csv", index=False)

    eq_rows = []
    navs = {bid: (1 + series[bid]).cumprod() for bid, _, _, _ in BOOKS}
    for bid in navs:
        for dt, nv in navs[bid].items():
            eq_rows.append({"date": dt.strftime("%Y-%m-%d"), "book": bid, "nav": float(nv)})
    pd.DataFrame(eq_rows).to_csv(OUT / "equity.csv", index=False)

    fig, ax = plt.subplots(figsize=(11, 5.5), dpi=120)
    ax.plot(navs["FACE"].index, navs["FACE"], color="black", lw=2.2, label="FACE")
    ax.plot(navs[main_id].index, navs[main_id], color="#ff6a39", lw=1.8, label=main_id)
    for bid, label, cn, ck in BOOKS:
        if bid in ("FACE", main_id):
            continue
        ax.plot(navs[bid].index, navs[bid], color="gray", lw=0.9, alpha=0.85, label=label)
    ax.set_yscale("log")
    ax.set_title("EXIT-ATR-CHANDELIER vs FACE")
    ax.grid(True, alpha=0.3)
    ax.legend(fontsize=7)
    fig.tight_layout()
    fig.savefig(OUT / "equity_curve.png")
    plt.close(fig)

    design = DESIGN_MD.read_text(encoding="utf-8") if DESIGN_MD.exists() else ""
    knife = KNIFE_MD.read_text(encoding="utf-8") if KNIFE_MD.exists() else ""
    headline = "请拍板：维持面层 B45 + spike_ft max5 + E0 + TV25 + SHARPE20，吊灯主簿无论记正或证伪都不换冠。"

    def md_row(bid: str) -> str:
        m = metrics[bid]
        return (
            f"| {bid} | {pct(m['ret'])} | {pct(m['maxDD'])} | {m['Calmar']:.2f} | {m['Sharpe']:.2f} | "
            f"{m['avgTO']:.3f} | {m['n_chandelier']} | {m['n_e0']} | {100*m['atr_skip_name_week_pct']:.1f}% |"
        )

    neighbor_notes = []
    for bid, label, cn, ck in BOOKS:
        if bid in ("FACE", main_id):
            continue
        m = metrics[bid]
        dr = m["ret"] - face_m["ret"]
        dm = abs(m["maxDD"]) - abs(face_m["maxDD"])
        g1n = dr >= dm
        g2n = m["w2023_26_ret"] >= face_m["w2023_26_ret"] and m["w2023_26_ret"] > 0
        neighbor_notes.append(
            f"- **{label}**：G1={'过' if g1n else '否'} G2={'过' if g2n else '否'}；"
            f"ret {pct(m['ret'])} Calmar {m['Calmar']:.2f}"
        )

    report = f"""{headline}

# REPORT · EXIT-ATR-CHANDELIER

## 1. 准则原文

```
{knife.strip()}
```

H1：主簿 CH-ATR14×3 相对 in-run FACE — Δret≥Δ|MDD|；2023–26 不踏空（≥FACE 后段且为正）。

## 2. 实现要点

- 引擎针 `{SOURCE_SHA}`（BTHETA LIVE1430）；样本 {EVAL_START}→{actual_end}。
- FACE 重放：ret={pct(face_m['ret'])} maxDD={pct(face_m['maxDD'])} Sharpe={face_m['Sharpe']:.2f}（锚 131.6%/-18.8%/0.82）。
- 吊灯：入场后 HH − k×Wilder ATR(N)；E0 保留；退出优先级 breadth/eod → chandelier → E0。
- ATR 跳过（持仓名字-周）：主簿 {100*main_m['atr_skip_name_week_pct']:.1f}%（阈 5%）。

## 3. 主表

| book | ret | maxDD | Calmar | Sharpe | avgTO | n_ch | n_e0 | atr_skip% |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
{md_row('FACE')}
{md_row(main_id)}
{chr(10).join(md_row(b[0]) for b in BOOKS if b[0] not in ('FACE', main_id))}

### 邻档旁注

{chr(10).join(neighbor_notes)}

## 4. 一句判词

{verdict}
"""
    (OUT / "REPORT.md").write_text(report, encoding="utf-8")

    summary = {
        "batch": "EXIT-ATR-CHANDELIER",
        "champion_swap": False,
        "crown": "NO",
        "source_sha": SOURCE_SHA,
        "sample": [calendar[0], actual_end],
        "anchor_pass": anchor_pass,
        "anchor": {
            "ret": face_m["ret"],
            "maxDD": face_m["maxDD"],
            "Calmar": face_m["Calmar"],
            "Sharpe": face_m["Sharpe"],
            "n_weeks": len(calendar),
            "T": len(calendar) - 1,
            "n_codes": len(codes),
        },
        "h1": "CH-ATR14x3 vs FACE: G1 Δret>=Δ|MDD| and G2 2023-26 not missed",
        "family_verdict": family_verdict,
        "positive_ids": positive_ids,
        "books": [b[0] for b in BOOKS],
        "g1": g1,
        "g2": g2,
        "atr_skip_name_week_pct_main": main_m["atr_skip_name_week_pct"],
        "elapsed_sec": round(time.time() - t0, 1),
    }
    (OUT / "summary.json").write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
    print(verdict, flush=True)
    print(f"done {OUT} verdict={family_verdict}", flush=True)


if __name__ == "__main__":
    main()
