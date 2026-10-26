from __future__ import annotations

from typing import Any, Mapping

from etf_fundamental_score.factors.base import BaseFactor, FactorResult, linear_map


class LiquidityFactor(BaseFactor):
    """
    ADV / AUM turnover proxy: higher average daily dollar volume relative to AUM
    → better on-screen liquidity (research stub).
    """

    name = "liquidity"

    def compute(self, row: Mapping[str, Any], ctx: Mapping[str, Any]) -> FactorResult:
        adv = row.get("avg_daily_volume_usd")
        aum = row.get("aum_usd")
        if adv is not None and adv != "" and aum is not None and aum != "":
            aum_f = float(aum)
            if aum_f <= 0:
                return FactorResult(self.name, None, None, detail="non_positive_aum")
            ratio = float(adv) / aum_f
        elif row.get("adv_to_aum") is not None and row.get("adv_to_aum") != "":
            ratio = float(row["adv_to_aum"])
        else:
            return self._missing("avg_daily_volume_usd|adv_to_aum")

        best = float(self.params.get("best_adv_ratio", 0.08))
        worst = float(self.params.get("worst_adv_ratio", 0.002))
        score = linear_map(ratio, best=best, worst=worst, higher_is_better=True)
        return FactorResult(self.name, score, ratio, detail="adv_to_aum")
