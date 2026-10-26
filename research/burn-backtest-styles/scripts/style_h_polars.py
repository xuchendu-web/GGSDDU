#!/usr/bin/env python3
"""Style H: Polars for panel transforms; pandas only for W-FRI resample."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from shared.config import (  # noqa: E402
    BREADTH_MIN,
    MA_WINDOW,
    MOM_LOOKBACK_DAYS,
    PANEL_CSV,
    RESAMPLE_RULE,
    TOP_K,
)
from shared.generate_synthetic_panel import write_panel  # noqa: E402

try:
    import polars as pl
except ImportError:  # pragma: no cover
    pl = None  # type: ignore


def _pl_to_wide_mom(df: pl.DataFrame) -> tuple[pd.Series, pd.DataFrame]:
    """Build daily breadth and wide momentum without polars.to_pandas() on full panel."""
    breadth_rows = (
        df.group_by("date")
        .agg(pl.col("above_ma").fill_null(False).mean().alias("breadth"))
        .sort("date")
        .iter_rows()
    )
    breadth_s = pd.Series({d: b for d, b in breadth_rows})
    breadth_s.index = pd.to_datetime(breadth_s.index)

    dates = df.get_column("date").to_list()
    symbols = df.get_column("symbol").to_list()
    mom_vals = df.get_column("mom").to_list()
    mom_map: dict = {}
    for d, sym, m in zip(dates, symbols, mom_vals):
        mom_map.setdefault(d, {})[sym] = m
    wide_mom = pd.DataFrame.from_dict(mom_map, orient="index").sort_index()
    wide_mom.index = pd.to_datetime(wide_mom.index)
    return breadth_s, wide_mom


def run_ranking(panel_path: Path = PANEL_CSV) -> pd.DataFrame:
    if pl is None:
        raise ImportError("polars is not installed; pip install polars")

    df = pl.read_csv(panel_path, try_parse_dates=True)
    df = df.sort(["symbol", "date"])
    df = df.with_columns(
        pl.col("close")
        .rolling_mean(MA_WINDOW, min_samples=MA_WINDOW)
        .over("symbol")
        .alias("ma")
    )
    df = df.with_columns((pl.col("close") > pl.col("ma")).alias("above_ma"))
    df = df.with_columns(
        (
            pl.col("close")
            / pl.col("close").shift(MOM_LOOKBACK_DAYS).over("symbol")
            - 1.0
        ).alias("mom")
    )

    breadth_s, wide_mom = _pl_to_wide_mom(df)
    w_breadth = breadth_s.resample(RESAMPLE_RULE).last()
    w_mom = wide_mom.resample(RESAMPLE_RULE).last()

    records = []
    for week_end in w_mom.index:
        b = w_breadth.loc[week_end]
        gate = bool(b >= BREADTH_MIN) if pd.notna(b) else False
        row = w_mom.loc[week_end]
        if not gate:
            ranks = []
        else:
            ranks = (
                row.dropna()
                .sort_values(ascending=False)
                .index.astype(str)
                .tolist()
            )
        records.append(
            {
                "week_end": week_end,
                "breadth": float(b) if pd.notna(b) else float("nan"),
                "gate_pass": gate,
                "ranks": ranks,
                "top_k": ranks[:TOP_K],
            }
        )
    return pd.DataFrame(records)


def main() -> None:
    parser = argparse.ArgumentParser(description="Style H polars ranks")
    parser.add_argument("--panel", type=Path, default=PANEL_CSV)
    parser.add_argument("--ensure-data", action="store_true")
    args = parser.parse_args()
    if args.ensure_data and not args.panel.is_file():
        write_panel(args.panel)
    out = run_ranking(args.panel)
    print(out[["week_end", "breadth", "gate_pass", "top_k"]].to_string(index=False))


if __name__ == "__main__":
    main()
