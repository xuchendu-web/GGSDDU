"""Reuse frozen weekly panel + B45 face from dual_momentum_weekly."""

from __future__ import annotations

from pathlib import Path

import pandas as pd

from .config import DATA


def load_weekly_panel(path: Path | None = None) -> pd.DataFrame:
    fp = Path(path) if path else DATA / "weekly_panel.parquet"
    panel = pd.read_parquet(fp)
    panel.index = pd.to_datetime(panel.index)
    panel.columns = [str(c).zfill(6) for c in panel.columns]
    return panel.sort_index()


def load_b45_nav(path: Path | None = None) -> pd.Series:
    fp = Path(path) if path else DATA / "nav_LIVE1430-B45-S20.csv"
    df = pd.read_csv(fp)
    col = "nav" if "nav" in df.columns else df.columns[-1]
    date_col = df.columns[0]
    s = pd.Series(df[col].astype(float).to_numpy(), index=pd.to_datetime(df[date_col]))
    return s[~s.index.duplicated(keep="last")].sort_index()
