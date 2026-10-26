"""Frozen research-only knobs. Do not import LIVE_OPS / strategy_exec."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "data"
RESULTS = ROOT / "results"

EVAL_START = "2020-01-03"
EVAL_END = "2026-10-23"
AUM_MIN_YI = 2.0
LOOKBACK = 52
SKIP = 1
N_SEATS = 5
COST_RT = 0.002
COST_SIDE = 0.001
ABS_THRESHOLD = 0.0
L_CAP = 1.0
FACE_BOOK = "LIVE1430-B45-S20"


@dataclass(frozen=True)
class DualMomConfig:
    lookback: int = LOOKBACK
    skip: int = SKIP
    n_seats: int = N_SEATS
    abs_threshold: float = ABS_THRESHOLD
    cost_side: float = COST_SIDE
    l_cap: float = L_CAP
    apply_absolute: bool = True
    name: str = "DM-L52s1-N5"

    def label(self) -> str:
        gate = "ABS" if self.apply_absolute else "XS"
        return f"{gate}-L{self.lookback}s{self.skip}-N{self.n_seats}"
