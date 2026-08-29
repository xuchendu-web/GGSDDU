from etf_board.indicators import bias, n_day_return, overlay_live_close, premium_rate, target_price
import pandas as pd


def test_n_day_return_needs_n_plus_one_bars():
    closes = [100, 101, 102]
    assert pd.isna(n_day_return(closes, 3))
    # 2 日涨跌 = 102 / 100 - 1
    assert abs(n_day_return(closes, 2) - 0.02) < 1e-12


def test_n_day_return_nineteen_vs_twenty_bars():
    closes = list(range(1, 21))  # 20 根，今日=20
    # 19 日：20 / 1 - 1 = 19
    assert n_day_return(closes, 19) == 19.0


def test_bias_and_target_price():
    closes = [10.0] * 19 + [12.0]
    ma = (10.0 * 19 + 12.0) / 20
    expected_bias = 12.0 / ma - 1.0
    assert abs(bias(closes, 20) - expected_bias) < 1e-12
    assert abs(target_price(closes, 20, 0.10) - ma * 1.10) < 1e-12
    assert abs(target_price(closes, 20, 0.15) - ma * 1.15) < 1e-12


def test_premium_from_iopv_not_raw_field():
    # 市价 9.530，IOPV 9.540 → 溢价 -0.1048%
    prem = premium_rate(9.530, 9.540)
    assert abs(prem - (9.530 / 9.540 - 1)) < 1e-12
    assert pd.isna(premium_rate(9.53, 0))
    assert pd.isna(premium_rate(9.53, float("nan")))


def test_overlay_replaces_today_and_appends_when_missing():
    hist = pd.DataFrame({"日期": ["2026-08-27", "2026-08-28"], "收盘": [9.4, 9.5]})
    series = overlay_live_close(hist, 9.53, "2026-08-28")
    assert list(series.round(3)) == [9.4, 9.53]
    series2 = overlay_live_close(hist, 9.60, "2026-08-29")
    assert list(series2.round(3)) == [9.4, 9.5, 9.6]
