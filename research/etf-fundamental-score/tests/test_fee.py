from etf_fundamental_score.factors.fee import FeeFactor


def test_fee_best_worst():
    f = FeeFactor({"best_er": 0.001, "worst_er": 0.01})
    assert f.compute({"expense_ratio": 0.001}, {}).score == 100.0
    assert f.compute({"expense_ratio": 0.01}, {}).score == 0.0


def test_fee_mid():
    f = FeeFactor({"best_er": 0.0, "worst_er": 0.01})
    r = f.compute({"expense_ratio": 0.005}, {})
    assert r.score == 50.0
