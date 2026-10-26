from __future__ import annotations

import numpy as np
import pandas as pd

from dual_momentum.config import DualMomConfig
from dual_momentum.engine import run_dual_momentum, select_names, skip_lookback_return
from dual_momentum.panel import to_week_friday


def test_to_week_friday_maps_thu_to_fri():
    assert to_week_friday(pd.Timestamp("2026-10-22")).date().isoformat() == "2026-10-23"
    assert to_week_friday(pd.Timestamp("2026-10-23")).date().isoformat() == "2026-10-23"


def test_skip_lookback_drops_last_week():
    px = pd.Series([1.0, 1.1, 1.21, 1.0, 2.0])
    # loc=4, L=2, skip=1 -> 1.0 / 1.1 - 1, ignores last print 2.0
    got = skip_lookback_return(px, 4, lookback=2, skip=1)
    assert abs(got - (1.0 / 1.1 - 1.0)) < 1e-12


def test_select_names_absolute_then_relative():
    xs = pd.Series({"a": 0.4, "b": -0.1, "c": 0.2, "d": 0.15})
    assert select_names(xs, n_seats=2, abs_threshold=0.0, apply_absolute=True) == ["a", "c"]
    assert select_names(xs, n_seats=2, abs_threshold=0.0, apply_absolute=False) == ["a", "c"]
    only_neg = pd.Series({"a": -0.2, "b": -0.1})
    assert select_names(only_neg, 2, 0.0, True) == []


def _synth_panel() -> pd.DataFrame:
    weeks = pd.date_range("2018-01-05", periods=160, freq="W-FRI")
    rng = np.random.default_rng(7)
    winner = 1.0 * np.exp(np.cumsum(np.full(len(weeks), 0.01)))
    loser = 1.0 * np.exp(np.cumsum(np.full(len(weeks), -0.005)))
    noise = 1.0 * np.exp(np.cumsum(rng.normal(0.0, 0.01, len(weeks))))
    # last 40 weeks: flip winner down so absolute gate should cash out
    winner[-40:] = winner[-41] * np.exp(np.cumsum(np.full(40, -0.02)))
    return pd.DataFrame({"111111": winner, "222222": loser, "333333": noise}, index=weeks)


def test_dual_mom_cashes_when_absolute_negative():
    panel = _synth_panel()
    cfg = DualMomConfig(lookback=12, skip=1, n_seats=1, apply_absolute=True, cost_side=0.0)
    res = run_dual_momentum(panel, cfg, eval_start="2019-01-04", eval_end="2021-01-29")
    assert res.cash_week_pct > 0.15
    # last stretch should be mostly cash
    tail = res.holdings.tail(20)
    assert (tail["n"] == 0).mean() > 0.7


def test_xs_only_stays_invested():
    panel = _synth_panel()
    cfg = DualMomConfig(lookback=12, skip=1, n_seats=1, apply_absolute=False, cost_side=0.0)
    res = run_dual_momentum(panel, cfg, eval_start="2019-01-04", eval_end="2021-01-29")
    assert res.cash_week_pct < 0.02
    assert res.avg_gross > 0.98


def test_cost_reduces_nav():
    panel = _synth_panel()
    cheap = DualMomConfig(lookback=12, skip=1, n_seats=1, apply_absolute=True, cost_side=0.0)
    dear = DualMomConfig(lookback=12, skip=1, n_seats=1, apply_absolute=True, cost_side=0.01)
    a = run_dual_momentum(panel, cheap, eval_start="2019-01-04", eval_end="2020-12-25")
    b = run_dual_momentum(panel, dear, eval_start="2019-01-04", eval_end="2020-12-25")
    assert b.nav.iloc[-1] < a.nav.iloc[-1]


def test_no_live_ops_imports():
    import ast
    from pathlib import Path

    root = Path(__file__).resolve().parents[1]
    banned = {"strategy_exec", "live_ops", "LIVE_OPS"}
    scanned = [root / "dual_momentum", root / "scripts"]
    for folder in scanned:
        for fp in folder.rglob("*.py"):
            tree = ast.parse(fp.read_text(encoding="utf-8"), filename=str(fp))
            for node in ast.walk(tree):
                if isinstance(node, ast.Import):
                    names = {a.name.split(".")[0] for a in node.names}
                elif isinstance(node, ast.ImportFrom) and node.module:
                    names = {node.module.split(".")[0]}
                else:
                    continue
                leaked = names & banned
                assert not leaked, f"{leaked} imported in {fp}"
