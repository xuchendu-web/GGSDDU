"""SPIKE-S20-EXIT-CROSS-PT15-COOL6-LIVE1430: face + PT15 × COOL−6 cross (Composer research).

Frozen face: breadth≥45% + spike_ft max5 + E0 + TV25 + SHARPE20; Fri≥14:30/close; 0.2%RT; L≤1; research pool.
Unique: BOTH profit-take +15% AND loss-cool (prior-week port ret ≤−6% → cash).
Attribution: PT-only, COOL-only, 2×2; neighbors PT10/20 & COOL−4/−8 side table.
Does NOT write strategy_exec / LIVE_OPS / champion.
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
    risk_on_by_fri: dict[str, bool],
    rank_fn: RankFn,
    variant: str,
    require_sharpe: bool,
    sharpe_n: int | None,
    max_pos: int,
    profit_take_pct: float | None = None,
) -> tuple[list[dict[str, Any]], dict[str, list[str]], dict[str, Any]]:
    cash = 1.0
    positions: dict[str, Position] = {}
    trades: list[dict[str, Any]] = []
    picks: dict[str, list[str]] = {}
    n_tight = 0
    n_feat = 0
    n_entries = 0
    n_miss_sharpe = 0
    n_profit_take = 0
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
            if profit_take_pct is not None and p.entry_px > 0:
                unr = px / p.entry_px - 1.0
                if unr >= profit_take_pct:
                    reason = "profit_take"
            sn = snap_at(code, d)
            if reason is None and sn:
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
            if reason == "profit_take":
                n_profit_take += 1
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

    stats = {
        "n_fridays_queue_gt_seats": n_tight,
        "n_fridays_with_cands": n_feat,
        "n_entries": n_entries,
        "n_entries_missing_sharpe": n_miss_sharpe,
        "n_trades": len(trades),
        "n_profit_take_exits": n_profit_take,
        "profit_take_pct": profit_take_pct,
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




def baseline_week_returns(
    r: pd.Series, calendar: list[str]
) -> dict[str, float]:
    """Portfolio week return ending on each signal Friday (Fri→Fri)."""
    reb = calendar[:-1]
    out: dict[str, float] = {}
    for i, d in enumerate(reb):
        if i == 0:
            continue
        prev = reb[i - 1]
        ts_d, ts_prev = pd.Timestamp(d), pd.Timestamp(prev)
        seg = r[(r.index > ts_prev) & (r.index <= ts_d)]
        if len(seg) == 0:
            continue
        out[d] = float((1 + seg).prod() - 1)
    return out


def apply_loss_cool_overlay(
    baseline_hold: dict[str, list[str]],
    calendar: list[str],
    week_ret_end: dict[str, float],
    threshold: float,
) -> tuple[dict[str, list[str]], int, list[dict[str, Any]]]:
    """Force empty holdings on signal Friday when week ending that day ≤ threshold."""
    reb = calendar[:-1]
    cooled: dict[str, list[str]] = {}
    triggers: list[dict[str, Any]] = []
    n_cool = 0
    for i, d in enumerate(reb):
        wr = week_ret_end.get(d)
        if i > 0 and wr is not None and wr <= threshold:
            cooled[d] = []
            n_cool += 1
            triggers.append({"date": d, "week_ret_pp": wr * 100, "threshold_pp": threshold * 100})
        else:
            cooled[d] = list(baseline_hold.get(d) or [])
    cooled[calendar[-1]] = []
    return cooled, n_cool, triggers


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

    print("load daily qfq + sina for 14:30 map…", flush=True)
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

    listed = noon[noon["status"] != "not_listed"]
    listed = listed[(listed.trade_date >= EVAL_START) & (listed.trade_date <= END_S)]
    nonnull_rate = float(listed["price_1130"].notna().mean()) if len(listed) else 0.0
    cov_stats = {
        "px_1430_csv": str(NOON_CSV),
        "n_codes_aum2": len(codes),
        "n_calendar_weeks": len(calendar),
        "listed_1430_nonnull_rate": nonnull_rate,
        "n_qfq_1430_mapped": n_map,
        "snap_cache_used": str(SNAP_CACHE),
        "sample_note": f"CLOUD-BATCH 延窗：{EVAL_START}→{END_S}",
        "approximation": [
            "研究池 research_cache；breadth≥45% face risk_on",
            "Fri≥14:30 信号 / 收盘成交；TV25；0.2%RT；L≤1",
            "止盈：周评未实现≥阈值相对 entry_px 强制退出（simulate 内）",
            "冷静：上周组合周收益≤阈值则本周信号日强制空仓（overlay）；触发周收益取自同路径无冷静 NAV",
            "不写 strategy_exec / LIVE_OPS / champion",
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

    cached = json.loads(SNAP_CACHE.read_text(encoding="utf-8"))
    snaps = {c: snap_index((cached.get("by_code") or {}).get(c) or []) for c in codes}

    SIGMA_FIXED = 0.25
    COOL_PRIMARY = -0.06
    PT_PRIMARY = 0.15

    sim_raw: dict[str, dict[str, list[str]]] = {}
    sim_stats: dict[str, Any] = {}

    def sim_book(name: str, pt: float | None) -> dict[str, list[str]]:
        trades, hold, st = simulate(
            calendar,
            snaps,
            closes_w_sig,
            alias,
            aum,
            daily,
            risk_on_by_fri,
            sharpe_key,
            name,
            True,
            20,
            5,
            profit_take_pct=pt,
        )
        sim_raw[name] = hold
        sim_stats[name] = {**st, "profit_take_pct": pt}
        pd.DataFrame(trades).to_csv(OUT / f"trades_{name}.csv", index=False)
        return hold

    print("simulate face (no PT)…", flush=True)
    hold_face = sim_book("RAW-FACE", None)
    print("simulate PT15 path…", flush=True)
    hold_pt15 = sim_book("RAW-PT15", PT_PRIMARY)

    all_codes: set[str] = set()
    for h in (hold_face, hold_pt15):
        for cs in h.values():
            all_codes |= set(cs)
    px_map = {c: daily[c] for c in sorted(all_codes) if c in daily}
    px = pd.DataFrame(px_map).sort_index()
    px = px.loc[(px.index >= EVAL_START) & (px.index <= END_S)]
    R = px.pct_change()
    days = px["510300"].dropna().index if "510300" in px.columns else px.dropna(how="all").index
    days = days[(days >= EVAL_START) & (days <= END_S)]
    actual_end = calendar[-1]

    def nav_from_hold(hold: dict[str, list[str]]) -> pd.Series:
        hd = {pd.Timestamp(d): cs for d, cs in hold.items()}
        r, _, _ = run_live_tv(hd, days, px, R, sigma_star=SIGMA_FIXED)
        return r

    r_face = nav_from_hold(hold_face)
    r_pt15 = nav_from_hold(hold_pt15)
    week_ret_face = baseline_week_returns(r_face, calendar)
    week_ret_pt15 = baseline_week_returns(r_pt15, calendar)
    pd.DataFrame(
        [{"date": d, "week_ret_pp": week_ret_face[d] * 100} for d in sorted(week_ret_face)]
    ).to_csv(OUT / "baseline_week_returns_face.csv", index=False)

    hold_by: dict[str, dict[str, list[str]]] = {}
    cool_meta: dict[str, Any] = {}

    def attach_cool(
        out_name: str,
        raw_hold: dict[str, list[str]],
        week_ret: dict[str, float],
        thr: float,
        pt: float | None,
        role: str,
    ) -> None:
        cooled, n_cool, triggers = apply_loss_cool_overlay(raw_hold, calendar, week_ret, thr)
        hold_by[out_name] = cooled
        cool_meta[out_name] = {
            "threshold": thr,
            "n_cool_weeks": n_cool,
            "triggers": triggers,
            "profit_take_pct": pt,
            "role": role,
        }
        raw_key = "RAW-PT15" if pt is not None else "RAW-FACE"
        sim_stats[out_name] = {
            **sim_stats.get(raw_key, {}),
            "n_cool_weeks": n_cool,
            "cool_threshold": thr,
            "profit_take_pct": pt,
            "role": role,
        }
        if triggers:
            pd.DataFrame(triggers).to_csv(OUT / f"cool_triggers_{out_name}.csv", index=False)

    # 2×2 + attribution books
    BOOKS: list[tuple[str, float | None, float | None, str, dict[str, list[str]], dict[str, float]]] = [
        ("LIVE1430-FACE", None, None, "face_baseline", hold_face, week_ret_face),
        ("LIVE1430-PT15-only", PT_PRIMARY, None, "pt_only", hold_pt15, week_ret_pt15),
        ("LIVE1430-COOL6-only", None, COOL_PRIMARY, "cool_only", hold_face, week_ret_face),
        ("LIVE1430-CROSS-PT15-COOL6", PT_PRIMARY, COOL_PRIMARY, "primary_cross", hold_pt15, week_ret_pt15),
    ]

    for name, pt, cool_thr, role, raw, wret in BOOKS:
        if cool_thr is None:
            hold_by[name] = raw
            raw_key = "RAW-PT15" if pt is not None else "RAW-FACE"
            sim_stats[name] = {
                **sim_stats[raw_key],
                "profit_take_pct": pt,
                "cool_threshold": None,
                "n_cool_weeks": 0,
                "role": role,
            }
        else:
            attach_cool(name, raw, wret, cool_thr, pt, role)

    # 2×2 explicit labels (same holds, clearer grid keys)
    grid_22 = {
        "grid_PT0_COOL0": "LIVE1430-FACE",
        "grid_PT1_COOL0": "LIVE1430-PT15-only",
        "grid_PT0_COOL1": "LIVE1430-COOL6-only",
        "grid_PT1_COOL1": "LIVE1430-CROSS-PT15-COOL6",
    }

    def write_holdings(name: str, hold: dict[str, list[str]]) -> None:
        rows = []
        for d in calendar[:-1]:
            codes_h = hold.get(d) or []
            meta = cool_meta.get(name, {})
            rows.append(
                {
                    "date": d,
                    "risk_on": int(risk_on_by_fri.get(d, False)),
                    "n_held": len(codes_h),
                    "codes": ",".join(codes_h),
                    "profit_take": meta.get("profit_take_pct") if meta else sim_stats[name].get("profit_take_pct"),
                    "cool_thr": meta.get("threshold") if meta else sim_stats[name].get("cool_threshold"),
                }
            )
        pd.DataFrame(rows).to_csv(OUT / f"holdings_{name}.csv", index=False)

    variants = [b[0] for b in BOOKS]
    for name in variants:
        write_holdings(name, hold_by[name])

    table_rows: list[dict[str, Any]] = []
    series: dict[str, pd.Series] = {}
    for name in variants:
        r = nav_from_hold(hold_by[name])
        series[name] = r
        st = stats_full(r)
        r2022 = r[(r.index >= "2020-01-01") & (r.index <= "2022-12-31")]
        r2023 = r[r.index >= "2023-01-01"]
        st2022 = stats_full(r2022) if len(r2022) > 5 else {k: float("nan") for k in st}
        st2023 = stats_full(r2023) if len(r2023) > 5 else {k: float("nan") for k in st}
        meta = sim_stats[name]
        pt = meta.get("profit_take_pct")
        cool = meta.get("cool_threshold")
        table_rows.append(
            {
                "book": name,
                "pt_on": int(pt is not None),
                "cool_on": int(cool is not None),
                "profit_take_pct": pt if pt is not None else 0.0,
                "cool_threshold": cool if cool is not None else 0.0,
                "role": meta.get("role"),
                "n_pt_exits": meta.get("n_profit_take_exits", 0),
                "n_cool_weeks": meta.get("n_cool_weeks", 0),
                **st,
                "2020-22_ret": st2022["ret"],
                "2020-22_DD": st2022["maxDD"],
                "2020-22_Calmar": st2022["Calmar"],
                "2023-26_ret": st2023["ret"],
                "2023-26_DD": st2023["maxDD"],
                "2023-26_Calmar": st2023["Calmar"],
            }
        )
        print(
            f"  {name}: ret={pct(st['ret'])} Calmar={st['Calmar']:.2f} "
            f"pt_ex={meta.get('n_profit_take_exits', 0)} cool_w={meta.get('n_cool_weeks', 0)}",
            flush=True,
        )

    # Neighbor side tables
    neighbor_pt: list[dict[str, Any]] = []
    for thr, lab in [(0.10, "PT10"), (0.20, "PT20")]:
        h = sim_book(f"NEIGHBOR-{lab}", thr)
        stn = stats_full(nav_from_hold(h))
        neighbor_pt.append(
            {
                "kind": "profit_take",
                "label": lab,
                "profit_take": thr,
                "cool_threshold": None,
                **stn,
                "n_pt_exits": sim_stats[f"NEIGHBOR-{lab}"]["n_profit_take_exits"],
            }
        )

    neighbor_cool: list[dict[str, Any]] = []
    for thr, lab in [(-0.04, "COOL4"), (-0.08, "COOL8")]:
        cooled, n_cool, _ = apply_loss_cool_overlay(hold_face, calendar, week_ret_face, thr)
        stn = stats_full(nav_from_hold(cooled))
        neighbor_cool.append(
            {
                "kind": "loss_cool",
                "label": lab,
                "profit_take": None,
                "cool_threshold": thr,
                "n_cool_weeks": n_cool,
                **stn,
            }
        )

    df = pd.DataFrame(table_rows)
    df.to_csv(OUT / "table.csv", index=False)
    pd.DataFrame(neighbor_pt + neighbor_cool).to_csv(OUT / "neighbor_side.csv", index=False)

    eq = pd.DataFrame({k: (1 + series[k]).cumprod() for k in variants})
    eq.to_csv(OUT / "equity.csv")

    fig, ax = plt.subplots(figsize=(11, 5.5), dpi=120)
    styles = [
        ("LIVE1430-FACE", 2.2, "-"),
        ("LIVE1430-PT15-only", 1.3, "--"),
        ("LIVE1430-COOL6-only", 1.3, "-."),
        ("LIVE1430-CROSS-PT15-COOL6", 1.8, "-"),
    ]
    for name, lw, ls in styles:
        ax.plot(eq.index, eq[name], label=name.replace("LIVE1430-", ""), lw=lw, ls=ls)
    ax.set_yscale("log")
    ax.set_title("SPIKE-S20 EXIT CROSS PT15×COOL6（face 冻结 · 研究池）")
    ax.set_ylabel("净值（对数）")
    ax.grid(True, alpha=0.3)
    ax.legend(fontsize=7)
    fig.tight_layout()
    fig.savefig(OUT / "equity_curve.png")
    plt.close(fig)

    base_name = "LIVE1430-FACE"
    base = df[df.book == base_name].iloc[0]
    cross = df[df.book == "LIVE1430-CROSS-PT15-COOL6"].iloc[0]

    def delta_vs_face(row: pd.Series) -> dict[str, Any]:
        dret = (float(row["ret"]) - float(base["ret"])) * 100
        ddd_abs = (abs(float(row["maxDD"])) - abs(float(base["maxDD"]))) * 100
        cal_beat = float(row["Calmar"]) > float(base["Calmar"])
        return {
            "dret_pp": dret,
            "d_abs_mdd_pp": ddd_abs,
            "covers": dret >= ddd_abs,
            "calmar_beat": cal_beat,
            "rear_ok": float(row["2023-26_ret"]) >= float(base["2023-26_ret"]) * 0.9,
        }

    d_cross = delta_vs_face(cross)
    passes = (
        float(cross["Calmar"]) > float(base["Calmar"])
        and d_cross["covers"]
        and d_cross["dret_pp"] > 0
        and d_cross["rear_ok"]
    )

    # neighbor stability for primary knobs
    pt15_cal = float(df[df.book == "LIVE1430-PT15-only"].iloc[0]["Calmar"])
    pt10_cal = neighbor_pt[0]["Calmar"]
    pt20_cal = neighbor_pt[1]["Calmar"]
    cool6_cal = float(df[df.book == "LIVE1430-COOL6-only"].iloc[0]["Calmar"])
    cool4_cal = neighbor_cool[0]["Calmar"]
    cool8_cal = neighbor_cool[1]["Calmar"]
    neighbors_unstable = not (
        min(pt10_cal, pt20_cal) <= pt15_cal <= max(pt10_cal, pt20_cal)
        and min(cool4_cal, cool8_cal) <= cool6_cal <= max(cool4_cal, cool8_cal)
    )

    falsify = not passes or neighbors_unstable

    if falsify:
        verdict = (
            f"**交叉退出证伪（不换冠）**：face Calmar={float(base['Calmar']):.2f}；"
            f" CROSS PT15×COOL6 Calmar={float(cross['Calmar']):.2f} "
            f"Δret={d_cross['dret_pp']:+.1f}pp Δ|MDD|={d_cross['d_abs_mdd_pp']:+.1f}pp "
            f"后段{'OK' if d_cross['rear_ok'] else 'SKIP'}；"
            f"邻档{'不稳' if neighbors_unstable else '稳'}。"
            f" 单腿 PT15 / COOL6 此前已 falsify，交叉无新增升格。"
        )
    else:
        verdict = (
            f"**交叉退出记正（探索记账）**：CROSS 相对 face Calmar 提升且 Δret 盖住 Δ|MDD|；不换冠。"
        )

    grid_22_metrics = {k: delta_vs_face(df[df.book == v].iloc[0]) for k, v in grid_22.items()}

    summary = {
        "knife_id": "SPIKE-S20-EXIT-CROSS-PT15-COOL6-LIVE1430",
        "title": "SPIKE-S20 EXIT CROSS PT15 × COOL−6",
        "batch": "COMPOSER-EXIT-CROSS",
        "convention": "B45+S20+TV25 max5 face; Fri≥14:30/close; 0.2%RT; research pool",
        "unique_change": "profit_take +15% AND loss_cool −6% (cross); attribution PT-only / COOL-only / 2×2",
        "sample": f"{EVAL_START} → {actual_end}",
        "falsify": falsify,
        "passes_explore": passes,
        "n_calendar_weeks": len(calendar),
        "coverage": cov_stats,
        "cool_meta": cool_meta,
        "sim_stats": {k: v for k, v in sim_stats.items() if not k.startswith("RAW-") and not k.startswith("NEIGHBOR-")},
        "table": table_rows,
        "grid_2x2": grid_22,
        "grid_2x2_delta_vs_face": grid_22_metrics,
        "delta_cross_vs_face": d_cross,
        "neighbor_pt": neighbor_pt,
        "neighbor_cool": neighbor_cool,
        "neighbors_unstable": neighbors_unstable,
        "verdict": verdict,
        "isolation": "strategy_exec / LIVE_OPS / champion: NONE",
        "elapsed_sec": round(time.time() - t0, 1),
    }
    (OUT / "summary.json").write_text(
        json.dumps(summary, ensure_ascii=False, indent=2, default=str), encoding="utf-8"
    )

    knife_text = """# SPIKE-S20-EXIT-CROSS-PT15-COOL6-LIVE1430

- 面层冻结：breadth≥45% + spike_ft max5 + E0 + TV25 + SHARPE20；Fri≥14:30/收盘；0.2%RT；L≤1；研究池
- 唯一改动：同时启用 profit-take +15% 与 loss-cool −6%（上周组合收益≤−6% → 本周空仓）
- 证伪：交叉相对 face 无法在 Calmar 上胜出且 Δret 盖住 Δ|MDD|；或 2023–26 踏空；或邻档不稳
- 先验：PR#35 止盈单腿 falsify；PR#37 冷静单腿 falsify；本刀测交叉协同
"""
    (OUT / "criterion.md").write_text(knife_text, encoding="utf-8")

    def row_md(r: pd.Series) -> str:
        pt_l = "off" if not r["pt_on"] else f"PT{int(PT_PRIMARY*100)}"
        cl_l = "off" if not r["cool_on"] else f"COOL{int(abs(COOL_PRIMARY)*100)}"
        return (
            f"| {r['book']} | {pt_l} | {cl_l} | {pct(r['ret'])} | {pct(r['maxDD'])} | "
            f"{r['Calmar']:.2f} | {pct(r['2020-22_ret'])}/{pct(r['2023-26_ret'])} | "
            f"{int(r['n_pt_exits'])} | {int(r['n_cool_weeks'])} |"
        )

    main_body = "\n".join(row_md(df.loc[i]) for i in range(len(df)))

    g22_lines = ["| 2×2 cell | book | Δret vs face | Δ|MDD| | Calmar beat |", "|---|---|---:|---:|---|"]
    for cell, book in grid_22.items():
        d = grid_22_metrics[cell]
        g22_lines.append(
            f"| {cell} | {book} | {d['dret_pp']:+.1f}pp | {d['d_abs_mdd_pp']:+.1f}pp | "
            f"{'是' if d['calmar_beat'] else '否'} |"
        )

    neigh_lines = [
        "### PT 邻档（无冷静）",
        "| label | ret | maxDD | Calmar | pt_exits |",
        "|---|---:|---:|---:|---:|",
    ]
    for nr in neighbor_pt:
        neigh_lines.append(
            f"| {nr['label']} | {pct(nr['ret'])} | {pct(nr['maxDD'])} | {nr['Calmar']:.2f} | {nr['n_pt_exits']} |"
        )
    neigh_lines += [
        "### COOL 邻档（无止盈）",
        "| label | ret | maxDD | Calmar | cool_weeks |",
        "|---|---:|---:|---:|---:|",
    ]
    for nr in neighbor_cool:
        neigh_lines.append(
            f"| {nr['label']} | {pct(nr['ret'])} | {pct(nr['maxDD'])} | {nr['Calmar']:.2f} | {nr['n_cool_weeks']} |"
        )

    report = f"""# REPORT · SPIKE-S20-EXIT-CROSS-PT15-COOL6-LIVE1430

## 1. 准则

```
{knife_text.strip()}
```

## 2. 实现要点

- **交叉**：simulate 内 profit-take；冷静为 signal 周持仓 overlay（触发周收益=同路径无冷静 NAV 的周收益）。
- **主细胞**：PT15 × COOL−6；归因复跑 PT-only / COOL-only；2×2 显式记账。
- **冻结 face**；研究池；不写 strategy_exec / LIVE_OPS / champion。

## 3. 主表

| book | PT | COOL | ret | maxDD | Calmar | 2020–22 / 2023–26 ret | pt_exits | cool_w |
|---|---|---|---:|---:|---:|---|---:|---:|
{main_body}

### CROSS vs FACE

| 指标 | face | CROSS | Δ |
|---|---:|---:|---:|
| Calmar | {float(base['Calmar']):.2f} | {float(cross['Calmar']):.2f} | {float(cross['Calmar'])-float(base['Calmar']):+.2f} |
| ret | {pct(base['ret'])} | {pct(cross['ret'])} | {d_cross['dret_pp']:+.1f}pp |
| |MDD| | {pct(abs(float(base['maxDD'])))} | {pct(abs(float(cross['maxDD'])))} | {d_cross['d_abs_mdd_pp']:+.1f}pp |
| Δret 盖住 Δ|MDD| | — | — | {'是' if d_cross['covers'] else '否'} |
| 2023–26 ≥90% face | — | {pct(cross['2023-26_ret'])} | {'是' if d_cross['rear_ok'] else '否'} |

## 4. 2×2（PT15 on/off × COOL−6 on/off）

{chr(10).join(g22_lines)}

## 5. 邻档旁注

{chr(10).join(neigh_lines)}

## 6. 一句结论

{verdict}

产物：`summary.json` · `table.csv` · `equity_curve.png` · `run.py`（耗时 {summary['elapsed_sec']}s）
"""
    (OUT / "REPORT.md").write_text(report, encoding="utf-8")
    print("done", OUT, flush=True)
    print(verdict, flush=True)


if __name__ == "__main__":
    main()
