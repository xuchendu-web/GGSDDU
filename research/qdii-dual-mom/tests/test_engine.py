"""Unit tests for QDII dual-momentum selection."""

from __future__ import annotations

import pandas as pd

from qdii_dual_mom.config import QdiiDmConfig
from qdii_dual_mom.engine import run_qdii_dual_mom, select_names


def _synthetic_panel() -> pd.DataFrame:
    idx = pd.date_range("2019-06-07", periods=80, freq="W-FRI")
    a = pd.Series(range(100, 180), index=idx, dtype=float)
    b = pd.Series([100 - i * 0.5 for i in range(80)], index=idx, dtype=float)
    c = pd.Series([100 + (i % 5) for i in range(80)], index=idx, dtype=float)
    return pd.DataFrame({"111111": a, "222222": b, "333333": c})


def test_select_excludes_falling_name():
    panel = _synthetic_panel()
    cfg = QdiiDmConfig(ma_weeks=4, r12_lookback=4, n_seats=2, name="t")
    names = select_names(panel, len(panel) - 1, cfg)
    assert "222222" not in names
    assert "111111" in names


def test_run_produces_nav():
    panel = _synthetic_panel()
    cfg = QdiiDmConfig(ma_weeks=4, r12_lookback=4, n_seats=2, name="t")
    res = run_qdii_dual_mom(panel, cfg, eval_start="2020-01-03", eval_end="2020-12-31")
    assert len(res.nav) > 10
    assert res.nav.iloc[-1] > 0
