from etf_fundamental_score.factors.premium import PremiumFactor


def test_premium_lower_is_better():
    f = PremiumFactor({"best_premium_bps": -20, "worst_premium_bps": 100})
    good = f.compute({"premium_bps": -10}, {})
    bad = f.compute({"premium_bps": 90}, {})
    assert good.score is not None and bad.score is not None
    assert good.score > bad.score
