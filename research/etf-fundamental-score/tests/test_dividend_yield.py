from etf_fundamental_score.factors.dividend_yield import DividendYieldFactor


def test_dividend_yield_higher_is_better():
    f = DividendYieldFactor()
    hi = f.compute({"dividend_yield": 0.04}, {})
    lo = f.compute({"dividend_yield": 0.005}, {})
    assert hi.score is not None and lo.score is not None
    assert hi.score > lo.score
