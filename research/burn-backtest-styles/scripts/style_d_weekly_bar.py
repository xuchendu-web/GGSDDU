#!/usr/bin/env python3
"""Style D: weekly bar table — outer loop on W-FRI bars, metrics from daily history."""

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
    week_ends = wide.resample(RESAMPLE_RULE).last().index

    records = []
    for week_end in week_ends:
        hist = wide.loc[wide.index <= week_end]
        last = hist.iloc[-1]
        ma_row = hist.rolling(MA_WINDOW, min_periods=MA_WINDOW).mean().iloc[-1]
        breadth = (last > ma_row).mean()
        gate = bool(breadth >= BREADTH_MIN) if pd.notna(breadth) else False
        if len(hist) > MOM_LOOKBACK_DAYS:
            mom = last / hist.iloc[-1 - MOM_LOOKBACK_DAYS] - 1.0
        else:
            mom = pd.Series(dtype=float)
        if not gate:
            ranks: list[str] = []
        else:
            ranks = mom.dropna().sort_values(ascending=False).index.astype(str).tolist()
        records.append(
            {
                "week_end": week_end,
                "breadth": float(breadth),
                "gate_pass": gate,
                "ranks": ranks,
                "top_k": ranks[:TOP_K],
            }
        )
    return pd.DataFrame(records)


def main() -> None:
    parser = argparse.ArgumentParser(description="Style D weekly-bar ranks")
    parser.add_argument("--panel", type=Path, default=PANEL_CSV)
    parser.add_argument("--ensure-data", action="store_true")
    args = parser.parse_args()
    if args.ensure_data and not args.panel.is_file():
        write_panel(args.panel)
    out = run_ranking(args.panel)
    print(out[["week_end", "breadth", "gate_pass", "top_k"]].to_string(index=False))


if __name__ == "__main__":
    main()
