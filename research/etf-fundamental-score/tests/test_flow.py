import pytest

from etf_fundamental_score.factors.flow import FlowFactor


def test_flow_ratio_from_fields():
    f = FlowFactor({"best_flow_ratio": 0.1, "worst_flow_ratio": -0.1})
    row = {"net_flow_30d_usd": 50_000_000, "aum_usd": 1_000_000_000}
    r = f.compute(row, {})
    assert r.raw == 0.05
    assert r.score == pytest.approx(75.0)


def test_flow_precalc():
    f = FlowFactor({"best_flow_ratio": 1.0, "worst_flow_ratio": 0.0})
    r = f.compute({"flow_to_aum_30d": 0.5}, {})
    assert r.score == 50.0
