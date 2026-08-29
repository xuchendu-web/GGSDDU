"""动量 / 溢价 / BIAS 口径。

对齐 EarlETF 文章：
- N 日涨跌幅（含当日）= 最新价 / REF(收盘, N) - 1，至少需要 N+1 根 K 线。
- BIAS_N = (最新价 - MA_N) / MA_N，MA 用含当日的复权收盘。
- 目标价 = MA_N * (1 + 阈值)，即 BIAS 打到该阈值时的价格。
- 溢价率 = (最新价 - IOPV) / IOPV，不直接采信接口里的「折价率」符号。
"""

from __future__ import annotations

from typing import Iterable

import numpy as np
import pandas as pd


def _to_float_series(values: Iterable[float] | pd.Series | np.ndarray) -> pd.Series:
    series = pd.to_numeric(pd.Series(list(values) if not isinstance(values, pd.Series) else values), errors="coerce")
    return series.astype(float)


def n_day_return(closes: Iterable[float] | pd.Series, n: int) -> float:
    """N 日涨跌幅（含当日）：最新价相对 N 根之前收盘。"""
    if n <= 0:
        return float("nan")
    series = _to_float_series(closes).dropna()
    if len(series) < n + 1:
        return float("nan")
    base = float(series.iloc[-(n + 1)])
    last = float(series.iloc[-1])
    if base == 0:
        return float("nan")
    return last / base - 1.0


def moving_average(closes: Iterable[float] | pd.Series, n: int) -> float:
    if n <= 0:
        return float("nan")
    series = _to_float_series(closes).dropna()
    if len(series) < n:
        return float("nan")
    return float(series.iloc[-n:].mean())


def bias(closes: Iterable[float] | pd.Series, n: int, last_price: float | None = None) -> float:
    """BIAS_N。last_price 为空时用序列最后一根。"""
    series = _to_float_series(closes).dropna()
    if last_price is not None and np.isfinite(last_price):
        if series.empty:
            return float("nan")
        series = pd.concat([series.iloc[:-1], pd.Series([float(last_price)])], ignore_index=True)
    ma = moving_average(series, n)
    price = float(series.iloc[-1]) if not series.empty else float("nan")
    if not np.isfinite(ma) or ma == 0 or not np.isfinite(price):
        return float("nan")
    return price / ma - 1.0


def target_price(closes: Iterable[float] | pd.Series, n: int, bias_threshold: float) -> float:
    """BIAS 达到阈值时的价格。bias_threshold=0.10 表示 10%。"""
    ma = moving_average(closes, n)
    if not np.isfinite(ma):
        return float("nan")
    return ma * (1.0 + bias_threshold)


def premium_rate(last_price: float, iopv: float) -> float:
    """溢价率 = (市价 - IOPV) / IOPV。"""
    price = float(last_price) if last_price is not None else float("nan")
    nav = float(iopv) if iopv is not None else float("nan")
    if not np.isfinite(price) or not np.isfinite(nav) or nav == 0:
        return float("nan")
    return price / nav - 1.0


def overlay_live_close(hist: pd.DataFrame, live_price: float, trade_date: str | None) -> pd.Series:
    """把实时价叠到日线收盘上，供盘中 BIAS / N 日涨跌使用。"""
    if hist is None or hist.empty or "收盘" not in hist.columns:
        if np.isfinite(live_price):
            return pd.Series([float(live_price)])
        return pd.Series(dtype=float)

    work = hist.copy()
    work["收盘"] = pd.to_numeric(work["收盘"], errors="coerce")
    if "日期" in work.columns:
        work["日期"] = pd.to_datetime(work["日期"], errors="coerce").dt.strftime("%Y-%m-%d")
        work = work.dropna(subset=["日期", "收盘"]).sort_values("日期")
        if trade_date:
            if trade_date in set(work["日期"]):
                work.loc[work["日期"] == trade_date, "收盘"] = float(live_price)
            elif np.isfinite(live_price):
                extra = pd.DataFrame([{"日期": trade_date, "收盘": float(live_price)}])
                work = pd.concat([work, extra], ignore_index=True)
        elif np.isfinite(live_price) and not work.empty:
            work.iloc[-1, work.columns.get_loc("收盘")] = float(live_price)
    elif np.isfinite(live_price) and not work.empty:
        work.iloc[-1, work.columns.get_loc("收盘")] = float(live_price)
    return work["收盘"].astype(float)
