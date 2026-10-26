#!/usr/bin/env python3
"""Style D: native weekly-bar table (Period groupby), daily signals at week-end."""

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

    ma = wide.rolling(MA_WINDOW, min_periods=MA_WINDOW).mean()
    breadth_daily = (wide > ma).mean(axis=1)
    mom_daily = wide / wide.shift(MOM_LOOKBACK_DAYS) - 1.0

    # Materialize weekly bars (last close per symbol per week) — storage path only.
    long = df.sort_values(["symbol", "date"]).copy()
    long["week_period"] = long["date"].dt.to_period(RESAMPLE_RULE)
    _ = long.groupby(["week_period", "symbol"], as_index=False)["close"].last()

    day_period = wide.index.to_period(RESAMPLE_RULE)
    records = []
    for per in day_period.unique().sort_values():
        # W-FRI label (Friday), signals from last trading day in the period (matches resample).
        week_end = per.to_timestamp(how="end").normalize()
        mask = day_period == per
        last_obs = wide.index[mask][-1]
        b = float(breadth_daily.loc[last_obs])
        gate = bool(b >= BREADTH_MIN) if pd.notna(b) else False
        row = mom_daily.loc[last_obs]
        if not gate:
            ranks: list[str] = []
        else:
            valid = row.dropna()
            ranks = valid.sort_values(ascending=False).index.astype(str).tolist()
        records.append(
            {
                "week_end": week_end,
                "breadth": b,
                "gate_pass": gate,
                "ranks": ranks,
                "top_k": ranks[:TOP_K],
            }
        )
    return pd.DataFrame(records)


def main() -> None:
    parser = argparse.ArgumentParser(description="Style D weekly-bar calendar ranks")
    parser.add_argument("--panel", type=Path, default=PANEL_CSV)
    parser.add_argument("--ensure-data", action="store_true")
    args = parser.parse_args()
    if args.ensure_data and not args.panel.is_file():
        write_panel(args.panel)
    out = run_ranking(args.panel)
    print(out[["week_end", "breadth", "gate_pass", "top_k"]].to_string(index=False))


if __name__ == "__main__":
    main()
