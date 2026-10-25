from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Mapping, Sequence

import pandas as pd
import yaml

from etf_fundamental_score.adapters.base import UniverseRow
from etf_fundamental_score.factors import FACTOR_REGISTRY
from etf_fundamental_score.factors.base import FactorResult


def load_config(path: str | Path) -> dict[str, Any]:
    with open(path, encoding="utf-8") as f:
        cfg = yaml.safe_load(f)
    weights = cfg.get("weights", {})
    total = sum(float(v) for v in weights.values())
    if abs(total - 1.0) > 1e-6:
        raise ValueError(f"weights must sum to 1.0, got {total}")
    return cfg


def _aum_percentiles(rows: Sequence[UniverseRow]) -> dict[str, float]:
    symbols: list[tuple[str, float]] = []
    for r in rows:
        aum = r.fields.get("aum_usd")
        if aum is not None and float(aum) > 0:
            symbols.append((r.symbol, float(aum)))
    if len(symbols) < 2:
        return {}
    symbols.sort(key=lambda x: x[1])
    n = len(symbols)
    return {sym: i / (n - 1) for i, (sym, _) in enumerate(symbols)}


@dataclass
class ScoredETF:
    symbol: str
    name: str
    composite_score: float
    factor_scores: dict[str, float | None] = field(default_factory=dict)
    factor_raw: dict[str, float | None] = field(default_factory=dict)
    factor_detail: dict[str, str] = field(default_factory=dict)
    weight_used: dict[str, float] = field(default_factory=dict)
    flags: list[str] = field(default_factory=list)


class ScoreEngine:
    """Weighted multi-factor composite for research screening."""

    def __init__(self, config: Mapping[str, Any]) -> None:
        self.config = dict(config)
        self.weights: dict[str, float] = {
            k: float(v) for k, v in self.config["weights"].items()
        }
        fp = self.config.get("factor_params", {})
        self.factors = {
            name: cls(fp.get(name, {}))
            for name, cls in FACTOR_REGISTRY.items()
            if name in self.weights
        }
        self.missing_policy = (
            self.config.get("normalization", {}).get("missing_factor_policy", "reweight")
        )

    def build_context(self, rows: Sequence[UniverseRow]) -> dict[str, Any]:
        return {"aum_percentile": _aum_percentiles(rows)}

    def score_row(
        self, row: Mapping[str, Any], ctx: Mapping[str, Any]
    ) -> tuple[float, dict[str, FactorResult], dict[str, float], list[str]]:
        results: dict[str, FactorResult] = {}
        for name, factor in self.factors.items():
            results[name] = factor.compute(row, ctx)

        flags: list[str] = []
        effective_weights: dict[str, float] = {}
        weighted_sum = 0.0
        weight_total = 0.0

        for name, w in self.weights.items():
            fr = results.get(name)
            if fr is None or fr.score is None:
                flags.append(f"missing_factor:{name}")
                if self.missing_policy == "zero":
                    effective_weights[name] = w
                    weighted_sum += 0.0
                    weight_total += w
                continue
            effective_weights[name] = w
            weighted_sum += w * fr.score
            weight_total += w

        if weight_total <= 0:
            flags.append("no_scorable_factors")
            return 0.0, results, effective_weights, flags

        if self.missing_policy == "reweight" and weight_total < 1.0 - 1e-9:
            flags.append("reweighted_missing")
            composite = weighted_sum / weight_total
        else:
            composite = weighted_sum

        return composite, results, effective_weights, flags

    def score_universe(self, rows: Sequence[UniverseRow]) -> list[ScoredETF]:
        ctx = self.build_context(rows)
        scored: list[ScoredETF] = []
        for ur in rows:
            mapping = ur.as_mapping()
            composite, results, eff_w, flags = self.score_row(mapping, ctx)
            scored.append(
                ScoredETF(
                    symbol=ur.symbol,
                    name=ur.name,
                    composite_score=round(composite, 4),
                    factor_scores={n: r.score for n, r in results.items()},
                    factor_raw={n: r.raw for n, r in results.items()},
                    factor_detail={n: r.detail for n, r in results.items()},
                    weight_used=eff_w,
                    flags=flags,
                )
            )
        scored.sort(key=lambda x: x.composite_score, reverse=True)
        return scored

    def to_dataframe(self, scored: Sequence[ScoredETF]) -> pd.DataFrame:
        out_cfg = self.config.get("output", {})
        include_scores = out_cfg.get("include_factor_columns", True)
        include_raw = out_cfg.get("include_raw_columns", True)

        records: list[dict[str, Any]] = []
        for s in scored:
            rec: dict[str, Any] = {
                "symbol": s.symbol,
                "name": s.name,
                "composite_score": s.composite_score,
                "rank": None,
                "flags": "|".join(s.flags) if s.flags else "",
            }
            if include_scores:
                for k, v in s.factor_scores.items():
                    rec[f"score_{k}"] = v
            if include_raw:
                for k, v in s.factor_raw.items():
                    rec[f"raw_{k}"] = v
            records.append(rec)

        df = pd.DataFrame(records)
        if not df.empty:
            df["rank"] = df["composite_score"].rank(ascending=False, method="min").astype(int)
            cols = ["rank", "symbol", "name", "composite_score"] + [
                c for c in df.columns if c not in ("rank", "symbol", "name", "composite_score", "flags")
            ] + ["flags"]
            df = df[cols]
        return df
