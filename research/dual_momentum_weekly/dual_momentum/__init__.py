"""Weekly dual-momentum research engine. No LIVE / no strategy_exec."""

from .config import DualMomConfig
from .engine import run_dual_momentum, skip_lookback_return
from .metrics import book_stats, segment_stats, yearly_stats

__all__ = [
    "DualMomConfig",
    "run_dual_momentum",
    "skip_lookback_return",
    "book_stats",
    "segment_stats",
    "yearly_stats",
]
