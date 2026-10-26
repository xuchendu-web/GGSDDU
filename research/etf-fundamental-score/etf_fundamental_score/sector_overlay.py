from __future__ import annotations

from typing import Any, Mapping


def _category(row: Mapping[str, Any], category_field: str) -> str | None:
    raw = row.get(category_field)
    if raw is None or raw == "":
        return None
    return str(raw).strip()


def resolve_weights(
    base_weights: Mapping[str, float],
    category: str | None,
    overlays: Mapping[str, Any] | None,
) -> dict[str, float]:
    if not overlays or not overlays.get("enabled"):
        return dict(base_weights)

    by_cat = overlays.get("by_category") or {}
    if not category or category not in by_cat:
        return dict(base_weights)

    spec = by_cat[category]
    mults = spec.get("weight_multipliers") or {}
    if not mults:
        return dict(base_weights)

    adjusted = {k: float(v) * float(mults.get(k, 1.0)) for k, v in base_weights.items()}
    total = sum(adjusted.values())
    if total <= 0:
        return dict(base_weights)
    return {k: v / total for k, v in adjusted.items()}


def resolve_factor_params(
    base_params: Mapping[str, Mapping[str, Any]],
    category: str | None,
    overlays: Mapping[str, Any] | None,
) -> dict[str, dict[str, Any]]:
    merged = {k: dict(v) for k, v in base_params.items()}
    if not overlays or not overlays.get("enabled") or not category:
        return merged

    by_cat = overlays.get("by_category") or {}
    spec = by_cat.get(category) or {}
    overrides = spec.get("factor_params") or {}
    for factor_name, patch in overrides.items():
        if factor_name not in merged:
            merged[factor_name] = {}
        merged[factor_name].update(dict(patch))
    return merged
