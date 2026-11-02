"""休市自判：时钟 + 节假日提示 + 行情日期三层。行情日期优先。"""

from __future__ import annotations

from collections import Counter
from datetime import date, datetime, time
from typing import Iterable
from zoneinfo import ZoneInfo

from .bars import Bar

SHANGHAI = ZoneInfo("Asia/Shanghai")

MORNING_OPEN = time(9, 30)
MORNING_CLOSE = time(11, 30)
AFTERNOON_OPEN = time(13, 0)
AFTERNOON_CLOSE = time(15, 0)

def _d(y: int, m: int, day: int) -> date:
    return date(y, m, day)


def _span(y: int, m: int, a: int, b: int) -> list[date]:
    return [_d(y, m, i) for i in range(a, b + 1)]


# 提示层，不是权威日历。2026 年常见休市窗；错漏靠行情日期纠偏。
HOLIDAY_HINTS_2026 = frozenset(
    [
        *_span(2026, 1, 1, 3),
        *_span(2026, 2, 15, 23),  # 春节窗（提示）
        *_span(2026, 4, 4, 6),
        *_span(2026, 5, 1, 5),
        *_span(2026, 6, 19, 21),
        *_span(2026, 9, 25, 27),
        *_span(2026, 10, 1, 8),
    ]
)


def now_shanghai(now: datetime | None = None) -> datetime:
    if now is None:
        return datetime.now(SHANGHAI)
    if now.tzinfo is None:
        return now.replace(tzinfo=SHANGHAI)
    return now.astimezone(SHANGHAI)


def is_weekday(d: date) -> bool:
    return d.weekday() < 5


def in_holiday_hint(d: date) -> bool:
    return d in HOLIDAY_HINTS_2026


def clock_state(now: datetime | None = None) -> dict:
    ts = now_shanghai(now)
    d = ts.date()
    t = ts.time()
    if not is_weekday(d) or in_holiday_hint(d):
        state = "closed_non_trading"
        label = "周末或节假日提示休市"
    elif MORNING_OPEN <= t <= MORNING_CLOSE or AFTERNOON_OPEN <= t <= AFTERNOON_CLOSE:
        state = "open"
        label = "沪深连续竞价"
    elif t < MORNING_OPEN:
        state = "pre"
        label = "开盘前"
    elif MORNING_CLOSE < t < AFTERNOON_OPEN:
        state = "lunch"
        label = "午间休市"
    else:
        state = "after_hours"
        label = "当日已收盘"
    return {
        "clock": ts.strftime("%Y-%m-%d %H:%M:%S"),
        "today": d.isoformat(),
        "weekday": is_weekday(d),
        "holiday_hint": in_holiday_hint(d),
        "clock_state": state,
        "clock_label": label,
    }


def last_trade_date(bars: Iterable[Bar]) -> str | None:
    dates = [b.trade_date for b in bars]
    if not dates:
        return None
    return max(dates)


def infer_session(now: datetime | None, bars_groups: Iterable[Iterable[Bar]]) -> dict:
    """用多数标的的最大行情日判定交易日；时钟只作会话阶段。"""
    clock = clock_state(now)
    dates = [last_trade_date(g) for g in bars_groups]
    dates = [d for d in dates if d]
    inferred = None
    if dates:
        inferred = Counter(dates).most_common(1)[0][0]
    today = clock["today"]
    if inferred is None:
        session = "no_data"
        trading_day = None
        note = "无可用分钟，无法自判交易日"
    elif inferred == today:
        session = clock["clock_state"] if clock["clock_state"] != "closed_non_trading" else "open_against_hint"
        trading_day = inferred
        note = "行情日=今日，按时钟标会话"
    elif clock["clock_state"] in {"closed_non_trading", "pre"}:
        session = "closed_prior"
        trading_day = inferred
        note = "今日非交易或未开盘，沿用最近行情日"
    else:
        session = "inferred_closed"
        trading_day = inferred
        note = "时钟像交易日但全样本最新行情日早于今日，按休市自判，不标红"
    return {
        **clock,
        "inferred_trade_date": inferred,
        "trading_day": trading_day,
        "session": session,
        "note": note,
        "is_trading_day": inferred == today if inferred else False,
    }
