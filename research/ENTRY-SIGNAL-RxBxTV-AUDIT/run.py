#!/usr/bin/env python3
"""ENTRY-SIGNAL-RxBxTV: R x B x TV cross audit on btheta extended LIVE1430 engine.

Fork pin: 05f0f8a4 (SPIKE-S20-BTHETA-GRID-LIVE1430). Eight books from cells.json.
Research only; no crown swap.
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

from ruler import covers, verdict, window_ok  # noqa: E402

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

HERE = Path(__file__).resolve().parent
OUT = HERE / "out"
SOURCE_SHA = "05f0f8a4f778fde886f3e7b2976646ff4b7d777b"
CACHE = KIT / "data" / "research_cache"
UNI_CSV = KIT / "data" / "universe_replace_only_436.csv"
WEEK = CACHE / "week"
FACE = CACHE / "holdings_ro2_extended.csv"
DAY_DIR = CACHE / "day"
TEMA_PX = Path("/nonexistent_tema_px")
NOON_CSV = CACHE / "fri_1430_through_20261023.csv"
SINA_DAILY = CACHE / "sina_daily"
CLASSIFY_FROM = "2019-07-01"
SNAP_CACHE = KIT / "data" / "cache_1430_snaps.json"
EVAL_START = "2020-01-03"
END_S = "2026-10-23"
COST_SIDE = 0.001
ANCHOR_RET = 1.316
ANCHOR_MDD = -0.188
ANCHOR_CAL = 0.70
ANCHOR_N_WEEKS = 349
ANCHOR_N_CODES = 324
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


def ret_nd_on(closes: pd.Series, d: str, n: int) -> float | None:
    """Total return over n trading days ending strictly BEFORE signal date d."""
    ts = pd.Timestamp(d)
    sub = closes.loc[: ts - pd.Timedelta(days=1)]
    if len(sub) < n + 1:
        return None
    if (ts - sub.index[-1]).days > 5:
        return None
    c0 = float(sub.iloc[-(n + 1)])
    c1 = float(sub.iloc[-1])
    if c0 <= 0 or not np.isfinite(c0) or not np.isfinite(c1):
        return None
    return c1 / c0 - 1.0


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
    entry_mom_lb: int | None = None,
) -> tuple[list[dict[str, Any]], dict[str, list[str]], dict[str, Any]]:
    cash = 1.0
    positions: dict[str, Position] = {}
    trades: list[dict[str, Any]] = []
    picks: dict[str, list[str]] = {}
    n_tight = 0
    n_feat = 0
    n_entries = 0
    n_miss_sharpe = 0
    n_mom_blocked = 0
    rank_rows: list[dict[str, Any]] = []

    def px_on(code: str, d: str) -> float | None:
        return closes_w.get(code, {}).get((alias.get(code) or {}).get(d) or d)

    def snap_at(code: str, d: str) -> dict[str, Any] | None:
        key = (alias.get(code) or {}).get(d) or d
        return snaps.get(code, {}).get(key)

    def equity_now() -> float:
        return cash + sum(p.shares * p.last_px for p in positions.values())

    def build_cands(d: str, skip: set[str]) -> list[Cand]:
        nonlocal n_mom_blocked
        out: list[Cand] = []
        for code in snaps:
            if code in skip:
                continue
            sn = snap_at(code, d)
            if not is_spike(sn):
                continue
            if entry_mom_lb is not None:
                if code not in daily:
                    n_mom_blocked += 1
                    continue
                rmom = ret_nd_on(daily[code], d, entry_mom_lb)
                if rmom is None or rmom <= 0:
                    n_mom_blocked += 1
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
        "n_spike_blocked_by_mom": n_mom_blocked if entry_mom_lb is not None else 0,
    }
    if rank_rows:
        pd.DataFrame(rank_rows).to_csv(OUT / f"entries_{variant}.csv", index=False)
    return trades, hold, stats


def run_live_tv(
    hold: dict[pd.Timestamp, list[str]],
    days: pd.DatetimeIndex,
    px: pd.DataFrame,
    R: pd.DataFrame,
    sigma_star: float,
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
                L = float(min(LCAP, sigma_star / sh)) if sh and sh > 0 else 1.0
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
    avg_to = to_sum / to_n if to_n else 0.0
    return r, Ls, avg_to / 2.0


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
        return "n/a"
    return f"{100 * x:.1f}%"


def slice_windows(r: pd.Series) -> tuple[dict[str, float], dict[str, float]]:
    r2022 = r[(r.index >= "2020-01-01") & (r.index <= "2022-12-31")]
    r2023 = r[r.index >= "2023-01-01"]
    w0 = stats_full(r2022) if len(r2022) > 5 else {k: float("nan") for k in ("ret", "maxDD", "Calmar")}
    w1 = stats_full(r2023) if len(r2023) > 5 else {k: float("nan") for k in ("ret", "maxDD", "Calmar")}
    return w0, w1


def anchor_pass(f0: dict[str, float], n_weeks: int, n_codes: int, end: str) -> bool:
    if end != END_S:
        return False
    if n_weeks != ANCHOR_N_WEEKS or n_codes != ANCHOR_N_CODES:
        return False
    return (
        abs(f0["ret"] - ANCHOR_RET) <= 0.005
        and abs(f0["maxDD"] - ANCHOR_MDD) <= 0.002
        and abs(f0["Calmar"] - ANCHOR_CAL) <= 0.02
    )


def load_cells() -> tuple[dict[str, Any], list[dict[str, Any]]]:
    doc = json.loads((HERE / "cells.json").read_text(encoding="utf-8"))
    cells = doc["cells"]
    return doc, cells


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    t0 = time.time()
    doc, cells = load_cells()
    allowed_books = {c["book"] for c in cells}
    cell_by_book = {c["book"]: c for c in cells}

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
    n_codes = len(codes)

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
    n_weeks = len(calendar)
    print(f"calendar {calendar[0]} -> {actual_end} n={n_weeks}", flush=True)

    breadth_b: dict[str, float] = {}
    for _, row in face.iterrows():
        d = str(row["date"])[:10]
        bv = row.get("b")
        if bv is not None and not (isinstance(bv, float) and math.isnan(bv)):
            breadth_b[d] = float(bv)

    thetas_needed = sorted({float(c["B"]) for c in cells})

    def risk_map_for_theta(theta: float) -> dict[str, bool]:
        rmap: dict[str, bool] = {}
        for d in calendar:
            b = breadth_b.get(d)
            rmap[d] = bool(b is not None and b >= theta)
        rmap[calendar[-1]] = False
        return rmap

    risk_by_theta = {th: risk_map_for_theta(th) for th in thetas_needed}

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

    print("load sina + daily qfq for 14:30 map...", flush=True)
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
    for cell in cells:
        book = cell["book"]
        if book not in allowed_books:
            raise SystemExit(f"unknown book {book}")
        theta = float(cell["B"])
        mom_lb = int(cell["R"]) if cell["R"] is not None else None
        print(f"simulate {book} B={theta} R={mom_lb} TV={cell['TV']}...", flush=True)
        trades, hold, st = simulate(
            calendar,
            snaps,
            closes_w_sig,
            alias,
            aum,
            daily,
            risk_by_theta[theta],
            sharpe_key,
            book,
            True,
            20,
            5,
            mom_lb,
        )
        hold_by[book] = hold
        sim_stats[book] = st
        pd.DataFrame(trades).to_csv(OUT / f"trades_{book}.csv", index=False)
        rows_h = []
        for d in calendar[:-1]:
            codes_h = hold.get(d) or []
            rows_h.append({"date": d, "n_held": len(codes_h), "codes": ",".join(codes_h)})
        pd.DataFrame(rows_h).to_csv(OUT / f"holdings_{book}.csv", index=False)

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
    Rmat = px.pct_change()
    if "510300" in px.columns:
        days = px["510300"].dropna().index
    else:
        days = px.dropna(how="all").index
    days = days[(days >= EVAL_START) & (days <= END_S)]

    series: dict[str, pd.Series] = {}
    metrics: dict[str, dict[str, Any]] = {}
    for cell in cells:
        book = cell["book"]
        tv = float(cell["TV"])
        hd = {pd.Timestamp(d): cs for d, cs in hold_by[book].items()}
        r, Ls, avg_to = run_live_tv(hd, days, px, Rmat, tv)
        series[book] = r
        st_full = stats_full(r)
        w2020, w2023 = slice_windows(r)
        metrics[book] = {
            **st_full,
            "avgL": float(Ls[Ls > 0].mean()) if (Ls > 0).any() else 0.0,
            "avg_turnover_1way": avg_to,
            "w2020_22": w2020,
            "w2023_26": w2023,
            "sim": sim_stats[book],
        }

    f0_book = cells[0]["book"]
    face_m = metrics[f0_book]
    ap = anchor_pass(face_m, n_weeks, n_codes, actual_end)

    face_for_ruler = {
        "ret": face_m["ret"],
        "maxDD": face_m["maxDD"],
        "w2020_22": {"ret": face_m["w2020_22"]["ret"]},
        "w2023_26": {"ret": face_m["w2023_26"]["ret"]},
    }

    cell_results: list[dict[str, Any]] = []
    positive_ids: list[str] = []
    table_rows: list[dict[str, Any]] = []

    for cell in cells:
        cid = cell["id"]
        book = cell["book"]
        m = metrics[book]
        sim = m["sim"]
        if cid == "F0":
            vlabel = "ANCHOR" if ap else "BLOCKED"
            cov = True
            w0ok = w1ok = True
            d_ret = d_mdd = 0.0
        elif not ap:
            vlabel = "BLOCKED"
            cov = w0ok = w1ok = False
            d_ret = d_mdd = float("nan")
        else:
            ruler_cell = {
                "ret": m["ret"],
                "maxDD": m["maxDD"],
                "w2020_22": {"ret": m["w2020_22"]["ret"]},
                "w2023_26": {"ret": m["w2023_26"]["ret"]},
            }
            vlabel = verdict(ruler_cell, face_for_ruler)
            cov = covers(m["ret"], m["maxDD"], face_m["ret"], face_m["maxDD"])
            w0ok = window_ok(m["w2020_22"]["ret"], face_m["w2020_22"]["ret"])
            w1ok = window_ok(m["w2023_26"]["ret"], face_m["w2023_26"]["ret"])
            d_ret = m["ret"] - face_m["ret"]
            d_mdd = abs(m["maxDD"]) - abs(face_m["maxDD"])
            if vlabel == "记正":
                positive_ids.append(cid)

        Rcsv = "off" if cell["R"] is None else cell["R"]
        row = {
            "id": cid,
            "book": book,
            "R": Rcsv,
            "B": cell["B"],
            "TV": cell["TV"],
            "ret": m["ret"],
            "maxDD": m["maxDD"],
            "CAGR": m["CAGR"],
            "Calmar": m["Calmar"],
            "w2020_22_ret": m["w2020_22"]["ret"],
            "w2020_22_maxDD": m["w2020_22"]["maxDD"],
            "w2020_22_Calmar": m["w2020_22"]["Calmar"],
            "w2023_26_ret": m["w2023_26"]["ret"],
            "w2023_26_maxDD": m["w2023_26"]["maxDD"],
            "w2023_26_Calmar": m["w2023_26"]["Calmar"],
            "avgL": m["avgL"],
            "avg_turnover_1way": m["avg_turnover_1way"],
            "n_cash_weeks": sim["n_cash_weeks"],
            "n_entries": sim["n_entries"],
            "n_spike_blocked_by_mom": sim["n_spike_blocked_by_mom"],
            "delta_ret": d_ret,
            "delta_abs_mdd": d_mdd,
            "covers": cov,
            "window_2020_22": w0ok,
            "window_2023_26": w1ok,
            "verdict": vlabel,
        }
        table_rows.append(row)
        cell_results.append(
            {
                "id": cid,
                "book": book,
                "R": cell["R"],
                "B": cell["B"],
                "TV": cell["TV"],
                "ret": m["ret"],
                "maxDD": m["maxDD"],
                "CAGR": m["CAGR"],
                "Calmar": m["Calmar"],
                "avgL": m["avgL"],
                "avg_turnover_1way": m["avg_turnover_1way"],
                "n_cash_weeks": sim["n_cash_weeks"],
                "n_entries": sim["n_entries"],
                "n_spike_blocked_by_mom": sim["n_spike_blocked_by_mom"],
                "w2020_22": m["w2020_22"],
                "w2023_26": m["w2023_26"],
                "delta_ret": d_ret,
                "delta_abs_mdd": d_mdd,
                "covers": cov,
                "window_2020_22": w0ok,
                "window_2023_26": w1ok,
                "verdict": vlabel,
            }
        )

    if not ap:
        family_verdict = "BLOCKED"
        h1 = "anchor blocked"
        one_line = (
            f"锚点未过（F0 ret={pct(face_m['ret'])} maxDD={pct(face_m['maxDD'])} "
            f"Calmar={face_m['Calmar']:.2f}；目标 131.6%/-18.8%/0.70），家族结论 BLOCKED，不换冠。"
        )
    elif positive_ids:
        family_verdict = "H1_REJECT"
        h1 = f"记正: {','.join(positive_ids)}"
        one_line = f"H1 证伪：{','.join(positive_ids)} 记正；仍不换冠。"
    else:
        family_verdict = "H1_HOLD"
        h1 = "X1-X7 all 证伪"
        one_line = "H1 成立：X1–X7 在严格尺子下全部证伪；维持面层、不换冠。"

    cols = [
        "id",
        "book",
        "R",
        "B",
        "TV",
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
        "n_spike_blocked_by_mom",
        "delta_ret",
        "delta_abs_mdd",
        "covers",
        "window_2020_22",
        "window_2023_26",
        "verdict",
    ]
    pd.DataFrame(table_rows)[cols].to_csv(OUT / "table.csv", index=False)

    eq_rows: list[dict[str, Any]] = []
    for cell in cells:
        book = cell["book"]
        nav = (1 + series[book]).cumprod()
        for d, v in nav.items():
            eq_rows.append({"date": d.strftime("%Y-%m-%d"), "book": book, "nav": float(v)})
    pd.DataFrame(eq_rows).to_csv(OUT / "equity.csv", index=False)

    f0_name = cells[0]["book"]
    fig, ax = plt.subplots(figsize=(11, 5.5), dpi=120)
    for cell in cells:
        book = cell["book"]
        nav = (1 + series[book]).cumprod()
        lw = 2.2 if book == f0_name else 1.0
        color = "black" if book == f0_name else None
        ax.plot(nav.index, nav.values, label=book, lw=lw, color=color)
    ax.set_yscale("log")
    ax.set_title("ENTRY-SIGNAL-RxBxTV (F0 black)")
    ax.set_ylabel("nav (log)")
    ax.grid(True, alpha=0.3)
    ax.legend(fontsize=7)
    fig.tight_layout()
    fig.savefig(OUT / "equity_curve.png")
    plt.close(fig)

    summary = {
        "batch": "ENTRY-SIGNAL-RxBxTV",
        "champion_swap": False,
        "crown": "NO",
        "source_sha": SOURCE_SHA,
        "sample": [EVAL_START, actual_end],
        "anchor_pass": ap,
        "anchor": {
            "ret": face_m["ret"],
            "maxDD": face_m["maxDD"],
            "Calmar": face_m["Calmar"],
            "n_weeks": n_weeks,
            "n_codes": n_codes,
        },
        "face_id": "F0",
        "h1": h1,
        "family_verdict": family_verdict,
        "positive_ids": positive_ids,
        "cells": cell_results,
        "elapsed_sec": round(time.time() - t0, 1),
    }
    (OUT / "summary.json").write_text(
        json.dumps(summary, ensure_ascii=False, indent=2, default=str), encoding="utf-8"
    )

    readme_line = (HERE / "README.md").read_text(encoding="utf-8").splitlines()[2]
    criterion = (HERE / "CRITERION.md").read_text(encoding="utf-8")
    template_start = criterion.index("```")
    template_end = criterion.index("```", template_start + 3)
    template = criterion[template_start + 3 : template_end].strip()

    anchor_block = (
        f"| ret | {pct(face_m['ret'])} | {pct(ANCHOR_RET)} | {'PASS' if ap else 'FAIL'} |\n"
        f"| maxDD | {pct(face_m['maxDD'])} | {pct(ANCHOR_MDD)} | |\n"
        f"| Calmar | {face_m['Calmar']:.2f} | {ANCHOR_CAL:.2f} | |\n"
        f"| weeks | {n_weeks} | {ANCHOR_N_WEEKS} | |\n"
        f"| codes | {n_codes} | {ANCHOR_N_CODES} | |\n"
    )

    def md_row(r: dict[str, Any]) -> str:
        return (
            f"| {r['id']} | {r['book']} | {r['R']} | {r['B']} | {r['TV']} | "
            f"{pct(r['ret'])} | {pct(r['maxDD'])} | {r['Calmar']:.2f} | "
            f"{pct(r['w2020_22_ret'])} | {pct(r['w2023_26_ret'])} | {r['verdict']} |"
        )

    main_table = "\n".join(md_row(r) for r in table_rows)
    delta_lines = []
    for r in table_rows[1:]:
        delta_lines.append(
            f"- {r['id']}: Δret={100*r['delta_ret']:+.1f}pp Δ|MDD|={100*r['delta_abs_mdd']:+.1f}pp "
            f"covers={r['covers']} 2020-22={r['window_2020_22']} 2023-26={r['window_2023_26']} → {r['verdict']}"
        )

    falsify_sec = (
        f"**家族结论**：{family_verdict}。{h1}。`champion_swap=false`。\n\n"
        + ("锚点门未过，各格 BLOCKED。\n" if not ap else "")
    )

    report = f"""{readme_line}

{one_line}

## Criterion（TEMPLATE）

```
{template}
```

## 锚点门（F0 vs btheta LIVE1430-B45-S20-max5）

| 量 | 本次 F0 | 锚 | 判定 |
|---|---:|---:|---|
{anchor_block}

## 主表

| id | book | R | B | TV | ret | maxDD | Calmar | 2020-22 ret | 2023-26 ret | verdict |
|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---|
{main_table}

## Δ 相对 F0

{chr(10).join(delta_lines)}

## 证伪段

{falsify_sec}

红线：未改 strategy_exec / LIVE_OPS / champion_mast / 固收+ / 红利袖。source_sha={SOURCE_SHA}。
耗时 {summary['elapsed_sec']}s。
"""
    (OUT / "REPORT.md").write_text(report, encoding="utf-8")
    print("done", OUT, flush=True)
    print(one_line, flush=True)


if __name__ == "__main__":
    main()
