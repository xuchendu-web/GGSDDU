from etf_fundamental_score.factors.liquidity import LiquidityFactor


def test_liquidity_adv_ratio():
    f = LiquidityFactor()
    high = f.compute({"avg_daily_volume_usd": 8e9, "aum_usd": 1e10}, {})
    low = f.compute({"avg_daily_volume_usd": 2e7, "aum_usd": 1e10}, {})
    assert high.score is not None and low.score is not None
    assert high.score > low.score
