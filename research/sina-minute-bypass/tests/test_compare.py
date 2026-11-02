import unittest
from datetime import datetime

from sina_bypass.bars import Bar
from sina_bypass.compare import compare_symbol
from sina_bypass.sina_client import FetchResult


def _bar(code: str, ts: str, close: float, source: str) -> Bar:
    return Bar(
        code=code,
        scale=1,
        ts=datetime.strptime(ts, "%Y-%m-%d %H:%M"),
        open=close,
        high=close,
        low=close,
        close=close,
        volume=100,
        amount=None,
        source=source,
    )


def _fr(source: str, bars: list[Bar], ok: bool = True, error: str = "") -> FetchResult:
    return FetchResult(source, "510300", 1, ok, bars=bars, error=error)


class CompareTests(unittest.TestCase):
    def test_green_within_3bp(self):
        sina = _fr("sina_cn", [_bar("510300", "2026-11-02 09:40", 4.075, "sina_cn")])
        tec = _fr("tencent", [_bar("510300", "2026-11-02 09:40", 4.074, "tencent")])
        r = compare_symbol(sina, tec, name="沪深300ETF")
        self.assertEqual(r.flag, "GREEN")
        self.assertLessEqual(r.last_abs_pct, 0.003)

    def test_yellow_over_30bp(self):
        sina = _fr("sina_cn", [_bar("510300", "2026-11-02 09:40", 4.090, "sina_cn")])
        tec = _fr("tencent", [_bar("510300", "2026-11-02 09:40", 4.070, "tencent")])
        r = compare_symbol(sina, tec, name="沪深300ETF")
        self.assertEqual(r.flag, "YELLOW")
        self.assertGreater(r.last_abs_pct, 0.003)

    def test_red_sina_fail(self):
        sina = _fr("sina_cn", [], ok=False, error="empty")
        tec = _fr("tencent", [_bar("510300", "2026-11-02 09:40", 4.07, "tencent")])
        r = compare_symbol(sina, tec, session="open")
        self.assertEqual(r.flag, "RED")

    def test_closed_tencent_missing_not_red(self):
        sina = _fr("sina_cn", [_bar("510300", "2026-10-30 14:59", 4.07, "sina_cn")])
        tec = _fr("tencent", [], ok=False, error="empty")
        r = compare_symbol(sina, tec, session="inferred_closed")
        self.assertEqual(r.flag, "YELLOW")

    def test_stale_last_ts_red_when_open(self):
        sina = _fr("sina_cn", [_bar("510300", "2026-11-02 09:50", 4.07, "sina_cn")])
        tec = _fr("tencent", [_bar("510300", "2026-11-02 09:40", 4.07, "tencent")])
        r = compare_symbol(sina, tec, session="open")
        self.assertEqual(r.flag, "RED")
        self.assertTrue(any(x.startswith("stale_last_ts") for x in r.reasons))


if __name__ == "__main__":
    unittest.main()
