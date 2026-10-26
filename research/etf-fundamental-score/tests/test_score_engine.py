from pathlib import Path

import pytest

from etf_fundamental_score.adapters.fixture_csv import FixtureCsvAdapter
from etf_fundamental_score.score import ScoreEngine, load_config


ROOT = Path(__file__).resolve().parent.parent


def test_load_config_weights_sum():
    cfg = load_config(ROOT / "config.yaml")
    assert abs(sum(cfg["weights"].values()) - 1.0) < 1e-6


def test_score_universe_sample():
    cfg = load_config(ROOT / "config.yaml")
    rows = FixtureCsvAdapter(ROOT / "fixtures" / "universe_sample.csv").load_universe()
    engine = ScoreEngine(cfg)
    scored = engine.score_universe(rows)
    assert len(scored) == len(rows)
    assert scored[0].composite_score >= scored[-1].composite_score

    missing_te = next(s for s in scored if s.symbol == "SYN.MISS")
    assert any("tracking_error" in f for f in missing_te.flags)


def test_config_bad_weights():
    with pytest.raises(ValueError):
        load_config(ROOT / "tests" / "bad_weights.yaml")
