#!/usr/bin/env python3
"""Unit checks for weekly VT12 overlay (no market cache)."""
from __future__ import annotations

import math

import numpy as np
import pandas as pd

from run import BOOK_FACE, LCAP, SIGMA_STAR_FACE, SIGMA_STAR_VT12, run_live_tv


def _book(n: int = 120, daily_vol: float = 0.02) -> tuple:
    days = pd.bdate_range("2020-01-03", periods=n)
    rng = np.random.default_rng(7)
    px = pd.DataFrame({"AAAAAA": 1.0 + np.cumsum(rng.normal(0.0, daily_vol, size=n))}, index=days)
    px = px.clip(lower=0.2)
    R = px.pct_change()
    fridays = [d for d in days if d.weekday() == 4]
    hold = {d: ["AAAAAA"] for d in fridays}
    return hold, days, px, R


def test_face_tv25_uses_daily_vol() -> None:
    hold, days, px, R = _book()
    _r, L, _rp, _c = run_live_tv(
        hold, days, px, R, sigma_star=SIGMA_STAR_FACE, vol_mode="daily_max2060"
    )
    assert float((L[L > 0] - 1.0).abs().max()) < 1.0  # may delever


def test_vt12_weekly_caps_leverage() -> None:
    hold, days, px, R = _book(daily_vol=0.03)
    slog: list = []
    r, L, _rp, _c = run_live_tv(
        hold,
        days,
        px,
        R,
        sigma_star=SIGMA_STAR_VT12,
        vol_mode="weekly_w20",
        scale_log=slog,
    )
    invested = L[L > 0]
    assert float(invested.max()) <= LCAP + 1e-12
    vol = float(r.std(ddof=1) * math.sqrt(252))
    assert vol < 0.22


if __name__ == "__main__":
    test_face_tv25_uses_daily_vol()
    test_vt12_weekly_caps_leverage()
    print("ok")
