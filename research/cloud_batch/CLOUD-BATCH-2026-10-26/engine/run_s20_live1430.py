#!/usr/bin/env python3
"""SPIKE-SHARPE20-LIVE1430: Fri 14:30 signal / Fri close fill; Sharpe seat fill + neighbors.

Books (same engine):
  LIVE1430-AUM-max5, LIVE1430-SHARPE20-max5 (main), LIVE1430-SHARPE15-max5, LIVE1430-SHARPE25-max5

Frozen: breadth≥45% MA20 (face risk_on) + spike_ft (excl box_pending) + E0 + TV25 L≤1 + 0.2%RT
Unique change: empty spike seats ranked by 近N日 Sharpe (mean/std×√252), max5 EW.

LIVE1430: 14:30-modified weekly classify; empty 14:30 → unselectable; Sharpe window ends
strictly before signal trade_date (no Fri-close look-ahead); PnL fill at daily close.
Sample: 2020-01-03 → 2026-09-24 (14:30 pytdx coverage). Exploration — no crown swap.
Explicit: 14:30 signal (not 11:30 LIVE, not Fri-close explore).
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

OUT = Path("/workspace/strategy-weekly/spike_mom_rank/SPIKE-SHARPE20-LIVE1430")
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
SNAP_CACHE = OUT / "cache_1430_snaps.json"

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

    variants: dict[str, tuple[RankFn, bool, int | None]] = {
        "LIVE1430-AUM-max5": (aum_key, False, None),
        "LIVE1430-SHARPE20-max5": (sharpe_key, True, 20),
        "LIVE1430-SHARPE15-max5": (sharpe_key, True, 15),
        "LIVE1430-SHARPE25-max5": (sharpe_key, True, 25),
    }
    hold_by: dict[str, dict[str, list[str]]] = {}
    sim_stats: dict[str, Any] = {}
    for name, (rfn, req, sn) in variants.items():
        print(f"simulate {name}…", flush=True)
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

    # pick diffs
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
        "SHARPE20_vs_AUM": pick_diff("LIVE1430-AUM-max5", "LIVE1430-SHARPE20-max5"),
        "SHARPE15_vs_AUM": pick_diff("LIVE1430-AUM-max5", "LIVE1430-SHARPE15-max5"),
        "SHARPE25_vs_AUM": pick_diff("LIVE1430-AUM-max5", "LIVE1430-SHARPE25-max5"),
        "SHARPE15_vs_20": pick_diff("LIVE1430-SHARPE20-max5", "LIVE1430-SHARPE15-max5"),
        "SHARPE25_vs_20": pick_diff("LIVE1430-SHARPE20-max5", "LIVE1430-SHARPE25-max5"),
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

    df = pd.DataFrame(table_rows)
    df.to_csv(OUT / "table.csv", index=False)

    # yearly wide
    y = yearly_table(series["LIVE1430-AUM-max5"]).rename(
        columns=lambda c: f"aum_{c}" if c != "year" else c
    )
    for slug, col in [
        ("LIVE1430-SHARPE20-max5", "s20"),
        ("LIVE1430-SHARPE15-max5", "s15"),
        ("LIVE1430-SHARPE25-max5", "s25"),
    ]:
        yi = yearly_table(series[slug]).rename(
            columns=lambda c, p=col: f"{p}_{c}" if c != "year" else c
        )
        y = y.merge(yi, on="year", how="outer")
    y["delta_s20_vs_aum_pp"] = (y["s20_ret"] - y["aum_ret"]) * 100
    y.to_csv(OUT / "yearly.csv", index=False)

    eq = pd.DataFrame({k: (1 + series[k]).cumprod() for k in variants})
    eq.to_csv(OUT / "equity.csv")

    fig, ax = plt.subplots(figsize=(11, 5.5), dpi=120)
    for name, lw, ls in [
        ("LIVE1430-AUM-max5", 1.8, "-"),
        ("LIVE1430-SHARPE20-max5", 1.8, "-"),
        ("LIVE1430-SHARPE15-max5", 1.2, "--"),
        ("LIVE1430-SHARPE25-max5", 1.2, ":"),
    ]:
        ax.plot(eq.index, eq[name], label=name, lw=lw, ls=ls)
    ax.set_yscale("log")
    ax.set_title("SPIKE-SHARPE20-LIVE1430（Fri 14:30 信号 / 收盘成交；探索）")
    ax.set_ylabel("净值（对数）")
    ax.grid(True, alpha=0.3)
    ax.legend(fontsize=8)
    fig.tight_layout()
    fig.savefig(OUT / "equity_curve.png")
    plt.close(fig)

    aum_r = df[df.book == "LIVE1430-AUM-max5"].iloc[0]
    sh_r = df[df.book == "LIVE1430-SHARPE20-max5"].iloc[0]
    s15 = df[df.book == "LIVE1430-SHARPE15-max5"].iloc[0]
    s25 = df[df.book == "LIVE1430-SHARPE25-max5"].iloc[0]
    dret = (sh_r["ret"] - aum_r["ret"]) * 100
    ddd = (sh_r["maxDD"] - aum_r["maxDD"]) * 100
    dcal = sh_r["Calmar"] - aum_r["Calmar"]
    dcagr = (sh_r["CAGR"] - aum_r["CAGR"]) * 100

    # neighbor collapse check
    neighbor_ok = (
        s15["ret"] > aum_r["ret"] * 0.9
        and s25["ret"] > aum_r["ret"] * 0.9
        and abs(s15["Calmar"] - sh_r["Calmar"]) < 0.25
        and abs(s25["Calmar"] - sh_r["Calmar"]) < 0.25
    )
    # "collapse" = neighbors much worse than S20 or fall below AUM badly
    neighbor_collapse = (s15["ret"] < aum_r["ret"] * 0.7) or (s25["ret"] < aum_r["ret"] * 0.7)

    # four-gate style note (exploration only)
    mdd_blocks = sh_r["maxDD"] < aum_r["maxDD"] - 1e-9  # deeper (more negative)
    calmar_not_up = not (sh_r["Calmar"] > aum_r["Calmar"] + 0.02)
    upgrade_blocked = mdd_blocks or calmar_not_up

    if upgrade_blocked:
        verdict = (
            f"**暂停升格 / 探索记账**：LIVE1430（Fri≥14:30 信号）下 SHARPE20 相对同引擎 AUM "
            f"Δret={dret:+.1f}pp、ΔMDD代数差={ddd:+.1f}pp（正=更浅）、ΔCalmar={dcal:+.2f}；"
            + ("回撤更深，" if mdd_blocks else "")
            + ("Calmar 未明显抬升，" if calmar_not_up else "")
            + "探索记账，**不换冠军**。"
        )
    else:
        verdict = (
            f"**探索可继续（仍不换冠）**：LIVE1430 SHARPE20 Δret={dret:+.1f}pp ΔMDD={ddd:+.1f}pp "
            f"ΔCalmar={dcal:+.2f}；须过四闸与邻档稳健后才谈升格。"
        )
    if neighbor_collapse:
        verdict += " 邻档 15/25 相对 AUM 塌缩 → 窗长稳健性失败信号。"
    elif not neighbor_ok:
        verdict += " 邻档 15/25 与 20 分歧偏大，稳健性存疑。"
    else:
        verdict += " 邻档 15/25 未塌缩（非选美，仅稳健旁注）。"

    # pointer to fri-close SPIKE-SHARPE20
    fri_close_note = ""
    fc_table = FRI_CLOSE_REF / "table.csv"
    if fc_table.exists():
        fct = pd.read_csv(fc_table)
        fri_close_note = (
            f"旧周五收盘刀见 `{FRI_CLOSE_REF}/`："
            + ", ".join(
                f"{r.book} ret={pct(float(r.ret))} MDD={pct(float(r.maxDD))} Calmar={float(r.Calmar):.2f}"
                for _, r in fct.iterrows()
            )
            + "（样本含 2016–2019，口径不同，不可直接比绝对值）。"
        )

    summary = {
        "title": "SPIKE-SHARPE20-LIVE1430 Fri 14:30 signal / close fill",
        "convention": "Fri 14:30 signal (pytdx idx209), Friday close fill; TV25 L≤1; 0.2%RT",
        "sample": f"{EVAL_START} → {END_S}",
        "rank": "top max5 by mean(r)/std(r)*√252 over last N trading days ending before signal date; skip if <N or σ=0; EW",
        "coverage": cov_stats,
        "pick_diffs": diffs,
        "sim_stats": sim_stats,
        "table": table_rows,
        "neighbor_collapse": neighbor_collapse,
        "upgrade_blocked": upgrade_blocked,
        "verdict": verdict,
        "elapsed_sec": round(time.time() - t0, 1),
    }
    (OUT / "summary.json").write_text(
        json.dumps(summary, ensure_ascii=False, indent=2, default=str), encoding="utf-8"
    )

    (OUT / "criterion.md").write_text(
        "# Criterion · SPIKE-SHARPE20-LIVE1430\n\n"
        "- **主刀唯一改动**：spike_ft 空席排序 (−AUM) → **近 N 日 Sharpe**（mean/std×√252）；主 N=20；邻档 15/25。\n"
        "- **冻结**：breadth≥45% MA20（**face** `holdings_ro2_from2016` risk_on）、enter_kinds={spike_ft} 排除 box_pending、"
        "等权、TV25 L=min(1,0.25/max(σ20,σ60))、0.2%RT。\n"
        "- **成交约定（主表）**：**周五 ≥14:30 / 14:30 信号**、**当日（周末交易日）收盘成交**；非 11:30 LIVE、非周五收盘探索。\n"
        "- **样本**：2020-01-03→2026-09-24（pytdx 14:30 CSV）；不假装 2016–2019 有 LIVE 14:30。\n"
        "- **14:30 价**：`fri_1430_through_20260925.csv`（pytdx idx209）；空/无法映射 → 该周该码不可选。\n"
        "- **Sharpe 窗**：截至信号日**严格前一交易日**（无周五收盘前视）。\n"
        "- **不换冠**；INVVOL 不在本包。\n",
        encoding="utf-8",
    )

    def row_md(name: str) -> str:
        r = df[df.book == name].iloc[0]
        return (
            f"| {name} | {pct(r['ret'])} | {pct(r['maxDD'])} | {pct(r['CAGR'])} | {r['Calmar']:.2f} | "
            f"{pct(r['2020-22_ret'])}/{pct(r['2020-22_DD'])}/{r['2020-22_Calmar']:.2f} | "
            f"{pct(r['2023-26_ret'])}/{pct(r['2023-26_DD'])}/{r['2023-26_Calmar']:.2f} | {r['avgL']:.2f} |"
        )

    y_lines = [
        "| 年 | AUM | S20 | Δpp | S15 | S25 | AUM MDD | S20 MDD |",
        "|---|---:|---:|---:|---:|---:|---:|---:|",
    ]
    for _, row in y.iterrows():
        y_lines.append(
            f"| {int(row.year)} | {pct(float(row.aum_ret)) if pd.notna(row.aum_ret) else '—'} | "
            f"{pct(float(row.s20_ret)) if pd.notna(row.s20_ret) else '—'} | "
            f"{float(row.delta_s20_vs_aum_pp):+.1f} | "
            f"{pct(float(row.s15_ret)) if pd.notna(row.s15_ret) else '—'} | "
            f"{pct(float(row.s25_ret)) if pd.notna(row.s25_ret) else '—'} | "
            f"{pct(float(row.aum_mdd)) if pd.notna(row.aum_mdd) else '—'} | "
            f"{pct(float(row.s20_mdd)) if pd.notna(row.s20_mdd) else '—'} |"
        )

    approx_md = "\n".join(f"- {a}" for a in cov_stats["approximation"])
    d20 = diffs["SHARPE20_vs_AUM"]

    report = f"""# REPORT · SPIKE-SHARPE20-LIVE1430（Fri 14:30 信号 / 收盘成交）

## 设定

- **主刀**：空席按近 **20** 交易日 Sharpe（mean/std×√252）填 max5 等权；对照同引擎 **LIVE1430-AUM-max5**。
- **邻档（稳健，非选美）**：SHARPE15 / SHARPE25。
- **冻结**：face breadth risk_on + spike_ft（excl box_pending）+ E0 + TV25 L≤1 + 0.2%RT。
- **约定（主表第一行口径）**：**周五 14:30 信号 → 周末交易日收盘成交**（非 11:30、非周五收盘探索）。
- **样本**：{EVAL_START}→{END_S}（pytdx 14:30 覆盖；无 2016–2019 LIVE 14:30）。
- **不换冠军**；本包不开 INVVOL。

## 近似与覆盖（必读）

{approx_md}

| 覆盖 | 值 |
|---|---|
| 可投池（AUM≥2亿） | {len(codes)} |
| 日历周 | {len(calendar)} |
| listed 行 14:30 非空率 | {100*nonnull_rate:.1f}% |
| 成功映射 qfq_1430 | {n_map} |
| 映射失败（无 sina/qfq） | {n_skip} |
| SHARPE20 有候选周 | {sim_stats['LIVE1430-SHARPE20-max5']['n_fridays_with_cands']} |
| SHARPE20 vs AUM 持仓差异周 | {d20['n_diff']}/{d20['n']} ({100*(d20['pct_diff'] or 0):.0f}%) |

## 主表（LIVE1430 · Fri 14:30 信号）

| book | ret | maxDD | CAGR | Calmar | 2020–22 ret/DD/Calmar | 2023–26 ret/DD/Calmar | avgL |
|---|---:|---:|---:|---:|---|---|---:|
{row_md("LIVE1430-AUM-max5")}
{row_md("LIVE1430-SHARPE20-max5")}
{row_md("LIVE1430-SHARPE15-max5")}
{row_md("LIVE1430-SHARPE25-max5")}

## Δ · LIVE1430-SHARPE20 vs LIVE1430-AUM

| | |
|---|---|
| Δ总收益 | {dret:+.1f}pp |
| ΔMDD（代数差；正=更浅） | {ddd:+.1f}pp |
| ΔCAGR | {dcagr:+.2f}pp |
| ΔCalmar | {dcal:+.2f} |

## 邻档一句话

- S15：ret={pct(float(s15['ret']))} MDD={pct(float(s15['maxDD']))} Calmar={float(s15['Calmar']):.2f}
- S25：ret={pct(float(s25['ret']))} MDD={pct(float(s25['maxDD']))} Calmar={float(s25['Calmar']):.2f}
- 相对 S20：{"邻档未塌缩" if not neighbor_collapse else "邻档塌缩（稳健性失败）"}；持仓差周 15vs20={diffs['SHARPE15_vs_20']['n_diff']}/{diffs['SHARPE15_vs_20']['n']}，25vs20={diffs['SHARPE25_vs_20']['n_diff']}/{diffs['SHARPE25_vs_20']['n']}。

## 分段

| 段 | AUM ret/DD/Calmar | S20 ret/DD/Calmar |
|---|---|---|
| 2020–22 | {pct(float(aum_r['2020-22_ret']))} / {pct(float(aum_r['2020-22_DD']))} / {float(aum_r['2020-22_Calmar']):.2f} | {pct(float(sh_r['2020-22_ret']))} / {pct(float(sh_r['2020-22_DD']))} / {float(sh_r['2020-22_Calmar']):.2f} |
| 2023–26 | {pct(float(aum_r['2023-26_ret']))} / {pct(float(aum_r['2023-26_DD']))} / {float(aum_r['2023-26_Calmar']):.2f} | {pct(float(sh_r['2023-26_ret']))} / {pct(float(sh_r['2023-26_DD']))} / {float(sh_r['2023-26_Calmar']):.2f} |

## 历年

{chr(10).join(y_lines)}

## 旧周五收盘刀指针

{fri_close_note or "见 `/workspace/strategy-weekly/spike_mom_rank/SPIKE-SHARPE20/`。"}

## 结论（探索记账，不换冠）

{verdict}

权重轴 INVVOL 已于 2026-10-14 在冠军等权上证伪；本包未重开。若 LIVE 仍「收益好、回撤深」，下一刀优先考虑持仓缓冲（K2），非再搜 N。

## 产物

- `run.py` / `criterion.md` / `REPORT.md` / `OPT_PLAN.md` / `equity_curve.png`
- `table.csv` / `yearly.csv` / `equity.csv` / `summary.json`
- `holdings_LIVE-*.csv` / `trades_LIVE-*.csv` / `entries_*.csv`
- `cache_1430_snaps.json`（14:30 重分类缓存）
- 对照：`SPIKE-SHARPE20-LIVE/` = Fri 11:30；`SPIKE-SHARPE20/` = Fri-close explore

耗时约 {summary['elapsed_sec']}s。
"""
    (OUT / "REPORT.md").write_text(report, encoding="utf-8")
    print("done", OUT, flush=True)
    print(verdict, flush=True)


if __name__ == "__main__":
    main()
