"""Ensure panel exists and three styles agree on rankings."""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from shared.config import PANEL_CSV  # noqa: E402
from shared.generate_synthetic_panel import write_panel  # noqa: E402
from scripts.style_a_vector import run_ranking as run_a  # noqa: E402
from scripts.style_b_event import run_ranking as run_b  # noqa: E402
from scripts.style_c_pandas import run_ranking as run_c  # noqa: E402


@pytest.fixture(scope="module")
def panel_path():
    if not PANEL_CSV.is_file():
        write_panel(PANEL_CSV)
    return PANEL_CSV


def _assert_same(a, b, label: str) -> None:
    merged = a.merge(b, on="week_end", suffixes=("_a", "_b"))
    assert len(merged) == len(a) == len(b), f"{label}: week count mismatch"
    for _, row in merged.iterrows():
        assert row["ranks_a"] == row["ranks_b"], (
            f"{label} rank mismatch on {row['week_end']}: "
            f"{row['ranks_a']} vs {row['ranks_b']}"
        )
        assert row["top_k_a"] == row["top_k_b"]


def test_three_styles_weekly_ranks_match(panel_path):
    ra, rb, rc = run_a(panel_path), run_b(panel_path), run_c(panel_path)
    _assert_same(ra, rb, "A vs B")
    _assert_same(ra, rc, "A vs C")
    _assert_same(rb, rc, "B vs C")


def test_deterministic_regeneration(panel_path):
    from shared.generate_synthetic_panel import generate_panel

    a = generate_panel()
    b = generate_panel()
    assert a.equals(b)
