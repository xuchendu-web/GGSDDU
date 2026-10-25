#!/usr/bin/env python3
"""Generate fixed-seed synthetic ETF daily panel (long format)."""

from __future__ import annotations

import argparse
from pathlib import Path

import numpy as np
import pandas as pd

from shared.config import (
    DATA_DIR,
    N_SYMBOLS,
    N_TRADING_DAYS,
    PANEL_CSV,
    SEED,
    SYMBOL_PREFIX,
)


def generate_panel(
    seed: int = SEED,
    n_symbols: int = N_SYMBOLS,
    n_days: int = N_TRADING_DAYS,
) -> pd.DataFrame:
    rng = np.random.default_rng(seed)
    dates = pd.bdate_range("2024-01-02", periods=n_days, freq="B")
    symbols = [f"{SYMBOL_PREFIX}{i:02d}" for i in range(n_symbols)]

    rows: list[dict] = []
    # Geometric Brownian-style paths with symbol-specific drift/vol.
    for i, sym in enumerate(symbols):
        mu = rng.uniform(-0.0002, 0.0008)
        sigma = rng.uniform(0.008, 0.025)
        shocks = rng.normal(mu, sigma, size=n_days)
        log_price = np.cumsum(shocks)
        close = 100.0 * np.exp(log_price)
        for d, c in zip(dates, close):
            rows.append({"date": d, "symbol": sym, "close": float(c)})

    df = pd.DataFrame(rows)
    df["date"] = pd.to_datetime(df["date"])
    return df.sort_values(["date", "symbol"]).reset_index(drop=True)


def write_panel(path=PANEL_CSV) -> pd.DataFrame:
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    df = generate_panel()
    df.to_csv(path, index=False)
    return df


def main() -> None:
    parser = argparse.ArgumentParser(description="Write synthetic_panel.csv")
    parser.add_argument(
        "--output",
        type=Path,
        default=PANEL_CSV,
        help="Output CSV path",
    )
    args = parser.parse_args()
    df = write_panel(args.output)
    print(f"Wrote {len(df)} rows, {df['symbol'].nunique()} symbols -> {args.output}")


if __name__ == "__main__":
    main()
