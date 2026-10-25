from __future__ import annotations

from typing import Any, Mapping

from etf_fundamental_score.factors.base import BaseFactor, FactorResult, linear_map


class FlowFactor(BaseFactor):
    """
    Flow stub: net_flow_30d / aum_usd (creation/redemption pressure proxy).
    """

    name = "flow"

    def compute(self, row: Mapping[str, Any], ctx: Mapping[str, Any]) -> FactorResult:
        flow_key = "net_flow_30d_usd"
        aum_key = "aum_usd"
        if row.get(flow_key) is None or row.get(aum_key) in (None, ""):
            ratio_key = "flow_to_aum_30d"
            if row.get(ratio_key) is None or row[ratio_key] == "":
                return self._missing(flow_key)
            ratio = float(row[ratio_key])
            detail = "precalc_ratio"
        else:
            aum = float(row[aum_key])
            if aum <= 0:
                return FactorResult(self.name, None, None, detail="bad_aum")
            ratio = float(row[flow_key]) / aum
            detail = "flow_over_aum"

        best = float(self.params.get("best_flow_ratio", 0.05))
        worst = float(self.params.get("worst_flow_ratio", -0.08))
        score = linear_map(ratio, best=best, worst=worst, higher_is_better=True)
        return FactorResult(self.name, score, ratio, detail=detail)
