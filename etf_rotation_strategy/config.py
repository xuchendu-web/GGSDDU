# -*- coding: utf-8 -*-
"""官方策略参数:2022-01-01 起至样本末,每次只持有 1 只 ETF。"""

OFFICIAL = dict(
    pick_mode="class",
    mom_wins=(10, 20, 60),
    top_k=1,
    rebal_n=10,
    abs_thresh=0.0,
    ma_win=20,
    trail_stop=0.05,
    confirm_all=False,
    start="2022-01-01",
    end=None,
    risk_adj=True,
    fee=5e-4,
    liq_win=20,
    min_days=120,
)

# 对照:同一套规则从 2019 年起
LONG_SAMPLE = dict(OFFICIAL, start="2019-01-01", end=None)
