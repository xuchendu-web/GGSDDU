from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import pandas as pd

from .compression import batch_gate, weekly_bars
from .data import breadth_b45, friday_signal_dates, load_panel, sharpe20
from .metrics import book_metrics, entry_quality


@dataclass
class FaceConfig:
    breadth_min: float = 0.45
    spike_max: int = 5
    vol_target: float = 0.25
    cost_rt: float = 0.002
    leverage_cap: float = 1.0
    sharpe_lookback: int = 20
    compression_n: int | None = None  # None = FACE


def _vol_scale(weights: np.ndarray, vols: np.ndarray, target: float, cap: float) -> np.ndarray:
    if weights.sum() <= 0:
        return weights
    port_vol = float(np.sqrt(np.sum((weights * vols) ** 2)))
    if port_vol <= 1e-8:
        return weights * 0.0
    scale = min(target / port_vol, cap / weights.sum())
    return weights * scale


def run_face(
    cfg: FaceConfig,
    start: str = "2020-01-03",
    end: str = "2026-10-23",
) -> tuple[pd.Series, pd.DataFrame, pd.DataFrame]:
    panel = load_panel()
    weekly_by = {c: weekly_bars(df) for c, df in panel.items()}
    dates = friday_signal_dates(panel, start, end)
    if len(dates) == 0:
        raise RuntimeError("no signal dates in panel")

    nav = 1.0
    navs = []
    nav_idx = []
    turnovers = []
    leverages = []
    holdings: dict[str, float] = {}
    entry_rows = []

    for i, d in enumerate(dates):
        b = breadth_b45(panel, d)
        risk_on = b >= cfg.breadth_min
        target_w: dict[str, float] = {}
        if risk_on:
            scores = []
            for code, df in panel.items():
                sh = sharpe20(df["close"], d)
                if np.isfinite(sh):
                    scores.append((code, sh))
            scores.sort(key=lambda x: x[1], reverse=True)
            prev_set = set(holdings.keys())
            picked = []
            for code, _ in scores:
                if len(picked) >= cfg.spike_max:
                    break
                is_new = code not in prev_set
                if is_new and not batch_gate(weekly_by, code, d, cfg.compression_n):
                    continue
                picked.append(code)
            if picked:
                raw = np.ones(len(picked)) / len(picked)
                vols = []
                for code in picked:
                    r = panel[code]["close"].loc[:d].pct_change().tail(20).std() * np.sqrt(252)
                    vols.append(r if np.isfinite(r) and r > 0 else 0.2)
                w = _vol_scale(raw, np.array(vols), cfg.vol_target, cfg.leverage_cap)
                for j, code in enumerate(picked):
                    target_w[code] = float(w[j])

        # turnover + cost
        all_codes = set(holdings) | set(target_w)
        to = 0.0
        for c in all_codes:
            to += abs(target_w.get(c, 0.0) - holdings.get(c, 0.0))
        nav *= 1.0 - cfg.cost_rt * to
        turnovers.append(to)
        leverages.append(sum(target_w.values()))

        # weekly return (close to close into next signal)
        next_idx = i + 1
        if next_idx < len(dates):
            d1 = dates[next_idx]
        else:
            d1 = min(df.index.max() for df in panel.values())

        port_ret = 0.0
        for code, w in target_w.items():
            px0 = panel[code]["close"].asof(d)
            px1 = panel[code]["close"].asof(d1)
            if pd.isna(px0) or pd.isna(px1) or px0 == 0:
                continue
            r = px1 / px0 - 1.0
            port_ret += w * r
            if code not in holdings and w > 0:
                entry_rows.append(
                    {
                        "symbol": code,
                        "entry_date": d,
                        "ret_1w": r,
                    }
                )
        nav *= 1.0 + port_ret
        holdings = target_w
        navs.append(nav)
        nav_idx.append(d1)

    nav_s = pd.Series(navs, index=pd.DatetimeIndex(nav_idx), name="nav")
    to_s = pd.Series(turnovers, index=dates[: len(turnovers)], name="turnover")
    entries = pd.DataFrame(entry_rows)
    lev_s = pd.Series(leverages, index=dates[: len(leverages)], name="leverage")
    return nav_s, to_s, entries, lev_s


def run_book(cfg: FaceConfig) -> dict:
    nav, to, entries, lev = run_face(cfg)
    m = book_metrics(nav, to)
    eq = entry_quality(entries)
    m.update(
        {
            "book": f"CB-N{cfg.compression_n}" if cfg.compression_n else "FACE-B45-S20-LIVE1430",
            "compression_n": cfg.compression_n,
            **eq,
        }
    )
    m["avgL"] = float(lev.mean()) if len(lev) else np.nan
    return {"metrics": m, "nav": nav, "turnover": to, "entries": entries}
