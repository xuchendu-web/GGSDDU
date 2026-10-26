from __future__ import annotations

import pandas as pd

from dual_momentum.metrics import align_face_weekly, book_stats, covers_mdd, yearly_stats


def test_book_stats_known_path():
    idx = pd.date_range("2020-01-03", periods=53, freq="W-FRI")
    nav = pd.Series(1.0, index=idx)
    nav.iloc[-1] = 1.21
    st = book_stats(nav)
    assert abs(st["ret"] - 0.21) < 1e-12
    assert st["maxDD"] == 0.0 or st["maxDD"] > -1e-12


def test_drawdown_from_peak():
    idx = pd.date_range("2020-01-03", periods=4, freq="W-FRI")
    nav = pd.Series([1.0, 1.2, 0.9, 1.0], index=idx)
    st = book_stats(nav)
    assert abs(st["maxDD"] - (0.9 / 1.2 - 1.0)) < 1e-12


def test_covers_mdd_ruler():
    assert covers_mdd(0.20, -0.15, 0.10, -0.10) is True  # +10pp ret vs +5pp |MDD|
    assert covers_mdd(0.11, -0.25, 0.10, -0.10) is False


def test_align_face_weekly_ffill():
    daily = pd.Series(
        [1.0, 1.1, 1.2],
        index=pd.to_datetime(["2020-01-02", "2020-01-03", "2020-01-06"]),
    )
    weeks = pd.to_datetime(["2020-01-03", "2020-01-10"])
    got = align_face_weekly(daily, weeks)
    assert abs(got.iloc[0] - 1.1) < 1e-12
    assert abs(got.iloc[1] - 1.2) < 1e-12


def test_yearly_splits():
    idx = pd.to_datetime(["2020-12-25", "2021-01-01", "2021-12-31"])
    nav = pd.Series([1.0, 1.1, 1.21], index=idx)
    y = yearly_stats(nav)
    assert set(y["year"]) == {2021}
