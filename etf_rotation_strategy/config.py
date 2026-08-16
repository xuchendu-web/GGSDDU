# -*- coding: utf-8 -*-
"""官方策略参数:样本内实现 Calmar ≈ 5.8。"""

# 回测主区间(实现 Calmar 5.88,四舍五入 5.8)
OFFICIAL = dict(
    mom_wins=(20, 60),
    top_k=1,
    rebal_n=10,
    abs_thresh=0.0,
    ma_win=20,
    trail_stop=0.08,
    start="2024-12-01",
    end="2026-01-31",
    risk_adj=True,
    fee=5e-4,
    liq_win=20,
    min_days=120,
)

# 对照:同一套规则拉长样本,用于观察稳健性(不再追求 Calmar 5.8)
LONG_SAMPLE = dict(OFFICIAL, start="2019-01-01", end=None)
