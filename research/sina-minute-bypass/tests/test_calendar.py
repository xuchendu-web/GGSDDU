import unittest
from datetime import datetime

from sina_bypass.bars import Bar
from sina_bypass.calendar import clock_state, infer_session


def _bar(day: str) -> Bar:
    return Bar(
        code="510300",
        scale=1,
        ts=datetime.strptime(day + " 14:55", "%Y-%m-%d %H:%M"),
        open=1,
        high=1,
        low=1,
        close=1,
        volume=1,
        amount=1,
        source="sina_cn",
    )


class CalendarTests(unittest.TestCase):
    def test_weekend_clock(self):
        # 2026-11-01 周日
        st = clock_state(datetime(2026, 11, 1, 10, 0))
        self.assertEqual(st["clock_state"], "closed_non_trading")

    def test_open_clock(self):
        st = clock_state(datetime(2026, 11, 2, 10, 0))
        self.assertEqual(st["clock_state"], "open")

    def test_infer_today(self):
        now = datetime(2026, 11, 2, 10, 5)
        out = infer_session(now, [[_bar("2026-11-02")]])
        self.assertTrue(out["is_trading_day"])
        self.assertEqual(out["trading_day"], "2026-11-02")
        self.assertEqual(out["session"], "open")

    def test_infer_closed_when_bars_old_on_weekday(self):
        now = datetime(2026, 11, 2, 10, 5)
        out = infer_session(now, [[_bar("2026-10-30")], [_bar("2026-10-30")]])
        self.assertEqual(out["session"], "inferred_closed")
        self.assertEqual(out["trading_day"], "2026-10-30")
        self.assertFalse(out["is_trading_day"])

    def test_weekend_uses_prior(self):
        now = datetime(2026, 11, 1, 10, 0)
        out = infer_session(now, [[_bar("2026-10-30")]])
        self.assertEqual(out["session"], "closed_prior")


if __name__ == "__main__":
    unittest.main()
