#!/usr/bin/env python3
"""Style I: numexpr for vector comparisons on wide close matrix."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

import numexpr as ne
import numpy as np
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
    syms = wide.columns
    close = wide.to_numpy(dtype=np.float64)
    ma = wide.rolling(MA_WINDOW, min_periods=MA_WINDOW).mean().to_numpy(dtype=np.float64)

    above = ne.evaluate("close > ma")
    breadth_daily = np.nanmean(above.astype(np.float64), axis=1)
    lag = wide.shift(MOM_LOOKBACK_DAYS).to_numpy(dtype=np.float64)
    mom = ne.evaluate("close / lag - 1")

    breadth_s = pd.Series(breadth_daily, index=wide.index)
    mom_df = pd.DataFrame(mom, index=wide.index, columns=syms)

    w_breadth = breadth_s.resample(RESAMPLE_RULE).last()
    w_mom = mom_df.resample(RESAMPLE_RULE).last()

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
    parser = argparse.ArgumentParser(description="Style I numexpr ranks")
    parser.add_argument("--panel", type=Path, default=PANEL_CSV)
    parser.add_argument("--ensure-data", action="store_true")
    args = parser.parse_args()
    if args.ensure_data and not args.panel.is_file():
        write_panel(args.panel)
    out = run_ranking(args.panel)
    print(out[["week_end", "breadth", "gate_pass", "top_k"]].to_string(index=False))


if __name__ == "__main__":
    main()
