from __future__ import annotations

from typing import Any, Mapping

from etf_fundamental_score.factors.base import BaseFactor, FactorResult, linear_map


class FeeFactor(BaseFactor):
    """Lower expense ratio → higher score (total annual fee drag)."""

    name = "fee"

    def compute(self, row: Mapping[str, Any], ctx: Mapping[str, Any]) -> FactorResult:
        key = "expense_ratio"
        if row.get(key) is None or row[key] == "":
            return self._missing(key)
        er = float(row[key])
        if er < 0:
            return FactorResult(self.name, None, er, detail="negative_er")

        best = float(self.params.get("best_er", 0.0003))
        worst = float(self.params.get("worst_er", 0.015))
        score = linear_map(er, best=best, worst=worst, higher_is_better=False)
        return FactorResult(self.name, score, er, detail="expense_ratio")
