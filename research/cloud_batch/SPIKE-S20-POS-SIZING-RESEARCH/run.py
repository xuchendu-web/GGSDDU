#!/usr/bin/env python3
"""SPIKE-S20-POS-SIZING-RESEARCH: position-weight variants; S20 entry ranks frozen.

Books (B45 + spike_ft max5 + SHARPE20 + E0 + TV25 + 0.2%RT + L≤1; only sizing changes):
  RESEARCH-S20-EQ5      — equal weight among held (B45+S20 baseline)
  RESEARCH-S20-INV20W   — inverse 20-week realized vol (weekly bars)
  RESEARCH-S20-CAP30    — equal weight with 30% single-name cap (+ cash if bind)

Research pool; Fri≥14:30/close convention; no strategy_exec / LIVE_OPS.
Extended window ≥2026-10-23 via CLOUD-BATCH research_cache.
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

KIT = Path(__file__).resolve().parents[1] / "CLOUD-BATCH-2026-10-26"
SCRIPTS = KIT / "scripts"
sys.path.insert(0, str(SCRIPTS))

from backtest import KEEP, LIVE_PHASE, MIN_BARS, Position, nearest_date, snap_index  # noqa: E402
from build_scan import Bar, classify  # noqa: E402

OUT = Path(__file__).resolve().parent
CACHE = KIT / "data" / "research_cache"
UNI_CSV = KIT / "data" / "universe_replace_only_436.csv"
WEEK = CACHE / "week"
FACE = CACHE / "holdings_ro2_extended.csv"
DAY_DIR = CACHE / "day"
TEMA_PX = Path("/nonexistent_tema_px")  # optional; day cache covers extended window
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


def aum_key(c: Cand, pool: list[Cand]) -> tuple:
    return (-c.aum, c.code)


def sharpe_key(c: Cand, pool: list[Cand]) -> tuple:
    miss = 0 if c.sharpe is not None else 1
    return (miss, -(c.sharpe if c.sharpe is not None else 0.0), c.code)


SizingMode = str  # "eq" | "inv20w" | "cap30"
MAX_POS = 5
CAP_SINGLE = 0.30


def vol_20w_weekly(closes: dict[str, float], end_week: str, n: int = 20) -> float | None:
    """Std of last n weekly returns with week ending on/before end_week."""
    dates = sorted(d for d in closes if d <= end_week)
    if len(dates) < n + 1:
        return None
    window = dates[-(n + 1) :]
    prices = [float(closes[dt]) for dt in window]
    rets = [prices[i] / prices[i - 1] - 1.0 for i in range(1, len(prices))]
    if len(rets) < n:
        return None
    rets = rets[-n:]
    sigma = float(np.std(rets, ddof=1)) if len(rets) > 1 else 0.0
    if sigma <= 0 or not np.isfinite(sigma):
        return None
    return sigma


def equal_weights(codes: list[str]) -> dict[str, float]:
    if not codes:
        return {}
    w = 1.0 / len(codes)
    return {c: w for c in codes}


def inverse_vol_weights(
    codes: list[str], d: str, week_closes: dict[str, dict[str, float]]
) -> dict[str, float]:
    inv: dict[str, float] = {}
    for c in codes:
        sigma = vol_20w_weekly(week_closes.get(c) or {}, d, 20)
        if sigma is None or sigma <= 0:
            continue
        inv[c] = 1.0 / sigma
    if not inv:
        return equal_weights(codes)
    s = sum(inv.values())
    return {c: v / s for c, v in inv.items()}


def cap_single_weights(raw: dict[str, float], cap: float = CAP_SINGLE) -> dict[str, float]:
    """Cap each name; excess not redistributed — remainder is implicit cash."""
    if not raw:
        return {}
    w = dict(raw)
    for _ in range(32):
        over = [k for k, v in w.items() if v > cap + 1e-12]
        if not over:
            break
        for k in over:
            w[k] = cap
    return w


def sizing_weights(
    mode: SizingMode,
    codes: list[str],
    d: str,
    week_closes: dict[str, dict[str, float]],
) -> dict[str, float]:
    if not codes:
        return {}
    if mode == "eq":
        return equal_weights(codes)
    if mode == "inv20w":
        return inverse_vol_weights(codes, d, week_closes)
    if mode == "cap30":
        return cap_single_weights(equal_weights(codes))
    raise ValueError(f"unknown sizing {mode}")


def apply_weights_to_positions(
    positions: dict[str, Position], weights: dict[str, float], eq: float
) -> float:
    """Set shares from portfolio weights; return cash (uninvested fraction × eq)."""
    invested = sum(weights.values())
    cash = eq * max(0.0, 1.0 - invested)
    for code, p in positions.items():
        wi = weights.get(code, 0.0)
        if p.last_px > 0 and wi > 0:
            p.shares = (eq * wi) / p.last_px
        else:
            p.shares = 0.0
    return cash


def load_daily_closes(codes: list[str]) -> dict[str, pd.Series]:
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
                    s = s.combine_first(px).sort_index()
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
    """Annualized Sharpe of last n daily returns ending strictly BEFORE d."""
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
    week_closes: dict[str, dict[str, float]],
    alias: dict[str, dict[str, str]],
    aum: dict[str, float],
    daily: dict[str, pd.Series],
    risk_on_by_fri: dict[str, bool],
    rank_fn: RankFn,
    variant: str,
    require_sharpe: bool,
    sharpe_n: int | None,
    max_pos: int,
    sizing_mode: SizingMode,
) -> tuple[list[dict[str, Any]], dict[str, list[str]], dict[str, dict[str, float]], dict[str, Any]]:
    cash = 1.0
    positions: dict[str, Position] = {}
    trades: list[dict[str, Any]] = []
    picks: dict[str, list[str]] = {}
    weights_by_day: dict[str, dict[str, float]] = {}
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
            n_after = len(positions) + len(take)
            if n_after > max_pos:
                raise SystemExit(f"overflow {variant} {d} n={n_after}")
            for c in take:
                positions[c.code] = Position(
                    code=c.code,
                    kind="spike_ft",
                    entry_date=d,
                    entry_px=c.px,
                    entry_falsify=c.fz,
                    shares=0.0,
                    last_px=c.px,
                    weeks=0,
                )

        held = sorted(positions.keys())
        if held:
            eq = equity_now()
            wk = sizing_weights(sizing_mode, held, d, week_closes)
            weights_by_day[d] = wk
            cash = apply_weights_to_positions(positions, wk, eq)
            for c in take:
                p = positions.get(c.code)
                if p and p.shares > 0:
                    p.shares *= 1.0 - COST_SIDE
        else:
            weights_by_day[d] = {}
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

    stats = {
        "n_fridays_queue_gt_seats": n_tight,
        "n_fridays_with_cands": n_feat,
        "n_entries": n_entries,
        "n_entries_missing_sharpe": n_miss_sharpe,
        "n_trades": len(trades),
        "max_pos": max_pos,
    }
    if rank_rows:
        pd.DataFrame(rank_rows).to_csv(OUT / f"entries_{variant}.csv", index=False)
    return trades, hold, weights_by_day, stats


def run_live_tv(
    hold_w: dict[pd.Timestamp, dict[str, float]],
    days: pd.DatetimeIndex,
    px: pd.DataFrame,
    R: pd.DataFrame,
) -> tuple[pd.Series, pd.Series, float]:
    """Returns daily net ret, L series, and average one-way turnover per rebalance."""
    reb = sorted(hold_w)
    rp = pd.Series(0.0, index=days)
    Ls = pd.Series(0.0, index=days)
    prev: dict[str, float] = {}
    cst = pd.Series(0.0, index=days)
    R2 = R.reindex(days)
    to_sum = 0.0
    to_n = 0

    for i, d in enumerate(reb):
        w0 = hold_w[d]
        cs = [c for c in w0 if c in px.columns and w0[c] > 0]
        nxt = reb[i + 1] if i + 1 < len(reb) else days[-1] + pd.Timedelta(days=1)
        seg = days[(days > d) & (days <= nxt)]
        if not cs:
            w: dict[str, float] = {}
            L = 0.0
        else:
            w = {c: float(w0[c]) for c in cs}
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
    avg_to = to_sum / to_n if to_n else 0.0  # two-way weight change; /2 ≈ one-way
    return r, Ls, avg_to / 2.0


def stats_full(s: pd.Series) -> dict[str, float]:
    q = (1 + s).cumprod()
    ret = float(q.iloc[-1] - 1)
    dd = float((q / q.cummax().clip(lower=1e-12) - 1).min())
    n = (s.index[-1] - s.index[0]).days
    cagr = (1 + ret) ** (365.25 / n) - 1 if n > 0 and (1 + ret) > 0 else float("nan")
    cal = cagr / abs(dd) if dd < 0 else float("nan")
    return {"ret": ret, "maxDD": dd, "CAGR": cagr, "Calmar": cal}


def occupied_week_stats(
    r: pd.Series, hold: dict[pd.Timestamp, list[str]], days: pd.DatetimeIndex
) -> dict[str, Any]:
    """Week PnL over Fri→next-Fri segments with non-empty holdings; winrate & payoff."""
    reb = sorted(hold)
    week_rets: list[float] = []
    for i, d in enumerate(reb):
        if not hold[d]:
            continue
        nxt = reb[i + 1] if i + 1 < len(reb) else days[-1] + pd.Timedelta(days=1)
        seg = r[(r.index > d) & (r.index <= nxt)]
        if len(seg) == 0:
            continue
        week_rets.append(float((1 + seg).prod() - 1))
    n = len(week_rets)
    if n == 0:
        return {
            "n_occ_weeks": 0,
            "winrate": float("nan"),
            "avg_win": float("nan"),
            "avg_loss": float("nan"),
            "payoff": float("nan"),
            "avg_week_ret": float("nan"),
        }
    wins = [x for x in week_rets if x > 0]
    losses = [x for x in week_rets if x < 0]
    zeros = n - len(wins) - len(losses)
    avg_win = float(np.mean(wins)) if wins else float("nan")
    avg_loss = float(np.mean(losses)) if losses else float("nan")
    if losses and wins and avg_loss != 0:
        payoff = avg_win / abs(avg_loss)
    else:
        payoff = float("nan")
    return {
        "n_occ_weeks": n,
        "n_wins": len(wins),
        "n_losses": len(losses),
        "n_flat": zeros,
        "winrate": len(wins) / n,
        "avg_win": avg_win,
        "avg_loss": avg_loss,
        "payoff": payoff,
        "avg_week_ret": float(np.mean(week_rets)),
    }


def yearly_table(r: pd.Series) -> pd.DataFrame:
    rows = []
    years = sorted(set(r.index.year))
    for y in years:
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


def num(x: float | None, nd: int = 2) -> str:
    if x is None or (isinstance(x, float) and (math.isnan(x) or math.isinf(x))):
        return "—"
    return f"{x:.{nd}f}"


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    t0 = time.time()
    print("load universe + 14:30 + week…", flush=True)
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
    noon_ok = noon[(noon["status"] == "ok") & noon["price_1130"].notna()].copy()

    face = pd.read_csv(FACE)
    face["date"] = face["date"].astype(str).str[:10]
    face = face[(face["date"] >= EVAL_START) & (face["date"] <= END_S)].copy()
    calendar = sorted(face["date"].unique().tolist())
    if not calendar:
        raise SystemExit("empty calendar")
    print(f"calendar {calendar[0]} → {calendar[-1]} n={len(calendar)}", flush=True)

    risk_on_by_fri: dict[str, bool] = {}
    for _, row in face.iterrows():
        d = str(row["date"])[:10]
        v = row["risk_on"]
        if isinstance(v, (bool, np.bool_)):
            risk_on_by_fri[d] = bool(v)
        else:
            risk_on_by_fri[d] = str(v).lower() in {"1", "true", "True"}
    for d in calendar:
        risk_on_by_fri.setdefault(d, False)
    risk_on_by_fri[calendar[-1]] = False
    print(
        f"face risk_on={sum(1 for d in calendar if risk_on_by_fri.get(d))} / {len(calendar)}",
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

    print("load daily qfq + sina (bfq-like) for 14:30 map…", flush=True)
    daily = load_daily_closes(codes)
    print(f"daily qfq series: {len(daily)}/{len(codes)}", flush=True)
    sina = load_sina_closes(codes)
    print(f"sina daily: {len(sina)}/{len(codes)}", flush=True)

    noon_w: dict[str, dict[str, float]] = defaultdict(dict)
    noon_d: dict[str, dict[str, float]] = defaultdict(dict)
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
        if not q or not b or b <= 0:
            n_skip += 1
            blocked_empty[td].add(r.code)
            continue
        qn = float(r.price_1130) * (q / b)
        noon_d[r.code][td] = qn
        wkey = (alias.get(r.code) or {}).get(td) or td
        noon_w[r.code][wkey] = qn
        n_map += 1
    print(
        f"mapped qfq_1430={n_map} skip_no_bfq={n_skip} empty_block_rows={n_empty}",
        flush=True,
    )

    listed = noon[noon["status"] != "not_listed"]
    listed = listed[(listed.trade_date >= EVAL_START) & (listed.trade_date <= END_S)]
    nonnull_rate = float(listed["price_1130"].notna().mean()) if len(listed) else 0.0
    weeks_with_any_noon = listed[listed["price_1130"].notna()].groupby("trade_date").size()
    cov_stats = {
        "px_1430_csv": str(NOON_CSV),
        "n_codes_aum2": len(codes),
        "n_calendar_weeks": len(calendar),
        "listed_1430_nonnull_rate": nonnull_rate,
        "n_qfq_1430_mapped": n_map,
        "n_skip_no_sina_or_qfq": n_skip,
        "n_empty_status_rows": n_empty,
        "weeks_with_mapped_1430_median_codes": float(weeks_with_any_noon.median())
        if len(weeks_with_any_noon)
        else 0.0,
        "snap_cache_used": str(SNAP_CACHE),
        "sample_note": f"延窗研究：2020-01-03→{END_S}（CLOUD-BATCH research_cache + cache_1430_snaps end=2026-10-23）。",
        "approximation": [
            "延窗：week/day/face/14:30 来自 CLOUD-BATCH data/research_cache；breadth risk_on 用 holdings_ro2_extended",
            "qfq_1430 = price_1430 × (day qfq 收 / sina 收)；sina 作 bfq 代理",
            "14:30 分类只读 cache_1430_snaps.json（end=2026-10-23）",
            "Sharpe 窗截至信号日严格前一交易日（无周五收盘前视）",
            "成交/净值：周五收盘填仓 + TV25 + 0.2%RT；L≤1",
            "唯一改动：持仓权重 EQ5 / INV20W / CAP30；SHARPE20 填席与 max5 不变",
            "不写 strategy_exec / LIVE_OPS / 冠军主钉",
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
        raise SystemExit(f"missing read-only SNAP_CACHE {SNAP_CACHE}")
    print(f"load cached 1430 snaps {SNAP_CACHE}", flush=True)
    cached = json.loads(SNAP_CACHE.read_text(encoding="utf-8"))
    by_rows = cached.get("by_code") or {}
    snaps = {c: snap_index(by_rows.get(c) or []) for c in codes}
    print(f"  cached codes with snaps: {sum(1 for c in codes if snaps.get(c))}", flush=True)

    # (rank_fn, require_sharpe, sharpe_n, sizing_mode)
    variants: dict[str, tuple[RankFn, bool, int | None, SizingMode]] = {
        "RESEARCH-S20-EQ5": (sharpe_key, True, 20, "eq"),
        "RESEARCH-S20-INV20W": (sharpe_key, True, 20, "inv20w"),
        "RESEARCH-S20-CAP30": (sharpe_key, True, 20, "cap30"),
    }
    hold_by: dict[str, dict[str, list[str]]] = {}
    weights_by: dict[str, dict[str, dict[str, float]]] = {}
    sim_stats: dict[str, Any] = {}
    for name, (rfn, req, sn, sm) in variants.items():
        print(f"simulate {name} (sizing={sm})…", flush=True)
        trades, hold, wby, st = simulate(
            calendar,
            snaps,
            closes_w_sig,
            closes_w_close,
            alias,
            aum,
            daily,
            risk_on_by_fri,
            rfn,
            name,
            req,
            sn,
            MAX_POS,
            sm,
        )
        # empty/cash weeks among signal Fridays (excl last calendar sentinel)
        n_cash = sum(1 for d in calendar[:-1] if not (hold.get(d) or []))
        st = {**st, "n_cash_weeks": n_cash}
        hold_by[name] = hold
        weights_by[name] = wby
        sim_stats[name] = st
        rows = []
        for d in calendar[:-1]:
            codes_h = hold.get(d) or []
            wk = wby.get(d) or {}
            rows.append(
                {
                    "date": d,
                    "risk_on": int(risk_on_by_fri.get(d, False)),
                    "n_held": len(codes_h),
                    "codes": ",".join(codes_h),
                    "weights": ";".join(f"{c}:{wk.get(c, 0):.4f}" for c in codes_h),
                    "invested_frac": sum(wk.get(c, 0) for c in codes_h),
                }
            )
        pd.DataFrame(rows).to_csv(OUT / f"holdings_{name}.csv", index=False)
        pd.DataFrame(trades).to_csv(OUT / f"trades_{name}.csv", index=False)
        print(
            f"  entries={st['n_entries']} trades={st['n_trades']} "
            f"cands_weeks={st['n_fridays_with_cands']} tight={st['n_fridays_queue_gt_seats']} "
            f"cash={n_cash}",
            flush=True,
        )

    def pick_diff(a: str, b: str) -> dict[str, Any]:
        n = n_diff = 0
        for d, ca in hold_by[a].items():
            cb = hold_by[b].get(d) or []
            if not ca and not cb:
                continue
            n += 1
            if set(ca) != set(cb):
                n_diff += 1
        return {"n": n, "n_diff": n_diff, "pct_diff": n_diff / n if n else None}

    base = "RESEARCH-S20-EQ5"
    alt_names = [k for k in variants if k != base]
    diffs = {f"{k}_vs_EQ5": pick_diff(base, k) for k in alt_names}
    print("hold diffs vs EQ5", diffs, flush=True)

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
            if f.exists():
                df = pd.read_csv(f, parse_dates=["Date"])
                px_map[c] = df.set_index("Date")["Close"].astype(float).sort_index()
    px = pd.DataFrame(px_map).sort_index()
    px = px.loc[(px.index >= EVAL_START) & (px.index <= END_S)]
    R = px.pct_change()
    if "510300" in px.columns:
        days = px["510300"].dropna().index
    else:
        days = px.dropna(how="all").index
    days = days[(days >= EVAL_START) & (days <= END_S)]
    print(f"live days {days[0].date()} → {days[-1].date()} n={len(days)}", flush=True)

    table_rows = []
    series: dict[str, pd.Series] = {}
    Ls_map: dict[str, pd.Series] = {}
    occ_map: dict[str, dict[str, Any]] = {}
    to_map: dict[str, float] = {}
    for name in variants:
        hd: dict[pd.Timestamp, dict[str, float]] = {}
        for d in calendar:
            cs = hold_by[name].get(d) or []
            if not cs:
                hd[pd.Timestamp(d)] = {}
                continue
            wk = weights_by[name].get(d)
            if not wk:
                wk = {c: 1.0 / len(cs) for c in cs}
            hd[pd.Timestamp(d)] = wk
        r, L, avg_to = run_live_tv(hd, days, px, R)
        series[name] = r
        Ls_map[name] = L
        to_map[name] = avg_to
        occ = occupied_week_stats(r, hd, days)
        occ_map[name] = occ
        st = stats_full(r)
        r2022 = r[(r.index >= "2020-01-01") & (r.index <= "2022-12-31")]
        r2023 = r[r.index >= "2023-01-01"]
        st2022 = stats_full(r2022) if len(r2022) > 5 else {k: float("nan") for k in st}
        st2023 = stats_full(r2023) if len(r2023) > 5 else {k: float("nan") for k in st}
        row = {
            "book": name,
            **st,
            "2020-22_ret": st2022["ret"],
            "2020-22_DD": st2022["maxDD"],
            "2020-22_Calmar": st2022["Calmar"],
            "2023-26_ret": st2023["ret"],
            "2023-26_DD": st2023["maxDD"],
            "2023-26_Calmar": st2023["Calmar"],
            "avgL": float(L[L > 0].mean()) if (L > 0).any() else 0.0,
            "avg_turnover_1way": avg_to,
            "avg_turnover": avg_to,  # alias for RET-style reports
            "occ_n": occ["n_occ_weeks"],
            "occ_winrate": occ["winrate"],
            "occ_payoff": occ["payoff"],
            "occ_avg_win": occ["avg_win"],
            "occ_avg_loss": occ["avg_loss"],
            "n_cash_weeks": sim_stats[name]["n_cash_weeks"],
        }
        table_rows.append(row)
        print(
            f"  {name}: ret={pct(st['ret'])} dd={pct(st['maxDD'])} "
            f"CAGR={pct(st['CAGR'])} Calmar={st['Calmar']:.2f} "
            f"occWR={pct(occ['winrate'])} payoff={num(occ['payoff'])} to1w={avg_to:.3f}",
            flush=True,
        )

    df = pd.DataFrame(table_rows)
    df.to_csv(OUT / "table.csv", index=False)
    df.to_csv(OUT / "metrics.csv", index=False)

    y = yearly_table(series[base]).rename(columns=lambda c: f"eq_{c}" if c != "year" else c)
    for slug, tag in (
        ("RESEARCH-S20-INV20W", "inv"),
        ("RESEARCH-S20-CAP30", "cap"),
    ):
        yi = yearly_table(series[slug]).rename(
            columns=lambda c, p=tag: f"{p}_{c}" if c != "year" else c
        )
        y = y.merge(yi, on="year", how="outer")
    y["delta_inv_vs_eq_pp"] = (y["inv_ret"] - y["eq_ret"]) * 100
    y["delta_cap_vs_eq_pp"] = (y["cap_ret"] - y["eq_ret"]) * 100
    y.to_csv(OUT / "yearly.csv", index=False)

    eq = pd.DataFrame({k: (1 + series[k]).cumprod() for k in variants})
    eq.to_csv(OUT / "equity.csv")
    eq.to_csv(OUT / "nav_all.csv")
    for name in variants:
        series[name].to_csv(OUT / f"nav_{name}.csv", header=["r"])

    fig, ax = plt.subplots(figsize=(11, 5.5), dpi=120)
    styles = {
        "RESEARCH-S20-EQ5": (2.0, "-"),
        "RESEARCH-S20-INV20W": (1.4, "--"),
        "RESEARCH-S20-CAP30": (1.2, ":"),
    }
    for name, (lw, ls) in styles.items():
        ax.plot(
            eq.index,
            eq[name],
            label=name.replace("RESEARCH-S20-", ""),
            lw=lw,
            ls=ls,
        )
    ax.set_yscale("log")
    ax.set_title("SPIKE-S20-POS-SIZING-RESEARCH（权重轴；研究池）")
    ax.set_ylabel("净值（对数）")
    ax.grid(True, alpha=0.3)
    ax.legend(fontsize=8)
    fig.tight_layout()
    fig.savefig(OUT / "equity_curve.png")
    plt.close(fig)

    eq_row = df[df.book == base].iloc[0]
    by_alt = {k: df[df.book == k].iloc[0] for k in alt_names}

    def delta_vs_eq(row: pd.Series) -> dict[str, Any]:
        dret = (float(row["ret"]) - float(eq_row["ret"])) * 100
        ddd_abs = (abs(float(row["maxDD"])) - abs(float(eq_row["maxDD"]))) * 100
        strong_ok = float(row["2023-26_ret"]) >= float(eq_row["2023-26_ret"]) * 0.9
        covers = dret >= ddd_abs
        return {
            "dret_pp": dret,
            "d_abs_mdd_pp": ddd_abs,
            "covers": covers,
            "strong_2023_26_ok": strong_ok,
            "better_calmar": float(row["Calmar"]) > float(eq_row["Calmar"]),
        }

    sizing_delta = {k: delta_vs_eq(by_alt[k]) for k in alt_names}
    align_note = (
        f"基线 **EQ5**（=B45+S20 等权）：ret={pct(float(eq_row['ret']))} "
        f"MDD={pct(float(eq_row['maxDD']))} Calmar={float(eq_row['Calmar']):.2f}；"
        f"样本 {calendar[0]}→{calendar[-1]}（n={len(calendar)} 周）。"
    )
    print(align_note, flush=True)

    lines = []
    labels = {"RESEARCH-S20-INV20W": "INV20W", "RESEARCH-S20-CAP30": "CAP30"}
    for k in alt_names:
        d = sizing_delta[k]
        r = by_alt[k]
        lines.append(
            f"- {labels[k]}：ret={pct(float(r['ret']))} MDD={pct(float(r['maxDD']))} "
            f"Calmar={float(r['Calmar']):.2f}；Δvs EQ5 ret={d['dret_pp']:+.1f}pp "
            f"Δ|MDD|={d['d_abs_mdd_pp']:+.1f}pp 盖住={'是' if d['covers'] else '否'} "
            f"2023–26不差={'是' if d['strong_2023_26_ok'] else '否'}"
        )
    grid_lines = "\n".join(lines)

    winners = [
        labels[k]
        for k in alt_names
        if sizing_delta[k]["dret_pp"] > 0
        and sizing_delta[k]["covers"]
        and sizing_delta[k]["strong_2023_26_ok"]
    ]
    if winners:
        verdict = (
            f"**探索记正（不换冠）**：{', '.join(winners)} 相对 EQ5 Δret 盖住 Δ|MDD| 且后段不踏空；"
            "仍不改冠军等权主钉。"
        )
    elif any(
        sizing_delta[k]["dret_pp"] > 0 and sizing_delta[k]["covers"] for k in alt_names
    ):
        verdict = (
            "**探索偏弱（不换冠）**：有变体盖住回撤但 2023–26 踏空或未优于 Calmar；维持 EQ5。"
        )
    else:
        verdict = (
            "**探索证伪/记账（不换冠）**：INV20W 与 CAP30 均未稳定优于 B45+S20 等权；"
            "与 2026-10-14 INVVOL 叙事一致，不换冠。"
        )

    summary = {
        "title": "SPIKE-S20-POS-SIZING-RESEARCH",
        "convention": "Fri ≥14:30 signal / Friday close fill; TV25 L≤1; 0.2%RT; breadth≥0.45; research pool",
        "unique_change": "position weights EQ5 vs INV20W vs CAP30; SHARPE20 entry ranks frozen; max5",
        "batch": "CLOUD-POS-SIZING",
        "sample": f"{EVAL_START} → {calendar[-1]}",
        "n_calendar_weeks": len(calendar),
        "coverage": cov_stats,
        "hold_diffs_vs_eq5": diffs,
        "sim_stats": sim_stats,
        "table": table_rows,
        "delta_vs_eq5": sizing_delta,
        "baseline_eq5": {
            "ret": float(eq_row["ret"]),
            "maxDD": float(eq_row["maxDD"]),
            "Calmar": float(eq_row["Calmar"]),
        },
        "verdict": verdict,
        "isolation": "strategy_exec / LIVE_OPS: NONE overwritten",
        "elapsed_sec": round(time.time() - t0, 1),
    }
    (OUT / "summary.json").write_text(
        json.dumps(summary, ensure_ascii=False, indent=2, default=str), encoding="utf-8"
    )

    (OUT / "criterion.md").write_text(
        "# Criterion · SPIKE-S20-POS-SIZING-RESEARCH\n\n"
        "- **唯一改动**：持仓权重 **EQ5 / INV20W / CAP30**；填席仍 **SHARPE20**；**max5** 不变。\n"
        "- **冻结**：B45 + spike_ft + E0 + TV25；Fri≥14:30 / 收盘；0.2%RT；L≤1；**研究池**。\n"
        "- **基线**：RESEARCH-S20-EQ5 = B45+S20 等权。\n"
        "- **INV20W**：20 周周线已实现波动率倒数加权（全投资）。\n"
        "- **CAP30**：等权后单票上限 30%，超出部分留现金。\n"
        "- **样本**：延窗 ≥2026-10-23（CLOUD-BATCH research_cache）。\n"
        "- **探索尺子**：Δret 须盖住 Δ|MDD|；报 2020–22 / 2023–26；强势段不踏空。\n"
        "- **红线**：不写 strategy_exec / LIVE_OPS；不换冠。\n"
        "- **批次**：CLOUD-POS-SIZING。\n",
        encoding="utf-8",
    )

    def row_md(name: str) -> str:
        r = df[df.book == name].iloc[0]
        st = sim_stats[name]
        tag = " **基线**" if name == base else ""
        short = name.replace("RESEARCH-S20-", "")
        return (
            f"| {short}{tag} | {pct(r['ret'])} | {pct(r['maxDD'])} | {pct(r['CAGR'])} | {r['Calmar']:.2f} | "
            f"{pct(r['2020-22_ret'])}/{pct(r['2020-22_DD'])}/{r['2020-22_Calmar']:.2f} | "
            f"{pct(r['2023-26_ret'])}/{pct(r['2023-26_DD'])}/{r['2023-26_Calmar']:.2f} | "
            f"{r['avgL']:.2f} | {r['avg_turnover']:.3f} | {st['n_cash_weeks']} |"
        )

    y_lines = [
        "| 年 | EQ5 | INV20W | Δpp(inv-eq) | CAP30 | Δpp(cap-eq) |",
        "|---|---:|---:|---:|---:|---:|",
    ]
    for _, row in y.iterrows():
        y_lines.append(
            f"| {int(row.year)} | {pct(float(row.eq_ret)) if pd.notna(row.eq_ret) else '—'} | "
            f"{pct(float(row.inv_ret)) if pd.notna(row.inv_ret) else '—'} | "
            f"{float(row.delta_inv_vs_eq_pp):+.1f} | "
            f"{pct(float(row.cap_ret)) if pd.notna(row.cap_ret) else '—'} | "
            f"{float(row.delta_cap_vs_eq_pp):+.1f} |"
        )

    approx_md = "\n".join(f"- {a}" for a in cov_stats["approximation"])
    d_inv = diffs.get("RESEARCH-S20-INV20W_vs_EQ5", {})
    d_cap = diffs.get("RESEARCH-S20-CAP30_vs_EQ5", {})

    report = f"""# REPORT · SPIKE-S20-POS-SIZING-RESEARCH（权重轴 · 研究池）

## 准则原文（摘要）

相对 B45+S20（EQ5 等权）**只改持仓权重**：等权 max5 / 20 周反波动 / 单票 30% 上限；**入场排序仍 SHARPE20**；E0+TV25 不变。研究池；窗 ≥2026-10-23。CLOUD-POS-SIZING，不换冠。

## 实现要点

- 引擎：fork MAXSEAT `run.py` + CLOUD-BATCH `research_cache` 延窗路径。
- 三账本：EQ5 / INV20W / CAP30；EQ5 为 B45+S20 基线。
- 只读：`CLOUD-BATCH-2026-10-26/data/cache_1430_snaps.json`（end=2026-10-23）。
- 隔离：strategy_exec / LIVE_OPS **NONE** 写入。

{align_note}

## 近似与覆盖

{approx_md}

| 覆盖 | 值 |
|---|---|
| 可投池（AUM≥2亿） | {len(codes)} |
| 日历周 | {len(calendar)}（至 {calendar[-1]}） |
| listed 行 14:30 非空率 | {100*nonnull_rate:.1f}% |
| 成功映射 qfq_1430 | {n_map} |
| EQ5 候选周 / 排队>席 | {sim_stats[base]['n_fridays_with_cands']} / {sim_stats[base]['n_fridays_queue_gt_seats']} |
| INV20W vs EQ5 持仓差异周 | {d_inv.get('n_diff', 0)}/{d_inv.get('n', 0)} |
| CAP30 vs EQ5 持仓差异周 | {d_cap.get('n_diff', 0)}/{d_cap.get('n', 0)} |

## 主表（研究池 · Fri 14:30 · 三档）

| book | ret | maxDD | CAGR | Calmar | 2020–22 ret/DD/Calmar | 2023–26 ret/DD/Calmar | avgL | avgTO | 空仓周 |
|---|---:|---:|---:|---:|---|---|---:|---:|---:|
{row_md("RESEARCH-S20-EQ5")}
{row_md("RESEARCH-S20-INV20W")}
{row_md("RESEARCH-S20-CAP30")}

## Δ vs EQ5（探索尺子）

{grid_lines}

## 分段（EQ5 基线）

| 段 | EQ5 ret/DD/Calmar |
|---|---|
| 2020–22 | {pct(float(eq_row['2020-22_ret']))} / {pct(float(eq_row['2020-22_DD']))} / {float(eq_row['2020-22_Calmar']):.2f} |
| 2023–26 | {pct(float(eq_row['2023-26_ret']))} / {pct(float(eq_row['2023-26_DD']))} / {float(eq_row['2023-26_Calmar']):.2f} |

## 历年

{chr(10).join(y_lines)}

## 结论（探索记账，不换冠）

{verdict}

## 产物

- `run.py` / `criterion.md` / `REPORT.md` / `summary.json`
- `table.csv` / `metrics.csv` / `yearly.csv` / `equity.csv` / `nav_*.csv` / `equity_curve.png`
- `holdings_*.csv` / `trades_*.csv` / `entries_*.csv`

耗时约 {summary['elapsed_sec']}s。
"""
    (OUT / "REPORT.md").write_text(report, encoding="utf-8")
    print("done", OUT, flush=True)
    print(verdict, flush=True)


if __name__ == "__main__":
    main()
