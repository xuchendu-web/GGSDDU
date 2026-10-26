"""Frozen research-only knobs. Do not import LIVE_OPS / strategy_exec."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT.parent / "dual_momentum_weekly" / "data"
RESULTS = ROOT / "results"

EVAL_START = "2020-01-03"
EVAL_END = "2026-10-23"
AUM_MIN_YI = 2.0
ABS_LOOKBACK = 52
ABS_SKIP = 1
REL_LOOKBACK = 26
REL_SKIP = 1
N_SEATS = 5
COST_RT = 0.002
COST_SIDE = 0.001
ABS_THRESHOLD = 0.0
L_CAP = 1.0
FACE_BOOK = "LIVE1430-B45-S20"


@dataclass(frozen=True)
class DualTfConfig:
    abs_lookback: int = ABS_LOOKBACK
    abs_skip: int = ABS_SKIP
    rel_lookback: int = REL_LOOKBACK
    rel_skip: int = REL_SKIP
    n_seats: int = N_SEATS
    abs_threshold: float = ABS_THRESHOLD
    cost_side: float = COST_SIDE
    l_cap: float = L_CAP
    apply_absolute: bool = True
    name: str = ""

    def label(self) -> str:
        if self.name:
            return self.name
        gate = f"A{self.abs_lookback}s{self.abs_skip}" if self.apply_absolute else "XS"
        return f"DT-{gate}-R{self.rel_lookback}s{self.rel_skip}-N{self.n_seats}"
