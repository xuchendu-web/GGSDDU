"""Ensure panel exists and all engine styles agree on rankings."""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from shared.config import PANEL_CSV  # noqa: E402
from shared.engine_registry import engine_ids, load_runner  # noqa: E402
from shared.generate_synthetic_panel import write_panel  # noqa: E402
from shared.rule_spec import (  # noqa: E402
    compute_weekly_rankings,
    load_panel,
    panel_to_wide_close,
)


@pytest.fixture(scope="module")
def panel_path():
    if not PANEL_CSV.is_file():
        write_panel(PANEL_CSV)
    return PANEL_CSV


@pytest.fixture(scope="module")
def reference_rankings(panel_path):
    wide = panel_to_wide_close(load_panel(panel_path))
    return compute_weekly_rankings(wide)


def _available_engines():
    engines = []
    for eid in engine_ids():
        try:
            load_runner(eid)
            engines.append(eid)
        except ImportError:
            pass
    return engines


def _assert_same(a, b, label: str) -> None:
    merged = a.merge(b, on="week_end", suffixes=("_a", "_b"))
    assert len(merged) == len(a) == len(b), f"{label}: week count mismatch"
    for _, row in merged.iterrows():
        assert row["ranks_a"] == row["ranks_b"], (
            f"{label} rank mismatch on {row['week_end']}: "
            f"{row['ranks_a']} vs {row['ranks_b']}"
        )
        assert row["top_k_a"] == row["top_k_b"]


@pytest.mark.parametrize("engine_id", _available_engines())
def test_engine_matches_reference(panel_path, reference_rankings, engine_id):
    run = load_runner(engine_id)
    got = run(panel_path)
    _assert_same(reference_rankings, got, f"ref vs {engine_id}")


def test_at_least_eight_engines_when_polars_present():
    """Core burn requires ≥8 styles; polars is optional."""
    n = len(_available_engines())
    assert n >= 8, f"expected >=8 runnable engines, got {n}"


def test_deterministic_regeneration(panel_path):
    from shared.generate_synthetic_panel import generate_panel

    a = generate_panel()
    b = generate_panel()
    assert a.equals(b)
