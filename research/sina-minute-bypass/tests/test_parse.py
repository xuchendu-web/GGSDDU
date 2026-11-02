import json
import unittest
from pathlib import Path

from sina_bypass.http import parse_jsonp
from sina_bypass.sina_client import _bars_from_payload
from sina_bypass.tencent_client import parse_mkline_payload

FIX = Path(__file__).resolve().parent / "fixtures"


class ParseTests(unittest.TestCase):
    def test_sina_jsonp(self):
        text = (FIX / "sina_jsonp_1m.txt").read_text(encoding="utf-8")
        payload = parse_jsonp(text)
        bars = _bars_from_payload("510300", 1, payload, "sina_cn")
        self.assertEqual(len(bars), 2)
        self.assertEqual(bars[-1].ts_key, "2026-11-02 09:40")
        self.assertAlmostEqual(bars[-1].close, 4.075)

    def test_money_null(self):
        text = (FIX / "money_finance_null.txt").read_text(encoding="utf-8").strip()
        self.assertEqual(text, "null")
        self.assertIsNone(parse_jsonp(text))

    def test_tencent_mkline(self):
        payload = json.loads((FIX / "tencent_mkline_1m.json").read_text(encoding="utf-8"))
        bars = parse_mkline_payload("510300", 1, payload)
        self.assertEqual(len(bars), 2)
        self.assertEqual(bars[0].source, "tencent")
        self.assertAlmostEqual(bars[0].open, 4.076)
        self.assertAlmostEqual(bars[0].close, 4.077)
        self.assertAlmostEqual(bars[0].high, 4.080)


class UniverseTests(unittest.TestCase):
    def test_count(self):
        from sina_bypass.universe import load_universe

        etfs = load_universe()
        self.assertGreaterEqual(len(etfs), 20)
        codes = [e["code"] for e in etfs]
        self.assertIn("510300", codes)
        self.assertIn("159915", codes)
        self.assertEqual(len(codes), len(set(codes)))


if __name__ == "__main__":
    unittest.main()
