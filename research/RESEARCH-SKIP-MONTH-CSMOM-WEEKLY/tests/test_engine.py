from __future__ import annotations

import numpy as np
import pandas as pd

from skip_month_csmom.engine import cross_section_formation, run_csmom, select_top_n
from skip_month_csmom.config import CsmomConfig


def test_select_top_n():
    xs = pd.Series({"a": 0.4, "b": 0.2, "c": -0.1})
    assert select_top_n(xs, 2) == ["a", "b"]


def test_skip_month_ends_before_no_skip():
    weeks = pd.date_range("2024-01-05", periods=80, freq="W-FRI")
    fast = pd.Series(np.linspace(100, 200, len(weeks)), index=weeks)
    slow = pd.Series(np.linspace(100, 110, len(weeks)), index=weeks)
    # spike last month only on fast
    fast.iloc[-4:] = fast.iloc[-5] * 1.25
    panel = pd.DataFrame({"111111": fast, "222222": slow})
    dt = weeks[-1]
    skip = cross_section_formation(panel, dt, lookback_months=3, skip_months=1)
    noskip = cross_section_formation(panel, dt, lookback_months=3, skip_months=0)
    assert float(skip["111111"]) < float(noskip["111111"])


def test_csmom_runs_with_cost():
    weeks = pd.date_range("2019-01-04", periods=120, freq="W-FRI")
    rng = np.random.default_rng(1)
    cols = {}
    for i, c in enumerate(["111111", "222222", "333333"]):
        cols[c] = 100 * np.exp(np.cumsum(rng.normal(0.002 + i * 0.001, 0.02, len(weeks))))
    panel = pd.DataFrame(cols, index=weeks)
    cheap = CsmomConfig(skip_months=1, n_seats=2, cost_side=0.0)
    dear = CsmomConfig(skip_months=1, n_seats=2, cost_side=0.01)
    a = run_csmom(panel, cheap, eval_start="2020-01-03", eval_end="2021-12-31")
    b = run_csmom(panel, dear, eval_start="2020-01-03", eval_end="2021-12-31")
    assert b.nav.iloc[-1] < a.nav.iloc[-1]


def test_no_live_ops_imports():
    import ast
    from pathlib import Path

    root = Path(__file__).resolve().parents[1]
    banned = {"strategy_exec", "live_ops", "LIVE_OPS"}
    for folder in (root / "skip_month_csmom", root / "scripts"):
        for fp in folder.rglob("*.py"):
            tree = ast.parse(fp.read_text(encoding="utf-8"), filename=str(fp))
            for node in ast.walk(tree):
                if isinstance(node, ast.Import):
                    names = {a.name.split(".")[0] for a in node.names}
                elif isinstance(node, ast.ImportFrom) and node.module:
                    names = {node.module.split(".")[0]}
                else:
                    continue
                assert not (names & banned), f"{names & banned} in {fp}"
