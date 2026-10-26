"""Book stats vs B45 face tables (incl. Sharpe / Sortino on weekly returns)."""

from __future__ import annotations

import numpy as np
import pandas as pd


def _from_nav(nav: pd.Series) -> dict[str, float]:
    q = nav.dropna().astype(float)
    if len(q) < 2:
        nan = float("nan")
        return {k: nan for k in ("ret", "maxDD", "CAGR", "Calmar")}
    ret = float(q.iloc[-1] / q.iloc[0] - 1.0)
    dd = float((q / q.cummax().clip(lower=1e-12) - 1.0).min())
    n = (q.index[-1] - q.index[0]).days
    cagr = (1.0 + ret) ** (365.25 / n) - 1.0 if n > 0 and (1.0 + ret) > 0 else float("nan")
    cal = cagr / abs(dd) if dd < 0 and np.isfinite(cagr) else float("nan")
    return {"ret": ret, "maxDD": dd, "CAGR": cagr, "Calmar": cal}


def _risk_from_weekly(weekly_ret: pd.Series) -> dict[str, float]:
    r = weekly_ret.dropna().astype(float)
    if len(r) < 8:
        return {"Sharpe": float("nan"), "Sortino": float("nan")}
    mu = float(r.mean())
    sd = float(r.std(ddof=1))
    sharpe = (mu / sd * np.sqrt(52.0)) if sd > 1e-12 else float("nan")
    neg = r[r < 0]
    dsd = float(neg.std(ddof=1)) if len(neg) > 1 else float("nan")
    sortino = (mu / dsd * np.sqrt(52.0)) if dsd > 1e-12 else float("nan")
    return {"Sharpe": sharpe, "Sortino": sortino}


def book_stats(nav: pd.Series, weekly_ret: pd.Series | None = None) -> dict[str, float]:
    out = _from_nav(nav)
    if weekly_ret is not None:
        out.update(_risk_from_weekly(weekly_ret))
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


def align_face_weekly(face_daily: pd.Series, weeks: pd.DatetimeIndex) -> pd.Series:
    s = face_daily.sort_index().astype(float)
    out = s.reindex(weeks, method="ffill")
    return out.dropna()


def covers_mdd(ret_a: float, mdd_a: float, ret_b: float, mdd_b: float) -> bool:
    d_ret = (ret_a - ret_b) * 100.0
    d_mdd = (abs(mdd_a) - abs(mdd_b)) * 100.0
    return d_ret >= d_mdd
