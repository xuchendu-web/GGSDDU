from __future__ import annotations

from typing import Any, Mapping

from etf_fundamental_score.factors.base import BaseFactor, FactorResult, linear_map


class DividendYieldFactor(BaseFactor):
    """Higher trailing dividend yield → higher score (income sleeve preference stub)."""

    name = "dividend_yield"

    def compute(self, row: Mapping[str, Any], ctx: Mapping[str, Any]) -> FactorResult:
        key = "dividend_yield"
        if row.get(key) is None or row[key] == "":
            return self._missing(key)
        dy = float(row[key])
        if dy < 0:
            return FactorResult(self.name, None, dy, detail="negative_yield")

        best = float(self.params.get("best_yield", 0.045))
        worst = float(self.params.get("worst_yield", 0.0))
        score = linear_map(dy, best=best, worst=worst, higher_is_better=True)
        return FactorResult(self.name, score, dy, detail="dividend_yield")
