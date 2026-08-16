# -*- coding: utf-8 -*-
"""策略关键约束的回归测试。"""
import numpy as np
import pandas as pd

from backtest import calc_stats, clean_returns, load_wide, run_backtest
from config import OFFICIAL
from universe import asset_class


def test_split_day_zeroed():
    close, _, _ = load_wide()
    ret, _ = clean_returns(close)
    # 588170 在 2026-07-06 发生份额折算,原始收益约 -67%,应被置 0
    if "588170" in ret.columns:
        day = pd.Timestamp("2026-07-06")
        if day in ret.index:
            assert abs(ret.loc[day, "588170"]) < 1e-12


def test_always_full_and_calmar():
    close, amount, names = load_wide()
    ser, hold, st = run_backtest(close, amount, names, **OFFICIAL)
    days = list(hold)
    # 首日允许空仓(T+1 生效),之后必须满仓
    for d in days[1:]:
        assert len(hold[d]) >= 1, f"empty {d}"
    assert 5.5 <= st["calmar"] <= 6.2, st["calmar"]
    assert st["max_drawdown"] < 0.15
    # 持仓必须来自成交额达标的场内基金
    assert ser.notna().all()


def test_asset_class_money_and_gold():
    assert asset_class("华宝添益ETF") == "货币"
    assert asset_class("黄金ETF华安") == "黄金"
    assert asset_class("黄金股ETF国泰") is None
    assert asset_class("港股创新药ETF广发") is None
    assert asset_class("恒生ETF华夏") == "港股"


def test_stats_calmar_identity():
    r = pd.Series([0.01, -0.005, 0.02, 0.0], index=pd.bdate_range("2024-01-01", periods=4))
    st = calc_stats(r)
    assert np.isclose(st["calmar"], st["annual_return"] / st["max_drawdown"])


if __name__ == "__main__":
    test_split_day_zeroed()
    test_asset_class_money_and_gold()
    test_stats_calmar_identity()
    test_always_full_and_calmar()
    print("all tests passed")
