"""UNIV-THEME-BROAD-SPLIT-B45: theme vs broad split books + blend vs face mix.

Books:
  FACE (全池混排) · SPLIT-THEME · SPLIT-BROAD — each B45+spike_ft max5+S20+E0+TV25.
  BLEND 50/50 · ER · 60/40 · 70/30 — synthetic NAV from theme+broad legs.
  Breadth: **共用母池 face** risk_on（holdings_ro2_extended）；各腿仅在子宇宙内排序取 spike。
  Fri≥14:30 / close; 0.2%RT; L≤1; research pool only; no crown swap.
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
    allowed_codes: set[str] | None = None,
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
            if allowed_codes is not None and code not in allowed_codes:
                continue
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


def blend_fixed(r_a: pd.Series, r_b: pd.Series, w_a: float) -> pd.Series:
    idx = r_a.index.union(r_b.index).sort_values()
    a = r_a.reindex(idx).fillna(0.0)
    b = r_b.reindex(idx).fillna(0.0)
    return w_a * a + (1.0 - w_a) * b


def blend_equal_risk(
    r_theme: pd.Series,
    r_broad: pd.Series,
    calendar: list[str],
    lookback: int = 60,
) -> pd.Series:
    idx = r_theme.index.union(r_broad.index).sort_values()
    rt = r_theme.reindex(idx).fillna(0.0)
    rb = r_broad.reindex(idx).fillna(0.0)
    out = pd.Series(0.0, index=idx)
    reb = [pd.Timestamp(d) for d in calendar[:-1]]
    for i, d in enumerate(reb):
        nxt = reb[i + 1] if i + 1 < len(reb) else idx[-1] + pd.Timedelta(days=1)
        seg = idx[(idx > d) & (idx <= nxt)]
        if len(seg) == 0:
            continue
        past_t = rt[rt.index <= d].iloc[-lookback:]
        past_b = rb[rb.index <= d].iloc[-lookback:]
        vt = float(past_t.std()) if len(past_t) > 5 else float("nan")
        vb = float(past_b.std()) if len(past_b) > 5 else float("nan")
        if not vt or vt <= 0 or not vb or vb <= 0:
            wt = 0.5
        else:
            wt = (1.0 / vt) / (1.0 / vt + 1.0 / vb)
        out.loc[seg] = wt * rt.loc[seg] + (1.0 - wt) * rb.loc[seg]
    return out


CRITERION_MD = """# UNIV-THEME-BROAD-SPLIT-B45

- 编号 / 日期：UNIV-THEME-BROAD-SPLIT-B45 / 2026-10-26 / 机械批测 Composer
- 性质：**分账轮动** — 行业主题宇宙 vs 宽基宇宙分开跑 B45+S20，再合成净值；对照全池混排 face

## 准则原文
- 子宇宙：**宽基** = `family` 以「宽基」开头；**主题侧** = 其余（行业/风格/主题等，AUM≥2亿研究池）。
- 各腿规则冻结：spike_ft **max5** + E0 + **TV25** + **SHARPE20**；breadth≥45%（**共用母池 face** `risk_on`）。
- 合成：50/50 固定权、等风险（60日逆波周调）、邻档 **60/40**、**70/30**（主题:宽基）。
- 对照：**FACE** = 全池混排同一规则（face 基线）。
- 成交：Fri≥14:30 / 收盘；**0.2%RT**；**L≤1**；窗 ≥2026-10-23。

## 假设 H1
分账合成**不能**稳定胜过混排 face（Δret 盖 Δ|MDD| 且 2023–26 不踏空）。

## 证伪
任一分账/合成档相对 FACE 同时满足探索尺子且 Calmar 更高 → H1 不成立（只记账，不换冠）。

## 红线
研究池 only；不换冠；不碰 strategy_exec / LIVE_OPS / 实盘。

## 交付
四件套：`research/univ-theme-broad-split-b45/`（run.py / criterion.md / REPORT.md / summary.json）
"""


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
        "sample_note": f"CLOUD-BATCH 延窗研究：{EVAL_START}→{END_S}（14:30 至 2026-10-23）",
        "approximation": [
            "延窗：research_cache week/day/face/14:30；≤2026-10-09 沿用 face；其后研究周线 MA20 宽度",
            "qfq_1430 = price_1430 × (day qfq 收 / sina daily 收)；sina 作 bfq 代理",
            "冲击分类：周线收盘替换为 qfq_1430 后因果 classify（Fri≥14:30 信号）",
            "Sharpe 窗截至信号日严格前一交易日",
            "成交：周五收盘填仓 + 0.2%RT；L=min(1, 0.25/max(σ20,σ60))；TV25 冻结",
            "分账：主题/宽基子宇宙内 spike 排序；breadth **共用母池 face** risk_on",
            "合成：主题+宽基腿日收益固定权或逆波等权；只读 cache_1430_snaps",
            "只读 kit `data/cache_1430_snaps.json`；不写 strategy_exec / LIVE_OPS",
        ],
    }

    fam = {r.code: str(r.family) for r in uni.itertuples()}
    codes_broad = {c for c in codes if fam.get(c, "").startswith("宽基")}
    codes_theme = {c for c in codes if c not in codes_broad}
    print(f"universe split: broad={len(codes_broad)} theme={len(codes_theme)}", flush=True)

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

    # --- split books: FACE / THEME / BROAD + blends ---
    sim_specs: list[tuple[str, set[str] | None, str]] = [
        ("LIVE1430-FACE-B45-S20", None, "baseline"),
        ("LIVE1430-SPLIT-THEME-B45-S20", codes_theme, "leg"),
        ("LIVE1430-SPLIT-BROAD-B45-S20", codes_broad, "leg"),
    ]
    hold_by: dict[str, dict[str, list[str]]] = {}
    sim_stats: dict[str, Any] = {}
    trades_by: dict[str, list[dict[str, Any]]] = {}

    for name, allowed, role in sim_specs:
        print(f"simulate {name} allowed={len(allowed) if allowed else 'ALL'}…", flush=True)
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
            allowed_codes=allowed,
        )
        n_cash = sum(1 for d in calendar[:-1] if not (hold.get(d) or []))
        st = {**st, "n_cash_weeks": n_cash, "role": role, "n_universe": len(allowed) if allowed else len(codes)}
        hold_by[name] = hold
        sim_stats[name] = st
        trades_by[name] = trades
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
            f"  entries={st['n_entries']} trades={st['n_trades']} cash_weeks={n_cash}",
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

    base_name = "LIVE1430-FACE-B45-S20"
    diffs = {f"{b}_vs_FACE": pick_diff(base_name, b) for b in hold_by if b != base_name}

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

    leg_names = ["LIVE1430-SPLIT-THEME-B45-S20", "LIVE1430-SPLIT-BROAD-B45-S20"]
    series: dict[str, pd.Series] = {}
    Ls_map: dict[str, pd.Series] = {}
    to_map: dict[str, float] = {}
    occ_map: dict[str, dict[str, Any]] = {}

    for name in [s[0] for s in sim_specs]:
        hd = {pd.Timestamp(d): cs for d, cs in hold_by[name].items()}
        r, L, avg_to = run_live_tv(hd, days, px, R, sigma_star=SIGMA_STAR)
        series[name] = r
        Ls_map[name] = L
        to_map[name] = avg_to
        occ_map[name] = occupied_week_stats(r, hd, days)

    r_theme = series["LIVE1430-SPLIT-THEME-B45-S20"]
    r_broad = series["LIVE1430-SPLIT-BROAD-B45-S20"]
    blend_specs = [
        ("LIVE1430-BLEND-50-50", blend_fixed(r_theme, r_broad, 0.5), "blend"),
        ("LIVE1430-BLEND-ER", blend_equal_risk(r_theme, r_broad, calendar), "blend"),
        ("LIVE1430-BLEND-60-40", blend_fixed(r_theme, r_broad, 0.6), "blend"),
        ("LIVE1430-BLEND-70-30", blend_fixed(r_theme, r_broad, 0.7), "blend"),
    ]
    for bname, br, role in blend_specs:
        series[bname] = br
        Ls_map[bname] = (Ls_map[leg_names[0]] + Ls_map[leg_names[1]]) / 2.0
        to_map[bname] = (to_map[leg_names[0]] + to_map[leg_names[1]]) / 2.0
        sim_stats[bname] = {"role": role, "n_cash_weeks": float("nan"), "synthetic": True}
        occ_map[bname] = occupied_week_stats(br, hold_by[base_name], days)

    variants = [s[0] for s in sim_specs] + [b[0] for b in blend_specs]

    table_rows = []
    for name in variants:
        r = series[name]
        L = Ls_map[name]
        avg_to = to_map[name]
        occ = occ_map[name]
        st = stats_full(r)
        r2022 = r[(r.index >= "2020-01-01") & (r.index <= "2022-12-31")]
        r2023 = r[r.index >= "2023-01-01"]
        st2022 = stats_full(r2022) if len(r2022) > 5 else {k: float("nan") for k in st}
        st2023 = stats_full(r2023) if len(r2023) > 5 else {k: float("nan") for k in st}
        row = {
            "book": name,
            "kind": sim_stats[name].get("role", ""),
            **st,
            "2020-22_ret": st2022["ret"],
            "2020-22_DD": st2022["maxDD"],
            "2020-22_Calmar": st2022["Calmar"],
            "2023-26_ret": st2023["ret"],
            "2023-26_DD": st2023["maxDD"],
            "2023-26_Calmar": st2023["Calmar"],
            "avgL": float(L[L > 0].mean()) if (L > 0).any() else 0.0,
            "avg_turnover": avg_to,
            "occ_n": occ["n_occ_weeks"],
            "n_cash_weeks": sim_stats[name].get("n_cash_weeks"),
        }
        table_rows.append(row)
        print(
            f"  {name}: ret={pct(st['ret'])} dd={pct(st['maxDD'])} Calmar={st['Calmar']:.2f}",
            flush=True,
        )

    df = pd.DataFrame(table_rows)
    df.to_csv(OUT / "table.csv", index=False)
    df.to_csv(OUT / "metrics.csv", index=False)

    y = yearly_table(series[base_name]).rename(columns=lambda c: f"face_{c}" if c != "year" else c)
    for slug, col in [
        ("LIVE1430-SPLIT-THEME-B45-S20", "theme"),
        ("LIVE1430-SPLIT-BROAD-B45-S20", "broad"),
        ("LIVE1430-BLEND-50-50", "b5050"),
    ]:
        yi = yearly_table(series[slug]).rename(columns=lambda c, p=col: f"{p}_{c}" if c != "year" else c)
        y = y.merge(yi, on="year", how="outer")
    y.to_csv(OUT / "yearly.csv", index=False)

    eq = pd.DataFrame({k: (1 + series[k]).cumprod() for k in variants})
    eq.to_csv(OUT / "equity.csv")
    eq.to_csv(OUT / "nav_all.csv")
    for name in variants:
        series[name].to_csv(OUT / f"nav_{name}.csv", header=["r"])

    fig, ax = plt.subplots(figsize=(11, 5.5), dpi=120)
    plot_order = [
        (base_name, 2.5, "-"),
        ("LIVE1430-BLEND-50-50", 1.8, "-"),
        ("LIVE1430-BLEND-ER", 1.5, "--"),
        ("LIVE1430-BLEND-60-40", 1.2, ":"),
        ("LIVE1430-BLEND-70-30", 1.2, ":"),
        ("LIVE1430-SPLIT-THEME-B45-S20", 1.0, "-."),
        ("LIVE1430-SPLIT-BROAD-B45-S20", 1.0, "-."),
    ]
    for name, lw, ls in plot_order:
        if name in eq.columns:
            ax.plot(eq.index, eq[name], label=name.replace("LIVE1430-", ""), lw=lw, ls=ls)
    ax.set_yscale("log")
    ax.set_title("UNIV-THEME-BROAD-SPLIT-B45（分账 vs FACE）")
    ax.set_ylabel("净值（对数）")
    ax.grid(True, alpha=0.3)
    ax.legend(fontsize=7, ncol=2)
    fig.tight_layout()
    fig.savefig(OUT / "equity_curve.png")
    plt.close(fig)

    base = df[df.book == base_name].iloc[0]
    by_book = {r.book: r for _, r in df.iterrows()}

    def delta_vs_face(name: str) -> dict[str, float]:
        r = by_book[name]
        dret = (float(r["ret"]) - float(base["ret"])) * 100
        ddd_abs = (abs(float(r["maxDD"])) - abs(float(base["maxDD"]))) * 100
        return {
            "dret_pp": dret,
            "d_abs_mdd_pp": ddd_abs,
            "covers": dret >= ddd_abs,
            "rear_ok": float(r["2023-26_ret"]) >= float(base["2023-26_ret"]) * 0.9,
        }

    face_delta = {n: delta_vs_face(n) for n in variants if n != base_name}
    blend_names = [b[0] for b in blend_specs]
    h1_fail_candidates = [
        n
        for n in blend_names
        if face_delta[n]["covers"] and face_delta[n]["dret_pp"] > 0 and face_delta[n]["rear_ok"]
    ]
    h1_holds = len(h1_fail_candidates) == 0
    best_cal = df.loc[df["Calmar"].idxmax()]
    best_name = str(best_cal["book"])

    if h1_holds:
        verdict = (
            f"**H1 成立（不换冠）**：无分账/合成档相对 FACE 同时满足「Δret 盖住 Δ|MDD|」且 2023–26 不踏空。"
            f" Calmar 最高：**{best_name.replace('LIVE1430-', '')}**（{float(best_cal['Calmar']):.2f}）。"
            f" FACE ret={pct(float(base['ret']))} / DD={pct(float(base['maxDD']))}。"
        )
    else:
        verdict = (
            f"**H1 不成立（只记账）**：{', '.join(n.replace('LIVE1430-', '') for n in h1_fail_candidates)}"
            f" 相对 FACE 过探索尺子；不换冠。"
        )

    summary = {
        "title": "UNIV-THEME-BROAD-SPLIT-B45",
        "batch": "UNIV-SPLIT-B45",
        "convention": "Fri≥14:30 / close; L≤1; 0.2%RT; B45+S20 max5+E0+TV25",
        "unique_change": "theme/broad split books + 50/50 ER 60/40 70/30 blends vs FACE mix",
        "breadth": "mother_pool_face_risk_on",
        "n_broad": len(codes_broad),
        "n_theme": len(codes_theme),
        "sample": f"{EVAL_START} → {actual_end}",
        "n_calendar_weeks": len(calendar),
        "coverage": cov_stats,
        "hold_diffs_vs_face": diffs,
        "sim_stats": sim_stats,
        "table": table_rows,
        "delta_vs_face": face_delta,
        "hypothesis_H1_holds": h1_holds,
        "best_calmar_book": best_name,
        "verdict": verdict,
        "isolation": "strategy_exec / LIVE_OPS: NONE",
        "elapsed_sec": round(time.time() - t0, 1),
    }
    (OUT / "summary.json").write_text(
        json.dumps(summary, ensure_ascii=False, indent=2, default=str), encoding="utf-8"
    )
    (OUT / "criterion.md").write_text(CRITERION_MD.strip() + "\n", encoding="utf-8")

    def row_md(name: str) -> str:
        r = df[df.book == name].iloc[0]
        tag = " **基线**" if name == base_name else ""
        nc = sim_stats.get(name, {}).get("n_cash_weeks", "—")
        return (
            f"| {name.replace('LIVE1430-', '')}{tag} | {pct(r['ret'])} | {pct(r['maxDD'])} | "
            f"{pct(r['CAGR'])} | {r['Calmar']:.2f} | "
            f"{pct(r['2020-22_ret'])}/{pct(r['2020-22_DD'])}/{r['2020-22_Calmar']:.2f} | "
            f"{pct(r['2023-26_ret'])}/{pct(r['2023-26_DD'])}/{r['2023-26_Calmar']:.2f} | "
            f"{r['avgL']:.2f} | {r['avg_turnover']:.3f} | {nc} |"
        )

    delta_lines = [
        "| book | Δret vs FACE | Δ|MDD| | 盖住? | 2023–26 不差 |",
        "|---|---:|---:|---|---|",
    ]
    for n in variants:
        if n == base_name:
            continue
        d = face_delta[n]
        delta_lines.append(
            f"| {n.replace('LIVE1430-', '')} | {d['dret_pp']:+.1f}pp | {d['d_abs_mdd_pp']:+.1f}pp | "
            f"{'是' if d['covers'] else '否'} | {'是' if d['rear_ok'] else '否'} |"
        )

    table_body = "\n".join(row_md(n) for n in variants)
    approx_md = "\n".join(f"- {a}" for a in cov_stats["approximation"])
    d_hold = diffs.get("LIVE1430-SPLIT-THEME-B45-S20_vs_FACE", {"n_diff": 0, "n": 0})

    report = f"""# REPORT · UNIV-THEME-BROAD-SPLIT-B45（主题/宽基分账 · 延窗）

## 1. 准则原文

```
{CRITERION_MD.strip()}
```

## 2. 实现要点

- **唯一改动**：行业主题 vs 宽基 **分账** 各跑 B45+spike_ft max5+S20+E0+**TV25**；再 50/50、等风险（60日逆波周调）、60/40、70/30 合成；对照 **FACE 全池混排**。
- **Breadth**：**共用母池** `holdings_ro2_extended` 的 `risk_on`（非子池自算宽度）。
- **子宇宙**：宽基 `family` 以「宽基」起；其余归主题侧（AUM≥2亿）。
- **冻结**：Fri≥14:30 / 收盘；**0.2%RT**；**L≤1**；延窗至 **{actual_end}**。
- **隔离**：不写 strategy_exec / LIVE_OPS。

## 近似与覆盖

{approx_md}

| 覆盖 | 值 |
|---|---|
| 可投池（AUM≥2亿） | {len(codes)}（宽基 {len(codes_broad)} / 主题 {len(codes_theme)}） |
| 日历周 | {len(calendar)}（{calendar[0]}→{actual_end}） |
| listed 行 14:30 非空率 | {100*nonnull_rate:.1f}% |
| 成功映射 qfq_1430 | {n_map} |
| 持仓 vs FACE（THEME 腿）差异周 | {d_hold.get('n_diff', 0)}/{d_hold.get('n', 0)} |

## 3. 主表

| book | ret | maxDD | CAGR | Calmar | 2020–22 ret/DD/C | 2023–26 ret/DD/C | avgL | avgTO | 空仓周 |
|---|---:|---:|---:|---:|---|---|---:|---:|---:|
{table_body}

### Δ vs FACE（探索尺子）

{chr(10).join(delta_lines)}

### 分段 · FACE 基线

| 段 | ret | maxDD | Calmar |
|---|---:|---:|---:|
| 2020–22 | {pct(float(base['2020-22_ret']))} | {pct(float(base['2020-22_DD']))} | {float(base['2020-22_Calmar']):.2f} |
| 2023–26 | {pct(float(base['2023-26_ret']))} | {pct(float(base['2023-26_DD']))} | {float(base['2023-26_Calmar']):.2f} |

## 4. 一句结论（探索记账，不换冠）

{verdict}

## 产物

- `run.py` / `criterion.md` / `REPORT.md` / `summary.json`
- `table.csv` / `metrics.csv` / `yearly.csv` / `equity.csv` / `nav_*.csv` / `equity_curve.png`

耗时约 {summary['elapsed_sec']}s。
"""
    (OUT / "REPORT.md").write_text(report, encoding="utf-8")
    print("done", OUT, flush=True)
    print(verdict, flush=True)
if __name__ == "__main__":
    main()
