from __future__ import annotations

import math
from typing import Any, Mapping

from etf_fundamental_score.factors.base import BaseFactor, FactorResult, clamp_score


class AumFactor(BaseFactor):
    """
    Scale / liquidity proxy: larger AUM → higher score within configured log band,
    then blended with cross-sectional percentile when universe context is present.
    """

    name = "aum"

    def compute(self, row: Mapping[str, Any], ctx: Mapping[str, Any]) -> FactorResult:
        key = "aum_usd"
        if row.get(key) is None or row[key] == "":
            return self._missing(key)
        aum = float(row[key])
        if aum <= 0:
            return FactorResult(self.name, 0.0, aum, detail="non_positive_aum")

        min_log = float(self.params.get("min_log_aum", 6.0))
        max_log = float(self.params.get("max_log_aum", 11.5))
        log_aum = math.log10(max(aum, 1.0))
        band_score = clamp_score(100.0 * (log_aum - min_log) / (max_log - min_log))

        percentiles: Mapping[str, float] | None = ctx.get("aum_percentile")
        if percentiles and row.get("symbol") in percentiles:
            pct = float(percentiles[row["symbol"]])
            blended = 0.5 * band_score + 0.5 * clamp_score(100.0 * pct)
            return FactorResult(self.name, blended, aum, detail="band+percentile")

        return FactorResult(self.name, band_score, aum, detail="band_only")
