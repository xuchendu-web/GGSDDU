"""Reference implementation of the toy rule (used by tests and compare)."""

from __future__ import annotations

import pandas as pd

from shared.config import (
    BREADTH_MIN,
    MA_WINDOW,
    MOM_LOOKBACK_DAYS,
    RESAMPLE_RULE,
    TOP_K,
)


def load_panel(path) -> pd.DataFrame:
    df = pd.read_csv(path, parse_dates=["date"])
    return df.sort_values(["date", "symbol"]).reset_index(drop=True)


def panel_to_wide_close(df: pd.DataFrame) -> pd.DataFrame:
    wide = df.pivot(index="date", columns="symbol", values="close").sort_index()
    return wide


def compute_weekly_rankings(wide_close: pd.DataFrame) -> pd.DataFrame:
    """
    Return one row per rebalance week with ordered rank list (best momentum first).

    Columns: week_end, breadth, gate_pass, ranks (list of symbols), top_k (list)
    """
    ma = wide_close.rolling(MA_WINDOW, min_periods=MA_WINDOW).mean()
    above = wide_close > ma
    breadth = above.mean(axis=1)

    mom = wide_close / wide_close.shift(MOM_LOOKBACK_DAYS) - 1.0

    weekly_close = wide_close.resample(RESAMPLE_RULE).last()
    weekly_breadth = breadth.resample(RESAMPLE_RULE).last()
    weekly_mom = mom.resample(RESAMPLE_RULE).last()

    records = []
    for week_end in weekly_close.index:
        b = weekly_breadth.loc[week_end]
        gate = bool(b >= BREADTH_MIN) if pd.notna(b) else False
        m = weekly_mom.loc[week_end]
        valid = m.dropna()
        if not gate or valid.empty:
            ranks: list[str] = []
        else:
            ranks = valid.sort_values(ascending=False).index.astype(str).tolist()
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


def rankings_to_compare_frame(rank_df: pd.DataFrame) -> pd.DataFrame:
    """Flatten for CSV merge: week_end + rank_1..rank_n + top_k joined."""
    max_len = max((len(r) for r in rank_df["ranks"]), default=0)
    out = rank_df[["week_end", "breadth", "gate_pass"]].copy()
    for i in range(max_len):
        out[f"rank_{i + 1}"] = rank_df["ranks"].apply(
            lambda xs, j=i: xs[j] if j < len(xs) else ""
        )
    out["top_k"] = rank_df["top_k"].apply(lambda xs: ",".join(xs))
    return out
