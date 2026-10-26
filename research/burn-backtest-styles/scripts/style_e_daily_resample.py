#!/usr/bin/env python3
"""Style E: daily indicators then explicit W-FRI resample via Grouper (not index.resample)."""

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
    breadth_daily = (wide > ma).mean(axis=1).rename("breadth")
    mom_daily = wide / wide.shift(MOM_LOOKBACK_DAYS) - 1.0

    # Long stack + Grouper resample (daily → weekly) instead of DatetimeIndex.resample.
    mom_long = mom_daily.stack(future_stack=True).rename("mom").reset_index()
    mom_long.columns = ["date", "symbol", "mom"]
    weekly_mom = (
        mom_long.groupby(["symbol", pd.Grouper(key="date", freq=RESAMPLE_RULE)])["mom"]
        .last()
        .reset_index()
        .rename(columns={"date": "week_end"})
    )

    weekly_breadth = (
        breadth_daily.to_frame()
        .groupby(pd.Grouper(freq=RESAMPLE_RULE))["breadth"]
        .last()
        .reset_index()
        .rename(columns={"date": "week_end"})
    )

    records = []
    for _, brow in weekly_breadth.iterrows():
        week_end = brow["week_end"]
        b = float(brow["breadth"])
        gate = bool(b >= BREADTH_MIN) if pd.notna(b) else False
        grp = weekly_mom.loc[weekly_mom["week_end"] == week_end]
        if not gate:
            ranks: list[str] = []
        else:
            g = grp.dropna(subset=["mom"])
            ranks = (
                g.sort_values("mom", ascending=False)["symbol"].astype(str).tolist()
            )
        records.append(
            {
                "week_end": week_end,
                "breadth": b,
                "gate_pass": gate,
                "ranks": ranks,
                "top_k": ranks[:TOP_K],
            }
        )
    return pd.DataFrame(records).sort_values("week_end").reset_index(drop=True)


def main() -> None:
    parser = argparse.ArgumentParser(description="Style E daily→weekly Grouper resample")
    parser.add_argument("--panel", type=Path, default=PANEL_CSV)
    parser.add_argument("--ensure-data", action="store_true")
    args = parser.parse_args()
    if args.ensure_data and not args.panel.is_file():
        write_panel(args.panel)
    out = run_ranking(args.panel)
    print(out[["week_end", "breadth", "gate_pass", "top_k"]].to_string(index=False))


if __name__ == "__main__":
    main()
