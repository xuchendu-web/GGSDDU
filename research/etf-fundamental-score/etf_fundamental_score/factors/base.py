from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Any, Mapping, Optional


@dataclass(frozen=True)
class FactorResult:
    """Single-factor output for one ETF row."""

    name: str
    score: Optional[float]  # 0–100, None if not computable
    raw: Optional[float]
    detail: str = ""


def clamp_score(value: float) -> float:
    return max(0.0, min(100.0, float(value)))


def linear_map(
    x: float,
    *,
    best: float,
    worst: float,
    higher_is_better: bool,
) -> float:
    """
    Map x from [worst, best] (or reversed) to score 0–100.
    Values outside the band are clamped to 0 or 100.
    """
    if best == worst:
        return 50.0
    if higher_is_better:
        lo, hi = worst, best
        if x <= lo:
            return 0.0
        if x >= hi:
            return 100.0
        t = (x - lo) / (hi - lo)
        return clamp_score(100.0 * t)
    # Lower raw value is better (fee, TE, concentration, valuation).
    lo, hi = best, worst
    if x <= lo:
        return 100.0
    if x >= hi:
        return 0.0
    t = (x - lo) / (hi - lo)
    return clamp_score(100.0 * (1.0 - t))


class BaseFactor(ABC):
    name: str

    def __init__(self, params: Mapping[str, Any] | None = None) -> None:
        self.params = dict(params or {})

    @abstractmethod
    def compute(self, row: Mapping[str, Any], ctx: Mapping[str, Any]) -> FactorResult:
        """Compute factor score for one universe row."""

    def _missing(self, raw_key: str) -> FactorResult:
        return FactorResult(
            name=self.name,
            score=None,
            raw=None,
            detail=f"missing:{raw_key}",
        )
