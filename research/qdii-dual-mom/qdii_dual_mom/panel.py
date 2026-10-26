"""Weekly close panel for overseas-equity (QDII) research sleeve only."""

from __future__ import annotations

import sys
from pathlib import Path

import pandas as pd

from .config import AUM_MIN_YI, DATA, EVAL_END, MIN_UNIV

_REPO = Path(__file__).resolve().parents[3]
if str(_REPO) not in sys.path:
    sys.path.insert(0, str(_REPO / "research" / "overseas-volscaled-tsmom"))

from vs_tsmom_lib import (  # noqa: E402
    OX,
    daily_to_weekly_close,
    load_daily_close,
    load_rebalance_fridays,
    resolve_pool_path,
)


def load_universe_from_pool(aum_min: float = AUM_MIN_YI) -> pd.DataFrame:
    pool = pd.read_csv(resolve_pool_path())
    pool["code"] = pool["code"].astype(str).str.zfill(6)
    ox = pool.loc[(pool["l0"] == "海外权益") & (pool["aum"] >= aum_min)].copy()
    ox = ox.sort_values("code")
    # Align with frozen OX kit set when present
    ox_codes = set(ox["code"]) & OX
    if len(ox_codes) >= MIN_UNIV:
        ox = ox[ox["code"].isin(ox_codes)]
    return ox.reset_index(drop=True)


def build_weekly_panel(codes: list[str], weeks: pd.DatetimeIndex | None = None) -> pd.DataFrame:
    if weeks is None:
        weeks = load_rebalance_fridays()
    cols: dict[str, pd.Series] = {}
    for code in codes:
        daily, _, _ = load_daily_close(code)
        if daily.empty:
            continue
        w = daily_to_weekly_close(daily)
        if w.empty:
            continue
        aligned = w.reindex(weeks, method="ffill")
        cols[code] = aligned
    if not cols:
        raise FileNotFoundError("no QDII weekly series loaded")
    panel = pd.DataFrame(cols).sort_index()
    panel = panel.loc[: pd.Timestamp(EVAL_END)]
    return panel


def load_weekly_panel(path: Path | None = None) -> pd.DataFrame:
    fp = Path(path) if path else DATA / "weekly_panel.parquet"
    panel = pd.read_parquet(fp)
    panel.index = pd.to_datetime(panel.index)
    panel.columns = [str(c).zfill(6) for c in panel.columns]
    return panel.sort_index()


def inventory_note() -> dict:
    uni = load_universe_from_pool()
    n = len(uni)
    ok = n >= MIN_UNIV
    return {
        "n_universe": n,
        "min_required": MIN_UNIV,
        "ok": ok,
        "codes": uni["code"].tolist(),
        "pool": str(resolve_pool_path().relative_to(_REPO)),
    }
