"""Frozen LIVE1430 face layer: B45 + spike_ft max5 + E0 + TV25 + SHARPE20."""
from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Dict, Iterable, List, Optional, Sequence, Tuple

import numpy as np
import pandas as pd

COST_RT = 0.002
TV_TARGET = 0.25
BREADTH_ON = 0.45
SHARPE_WIN = 20
SPIKE_FT_WIN = 5
MAX_SEATS = 5
ANNUALIZATION = 252


@dataclass
class FaceConfig:
    breadth_threshold: float = BREADTH_ON
    tv_target: float = TV_TARGET
    cost_rt: float = COST_RT
    max_leverage: float = 1.0
    max_seats: int = MAX_SEATS


def _fridays_between(idx: pd.DatetimeIndex, start: str, end: str) -> pd.DatetimeIndex:
    s, e = pd.Timestamp(start), pd.Timestamp(end)
    fris = idx[(idx >= s) & (idx <= e) & (idx.dayofweek == 4)]
    return fris.sort_values()


def _ma(series: pd.Series, win: int) -> pd.Series:
    return series.rolling(win, min_periods=win).mean()


def _realized_vol(daily_ret: pd.Series, win: int = 20) -> float:
    tail = daily_ret.dropna().tail(win)
    if len(tail) < win:
        return float("nan")
    return float(tail.std(ddof=0) * math.sqrt(ANNUALIZATION))


def _sharpe20(daily_ret: pd.Series, asof: pd.Timestamp) -> float:
    hist = daily_ret[daily_ret.index < asof].dropna().tail(SHARPE_WIN)
    if len(hist) < SHARPE_WIN:
        return float("nan")
    mu = hist.mean()
    sd = hist.std(ddof=0)
    if sd <= 1e-12:
        return float("nan")
    return float(mu / sd * math.sqrt(ANNUALIZATION))


def _spike_ft_ok(daily_ret: pd.Series, asof: pd.Timestamp) -> bool:
    """E0: 5d trailing sum return > 0 on prices implied by daily returns."""
    hist = daily_ret[daily_ret.index < asof].dropna().tail(SPIKE_FT_WIN)
    if len(hist) < SPIKE_FT_WIN:
        return False
    return float(hist.sum()) > 0.0


def breadth_ma20_width(close: pd.DataFrame, asof: pd.Timestamp, codes: Sequence[str]) -> float:
    sub = close.loc[:asof, list(codes)]
    if sub.empty or len(sub) < 20:
        return float("nan")
    last = sub.iloc[-1]
    ma = sub.rolling(20, min_periods=20).mean().iloc[-1]
    valid = last.notna() & ma.notna()
    if valid.sum() == 0:
        return float("nan")
    return float((last[valid] > ma[valid]).mean())


def _select_weights(
    close: pd.DataFrame,
    daily_ret: pd.DataFrame,
    signal_day: pd.Timestamp,
    tradable: Sequence[str],
    cfg: FaceConfig,
) -> Tuple[Dict[str, float], float]:
    candidates: List[Tuple[str, float]] = []
    for code in tradable:
        if code not in daily_ret.columns:
            continue
        if not _spike_ft_ok(daily_ret[code], signal_day):
            continue
        sh = _sharpe20(daily_ret[code], signal_day)
        if math.isnan(sh):
            continue
        candidates.append((code, sh))
    candidates.sort(key=lambda x: x[1], reverse=True)
    picks = [c for c, _ in candidates[: cfg.max_seats]]
    if not picks:
        return {}, 0.0
    w = 1.0 / len(picks)
    weights = {c: w for c in picks}
    vols = []
    ws = []
    for c, wt in weights.items():
        v = _realized_vol(daily_ret[c], 20)
        if math.isnan(v) or v <= 1e-9:
            continue
        vols.append(v)
        ws.append(wt)
    if not ws:
        return {}, 0.0
    port_vol = math.sqrt(sum((w_i * v_i) ** 2 for w_i, v_i in zip(ws, vols)))
    L = min(cfg.max_leverage, cfg.tv_target / port_vol) if port_vol > 0 else 0.0
    return {c: wt * L for c, wt in weights.items()}, L


def run_face_backtest(
    close: pd.DataFrame,
    investable_by_date: Dict[pd.Timestamp, List[str]],
    breadth_codes: Sequence[str],
    cfg: Optional[FaceConfig] = None,
    start: str = "2020-01-03",
    end: str = "2026-10-23",
) -> Tuple[pd.Series, pd.DataFrame, dict]:
    cfg = cfg or FaceConfig()
    close = close.sort_index()
    daily_ret = close.pct_change()
    fridays = _fridays_between(close.index, start, end)
    nav = 1.0
    nav_series = []
    nav_dates = []
    rows = []
    prev_w: Dict[str, float] = {}

    last_tradable: List[str] = []
    for fri in fridays:
        tradable = investable_by_date.get(fri, last_tradable)
        if not tradable:
            tradable = list(close.columns)
        last_tradable = tradable

        b = breadth_ma20_width(close, fri, breadth_codes)
        risk_on = not math.isnan(b) and b >= cfg.breadth_threshold

        if risk_on:
            target_w, avg_l = _select_weights(close, daily_ret, fri, tradable, cfg)
        else:
            target_w, avg_l = {}, 0.0

        all_codes = set(prev_w) | set(target_w)
        turnover = sum(abs(target_w.get(c, 0.0) - prev_w.get(c, 0.0)) for c in all_codes)
        nav *= 1.0 - cfg.cost_rt * turnover

        if fri in close.index:
            day_ret = 0.0
            for c, w in target_w.items():
                r = daily_ret.at[fri, c] if c in daily_ret.columns else float("nan")
                if pd.notna(r):
                    day_ret += w * float(r)
            nav *= 1.0 + day_ret

        nav_series.append(nav)
        nav_dates.append(fri)
        rows.append(
            {
                "date": fri,
                "nav": nav,
                "breadth": b,
                "risk_on": risk_on,
                "avgL": avg_l,
                "n_hold": len(target_w),
                "turnover": turnover,
            }
        )
        prev_w = target_w

    nav_s = pd.Series(nav_series, index=pd.DatetimeIndex(nav_dates), name="nav")
    weekly = pd.DataFrame(rows)
    stats = summarize_nav(nav_s)
    return nav_s, weekly, stats


def summarize_nav(nav: pd.Series) -> dict:
    nav = nav.dropna()
    if len(nav) < 2:
        return {}
    daily = nav.pct_change().dropna()
    ret = float(nav.iloc[-1] / nav.iloc[0] - 1.0)
    dd = float((nav / nav.cummax() - 1.0).min())
    years = (nav.index[-1] - nav.index[0]).days / 365.25
    cagr = float((nav.iloc[-1] / nav.iloc[0]) ** (1 / years) - 1) if years > 0 else float("nan")
    calmar = float(cagr / abs(dd)) if dd < 0 else float("nan")
    vol = float(daily.std(ddof=0) * math.sqrt(52)) if len(daily) > 1 else float("nan")

    def _seg(s: str, e: str) -> dict:
        sub = nav[(nav.index >= pd.Timestamp(s)) & (nav.index <= pd.Timestamp(e))]
        if len(sub) < 2:
            return {}
        r = float(sub.iloc[-1] / sub.iloc[0] - 1)
        mdd = float((sub / sub.cummax() - 1).min())
        y = (sub.index[-1] - sub.index[0]).days / 365.25
        cg = float((sub.iloc[-1] / sub.iloc[0]) ** (1 / y) - 1) if y > 0 else float("nan")
        cm = float(cg / abs(mdd)) if mdd < 0 else float("nan")
        return {"ret": r, "maxDD": mdd, "Calmar": cm}

    return {
        "ret": ret,
        "maxDD": dd,
        "CAGR": cagr,
        "Calmar": calmar,
        "vol_weekly": vol,
        "n_weeks": int(len(nav)),
        "2020-22": _seg("2020-01-01", "2022-12-31"),
        "2023-26": _seg("2023-01-01", "2026-12-31"),
    }


def pit_filter(
    listing: Dict[str, pd.Timestamp],
    asof: pd.Timestamp,
    codes: Iterable[str],
) -> List[str]:
    out = []
    for c in codes:
        ld = listing.get(c)
        if ld is None or ld <= asof:
            out.append(c)
    return out
