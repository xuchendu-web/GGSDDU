from pathlib import Path

import yaml

from etf_fundamental_score.score import ScoreEngine, load_config
from etf_fundamental_score.sector_overlay import resolve_weights


ROOT = Path(__file__).resolve().parent.parent


def test_resolve_weights_multipliers_normalize():
    base = {"a": 0.5, "b": 0.5}
    overlays = {
        "enabled": True,
        "by_category": {"x": {"weight_multipliers": {"a": 2.0}}},
    }
    w = resolve_weights(base, "x", overlays)
    assert abs(sum(w.values()) - 1.0) < 1e-9
    assert w["a"] > w["b"]


def test_qdii_overlay_differs_from_broad():
    cfg = load_config(ROOT / "config.yaml")
    engine = ScoreEngine(cfg)
    row_qdii = {
        "symbol": "T",
        "category": "qdii_us",
        "expense_ratio": 0.006,
        "aum_usd": 3e10,
        "tracking_error_bps": 90,
        "top10_holdings_weight": 0.45,
        "holdings_median_pe": 30,
        "net_flow_30d_usd": 1e9,
        "premium_bps": 90,
        "avg_daily_volume_usd": 1e9,
        "dividend_yield": 0.01,
    }
    row_broad = dict(row_qdii)
    row_broad["category"] = "broad_equity_cn"
    row_broad["tracking_error_bps"] = 30
    row_broad["premium_bps"] = 20
    ctx = engine.build_context([])
    c_q, _, _, _ = engine.score_row(row_qdii, ctx)
    c_b, _, _, _ = engine.score_row(row_broad, ctx)
    assert c_q != c_b


def test_within_category_rank_column():
    cfg = yaml.safe_load((ROOT / "config.yaml").read_text(encoding="utf-8"))
    cfg["ranking"] = {"within_category": True}
    from etf_fundamental_score.adapters.fixture_csv import FixtureCsvAdapter

    rows = FixtureCsvAdapter(ROOT / "fixtures" / "universe_sample.csv").load_universe()
    engine = ScoreEngine(cfg)
    df = engine.to_dataframe(engine.score_universe(rows))
    assert "rank_within_category" in df.columns
    growth = df[df["category"] == "growth_cn"]
    assert growth["rank_within_category"].nunique() == len(growth)
