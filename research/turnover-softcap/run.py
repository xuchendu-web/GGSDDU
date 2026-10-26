#!/usr/bin/env python3
"""turnover-softcap: B45 + spike_ft max5 + E0 + TV25 + SHARPE20 + 52w 换手软帽（研究池，不换冠）。"""
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
TRAIL_WEEKS = 52
BOOK_SPECS = [
    ("F0", "LIVE1430-Tcap-off-B45-TV25", None),
    ("TCAP6", "LIVE1430-Tcap6-B45-TV25", 6.0),
    ("TCAP8", "LIVE1430-Tcap8-B45-TV25", 8.0),
    ("TCAP10", "LIVE1430-Tcap10-B45-TV25", 10.0),
]
ANCHOR_RET, ANCHOR_MDD, ANCHOR_CALMAR = 1.316, -0.188, 0.70
ANCHOR_N_WEEKS, ANCHOR_T, ANCHOR_N_CODES, ANCHOR_N_CASH = 349, 348, 324, 150
DECISION_LINE = (
    "请拍板：维持面层 B45 + spike_ft max5 + E0 + TV25 + SHARPE20（LIVE≥14:30），"
    "仅在目标 max5 权重落地前加 **52 周滚动单边换手软帽 T***（主档 8×/年）；"
    "超帽则按持仓 pro-rata 缩仓。无论记正与否都不换冠。"
)
H1_BLOCK = """```
唯一改动：在面层 B45 + spike_ft max5 + E0 + TV25 + SHARPE20 上，
算完当周目标 max5 权重后，若本周单边换手会使 trailing 52 周单边换手累计 > T*，
则 w = w_prev + α(w*−w_prev)，α∈[0,1] 取最大仍满足帽。
  T* 主档 8×/年（单边）；邻档仅 6×、10×。四件套 4 本（含 F0 关帽）。
  出场维持 E0。B、TV、席位、填席键、0.2%RT 不离开面。
  非 PR#77 成本×λ 联合；非填席换手惩罚（PR#55）。

H1：TCAP6 / TCAP8 / TCAP10 在严格尺子下相对本次 F0 全部证伪。
  任一记正 → H1 证伪（家族记一笔，不换冠）。
  全部证伪 → H1 成立。
  惰性（n_cap_bind=0 或与 F0 逐周权重相同）→ 记「证伪·惰性」，不能记正。
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


def one_way_turnover(wt: dict[str, float], prev: dict[str, float]) -> float:
    keys = set(wt) | set(prev)
    return sum(abs(wt.get(k, 0.0) - prev.get(k, 0.0)) for k in keys) / 2.0


def trailing52_sum(hist: list[float], to_week: float) -> float:
    past = hist[-(TRAIL_WEEKS - 1) :] if hist else []
    return sum(past) + to_week


def apply_turnover_soft_cap(
    wt_target: dict[str, float],
    prev: dict[str, float],
    hist: list[float],
    cap_annual: float | None,
) -> tuple[dict[str, float], float, bool, float]:
    """Pro-rata shrink toward prev until trailing-52w one-way sum <= cap_annual."""
    keys = set(wt_target) | set(prev)

    def blend(alpha: float) -> dict[str, float]:
        return {
            k: prev.get(k, 0.0) + alpha * (wt_target.get(k, 0.0) - prev.get(k, 0.0))
            for k in keys
        }

    if cap_annual is None:
        to = one_way_turnover(wt_target, prev)
        return wt_target, to, False, 1.0
    to_star = one_way_turnover(wt_target, prev)
    if trailing52_sum(hist, to_star) <= cap_annual:
        return wt_target, to_star, False, 1.0
    lo, hi = 0.0, 1.0
    for _ in range(64):
        mid = (lo + hi) / 2.0
        if trailing52_sum(hist, one_way_turnover(blend(mid), prev)) <= cap_annual:
            lo = mid
        else:
            hi = mid
    alpha = lo
    wt = blend(alpha)
    to = one_way_turnover(wt, prev)
    return wt, to, True, alpha


def run_live_tv(
    hold: dict[pd.Timestamp, list[str]],
    days: pd.DatetimeIndex,
    px: pd.DataFrame,
    R: pd.DataFrame,
    cap_annual: float | None = None,
) -> tuple[pd.Series, pd.Series, float, dict[str, Any]]:
    reb = sorted(hold)
    rp = pd.Series(0.0, index=days)
    Ls = pd.Series(0.0, index=days)
    prev: dict[str, float] = {}
    cst = pd.Series(0.0, index=days)
    R2 = R.reindex(days)
    turnovers: list[float] = []
    cap_rows: list[dict[str, Any]] = []
    n_cap_bind = 0
    alphas: list[float] = []

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
        if not cs:
            wt_target: dict[str, float] = {}
            wt = {}
            to = one_way_turnover(wt, prev)
            clipped, alpha = False, 1.0
        else:
            wt_target = {c: L * v for c, v in w.items()}
            wt, to, clipped, alpha = apply_turnover_soft_cap(wt_target, prev, turnovers, cap_annual)
        if clipped:
            n_cap_bind += 1
        alphas.append(alpha)
        turnovers.append(to)
        trail = trailing52_sum(turnovers[:-1], to)
        cap_rows.append(
            {
                "date": d.strftime("%Y-%m-%d") if hasattr(d, "strftime") else str(d)[:10],
                "cap_annual": cap_annual if cap_annual is not None else "off",
                "to_1way": to,
                "trail52_1way": trail,
                "alpha": alpha,
                "cap_bind": int(clipped),
                "L": L,
                "n_names": len(cs),
            }
        )
        prev = wt
        if d in cst.index:
            cst.loc[d] = to * LIVE_COST_RT
        if len(seg) and w:
            expo = float(sum(wt.values())) if wt else 0.0
            if expo > 0:
                rp.loc[seg] = (R2.loc[seg, list(w)].fillna(0) @ pd.Series(w)).values
                Ls.loc[seg] = expo
    r = rp * Ls - cst
    avg_to = float(np.mean(turnovers)) if turnovers else 0.0
    trail_end = trailing52_sum(turnovers[:-1], turnovers[-1]) if turnovers else 0.0
    diag = {
        "n_cap_bind": n_cap_bind,
        "trail52_end": trail_end,
        "turnover_annual_1way": sum(turnovers) * (52.0 / max(1, len(turnovers))),
        "cap_rows": cap_rows,
        "mean_alpha": float(np.mean(alphas)) if alphas else 1.0,
    }
    return r, Ls, avg_to, diag


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
    if cell["inert"]:
        cell["verdict"] = "证伪"
        return
    if cell["covers"] and cell["window_2020_22"] and cell["window_2023_26"]:
        cell["verdict"] = "记正"
    else:
        cell["verdict"] = "证伪"


def run_cap_fixtures() -> None:
    prev = {"a": 0.5, "b": 0.3}
    tgt = {"a": 0.0, "b": 0.8}
    hist = [0.15] * 51
    wt, to, clipped, alpha = apply_turnover_soft_cap(tgt, prev, hist, 8.0)
    if not clipped or alpha >= 1.0:
        raise SystemExit("cap fixture: expected bind")
    if trailing52_sum(hist, to) > 8.0 + 1e-9:
        raise SystemExit("cap fixture: trail exceeds cap")


def main() -> None:
    run_cap_fixtures()
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

    f0_book = BOOK_SPECS[0][1]
    print(f"simulate {f0_book} (shared holdings)…", flush=True)
    trades, hold_f0, picks_f0, sim_stats_f0 = simulate(
        calendar,
        snaps,
        closes_w_sig,
        alias,
        aum,
        daily,
        risk_b45,
        sharpe_key,
        f0_book,
        True,
        20,
        5,
        risk_b45,
    )
    sim_stats_f0["calendar_end"] = actual_end
    pd.DataFrame(trades).to_csv(OUT / "trades_F0.csv", index=False)

    all_codes: set[str] = set()
    for cs in hold_f0.values():
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

    series: dict[str, pd.Series] = {}
    cells: list[dict[str, Any]] = []
    tv_diag: dict[str, dict[str, Any]] = {}
    hd = {pd.Timestamp(d): cs for d, cs in hold_f0.items()}
    hit, wsz = entry_quality(calendar, picks_f0, hold_f0, closes_w_sig, alias)

    for bid, book, cap_star in BOOK_SPECS:
        print(f"live TV {book} cap={cap_star}…", flush=True)
        r, L, avg_to, diag = run_live_tv(hd, days, px, R, cap_annual=cap_star)
        tv_diag[bid] = diag
        pd.DataFrame(diag["cap_rows"]).to_csv(OUT / f"cap_weeks_{bid}.csv", index=False)
        series[book] = r
        st = stats_full(r)
        w22 = stats_full(window_slice(r, "2020-01-01", "2022-12-31"))
        w26 = stats_full(window_slice(r, "2023-01-01", None))
        cell: dict[str, Any] = {
            "id": bid,
            "book": book,
            "T_star": cap_star,
            "ret": st["ret"],
            "maxDD": st["maxDD"],
            "CAGR": st["CAGR"],
            "Calmar": st["Calmar"],
            "avgL": float(L[L > 0].mean()) if (L > 0).any() else 0.0,
            "avg_turnover_1way": avg_to,
            "turnover_annual_1way": diag["turnover_annual_1way"],
            "trail52_end": diag["trail52_end"],
            "n_cap_bind": diag["n_cap_bind"],
            "n_cash_weeks": sim_stats_f0["n_cash_weeks"],
            "n_ma_off": 0,
            "n_breadth_off": sum(1 for d in calendar[:-1] if not risk_b45.get(d)),
            "n_ma_off_breadth_on": 0,
            "n_both_off": 0,
            "n_entries": sim_stats_f0["n_entries"],
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
        cells.append(cell)

    f0 = next(c for c in cells if c["id"] == "F0")
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
        cell["inert"] = cell["n_cap_bind"] == 0

    blocked = not anchor_pass({**f0, **sim_stats_f0}, len(calendar), len(codes))
    anchor_ok = not blocked
    if not anchor_ok:
        print(
            f"anchor fail F0 ret={f0['ret']:.4f} mdd={f0['maxDD']:.4f} cal={f0['Calmar']:.2f} "
            f"cash={f0['n_cash_weeks']}",
            flush=True,
        )

    for cell in cells:
        ruler_cell(cell, f0, blocked)

    neighbor_cells = [c for c in cells if c["id"] != "F0"]
    positive_ids = [c["id"] for c in neighbor_cells if c["verdict"] == "记正"]
    if blocked:
        family_verdict = "BLOCKED"
        h1 = "BLOCKED"
    elif positive_ids:
        family_verdict = "H1_REJECT"
        h1 = f"TCAP 邻档记正: {', '.join(positive_ids)}"
    else:
        family_verdict = "H1_HOLD"
        h1 = "TCAP6/TCAP8/TCAP10 all 证伪"

    # equity long + png
    eq_rows = []
    nav_by_book = {}
    for bid, book, _cap in BOOK_SPECS:
        nav = (1 + series[book]).cumprod()
        nav_by_book[book] = nav
        for dt, v in nav.items():
            eq_rows.append({"date": dt.strftime("%Y-%m-%d"), "book": book, "nav": float(v)})
    pd.DataFrame(eq_rows).to_csv(OUT / "equity.csv", index=False)

    fig, ax = plt.subplots(figsize=(11, 5.5), dpi=120)
    f0_name = BOOK_SPECS[0][1]
    ax.plot(nav_by_book[f0_name].index, nav_by_book[f0_name], color="black", lw=2.2, label=f0_name)
    for bid, book, _cap in BOOK_SPECS[1:]:
        ax.plot(nav_by_book[book].index, nav_by_book[book], color="gray", lw=1.0, ls="-", label=book)
    ax.set_yscale("log")
    ax.set_title("turnover-softcap（F0 黑线；TCAP 灰线）")
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
                "T_star": "off" if cell["T_star"] is None else cell["T_star"],
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
                "turnover_annual_1way": cell["turnover_annual_1way"],
                "trail52_end": cell["trail52_end"],
                "n_cap_bind": cell["n_cap_bind"],
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
        "batch": "turnover-softcap",
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
        "turnover_cap": {
            "trail_weeks": TRAIL_WEEKS,
            "metric": "sum of weekly one-way turnover over trailing 52 rebalance Fridays",
            "T_star_grid": [6.0, 8.0, 10.0],
            "primary_T_star": 8.0,
            "live_cost_rt": LIVE_COST_RT,
        },
        "h1": h1,
        "family_verdict": family_verdict,
        "positive_ids": positive_ids,
        "cells": cells,
        "tv_diag": {k: {kk: vv for kk, vv in v.items() if kk != "cap_rows"} for k, v in tv_diag.items()},
    }
    (OUT / "summary.json").write_text(
        json.dumps(summary, ensure_ascii=False, indent=2, default=str), encoding="utf-8"
    )

    def md_row(c: dict[str, Any]) -> str:
        tcap = "off" if c["T_star"] is None else f"{c['T_star']:.0f}×"
        return (
            f"| {c['id']} | {tcap} | {pct(c['ret'])} | {pct(c['maxDD'])} | {c['Calmar']:.2f} | "
            f"{pct(c['w2020_22']['ret'])} | {pct(c['w2023_26']['ret'])} | "
            f"{c['turnover_annual_1way']:.2f}× | {c['n_cap_bind']} | {c['verdict']} |"
        )

    report = f"""# REPORT · turnover-softcap

{DECISION_LINE}

{H1_BLOCK}

## 换手软帽定义（Choffstein 路径：cost / turnover）

- **单边换手（周）**：再平衡日目标杠杆权重相对上周持仓权重，`TO_1w = ½ Σ|Δw|`（与 kit `run_live_tv` / X-metric 一致）。
- **滚动 52 周帽**：含当周的 trailing 和「过去 51 周 + 本周」单边换手之和 ≤ T*；T* 为年化单边换手倍数（主档 8×/年，邻档 6×、10×）。
- **软帽执行**：先算 FACE 目标 max5 等权 × TV25 杠杆权重 `w*`；若加入本周会使 trailing 和超 `T*`，取最大 `α∈[0,1]` 使 `w = w_prev + α(w*−w_prev)` 仍满足帽（pro-rata 缩交易，非改费率）。
- **成本**：往返 **0.2% RT**；当周成本 `TO_1w × 0.2%`（单边×RT）。**非** PR#77 RT×λ 联合，**非** PR#55 填席惩罚。

## 锚点门

- F0：ret {pct(f0['ret'])} / maxDD {pct(f0['maxDD'])} / Calmar {f0['Calmar']:.2f}；空仓周 {f0['n_cash_weeks']} / T={len(calendar)-1}
- anchor_pass：**{anchor_ok}**（对照 131.6% / −18.8% / 0.70 @ `{SOURCE_SHA[:8]}`）
- family_verdict：**{family_verdict}**（不换冠）

## 主表

| id | T* | ret | maxDD | Calmar | 2020-22 | 2023-26 | TO年化(单边) | n_cap_bind | verdict |
|----|-----|-----|-------|--------|---------|---------|--------------|------------|---------|
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
## 帽质量旁注

- 逐周 `cap_weeks_*.csv`：`to_1way`、`trail52_1way`、`alpha`、`cap_bind`。
- hit_rate / win_size 见 `table.csv`，不进 verdict（惰性除外）。

## 证伪段

- **{family_verdict}**：{h1}。champion_swap=false，不换冠。
- 记正尺子：Δret ≥ Δ|MDD| 且 2020–22、2023–26 均 ≥ F0；`n_cap_bind=0` 惰性不记正。

## 红线

研究池；未改 LIVE/实盘/冠；未重开 PR#77 成本×换手联合、PR#55 填席换手惩罚。

elapsed {time.time()-t0:.0f}s
"""
    (OUT / "REPORT.md").write_text(report, encoding="utf-8")

    attr = f"""# ATTRIBUTION · turnover-softcap

## 引擎与面

| 项 | 值 |
|----|-----|
| 针 SHA | `{SOURCE_SHA}` |
| 面层 | B45 + spike_ft max5 + E0 + TV25 + SHARPE20-fill |
| 成交 | Fri LIVE≥14:30；0.2% RT；L≤1 |
| 样本 | {EVAL_START} → {END_S} |
| FACE 锚 | 131.6% / −18.8% / Calmar 0.70（延窗 inventory） |

## 数据（未提交 kit）

- `research/cloud_batch/CLOUD-BATCH-2026-10-26/data/research_cache/`
- `holdings_ro2_extended.csv`（B45 宽度日历）
- `cache_1430_snaps.json`（spike 分类）
- `fri_1430_through_20261023.csv`

## 本刀唯一改动

路径约束：目标 max5 权重后的 **52 周滚动单边换手软帽**（T*∈{{6,8,10}}×/年），pro-rata 缩仓。

## 排除

- PR#77 `COST-TURNOVER-JOINT-B45`（RT×λ 填席联合）
- PR#55 turnover-penalty（λ 排序扣分）
- LIVE_OPS / champion_mast / strategy_exec

## 运行

```bash
python research/turnover-softcap/run.py
```

elapsed {time.time()-t0:.0f}s
"""
    (ROOT / "ATTRIBUTION.md").write_text(attr, encoding="utf-8")
    print(f"done family_verdict={family_verdict} anchor_pass={anchor_ok}", flush=True)
    if not anchor_ok:
        raise SystemExit("anchor_pass=false — STOP")


if __name__ == "__main__":
    main()
