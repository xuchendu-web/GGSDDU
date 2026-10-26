from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Mapping, Sequence

import pandas as pd
import yaml

from etf_fundamental_score.adapters.base import UniverseRow
from etf_fundamental_score.factors import FACTOR_REGISTRY
from etf_fundamental_score.factors.base import BaseFactor, FactorResult
from etf_fundamental_score.sector_overlay import resolve_factor_params, resolve_weights


def load_config(path: str | Path) -> dict[str, Any]:
    with open(path, encoding="utf-8") as f:
        cfg = yaml.safe_load(f)
    weights = cfg.get("weights", {})
    total = sum(float(v) for v in weights.values())
    if abs(total - 1.0) > 1e-6:
        raise ValueError(f"weights must sum to 1.0, got {total}")
    if cfg.get("research_pool_only") is False:
        raise ValueError(
            "research_pool_only must remain true in this package (no LIVE升格 / production trading mode)"
        )
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
    category: str | None = None
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
        self.base_factor_params: dict[str, dict[str, Any]] = dict(
            self.config.get("factor_params", {})
        )
        self.overlays = self.config.get("sector_overlays") or {}
        self.category_field = str(
            self.overlays.get("category_field", "category")
        )
        norm = self.config.get("normalization", {})
        self.missing_policy = norm.get("missing_factor_policy", "reweight")
        self.min_factor_coverage = float(norm.get("min_factor_coverage", 0.0))
        self.required_factors: list[str] = list(norm.get("required_factors") or [])
        self.neutral_score = float(norm.get("neutral_missing_score", 50.0))
        self._factor_cache: dict[tuple[str, str | None], BaseFactor] = {}

    def _factor_instance(self, name: str, category: str | None) -> BaseFactor:
        key = (name, category)
        if key in self._factor_cache:
            return self._factor_cache[key]
        params_map = resolve_factor_params(
            self.base_factor_params, category, self.overlays
        )
        cls = FACTOR_REGISTRY[name]
        inst = cls(params_map.get(name, {}))
        self._factor_cache[key] = inst
        return inst

    def build_context(self, rows: Sequence[UniverseRow]) -> dict[str, Any]:
        return {"aum_percentile": _aum_percentiles(rows)}

    def _apply_missing(
        self,
        name: str,
        w: float,
        fr: FactorResult | None,
        flags: list[str],
    ) -> tuple[float, float, bool]:
        """Return (weighted contribution, weight counted toward coverage, included in sum)."""
        if fr is not None and fr.score is not None:
            return w * fr.score, w, True

        flags.append(f"missing_factor:{name}")
        if self.missing_policy == "zero":
            return 0.0, w, True
        if self.missing_policy == "neutral":
            return w * self.neutral_score, w, True
        # reweight: omit weight from denominator
        return 0.0, 0.0, False

    def score_row(
        self, row: Mapping[str, Any], ctx: Mapping[str, Any]
    ) -> tuple[float, dict[str, FactorResult], dict[str, float], list[str]]:
        category = row.get(self.category_field)
        cat_key = str(category).strip() if category not in (None, "") else None
        row_weights = resolve_weights(self.weights, cat_key, self.overlays)

        results: dict[str, FactorResult] = {}
        for name in row_weights:
            factor = self._factor_instance(name, cat_key)
            results[name] = factor.compute(row, ctx)

        flags: list[str] = []
        for req in self.required_factors:
            fr = results.get(req)
            if fr is None or fr.score is None:
                flags.append(f"required_missing:{req}")

        effective_weights: dict[str, float] = {}
        weighted_sum = 0.0
        weight_total = 0.0
        present_weight = 0.0

        for name, w in row_weights.items():
            fr = results.get(name)
            if fr is not None and fr.score is not None:
                present_weight += w
            contrib, _, in_sum = self._apply_missing(name, w, fr, flags)
            if in_sum:
                effective_weights[name] = w
                weighted_sum += contrib
                weight_total += w

        if self.required_factors and any(f.startswith("required_missing:") for f in flags):
            flags.append("failed_required_factors")
            return 0.0, results, effective_weights, flags

        if present_weight < self.min_factor_coverage - 1e-9:
            flags.append("insufficient_factor_coverage")
            return 0.0, results, effective_weights, flags

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
            cat = mapping.get(self.category_field)
            scored.append(
                ScoredETF(
                    symbol=ur.symbol,
                    name=ur.name,
                    category=str(cat) if cat not in (None, "") else None,
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
        ranking = self.config.get("ranking", {})
        within_category = bool(ranking.get("within_category", False))

        records: list[dict[str, Any]] = []
        for s in scored:
            rec: dict[str, Any] = {
                "symbol": s.symbol,
                "name": s.name,
                "category": s.category or "",
                "composite_score": s.composite_score,
                "rank": None,
                "rank_within_category": None,
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
        if df.empty:
            return df

        df["rank"] = df["composite_score"].rank(ascending=False, method="min").astype(int)
        if within_category and "category" in df.columns:
            df["rank_within_category"] = (
                df.groupby("category", dropna=False)["composite_score"]
                .rank(ascending=False, method="min")
                .astype("Int64")
            )

        lead = ["rank", "rank_within_category", "symbol", "name", "category", "composite_score"]
        lead = [c for c in lead if c in df.columns]
        rest = [c for c in df.columns if c not in lead and c != "flags"]
        df = df[lead + rest + ["flags"]]
        return df
