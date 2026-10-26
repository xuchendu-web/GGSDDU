"""COST-TURNOVER-JOINT-B45: B45+S20 face; joint RT × λ sensitivity.

Books: RT ∈ {0.10%,0.15%,0.20%,0.30%} × λ ∈ {0,0.15} (score=sharpe20−λ×to_norm).
  Control: RT=0.20%, λ=0 plain face. Fri≥14:30/close; L≤1; CLOUD-BATCH research_cache.

Exploration — no crown swap. Does NOT write strategy_exec / LIVE_OPS.
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

OUT = Path(__file__).resolve().parent
CACHE = KIT / "data" / "research_cache"
UNI_CSV = KIT / "data" / "universe_replace_only_436.csv"
WEEK = CACHE / "week"
FACE = CACHE / "holdings_ro2_extended.csv"
DAY_DIR = CACHE / "day"
TEMA_PX = KIT / "data" / "tema_prices"  # optional; day/ covers extended window
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
RT_GRID = [0.001, 0.0015, 0.002, 0.003]  # round-trip
LAMBDA_GRID = [0.0, 0.15]
CONTROL_RT = 0.002
CONTROL_LAM = 0.0


@dataclass
class Cand:
    code: str
    px: float
    fz: float | None
    aum: float
    sharpe: float | None
    turnover_4w: float = 0.0
    score: float | None = None


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


def trailing_4w_turnover(
    code: str,
    signal_fri: str,
    calendar: list[str],
    aum_billion: float,
    vol_fri: dict[str, float],
    px_fri: dict[str, float],
) -> float:
    """Mean Fri 14:30 turnover_rate over the 4 calendar Fridays strictly before signal_fri."""
    if aum_billion <= 0:
        return 0.0
    aum_yuan = aum_billion * 1e8
    try:
        idx = calendar.index(signal_fri)
    except ValueError:
        return 0.0
    prior = calendar[max(0, idx - 4) : idx]
    rates: list[float] = []
    for fd in prior:
        vol = vol_fri.get(fd)
        px = px_fri.get(fd)
        if vol is None or px is None or vol <= 0 or px <= 0:
            continue
        rates.append(float(vol) * float(px) / aum_yuan)
    return float(np.mean(rates)) if rates else 0.0


def turnover_norm_in_pool(c: Cand, pool: list[Cand]) -> float:
    """Min-max normalize trailing_4w_turnover within sharpe-eligible spike pool (0–1)."""
    elig = [x for x in pool if x.sharpe is not None]
    if not elig:
        return 0.0
    vals = [x.turnover_4w for x in elig]
    lo, hi = min(vals), max(vals)
    if hi <= lo:
        return 0.0
    return (c.turnover_4w - lo) / (hi - lo)


def make_sharpe_turnover_rank(lam: float) -> RankFn:
    def rank_key(c: Cand, pool: list[Cand]) -> tuple:
        if c.sharpe is None:
            return (1, 0.0, c.code)
        if lam <= 0:
            sc = c.sharpe
        else:
            sc = c.sharpe - lam * turnover_norm_in_pool(c, pool)
        return (0, -sc, c.code)

    return rank_key


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
                    s = px.combine_first(s).sort_index()
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
    vol_fri_by_code: dict[str, dict[str, float]],
    risk_on_by_fri: dict[str, bool],
    rank_fn: RankFn,
    variant: str,
    require_sharpe: bool,
    sharpe_n: int | None,
    max_pos: int,
    penalty_lambda: float,
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
            vf = vol_fri_by_code.get(code) or {}
            px_map = closes_w.get(code) or {}
            to4 = trailing_4w_turnover(
                code, d, calendar, aum.get(code) or 0.0, vf, px_map
            )
            out.append(
                Cand(
                    code=code,
                    px=px,
                    fz=float(fz) if fz is not None else None,
                    aum=aum.get(code) or 0.0,
                    sharpe=sh,
                    turnover_4w=to4,
                    score=sh,
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
                    to_n = turnover_norm_in_pool(c, pool_rank) if penalty_lambda > 0 else 0.0
                    sc = (
                        (c.sharpe - penalty_lambda * to_n)
                        if c.sharpe is not None
                        else None
                    )
                    rank_rows.append(
                        {
                            "date": d,
                            "variant": variant,
                            "code": c.code,
                            "aum": c.aum,
                            "sharpe": c.sharpe,
                            "turnover_4w": c.turnover_4w,
                            "turnover_norm": to_n,
                            "penalty_lambda": penalty_lambda,
                            "score": sc,
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
    }
    if rank_rows:
        pd.DataFrame(rank_rows).to_csv(OUT / f"entries_{variant}.csv", index=False)
    return trades, hold, stats


def run_live_tv(
    hold: dict[pd.Timestamp, list[str]],
    days: pd.DatetimeIndex,
    px: pd.DataFrame,
    R: pd.DataFrame,
    sigma_star: float = SIGMA_STAR,
    live_cost_rt: float = LIVE_COST_RT,
) -> tuple[pd.Series, pd.Series, float]:
    """Returns daily net ret, L series, and average one-way turnover per rebalance.
    L = min(LCAP, sigma_star / max(σ20,σ60)); unique knife knob is sigma_star.
    """
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
            cst.loc[d] = to * live_cost_rt / 2
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
    for p in (SCRIPTS, UNI_CSV, WEEK, FACE, DAY_DIR, NOON_CSV, SINA_DAILY, SNAP_CACHE):
        if not Path(p).exists():
            raise SystemExit(f"missing kit path {p}")
    print("load universe + extended 14:30 + week…", flush=True)
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
    vol_fri_by_code: dict[str, dict[str, float]] = defaultdict(dict)
    for r in noon.itertuples():
        td = r.trade_date
        if td < EVAL_START or td > END_S or r.status != "ok":
            continue
        v = getattr(r, "vol_1430", None)
        if v is None or (isinstance(v, float) and math.isnan(v)) or float(v) <= 0:
            continue
        vol_fri_by_code[r.code][td] = float(v)
    print(
        f"mapped qfq_1430={n_map} skip_no_bfq={n_skip} empty_block_rows={n_empty} "
        f"vol_fri_codes={sum(1 for c in vol_fri_by_code if vol_fri_by_code[c])}",
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
        "sample_note": f"CLOUD-BATCH 延窗研究：{EVAL_START}→{END_S}（14:30 至 2026-10-23）",
        "approximation": [
            "延窗：research_cache week/day/face/14:30；≤2026-10-09 沿用 face；其后研究周线 MA20 宽度",
            "qfq_1430 = price_1430 × (day qfq 收 / sina daily 收)；sina 作 bfq 代理",
            "冲击分类：周线收盘替换为 qfq_1430 后因果 classify（Fri≥14:30 信号）",
            "Sharpe 窗截至信号日严格前一交易日",
            "成交：周五收盘填仓 + TV25；RT 网格缩放换手扣费；L≤1",
            "填席：score=sharpe20−λ×to_norm；to_norm=池内min-max(trailing_4w_turnover)",
            "trailing_4w_turnover=mean_Fri(vol_1430×px_1430)/(aum_亿×1e8) 信号日前4周五",
            "冻结 B45+spike_ft max5+S20+E0+TV25；**联合 RT×λ**",
            "只读 kit `data/cache_1430_snaps.json`；不写 strategy_exec / LIVE_OPS",
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

    def lam_tag(lam: float) -> str:
        return f"LAM{int(round(lam * 100)):02d}"

    def rt_tag(rt: float) -> str:
        return f"RT{int(round(rt * 10000))}"

    def book_name(rt: float, lam: float) -> str:
        return f"LIVE1430-B45-S20-{rt_tag(rt)}-{lam_tag(lam)}"

    lam_paths: list[tuple[float, str]] = [(lam, lam_tag(lam)) for lam in LAMBDA_GRID]
    book_defs: list[tuple[str, float, float, str]] = []
    for rt in RT_GRID:
        for lam in LAMBDA_GRID:
            role = "control" if rt == CONTROL_RT and lam == CONTROL_LAM else "grid"
            book_defs.append((book_name(rt, lam), rt, lam, role))
    variants = [name for name, _, _, _ in book_defs]
    rt_of = {name: rt for name, rt, _, _ in book_defs}
    lam_of = {name: lam for name, _, lam, _ in book_defs}

    hold_by_lam: dict[float, dict[str, list[str]]] = {}
    sim_stats_lam: dict[float, Any] = {}
    for lam, ltag in lam_paths:
        variant = f"LIVE1430-B45-S20-{ltag}"
        rfn = make_sharpe_turnover_rank(lam) if lam > 0 else sharpe_key
        print(f"simulate B45+S20 max5 λ={lam} (holdings path)…", flush=True)
        trades, hold, st = simulate(
            calendar,
            snaps,
            closes_w_sig,
            alias,
            aum,
            daily,
            vol_fri_by_code,
            risk_on_by_fri,
            rfn,
            variant,
            True,
            20,
            5,
            lam,
        )
        n_cash = sum(1 for d in calendar[:-1] if not (hold.get(d) or []))
        st = {**st, "n_cash_weeks": n_cash, "penalty_lambda": lam}
        hold_by_lam[lam] = hold
        sim_stats_lam[lam] = st
        rows = []
        for d in calendar[:-1]:
            codes_h = hold.get(d) or []
            rows.append(
                {
                    "date": d,
                    "risk_on": int(risk_on_by_fri.get(d, False)),
                    "n_held": len(codes_h),
                    "codes": ",".join(codes_h),
                    "penalty_lambda": lam,
                }
            )
        pd.DataFrame(rows).to_csv(OUT / f"holdings_LAM{ltag}.csv", index=False)
        pd.DataFrame(trades).to_csv(OUT / f"trades_LAM{ltag}.csv", index=False)
        print(
            f"  λ={lam}: entries={st['n_entries']} trades={st['n_trades']} "
            f"tight={st['n_fridays_queue_gt_seats']} cash={n_cash}",
            flush=True,
        )

    def pick_diff_h(a: dict[str, list[str]], b: dict[str, list[str]]) -> dict[str, Any]:
        n = n_diff = 0
        for d, ca in a.items():
            cb = b.get(d) or []
            if not ca and not cb:
                continue
            n += 1
            if set(ca) != set(cb):
                n_diff += 1
        return {"n": n, "n_diff": n_diff, "pct_diff": n_diff / n if n else None}

    diffs = {
        "LAM15_vs_LAM00": pick_diff_h(hold_by_lam[0.0], hold_by_lam[0.15]),
    }
    print(f"hold diffs λ=0.15 vs λ=0: {diffs}", flush=True)

    control_name = book_name(CONTROL_RT, CONTROL_LAM)
    base_name = control_name

    all_codes: set[str] = set()
    for h in hold_by_lam.values():
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
    actual_end = calendar[-1]
    if len(days) and str(days[-1].date()) < actual_end:
        all_idx = None
        for s in daily.values():
            all_idx = s.index if all_idx is None else all_idx.union(s.index)
        if all_idx is not None:
            days2 = all_idx[(all_idx >= EVAL_START) & (all_idx <= END_S)]
            if len(days2) > len(days):
                days = days2
    print(f"live days {days[0].date()} → {days[-1].date()} n={len(days)}", flush=True)

    table_rows = []
    series: dict[str, pd.Series] = {}
    Ls_map: dict[str, pd.Series] = {}
    occ_map: dict[str, dict[str, Any]] = {}
    to_map: dict[str, float] = {}
    for name, rt, lam, role in book_defs:
        hd = {pd.Timestamp(d): cs for d, cs in hold_by_lam[lam].items()}
        r, L, avg_to = run_live_tv(hd, days, px, R, sigma_star=SIGMA_STAR, live_cost_rt=rt)
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
            "rt_cost": rt,
            "penalty_lambda": lam,
            "role": role,
            "sigma_star": SIGMA_STAR,
            "tv": "TV25",
            **st,
            "2020-22_ret": st2022["ret"],
            "2020-22_DD": st2022["maxDD"],
            "2020-22_Calmar": st2022["Calmar"],
            "2023-26_ret": st2023["ret"],
            "2023-26_DD": st2023["maxDD"],
            "2023-26_Calmar": st2023["Calmar"],
            "avgL": float(L[L > 0].mean()) if (L > 0).any() else 0.0,
            "avg_turnover_1way": avg_to,
            "avg_turnover": avg_to,
            "occ_n": occ["n_occ_weeks"],
            "occ_winrate": occ["winrate"],
            "occ_payoff": occ["payoff"],
            "occ_avg_win": occ["avg_win"],
            "occ_avg_loss": occ["avg_loss"],
            "n_cash_weeks": sim_stats_lam[lam]["n_cash_weeks"],
        }
        table_rows.append(row)
        print(
            f"  {name} RT={100*rt:.2f}% λ={lam}: ret={pct(st['ret'])} dd={pct(st['maxDD'])} "
            f"CAGR={pct(st['CAGR'])} Calmar={st['Calmar']:.2f} avgL={row['avgL']:.3f} "
            f"to1w={avg_to:.3f}",
            flush=True,
        )

    df = pd.DataFrame(table_rows)
    df.to_csv(OUT / "table.csv", index=False)
    df.to_csv(OUT / "metrics.csv", index=False)

    y = yearly_table(series[base_name]).rename(
        columns=lambda c: f"lam00_{c}" if c != "year" else c
    )
    for name in variants:
        if name == base_name:
            continue
        slug = name.replace("LIVE1430-B45-S20-", "").lower()
        yi = yearly_table(series[name]).rename(
            columns=lambda c, p=slug: f"{p}_{c}" if c != "year" else c
        )
        y = y.merge(yi, on="year", how="outer")
    y.to_csv(OUT / "yearly.csv", index=False)

    eq = pd.DataFrame({k: (1 + series[k]).cumprod() for k in variants})
    eq.to_csv(OUT / "equity.csv")
    eq.to_csv(OUT / "nav_all.csv")
    for name in variants:
        series[name].to_csv(OUT / f"nav_{name}.csv", header=["r"])

    fig, ax = plt.subplots(figsize=(12, 6), dpi=120)
    for lam in LAMBDA_GRID:
        for rt in RT_GRID:
            name = book_name(rt, lam)
            if name not in eq.columns:
                continue
            lw = 2.0 if name == control_name else 0.9
            ls = "-" if lam == 0 else "--"
            ax.plot(eq.index, eq[name], label=f"RT{int(rt*10000)} λ={lam}", lw=lw, ls=ls, alpha=0.85)
    ax.set_yscale("log")
    ax.set_title("COST-TURNOVER-JOINT-B45（RT×λ 联合 · B45+S20）")
    ax.set_ylabel("净值（对数）")
    ax.grid(True, alpha=0.3)
    ax.legend(fontsize=6, ncol=2, loc="upper left")
    fig.tight_layout()
    fig.savefig(OUT / "equity_curve.png")
    plt.close(fig)

    base = df[df.book == control_name].iloc[0]
    by_book = {r.book: r for _, r in df.iterrows()}

    def delta_vs_control(name: str) -> dict[str, float]:
        r = by_book[name]
        dret = (float(r["ret"]) - float(base["ret"])) * 100
        ddd_abs = (abs(float(r["maxDD"])) - abs(float(base["maxDD"]))) * 100
        dcal = float(r["Calmar"]) - float(base["Calmar"])
        return {
            "dret_pp": dret,
            "d_abs_mdd_pp": ddd_abs,
            "d_calmar": dcal,
            "covers": dret >= ddd_abs,
            "wins_calmar": float(r["Calmar"]) > float(base["Calmar"]),
            "upgrade_candidate": float(r["Calmar"]) > float(base["Calmar"]) and dret >= ddd_abs,
        }

    grid_delta = {n: delta_vs_control(n) for n in variants if n != control_name}
    upgrade_cells = [n for n, d in grid_delta.items() if d["upgrade_candidate"]]
    low_rt_light_lam = [
        book_name(rt, 0.15) for rt in RT_GRID if rt <= 0.0015
    ]
    h1_candidates = [
        n for n in low_rt_light_lam if grid_delta.get(n, {}).get("upgrade_candidate")
    ]

    pivot_calmar: list[dict[str, Any]] = []
    pivot_ret: list[dict[str, Any]] = []
    for rt in RT_GRID:
        row_c: dict[str, Any] = {"rt_pct": 100 * rt}
        row_r: dict[str, Any] = {"rt_pct": 100 * rt}
        for lam in LAMBDA_GRID:
            nm = book_name(rt, lam)
            row_c[f"lam_{lam}"] = float(by_book[nm]["Calmar"])
            row_r[f"lam_{lam}"] = float(by_book[nm]["ret"])
        pivot_calmar.append(row_c)
        pivot_ret.append(row_r)

    lam0_cals = [float(by_book[book_name(rt, 0.0)]["Calmar"]) for rt in RT_GRID]
    lam15_cals = [float(by_book[book_name(rt, 0.15)]["Calmar"]) for rt in RT_GRID]
    lam15_wins = [c15 > c0 for c0, c15 in zip(lam0_cals, lam15_cals)]
    ctrl_i = RT_GRID.index(CONTROL_RT)
    cal_lam0_rt15 = lam0_cals[RT_GRID.index(0.0015)]
    cal_lam0_rt20 = lam0_cals[ctrl_i]
    ret_lam0 = {rt: float(by_book[book_name(rt, 0.0)]["ret"]) for rt in RT_GRID}
    ret_cross_015 = ret_lam0[0.0015] > ret_lam0[CONTROL_RT] and cal_lam0_rt15 > cal_lam0_rt20

    if h1_candidates:
        verdict = (
            f"**H1 未成立（记账，不换冠）**：「低成本+轻惩罚」格 {', '.join(h1_candidates)} "
            f"相对 RT20-λ0 同时 Calmar 更优且 Δret 盖住 Δ|MDD|；"
            f"但属敏感面探索，**不记正升格、不换冠**。"
        )
    else:
        verdict = (
            f"**H1 成立（仅记账，不换冠）**：RT≤0.15% 且 λ=0.15 无格相对 RT20-λ0 达升格尺子。"
            f" λ=0.15 Calmar 胜 λ=0：{sum(lam15_wins)}/{len(RT_GRID)} 档；"
            f"λ=0 在 RT 0.15% vs 0.20%：Calmar {cal_lam0_rt15:.2f} vs {cal_lam0_rt20:.2f}（{'低成本更优' if ret_cross_015 else '未翻转'}）。"
        )

    knife_md = (KIT / "knives" / "COST-TURNOVER-JOINT-B45.md").read_text(encoding="utf-8")

    joint_table_csv = OUT / "joint_pivot_calmar.csv"
    pd.DataFrame(pivot_calmar).to_csv(joint_table_csv, index=False)

    summary = {
        "title": "COST-TURNOVER-JOINT-B45",
        "batch": "CLOUD-COST-TURNOVER-JOINT",
        "convention": "Fri≥14:30 / close; L≤1; TV25; B45+S20 max5+E0",
        "unique_change": "joint RT×λ grid; turnover penalty reused from SPIKE-S20-TURNOVER-PENALTY",
        "control": {"rt": CONTROL_RT, "lambda": CONTROL_LAM, "book": control_name},
        "sample": f"{EVAL_START} → {actual_end}",
        "rt_grid": RT_GRID,
        "lambda_grid": LAMBDA_GRID,
        "n_calendar_weeks": len(calendar),
        "coverage": cov_stats,
        "hold_diffs": diffs,
        "table": table_rows,
        "pivot_calmar": pivot_calmar,
        "pivot_ret": pivot_ret,
        "grid_delta_vs_control": grid_delta,
        "upgrade_candidates": upgrade_cells,
        "h1_low_rt_light_lam_upgrade": h1_candidates,
        "lam15_calmar_wins_vs_lam0_by_rt": lam15_wins,
        "lam0_calmar_rt15_vs_rt20": {"rt15": cal_lam0_rt15, "rt20": cal_lam0_rt20},
        "verdict": verdict,
        "hypothesis_h1": "no stable low-RT+light-lambda upgrade vs control",
        "isolation": "strategy_exec / LIVE_OPS: NONE",
        "elapsed_sec": round(time.time() - t0, 1),
    }
    (OUT / "summary.json").write_text(
        json.dumps(summary, ensure_ascii=False, indent=2, default=str), encoding="utf-8"
    )

    (OUT / "criterion.md").write_text(knife_md + "\n", encoding="utf-8")

    def row_md(name: str) -> str:
        r = df[df.book == name].iloc[0]
        lam = float(r["penalty_lambda"])
        tag = " **对照**" if name == control_name else ""
        return (
            f"| {name}{tag} | {100*r['rt_cost']:.2f}% | {lam:.2f} | {pct(r['ret'])} | {pct(r['maxDD'])} | "
            f"{pct(r['CAGR'])} | {r['Calmar']:.2f} | "
            f"{pct(r['2020-22_ret'])}/{pct(r['2020-22_DD'])}/{r['2020-22_Calmar']:.2f} | "
            f"{pct(r['2023-26_ret'])}/{pct(r['2023-26_DD'])}/{r['2023-26_Calmar']:.2f} | "
            f"{r['avgL']:.2f} | {r['avg_turnover']:.3f} | {int(r['n_cash_weeks'])} |"
        )

    delta_lines = [
        "| book | RT | λ | Δret | Δ|MDD| | ΔCalmar | 升格? |",
        "|---|---:|---:|---:|---:|---:|---|",
    ]
    for name, rt, lam, _ in book_defs:
        if name == control_name:
            continue
        d = grid_delta[name]
        delta_lines.append(
            f"| {name} | {100*rt:.2f}% | {lam:.2f} | {d['dret_pp']:+.1f}pp | {d['d_abs_mdd_pp']:+.1f}pp | "
            f"{d['d_calmar']:+.2f} | {'是' if d['upgrade_candidate'] else '否'} |"
        )

    pivot_lines = [
        "| RT | λ=0 Calmar | λ=0.15 Calmar | λ=0 ret | λ=0.15 ret | λ15胜Calmar |",
        "|---:|---:|---:|---:|---:|---|",
    ]
    for i, rt in enumerate(RT_GRID):
        pivot_lines.append(
            f"| {100*rt:.2f}% | {lam0_cals[i]:.2f} | {lam15_cals[i]:.2f} | "
            f"{pct(pivot_ret[i]['lam_0.0'])} | {pct(pivot_ret[i]['lam_0.15'])} | "
            f"{'是' if lam15_wins[i] else '否'} |"
        )

    table_body = "\n".join(row_md(n) for n, _, _, _ in book_defs)
    approx_md = "\n".join(f"- {a}" for a in cov_stats["approximation"])
    d_hold15 = diffs.get("LAM15_vs_LAM00", {"n_diff": 0, "n": 0, "pct_diff": 0})

    report = f"""# REPORT · COST-TURNOVER-JOINT-B45（成本×换手联合敏感）

## 1. 准则原文

```
{knife_md.strip()}
```

## 2. 实现要点

- **联合改动**：RT ∈ {{0.10%, 0.15%, 0.20%, 0.30%}} × λ ∈ {{0, 0.15}}；持仓路径仅随 λ 变化，成本仅缩放 `run_live_tv` 换手 RT。
- **换手惩罚**：复用 turnover-penalty 刀 `score = sharpe20 − λ × to_norm`（非额外费率）。
- **对照**：**RT=0.20%、λ=0**（标准 B45+S20 plain face）。
- **冻结**：B45 + spike_ft max5 + E0 + **TV25** + SHARPE20；Fri≥14:30 / 收盘；**L≤1**。
- **延窗**：CLOUD-BATCH `research_cache`，日历至 **{actual_end}**（≥2026-10-23）。
- **隔离**：研究池；不写 strategy_exec / LIVE_OPS / 实盘。

## 近似与覆盖

{approx_md}

| 覆盖 | 值 |
|---|---|
| 可投池（AUM≥2亿） | {len(codes)} |
| 日历周 | {len(calendar)}（{calendar[0]}→{actual_end}） |
| listed 行 14:30 非空率 | {100*nonnull_rate:.1f}% |
| 成功映射 qfq_1430 | {n_map} |
| 持仓差异周 λ=0.15 vs λ=0 | {d_hold15['n_diff']}/{d_hold15['n']} |

## 3. 联合主表（八账 · NAV）

| book | RT | λ | ret | maxDD | CAGR | Calmar | 2020–22 ret/DD/C | 2023–26 ret/DD/C | avgL | avgTO | 空仓周 |
|---|---:|---:|---:|---:|---:|---:|---|---|---:|---:|---:|
{table_body}

### RT 透视（联合 · 非单维重复）

{chr(10).join(pivot_lines)}

### Δ vs 对照（RT20-λ0）

{chr(10).join(delta_lines)}

### 分段 · 对照 RT20-λ0

| 段 | ret | maxDD | Calmar |
|---|---:|---:|---:|
| 2020–22 | {pct(float(base['2020-22_ret']))} | {pct(float(base['2020-22_DD']))} | {float(base['2020-22_Calmar']):.2f} |
| 2023–26 | {pct(float(base['2023-26_ret']))} | {pct(float(base['2023-26_DD']))} | {float(base['2023-26_Calmar']):.2f} |

## 4. 一句结论（H1 · 探索记账，不换冠）

{verdict}

## 产物

- `run.py` / `criterion.md` / `REPORT.md` / `summary.json`
- `table.csv` / `joint_pivot_calmar.csv` / `metrics.csv` / `yearly.csv` / `equity.csv` / `nav_*.csv` / `equity_curve.png`

耗时约 {summary['elapsed_sec']}s。
"""
    (OUT / "REPORT.md").write_text(report, encoding="utf-8")
    print("done", OUT, flush=True)
    print(verdict, flush=True)


if __name__ == "__main__":
    main()
