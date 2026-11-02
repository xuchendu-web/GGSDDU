#!/usr/bin/env python3
"""腾讯公开分钟探活：解析 / 14:30 过滤 / 休市自判 / 黄线，不碰网络。"""

from __future__ import annotations

import sys
import unittest
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from probe_tencent_minute import (  # noqa: E402
    CST,
    classify_session,
    filter_le_1430_bars,
    filter_le_1430_pts,
    keep_session_bars,
    market_prefix,
    parse_m1_node,
    parse_minute_node,
    parse_qt_body,
    rel_diff,
    symbol,
    traffic_light,
    yellow_spread,
    MinuteBar,
    TimelinePt,
)


QT_SAMPLE = (
    'v_sh510300="1~沪深300ETF华泰柏瑞~510300~4.076~4.065~4.084~1915600~'
    "757659~1157550~4.075~1142~4.074~7603~4.073~7147~4.072~5257~4.071~3162~"
    "4.076~341~4.077~17877~4.078~54550~4.079~63605~4.080~8086~~20261102094328~"
    '0.011~0.27~4.093~4.065~4.076/1915600/780792247~1915600~78079~0.49";'
)

M1_PAYLOAD = {
    "code": 0,
    "data": {
        "sh510300": {
            "m1": [
                ["202611021428", "4.080", "4.081", "4.082", "4.079", "1000"],
                ["202611021431", "4.081", "4.090", "4.091", "4.080", "2000"],
                ["202611021500", "4.090", "4.088", "4.092", "4.087", "3000"],
            ]
        }
    },
}

MINUTE_PAYLOAD = {
    "code": 0,
    "data": {
        "sh510300": {
            "data": {
                "date": "20261102",
                "data": [
                    "1428 4.081 100 1",
                    "1430 4.082 110 1.1",
                    "1431 4.090 120 1.2",
                ],
            }
        }
    },
}


class PrefixTests(unittest.TestCase):
    def test_sh_sz(self) -> None:
        self.assertEqual(market_prefix("510300"), "sh")
        self.assertEqual(market_prefix("588000"), "sh")
        self.assertEqual(market_prefix("159915"), "sz")
        self.assertEqual(symbol("159915"), "sz159915")


class ParseTests(unittest.TestCase):
    def test_qt(self) -> None:
        rec = parse_qt_body(QT_SAMPLE)["510300"]
        self.assertEqual(rec["name"], "沪深300ETF华泰柏瑞")
        self.assertAlmostEqual(rec["price"], 4.076)
        self.assertAlmostEqual(rec["prev_close"], 4.065)
        self.assertEqual(rec["session_date"], "20261102")
        self.assertEqual(rec["session_hhmmss"], "094328")
        self.assertNotIn("aum", rec)

    def test_m1_and_1430(self) -> None:
        bars = parse_m1_node(M1_PAYLOAD, "510300")
        self.assertEqual(len(bars), 3)
        self.assertAlmostEqual(bars[0].c or 0, 4.081)
        cut = filter_le_1430_bars(bars)
        self.assertEqual([b.hhmm for b in cut], ["1428"])
        self.assertTrue(all((b.hhmm_i or 0) <= 1430 for b in cut))

    def test_keep_session_drops_prev_day(self) -> None:
        mixed = [
            MinuteBar("202610311500", "20261031", "1500", 1, 1, 1, 1, 1),
            MinuteBar("202611020930", "20261102", "0930", 1, 1, 1, 1, 1),
        ]
        kept = keep_session_bars(mixed, "20261102")
        self.assertEqual([b.session_date for b in kept], ["20261102"])
        self.assertEqual(keep_session_bars(mixed, "")[-1].session_date, "20261102")

    def test_timeline_and_1430(self) -> None:
        date, pts = parse_minute_node(MINUTE_PAYLOAD, "510300")
        self.assertEqual(date, "20261102")
        self.assertEqual(len(pts), 3)
        cut = filter_le_1430_pts(pts)
        self.assertEqual([p.hhmm for p in cut], ["1428", "1430"])


class GateTests(unittest.TestCase):
    def test_yellow_03pct(self) -> None:
        self.assertFalse(yellow_spread((1.0, 1.002)))
        self.assertTrue(yellow_spread((1.0, 1.004)))
        self.assertIsNone(rel_diff(None, 1.0))

    def test_replay_vs_stale(self) -> None:
        monday_open = datetime(2026, 11, 2, 10, 0, tzinfo=CST)
        kind, _ = classify_session("20261031", monday_open, "1500")
        self.assertEqual(kind, "stale")
        sunday = datetime(2026, 11, 1, 20, 0, tzinfo=CST)
        kind, _ = classify_session("20261031", sunday, "1500")
        self.assertEqual(kind, "replay")
        kind, _ = classify_session("20261102", monday_open, "0955")
        self.assertEqual(kind, "live")
        # 10:00 vs 09:55 是 5 分钟，hhmm 相减会得到 45，不能当停滞
        ten = datetime(2026, 11, 2, 10, 0, tzinfo=CST)
        kind, _ = classify_session("20261102", ten, "0955")
        self.assertEqual(kind, "live")
        kind, _ = classify_session("20261102", ten, "0948")
        self.assertEqual(kind, "stale")

    def test_lights(self) -> None:
        flag, _ = traffic_light(
            ok_http=False,
            price=None,
            n_m1=0,
            session_kind="unknown",
            spread_yellow=False,
            n_near=0,
            in_session=True,
        )
        self.assertEqual(flag, "红")
        flag, _ = traffic_light(
            ok_http=True,
            price=4.0,
            n_m1=10,
            session_kind="stale",
            spread_yellow=False,
            n_near=10,
            in_session=True,
        )
        self.assertEqual(flag, "红")
        flag, why = traffic_light(
            ok_http=True,
            price=4.0,
            n_m1=10,
            session_kind="replay",
            spread_yellow=True,
            n_near=10,
            in_session=False,
        )
        self.assertEqual(flag, "黄")
        self.assertIn("0.3%", why)
        flag, why = traffic_light(
            ok_http=True,
            price=4.0,
            n_m1=0,
            session_kind="live",
            spread_yellow=False,
            n_near=20,
            in_session=True,
        )
        self.assertEqual(flag, "黄")
        self.assertIn("1m 空包", why)
        flag, _ = traffic_light(
            ok_http=True,
            price=4.0,
            n_m1=0,
            session_kind="live",
            spread_yellow=False,
            n_near=0,
            in_session=True,
        )
        self.assertEqual(flag, "红")
        flag, _ = traffic_light(
            ok_http=True,
            price=4.0,
            n_m1=20,
            session_kind="live",
            spread_yellow=False,
            n_near=20,
            in_session=True,
        )
        self.assertEqual(flag, "绿")


class FilterEdgeTests(unittest.TestCase):
    def test_empty_safe(self) -> None:
        self.assertEqual(filter_le_1430_bars([]), [])
        self.assertEqual(filter_le_1430_pts([]), [])
        bar = MinuteBar("202611021430", "20261102", "1430", 1, 1, 1, 1, 1)
        self.assertEqual(filter_le_1430_bars([bar])[0].hhmm, "1430")
        pt = TimelinePt("20261102", "1430", 1.0, 1, 1)
        self.assertEqual(filter_le_1430_pts([pt])[0].hhmm, "1430")


if __name__ == "__main__":
    unittest.main()
