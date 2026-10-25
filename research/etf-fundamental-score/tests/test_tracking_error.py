from etf_fundamental_score.factors.tracking_error import TrackingErrorFactor


def test_te_direct():
    f = TrackingErrorFactor({"best_te_bps": 10, "worst_te_bps": 110})
    assert f.compute({"symbol": "S", "tracking_error_bps": 10}, {}).score == 100.0
    assert f.compute({"symbol": "S", "tracking_error_bps": 110}, {}).score == 0.0


def test_te_derived_ctx():
    f = TrackingErrorFactor({"best_te_bps": 0, "worst_te_bps": 100})
    ctx = {"derived_te_bps": {"S": 25}}
    r = f.compute({"symbol": "S"}, ctx)
    assert r.score == 75.0
    assert r.detail == "derived_from_returns"
