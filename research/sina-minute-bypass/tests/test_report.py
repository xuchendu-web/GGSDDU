import tempfile
import unittest
from datetime import datetime
from pathlib import Path

from sina_bypass.bars import Bar
from sina_bypass.compare import CompareResult
from sina_bypass.report import render_summary, write_bars_csv
from sina_bypass.tencent_client import load_tencent_csv


class ReportTests(unittest.TestCase):
    def test_summary_mentions_rules(self):
        md = render_summary(
            session={"session": "open", "clock_state": "open", "clock": "x", "trading_day": "2026-11-02", "today": "2026-11-02", "note": "ok"},
            compares=[
                CompareResult(
                    code="510300",
                    name="沪深300ETF",
                    scale=1,
                    flag="YELLOW",
                    reasons=["abs_pct>0.3%"],
                    last_ts="2026-11-02 09:40",
                    sina_close=4.09,
                    tencent_close=4.07,
                    last_abs_pct=0.0049,
                    max_abs_pct=0.0049,
                    overlap=1,
                )
            ],
            scales=[1, 5],
            money_finance_notes=["510300 1m → ok=False err=null"],
            generated_at="2026-11-02 10:00:00",
        )
        self.assertIn("YELLOW", md)
        self.assertIn("0.3%", md)
        self.assertIn("进门", md)
        self.assertIn("strategy_exec", md)

    def test_tencent_csv_roundtrip(self):
        bar = Bar(
            code="510300",
            scale=1,
            ts=datetime(2026, 11, 2, 9, 40),
            open=4.07,
            high=4.08,
            low=4.06,
            close=4.075,
            volume=1,
            amount=None,
            source="tencent",
        )
        with tempfile.TemporaryDirectory() as td:
            path = Path(td) / "t.csv"
            write_bars_csv(path, [bar])
            loaded = load_tencent_csv(str(path), scale=1)
            self.assertEqual(list(loaded)[0], "510300")
            self.assertAlmostEqual(loaded["510300"][0].close, 4.075)


if __name__ == "__main__":
    unittest.main()
