from __future__ import annotations

from typing import Any, Mapping

from etf_fundamental_score.factors.base import BaseFactor, FactorResult, linear_map


class ConcentrationFactor(BaseFactor):
    """
    Holdings concentration stub: top-10 weight in portfolio.
    Lower concentration → higher diversification score.
    """

    name = "concentration"

    def compute(self, row: Mapping[str, Any], ctx: Mapping[str, Any]) -> FactorResult:
        key = "top10_holdings_weight"
        if row.get(key) is None or row[key] == "":
            # Fallback: herfindahl if provided
            hhi = row.get("holdings_hhi")
            if hhi is None or hhi == "":
                return self._missing(key)
            # Map HHI ~0.02 ( diversified ) to ~0.25 (concentrated) into top10-like band
            top10_proxy = min(0.95, max(0.1, float(hhi) * 4.0))
            raw = top10_proxy
            detail = "hhi_proxy"
        else:
            raw = float(row[key])
            detail = "top10_weight"

        if raw < 0 or raw > 1:
            return FactorResult(self.name, None, raw, detail="out_of_range")

        best = float(self.params.get("best_top10", 0.25))
        worst = float(self.params.get("worst_top10", 0.85))
        score = linear_map(raw, best=best, worst=worst, higher_is_better=False)
        return FactorResult(self.name, score, raw, detail=detail)
