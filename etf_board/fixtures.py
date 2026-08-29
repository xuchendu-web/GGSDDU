"""离线演示数据。云环境访问东财失败时，看板仍能按同一口径渲染。"""

from __future__ import annotations

from datetime import datetime, timedelta

import numpy as np
import pandas as pd

from etf_board.store import upsert_daily, upsert_spot


def _series(start: float, n: int, drift: float, seed: int) -> list[float]:
    rng = np.random.default_rng(seed)
    rets = rng.normal(drift, 0.012, size=n)
    prices = [start]
    for r in rets:
        prices.append(round(prices[-1] * (1 + float(r)), 3))
    return prices[1:]


def demo_history(code: str, n: int = 40) -> pd.DataFrame:
    profiles = {
        "518880": (8.40, 0.006, 11),
        "513100": (2.20, 0.003, 22),
        "510300": (3.90, 0.001, 33),
    }
    start, drift, seed = profiles.get(code, (1.50, 0.0, 99))
    closes = _series(start, n, drift, seed)
    dates = pd.bdate_range(end=pd.Timestamp.now(tz="Asia/Shanghai").normalize(), periods=n)
    rows = []
    for i, (d, c) in enumerate(zip(dates, closes)):
        rows.append(
            {
                "日期": d.strftime("%Y-%m-%d"),
                "开盘": round(c * 0.998, 3),
                "最高": round(c * 1.008, 3),
                "最低": round(c * 0.992, 3),
                "收盘": c,
                "成交量": 1e7 + i * 1e5,
                "成交额": 8e8 + i * 1e7,
            }
        )
    return pd.DataFrame(rows)


def demo_spot() -> pd.DataFrame:
    now = datetime.now()
    return pd.DataFrame(
        [
            {
                "代码": "518880",
                "名称": "黄金ETF",
                "最新价": 9.530,
                "涨跌幅": -0.36,
                "IOPV实时估值": 9.540,
                "基金折价率": 0.10,
                "成交额": 18.6e8,
                "成交量": 1.95e8,
                "最高价": 9.61,
                "最低价": 9.50,
                "数据日期": now.strftime("%Y-%m-%d"),
                "更新时间": now.strftime("%H:%M:%S"),
            },
            {
                "代码": "513100",
                "名称": "纳指ETF",
                "最新价": 2.451,
                "涨跌幅": 0.49,
                "IOPV实时估值": 2.444,
                "基金折价率": -0.29,
                "成交额": 42.3e8,
                "成交量": 17.2e8,
                "最高价": 2.46,
                "最低价": 2.43,
                "数据日期": now.strftime("%Y-%m-%d"),
                "更新时间": now.strftime("%H:%M:%S"),
            },
            {
                "代码": "510300",
                "名称": "沪深300ETF",
                "最新价": 4.215,
                "涨跌幅": 0.12,
                "IOPV实时估值": 4.218,
                "基金折价率": 0.07,
                "成交额": 56.1e8,
                "成交量": 13.3e8,
                "最高价": 4.23,
                "最低价": 4.19,
                "数据日期": now.strftime("%Y-%m-%d"),
                "更新时间": now.strftime("%H:%M:%S"),
            },
        ]
    )


def seed_demo(conn, codes: list[str] | None = None) -> None:
    spot = demo_spot()
    upsert_spot(conn, spot)
    use = codes or list(spot["代码"])
    for code in use:
        upsert_daily(conn, code, demo_history(code), adjust="qfq")
