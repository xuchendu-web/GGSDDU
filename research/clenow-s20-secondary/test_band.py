"""Design fixtures for CLENOW-S20-SECONDARY. Not a backtest.

Run from the repo root:

    python3 research/clenow-s20-secondary/test_band.py

A failure exits non-zero and must not create ``out/``.
"""

from __future__ import annotations

import json
import math
import subprocess
import sys
import unittest
from datetime import date, timedelta
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

import band  # noqa: E402


def _codes(take) -> list[str]:
    return [c.code for c in take]


def _line(n: int, daily: float, noise: float = 0.0) -> list[float]:
    out = []
    for i in range(n):
        shock = noise if (i % 2 == 0) else -noise
        out.append(math.exp(daily * i + shock))
    return out


def _bars(prices, signal: date):
    """One bar per calendar day, ending the day before ``signal``."""
    start = signal - timedelta(days=len(prices))
    return [(start + timedelta(days=i), px) for i, px in enumerate(prices)]


class SeatOrderTest(unittest.TestCase):
    def test_cs90s_seat_order_changes_with_score_same_band(self):
        """Same S20 band, same slots: the seat follows the Clenow score."""
        slots = 1
        self.assertEqual(band.band_k(slots), 3)
        low = [
            band.Cand("A", score=0.2, slope_ann=0.2),
            band.Cand("B", score=0.4, slope_ann=0.4),
            band.Cand("C", score=0.9, slope_ann=0.9),
            band.Cand("D", score=5.0, slope_ann=5.0),
        ]
        band_low = band.take_band(low, slots)
        self.assertEqual(_codes(band_low), ["A", "B", "C"])
        take_low, how_low = band.pick(band_low, slots, "clenow_sort")
        self.assertEqual(how_low, "sorted")
        self.assertEqual(_codes(take_low), ["C"])

        high = [
            band.Cand("A", score=0.9, slope_ann=0.9),
            band.Cand("B", score=0.4, slope_ann=0.4),
            band.Cand("C", score=0.2, slope_ann=0.2),
            band.Cand("D", score=5.0, slope_ann=5.0),
        ]
        band_high = band.take_band(high, slots)
        self.assertEqual(_codes(band_high), ["A", "B", "C"])
        take_high, how_high = band.pick(band_high, slots, "clenow_sort")
        self.assertEqual(how_high, "sorted")
        self.assertEqual(_codes(take_high), ["A"])
        self.assertNotEqual(_codes(take_low), _codes(take_high))

    def test_slots_two_order_changes_inside_same_band(self):
        slots = 2
        self.assertEqual(band.band_k(slots), 4)
        first = band.take_band(
            [
                band.Cand("A", score=0.10),
                band.Cand("B", score=0.50),
                band.Cand("C", score=0.30),
                band.Cand("D", score=0.05),
            ],
            slots,
        )
        second = band.take_band(
            [
                band.Cand("A", score=0.90),
                band.Cand("B", score=0.10),
                band.Cand("C", score=0.20),
                band.Cand("D", score=0.05),
            ],
            slots,
        )
        self.assertEqual(_codes(first), _codes(second))
        take_a, _ = band.pick(first, slots, "clenow_sort")
        take_b, _ = band.pick(second, slots, "clenow_sort")
        self.assertEqual(_codes(take_a), ["B", "C"])
        self.assertEqual(_codes(take_b), ["A", "C"])

    def test_outside_band_cannot_enter(self):
        slots = 1
        names = band.take_band(
            [
                band.Cand("A", score=0.1),
                band.Cand("B", score=0.2),
                band.Cand("C", score=0.3),
                band.Cand("D", score=9.0),
            ],
            slots,
        )
        take, _ = band.pick(names, slots, "clenow_sort")
        self.assertNotIn("D", _codes(take))
        self.assertEqual(_codes(take), ["C"])

    def test_missing_sorts_last_and_can_still_fill(self):
        only = band.take_band([band.Cand("A", score=None)], slots=1)
        take, how = band.pick(only, 1, "clenow_sort")
        self.assertEqual(_codes(take), ["A"])
        self.assertEqual(how, "fallback")
        self.assertEqual(len(take), 1)

    def test_low_score_is_not_dropped(self):
        names = [
            band.Cand("A", score=0.90),
            band.Cand("B", score=0.01),
            band.Cand("C", score=None),
        ]
        take, how = band.pick(names, 2, "clenow_sort")
        self.assertEqual(how, "sorted")
        self.assertEqual(_codes(take), ["A", "B"])
        self.assertEqual(len(take), 2)

    def test_negative_score_ranks_after_positive_and_stays_eligible(self):
        names = [
            band.Cand("A", score=-0.50),
            band.Cand("B", score=0.10),
            band.Cand("C", score=None),
        ]
        take, _ = band.pick(names, 2, "clenow_sort")
        self.assertEqual(_codes(take), ["B", "A"])

    def test_tie_keeps_s20_order(self):
        names = [
            band.Cand("B", score=0.4),
            band.Cand("A", score=0.4),
        ]
        take, _ = band.pick(names, 1, "clenow_sort")
        self.assertEqual(_codes(take), ["B"])

    def test_all_missing_falls_back_to_s20_order(self):
        names = [band.Cand("A", score=None), band.Cand("B", score=None), band.Cand("C", score=None)]
        take, how = band.pick(names, 2, "clenow_sort")
        self.assertEqual(how, "fallback")
        self.assertEqual(_codes(take), ["A", "B"])

    def test_off_mode_ignores_score(self):
        names = [band.Cand("A", score=0.1), band.Cand("B", score=0.9)]
        take, how = band.pick(names, 1, "off")
        self.assertEqual(how, "sorted")
        self.assertEqual(_codes(take), ["A"])

    def test_empty_band_is_not_a_short_fill(self):
        take, how = band.pick([], 3, "clenow_sort")
        self.assertEqual(take, [])
        self.assertEqual(how, "empty")
        take0, how0 = band.pick([band.Cand("A", score=1.0)], 0, "clenow_sort")
        self.assertEqual(take0, [])
        self.assertEqual(how0, "empty")


class FormulaTest(unittest.TestCase):
    def test_straight_line_is_exp_beta_252(self):
        signal = date(2024, 6, 7)
        prices = _line(90, 0.001)
        got = band.clenow_on(_bars(prices, signal), signal, 90)
        self.assertIsNotNone(got)
        target = math.exp(0.001 * 252) - 1.0
        self.assertEqual(got["r2"], 1.0)
        self.assertAlmostEqual(got["slope_ann"], target, delta=1e-12)
        self.assertAlmostEqual(got["score"], target, delta=1e-12)
        koker = (1.0 + 0.001) ** 252 - 1.0
        self.assertGreater(abs(got["slope_ann"] - koker), 1e-4)
        self.assertNotAlmostEqual(got["score"], (1.0 + got["beta"]) ** 252, delta=1e-4)

    def test_signal_day_close_is_ignored(self):
        signal = date(2024, 6, 7)
        prices = _line(90, 0.001)
        clean = band.clenow_on(_bars(prices, signal), signal, 90)
        leaked = _bars(prices, signal) + [(signal, 1e9)]
        dirty = band.clenow_on(leaked, signal, 90)
        self.assertEqual(clean, dirty)

    def test_flat_nonpositive_short_and_stale_are_missing(self):
        signal = date(2024, 6, 7)
        self.assertIsNone(band.clenow_on(_bars([10.0] * 90, signal), signal, 90))
        bad = _line(90, 0.001)
        bad[10] = 0.0
        self.assertIsNone(band.clenow_on(_bars(bad, signal), signal, 90))
        self.assertIsNone(band.clenow_on(_bars(_line(89, 0.001), signal), signal, 90))
        last = signal - timedelta(days=7)
        stale = [(last - timedelta(days=89 - i), math.exp(0.001 * i)) for i in range(90)]
        self.assertIsNone(band.clenow_on(stale, signal, 90))

    def test_cs90r_drops_r2_and_can_flip_the_seat(self):
        smooth = band.ols_clenow(_line(90, 0.0008))
        noisy = band.ols_clenow(_line(90, 0.0015, noise=0.05))
        self.assertGreater(smooth["score"], noisy["score"])
        self.assertGreater(noisy["slope_ann"], smooth["slope_ann"])
        names = [
            band.Cand("S", score=smooth["score"], slope_ann=smooth["slope_ann"]),
            band.Cand("N", score=noisy["score"], slope_ann=noisy["slope_ann"]),
        ]
        by_score, _ = band.pick(names, 1, "clenow_sort")
        by_slope, _ = band.pick(names, 1, "slope_ann_sort")
        self.assertEqual(_codes(by_score), ["S"])
        self.assertEqual(_codes(by_slope), ["N"])

    def test_cs60_window_can_change_the_seat(self):
        signal = date(2024, 6, 7)
        burst = []
        level = 1.0
        for i in range(90):
            level *= math.exp(-0.002 if i < 30 else 0.002)
            burst.append(level)
        steady = _line(90, 0.0008)
        b60 = band.clenow_on(_bars(burst, signal), signal, 60)
        b90 = band.clenow_on(_bars(burst, signal), signal, 90)
        s60 = band.clenow_on(_bars(steady, signal), signal, 60)
        s90 = band.clenow_on(_bars(steady, signal), signal, 90)
        self.assertGreater(b60["score"], s60["score"])
        self.assertLess(b90["score"], s90["score"])
        band60 = [
            band.Cand("S", score=s60["score"]),
            band.Cand("B", score=b60["score"]),
        ]
        band90 = [
            band.Cand("S", score=s90["score"]),
            band.Cand("B", score=b90["score"]),
        ]
        take60, _ = band.pick(band60, 1, "clenow_sort")
        take90, _ = band.pick(band90, 1, "clenow_sort")
        self.assertEqual(_codes(take60), ["B"])
        self.assertEqual(_codes(take90), ["S"])

    def test_no_k_theta_or_accel_on_the_seat_rule(self):
        src = Path(band.__file__).read_text(encoding="utf-8")
        self.assertNotIn("accel", src.lower())
        self.assertNotIn("theta", src.lower())
        self.assertNotIn("* 250", src)
        self.assertNotIn("* 260", src)
        self.assertEqual(band.ANNUALIZATION, 252)
        for name in ("k", "theta", "accel"):
            self.assertNotIn(name, band.pick.__code__.co_varnames)


class SpecLockTest(unittest.TestCase):
    def test_spec_locks_the_four_books(self):
        spec = json.loads((HERE / "SPEC.json").read_text(encoding="utf-8"))
        self.assertEqual([b["id"] for b in spec["books"]], ["F0", "CS90S", "CS60S", "CS90R"])
        self.assertEqual(spec["third_book"]["chosen"], "CS90R")
        rejected = " ".join(spec["third_book"]["rejected"])
        self.assertIn("CS90K2", rejected)
        self.assertIn("CS90S-top", rejected)
        self.assertIn("accel", rejected.lower())
        self.assertFalse(spec["hard_gate"])
        self.assertFalse(spec["replace_sharpe20"])
        self.assertFalse(spec["held_exit_on_key_worse"])
        self.assertFalse(spec["run_backtest_in_this_pr"])
        self.assertEqual(spec["source_sha"], "05f0f8a4f778fde886f3e7b2976646ff4b7d777b")
        design = (HERE / "DESIGN.md").read_text(encoding="utf-8")
        self.assertIn("F0/CS90S/CS60S/CS90R", design)

    def test_run_is_execution_module(self):
        src = (HERE / "run.py").read_text(encoding="utf-8")
        self.assertNotIn("refuse to backtest", src)
        self.assertIn("CLENOW-S20-SECONDARY", src)
        self.assertIn("def main", src)


if __name__ == "__main__":
    suite = unittest.defaultTestLoader.loadTestsFromModule(sys.modules[__name__])
    result = unittest.TextTestRunner(verbosity=2).run(suite)
    sys.exit(0 if result.wasSuccessful() else 1)
