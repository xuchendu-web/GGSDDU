#!/usr/bin/env python3
"""SPIKE-S20-HYST-M3-LIVE1430: Fri 14:30 / close; hysteresis exit band M=3.

Books (B45 + spike_ft + E0 + TV25 + SHARPE20 + max5 + θ=0.45 + 0.2%RT + L≤1):
  LIVE1430-B45-S20      — baseline fill-only (no rank-kick)
  LIVE1430-HYST-M2-S20  — control (reuse E24 logic; align |Δret|≈0)
  LIVE1430-HYST-M3-S20  — main: keep held if rank≤5+3; fill empties from Top5 only
  LIVE1430-HYST-M4-S20  — neighbor M=4 (Top9 keep band; side note only)

滞回只放宽踢出：rank≤5+M 沿持；rank>5+M 主动踢（风控强制另计）。
新进绝不从第 6..5+M 名开仓——空席只从 S20 Top5 未持有者填。max_pos 仍 5。
Exploration — no crown. OPT-HYST-M3 (Michael).
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

SCRIPTS = Path("/workspace/strategy_exec/champion/recon/scripts")
sys.path.insert(0, str(SCRIPTS))

from backtest import KEEP, LIVE_PHASE, MIN_BARS, Position, nearest_date, snap_index  # noqa: E402
from build_scan import Bar, classify  # noqa: E402

OUT = Path("/workspace/strategy-weekly/spike_mom_rank/SPIKE-S20-HYST-M3-LIVE1430")
REF1430 = Path("/workspace/strategy-weekly/spike_mom_rank/SPIKE-SHARPE20-LIVE1430")
FRI_CLOSE_REF = Path("/workspace/strategy-weekly/spike_mom_rank/SPIKE-SHARPE20")
ROOT16 = Path("/workspace/strategy-weekly/etf_replace_only_436/from2016_aum2")
UNI_CSV = Path("/workspace/strategy-weekly/etf_replace_only_436/universe_replace_only_436.csv")
WEEK = Path("/workspace/strategy_exec/champion/recon/data/week2016_2026-10-14")
FACE = ROOT16 / "holdings_ro2_from2016.csv"
DAY_DIR = Path("/workspace/strategy_exec/champion/recon/data/day2017_2026-10-14")
TEMA_PX = Path("/workspace/tema_etf_scan_2018/prices_daily")
NOON_CSV = Path("/workspace/fri_1430_pytdx/fri_1430_through_20260925.csv")  # 14:30 panel
SINA_DAILY = Path("/workspace/fri_noon_pytdx/work/daily")
CLASSIFY_FROM = "2019-07-01"
SNAP_CACHE = REF1430 / "cache_1430_snaps.json"  # read-only reuse; do not overwrite

EVAL_START = "2020-01-03"
END_S = "2026-09-24"
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
    """Annualized Sharpe of last n daily returns ending strictly BEFORE d (LIVE: no Fri close)."""
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
    q = (1 + s).cumprod()
    ret = float(q.iloc[-1] - 1)
    dd = float((q / q.cummax().clip(lower=1e-12) - 1).min())
    n = (s.index[-1] - s.index[0]).days
    cagr = (1 + ret) ** (365.25 / n) - 1 if n > 0 and (1 + ret) > 0 else float("nan")
    cal = cagr / abs(dd) if dd < 0 else float("nan")
    return {"ret": ret, "maxDD": dd, "CAGR": cagr, "Calmar": cal}


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
    noon = noon[noon["code"].isin(code_set)].copy()
    if "price_1430" in noon.columns and "price_1130" not in noon.columns:
        noon["price_1130"] = noon["price_1430"]

    face = pd.read_csv(FACE)
    face["date"] = face["date"].astype(str).str[:10]
    face = face[(face["date"] >= EVAL_START) & (face["date"] <= END_S)].copy()
    calendar = sorted(face["date"].unique().tolist())
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

    print("load daily qfq + sina…", flush=True)
    daily = load_daily_closes(codes)
    sina = load_sina_closes(codes)

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
        if not q or not b or b <= 0:
            n_skip += 1
            blocked_empty[td].add(r.code)
            continue
        qn = float(r.price_1130) * (q / b)
        wkey = (alias.get(r.code) or {}).get(td) or td
        noon_w[r.code][wkey] = qn
        n_map += 1
    print(f"mapped qfq_1430={n_map}", flush=True)

    listed = noon[noon["status"] != "not_listed"]
    listed = listed[(listed.trade_date >= EVAL_START) & (listed.trade_date <= END_S)]
    nonnull_rate = float(listed["price_1130"].notna().mean()) if len(listed) else 0.0
    cov_stats = {
        "px_1430_csv": str(NOON_CSV),
        "n_codes_aum2": len(codes),
        "n_calendar_weeks": len(calendar),
        "listed_1430_nonnull_rate": nonnull_rate,
        "n_qfq_1430_mapped": n_map,
        "approximation": [
            "breadth/risk_on 沿用 face；Sharpe 窗截至信号日前；收盘填仓 + TV25 + 0.2%RT + L≤1",
            "HYST：风控强制卖出后，对仍在 spike 排序中的持仓若 rank>5+M 则踢；非 spike 幸存者只走结构退出",
            "空席只从 S20 Top5 未持有者填入；绝不新开 rank 6..5+M；max_pos=5",
            "B45 基线：无排名踢出，仅空位 Top 填席（原 S20）",
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

    if SNAP_CACHE.exists():
        print(f"load cached 1430 snaps {SNAP_CACHE}", flush=True)
        cached = json.loads(SNAP_CACHE.read_text(encoding="utf-8"))
        by_rows = cached.get("by_code") or {}
        snaps = {c: snap_index(by_rows.get(c) or []) for c in codes}
    else:
        raise SystemExit(f"missing cache {SNAP_CACHE}")

    variants: dict[str, int | None] = {
        "LIVE1430-B45-S20": None,
        "LIVE1430-HYST-M2-S20": 2,
        "LIVE1430-HYST-M3-S20": 3,
        "LIVE1430-HYST-M4-S20": 4,
    }
    hold_by: dict[str, dict[str, list[str]]] = {}
    sim_stats: dict[str, Any] = {}
    risk_on_stats: dict[str, dict[str, Any]] = {}
    for name, hm in variants.items():
        print(f"simulate {name} (hyst_m={hm})…", flush=True)
        trades, hold, st = simulate(
            calendar, snaps, closes_w_sig, alias, aum, daily, risk_on_by_fri,
            sharpe_key, name, True, 20, hyst_m=hm,
        )
        hold_by[name] = hold
        sim_stats[name] = st
        n_on = sum(1 for d in calendar[:-1] if risk_on_by_fri.get(d, False))
        n_cash = sum(1 for d in calendar[:-1] if not (hold.get(d) or []))
        risk_on_stats[name] = {
            "n_risk_on": n_on,
            "pct_risk_on": n_on / max(1, len(calendar) - 1),
            "n_cash_weeks": n_cash,
            "pct_cash": n_cash / max(1, len(calendar) - 1),
        }
        pd.DataFrame(
            [
                {
                    "date": d,
                    "risk_on": int(risk_on_by_fri.get(d, False)),
                    "n_held": len(hold.get(d) or []),
                    "codes": ",".join(hold.get(d) or []),
                }
                for d in calendar[:-1]
            ]
        ).to_csv(OUT / f"holdings_{name}.csv", index=False)
        pd.DataFrame(trades).to_csv(OUT / f"trades_{name}.csv", index=False)
        print(
            f"  entries={st['n_entries']} trades={st['n_trades']} "
            f"forced_x={st['n_forced_exits']} hyst_x={st['n_hyst_exits']} "
            f"avgTO={st['avgTO']:.3f} cash={n_cash}",
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

    diffs = {
        "M3_vs_B45": pick_diff("LIVE1430-B45-S20", "LIVE1430-HYST-M3-S20"),
        "M2_vs_B45": pick_diff("LIVE1430-B45-S20", "LIVE1430-HYST-M2-S20"),
        "M3_vs_M2": pick_diff("LIVE1430-HYST-M2-S20", "LIVE1430-HYST-M3-S20"),
        "M4_vs_B45": pick_diff("LIVE1430-B45-S20", "LIVE1430-HYST-M4-S20"),
        "M4_vs_M3": pick_diff("LIVE1430-HYST-M3-S20", "LIVE1430-HYST-M4-S20"),
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
                dfx = pd.read_csv(f, parse_dates=["Date"])
                px_map[c] = dfx.set_index("Date")["Close"].astype(float).sort_index()
    px = pd.DataFrame(px_map).sort_index()
    px = px.loc[(px.index >= EVAL_START) & (px.index <= END_S)]
    R = px.pct_change()
    days = (px["510300"] if "510300" in px.columns else px.dropna(how="all")).dropna().index
    days = days[(days >= EVAL_START) & (days <= END_S)]

    table_rows = []
    series: dict[str, pd.Series] = {}
    for name in variants:
        hd = {pd.Timestamp(d): cs for d, cs in hold_by[name].items()}
        r, L = run_live_tv(hd, days, px, R)
        series[name] = r
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
            "avgTO": sim_stats[name]["avgTO"],
            "n_entries": sim_stats[name]["n_entries"],
            "n_trades": sim_stats[name]["n_trades"],
            "n_forced_exits": sim_stats[name]["n_forced_exits"],
            "n_hyst_exits": sim_stats[name]["n_hyst_exits"],
            "n_cash_weeks": risk_on_stats[name]["n_cash_weeks"],
            "hyst_m": sim_stats[name]["hyst_m"] if sim_stats[name]["hyst_m"] is not None else -1,
        }
        table_rows.append(row)
        print(
            f"  {name}: ret={pct(st['ret'])} dd={pct(st['maxDD'])} "
            f"Calmar={st['Calmar']:.2f} avgTO={row['avgTO']:.3f}",
            flush=True,
        )

    df = pd.DataFrame(table_rows)
    df.to_csv(OUT / "table.csv", index=False)
    df.to_csv(OUT / "metrics.csv", index=False)

    y = yearly_table(series["LIVE1430-B45-S20"]).rename(
        columns=lambda c: f"b45_{c}" if c != "year" else c
    )
    for slug, col in [
        ("LIVE1430-HYST-M2-S20", "m2"),
        ("LIVE1430-HYST-M3-S20", "m3"),
        ("LIVE1430-HYST-M4-S20", "m4"),
    ]:
        yi = yearly_table(series[slug]).rename(
            columns=lambda c, p=col: f"{p}_{c}" if c != "year" else c
        )
        y = y.merge(yi, on="year", how="outer")
    y["delta_m3_vs_b45_pp"] = (y["m3_ret"] - y["b45_ret"]) * 100
    y["delta_m3_vs_m2_pp"] = (y["m3_ret"] - y["m2_ret"]) * 100
    y.to_csv(OUT / "yearly.csv", index=False)

    eq = pd.DataFrame({k: (1 + series[k]).cumprod() for k in variants})
    eq.to_csv(OUT / "equity.csv")
    eq.to_csv(OUT / "nav_all.csv")
    for name in variants:
        series[name].to_csv(OUT / f"nav_{name}.csv", header=["r"])

    fig, ax = plt.subplots(figsize=(11, 5.5), dpi=120)
    for name, lw, ls, color in [
        ("LIVE1430-B45-S20", 1.8, "-", "#444444"),
        ("LIVE1430-HYST-M2-S20", 1.4, "--", "#2ca02c"),
        ("LIVE1430-HYST-M3-S20", 2.0, "-", "#1f77b4"),
        ("LIVE1430-HYST-M4-S20", 1.2, ":", "#ff7f0e"),
    ]:
        ax.plot(eq.index, eq[name], label=name, lw=lw, ls=ls, color=color)
    ax.set_yscale("log")
    ax.set_title("SPIKE-S20-HYST-M3-LIVE1430 (hysteresis M=3; explore)")
    ax.set_ylabel("NAV (log)")
    ax.grid(True, alpha=0.3)
    ax.legend(fontsize=8)
    fig.tight_layout()
    fig.savefig(OUT / "equity_curve.png")
    plt.close(fig)

    b45 = df[df.book == "LIVE1430-B45-S20"].iloc[0]
    m2 = df[df.book == "LIVE1430-HYST-M2-S20"].iloc[0]
    m3 = df[df.book == "LIVE1430-HYST-M3-S20"].iloc[0]
    m4 = df[df.book == "LIVE1430-HYST-M4-S20"].iloc[0]

    # Align B45 vs LIVE1430 ref; align M2 vs E24 package
    REF_RET, REF_CAL = 1.3497283467494534, 0.738742964565566
    ref_table = REF1430 / "table.csv"
    if ref_table.exists():
        rt = pd.read_csv(ref_table)
        row = rt[rt.book == "LIVE1430-SHARPE20-max5"]
        if len(row):
            REF_RET = float(row.iloc[0]["ret"])
            REF_CAL = float(row.iloc[0]["Calmar"])
    d_ret_align = abs(float(b45["ret"]) - REF_RET)
    d_cal_align = abs(float(b45["Calmar"]) - REF_CAL)

    E24 = Path("/workspace/strategy-weekly/spike_mom_rank/SPIKE-S20-HYST-M2-LIVE1430")
    E24_M2_RET, E24_M2_CAL = 1.4289998678998805, 0.6607537439835774
    e24_tab = E24 / "table.csv"
    if e24_tab.exists():
        et = pd.read_csv(e24_tab)
        er = et[et.book == "LIVE1430-HYST-M2-S20"]
        if len(er):
            E24_M2_RET = float(er.iloc[0]["ret"])
            E24_M2_CAL = float(er.iloc[0]["Calmar"])
    d_m2_ret = abs(float(m2["ret"]) - E24_M2_RET)
    d_m2_cal = abs(float(m2["Calmar"]) - E24_M2_CAL)

    align_note = (
        f"对齐：B45 |Δret|={d_ret_align:.2e} |ΔCalmar|={d_cal_align:.2e}；"
        f"HYST-M2 vs E24 |Δret|={d_m2_ret:.2e} |ΔCalmar|={d_m2_cal:.2e}。"
        if d_ret_align < 1e-4 and d_m2_ret < 1e-4
        else (
            f"**对齐点名**：B45 ret={pct(float(b45['ret']))} vs ref {pct(REF_RET)}；"
            f"M2 ret={pct(float(m2['ret']))} vs E24 {pct(E24_M2_RET)}。"
        )
    )

    # Primary: M3 vs B45
    dret = (float(m3["ret"]) - float(b45["ret"])) * 100
    ddd_abs = (abs(float(m3["maxDD"])) - abs(float(b45["maxDD"]))) * 100
    ddd_alg = (float(m3["maxDD"]) - float(b45["maxDD"])) * 100
    dcagr = (float(m3["CAGR"]) - float(b45["CAGR"])) * 100
    dcal = float(m3["Calmar"]) - float(b45["Calmar"])
    dto = float(m3["avgTO"]) - float(b45["avgTO"])
    covers = dret >= ddd_abs
    strong_ok = float(m3["2023-26_ret"]) >= float(b45["2023-26_ret"]) * 0.9

    # Side: M3 vs M2
    dret_m2 = (float(m3["ret"]) - float(m2["ret"])) * 100
    ddd_m2 = (abs(float(m3["maxDD"])) - abs(float(m2["maxDD"]))) * 100
    dcal_m2 = float(m3["Calmar"]) - float(m2["Calmar"])
    weak_vs_m2 = (float(m3["ret"]) < float(m2["ret"]) * 0.95) or (
        float(m3["2023-26_ret"]) < float(m2["2023-26_ret"]) * 0.9
    )

    if covers and dret > 0 and strong_ok and not weak_vs_m2:
        verdict = (
            f"**探索记正（不换冠）**：HYST-M3 vs B45 Δret={dret:+.1f}pp，Δ|MDD|={ddd_abs:+.1f}pp（盖住）；"
            f"2023–26 未踏空；vs HYST-M2 Δret={dret_m2:+.1f}pp / ΔCalmar={dcal_m2:+.2f} 不塌。"
        )
    elif covers and dret > 0 and strong_ok and weak_vs_m2:
        verdict = (
            f"**探索偏弱（不换冠）**：HYST-M3 vs B45 盖住（Δret={dret:+.1f}pp）但明显弱于 M2"
            f"（Δret={dret_m2:+.1f}pp）→ 证伪「M3 可作正式滞回档」升格。"
        )
    elif dret > 0 and not covers:
        verdict = (
            f"**探索偏弱（不换冠）**：HYST-M3 Δret={dret:+.1f}pp 未盖住 Δ|MDD|={ddd_abs:+.1f}pp；"
            f"vs M2 Δret={dret_m2:+.1f}pp。"
        )
    elif dret <= 0 or not strong_ok:
        verdict = (
            f"**探索证伪（不换冠）**：HYST-M3 vs B45 Δret={dret:+.1f}pp、Δ|MDD|={ddd_abs:+.1f}pp；"
            f"2023–26={'踏空' if not strong_ok else '未踏空'}；vs M2 Δret={dret_m2:+.1f}pp。"
        )
    else:
        verdict = (
            f"**探索记账（不换冠）**：HYST-M3 vs B45 Δret={dret:+.1f}pp Δ|MDD|={ddd_abs:+.1f}pp；"
            f"vs M2 Δret={dret_m2:+.1f}pp。"
        )
    verdict += (
        f" 旁注 M4：{pct(float(m4['ret']))}/−{abs(float(m4['maxDD']))*100:.1f}%/C{float(m4['Calmar']):.2f}。"
    )

    d3 = diffs["M3_vs_B45"]
    summary = {
        "title": "SPIKE-S20-HYST-M3-LIVE1430 hysteresis keep band Top(5+3)",
        "convention": "Fri≥14:30/close; L≤1; 0.2%RT; B45+S20; hyst rank-kick only",
        "unique_change": "keep held spike if rank≤5+M (M=3); fill empties from Top5 only",
        "batch": "OPT-HYST-M3",
        "sample": f"{EVAL_START} → {END_S}",
        "coverage": cov_stats,
        "pick_diffs": diffs,
        "sim_stats": sim_stats,
        "table": table_rows,
        "delta_m3_vs_b45": {
            "dret_pp": dret,
            "d_abs_mdd_pp": ddd_abs,
            "d_mdd_algebraic_pp": ddd_alg,
            "dcagr_pp": dcagr,
            "dcalmar": dcal,
            "d_avgTO": dto,
            "delta_ret_covers_delta_abs_mdd": covers,
            "strong_2023_26_ok": strong_ok,
        },
        "delta_m3_vs_m2": {
            "dret_pp": dret_m2,
            "d_abs_mdd_pp": ddd_m2,
            "dcalmar": dcal_m2,
            "weak_vs_m2": weak_vs_m2,
        },
        "align_b45_vs_ref": {
            "ref_ret": REF_RET,
            "ref_calmar": REF_CAL,
            "b45_ret": float(b45["ret"]),
            "b45_calmar": float(b45["Calmar"]),
            "abs_dret": d_ret_align,
            "abs_dcal": d_cal_align,
        },
        "align_m2_vs_e24": {
            "e24_m2_ret": E24_M2_RET,
            "e24_m2_calmar": E24_M2_CAL,
            "m2_ret": float(m2["ret"]),
            "m2_calmar": float(m2["Calmar"]),
            "abs_dret": d_m2_ret,
            "abs_dcal": d_m2_cal,
        },
        "align_note": align_note,
        "verdict": verdict,
        "isolation": "strategy_exec / LIVE_OPS / crown: NONE written",
        "elapsed_sec": round(time.time() - t0, 1),
        "overfit_lookahead_cost_notes": [
            "过拟合：M 档离散选美（E24 旁注已见 M3 更强）；本刀单独正式测，不做插值扫档",
            "前视：Sharpe 窗截至信号日前；14:30 信号 / 收盘成交同 LIVE1430",
            "成本：0.2%RT 双边；未计冲击/滑点以外费用",
        ],
    }
    (OUT / "summary.json").write_text(
        json.dumps(summary, ensure_ascii=False, indent=2, default=str), encoding="utf-8"
    )
    (OUT / "criterion.md").write_text(
        Path("/workspace/strategy-weekly/knives/SPIKE-S20-HYST-M3-LIVE1430.md").read_text(
            encoding="utf-8"
        ),
        encoding="utf-8",
    )

    def row_md(name: str) -> str:
        r = df[df.book == name].iloc[0]
        return (
            f"| {name} | {pct(r['ret'])} | {pct(r['maxDD'])} | {pct(r['CAGR'])} | {r['Calmar']:.2f} | "
            f"{pct(r['2020-22_ret'])}/{pct(r['2020-22_DD'])}/{r['2020-22_Calmar']:.2f} | "
            f"{pct(r['2023-26_ret'])}/{pct(r['2023-26_DD'])}/{r['2023-26_Calmar']:.2f} | "
            f"{r['avgL']:.2f} | {r['avgTO']:.3f} | {int(r['n_hyst_exits'])} | {int(r['n_forced_exits'])} |"
        )

    y_lines = [
        "| 年 | B45 | M2 | M3 | ΔM3-B45 | M4 |",
        "|---|---:|---:|---:|---:|---:|",
    ]
    for _, row in y.iterrows():
        y_lines.append(
            f"| {int(row.year)} | {pct(float(row.b45_ret)) if pd.notna(row.b45_ret) else '—'} | "
            f"{pct(float(row.m2_ret)) if pd.notna(row.m2_ret) else '—'} | "
            f"{pct(float(row.m3_ret)) if pd.notna(row.m3_ret) else '—'} | "
            f"{float(row.delta_m3_vs_b45_pp):+.1f} | "
            f"{pct(float(row.m4_ret)) if pd.notna(row.m4_ret) else '—'} |"
        )

    approx_md = "\n".join(f"- {a}" for a in cov_stats["approximation"])
    report = f"""# REPORT · SPIKE-S20-HYST-M3-LIVE1430（滞回 M=3：Top8 不踢；新进仍 Top5）

## 准则原文

- 编号：SPIKE-S20-HYST-M3-LIVE1430 / 2026-10-21 / OPT-HYST-M3（Michael）
- **唯一改动**：相对 E24 / B45+S20，滞回月数 **M=2→M=3**（已持仓 rank>5+3=8 才踢；空席只从 Top5 填）。
- **冻结**：B45+S20；Fri≥14:30/收盘/0.2%RT/L≤1；不做 M 插值扫档；不换冠；不碰实盘。

## 实现要点

- 只读复用 E24 `SPIKE-S20-HYST-M2-LIVE1430/run.py` 引擎；同逻辑改 M=3 为主刀。
- 每周 L = spike_ft 按 SHARPE20 降序；1-based rank。
- 风控强制卖出后：若持仓仍在 L 且 rank>5+M → `hyst_rank` 踢出。
- 空席从 L 的 Top5 未持有者依次填入至满 5；**不新开** rank 6..5+M。
- 主表：B45 / HYST-M2（对照）/ HYST-M3（主）/ HYST-M4（旁注）。

{align_note}

## 近似与覆盖

{approx_md}

| 覆盖 | 值 |
|---|---|
| 日历周 | {len(calendar)} |
| M3 vs B45 持仓差异周 | {d3['n_diff']}/{d3['n']} ({100*(d3['pct_diff'] or 0):.0f}%) |

## 主表

| book | ret | maxDD | CAGR | Calmar | 2020–22 | 2023–26 | avgL | avgTO | hyst_x | forced_x |
|---|---:|---:|---:|---:|---|---|---:|---:|---:|---:|
{row_md("LIVE1430-B45-S20")}
{row_md("LIVE1430-HYST-M2-S20")}
{row_md("LIVE1430-HYST-M3-S20")}
{row_md("LIVE1430-HYST-M4-S20")}

## Δ · HYST-M3 vs B45（主对照）

| | |
|---|---|
| Δ总收益 | {dret:+.1f}pp |
| Δ|MDD|（正=更深） | {ddd_abs:+.1f}pp |
| ΔMDD 代数差（正=更浅） | {ddd_alg:+.1f}pp |
| ΔCAGR | {dcagr:+.2f}pp |
| ΔCalmar | {dcal:+.2f} |
| ΔavgTO | {dto:+.3f} |
| Δ收益盖住 Δ|MDD| | {"是" if covers else "否"} |
| 2023–26 不差 | {"是" if strong_ok else "否"} |

## Δ · HYST-M3 vs HYST-M2（旁注）

| | |
|---|---|
| Δ总收益 | {dret_m2:+.1f}pp |
| Δ|MDD| | {ddd_m2:+.1f}pp |
| ΔCalmar | {dcal_m2:+.2f} |
| 明显弱于 M2 | {"是" if weak_vs_m2 else "否"} |

## 分段

| 段 | B45 | M2 | M3 |
|---|---|---|---|
| 2020–22 | {pct(float(b45['2020-22_ret']))} / {pct(float(b45['2020-22_DD']))} / {float(b45['2020-22_Calmar']):.2f} | {pct(float(m2['2020-22_ret']))} / {pct(float(m2['2020-22_DD']))} / {float(m2['2020-22_Calmar']):.2f} | {pct(float(m3['2020-22_ret']))} / {pct(float(m3['2020-22_DD']))} / {float(m3['2020-22_Calmar']):.2f} |
| 2023–26 | {pct(float(b45['2023-26_ret']))} / {pct(float(b45['2023-26_DD']))} / {float(b45['2023-26_Calmar']):.2f} | {pct(float(m2['2023-26_ret']))} / {pct(float(m2['2023-26_DD']))} / {float(m2['2023-26_Calmar']):.2f} | {pct(float(m3['2023-26_ret']))} / {pct(float(m3['2023-26_DD']))} / {float(m3['2023-26_Calmar']):.2f} |

## 历年

{chr(10).join(y_lines)}

## 过拟合 / 前视 / 成本

- 过拟合：M 档离散选美（E24 旁注已见 M3）；本刀正式单测，不做插值扫档。
- 前视：Sharpe 窗截至信号日前；14:30 信号 / 收盘成交。
- 成本：0.2%RT；未计冲击/滑点以外费用。

## 一句证伪 / 失效条件

- vs B45 未盖住 / 2023–26 踏空 / 明显弱于 M2 → 证伪「M3 可作正式滞回档」。
- 仅 M=3 尖峰、M4 翻盘 → 带宽选美，不升格。

## 结论（不换冠）

{verdict}

## 产物

`run.py` / `criterion.md` / `REPORT.md` / `summary.json` / `table.csv` / `metrics.csv` / `nav_*.csv` / `equity.csv` / `equity_curve.png` / `holdings_*`

耗时约 {summary['elapsed_sec']}s。
"""
    (OUT / "REPORT.md").write_text(report, encoding="utf-8")
    print("done", OUT, flush=True)
    print(align_note, flush=True)
    print(verdict, flush=True)


if __name__ == "__main__":
    main()
