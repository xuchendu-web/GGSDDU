#!/usr/bin/env python3
"""ma200-abs-gate: B45 + spike_ft max5 + E0 + TV25 + SHARPE20 + 周频 SMA 绝对趋势闸（研究池，不换冠）。"""
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

ROOT = Path(__file__).resolve().parent
KIT = ROOT.parent / "cloud_batch" / "CLOUD-BATCH-2026-10-26"
SCRIPTS = KIT / "scripts"
sys.path.insert(0, str(SCRIPTS))

from backtest import KEEP, LIVE_PHASE, MIN_BARS, Position, nearest_date, snap_index  # noqa: E402
from build_scan import Bar, classify  # noqa: E402

OUT = ROOT / "out"
CACHE = KIT / "data" / "research_cache"
UNI_CSV = KIT / "data" / "universe_replace_only_436.csv"
WEEK = CACHE / "week"
FACE = CACHE / "holdings_ro2_extended.csv"
DAY_DIR = CACHE / "day"
TEMA_PX = Path("/workspace/tema_etf_scan_2018/prices_daily")  # optional overlay
NOON_CSV = CACHE / "fri_1430_through_20261023.csv"
SINA_DAILY = CACHE / "sina_daily"
SNAP_CACHE = KIT / "data" / "cache_1430_snaps.json"
SOURCE_SHA = "05f0f8a4f778fde886f3e7b2976646ff4b7d777b"
BREADTH_THETA = 0.45
PROXY_CANDIDATES = {"hs300": ["000300", "510300"], "csi500": ["000905", "510500"]}
BOOK_SPECS = [
    ("F0", "LIVE1430-MA-off-B45-TV25", None, None),
    ("MA40-HS300", "LIVE1430-MA40-HS300-B45-TV25", 40, "hs300"),
    ("MA30-HS300", "LIVE1430-MA30-HS300-B45-TV25", 30, "hs300"),
    ("MA50-HS300", "LIVE1430-MA50-HS300-B45-TV25", 50, "hs300"),
    ("MA40-CSI500", "LIVE1430-MA40-CSI500-B45-TV25", 40, "csi500"),
]
ANCHOR_RET, ANCHOR_MDD, ANCHOR_CALMAR = 1.316, -0.188, 0.70
ANCHOR_N_WEEKS, ANCHOR_T, ANCHOR_N_CODES, ANCHOR_N_CASH = 349, 348, 324, 150
DECISION_LINE = (
    "请拍板：维持面层 B45 + spike_ft max5 + E0 + TV25 + SHARPE20，只在组合 risk_on 上 **AND** "
    "一道沪深300（或 kit 内 510300）周收 > 40 周 SMA 的绝对趋势闸；闸关则 100% 现金桩。无论记正与否都不换冠。"
)
H1_BLOCK = """```
唯一改动：在面层 B45 + spike_ft max5 + E0 + TV25 + SHARPE20 上，
把 risk_on 改成 (b ≥ 0.45) AND (C_t > SMA_N(代理))。
  主代理锁 CSI300（000300 否则 510300，同一跑不混）。
  N ∈ {关, 30, 40, 50}。四件套 4 本。
  CSI500 × MA40 只作代理旁注，不进 H1。
  闸关 100% 现金桩。出场维持 E0。B、TV、席位、成本不离开面。

H1：MA30-HS300 / MA40-HS300 / MA50-HS300 在严格尺子下相对本次 F0 全部证伪。
  任一记正 → H1 证伪（家族记一笔，不换冠）。
  全部证伪 → H1 成立。
  主簿 MA40 惰性（n_ma_off_breadth_on = 0，或与 F0 逐周持仓相同）
    → 该本记「证伪·惰性」，不能记正。
```"""

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


def abs_on(weekly_closes: pd.Series, d: str, n: int) -> bool:
    ts = pd.Timestamp(d)
    sub = weekly_closes.loc[:ts]
    if len(sub) < n:
        return False
    if (ts - sub.index[-1]).days > 5:
        return False
    window = sub.iloc[-n:]
    c = float(window.iloc[-1])
    sma = float(window.mean())
    if not (np.isfinite(c) and np.isfinite(sma)):
        return False
    return c > sma


def run_abs_fixtures() -> None:
    cases = [
        ([10, 11, 12, 13], True),
        ([13, 12, 11, 10], False),
        ([10, 10, 10, 10], False),
    ]
    for vals, want in cases:
        idx = pd.date_range("2020-01-03", periods=len(vals), freq="7D")
        s = pd.Series(vals, index=idx, dtype=float)
        if abs_on(s, str(idx[-1].date()), 4) != want:
            raise SystemExit(f"abs_on fixture failed for {vals}")
    idx3 = pd.date_range("2020-01-03", periods=3, freq="7D")
    s3 = pd.Series([10, 11, 12], index=idx3, dtype=float)
    if abs_on(s3, str(idx3[-1].date()), 4):
        raise SystemExit("abs_on short-length fixture failed")


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
    risk_on_b45_by_fri: dict[str, bool] | None = None,
) -> tuple[list[dict[str, Any]], dict[str, list[str]], dict[str, list[str]], dict[str, Any]]:
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
        risk_on = False if last_bar else bool(risk_on_by_fri.get(d, False))
        b45_on = False if last_bar else bool(
            (risk_on_b45_by_fri or risk_on_by_fri).get(d, False)
        )

        exiting: list[tuple[str, str, float]] = []
        for code, p in list(positions.items()):
            px = px_on(code, d)
            if last_bar:
                exiting.append((code, "eod_eval", px if px is not None else p.last_px))
                continue
            if not risk_on:
                reason = "abs_trend_off" if b45_on else "breadth_off"
                exiting.append((code, reason, px if px is not None else p.last_px))
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
    }
    return trades, hold, picks, stats


def run_live_tv(
    hold: dict[pd.Timestamp, list[str]], days: pd.DatetimeIndex, px: pd.DataFrame, R: pd.DataFrame
) -> tuple[pd.Series, pd.Series, float]:
    reb = sorted(hold)
    rp = pd.Series(0.0, index=days)
    Ls = pd.Series(0.0, index=days)
    prev: dict[str, float] = {}
    cst = pd.Series(0.0, index=days)
    R2 = R.reindex(days)
    turnovers: list[float] = []

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
        turnovers.append(to / 2.0)
        prev = wt
        if d in cst.index:
            cst.loc[d] = to * LIVE_COST_RT / 2
        if w and len(seg):
            rp.loc[seg] = (R2.loc[seg, list(w)].fillna(0) @ pd.Series(w)).values
            Ls.loc[seg] = L
    r = rp * Ls - cst
    avg_to = float(np.mean(turnovers)) if turnovers else 0.0
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
        return "—"
    return f"{100 * x:.1f}%"


# appended to run.py — content starts at def load_proxy_weekly


def load_proxy_weekly(
    role: str,
    noon_rows: pd.DataFrame,
    daily: dict[str, pd.Series],
    closes_w: dict[str, dict[str, float]],
    sina: dict[str, dict[str, float]],
) -> tuple[pd.Series, str]:
    for code in PROXY_CANDIDATES[role]:
        fp = WEEK / f"{code}.json"
        if not fp.exists():
            continue
        rec = json.loads(fp.read_text(encoding="utf-8"))
        bars = rec.get("bars") or []
        closes: dict[str, float] = {}
        for b in bars:
            d = str(b["date"])[:10]
            c = float(b["c"])
            if c > 0:
                closes[d] = c
        sub = noon_rows[noon_rows["code"] == code]
        for r in sub.itertuples():
            td = str(r.trade_date)[:10]
            if r.status != "ok" or r.price_1130 is None or (
                isinstance(r.price_1130, float) and math.isnan(r.price_1130)
            ):
                continue
            q = qfq_close_on(code, td, daily, closes_w)
            b = (sina.get(code) or {}).get(td)
            if not q or not b or b <= 0:
                continue
            qn = float(r.price_1130) * (q / b)
            wk = str(r.friday_week_date)[:10]
            closes[wk] = qn
        if not closes:
            continue
        idx = pd.to_datetime(sorted(closes))
        ser = pd.Series([closes[d.strftime("%Y-%m-%d")] for d in idx], index=idx, dtype=float)
        return ser.sort_index(), code
    raise SystemExit(f"BLOCKED: no proxy weekly file for role {role}")


def proxy_close_on(ser: pd.Series, d: str) -> float | None:
    ts = pd.Timestamp(d)
    if ts in ser.index:
        return float(ser.loc[ts])
    sub = ser.loc[:ts]
    if len(sub) and (ts - sub.index[-1]).days <= 5:
        return float(sub.iloc[-1])
    return None


def build_gate_maps(
    calendar: list[str],
    weekly: pd.Series,
    n: int | None,
    risk_b45: dict[str, bool],
) -> tuple[dict[str, bool], dict[str, bool], dict[str, bool]]:
    abs_by: dict[str, bool] = {}
    for d in calendar:
        if n is None:
            abs_by[d] = True
        else:
            abs_by[d] = abs_on(weekly, d, n)
    risk_on = {d: bool(risk_b45.get(d) and abs_by[d]) for d in calendar}
    risk_on[calendar[-1]] = False
    return abs_by, risk_on, risk_b45


def gate_quality(
    calendar: list[str], abs_by: dict[str, bool], risk_b45: dict[str, bool]
) -> dict[str, int]:
    sig = calendar[:-1]
    n_ma_off = sum(1 for d in sig if not abs_by.get(d, False))
    n_breadth_off = sum(1 for d in sig if not risk_b45.get(d, False))
    n_ma_off_breadth_on = sum(1 for d in sig if risk_b45.get(d) and not abs_by.get(d, False))
    n_both_off = sum(1 for d in sig if not risk_b45.get(d) and not abs_by.get(d, False))
    return {
        "n_ma_off": n_ma_off,
        "n_breadth_off": n_breadth_off,
        "n_ma_off_breadth_on": n_ma_off_breadth_on,
        "n_both_off": n_both_off,
    }


def entry_quality(
    calendar: list[str],
    picks: dict[str, list[str]],
    hold: dict[str, list[str]],
    closes_w: dict[str, dict[str, float]],
    alias: dict[str, dict[str, str]],
) -> tuple[float, float]:
    rets: list[float] = []
    prev: set[str] = set()
    sig = calendar[:-1]
    for i, d in enumerate(sig):
        cur = set(hold.get(d) or [])
        new_codes = [c for c in (picks.get(d) or []) if c not in prev]
        nxt = sig[i + 1] if i + 1 < len(sig) else None
        for code in new_codes:
            if not nxt:
                continue
            d0 = (alias.get(code) or {}).get(d) or d
            d1 = (alias.get(code) or {}).get(nxt) or nxt
            p0 = closes_w.get(code, {}).get(d0)
            p1 = closes_w.get(code, {}).get(d1)
            if p0 and p1 and p0 > 0:
                rets.append(float(p1 / p0 - 1.0))
        prev = cur
    if not rets:
        return 0.0, 0.0
    wins = [r for r in rets if r > 0]
    hit = len(wins) / len(rets)
    win_size = float(np.mean(wins)) if wins else 0.0
    return hit, win_size


def window_slice(r: pd.Series, start: str, end: str | None) -> pd.Series:
    if end:
        return r[(r.index >= start) & (r.index <= end)]
    return r[r.index >= start]


def anchor_pass(f0: dict[str, Any], n_weeks: int, n_codes: int) -> bool:
    if abs(f0["ret"] - ANCHOR_RET) > 0.005:
        return False
    if abs(f0["maxDD"] - ANCHOR_MDD) > 0.002:
        return False
    if abs(f0["Calmar"] - ANCHOR_CALMAR) > 0.02:
        return False
    if n_weeks != ANCHOR_N_WEEKS:
        return False
    if f0.get("n_calendar_weeks_ex_last", 0) != ANCHOR_T:
        return False
    if n_codes != ANCHOR_N_CODES:
        return False
    if abs(f0["n_cash_weeks"] - ANCHOR_N_CASH) > 2:
        return False
    if f0.get("calendar_end") != END_S:
        return False
    return True


def ruler_cell(cell: dict[str, Any], f0: dict[str, Any], blocked: bool) -> None:
    if blocked:
        cell["verdict"] = "BLOCKED"
        return
    if cell["id"] == "F0":
        cell["verdict"] = "ANCHOR"
        cell["covers"] = True
        cell["window_2020_22"] = True
        cell["window_2023_26"] = True
        cell["inert"] = False
        return
    if cell["id"] == "MA40-CSI500":
        if cell["inert"]:
            cell["verdict"] = "旁注-证伪"
        elif cell["covers"] and cell["window_2020_22"] and cell["window_2023_26"]:
            cell["verdict"] = "旁注-记正"
        else:
            cell["verdict"] = "旁注-证伪"
        return
    if cell["inert"]:
        cell["verdict"] = "证伪"
        return
    if cell["covers"] and cell["window_2020_22"] and cell["window_2023_26"]:
        cell["verdict"] = "记正"
    else:
        cell["verdict"] = "证伪"


def main() -> None:
    run_abs_fixtures()
    OUT.mkdir(parents=True, exist_ok=True)
    t0 = time.time()
    for p in (WEEK, FACE, DAY_DIR, NOON_CSV, SINA_DAILY, SNAP_CACHE):
        if not Path(p).exists():
            raise SystemExit(f"missing research cache path {p}")

    print("load universe + extended 14:30 + week…", flush=True)
    uni = pd.read_csv(UNI_CSV)
    uni["code"] = uni["code"].astype(str).str.zfill(6)
    uni = uni[uni["aum"] >= 2].copy()
    codes = uni["code"].tolist()
    aum = {r.code: float(r.aum or 0) for r in uni.itertuples()}
    code_set = set(codes)
    if len(codes) != ANCHOR_N_CODES:
        print(f"warn: n_codes={len(codes)} expected {ANCHOR_N_CODES}", flush=True)

    noon = pd.read_csv(NOON_CSV)
    noon["code"] = noon["etf_code"].astype(str).str.split(".").str[0].str.zfill(6)
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
    if actual_end != END_S:
        raise SystemExit(f"calendar end {actual_end} != {END_S}")
    if len(calendar) != ANCHOR_N_WEEKS:
        raise SystemExit(f"calendar weeks {len(calendar)} != {ANCHOR_N_WEEKS}")
    print(f"calendar {calendar[0]} → {actual_end} n={len(calendar)}", flush=True)

    risk_b45: dict[str, bool] = {}
    breadth_b: dict[str, float] = {}
    for _, row in face.iterrows():
        d = str(row["date"])[:10]
        bv = row.get("b")
        if bv is not None and not (isinstance(bv, float) and math.isnan(bv)):
            breadth_b[d] = float(bv)
            risk_b45[d] = float(bv) >= BREADTH_THETA
        else:
            risk_b45[d] = False
    risk_b45[calendar[-1]] = False

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
    print(f"daily series: {len(daily)}/{len(codes)}", flush=True)

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

    cached = json.loads(SNAP_CACHE.read_text(encoding="utf-8"))
    by_rows = cached.get("by_code") or {}
    snaps = {c: snap_index(by_rows.get(c) or []) for c in codes}

    proxy_daily = load_daily_closes(
        list({c for xs in PROXY_CANDIDATES.values() for c in xs}), sina
    )
    proxy_closes_w = {}
    for pc in {c for xs in PROXY_CANDIDATES.values() for c in xs}:
        fp = WEEK / f"{pc}.json"
        if fp.exists():
            rec = json.loads(fp.read_text(encoding="utf-8"))
            proxy_closes_w[pc] = {
                b["date"]: float(b["c"])
                for b in (rec.get("bars") or [])
                if b.get("date") and float(b["c"]) > 0
            }

    weekly_hs300, proxy_hs300 = load_proxy_weekly(
        "hs300", noon, proxy_daily, proxy_closes_w, sina
    )
    weekly_csi500, proxy_csi500 = load_proxy_weekly(
        "csi500", noon, proxy_daily, proxy_closes_w, sina
    )
    if proxy_hs300 != proxy_csi500 and proxy_hs300[:3] == proxy_csi500[:3]:
        pass
    print(f"proxy HS300={proxy_hs300} CSI500={proxy_csi500}", flush=True)

    proxy_blocked = False
    miss_hs = sum(
        1
        for d in calendar[:-1]
        if proxy_close_on(weekly_hs300, d) is None
    )
    if miss_hs > 2:
        print(f"BLOCKED: HS300 proxy missing {miss_hs} signal weeks", flush=True)
        proxy_blocked = True

    weekly_by_role = {"hs300": weekly_hs300, "csi500": weekly_csi500}

    variants: dict[str, tuple[dict[str, bool], dict[str, bool], int | None, str | None]] = {}
    gate_diag: dict[str, dict[str, Any]] = {}
    for bid, book, n_ma, role in BOOK_SPECS:
        wk = weekly_by_role[role] if role else weekly_hs300
        abs_by, risk_on, _ = build_gate_maps(calendar, wk, n_ma, risk_b45)
        variants[book] = (risk_on, abs_by, n_ma, role)
        gq = gate_quality(calendar, abs_by, risk_b45)
        gate_diag[book] = {"abs_by": abs_by, "gq": gq, "n_ma": n_ma, "role": role}

    hold_by: dict[str, dict[str, list[str]]] = {}
    picks_by: dict[str, dict[str, list[str]]] = {}
    sim_stats: dict[str, Any] = {}
    for bid, book, n_ma, role in BOOK_SPECS:
        risk_on, abs_by, _, _ = variants[book]
        print(f"simulate {book}…", flush=True)
        trades, hold, picks, st = simulate(
            calendar,
            snaps,
            closes_w_sig,
            alias,
            aum,
            daily,
            risk_on,
            sharpe_key,
            book,
            True,
            20,
            5,
            risk_b45,
        )
        st["calendar_end"] = actual_end
        hold_by[book] = hold
        picks_by[book] = picks
        sim_stats[book] = st
        rows = []
        for d in calendar[:-1]:
            c_ = proxy_close_on(weekly_by_role[role] if role else weekly_hs300, d)
            sub = weekly_by_role[role] if role else weekly_hs300
            sma_v = float("nan")
            if n_ma and c_ is not None:
                ts = pd.Timestamp(d)
                subw = sub.loc[:ts]
                if len(subw) >= n_ma:
                    sma_v = float(subw.iloc[-n_ma:].mean())
            rows.append(
                {
                    "date": d,
                    "b": breadth_b.get(d),
                    "risk_on_B45": int(risk_b45.get(d, False)),
                    "abs_on": int(abs_by.get(d, False)),
                    "risk_on": int(risk_on.get(d, False)),
                    "proxy_c": c_,
                    "sma": sma_v,
                }
            )
        pd.DataFrame(rows).to_csv(OUT / f"gate_weeks_{bid}.csv", index=False)
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
    print(f"live days {days[0].date()} → {days[-1].date()} n={len(days)}", flush=True)

    f0_book = BOOK_SPECS[0][1]
    series: dict[str, pd.Series] = {}
    cells: list[dict[str, Any]] = []
    f0_metrics: dict[str, Any] = {}

    for bid, book, n_ma, role in BOOK_SPECS:
        hd = {pd.Timestamp(d): cs for d, cs in hold_by[book].items()}
        r, L, avg_to = run_live_tv(hd, days, px, R)
        series[book] = r
        st = stats_full(r)
        w22 = stats_full(window_slice(r, "2020-01-01", "2022-12-31"))
        w26 = stats_full(window_slice(r, "2023-01-01", None))
        sim = sim_stats[book]
        gq = gate_diag[book]["gq"]
        hit, wsz = entry_quality(calendar, picks_by[book], hold_by[book], closes_w_sig, alias)
        proxy_code = None if bid == "F0" else (proxy_hs300 if role == "hs300" else proxy_csi500)
        cell: dict[str, Any] = {
            "id": bid,
            "book": book,
            "N": n_ma,
            "proxy": proxy_code,
            "ret": st["ret"],
            "maxDD": st["maxDD"],
            "CAGR": st["CAGR"],
            "Calmar": st["Calmar"],
            "avgL": float(L[L > 0].mean()) if (L > 0).any() else 0.0,
            "avg_turnover_1way": avg_to,
            "n_cash_weeks": sim["n_cash_weeks"],
            **gq,
            "n_entries": sim["n_entries"],
            "hit_rate": hit,
            "win_size": wsz,
            "w2020_22": w22,
            "w2023_26": w26,
            "delta_ret": 0.0,
            "delta_abs_mdd": 0.0,
            "covers": False,
            "window_2020_22": False,
            "window_2023_26": False,
            "inert": False,
            "verdict": "证伪",
        }
        if bid == "F0":
            f0_metrics = {**cell, **sim}
        cells.append(cell)

    f0 = next(c for c in cells if c["id"] == "F0")
    hold_f0 = hold_by[f0_book]
    for cell in cells:
        if cell["id"] == "F0":
            cell["delta_ret"] = 0.0
            cell["delta_abs_mdd"] = 0.0
            continue
        cell["delta_ret"] = float(cell["ret"] - f0["ret"])
        cell["delta_abs_mdd"] = float(abs(cell["maxDD"]) - abs(f0["maxDD"]))
        cell["covers"] = cell["delta_ret"] >= cell["delta_abs_mdd"]
        cell["window_2020_22"] = cell["w2020_22"]["ret"] >= f0["w2020_22"]["ret"]
        cell["window_2023_26"] = cell["w2023_26"]["ret"] >= f0["w2023_26"]["ret"]
        gq = gate_diag[cell["book"]]["gq"]
        same_hold = all(
            set(hold_by[cell["book"]].get(d) or []) == set(hold_f0.get(d) or [])
            for d in calendar[:-1]
        )
        cell["inert"] = gq["n_ma_off_breadth_on"] == 0 or same_hold

    blocked = proxy_blocked or not anchor_pass(
        {**f0, **sim_stats[f0_book]}, len(calendar), len(codes)
    )
    anchor_ok = not blocked and anchor_pass(
        {**f0, **sim_stats[f0_book]}, len(calendar), len(codes)
    )
    if not anchor_ok and not proxy_blocked:
        print(
            f"anchor fail F0 ret={f0['ret']:.4f} mdd={f0['maxDD']:.4f} cal={f0['Calmar']:.2f} "
            f"cash={f0['n_cash_weeks']}",
            flush=True,
        )

    for cell in cells:
        ruler_cell(cell, f0, blocked)

    hs300_cells = [c for c in cells if c["id"].endswith("-HS300")]
    positive_ids = [c["id"] for c in hs300_cells if c["verdict"] == "记正"]
    if blocked:
        family_verdict = "BLOCKED"
        h1 = "BLOCKED"
    elif positive_ids:
        family_verdict = "H1_REJECT"
        h1 = f"MA30/MA40/MA50-HS300 记正: {', '.join(positive_ids)}"
    else:
        family_verdict = "H1_HOLD"
        h1 = "MA30/MA40/MA50-HS300 all 证伪"

    # equity long + png
    eq_rows = []
    nav_by_book = {}
    for bid, book, _, _ in BOOK_SPECS:
        nav = (1 + series[book]).cumprod()
        nav_by_book[book] = nav
        for dt, v in nav.items():
            eq_rows.append({"date": dt.strftime("%Y-%m-%d"), "book": book, "nav": float(v)})
    pd.DataFrame(eq_rows).to_csv(OUT / "equity.csv", index=False)

    fig, ax = plt.subplots(figsize=(11, 5.5), dpi=120)
    f0_name = BOOK_SPECS[0][1]
    ax.plot(nav_by_book[f0_name].index, nav_by_book[f0_name], color="black", lw=2.2, label=f0_name)
    for bid, book, _, role in BOOK_SPECS[1:]:
        if role == "hs300":
            ax.plot(nav_by_book[book].index, nav_by_book[book], color="gray", lw=1.0, ls="-", label=book)
    ax.set_yscale("log")
    ax.set_title("ma200-abs-gate（F0 黑线；HS300 灰线）")
    ax.set_ylabel("净值（对数）")
    ax.grid(True, alpha=0.3)
    ax.legend(fontsize=7)
    fig.tight_layout()
    fig.savefig(OUT / "equity_curve.png")
    plt.close(fig)

    # table.csv
    csv_rows = []
    for cell in cells:
        csv_rows.append(
            {
                "id": cell["id"],
                "book": cell["book"],
                "N": "off" if cell["N"] is None else cell["N"],
                "proxy": "off" if cell["proxy"] is None else cell["proxy"],
                "ret": cell["ret"],
                "maxDD": cell["maxDD"],
                "CAGR": cell["CAGR"],
                "Calmar": cell["Calmar"],
                "w2020_22_ret": cell["w2020_22"]["ret"],
                "w2020_22_maxDD": cell["w2020_22"]["maxDD"],
                "w2020_22_Calmar": cell["w2020_22"]["Calmar"],
                "w2023_26_ret": cell["w2023_26"]["ret"],
                "w2023_26_maxDD": cell["w2023_26"]["maxDD"],
                "w2023_26_Calmar": cell["w2023_26"]["Calmar"],
                "avgL": cell["avgL"],
                "avg_turnover_1way": cell["avg_turnover_1way"],
                "n_cash_weeks": cell["n_cash_weeks"],
                "n_ma_off": cell["n_ma_off"],
                "n_breadth_off": cell["n_breadth_off"],
                "n_ma_off_breadth_on": cell["n_ma_off_breadth_on"],
                "n_both_off": cell["n_both_off"],
                "n_entries": cell["n_entries"],
                "hit_rate": cell["hit_rate"],
                "win_size": cell["win_size"],
                "delta_ret": cell["delta_ret"],
                "delta_abs_mdd": cell["delta_abs_mdd"],
                "covers": str(cell["covers"]).lower(),
                "window_2020_22": str(cell["window_2020_22"]).lower(),
                "window_2023_26": str(cell["window_2023_26"]).lower(),
                "inert": str(cell["inert"]).lower(),
                "verdict": cell["verdict"],
            }
        )
    pd.DataFrame(csv_rows).to_csv(OUT / "table.csv", index=False)

    summary = {
        "batch": "ma200-abs-gate",
        "champion_swap": False,
        "crown": "NO",
        "source_sha": SOURCE_SHA,
        "sample": [EVAL_START, END_S],
        "anchor_pass": anchor_ok,
        "anchor": {
            "ret": f0["ret"],
            "maxDD": f0["maxDD"],
            "Calmar": f0["Calmar"],
            "n_weeks": len(calendar),
            "T": len(calendar) - 1,
            "n_codes": len(codes),
            "n_cash_weeks": f0["n_cash_weeks"],
        },
        "face_id": "F0",
        "proxy_econ_hs300": "CSI300",
        "proxy_used_hs300": proxy_hs300,
        "proxy_econ_csi500": "CSI500",
        "proxy_used_csi500": proxy_csi500,
        "h1": h1,
        "family_verdict": family_verdict,
        "positive_ids": positive_ids,
        "cells": cells,
    }
    (OUT / "summary.json").write_text(
        json.dumps(summary, ensure_ascii=False, indent=2, default=str), encoding="utf-8"
    )

    def md_row(c: dict[str, Any]) -> str:
        return (
            f"| {c['id']} | {pct(c['ret'])} | {pct(c['maxDD'])} | {c['Calmar']:.2f} | "
            f"{pct(c['w2020_22']['ret'])} | {pct(c['w2023_26']['ret'])} | "
            f"{c['n_ma_off_breadth_on']} | {c['verdict']} |"
        )

    report = f"""# REPORT · ma200-abs-gate

{DECISION_LINE}

{H1_BLOCK}

## 锚点门

- F0：ret {pct(f0['ret'])} / maxDD {pct(f0['maxDD'])} / Calmar {f0['Calmar']:.2f}；空仓周 {f0['n_cash_weeks']} / T={len(calendar)-1}
- anchor_pass：**{anchor_ok}**（对照 131.6% / −18.8% / 0.70 @ `{SOURCE_SHA[:8]}`）
- 代理：HS300 `{proxy_hs300}`；CSI500 `{proxy_csi500}`
- family_verdict：**{family_verdict}**（不换冠）

## 主表

| id | ret | maxDD | Calmar | 2020-22 | 2023-26 | n_ma_off_breadth_on | verdict |
|----|-----|-------|--------|---------|---------|---------------------|---------|
{chr(10).join(md_row(c) for c in cells)}

## Δ 表（相对 F0）

| id | Δret | Δ|MDD| | covers | 2020-22 | 2023-26 | inert | verdict |
|----|------|--------|--------|---------|---------|-------|---------|
"""
    for c in cells:
        if c["id"] == "F0":
            continue
        report += (
            f"| {c['id']} | {100*c['delta_ret']:+.1f}pp | {100*c['delta_abs_mdd']:+.1f}pp | "
            f"{c['covers']} | {c['window_2020_22']} | {c['window_2023_26']} | {c['inert']} | {c['verdict']} |\n"
        )

    report += f"""
## 闸质量旁注

- n_ma_off / n_breadth_off / n_both_off 见 `table.csv`；增量现金周 `n_ma_off_breadth_on` 已入主表。
- hit_rate / win_size 仅披露，不进 verdict（惰性除外）。

## 证伪段

- **{family_verdict}**：{h1}。champion_swap=false，不换冠。
- 记正尺子：Δret ≥ Δ|MDD| 且两窗不踏空；惰性不记正。

## 红线

研究池；未改 LIVE/实盘；未换冠。未重开 Dual-TF / 通道 overlay。

elapsed {time.time()-t0:.0f}s
"""
    (OUT / "REPORT.md").write_text(report, encoding="utf-8")
    print(f"done family_verdict={family_verdict} anchor_pass={anchor_ok}", flush=True)


if __name__ == "__main__":
    main()
