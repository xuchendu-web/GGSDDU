"""Book stats + Sharpe on weekly returns (sleeve benchmarks, not B45)."""

from __future__ import annotations

import numpy as np
import pandas as pd


def _from_nav(nav: pd.Series) -> dict[str, float]:
    q = nav.dropna().astype(float)
    if len(q) < 2:
        return {k: float("nan") for k in ("ret", "maxDD", "CAGR", "Calmar")}
    ret = float(q.iloc[-1] / q.iloc[0] - 1.0)
    dd = float((q / q.cummax().clip(lower=1e-12) - 1.0).min())
    n = (q.index[-1] - q.index[0]).days
    cagr = (1.0 + ret) ** (365.25 / n) - 1.0 if n > 0 and (1.0 + ret) > 0 else float("nan")
    cal = cagr / abs(dd) if dd < 0 and np.isfinite(cagr) else float("nan")
    return {"ret": ret, "maxDD": dd, "CAGR": cagr, "Calmar": cal}


def sharpe_weekly(weekly_ret: pd.Series, periods: float = 52.0) -> float:
    r = weekly_ret.dropna().astype(float)
    if len(r) < 8:
        return float("nan")
    mu = float(r.mean())
    sig = float(r.std(ddof=1))
    if sig <= 0 or not np.isfinite(sig):
        return float("nan")
    return mu / sig * np.sqrt(periods)


def book_stats(nav: pd.Series, weekly_ret: pd.Series | None = None) -> dict[str, float]:
    out = _from_nav(nav)
    wr = weekly_ret if weekly_ret is not None else nav.pct_change().dropna()
    out["Sharpe"] = sharpe_weekly(wr)
    return out


def segment_stats(nav: pd.Series, start: str, end: str) -> dict[str, float]:
    sl = nav.loc[pd.Timestamp(start) : pd.Timestamp(end)]
    return _from_nav(sl)


def yearly_stats(nav: pd.Series) -> pd.DataFrame:
    rows = []
    nav = nav.dropna()
    for y in sorted(set(nav.index.year)):
        sl = nav[nav.index.year == y]
        if len(sl) < 2:
            continue
        st = _from_nav(sl)
        rows.append({"year": int(y), "ret": st["ret"], "maxDD": st["maxDD"]})
    return pd.DataFrame(rows)


def covers_mdd(ret_a: float, mdd_a: float, ret_b: float, mdd_b: float) -> bool:
    d_ret = (ret_a - ret_b) * 100.0
    d_mdd = (abs(mdd_a) - abs(mdd_b)) * 100.0
    return d_ret >= d_mdd
