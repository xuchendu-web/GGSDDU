#!/usr/bin/env python3
"""SPIKE-S20-ENTRY-PERSIST-K-LIVE1430: entry top-seat persistence K∈{1,2,3} before fill.

Books (B45 + spike_ft max5 + E0 + TV25 + S20 + 0.2%RT + L≤1; only entry persist K):
  LIVE1430-EP-K1 (=B45+S20 baseline), LIVE1430-EP-K2, LIVE1430-EP-K3.

Top-seat = S20 rank within spike_ft Top5 seats; fill only if streak≥K consecutive signal weeks.
CLOUD-ENTRY-PERSIST-K — research pool only; no crown swap; no strategy_exec / LIVE_OPS.
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
MAX_POS = 5
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
    alias: dict[str, dict[str, str]],
    aum: dict[str, float],
    daily: dict[str, pd.Series],
    risk_on_by_fri: dict[str, bool],
    rank_fn: RankFn,
    variant: str,
    require_sharpe: bool,
    sharpe_n: int | None,
    max_pos: int,
    entry_persist_k: int = 1,
) -> tuple[list[dict[str, Any]], dict[str, list[str]], dict[str, Any]]:
    cash = 1.0
    positions: dict[str, Position] = {}
    trades: list[dict[str, Any]] = []
    picks: dict[str, list[str]] = {}
    n_tight = 0
    n_feat = 0
    n_entries = 0
    n_miss_sharpe = 0
    n_blocked_persist = 0
    top_seat_streak: dict[str, int] = {}
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

        # Top-seat streak: consecutive signal weeks in S20 Top-max_pos among all spike_ft.
        all_spike = build_cands(d, set())
        all_rank = all_spike
        if require_sharpe:
            all_rank = [c for c in all_spike if c.sharpe is not None]
        top_sorted = sorted(all_rank, key=lambda c: rank_fn(c, all_rank))
        top_codes = {c.code for c in top_sorted[:max_pos]}
        for code in list(top_seat_streak.keys()):
            if code not in top_codes:
                top_seat_streak[code] = 0
        for code in top_codes:
            top_seat_streak[code] = top_seat_streak.get(code, 0) + 1

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
                ranked = sorted(pool_rank, key=lambda c: rank_fn(c, pool_rank))
                eligible: list[Cand] = []
                for c in ranked:
                    if top_seat_streak.get(c.code, 0) >= entry_persist_k:
                        eligible.append(c)
                    else:
                        n_blocked_persist += 1
                take = eligible[:slots]
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

    stats = {
        "n_fridays_queue_gt_seats": n_tight,
        "n_fridays_with_cands": n_feat,
        "n_entries": n_entries,
        "n_entries_missing_sharpe": n_miss_sharpe,
        "n_trades": len(trades),
        "max_pos": max_pos,
        "entry_persist_k": entry_persist_k,
        "n_blocked_persist": n_blocked_persist,
    }
    if rank_rows:
        pd.DataFrame(rank_rows).to_csv(OUT / f"entries_{variant}.csv", index=False)
    return trades, hold, stats


def run_live_tv(
    hold: dict[pd.Timestamp, list[str]], days: pd.DatetimeIndex, px: pd.DataFrame, R: pd.DataFrame
) -> tuple[pd.Series, pd.Series, float]:
    """Returns daily net ret, L series, and average one-way turnover per rebalance."""
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
            "唯一改动：新进填席须连续 K 周处于 S20 Top5 席位（top-seat）；K∈{1,2,3}",
            "不写 strategy_exec / LIVE_OPS / 冠军主钉 / 实盘池",
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

    # (rank_fn, require_sharpe, sharpe_n, entry_persist_k)
    variants: dict[str, tuple[RankFn, bool, int | None, int]] = {
        "LIVE1430-EP-K1": (sharpe_key, True, 20, 1),  # B45+S20 baseline
        "LIVE1430-EP-K2": (sharpe_key, True, 20, 2),
        "LIVE1430-EP-K3": (sharpe_key, True, 20, 3),
    }
    hold_by: dict[str, dict[str, list[str]]] = {}
    sim_stats: dict[str, Any] = {}
    for name, (rfn, req, sn, ek) in variants.items():
        print(f"simulate {name} (entry_persist_k={ek}, max_pos={MAX_POS})…", flush=True)
        trades, hold, st = simulate(
            calendar,
            snaps,
            closes_w_sig,
            alias,
            aum,
            daily,
            risk_on_by_fri,
            rfn,
            name,
            req,
            sn,
            MAX_POS,
            ek,
        )
        # empty/cash weeks among signal Fridays (excl last calendar sentinel)
        n_cash = sum(1 for d in calendar[:-1] if not (hold.get(d) or []))
        st = {**st, "n_cash_weeks": n_cash}
        hold_by[name] = hold
        sim_stats[name] = st
        rows = []
        for d in calendar[:-1]:
            codes_h = hold.get(d) or []
            rows.append(
                {
                    "date": d,
                    "risk_on": int(risk_on_by_fri.get(d, False)),
                    "n_held": len(codes_h),
                    "codes": ",".join(codes_h),
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

    base = "LIVE1430-EP-K1"
    diffs = {
        f"K{k}_vs_K1": pick_diff(base, f"LIVE1430-EP-K{k}") for k in (2, 3)
    }
    print("diffs", diffs, flush=True)

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
        hd = {pd.Timestamp(d): cs for d, cs in hold_by[name].items()}
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

    y = yearly_table(series[base]).rename(columns=lambda c: f"K1_{c}" if c != "year" else c)
    for k in (2, 3):
        slug = f"LIVE1430-EP-K{k}"
        yi = yearly_table(series[slug]).rename(
            columns=lambda c, p=f"K{k}": f"{p}_{c}" if c != "year" else c
        )
        y = y.merge(yi, on="year", how="outer")
    y["delta_K3_vs_K1_pp"] = (y["K3_ret"] - y["K1_ret"]) * 100
    y.to_csv(OUT / "yearly.csv", index=False)

    eq = pd.DataFrame({k: (1 + series[k]).cumprod() for k in variants})
    eq.to_csv(OUT / "equity.csv")
    eq.to_csv(OUT / "nav_all.csv")
    for name in variants:
        series[name].to_csv(OUT / f"nav_{name}.csv", header=["r"])

    fig, ax = plt.subplots(figsize=(11, 5.5), dpi=120)
    styles = {
        "LIVE1430-EP-K1": (2.0, "-"),
        "LIVE1430-EP-K2": (1.2, "--"),
        "LIVE1430-EP-K3": (1.0, ":"),
    }
    for name, (lw, ls) in styles.items():
        ax.plot(eq.index, eq[name], label=name.replace("LIVE1430-EP-", "K"), lw=lw, ls=ls)
    ax.set_yscale("log")
    ax.set_title("SPIKE-S20-ENTRY-PERSIST-K-LIVE1430（top-seat 连续周 · 延窗）")
    ax.set_ylabel("净值（对数）")
    ax.grid(True, alpha=0.3)
    ax.legend(fontsize=8)
    fig.tight_layout()
    fig.savefig(OUT / "equity_curve.png")
    plt.close(fig)

    b1 = df[df.book == base].iloc[0]
    by_k = {k: df[df.book == f"LIVE1430-EP-K{k}"].iloc[0] for k in (1, 2, 3)}

    def delta_vs_b45(row: pd.Series) -> dict[str, Any]:
        dret = (float(row["ret"]) - float(b1["ret"])) * 100
        ddd_abs = (abs(float(row["maxDD"])) - abs(float(b1["maxDD"]))) * 100
        strong_ok = float(row["2023-26_ret"]) >= float(b1["2023-26_ret"])
        covers = dret >= ddd_abs
        return {
            "dret_pp": dret,
            "d_abs_mdd_pp": ddd_abs,
            "covers": covers,
            "strong_2023_26_ok": strong_ok,
            "better_calmar": float(row["Calmar"]) > float(b1["Calmar"]),
        }

    grid_delta = {k: delta_vs_b45(by_k[k]) for k in (2, 3)}
    align_note = (
        f"基线 **B45+S20（EP-K1）**：ret={pct(float(b1['ret']))} "
        f"MDD={pct(float(b1['maxDD']))} Calmar={float(b1['Calmar']):.2f}；"
        f"样本 {calendar[0]}→{calendar[-1]}（n={len(calendar)} 周）。"
    )
    print(align_note, flush=True)

    falsify_hits = []
    for k in (2, 3):
        d = grid_delta[k]
        if d["dret_pp"] > 0 and d["covers"] and d["strong_2023_26_ok"]:
            falsify_hits.append(f"K{k}")

    lines = []
    for k in (2, 3):
        d = grid_delta[k]
        r = by_k[k]
        lines.append(
            f"- K{k}：ret={pct(float(r['ret']))} MDD={pct(float(r['maxDD']))} "
            f"Calmar={float(r['Calmar']):.2f}；Δvs B45 ret={d['dret_pp']:+.1f}pp "
            f"Δ|MDD|={d['d_abs_mdd_pp']:+.1f}pp 盖住={'是' if d['covers'] else '否'} "
            f"2023–26≥基线={'是' if d['strong_2023_26_ok'] else '否'}"
        )
    grid_lines = "\n".join(lines)

    if falsify_hits:
        falsify_line = (
            f"H1 证伪：入口持续性邻档可升格 — {', '.join(falsify_hits)} 相对 B45+S20 "
            f"Δret 盖住 Δ|MDD| 且 2023–26 不踏空（仍不换冠，仅记账）。"
        )
        verdict = falsify_line
    else:
        falsify_line = (
            "H1 成立：K=2/3 入口 top-seat 持续性未同时满足 Δret 盖住 Δ|MDD| 与 2023–26 不踏空；"
            "B45+S20 即时填席仍优。"
        )
        verdict = f"**不换冠**：{falsify_line}"

    summary = {
        "title": "SPIKE-S20-ENTRY-PERSIST-K-LIVE1430",
        "convention": "Fri ≥14:30 signal / Friday close fill; TV25 L≤1; 0.2%RT; breadth≥0.45",
        "unique_change": "entry top-seat persist K∈{1,2,3}; spike_ft max5 + SHARPE20 frozen",
        "batch": "CLOUD-ENTRY-PERSIST-K",
        "falsify_line": falsify_line,
        "sample": f"{EVAL_START} → {calendar[-1]}",
        "n_calendar_weeks": len(calendar),
        "coverage": cov_stats,
        "pick_diffs": diffs,
        "sim_stats": sim_stats,
        "table": table_rows,
        "delta_vs_B45": grid_delta,
        "baseline_B45_S20": {
            "ret": float(b1["ret"]),
            "maxDD": float(b1["maxDD"]),
            "Calmar": float(b1["Calmar"]),
        },
        "verdict": verdict,
        "isolation": "strategy_exec / LIVE_OPS: NONE overwritten",
        "elapsed_sec": round(time.time() - t0, 1),
    }
    (OUT / "summary.json").write_text(
        json.dumps(summary, ensure_ascii=False, indent=2, default=str), encoding="utf-8"
    )

    (OUT / "criterion.md").write_text(
        "# Criterion · SPIKE-S20-ENTRY-PERSIST-K-LIVE1430\n\n"
        "- **唯一改动**：新进填席前须 **连续 K 周** 处于 S20 **Top5 席位（top-seat）**；K∈{1,2,3}。\n"
        "- **冻结**：B45 + spike_ft **max5** + E0 + TV25 + SHARPE20；Fri≥14:30 / 收盘；0.2%RT；L≤1。\n"
        "- **基线**：K=1 = B45+S20（无额外等待）。\n"
        "- **样本**：延窗 ≥2026-10-23（CLOUD-BATCH research_cache · 冻结研究池）。\n"
        "- **探索尺子**：邻档 Δret 须盖住 Δ|MDD|；2023–26 累计 ≥ 基线。\n"
        "- **红线**：不写 strategy_exec / LIVE_OPS / champion_mast / 实盘池。\n"
        "- **批次**：CLOUD-ENTRY-PERSIST-K；**不升格**。\n",
        encoding="utf-8",
    )

    def row_md(name: str) -> str:
        r = df[df.book == name].iloc[0]
        st = sim_stats[name]
        tag = " **B45基线**" if name.endswith("K1") else ""
        return (
            f"| {name}{tag} | {pct(r['ret'])} | {pct(r['maxDD'])} | {pct(r['CAGR'])} | {r['Calmar']:.2f} | "
            f"{pct(r['2020-22_ret'])}/{pct(r['2020-22_DD'])}/{r['2020-22_Calmar']:.2f} | "
            f"{pct(r['2023-26_ret'])}/{pct(r['2023-26_DD'])}/{r['2023-26_Calmar']:.2f} | "
            f"{r['avgL']:.2f} | {r['avg_turnover']:.3f} | {st['n_cash_weeks']} |"
        )

    y_lines = [
        "| 年 | K1(B45) | K2 | K3 | Δpp(K3-K1) |",
        "|---|---:|---:|---:|---:|",
    ]
    for _, row in y.iterrows():
        y_lines.append(
            f"| {int(row.year)} | {pct(float(row.K1_ret)) if pd.notna(row.K1_ret) else '—'} | "
            f"{pct(float(row.K2_ret)) if pd.notna(row.K2_ret) else '—'} | "
            f"{pct(float(row.K3_ret)) if pd.notna(row.K3_ret) else '—'} | "
            f"{float(row.delta_K3_vs_K1_pp):+.1f} |"
        )

    approx_md = "\n".join(f"- {a}" for a in cov_stats["approximation"])
    d3 = diffs["K3_vs_K1"]

    main_table = f"""# main_table — 入口 top-seat 持续性 K vs B45+S20

样本窗：{EVAL_START} → {calendar[-1]}（CLOUD-BATCH research_cache · 冻结研究池）

**证伪一行**：{falsify_line}

| book | K | ret | maxDD | Calmar | 2023–26 ret | turnover/wk | sample |
|------|---|-----|-------|--------|-------------|-------------|--------|
| B45+S20 (EP-K1) | 1 | {pct(float(b1['ret']))} | {pct(float(b1['maxDD']))} | {float(b1['Calmar']):.2f} | {pct(float(b1['2023-26_ret']))} | {float(b1['avg_turnover']):.2f} | {calendar[0]}→{calendar[-1]} |
| B45+S20-EP-K2 | 2 | {pct(float(by_k[2]['ret']))} | {pct(float(by_k[2]['maxDD']))} | {float(by_k[2]['Calmar']):.2f} | {pct(float(by_k[2]['2023-26_ret']))} | {float(by_k[2]['avg_turnover']):.2f} | 同上 |
| B45+S20-EP-K3 | 3 | {pct(float(by_k[3]['ret']))} | {pct(float(by_k[3]['maxDD']))} | {float(by_k[3]['Calmar']):.2f} | {pct(float(by_k[3]['2023-26_ret']))} | {float(by_k[3]['avg_turnover']):.2f} | 同上 |

## Δ vs B45+S20（K1）

| K | Δret (pp) | Δ|MDD| (pp) | 盖回撤? | 2023–26≥基线? | blocked_entries |
|---|-----------|-------------|---------|---------------|-----------------|
| 2 | {grid_delta[2]['dret_pp']:+.1f} | {grid_delta[2]['d_abs_mdd_pp']:+.1f} | {'Y' if grid_delta[2]['covers'] else 'N'} | {'Y' if grid_delta[2]['strong_2023_26_ok'] else 'N'} | {sim_stats['LIVE1430-EP-K2']['n_blocked_persist']} |
| 3 | {grid_delta[3]['dret_pp']:+.1f} | {grid_delta[3]['d_abs_mdd_pp']:+.1f} | {'Y' if grid_delta[3]['covers'] else 'N'} | {'Y' if grid_delta[3]['strong_2023_26_ok'] else 'N'} | {sim_stats['LIVE1430-EP-K3']['n_blocked_persist']} |
"""
    (OUT / "main_table.md").write_text(main_table, encoding="utf-8")

    report = f"""# REPORT · SPIKE-S20-ENTRY-PERSIST-K-LIVE1430

## 准则（rule）

见 `criterion.md` / `../CLOUD-BATCH-2026-10-26/knives/SPIKE-S20-ENTRY-PERSIST-K-LIVE1430.md`。

## 实现（impl）

- `run.py`：fork MAXSEAT 延窗引擎；`simulate(..., entry_persist_k=K)`。
- top-seat = 当周 spike_ft 池内 S20 排名 Top5；新进须连续 K 周在 Top5 才可填席。

## 主表

见 `main_table.md`。

## 证伪

{falsify_line}

---

{align_note}

| K2 vs K1 持仓差异周 | {diffs['K2_vs_K1']['n_diff']}/{diffs['K2_vs_K1']['n']} |
| K3 vs K1 持仓差异周 | {d3['n_diff']}/{d3['n']} |

### 明细

| book | ret | maxDD | Calmar | avgTO | 空仓周 |
|---|---:|---:|---:|---:|---:|
{row_md("LIVE1430-EP-K1")}
{row_md("LIVE1430-EP-K2")}
{row_md("LIVE1430-EP-K3")}

{grid_lines}

耗时约 {summary['elapsed_sec']}s。
"""
    (OUT / "REPORT.md").write_text(report, encoding="utf-8")
    print("done", OUT, flush=True)
    print(falsify_line, flush=True)


if __name__ == "__main__":
    main()
