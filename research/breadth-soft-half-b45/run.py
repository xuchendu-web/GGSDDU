#!/usr/bin/env python3
"""BREADTH-SOFT-HALF-B45: MA20 width soft gate vs B45 hard face (research pool only).

Main soft: b≥0.45 full; 0.35≤b<0.45 deploy×0.5 (S20 select); b<0.35 flat.
Controls: B45 hard face; B50 hard side-note. Neighbors: SOFT4030-H50, H33/H66.
Frozen: spike_ft max5 + S20 + E0 + TV25 + Fri≥14:30 + 0.2%RT + L≤1.
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
TEMA_PX = Path("/workspace/tema_etf_scan_2018/prices_daily")  # optional overlay
NOON_CSV = CACHE / "fri_1430_through_20261023.csv"
SINA_DAILY = CACHE / "sina_daily"
CLASSIFY_FROM = "2019-07-01"
SNAP_CACHE = KIT / "data" / "cache_1430_snaps.json"
KNIFE_MD = KIT / "knives" / "BREADTH-SOFT-HALF-B45.md"


@dataclass(frozen=True)
class GateSpec:
    name: str
    kind: str  # "hard" | "soft"
    high: float
    low: float = 0.35
    half: float = 0.5


BOOKS: tuple[GateSpec, ...] = (
    GateSpec("LIVE1430-SOFT4535-H50-max5", "soft", 0.45, 0.35, 0.50),
    GateSpec("LIVE1430-B45-HARD-max5", "hard", 0.45),
    GateSpec("LIVE1430-B50-HARD-max5", "hard", 0.50),
    GateSpec("LIVE1430-SOFT4030-H50-max5", "soft", 0.40, 0.30, 0.50),
    GateSpec("LIVE1430-SOFT4535-H33-max5", "soft", 0.45, 0.35, 0.33),
    GateSpec("LIVE1430-SOFT4535-H66-max5", "soft", 0.45, 0.35, 0.66),
)
MAIN_SOFT = BOOKS[0].name
BASELINE_HARD = BOOKS[1].name
B50_HARD = BOOKS[2].name

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


def deploy_scale_for_b(spec: GateSpec, b: float | None) -> float:
    if b is None:
        return 0.0
    if spec.kind == "hard":
        return 1.0 if b >= spec.high else 0.0
    if b >= spec.high:
        return 1.0
    if b >= spec.low:
        return spec.half
    return 0.0


def scale_map_for_spec(spec: GateSpec, calendar: list[str], breadth_b: dict[str, float]) -> dict[str, float]:
    smap: dict[str, float] = {}
    for d in calendar:
        smap[d] = deploy_scale_for_b(spec, breadth_b.get(d))
    smap[calendar[-1]] = 0.0
    return smap


def simulate(
    calendar: list[str],
    snaps: dict[str, dict[str, dict[str, Any]]],
    closes_w: dict[str, dict[str, float]],
    alias: dict[str, dict[str, str]],
    aum: dict[str, float],
    daily: dict[str, pd.Series],
    deploy_scale_by_fri: dict[str, float],
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
        scale = 0.0 if last_bar else float(deploy_scale_by_fri.get(d, 0.0))
        select_on = scale > 0

        exiting: list[tuple[str, str, float]] = []
        for code, p in list(positions.items()):
            px = px_on(code, d)
            if last_bar:
                exiting.append((code, "eod_eval", px if px is not None else p.last_px))
                continue
            if not select_on:
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
        if not last_bar and select_on:
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

        eq = equity_now()
        n_pos = len(positions) + len(take)
        if take:
            if n_pos > max_pos:
                raise SystemExit(f"overflow {variant} {d} n={n_pos}")
            inv = eq * scale
            tpp = inv / n_pos if n_pos else 0.0
            for p in positions.values():
                if p.last_px > 0:
                    p.shares = tpp / p.last_px
            for c in take:
                positions[c.code] = Position(
                    code=c.code,
                    kind="spike_ft",
                    entry_date=d,
                    entry_px=c.px,
                    entry_falsify=c.fz,
                    shares=(tpp * (1.0 - COST_SIDE)) / c.px,
                    last_px=c.px,
                    weeks=0,
                )
            cash = max(0.0, eq - inv)
        elif positions and select_on:
            inv = eq * scale
            tpp = inv / len(positions) if positions else 0.0
            for p in positions.values():
                if p.last_px > 0:
                    p.shares = tpp / p.last_px
            cash = max(0.0, eq - inv)
        elif positions:
            cash = equity_now()
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

    n_cash = sum(1 for d in calendar[:-1] if not (hold.get(d) or []))
    n_weeks = max(1, len(calendar) - 1)

    def week_scale(d: str) -> float:
        return float(deploy_scale_by_fri.get(d, 0.0))

    stats = {
        "n_fridays_queue_gt_seats": n_tight,
        "n_fridays_with_cands": n_feat,
        "n_entries": n_entries,
        "n_entries_missing_sharpe": n_miss_sharpe,
        "n_trades": len(trades),
        "max_pos": max_pos,
        "n_cash_weeks": n_cash,
        "n_calendar_weeks_ex_last": max(0, len(calendar) - 1),
        "cash_week_pct": n_cash / n_weeks,
        "n_full_deploy_weeks": sum(1 for d in calendar[:-1] if week_scale(d) >= 1.0 - 1e-9),
        "full_deploy_week_pct": sum(1 for d in calendar[:-1] if week_scale(d) >= 1.0 - 1e-9) / n_weeks,
        "n_half_deploy_weeks": sum(
            1 for d in calendar[:-1] if 0 < week_scale(d) < 1.0 - 1e-9
        ),
        "half_deploy_week_pct": sum(
            1 for d in calendar[:-1] if 0 < week_scale(d) < 1.0 - 1e-9
        )
        / n_weeks,
        "n_risk_on_weeks": sum(1 for d in calendar[:-1] if week_scale(d) > 0),
        "risk_on_week_pct": sum(1 for d in calendar[:-1] if week_scale(d) > 0) / n_weeks,
    }
    if rank_rows:
        pd.DataFrame(rank_rows).to_csv(OUT / f"entries_{variant}.csv", index=False)
    return trades, hold, stats


def run_live_tv(
    hold: dict[pd.Timestamp, list[str]],
    days: pd.DatetimeIndex,
    px: pd.DataFrame,
    R: pd.DataFrame,
    deploy_scale: dict[pd.Timestamp, float] | None = None,
) -> tuple[pd.Series, pd.Series]:
    reb = sorted(hold)
    rp = pd.Series(0.0, index=days)
    Ls = pd.Series(0.0, index=days)
    prev: dict[str, float] = {}
    cst = pd.Series(0.0, index=days)
    R2 = R.reindex(days)

    for i, d in enumerate(reb):
        sc = 1.0 if deploy_scale is None else float(deploy_scale.get(d, 1.0))
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
        wt = {c: sc * L * v for c, v in w.items()}
        to = sum(abs(wt.get(k, 0) - prev.get(k, 0)) for k in set(wt) | set(prev))
        prev = wt
        if d in cst.index:
            cst.loc[d] = to * LIVE_COST_RT / 2
        if w and len(seg):
            stock = (R2.loc[seg, list(w)].fillna(0) @ pd.Series(w)).values
            rp.loc[seg] = sc * stock
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
        return "—"
    return f"{100 * x:.1f}%"


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    t0 = time.time()
    for p in (WEEK, FACE, DAY_DIR, NOON_CSV, SINA_DAILY):
        if not Path(p).exists():
            raise SystemExit(f"missing research cache path {p}; run extend_research_data.py first")

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

    face = pd.read_csv(FACE)
    face["date"] = face["date"].astype(str).str[:10]
    face = face[(face["date"] >= EVAL_START) & (face["date"] <= END_S)].copy()
    calendar = sorted(face["date"].unique().tolist())
    if not calendar:
        raise SystemExit("empty calendar")
    actual_end = calendar[-1]
    print(f"calendar {calendar[0]} → {actual_end} n={len(calendar)}", flush=True)

    breadth_b: dict[str, float] = {}
    for _, row in face.iterrows():
        d = str(row["date"])[:10]
        bv = row.get("b")
        if bv is not None and not (isinstance(bv, float) and math.isnan(bv)):
            breadth_b[d] = float(bv)

    scale_by_book: dict[str, dict[str, float]] = {
        spec.name: scale_map_for_spec(spec, calendar, breadth_b) for spec in BOOKS
    }
    for spec in BOOKS:
        sm = scale_by_book[spec.name]
        n_full = sum(1 for d in calendar[:-1] if sm.get(d, 0) >= 1.0 - 1e-9)
        n_half = sum(1 for d in calendar[:-1] if 0 < sm.get(d, 0) < 1.0 - 1e-9)
        n_off = sum(1 for d in calendar[:-1] if sm.get(d, 0) <= 0)
        print(
            f"{spec.name}: full={n_full} half={n_half} off={n_off} / {len(calendar)-1}",
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

    print("load sina + daily qfq for 14:30 map…", flush=True)
    sina = load_sina_closes(codes)
    print(f"sina daily: {len(sina)}/{len(codes)}", flush=True)
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
    print(f"mapped qfq_1430={n_map} skip_no_bfq={n_skip} empty_block_rows={n_empty}", flush=True)

    listed = noon[noon["status"] != "not_listed"]
    listed = listed[(listed.trade_date >= EVAL_START) & (listed.trade_date <= END_S)]
    nonnull_rate = float(listed["price_1130"].notna().mean()) if len(listed) else 0.0
    cov_stats = {
        "px_1430_csv": str(NOON_CSV),
        "n_codes_aum2": len(codes),
        "n_calendar_weeks": len(calendar),
        "calendar_end": actual_end,
        "listed_1430_nonnull_rate": nonnull_rate,
        "n_qfq_1430_mapped": n_map,
        "n_skip_no_sina_or_qfq": n_skip,
        "n_empty_status_rows": n_empty,
        "approximation": [
            "延窗研究缓存：week/day 合并 recon week_2026-10-23 / day_2026-10-23；缺日线用 sina 收益链拼接（研究目录）",
            "14:30 新周（09-30/10-09/10-16/10-23）pytdx idx209 拉入 research_cache；旧周复用 fri_1430_through_20260925",
            "breadth b：extended face holdings_ro2_extended（≤2026-10-09 原 face + 其后研究周线 MA20 宽度假算 aum≥2）",
            "主软门 b≥0.45 满仓；0.35≤b<0.45 目标×0.5（S20 仍选）；b<0.35 空仓；对照 B45/B50 硬门",
            "qfq_1430 = price_1430 × (day/tema qfq 收 / sina 收)；Sharpe 窗截至信号日前一交易日",
            "成交/净值：信号周末交易日收盘填仓 + TV25 + 0.2%RT；L≤1",
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
        raise SystemExit(f"missing 14:30 snap cache {SNAP_CACHE}")
    cached = json.loads(SNAP_CACHE.read_text(encoding="utf-8"))
    if cached.get("end") != actual_end:
        print(
            f"warn: snap cache end={cached.get('end')} calendar end={actual_end}; using cache anyway",
            flush=True,
        )
    print(f"load kit 1430 snaps from {SNAP_CACHE}", flush=True)
    by_rows = cached.get("by_code") or {}
    snaps = {c: snap_index(by_rows.get(c) or []) for c in codes}

    variants: dict[str, tuple[dict[str, float], int]] = {
        spec.name: (scale_by_book[spec.name], 5) for spec in BOOKS
    }
    hold_by: dict[str, dict[str, list[str]]] = {}
    scale_ts_by: dict[str, dict[pd.Timestamp, float]] = {}
    sim_stats: dict[str, Any] = {}
    for name, (smap, mp) in variants.items():
        print(f"simulate {name} (max_pos={mp})…", flush=True)
        trades, hold, st = simulate(
            calendar,
            snaps,
            closes_w_sig,
            alias,
            aum,
            daily,
            smap,
            sharpe_key,
            name,
            True,
            20,
            mp,
        )
        hold_by[name] = hold
        scale_ts_by[name] = {pd.Timestamp(d): float(smap.get(d, 0.0)) for d in calendar}
        sim_stats[name] = st
        rows = []
        for d in calendar[:-1]:
            codes_h = hold.get(d) or []
            sc = float(smap.get(d, 0.0))
            rows.append(
                {
                    "date": d,
                    "deploy_scale": sc,
                    "risk_on": int(sc > 0),
                    "full_face": int(sc >= 1.0 - 1e-9),
                    "half_band": int(0 < sc < 1.0 - 1e-9),
                    "n_held": len(codes_h),
                    "codes": ",".join(codes_h),
                }
            )
        pd.DataFrame(rows).to_csv(OUT / f"holdings_{name}.csv", index=False)
        pd.DataFrame(trades).to_csv(OUT / f"trades_{name}.csv", index=False)
        # nav placeholder filled later
        print(
            f"  entries={st['n_entries']} trades={st['n_trades']} "
            f"cands_weeks={st['n_fridays_with_cands']} cash_weeks={st['n_cash_weeks']} "
            f"({100*st['cash_week_pct']:.1f}%)",
            flush=True,
        )

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
            if TEMA_PX.exists() and f.exists():
                df = pd.read_csv(f, parse_dates=["Date"])
                px_map[c] = df.set_index("Date")["Close"].astype(float).sort_index()
    px = pd.DataFrame(px_map).sort_index()
    px = px.loc[(px.index >= EVAL_START) & (px.index <= END_S)]
    R = px.pct_change()
    if "510300" in px.columns:
        days = px["510300"].dropna().index
    else:
        days = px.dropna(how="all").index
    # also allow days from any column if 510300 short
    days = days[(days >= EVAL_START) & (days <= END_S)]
    # extend calendar days using union if needed
    if len(days) and str(days[-1].date()) < actual_end:
        # try use sina/day union index from all daily
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
    for name in variants:
        hd = {pd.Timestamp(d): cs for d, cs in hold_by[name].items()}
        r, L = run_live_tv(hd, days, px, R, scale_ts_by[name])
        series[name] = r
        Ls_map[name] = L
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
            "cash_week_pct": sim_stats[name]["cash_week_pct"],
            "risk_on_week_pct": sim_stats[name]["risk_on_week_pct"],
            "full_deploy_week_pct": sim_stats[name]["full_deploy_week_pct"],
            "half_deploy_week_pct": sim_stats[name]["half_deploy_week_pct"],
        }
        table_rows.append(row)
        nav = (1 + r).cumprod()
        nav.to_csv(OUT / f"nav_{name}.csv", header=["nav"])
        print(
            f"  {name}: ret={pct(st['ret'])} dd={pct(st['maxDD'])} "
            f"CAGR={pct(st['CAGR'])} Calmar={st['Calmar']:.2f} cash%={100*row['cash_week_pct']:.1f}",
            flush=True,
        )

    df = pd.DataFrame(table_rows)
    df.to_csv(OUT / "table.csv", index=False)
    df.to_csv(OUT / "metrics.csv", index=False)

    soft_name = MAIN_SOFT
    b45_name = BASELINE_HARD
    b50_name = B50_HARD

    y = yearly_table(series[soft_name]).rename(columns=lambda c: f"soft_{c}" if c != "year" else c)
    for bk, col in [(b45_name, "b45"), (b50_name, "b50")]:
        yi = yearly_table(series[bk]).rename(columns=lambda c, p=col: f"{p}_{c}" if c != "year" else c)
        y = y.merge(yi, on="year", how="outer")
    y["delta_soft_vs_b45_pp"] = (y["soft_ret"] - y["b45_ret"]) * 100
    y["delta_b50_vs_b45_pp"] = (y["b50_ret"] - y["b45_ret"]) * 100
    y.to_csv(OUT / "yearly.csv", index=False)

    eq = pd.DataFrame({k: (1 + series[k]).cumprod() for k in variants})
    eq.to_csv(OUT / "equity.csv")
    eq.to_csv(OUT / "nav_all.csv")

    plot_styles = [
        (soft_name, 2.0, "-"),
        (b45_name, 1.8, "--"),
        (b50_name, 1.4, ":"),
        (BOOKS[3].name, 1.0, "-."),
    ]
    fig, ax = plt.subplots(figsize=(11, 5.5), dpi=120)
    for name, lw, ls in plot_styles:
        if name in eq.columns:
            ax.plot(eq.index, eq[name], label=name, lw=lw, ls=ls)
    ax.set_yscale("log")
    ax.set_title("BREADTH-SOFT-HALF-B45（软门 vs B45 face；Fri 14:30）")
    ax.set_ylabel("净值（对数）")
    ax.grid(True, alpha=0.3)
    ax.legend(fontsize=7)
    fig.tight_layout()
    fig.savefig(OUT / "equity_curve.png")
    plt.close(fig)

    soft = df[df.book == soft_name].iloc[0]
    b45 = df[df.book == b45_name].iloc[0]
    b50 = df[df.book == b50_name].iloc[0]

    dret_soft = (soft["ret"] - b45["ret"]) * 100
    ddd_soft = (soft["maxDD"] - b45["maxDD"]) * 100
    ddd_abs_soft = (abs(soft["maxDD"]) - abs(b45["maxDD"])) * 100
    dcal_soft = soft["Calmar"] - b45["Calmar"]

    dret50 = (b50["ret"] - b45["ret"]) * 100
    ddd_abs50 = (abs(b50["maxDD"]) - abs(b45["maxDD"])) * 100
    dcal50 = b50["Calmar"] - b45["Calmar"]

    def vs_b45_covers(row: pd.Series) -> bool:
        dret = (row["ret"] - b45["ret"]) * 100
        d_abs = (abs(row["maxDD"]) - abs(b45["maxDD"])) * 100
        return dret >= d_abs - 1e-9

    def strong_vs_b45(row: pd.Series) -> bool:
        if math.isnan(row["2023-26_ret"]) or math.isnan(b45["2023-26_ret"]):
            return False
        return row["2023-26_ret"] >= b45["2023-26_ret"] - 0.02

    soft_covers = vs_b45_covers(soft)
    soft_strong = strong_vs_b45(soft)
    soft_beats_face = (
        float(soft["ret"]) > float(b45["ret"])
        and float(soft["Calmar"]) >= float(b45["Calmar"]) - 0.02
    )
    h1_falsified = soft_beats_face and soft_covers and soft_strong

    if h1_falsified:
        verdict = (
            f"**证伪 H1（软门可胜 face；不换冠）**：{soft_name} 相对 B45 face "
            f"ret {pct(float(soft['ret']))} vs {pct(float(b45['ret']))}，Calmar {float(soft['Calmar']):.2f} vs {float(b45['Calmar']):.2f}；"
            f"Δret={dret_soft:+.1f}pp 盖住 Δ|MDD|={ddd_abs_soft:+.1f}pp；"
            f"2023–26 {pct(float(soft['2023-26_ret']))} vs {pct(float(b45['2023-26_ret']))}。"
        )
    else:
        reasons: list[str] = []
        if not soft_beats_face:
            reasons.append(
                f"总收益/Calmar 未同时优于 face（ret {pct(float(soft['ret']))} vs {pct(float(b45['ret']))}；"
                f"Calmar {float(soft['Calmar']):.2f} vs {float(b45['Calmar']):.2f}）"
            )
        if not soft_covers:
            reasons.append(f"Δret={dret_soft:+.1f}pp 未盖住 Δ|MDD|={ddd_abs_soft:+.1f}pp")
        if not soft_strong:
            reasons.append(
                f"强势段踏空/后段塌（2023–26 {pct(float(soft['2023-26_ret']))} vs B45 {pct(float(b45['2023-26_ret']))}）"
            )
        verdict = "**H1 成立（软门不能胜硬门 face；不换冠）**：" + "；".join(reasons) + "。"

    b50_side = (
        f"B50 硬门旁注（勿改实盘）：vs B45 Δret={dret50:+.1f}pp，Δ|MDD|={ddd_abs50:+.1f}pp，ΔCalmar={dcal50:+.2f}；"
        f"2023–26 {pct(float(b50['2023-26_ret']))} vs B45 {pct(float(b45['2023-26_ret']))}。"
    )

    nob_ref_b45_ret = 1.3399609137897461
    nob_ref_b45_cal = 0.704970180111173
    align_note = (
        f"B45 硬门同窗对齐 kit nob_ref：本跑 ret={pct(float(b45['ret']))} Calmar={float(b45['Calmar']):.2f} "
        f"（参照 {pct(nob_ref_b45_ret)} / {nob_ref_b45_cal:.2f}）。"
    )

    criterion_src = KNIFE_MD.read_text(encoding="utf-8") if KNIFE_MD.exists() else ""

    summary = {
        "title": "BREADTH-SOFT-HALF-B45",
        "hypothesis": "H1: soft gate cannot beat B45 hard face on ret-vs-MDD and strong segment",
        "h1_falsified": h1_falsified,
        "unique_change": "MA20 width soft band vs B45/B50 hard; freeze spike max5+S20+E0+TV25",
        "sample": f"{EVAL_START} → {actual_end}",
        "main_soft": soft_name,
        "baseline_hard": b45_name,
        "b50_side_note": b50_name,
        "books": [s.name for s in BOOKS],
        "coverage": cov_stats,
        "sim_stats": sim_stats,
        "table": table_rows,
        "delta_soft_vs_b45": {
            "dret_pp": dret_soft,
            "dMDD_algebraic_pp": ddd_soft,
            "d_absMDD_pp": ddd_abs_soft,
            "dCalmar": dcal_soft,
        },
        "delta_b50_vs_b45": {"dret_pp": dret50, "d_absMDD_pp": ddd_abs50, "dCalmar": dcal50},
        "b45_align_nob_ref": {"ret": nob_ref_b45_ret, "Calmar": nob_ref_b45_cal},
        "verdict": verdict,
        "b50_side_note_text": b50_side,
        "elapsed_sec": round(time.time() - t0, 1),
    }
    (OUT / "summary.json").write_text(
        json.dumps(summary, ensure_ascii=False, indent=2, default=str), encoding="utf-8"
    )

    (OUT / "criterion.md").write_text(
        "# Criterion · BREADTH-SOFT-HALF-B45\n\n"
        + criterion_src
        + "\n\n## 本跑实现要点\n\n"
        "- 软门：`b≥high` 满仓；`low≤b<high` 目标×half（S20 仍选）；`b<low` 空仓；`b` 来自 extended face。\n"
        "- 硬门对照：`deploy_scale = 1` 当 `b≥θ` 否则 0（B45 face / B50 旁注）。\n"
        "- 冻结：spike_ft excl box_pending + SHARPE20 max5 + E0 + TV25 σ*=0.25 + Fri≥14:30/收盘 + 0.2%RT + L≤1。\n"
        f"- 样本：{EVAL_START}→{actual_end}；kit `research_cache` + `cache_1430_snaps.json`。\n"
        "- 红线：研究池 only；不换冠；不写 strategy_exec / LIVE_OPS。\n",
        encoding="utf-8",
    )

    def row_md(name: str, mark: str = "") -> str:
        r = df[df.book == name].iloc[0]
        tag = mark
        if not tag:
            if name == soft_name:
                tag = "**主软门**"
            elif name == b45_name:
                tag = "**face基线**"
            elif name == b50_name:
                tag = "旁注"
        return (
            f"| {name} {tag} | {pct(r['ret'])} | {pct(r['maxDD'])} | {pct(r['CAGR'])} | {r['Calmar']:.2f} | "
            f"{pct(r['2020-22_ret'])}/{pct(r['2020-22_DD'])}/{r['2020-22_Calmar']:.2f} | "
            f"{pct(r['2023-26_ret'])}/{pct(r['2023-26_DD'])}/{r['2023-26_Calmar']:.2f} | "
            f"{r['avgL']:.2f} | {100*r['full_deploy_week_pct']:.1f}% | {100*r['half_deploy_week_pct']:.1f}% | "
            f"{100*r['risk_on_week_pct']:.1f}% |"
        )

    table_md = "\n".join(row_md(n) for n in df["book"])

    y_lines = [
        "| 年 | SOFT4535-H50 | B45 face | B50 hard | Δsoft-B45 pp | ΔB50-B45 pp |",
        "|---|---:|---:|---:|---:|---:|",
    ]
    for _, row in y.iterrows():
        y_lines.append(
            f"| {int(row.year)} | "
            f"{pct(float(row.soft_ret)) if pd.notna(row.soft_ret) else '—'} | "
            f"{pct(float(row.b45_ret)) if pd.notna(row.b45_ret) else '—'} | "
            f"{pct(float(row.b50_ret)) if pd.notna(row.b50_ret) else '—'} | "
            f"{float(row.delta_soft_vs_b45_pp):+.1f} | "
            f"{float(row.delta_b50_vs_b45_pp):+.1f} |"
        )

    approx_md = "\n".join(f"- {a}" for a in cov_stats["approximation"])

    report = f"""# REPORT · BREADTH-SOFT-HALF-B45（宽度软门 vs B45 face）

## 1. 准则原文

```
{criterion_src.strip()}
```

## 2. 实现要点

- **主改动**：MA20 宽度软门（0.45/0.35，半仓 0.5）vs **B45 硬门 face**；B50 硬门仅旁注。
- **冻结**：spike_ft max5 + SHARPE20 + E0 + TV25 + Fri≥14:30/收盘 + 0.2%RT + L≤1。
- **延窗**：kit `research_cache`，日历至 **{actual_end}**。
- **face 基线**：`{b45_name}`。{align_note}
- **不换冠**；不写 strategy_exec / LIVE_OPS。

## 近似与覆盖

{approx_md}

| 覆盖 | 值 |
|---|---|
| 可投池（AUM≥2亿） | {len(codes)} |
| 日历周 | {len(calendar)}（{calendar[0]}→{actual_end}） |
| listed 行 14:30 非空率 | {100*nonnull_rate:.1f}% |
| 成功映射 qfq_1430 | {n_map} |

## 3. 主表（LIVE1430 · Fri 14:30 信号）

| book | ret | maxDD | CAGR | Calmar | 2020–22 ret/DD/C | 2023–26 ret/DD/C | avgL | full% | half% | on% |
|---|---:|---:|---:|---:|---|---|---:|---:|---:|---:|
{table_md}

### Δ · 主软门 vs B45 face（H1 检验）

| | |
|---|---|
| Δ总收益 | {dret_soft:+.1f}pp |
| ΔMDD（代数） | {ddd_soft:+.1f}pp |
| Δ|MDD|（正=更深） | {ddd_abs_soft:+.1f}pp |
| ΔCalmar | {dcal_soft:+.2f} |
| 2023–26 软门 vs face | {pct(float(soft['2023-26_ret']))} vs {pct(float(b45['2023-26_ret']))} |

### B50 硬门旁注（勿改实盘）

{b50_side}

### 历年（软门 / face / B50）

{chr(10).join(y_lines)}

## 4. H1 结论

{verdict}

## 产物

- 四件套：`run.py` / `criterion.md` / `REPORT.md` / `table.csv`
- `equity_curve.png` / `metrics.csv` / `yearly.csv` / `summary.json` / `nav_*.csv`
- 数据：`research/cloud_batch/CLOUD-BATCH-2026-10-26/data/`

耗时约 {summary['elapsed_sec']}s。延窗实际终点 **{actual_end}**。
"""
    (OUT / "REPORT.md").write_text(report, encoding="utf-8")
    print("done", OUT, flush=True)
    print(verdict, flush=True)
    print(b50_side, flush=True)
    print(f"H1_FALSIFIED={h1_falsified} END={actual_end}", flush=True)


if __name__ == "__main__":
    main()
