from etf_fundamental_score.factors.valuation import ValuationFactor


def test_valuation_cheaper_better():
    f = ValuationFactor({"best_pe": 10, "worst_pe": 30})
    assert f.compute({"holdings_median_pe": 10}, {}).score == 100.0
    assert f.compute({"holdings_median_pe": 30}, {}).score == 0.0


def test_valuation_non_positive():
    f = ValuationFactor()
    r = f.compute({"holdings_median_pe": 0}, {})
    assert r.score is None
