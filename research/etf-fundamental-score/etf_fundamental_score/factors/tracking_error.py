from __future__ import annotations

from typing import Any, Mapping

from etf_fundamental_score.factors.base import BaseFactor, FactorResult, linear_map


class TrackingErrorFactor(BaseFactor):
    """
    Tracking error proxy (annualized bps vs benchmark).
    Fixture field: tracking_error_bps.
    Live adapter may derive from return diffs — see adapters.
    """

    name = "tracking_error"

    def compute(self, row: Mapping[str, Any], ctx: Mapping[str, Any]) -> FactorResult:
        key = "tracking_error_bps"
        if row.get(key) is None or row[key] == "":
            # Optional derivation stub from 252-day return diff std
            derived = ctx.get("derived_te_bps", {}).get(row.get("symbol"))
            if derived is None:
                return self._missing(key)
            te = float(derived)
            detail = "derived_from_returns"
        else:
            te = float(row[key])
            detail = "direct_bps"

        if te < 0:
            return FactorResult(self.name, None, te, detail="negative_te")

        best = float(self.params.get("best_te_bps", 5))
        worst = float(self.params.get("worst_te_bps", 150))
        score = linear_map(te, best=best, worst=worst, higher_is_better=False)
        return FactorResult(self.name, score, te, detail=detail)
