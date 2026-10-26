from __future__ import annotations

import numpy as np
import pandas as pd


def weekly_bars(daily: pd.DataFrame) -> pd.DataFrame:
    """Resample daily OHLC to week ending Friday."""
    d = daily.sort_index().copy()
    d["week"] = d.index.to_period("W-FRI")
    g = d.groupby("week", sort=True)
    out = pd.DataFrame(
        {
            "open": g["open"].first(),
            "high": g["high"].max(),
            "low": g["low"].min(),
            "close": g["close"].last(),
        }
    )
    out.index = out.index.to_timestamp("W-FRI")
    out["rng"] = (out["high"] - out["low"]) / out["close"].replace(0, np.nan)
    return out


def compression_breakout_ok(
    weekly: pd.DataFrame,
    signal_date: pd.Timestamp,
    n_weeks: int,
    cum_quantile: float = 0.40,
    lookback_weeks: int = 52,
) -> bool:
    """
    Kaufman-style: prior N weeks compressed (low cumulative range vs history)
    and signal price breaks above prior N-week high.
    """
    if weekly.empty or n_weeks < 1:
        return False
    w = weekly.loc[weekly.index <= signal_date]
    if len(w) < n_weeks + 2:
        return False
    # Completed weeks strictly before signal week (last row may be partial week)
    completed = w.iloc[:-1] if w.index[-1] >= signal_date else w
    if len(completed) < n_weeks + 1:
        return False
    tail = completed.iloc[-n_weeks:]
    cum_rng = float(tail["rng"].sum())
    hist = completed.iloc[-(lookback_weeks + n_weeks) : -1]
    if len(hist) < n_weeks:
        return False
    cum_series = hist["rng"].rolling(n_weeks).sum().dropna()
    if cum_series.empty:
        return False
    thresh = float(cum_series.quantile(cum_quantile))
    compressed = cum_rng <= thresh
    prior_high = float(tail["high"].max())
    px = float(completed["close"].iloc[-1])
    breakout = px >= prior_high
    return bool(compressed and breakout)


def batch_gate(
    weekly_by_symbol: dict[str, pd.DataFrame],
    symbol: str,
    signal_date: pd.Timestamp,
    n_weeks: int | None,
) -> bool:
    if n_weeks is None:
        return True
    w = weekly_by_symbol.get(symbol)
    if w is None:
        return False
    return compression_breakout_ok(w, signal_date, n_weeks)
