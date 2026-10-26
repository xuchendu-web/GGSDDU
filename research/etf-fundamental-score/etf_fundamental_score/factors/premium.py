from __future__ import annotations

from typing import Any, Mapping

from etf_fundamental_score.factors.base import BaseFactor, FactorResult, linear_map


class PremiumFactor(BaseFactor):
    """Lower premium vs IOPV / fair value → higher score (execution cost proxy)."""

    name = "premium"

    def compute(self, row: Mapping[str, Any], ctx: Mapping[str, Any]) -> FactorResult:
        key = "premium_bps"
        if row.get(key) is None or row[key] == "":
            return self._missing(key)
        bps = float(row[key])
        best = float(self.params.get("best_premium_bps", -30))
        worst = float(self.params.get("worst_premium_bps", 80))
        score = linear_map(bps, best=best, worst=worst, higher_is_better=False)
        return FactorResult(self.name, score, bps, detail="premium_bps")
