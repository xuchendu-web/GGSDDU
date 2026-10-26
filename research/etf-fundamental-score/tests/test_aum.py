import math

from etf_fundamental_score.factors.aum import AumFactor


def test_aum_band_midpoint():
    f = AumFactor({"min_log_aum": 6.0, "max_log_aum": 11.0})
    aum = 10 ** 8.5
    r = f.compute({"symbol": "X", "aum_usd": aum}, {})
    assert r.score is not None
    assert 45 <= r.score <= 55


def test_aum_missing():
    f = AumFactor()
    r = f.compute({"symbol": "X"}, {})
    assert r.score is None
    assert "missing" in r.detail


def test_aum_percentile_blend():
    f = AumFactor({"min_log_aum": 6.0, "max_log_aum": 11.0})
    ctx = {"aum_percentile": {"A": 1.0, "B": 0.0}}
    r = f.compute({"symbol": "A", "aum_usd": 1e10}, ctx)
    assert r.score is not None
    assert r.score >= 70
