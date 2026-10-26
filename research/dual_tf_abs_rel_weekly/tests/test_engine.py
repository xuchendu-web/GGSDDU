from __future__ import annotations

import ast
import numpy as np
import pandas as pd
from pathlib import Path

from dual_tf_abs_rel.config import DualTfConfig
from dual_tf_abs_rel.engine import run_dual_tf, select_names_dual_tf


def test_select_dual_tf_gates_on_abs_ranks_on_rel():
    abs_ret = pd.Series({"a": 0.5, "b": 0.3, "c": -0.1, "d": 0.2})
    rel_ret = pd.Series({"a": 0.1, "b": 0.4, "c": 0.9, "d": 0.15})
    got = select_names_dual_tf(abs_ret, rel_ret, 2, 0.0, True)
    assert got == ["b", "d"]


def test_xs_only_ignores_abs():
    abs_ret = pd.Series({"a": -0.5, "b": -0.1})
    rel_ret = pd.Series({"a": 0.2, "b": 0.1})
    assert select_names_dual_tf(abs_ret, rel_ret, 1, 0.0, False) == ["a"]


def _synth_panel() -> pd.DataFrame:
    weeks = pd.date_range("2018-01-05", periods=160, freq="W-FRI")
    rng = np.random.default_rng(3)
    fast = 1.0 * np.exp(np.cumsum(np.full(len(weeks), 0.012)))
    slow = 1.0 * np.exp(np.cumsum(np.full(len(weeks), 0.002)))
    fast[-30:] = fast[-31] * np.exp(np.cumsum(np.full(30, -0.03)))
    noise = 1.0 * np.exp(np.cumsum(rng.normal(0.0, 0.008, len(weeks))))
    return pd.DataFrame({"111111": fast, "222222": slow, "333333": noise}, index=weeks)


def test_dual_tf_runs_with_split_lookbacks():
    panel = _synth_panel()
    cfg = DualTfConfig(
        abs_lookback=20,
        abs_skip=1,
        rel_lookback=8,
        rel_skip=1,
        n_seats=1,
        apply_absolute=True,
        cost_side=0.0,
        name="t",
    )
    res = run_dual_tf(panel, cfg, eval_start="2019-01-04", eval_end="2021-01-29")
    assert len(res.nav) > 10
    assert res.avg_gross <= 1.0


def test_no_live_ops_imports():
    banned = {"strategy_exec", "live_ops", "LIVE_OPS"}
    root = Path(__file__).resolve().parents[1]
    for folder in (root / "dual_tf_abs_rel", root / "scripts"):
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
