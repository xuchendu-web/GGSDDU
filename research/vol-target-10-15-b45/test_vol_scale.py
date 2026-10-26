#!/usr/bin/env python3
"""Unit checks for the VT12 overlay (no market cache)."""
from __future__ import annotations

import math

import numpy as np
import pandas as pd

from run import LCAP, SIGMA_STAR_VT12, run_live_tv


def _book(n: int = 80, daily_vol: float = 0.02) -> tuple:
    days = pd.bdate_range("2020-01-03", periods=n)
    rng = np.random.default_rng(7)
    px = pd.DataFrame({"AAAAAA": 1.0 + np.cumsum(rng.normal(0.0, daily_vol, size=n))}, index=days)
    px = px.clip(lower=0.2)
    R = px.pct_change()
    fridays = [d for d in days if d.weekday() == 4]
    hold_w = {d: {"AAAAAA": 1.0} for d in fridays}
    return hold_w, days, px, R


def test_unscaled_is_unit_leverage() -> None:
    hold_w, days, px, R = _book()
    _r, L, _to = run_live_tv(hold_w, days, px, R, sigma_star=None)
    assert float((L[L > 0] - 1.0).abs().max()) < 1e-12


def test_vt12_delevers_when_realized_vol_high() -> None:
    hold_w, days, px, R = _book(daily_vol=0.03)
    slog: list[dict] = []
    r, L, _to = run_live_tv(hold_w, days, px, R, sigma_star=SIGMA_STAR_VT12, scale_log=slog)
    invested = L[L > 0]
    assert float(invested.mean()) < 0.85
    assert float(invested.max()) <= LCAP + 1e-12
    vol = float(r.std(ddof=1) * math.sqrt(252))
    assert vol < 0.20
    later = [row for row in slog if row["n_held"] and row["sh"] == row["sh"]]
    assert later
    for row in later:
        if row["sh"] and row["sh"] > 0:
            expect = min(LCAP, SIGMA_STAR_VT12 / float(row["sh"]))
            assert abs(float(row["L"]) - expect) < 1e-9


if __name__ == "__main__":
    test_unscaled_is_unit_leverage()
    test_vt12_delevers_when_realized_vol_high()
    print("ok")
