from __future__ import annotations

import numpy as np
import pandas as pd


def max_drawdown(nav: pd.Series) -> float:
    peak = nav.cummax()
    dd = nav / peak - 1.0
    return float(dd.min())


def segment_slice(nav: pd.Series, start: str, end: str) -> pd.Series:
    s = nav.loc[(nav.index >= start) & (nav.index <= end)]
    return s


def book_metrics(nav: pd.Series, turnover_weekly: pd.Series | None = None) -> dict:
    nav = nav.dropna()
    if len(nav) < 2:
        return {}
    ret = float(nav.iloc[-1] / nav.iloc[0] - 1.0)
    years = (nav.index[-1] - nav.index[0]).days / 365.25
    cagr = float((nav.iloc[-1] / nav.iloc[0]) ** (1 / max(years, 1e-6)) - 1.0)
    mdd = max_drawdown(nav)
    calmar = cagr / abs(mdd) if mdd < 0 else np.nan
    rets = nav.pct_change().dropna()
    vol = float(rets.std() * np.sqrt(52))
    sharpe = float(rets.mean() / rets.std() * np.sqrt(52)) if rets.std() > 0 else np.nan
    avg_to = float(turnover_weekly.mean()) if turnover_weekly is not None else np.nan
    out = {
        "ret": ret,
        "maxDD": mdd,
        "CAGR": cagr,
        "Calmar": calmar,
        "Sharpe": sharpe,
        "vol_ann": vol,
        "avgTO": avg_to,
    }
    for label, a, b in [("2020-22", "2020-01-01", "2022-12-31"), ("2023-26", "2023-01-01", "2026-12-31")]:
        seg = segment_slice(nav, a, b)
        if len(seg) >= 2:
            r = float(seg.iloc[-1] / seg.iloc[0] - 1.0)
            dd = max_drawdown(seg)
            c = (r / abs(dd)) if dd < 0 else np.nan
            out[f"{label}_ret"] = r
            out[f"{label}_DD"] = dd
            out[f"{label}_Calmar"] = c
    return out


def entry_quality(entries: pd.DataFrame) -> dict:
    """entries: columns symbol, entry_date, ret_1w"""
    if entries.empty:
        return {"n_entries": 0, "hit_rate": np.nan, "win_size": np.nan}
    r = entries["ret_1w"].dropna()
    if r.empty:
        return {"n_entries": 0, "hit_rate": np.nan, "win_size": np.nan}
    wins = r[r > 0]
    losses = r[r <= 0]
    hit = float((r > 0).mean())
    if len(wins) == 0 or len(losses) == 0:
        win_size = np.nan
    else:
        win_size = float(wins.mean() / abs(losses.mean()))
    return {"n_entries": int(len(r)), "hit_rate": hit, "win_size": win_size}
