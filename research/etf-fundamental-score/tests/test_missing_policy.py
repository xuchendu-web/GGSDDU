from pathlib import Path

import yaml

from etf_fundamental_score.score import ScoreEngine


ROOT = Path(__file__).resolve().parent.parent


def _base_cfg():
    return yaml.safe_load((ROOT / "config.yaml").read_text(encoding="utf-8"))


def test_neutral_missing_policy():
    cfg = _base_cfg()
    cfg["normalization"]["missing_factor_policy"] = "neutral"
    engine = ScoreEngine(cfg)
    row = {
        "symbol": "X",
        "category": "test",
        "expense_ratio": 0.001,
        "aum_usd": 1e9,
        "tracking_error_bps": 30,
        "top10_holdings_weight": 0.4,
        "holdings_median_pe": 15,
        "net_flow_30d_usd": 0,
        "premium_bps": 10,
        "avg_daily_volume_usd": 5e7,
        "dividend_yield": 0.02,
    }
    row_miss = dict(row)
    row_miss["tracking_error_bps"] = None
    c_full, _, _, f_full = engine.score_row(row, {})
    c_miss, _, _, f_miss = engine.score_row(row_miss, {})
    assert "reweighted_missing" not in f_full
    assert "missing_factor:tracking_error" in f_miss
    assert c_miss < c_full


def test_min_factor_coverage():
    cfg = _base_cfg()
    cfg["normalization"]["missing_factor_policy"] = "reweight"
    cfg["normalization"]["min_factor_coverage"] = 0.95
    engine = ScoreEngine(cfg)
    row = {"symbol": "SYN.MISS", "category": "test_stub", "expense_ratio": 0.004, "aum_usd": 5e8}
    composite, _, _, flags = engine.score_row(row, {})
    assert composite == 0.0
    assert "insufficient_factor_coverage" in flags


def test_research_pool_only_guard():
    cfg = _base_cfg()
    cfg["research_pool_only"] = False
    from etf_fundamental_score.score import load_config
    import tempfile

    with tempfile.NamedTemporaryFile("w", suffix=".yaml", delete=False) as f:
        yaml.dump(cfg, f)
        path = f.name
    try:
        import pytest

        with pytest.raises(ValueError, match="research_pool_only"):
            load_config(path)
    finally:
        Path(path).unlink(missing_ok=True)
