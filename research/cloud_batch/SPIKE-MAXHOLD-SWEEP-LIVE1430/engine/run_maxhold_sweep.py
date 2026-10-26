#!/usr/bin/env python3
"""SPIKE-MAXHOLD-SWEEP-LIVE1430: max consecutive-hold cap sweep on frozen B45+S20+TV25 max5.

Books (same engine, research pool only):
  LIVE1430-B45-S20 (baseline, no cap), LIVE1430-MH4, LIVE1430-MH6, LIVE1430-MH8

Frozen: breadth≥45% MA20 (face risk_on) + spike_ft (excl box_pending) + SHARPE20 fill + E0 + TV25 L≤1 + 0.2%RT
Unique change: force exit single name when consecutive hold weeks ≥ {4,6,8} (grid); baseline uncapped.

Research pool: etf-correlation/data/research_pool_v2.csv ∩ aum≥2 universe with bars.
No strategy_exec / LIVE / champion edits. Four-pack to research/cloud_batch + etf-multifreq mirror.
"""
from __future__ import annotations

import json
import math
import shutil
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

KIT = Path("/workspace/research/cloud_batch/CLOUD-BATCH-2026-10-26")
SCRIPTS = KIT / "scripts"
sys.path.insert(0, str(SCRIPTS))

from backtest import KEEP, LIVE_PHASE, MIN_BARS, Position, nearest_date, snap_index  # noqa: E402
from build_scan import Bar, classify  # noqa: E402

ID = "SPIKE-MAXHOLD-SWEEP-LIVE1430"
OUT = Path(f"/workspace/research/cloud_batch/{ID}")
SYNC_OUT = Path(f"/workspace/etf-multifreq/{ID}")
RESEARCH_POOL_CSV = Path("/workspace/etf-correlation/data/research_pool_v2.csv")
UNI_CSV = KIT / "data/universe_replace_only_436.csv"
WEEK = KIT / "data/research_cache/week"
FACE = KIT / "data/holdings_ro2_from2016.csv"
DAY_DIR = KIT / "data/research_cache/day"
TEMA_PX = Path("/workspace/tema_etf_scan_2018/prices_daily")
NOON_CSV = KIT / "data/research_cache/fri_1430_through_20261023.csv"
SINA_DAILY = KIT / "data/research_cache/sina_daily"
CLASSIFY_FROM = "2019-07-01"
SNAP_CACHE = KIT / "data/cache_1430_snaps.json"

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
    max_hold_weeks: int | None = None,
) -> tuple[list[dict[str, Any]], dict[str, list[str]], dict[str, Any]]:
    cash = 1.0
    positions: dict[str, Position] = {}
    trades: list[dict[str, Any]] = []
    picks: dict[str, list[str]] = {}
    n_tight = 0
    n_feat = 0
    n_entries = 0
    n_miss_sharpe = 0
    n_cand_weeks = 0
    n_max_hold_exits = 0
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
            if max_hold_weeks is not None and p.weeks >= max_hold_weeks:
                reason = "max_hold"
            sn = snap_at(code, d)
            if sn and reason is None:
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
            if reason == "max_hold":
                n_max_hold_exits += 1
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
            slots = MAX_POS - len(positions)
            if pool:
                n_feat += 1
                n_cand_weeks += 1
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
        "n_max_hold_exits": n_max_hold_exits,
        "max_hold_weeks": max_hold_weeks,
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
    pool = pd.read_csv(RESEARCH_POOL_CSV, dtype={"code": str})
    pool["code"] = pool.code.str.zfill(6)
    pool_set = set(pool.code.drop_duplicates())
    uni = uni[uni["code"].isin(pool_set)].copy()
    codes = uni["code"].tolist()
    aum = {r.code: float(r.aum or 0) for r in uni.itertuples()}
    code_set = set(codes)
    print(f"universe research_pool_v2 ∩ aum≥2: n={len(codes)}", flush=True)

    noon = pd.read_csv(NOON_CSV)
    noon["code"] = noon["etf_code"].astype(str).str.split(".").str[0]
    noon["trade_date"] = noon["trade_date"].astype(str).str[:10]
    noon["friday_week_date"] = noon["friday_week_date"].astype(str).str[:10]
    noon = noon[noon["code"].isin(code_set)].copy()
    # alias price_1430 as price_1130 column name used below for minimal fork churn
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

    # qfq_1430 = price_1430 * (qfq_day / sina_day); block empty / unmapped
    noon_w: dict[str, dict[str, float]] = defaultdict(dict)
    noon_d: dict[str, dict[str, float]] = defaultdict(dict)
    blocked_empty: dict[str, set[str]] = defaultdict(set)
    n_map = n_skip = n_empty = 0
    for r in noon.itertuples():
        td = r.trade_date
        if td < EVAL_START or td > END_S:
            continue
        if r.status == "empty" or (r.status == "ok" and (r.price_1130 is None or (isinstance(r.price_1130, float) and math.isnan(r.price_1130)))):
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

    # coverage stats
    listed = noon[noon["status"] != "not_listed"]
    listed = listed[(listed.trade_date >= EVAL_START) & (listed.trade_date <= END_S)]
    nonnull_rate = float(listed["price_1130"].notna().mean()) if len(listed) else 0.0
    weeks_with_any_noon = (
        listed[listed["price_1130"].notna()].groupby("trade_date").size()
    )
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
        "approximation": [
            "breadth/risk_on 沿用 face holdings_ro2_from2016（收盘 MA20 宽度），未用 14:30 价重算 breadth",
            "qfq_1430 = price_1430 × (day2017/tema qfq 收 / sina daily 收)；sina 作 bfq 代理（缺 sina/qfq 无法映射则当日不可选）",
            "冲击分类：周线收盘替换为 qfq_1430 后因果 classify（14:30 信号，非 11:30、非周五收盘探索）",
            "Sharpe 窗截至信号日严格前一交易日（避免周五收盘前视）",
            "成交/净值：周五（信号周末交易日）收盘填仓 + TV25 + 0.2%RT（ops 目标盘后成交；收盘填仓对齐 LIVE 主表约定）",
            "14:30 价来自 pytdx get_history_minute_time_data idx209；非收盘伪装",
        ],
    }

    # decision closes: weekly close overwritten by noon; blocked codes lose px that week
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

    # 14:30 classify (cache)
    if SNAP_CACHE.exists():
        print(f"load cached 1430 snaps {SNAP_CACHE}", flush=True)
        cached = json.loads(SNAP_CACHE.read_text(encoding="utf-8"))
        by_rows = cached.get("by_code") or {}
        snaps = {c: snap_index(by_rows.get(c) or []) for c in codes}
        print(f"  cached codes with snaps: {sum(1 for c in codes if snaps.get(c))}", flush=True)
    else:
        print("14:30 classify_modified…", flush=True)
        by = classify_modified(raws_w, dict(noon_w))
        by_rows = {c: by.get(c) or [] for c in codes}
        SNAP_CACHE.write_text(
            json.dumps({"by_code": by_rows, "end": END_S, "start": EVAL_START}, ensure_ascii=False),
            encoding="utf-8",
        )
        snaps = {c: snap_index(by_rows.get(c) or []) for c in codes}
        print(f"  wrote {SNAP_CACHE}", flush=True)

    MAIN = "LIVE1430-B45-S20"
    variants: dict[str, tuple[RankFn, bool, int | None, int | None]] = {
        MAIN: (sharpe_key, True, 20, None),
        "LIVE1430-MH4": (sharpe_key, True, 20, 4),
        "LIVE1430-MH6": (sharpe_key, True, 20, 6),
        "LIVE1430-MH8": (sharpe_key, True, 20, 8),
    }
    hold_by: dict[str, dict[str, list[str]]] = {}
    sim_stats: dict[str, Any] = {}
    for name, (rfn, req, sn, mh) in variants.items():
        print(f"simulate {name} max_hold={mh}…", flush=True)
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
            max_hold_weeks=mh,
        )
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
            f"cands_weeks={st['n_fridays_with_cands']} tight={st['n_fridays_queue_gt_seats']}",
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

    diffs = {f"{k}_vs_base": pick_diff(MAIN, k) for k in variants if k != MAIN}
    print("hold diffs vs baseline", diffs, flush=True)

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
    for name in variants:
        hd = {pd.Timestamp(d): cs for d, cs in hold_by[name].items()}
        r, L = run_live_tv(hd, days, px, R)
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
        }
        table_rows.append(row)
        print(
            f"  {name}: ret={pct(st['ret'])} dd={pct(st['maxDD'])} "
            f"CAGR={pct(st['CAGR'])} Calmar={st['Calmar']:.2f}",
            flush=True,
        )

    for name, st in sim_stats.items():
        row = next(r for r in table_rows if r["book"] == name)
        row["max_hold_weeks"] = st.get("max_hold_weeks")
        row["n_max_hold_exits"] = st.get("n_max_hold_exits", 0)
        row["n_trades"] = st.get("n_trades", 0)

    df = pd.DataFrame(table_rows)
    order = [MAIN] + [k for k in variants if k != MAIN]
    df = df.set_index("book").reindex(order).reset_index()
    df.to_csv(OUT / "metrics.csv", index=False)

    yearly_parts = []
    for name in order:
        yi = yearly_table(series[name]).assign(book=name)
        yearly_parts.append(yi)
    yearly = pd.concat(yearly_parts, ignore_index=True)
    yearly.to_csv(OUT / "yearly.csv", index=False)

    nav = pd.DataFrame({k: (1 + series[k]).cumprod() for k in order})
    nav.to_csv(OUT / "nav.csv")

    fig, ax = plt.subplots(figsize=(11, 5.5), dpi=120)
    for name in order:
        ax.plot(nav.index, nav[name], label=name, lw=2.4 if name == MAIN else 1.2)
    ax.set_yscale("log")
    ax.set_title(f"{ID} · research pool · B45+S20+TV25 max5")
    ax.set_ylabel("净值（对数）")
    ax.grid(True, alpha=0.3)
    ax.legend(fontsize=7)
    fig.tight_layout()
    fig.savefig(OUT / "nav.png")
    plt.close(fig)

    base = df[df.book == MAIN].iloc[0]
    grid_lines = []
    for _, r in df.iterrows():
        if r.book == MAIN:
            continue
        dret = (r["ret"] - base["ret"]) * 100
        ddd = (r["maxDD"] - base["maxDD"]) * 100
        dcal = r["Calmar"] - base["Calmar"]
        grid_lines.append(
            f"| {r.book} | cap={int(r['max_hold_weeks'])} | {pct(r['ret'])} | {pct(r['maxDD'])} | "
            f"{r['Calmar']:.2f} | {pct(r['2023-26_ret'])} | {int(r['n_max_hold_exits'])} | "
            f"Δret {dret:+.1f}pp ΔMDD {ddd:+.1f}pp ΔCal {dcal:+.2f} |"
        )

    falsified = []
    for _, r in df.iterrows():
        if r.book == MAIN:
            continue
        if r["ret"] > base["ret"] and r["2023-26_ret"] > base["2023-26_ret"] and r["Calmar"] >= base["Calmar"]:
            falsified.append(r.book)
    verdict = (
        "**未证伪（探索记账）**：无 MH 档同时盖住基准全样本+后段且 Calmar≥基准。"
        if not falsified
        else f"**部分档位盖住基准**：{', '.join(falsified)}（仍不换冠）。"
    )

    approx_md = "\n".join(f"- {a}" for a in cov_stats["approximation"])
    hypo = """## 0. 假设与证伪（开跑前写死）
- **假设**：无 max-hold 的 B45+S20+TV25 max5 基准在后段更优；强加持有上限 4/6/8 周主要降换手、略损收益，Calmar 不系统性优于基准。
- **证伪**：∃MH∈{4,6,8} 全样本 ret 与 2023–26 ret 均盖住基准 **且** Calmar ≥ 基准。
- **红线**：研究池 only；不改 strategy_exec/LIVE/冠军；不合层。
"""

    def row_md(name: str) -> str:
        r = df[df.book == name].iloc[0]
        cap = "—" if pd.isna(r.get("max_hold_weeks")) or r.get("max_hold_weeks") is None else str(int(r["max_hold_weeks"]))
        return (
            f"| {name} | {cap} | {pct(r['ret'])} | {pct(r['maxDD'])} | {r['Calmar']:.2f} | "
            f"{pct(r['2020-22_ret'])}/{pct(r['2020-22_DD'])}/{r['2020-22_Calmar']:.2f} | "
            f"{pct(r['2023-26_ret'])}/{pct(r['2023-26_DD'])}/{r['2023-26_Calmar']:.2f} | {r['avgL']:.2f} |"
        )

    report = hypo + f"""
## 1. 准则
- **面层冻结**：breadth≥45%（face risk_on）+ spike_ft max5 + SHARPE20 填席 + E0 + TV25 L≤1 + 0.2%RT + Fri 14:30 信号 / 收盘成交。
- **唯一改动**：单票连续持有满 **W** 周强制清仓（W∈{{4,6,8}}）；基准 **无上限**。
- **宇宙**：`research_pool_v2` ∩ AUM≥2（n={len(codes)}）；数据 kit `{KIT}`。

## 2. 主表
| book | max_hold周 | ret | maxDD | Calmar | 2020–22 | 2023–26 | avgL |
|---|---:|---:|---:|---:|---|---|---:|
{chr(10).join(row_md(n) for n in order)}

### 网格 vs 基准
| book | cap | ret | maxDD | Calmar | 2023–26 | #max_hold退出 | Δ vs 基准 |
|---|---:|---:|---:|---:|---:|---:|---|
{chr(10).join(grid_lines)}

## 3. 覆盖
{approx_md}

| 项 | 值 |
|---|---|
| 研究池代码数 | {len(codes)} |
| 日历周 | {len(calendar)} |
| 14:30 映射成功 | {n_map} |

## 4. 结论
{verdict}

产物：`{OUT}/`（四件套 metrics/nav/REPORT/ATTRIBUTION）；镜像 `{SYNC_OUT}/`。
耗时 {round(time.time() - t0, 1)}s。
"""
    attr = f"""## 归因 · {ID}

### max-hold 强制退出次数
| book | cap | n_max_hold_exits | n_trades |
|---|---:|---:|---:|
""" + "\n".join(
        f"| {r.book} | {('—' if pd.isna(r.max_hold_weeks) or r.max_hold_weeks is None else int(r.max_hold_weeks))} | {int(r.n_max_hold_exits)} | {int(r.n_trades)} |"
        for _, r in df.iterrows()
    ) + "\n\n### 持仓差 vs 基准\n" + "\n".join(
        f"- {k}: {v['n_diff']}/{v['n']} 周持仓集合不同 ({100*(v['pct_diff'] or 0):.0f}%)"
        for k, v in diffs.items()
    )

    (OUT / "REPORT.md").write_text(report, encoding="utf-8")
    (OUT / "ATTRIBUTION.md").write_text(attr, encoding="utf-8")
    SYNC_OUT.mkdir(parents=True, exist_ok=True)
    for fname in ("metrics.csv", "yearly.csv", "nav.csv", "nav.png", "REPORT.md", "ATTRIBUTION.md"):
        shutil.copy2(OUT / fname, SYNC_OUT / fname)

    (OUT / "summary.json").write_text(
        json.dumps(
            {
                "id": ID,
                "pool": str(RESEARCH_POOL_CSV),
                "n_codes": len(codes),
                "diffs": diffs,
                "sim_stats": sim_stats,
                "verdict": verdict,
                "elapsed_sec": round(time.time() - t0, 1),
            },
            ensure_ascii=False,
            indent=2,
            default=str,
        ),
        encoding="utf-8",
    )
    print("done", OUT, flush=True)
    print(verdict, flush=True)


if __name__ == "__main__":
    main()
