#!/usr/bin/env python3
"""Style F: numba-ish nested loops over numpy (no JIT required)."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

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


def _rolling_mean_last_row(arr: np.ndarray, window: int) -> np.ndarray:
    n, m = arr.shape
    out = np.full(m, np.nan)
    if n < window:
        return out
    for j in range(m):
        out[j] = np.mean(arr[-window:, j])
    return out


def run_ranking(panel_path: Path = PANEL_CSV) -> pd.DataFrame:
    df = pd.read_csv(panel_path, parse_dates=["date"])
    wide = df.pivot(index="date", columns="symbol", values="close").sort_index()
    syms = wide.columns.to_numpy()
    values = wide.to_numpy(dtype=float)
    dates = wide.index
    week_ends = wide.resample(RESAMPLE_RULE).last().index

    records = []
    for week_end in week_ends:
        idx = dates.get_indexer([week_end], method="pad")[0]
        if idx < 0:
            continue
        hist = values[: idx + 1]
        last = hist[-1]
        ma = _rolling_mean_last_row(hist, MA_WINDOW)
        above = last > ma
        valid_ma = ~np.isnan(ma)
        breadth = float(np.mean(above[valid_ma])) if valid_ma.any() else float("nan")
        gate = bool(breadth >= BREADTH_MIN) if not np.isnan(breadth) else False
        ranks: list[str] = []
        if gate and idx >= MOM_LOOKBACK_DAYS:
            mom = last / hist[-1 - MOM_LOOKBACK_DAYS] - 1.0
            pairs = [(syms[j], mom[j]) for j in range(len(syms)) if not np.isnan(mom[j])]
            pairs.sort(key=lambda x: -x[1])
            ranks = [p[0] for p in pairs]
        records.append(
            {
                "week_end": week_end,
                "breadth": breadth,
                "gate_pass": gate,
                "ranks": ranks,
                "top_k": ranks[:TOP_K],
            }
        )
    return pd.DataFrame(records)


def main() -> None:
    parser = argparse.ArgumentParser(description="Style F numba-ish loop ranks")
    parser.add_argument("--panel", type=Path, default=PANEL_CSV)
    parser.add_argument("--ensure-data", action="store_true")
    args = parser.parse_args()
    if args.ensure_data and not args.panel.is_file():
        write_panel(args.panel)
    out = run_ranking(args.panel)
    print(out[["week_end", "breadth", "gate_pass", "top_k"]].to_string(index=False))


if __name__ == "__main__":
    main()
