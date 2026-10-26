#!/usr/bin/env python3
"""entry-kaufman-er: Kaufman ER gate on frozen B45+spike_ft max5+S20+E0+TV25 (btheta fork).

Four books: F0 (ER off) + ER10-T30/T40/T50. Research only 鈥?no crown.
Fork: 05f0f8a4 SPIKE-S20-BTHETA-GRID-LIVE1430/run.py
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

ROOT = Path(__file__).resolve().parent
OUT = ROOT / "out"
DESIGN_MD = ROOT / "DESIGN.md"
SOURCE_SHA = "05f0f8a4f778fde886f3e7b2976646ff4b7d777b"
ER_N = 10
BREADTH_B = 0.45
BOOKS: list[tuple[str, str, int | None, float | None]] = [
    ("F0", "LIVE1430-ER-off-B45-TV25", None, None),
    ("ER10-T30", "LIVE1430-ER10-T30-B45-TV25", 10, 0.30),
    ("ER10-T40", "LIVE1430-ER10-T40-B45-TV25", 10, 0.40),
    ("ER10-T50", "LIVE1430-ER10-T50-B45-TV25", 10, 0.50),
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


def kaufman_er(closes: pd.Series, d: str, n: int) -> float | None:
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
    return num / denom


def run_er_fixtures() -> None:
    """Arithmetic fixtures 鈥?must pass before backtest."""
    # monotonic up 10..20
    up = pd.Series(np.arange(10, 21, dtype=float), index=pd.date_range("2020-01-01", periods=11))
    er_up = kaufman_er(up, "2020-01-15", 10)
    if er_up is None or not (0.999999 <= er_up <= 1.000001):
        raise SystemExit(f"fixture monotonic fail er={er_up}")
    # chop
    chop_vals = [10, 11, 10, 11, 10, 11, 10, 11, 10, 11, 10]
    chop = pd.Series(chop_vals, index=pd.date_range("2020-01-01", periods=11))
    er_chop = kaufman_er(chop, "2020-01-15", 10)
    if er_chop is None or not (-1e-12 <= er_chop <= 1e-12):
        raise SystemExit(f"fixture chop fail er={er_chop}")
    flat = pd.Series([10.0] * 11, index=pd.date_range("2020-01-01", periods=11))
    if kaufman_er(flat, "2020-01-15", 10) is not None:
        raise SystemExit("fixture flat should return None")


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
    er_n: int | None = None,
    er_theta: float | None = None,
) -> tuple[list[dict[str, Any]], dict[str, list[str]], dict[str, Any], list[dict[str, Any]]]:
    cash = 1.0
    positions: dict[str, Position] = {}
    trades: list[dict[str, Any]] = []
    picks: dict[str, list[str]] = {}
    n_tight = 0
    n_feat = 0
    n_entries = 0
    n_miss_sharpe = 0
    n_er_blocked = 0
    rank_rows: list[dict[str, Any]] = []
    entry_rows: list[dict[str, Any]] = []

    def px_on(code: str, d: str) -> float | None:
        return closes_w.get(code, {}).get((alias.get(code) or {}).get(d) or d)

    def snap_at(code: str, d: str) -> dict[str, Any] | None:
        key = (alias.get(code) or {}).get(d) or d
        return snaps.get(code, {}).get(key)

    def equity_now() -> float:
        return cash + sum(p.shares * p.last_px for p in positions.values())

    def build_cands(d: str, skip: set[str]) -> list[Cand]:
        nonlocal n_er_blocked
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
            if er_theta is not None and er_n is not None:
                if code not in daily:
                    n_er_blocked += 1
                    continue
                er = kaufman_er(daily[code], d, er_n)
                if er is None or er < er_theta:
                    n_er_blocked += 1
                    continue
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
        "n_er_blocked": n_er_blocked if er_theta is not None else 0,
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
        return "\u2014"
    return f"{100 * x:.1f}%"


def window_stats(r: pd.Series, start: str, end: str | None = None) -> dict[str, float]:
    sub = r[r.index >= pd.Timestamp(start)]
    if end:
        sub = sub[sub.index <= pd.Timestamp(end)]
    return stats_full(sub) if len(sub) > 5 else {k: float("nan") for k in ("ret", "maxDD", "CAGR", "Calmar")}


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
    if not wins or not losses:
        win_size = float("nan")
    else:
        win_size = float(np.mean(wins) / abs(np.mean(losses)))
    return hit, win_size


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
        row["delta_ret"] = 0.0
        row["delta_abs_mdd"] = 0.0
        row["covers"] = False
        row["window_2020_22"] = False
        row["window_2023_26"] = False
        row["verdict"] = "BLOCKED"
        return row
    if row["id"] == "F0":
        row["delta_ret"] = 0.0
        row["delta_abs_mdd"] = 0.0
        row["covers"] = True
        row["window_2020_22"] = True
        row["window_2023_26"] = True
        row["verdict"] = "ANCHOR"
        return row
    dret = row["ret"] - f0["ret"]
    d_abs = abs(row["maxDD"]) - abs(f0["maxDD"])
    w22 = row["w2020_22"]["ret"] >= f0["w2020_22"]["ret"]
    w23 = row["w2023_26"]["ret"] >= f0["w2023_26"]["ret"]
    covers = dret >= d_abs
    positive = covers and w22 and w23
    row["delta_ret"] = dret
    row["delta_abs_mdd"] = d_abs
    row["covers"] = covers
    row["window_2020_22"] = w22
    row["window_2023_26"] = w23
    row["verdict"] = "记正" if positive else "证伪"
    return row




def main() -> None:
    run_er_fixtures()
    OUT.mkdir(parents=True, exist_ok=True)
    t0 = time.time()
    for p in (WEEK, FACE, DAY_DIR, NOON_CSV, SINA_DAILY):
        if not Path(p).exists():
            raise SystemExit(f"missing research cache path {p}")

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

    if not SNAP_CACHE.exists():
        raise SystemExit(f"missing snap cache {SNAP_CACHE}")
    cached = json.loads(SNAP_CACHE.read_text(encoding="utf-8"))
    by_rows = cached.get("by_code") or {}
    snaps = {c: snap_index(by_rows.get(c) or []) for c in codes}

    hold_by: dict[str, dict[str, list[str]]] = {}
    sim_stats: dict[str, Any] = {}
    entry_by: dict[str, list[dict[str, Any]]] = {}
    for bid, book, er_n, er_theta in BOOKS:
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
            True,
            20,
            5,
            er_n=er_n,
            er_theta=er_theta,
        )
        hold_by[book] = hold
        sim_stats[book] = st
        entry_by[book] = ent
        pd.DataFrame(trades).to_csv(OUT / f"trades_{bid}.csv", index=False)

    all_codes: set[str] = set()
    for h in hold_by.values():
        for cs in h.values():
            all_codes |= set(cs)
    px_map = {}
    for c in sorted(all_codes):
        if c in daily:
            px_map[c] = daily[c]
    px = pd.DataFrame(px_map).sort_index()
    px = px.loc[(px.index >= EVAL_START) & (px.index <= END_S)]
    R = px.pct_change()
    days = px.dropna(how="all").index
    days = days[(days >= EVAL_START) & (days <= END_S)]

    cells: list[dict[str, Any]] = []
    series: dict[str, pd.Series] = {}
    nav_by_book: dict[str, pd.Series] = {}
    for bid, book, er_n, er_theta in BOOKS:
        hd = {pd.Timestamp(d): cs for d, cs in hold_by[book].items()}
        r, L, avg_to = run_live_tv(hd, days, px, R)
        series[book] = r
        nav_by_book[book] = (1 + r).cumprod()
        st = stats_full(r)
        w22 = window_stats(r, "2020-01-01", "2022-12-31")
        w23 = window_stats(r, "2023-01-01")
        hit, win_size = entry_quality(entry_by[book], calendar, closes_w_sig)
        sim = sim_stats[book]
        cells.append(
            {
                "id": bid,
                "book": book,
                "N": er_n,
                "theta": er_theta,
                "ret": st["ret"],
                "maxDD": st["maxDD"],
                "CAGR": st["CAGR"],
                "Calmar": st["Calmar"],
                "avgL": float(L[L > 0].mean()) if (L > 0).any() else 0.0,
                "avg_turnover_1way": avg_to,
                "n_cash_weeks": sim["n_cash_weeks"],
                "n_entries": sim["n_entries"],
                "n_er_blocked": sim["n_er_blocked"],
                "hit_rate": hit,
                "win_size": win_size,
                "w2020_22": w22,
                "w2023_26": w23,
                "T": max(0, len(calendar) - 1),
            }
        )
        print(f"  {bid}: ret={pct(st['ret'])} dd={pct(st['maxDD'])} Calmar={st['Calmar']:.2f}", flush=True)

    f0 = next(c for c in cells if c["id"] == "F0")
    anchor_pass = check_anchor(f0, len(calendar), len(codes), actual_end)
    blocked = not anchor_pass
    for c in cells:
        ruler_cell(f0, c, blocked)

    positive_ids = [c["id"] for c in cells if c["verdict"] == "记正"]
    if blocked:
        family_verdict = "BLOCKED"
        h1_line = "锚点未过 — family BLOCKED"
    elif positive_ids:
        family_verdict = "H1_REJECT"
        h1_line = f"ER10 记正: {', '.join(positive_ids)}"
    else:
        family_verdict = "H1_HOLD"
        h1_line = "ER10-T30/T40/T50 all 证伪"

    # table.csv
    csv_rows = []
    for c in cells:
        csv_rows.append(
            {
                "id": c["id"],
                "book": c["book"],
                "N": "off" if c["N"] is None else c["N"],
                "theta": "off" if c["theta"] is None else c["theta"],
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
                "n_er_blocked": c["n_er_blocked"],
                "hit_rate": c["hit_rate"],
                "win_size": c["win_size"],
                "delta_ret": c["delta_ret"],
                "delta_abs_mdd": c["delta_abs_mdd"],
                "covers": str(c["covers"]).lower(),
                "window_2020_22": str(c["window_2020_22"]).lower(),
                "window_2023_26": str(c["window_2023_26"]).lower(),
                "verdict": c["verdict"],
            }
        )
    pd.DataFrame(csv_rows).to_csv(OUT / "table.csv", index=False)

    eq_long = []
    for bid, book, _, _ in BOOKS:
        nav = nav_by_book[book]
        for dt, nv in nav.items():
            eq_long.append({"date": dt.strftime("%Y-%m-%d"), "book": book, "nav": float(nv)})
    pd.DataFrame(eq_long).to_csv(OUT / "equity.csv", index=False)

    fig, ax = plt.subplots(figsize=(11, 5.5), dpi=120)
    f0_book = BOOKS[0][1]
    ax.plot(nav_by_book[f0_book].index, nav_by_book[f0_book].values, color="black", lw=2.2, label="F0")
    for bid, book, _, _ in BOOKS[1:]:
        ax.plot(nav_by_book[book].index, nav_by_book[book].values, color="gray", lw=1.0, alpha=0.85, label=bid)
    ax.set_yscale("log")
    ax.set_title("entry-kaufman-er (Fri 14:30 / close)")
    ax.set_ylabel("NAV (log)")
    ax.grid(True, alpha=0.3)
    ax.legend(fontsize=8)
    fig.tight_layout()
    fig.savefig(OUT / "equity_curve.png")
    plt.close(fig)

    summary_cells = []
    for c in cells:
        summary_cells.append(
            {
                "id": c["id"],
                "book": c["book"],
                "N": c["N"],
                "theta": c["theta"],
                "ret": c["ret"],
                "maxDD": c["maxDD"],
                "CAGR": c["CAGR"],
                "Calmar": c["Calmar"],
                "avgL": c["avgL"],
                "avg_turnover_1way": c["avg_turnover_1way"],
                "n_cash_weeks": c["n_cash_weeks"],
                "n_entries": c["n_entries"],
                "n_er_blocked": c["n_er_blocked"],
                "hit_rate": c["hit_rate"],
                "win_size": c["win_size"],
                "w2020_22": c["w2020_22"],
                "w2023_26": c["w2023_26"],
                "delta_ret": c["delta_ret"],
                "delta_abs_mdd": c["delta_abs_mdd"],
                "covers": c["covers"],
                "window_2020_22": c["window_2020_22"],
                "window_2023_26": c["window_2023_26"],
                "verdict": c["verdict"],
            }
        )

    summary = {
        "batch": "entry-kaufman-er",
        "champion_swap": False,
        "crown": "NO",
        "source_sha": SOURCE_SHA,
        "sample": [EVAL_START, actual_end],
        "anchor_pass": anchor_pass,
        "anchor": {
            "ret": ANCHOR["ret"],
            "maxDD": ANCHOR["maxDD"],
            "Calmar": ANCHOR["Calmar"],
            "n_weeks": len(calendar),
            "T": f0["T"],
            "n_codes": len(codes),
        },
        "face_id": "F0",
        "er_n": ER_N,
        "h1": h1_line,
        "family_verdict": family_verdict,
        "positive_ids": positive_ids,
        "cells": summary_cells,
        "elapsed_sec": round(time.time() - t0, 1),
    }
    (OUT / "summary.json").write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")

    design_text = DESIGN_MD.read_text(encoding="utf-8") if DESIGN_MD.exists() else ""
    qline = design_text.splitlines()[2] if len(design_text.splitlines()) > 2 else ""
    h1_block = ""
    if "## H1" in design_text:
        part = design_text.split("## H1", 1)[1].split("## ", 1)[0]
        if "```" in part:
            inner = part.split("```", 2)[1]
            h1_block = "```\n" + inner.strip() + "\n```"

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
        f"**anchor_pass={anchor_pass}** · **family_verdict={family_verdict}** · 不换冠。",
        "",
        "## 主表",
        "",
        "| id | ret | maxDD | Calmar | w2020-22 ret | w2023-26 ret | n_entries | n_er_blocked | hit_rate | win_size | verdict |",
        "|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---|",
    ]
    for c in cells:
        report_lines.append(
            f"| {c['id']} | {pct(c['ret'])} | {pct(c['maxDD'])} | {c['Calmar']:.2f} | "
            f"{pct(c['w2020_22']['ret'])} | {pct(c['w2023_26']['ret'])} | {c['n_entries']} | "
            f"{c['n_er_blocked']} | {c['hit_rate']:.2%} | {c['win_size']:.2f} | {c['verdict']} |"
        )
    report_lines.extend(["", "## Δ 表", "", "| id | Δret | Δ|MDD| | 盖住 | 2020-22 | 2023-26 |", "|---|---:|---:|:---:|:---:|:---:|"])
    for c in cells:
        if c["id"] == "F0":
            continue
        report_lines.append(
            f"| {c['id']} | {100*c['delta_ret']:+.1f}pp | {100*c['delta_abs_mdd']:+.1f}pp | "
            f"{c['covers']} | {c['window_2020_22']} | {c['window_2023_26']} |"
        )
    report_lines.extend(["", "## 证伪段", "", f"- {h1_line}", f"- positive_ids: {positive_ids or '[]'}", ""])
    if not anchor_pass:
        report_lines.append(
            f"- F0 实际 ret={pct(f0['ret'])} maxDD={pct(f0['maxDD'])} Calmar={f0['Calmar']:.2f}；"
            "更接近 btheta 锚 131.6%/0.70，非 TV 158.3%/0.94、非压缩突破 68.1%/0.31。"
        )
    report_lines.append("")
    report_lines.append("## 红线")
    report_lines.append("")
    report_lines.append("研究池 only；未改 LIVE/实盘；champion_swap=false。")
    (OUT / "REPORT.md").write_text("\n".join(report_lines), encoding="utf-8")
    print("done", OUT, family_verdict, flush=True)


if __name__ == "__main__":
    main()

