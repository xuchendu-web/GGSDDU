#!/usr/bin/env python3
"""Style E: wide-matrix daily features then explicit resample-to-weekly."""

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


def run_ranking(panel_path: Path = PANEL_CSV) -> pd.DataFrame:
    df = pd.read_csv(panel_path, parse_dates=["date"])
    wide = df.pivot(index="date", columns="symbol", values="close").sort_index()

    daily_breadth = (wide > wide.rolling(MA_WINDOW, min_periods=MA_WINDOW).mean()).mean(
        axis=1
    )
    daily_mom = wide / wide.shift(MOM_LOOKBACK_DAYS) - 1.0

    weekly_breadth = daily_breadth.resample(RESAMPLE_RULE).last()
    weekly_mom = daily_mom.resample(RESAMPLE_RULE).last()

    records = []
    for week_end in weekly_mom.index:
        b = weekly_breadth.loc[week_end]
        gate = bool(b >= BREADTH_MIN) if pd.notna(b) else False
        row = weekly_mom.loc[week_end]
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
    parser = argparse.ArgumentParser(description="Style E daily-resample ranks")
    parser.add_argument("--panel", type=Path, default=PANEL_CSV)
    parser.add_argument("--ensure-data", action="store_true")
    args = parser.parse_args()
    if args.ensure_data and not args.panel.is_file():
        write_panel(args.panel)
    out = run_ranking(args.panel)
    print(out[["week_end", "breadth", "gate_pass", "top_k"]].to_string(index=False))


if __name__ == "__main__":
    main()
