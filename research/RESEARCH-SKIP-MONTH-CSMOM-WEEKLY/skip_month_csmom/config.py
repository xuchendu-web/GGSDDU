"""Frozen research-only knobs. Do not import strategy_exec / LIVE_OPS."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "data"
RESULTS = ROOT / "results"

KNIFE_ID = "RESEARCH-SKIP-MONTH-CSMOM-WEEKLY"

EVAL_START = "2020-01-03"
EVAL_END = "2026-10-23"
AUM_MIN_YI = 2.0
LOOKBACK_MONTHS = 12
SKIP_MONTHS = 1  # skip t-1; formation ends at t-2
N_SEATS = 5
COST_RT = 0.002
COST_SIDE = 0.001
L_CAP = 1.0
FACE_BOOK = "LIVE1430-B45-S20"
BREADTH_GATE = 0.45


@dataclass(frozen=True)
class CsmomConfig:
    skip_months: int = SKIP_MONTHS
    lookback_months: int = LOOKBACK_MONTHS
    n_seats: int = N_SEATS
    cost_side: float = COST_SIDE
    l_cap: float = L_CAP
    breadth_gate: bool = False

    def label(self) -> str:
        sk = f"s{self.skip_months}" if self.skip_months else "s0"
        br = "+B45br" if self.breadth_gate else ""
        return f"CSMOM-M{self.lookback_months}{sk}-N{self.n_seats}{br}"
