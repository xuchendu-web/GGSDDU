#!/usr/bin/env python3
"""Style C: pure pandas resample / groupby pipeline on long-format panel."""

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
    df = df.sort_values(["symbol", "date"])
    df["ma"] = df.groupby("symbol")["close"].transform(
        lambda s: s.rolling(MA_WINDOW, min_periods=MA_WINDOW).mean()
    )
    df["above_ma"] = df["close"] > df["ma"]
    df["mom"] = df.groupby("symbol")["close"].transform(
        lambda s: s / s.shift(MOM_LOOKBACK_DAYS) - 1.0
    )

    daily_breadth = (
        df.groupby("date")["above_ma"].mean().rename("breadth").to_frame()
    )
    daily_breadth.index = pd.to_datetime(daily_breadth.index)

    weekly = (
        df.set_index("date")
        .groupby("symbol")
        .resample(RESAMPLE_RULE)
        .agg({"mom": "last", "close": "last"})
        .reset_index()
        .rename(columns={"date": "week_end"})
    )
    weekly_breadth = daily_breadth.resample(RESAMPLE_RULE).last().reset_index()
    weekly_breadth.columns = ["week_end", "breadth"]

    records = []
    for week_end, grp in weekly.groupby("week_end"):
        b_row = weekly_breadth.loc[weekly_breadth["week_end"] == week_end, "breadth"]
        b = float(b_row.iloc[0]) if len(b_row) else float("nan")
        gate = bool(b >= BREADTH_MIN) if pd.notna(b) else False
        if not gate:
            ranks = []
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
    out = pd.DataFrame(records).sort_values("week_end").reset_index(drop=True)
    return out


def main() -> None:
    parser = argparse.ArgumentParser(description="Style C pandas resample ranks")
    parser.add_argument("--panel", type=Path, default=PANEL_CSV)
    parser.add_argument("--ensure-data", action="store_true")
    args = parser.parse_args()
    if args.ensure_data and not args.panel.is_file():
        write_panel(args.panel)
    out = run_ranking(args.panel)
    print(out[["week_end", "breadth", "gate_pass", "top_k"]].to_string(index=False))


if __name__ == "__main__":
    main()
