"""沪深交易时段（上海时区，无夏令时）。"""

from __future__ import annotations

from datetime import date, datetime, time, timedelta
from zoneinfo import ZoneInfo

SHANGHAI = ZoneInfo("Asia/Shanghai")

MORNING_OPEN = time(9, 30)
MORNING_CLOSE = time(11, 30)
AFTERNOON_OPEN = time(13, 0)
AFTERNOON_CLOSE = time(15, 0)
PREOPEN = time(9, 15)


def now_shanghai(now: datetime | None = None) -> datetime:
    if now is None:
        return datetime.now(SHANGHAI)
    if now.tzinfo is None:
        return now.replace(tzinfo=SHANGHAI)
    return now.astimezone(SHANGHAI)


def is_weekday(d: date) -> bool:
    return d.weekday() < 5


def in_continuous_auction(now: datetime | None = None) -> bool:
    ts = now_shanghai(now)
    if not is_weekday(ts.date()):
        return False
    t = ts.time()
    return MORNING_OPEN <= t <= MORNING_CLOSE or AFTERNOON_OPEN <= t <= AFTERNOON_CLOSE


def in_session_window(now: datetime | None = None) -> bool:
    """含集合竞价到收盘，用于自动刷新。"""
    ts = now_shanghai(now)
    if not is_weekday(ts.date()):
        return False
    t = ts.time()
    return PREOPEN <= t <= AFTERNOON_CLOSE


def market_status(now: datetime | None = None) -> dict:
    ts = now_shanghai(now)
    if not is_weekday(ts.date()):
        label = "周末休市"
        state = "closed"
    elif in_continuous_auction(ts):
        label = "沪深交易中"
        state = "open"
    elif ts.time() < PREOPEN:
        label = "开盘前"
        state = "pre"
    elif MORNING_CLOSE < ts.time() < AFTERNOON_OPEN:
        label = "午间休市"
        state = "lunch"
    else:
        label = "沪深已收盘"
        state = "closed"
    return {
        "label": label,
        "state": state,
        "clock": ts.strftime("%H:%M:%S"),
        "date": ts.strftime("%Y-%m-%d"),
        "should_autorefresh": state in {"open", "lunch", "pre"},
    }


def recent_calendar_start(days_back: int = 80, now: datetime | None = None) -> str:
    ts = now_shanghai(now)
    return (ts.date() - timedelta(days=days_back)).strftime("%Y%m%d")


def today_yyyymmdd(now: datetime | None = None) -> str:
    return now_shanghai(now).strftime("%Y%m%d")


def today_iso(now: datetime | None = None) -> str:
    return now_shanghai(now).strftime("%Y-%m-%d")
