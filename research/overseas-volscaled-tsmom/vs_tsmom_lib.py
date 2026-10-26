"""Shared paths, price load, and VS-TSMOM mechanics (research-only)."""

from __future__ import annotations

import json
import math
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterable

import numpy as np
import pandas as pd

TASK = "VS-TSMOM-SLEEVE"
EVAL_START = "2020-01-03"
EVAL_END = "2026-10-23"
EVAL_END_TS = pd.Timestamp(EVAL_END)
PRE2019_CUTOFF = pd.Timestamp("2019-01-03")
SIGMA_STAR = 0.12
LOOKBACK_W = 52
VOL_W = 60
COST_RT = 0.002
COST_SIDE = COST_RT / 2.0
L_CAP = 1.0

OX = {
    "159941", "513500", "159509", "513400", "159687", "513880",
    "513850", "159561", "513800", "513290", "513080", "159329",
    "159529", "513730", "520870", "520580",
}
CMD = {"518880", "518600", "159980", "159985", "159981"}
RATES = {"511010", "511260"}
OXHK_EXTRA = {"159920", "510900", "513550", "520560", "159109", "513170", "520770"}

ROOT = Path(__file__).resolve().parents[2]
HERE = Path(__file__).resolve().parent
OUT_DIR = HERE / "VS-TSMOM-LIVE1430"

KIT = ROOT / "research/cloud_batch/CLOUD-BATCH-2026-10-26/data/research_cache"
PRICES_DAILY = ROOT / "research/cloud_batch/prices_daily"
WEEKLY_PANEL = ROOT / "research/dual_momentum_weekly/data/weekly_panel.parquet"

POOL_CANDIDATES = [
    ROOT / "etf-correlation/data/research_pool_v2.csv",
    ROOT / "strategy-weekly/etf_replace_only_436/universe_replace_only_436.csv",
]


def to_week_friday(ts: pd.Timestamp) -> pd.Timestamp:
    ts = pd.Timestamp(ts).normalize()
    return ts + pd.Timedelta(days=(4 - int(ts.weekday())) % 7)


def resolve_pool_path() -> Path:
    for p in POOL_CANDIDATES:
        if p.is_file():
            return p
    raise FileNotFoundError("research pool CSV not found")


def _bars_from_json(path: Path) -> list[dict[str, Any]]:
    rec = json.loads(path.read_text(encoding="utf-8"))
    text = json.dumps(rec).lower()
    if any(k in text for k in ("extend_bond", "backward", "drift")):
        return [], True
    bars = rec.get("bars") or []
    return bars, False


def _bars_from_bond_csv(path: Path) -> tuple[list[dict[str, Any]], bool]:
    if not path.is_file():
        return [], False
    head = path.read_text(encoding="utf-8", errors="ignore")[:2000].lower()
    drift = any(k in head for k in ("extend_bond", "backward", "drift"))
    df = pd.read_csv(path)
    if "close" not in df.columns:
        return [], drift
    bars = [{"date": str(r["date"]), "c": float(r["close"])} for _, r in df.iterrows()]
    return bars, drift


def load_daily_close(code: str) -> tuple[pd.Series, str, bool]:
    """Return (daily close series, source_path, drift_flag)."""
    code = str(code).zfill(6)
    drift_any = False

    day_fp = KIT / "day" / f"{code}.json"
    if day_fp.is_file():
        bars, drift = _bars_from_json(day_fp)
        drift_any = drift_any or drift
        if bars:
            idx = pd.to_datetime([b["date"] for b in bars])
            px = pd.Series([float(b.get("c", b.get("close", np.nan))) for b in bars], index=idx)
            px = px[px > 0].sort_index()
            return px, str(day_fp.relative_to(ROOT)), drift_any

    pd_fp = PRICES_DAILY / f"{code}.json"
    if pd_fp.is_file():
        bars, drift = _bars_from_json(pd_fp)
        drift_any = drift_any or drift
        if bars:
            idx = pd.to_datetime([b["date"] for b in bars])
            px = pd.Series([float(b.get("c", b.get("close", np.nan))) for b in bars], index=idx)
            px = px[px > 0].sort_index()
            return px, str(pd_fp.relative_to(ROOT)), drift_any

    if code in RATES:
        for sub in ("bond_daily", "day"):
            bond_fp = KIT / sub / f"{code}.csv"
            if bond_fp.suffix == ".json":
                bond_fp = KIT / sub / f"{code}.json"
            if bond_fp.is_file():
                if bond_fp.suffix == ".csv":
                    bars, drift = _bars_from_bond_csv(bond_fp)
                else:
                    bars, drift = _bars_from_json(bond_fp)
                drift_any = drift_any or drift
                if bars:
                    idx = pd.to_datetime([b["date"] for b in bars])
                    px = pd.Series([float(b["c"]) for b in bars], index=idx)
                    px = px[px > 0].sort_index()
                    return px, str(bond_fp.relative_to(ROOT)), drift_any

    return pd.Series(dtype=float), "", drift_any


def daily_to_weekly_close(daily: pd.Series) -> pd.Series:
    if daily.empty:
        return daily
    fri = pd.DatetimeIndex([to_week_friday(t) for t in daily.index])
    out = pd.Series(daily.to_numpy(), index=fri, dtype=float)
    return out[~out.index.duplicated(keep="last")].sort_index()


def friday_close_on_or_before(daily: pd.Series, friday: pd.Timestamp) -> float | None:
    if daily.empty:
        return None
    sub = daily[daily.index <= friday]
    if sub.empty:
        return None
    v = float(sub.iloc[-1])
    return v if v > 0 and math.isfinite(v) else None


def load_listing_date(code: str) -> pd.Timestamp | None:
    code = str(code).zfill(6)
    listing_fp = KIT / "listing.json"
    if listing_fp.is_file():
        rec = json.loads(listing_fp.read_text(encoding="utf-8"))
        if code in rec:
            for key in ("ipo_bs", "first_sina", "list_date"):
                if rec[code].get(key):
                    return pd.Timestamp(rec[code][key])
    return None


def load_rebalance_fridays() -> pd.DatetimeIndex:
    if not WEEKLY_PANEL.is_file():
        raise FileNotFoundError(f"missing weekly panel: {WEEKLY_PANEL}")
    panel = pd.read_parquet(WEEKLY_PANEL)
    panel.index = pd.to_datetime(panel.index)
    weeks = panel.index.sort_values()
    start = pd.Timestamp(EVAL_START)
    end = pd.Timestamp(EVAL_END)
    return weeks[(weeks >= start) & (weeks <= end)]


def sleeve_of(code: str, declared: set[str], ox_codes: set[str]) -> str | None:
    code = str(code).zfill(6)
    if code in ox_codes and "OX" in declared:
        return "OX"
    if code in CMD and "CMD" in declared:
        return "CMD"
    if code in RATES and "RATES" in declared:
        return "RATES"
    return None


@dataclass
class BookSpec:
    key: str
    mode: str  # VS, U, H, VS_BH, ERC, OXONLY, OXHK
    declared: frozenset[str]
    ox_codes: frozenset[str]


def weekly_simple_returns(px: pd.Series) -> pd.Series:
    return px.pct_change()


def name_eligible(
    code: str,
    week_i: int,
    weeks: pd.DatetimeIndex,
    weekly_px: pd.Series,
    listing: pd.Timestamp | None,
) -> bool:
    dt = weeks[week_i]
    if weekly_px.empty or dt not in weekly_px.index:
        # allow mapping: use last available weekly point at or before dt
        wsub = weekly_px[weekly_px.index <= dt]
        if wsub.empty:
            return False
        p_t = float(wsub.iloc[-1])
    else:
        p_t = float(weekly_px.loc[dt])
    if not math.isfinite(p_t) or p_t <= 0:
        return False
    if listing is not None and dt < listing:
        return False
    if week_i < LOOKBACK_W:
        return False
    p_lag = weekly_px.get(weeks[week_i - LOOKBACK_W], np.nan)
    if not math.isfinite(p_lag) or p_lag <= 0:
        return False
    if week_i < VOL_W:
        return False
    seg = weekly_px.loc[weeks[week_i - VOL_W] : weeks[week_i - 1]]
    if len(seg.dropna()) < VOL_W:
        return False
    return True


def sigma_i(weekly_px: pd.Series, weeks: pd.DatetimeIndex, week_i: int) -> float:
    seg = weekly_px.loc[weeks[week_i - VOL_W] : weeks[week_i - 1]].dropna()
    if len(seg) < VOL_W:
        return float("nan")
    rets = seg.pct_change().dropna()
    if len(rets) < 2:
        return float("nan")
    s = float(rets.std(ddof=1) * math.sqrt(52))
    return s if math.isfinite(s) and s > 0 else float("nan")


def r52(weekly_px: pd.Series, weeks: pd.DatetimeIndex, week_i: int) -> float:
    a = float(weekly_px.loc[weeks[week_i - LOOKBACK_W]])
    b = float(weekly_px.loc[weeks[week_i]])
    if a <= 0 or b <= 0:
        return float("nan")
    return b / a - 1.0


def compute_u_weights(
    eligible: list[str],
    weekly_panel: dict[str, pd.Series],
    weeks: pd.DatetimeIndex,
    week_i: int,
    book_mode: str,
) -> dict[str, float]:
    n_s = len(eligible)
    if n_s == 0:
        return {}
    out: dict[str, float] = {}
    for code in eligible:
        px = weekly_panel[code]
        if book_mode == "H":
            ui = 1.0 / n_s
        elif book_mode == "U":
            r = r52(px, weeks, week_i)
            ui = (1.0 / n_s) if math.isfinite(r) and r > 0 else 0.0
        else:
            r = r52(px, weeks, week_i)
            if not math.isfinite(r) or r <= 0:
                ui = 0.0
            else:
                ui = 1.0 / n_s
                if book_mode in ("VS", "VS_BH", "ERC"):
                    sig = sigma_i(px, weeks, week_i)
                    if not math.isfinite(sig) or sig <= 0:
                        ui = 0.0
                    else:
                        ui *= min(L_CAP, SIGMA_STAR / sig)
        if ui > 0:
            out[code] = ui
    return out


def sleeve_budget_equal(n_declared: int) -> float:
    return 1.0 / n_declared if n_declared > 0 else 0.0


def local_data_paths() -> list[dict[str, Any]]:
    paths = ["/cj-data", "/pyas-data-discovery"]
    return [{"path": p, "exists": Path(p).exists()} for p in paths]


def try_rates_from_local() -> dict[str, pd.Series]:
    """If local data mounts exist, caller may extend; default empty."""
    return {}
