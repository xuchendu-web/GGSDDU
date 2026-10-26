"""Pairwise ranking agreement helpers."""

from __future__ import annotations

import pandas as pd


def top_k_agreement(a: pd.DataFrame, b: pd.DataFrame) -> tuple[float, int, int]:
    merged = a.merge(b, on="week_end", suffixes=("_a", "_b"))
    if merged.empty:
        return 0.0, 0, 0
    matches = int((merged["top_k_a"] == merged["top_k_b"]).sum())
    n = len(merged)
    return matches / n, matches, n


def rank_list_agreement(a: pd.DataFrame, b: pd.DataFrame) -> tuple[float, int, int]:
    merged = a.merge(b, on="week_end", suffixes=("_a", "_b"))
    if merged.empty:
        return 0.0, 0, 0
    matches = int((merged["ranks_a"] == merged["ranks_b"]).sum())
    n = len(merged)
    return matches / n, matches, n


def agreement_matrix(
    results: dict[str, pd.DataFrame],
    metric: str = "top_k",
) -> pd.DataFrame:
    """Symmetric matrix of pairwise agreement rates (1.0 = identical every week)."""
    ids = sorted(results.keys())
    mat = pd.DataFrame(index=ids, columns=ids, dtype=float)
    for i in ids:
        for j in ids:
            if i == j:
                mat.loc[i, j] = 1.0
                continue
            fn = top_k_agreement if metric == "top_k" else rank_list_agreement
            rate, _, _ = fn(results[i], results[j])
            mat.loc[i, j] = rate
    return mat
