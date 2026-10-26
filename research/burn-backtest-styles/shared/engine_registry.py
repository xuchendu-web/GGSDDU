"""Registry of ranking engine styles (import runners lazily)."""

from __future__ import annotations

from typing import Callable

import pandas as pd
from pathlib import Path

EngineFn = Callable[[Path], pd.DataFrame]

_REGISTRY: dict[str, tuple[str, str]] = {
    "vector": ("A", "scripts.style_a_vector"),
    "event": ("B", "scripts.style_b_event"),
    "pandas_resample": ("C", "scripts.style_c_pandas"),
    "weekly_bar": ("D", "scripts.style_d_weekly_bar"),
    "daily_resample": ("E", "scripts.style_e_daily_resample"),
    "numba_loop": ("F", "scripts.style_f_numba_loop"),
    "pandas_rolling": ("G", "scripts.style_g_pandas_rolling"),
    "polars": ("H", "scripts.style_h_polars"),
    "numexpr": ("I", "scripts.style_i_numexpr"),
}


def engine_ids() -> list[str]:
    return list(_REGISTRY.keys())


def engine_labels() -> dict[str, str]:
    return {k: v[0] for k, v in _REGISTRY.items()}


def load_runner(engine_id: str) -> EngineFn:
    if engine_id not in _REGISTRY:
        raise KeyError(f"Unknown engine: {engine_id}")
    module_name = _REGISTRY[engine_id][1]
    import importlib

    mod = importlib.import_module(module_name)
    return mod.run_ranking


