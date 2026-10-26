from __future__ import annotations

import json
import os
from pathlib import Path

import numpy as np
import pandas as pd

# Research pool: liquid CN ETFs (AUM proxy list); not LIVE universe.
DEFAULT_UNIVERSE = [
    "510300", "510500", "512100", "159915", "588000",
    "512890", "515180", "512480", "512660", "512880",
    "513100", "513500", "518880", "511010", "511260",
    "159920", "513130", "512010", "512690", "512170",
    "159949", "512000", "512800", "515790", "516160",
    "562500", "159819", "512760", "515030", "512980",
]


def cache_dir() -> Path:
    env = os.environ.get("RESEARCH_CACHE")
    if env:
        return Path(env)
    return Path(__file__).resolve().parents[1] / "COMPRESSION-BREAKOUT-LIVE1430" / "data" / "research_cache"


def _symbol_path(code: str) -> Path:
    return cache_dir() / "daily" / f"{code}.parquet"


def _yf_ticker(code: str) -> str:
    if code.startswith(("5", "6")):
        return f"{code}.SS"
    return f"{code}.SZ"


def _fetch_daily_yfinance(code: str) -> pd.DataFrame | None:
    import yfinance as yf

    t = _yf_ticker(code)
    raw = yf.download(t, start="2019-06-01", progress=False, auto_adjust=True)
    if raw is None or raw.empty:
        return None
    if isinstance(raw.columns, pd.MultiIndex):
        raw.columns = [c[0].lower() if isinstance(c, tuple) else c for c in raw.columns]
    else:
        raw.columns = [str(c).lower() for c in raw.columns]
    df = raw.rename(columns={"adj close": "close"}).copy()
    for col in ("open", "high", "low", "close", "volume"):
        if col not in df.columns:
            return None
    df = df[["open", "high", "low", "close", "volume"]].astype(float)
    return df.sort_index()


def _fetch_daily_akshare(code: str) -> pd.DataFrame | None:
    import akshare as ak

    df = ak.fund_etf_hist_em(symbol=code, period="daily", adjust="qfq")
    if df is None or df.empty:
        return None
    df = df.rename(
        columns={
            "日期": "date",
            "开盘": "open",
            "收盘": "close",
            "最高": "high",
            "最低": "low",
            "成交量": "volume",
        }
    )
    df["date"] = pd.to_datetime(df["date"])
    return df.set_index("date").sort_index()[["open", "high", "low", "close", "volume"]].astype(float)


def build_cache_from_market(universe: list[str] | None = None, force: bool = False) -> Path:
    universe = universe or DEFAULT_UNIVERSE
    root = cache_dir()
    daily_dir = root / "daily"
    daily_dir.mkdir(parents=True, exist_ok=True)
    source = "yfinance"
    for code in universe:
        p = _symbol_path(code)
        if p.exists() and not force:
            continue
        df = None
        try:
            df = _fetch_daily_akshare(code)
            source = "akshare_fund_etf_hist_em"
        except Exception:
            df = None
        if df is None or df.empty:
            df = _fetch_daily_yfinance(code)
            source = "yfinance_qfq_proxy"
        if df is None or df.empty:
            continue
        df.to_parquet(p)
    meta = {"source": source, "universe": universe, "note": "research pool only"}
    (root / "meta.json").write_text(json.dumps(meta, ensure_ascii=False, indent=2), encoding="utf-8")
    return root


def load_panel(universe: list[str] | None = None) -> dict[str, pd.DataFrame]:
    universe = universe or DEFAULT_UNIVERSE
    root = cache_dir()
    if not (root / "daily").exists() or not any((root / "daily").glob("*.parquet")):
        build_cache_from_market(universe)
    panel: dict[str, pd.DataFrame] = {}
    for code in universe:
        p = _symbol_path(code)
        if not p.exists():
            continue
        panel[code] = pd.read_parquet(p)
    return panel


def friday_signal_dates(panel: dict[str, pd.DataFrame], start: str, end: str) -> pd.DatetimeIndex:
    """Calendar Fridays on benchmark (510300 if present, else longest history)."""
    bench = panel.get("510300")
    if bench is None:
        bench = max(panel.values(), key=len)
    w = bench.loc[start:end].index
    fris = w[w.dayofweek == 4]
    return pd.DatetimeIndex(sorted(fris))


def sharpe20(close: pd.Series, as_of: pd.Timestamp) -> float:
    s = close.loc[:as_of].tail(21)
    if len(s) < 21:
        return np.nan
    r = s.pct_change().dropna()
    if r.std() == 0:
        return np.nan
    return float(r.mean() / r.std() * np.sqrt(252))


def breadth_b45(panel: dict[str, pd.DataFrame], as_of: pd.Timestamp) -> float:
    hits = 0
    total = 0
    for df in panel.values():
        s = df["close"].loc[:as_of]
        if len(s) < 21:
            continue
        r20 = s.iloc[-1] / s.iloc[-21] - 1.0
        total += 1
        if r20 > 0:
            hits += 1
    return hits / total if total else 0.0
