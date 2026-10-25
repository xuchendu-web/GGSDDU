from etf_fundamental_score.factors.concentration import ConcentrationFactor


def test_concentration_top10():
    f = ConcentrationFactor({"best_top10": 0.2, "worst_top10": 0.8})
    assert f.compute({"top10_holdings_weight": 0.2}, {}).score == 100.0
    assert f.compute({"top10_holdings_weight": 0.8}, {}).score == 0.0


def test_concentration_hhi_fallback():
    f = ConcentrationFactor({"best_top10": 0.2, "worst_top10": 0.8})
    r = f.compute({"holdings_hhi": 0.1}, {})
    assert r.detail == "hhi_proxy"
    assert r.score is not None
