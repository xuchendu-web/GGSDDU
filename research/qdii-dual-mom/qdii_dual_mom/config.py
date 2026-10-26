"""Frozen research-only knobs — overseas QDII sleeve, no LIVE / B45 gate."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "data"
RESULTS = ROOT / "results"

EVAL_START = "2020-01-03"
EVAL_END = "2026-10-23"
AUM_MIN_YI = 2.0
R12_LOOKBACK = 12
R12_SKIP = 0
MA_MAIN = 20
MA_NEIGHBOR = 10
N_SEATS_MAIN = 3
N_SEATS_TABLE = 5
COST_RT = 0.002
COST_SIDE = COST_RT / 2.0
L_CAP = 1.0
MIN_UNIV = 8

FACE_BOOK = "OX-EW-BH"
MAIN_BOOK = "QDII-DM-MA20-K3"


@dataclass(frozen=True)
class QdiiDmConfig:
    ma_weeks: int = MA_MAIN
    r12_lookback: int = R12_LOOKBACK
    r12_skip: int = R12_SKIP
    n_seats: int = N_SEATS_MAIN
    apply_ma: bool = True
    apply_r12_abs: bool = True
    cost_side: float = COST_SIDE
    l_cap: float = L_CAP
    name: str = MAIN_BOOK

    def label(self) -> str:
        parts = ["QDII-DM"]
        if self.apply_ma:
            parts.append(f"MA{self.ma_weeks}")
        else:
            parts.append("noMA")
        if not self.apply_r12_abs:
            parts.append("noR12")
        parts.append(f"K{self.n_seats}")
        return "-".join(parts) if self.name == MAIN_BOOK else self.name
