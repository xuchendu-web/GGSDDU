"""Weekly close panel: Friday-aligned, research pool only."""

from __future__ import annotations

import json
from pathlib import Path

import pandas as pd

from .config import AUM_MIN_YI, DATA


def to_week_friday(ts: pd.Timestamp) -> pd.Timestamp:
    ts = pd.Timestamp(ts).normalize()
    return ts + pd.Timedelta(days=(4 - int(ts.weekday())) % 7)


def load_universe(path: Path | None = None, aum_min: float = AUM_MIN_YI) -> pd.DataFrame:
    fp = Path(path) if path else DATA / "universe.csv"
    df = pd.read_csv(fp)
    df["code"] = df["code"].astype(str).str.zfill(6)
    return df.loc[df["aum"] >= aum_min].copy()


def week_json_to_series(path: Path) -> pd.Series:
    rec = json.loads(Path(path).read_text(encoding="utf-8"))
    bars = rec.get("bars") or []
    if not bars:
        return pd.Series(dtype=float)
    idx = pd.to_datetime([b["date"] for b in bars])
    px = pd.Series([float(b["c"]) for b in bars], index=idx, dtype=float)
    px = px[px > 0]
    if px.empty:
        return px
    fri = pd.DatetimeIndex([to_week_friday(t) for t in px.index])
    out = pd.Series(px.to_numpy(), index=fri, dtype=float)
    return out[~out.index.duplicated(keep="last")].sort_index()


def build_weekly_panel(week_dir: Path, codes: list[str]) -> pd.DataFrame:
    cols: dict[str, pd.Series] = {}
    for code in codes:
        fp = Path(week_dir) / f"{code}.json"
        if not fp.exists():
            continue
        s = week_json_to_series(fp)
        if len(s) >= 8:
            cols[code] = s
    if not cols:
        raise FileNotFoundError(f"no weekly series under {week_dir}")
    panel = pd.DataFrame(cols).sort_index()
    return panel


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
