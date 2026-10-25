from __future__ import annotations

from typing import Any, Mapping

from etf_fundamental_score.factors.base import BaseFactor, FactorResult, linear_map


class ValuationFactor(BaseFactor):
    """
    Valuation stub: median P/E proxy at ETF level (holdings_median_pe).
    Cheaper → higher score. Not a live fundamental model.
    """

    name = "valuation"

    def compute(self, row: Mapping[str, Any], ctx: Mapping[str, Any]) -> FactorResult:
        key = "holdings_median_pe"
        if row.get(key) is None or row[key] == "":
            return self._missing(key)
        pe = float(row[key])
        if pe <= 0:
            return FactorResult(self.name, None, pe, detail="non_positive_pe")

        best = float(self.params.get("best_pe", 12.0))
        worst = float(self.params.get("worst_pe", 35.0))
        score = linear_map(pe, best=best, worst=worst, higher_is_better=False)
        return FactorResult(self.name, score, pe, detail="median_pe_stub")
