"""Research-grade ETF fundamental composite scoring (screening only, not live alpha)."""

from etf_fundamental_score.score import ScoreEngine, load_config

__all__ = ["ScoreEngine", "load_config"]
__version__ = "0.1.0"
