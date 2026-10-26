#!/usr/bin/env python3
"""Load research panel (daily P + weekly grid G) for TSMOM knives."""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
MF_ENGINE = ROOT / "cloud_batch" / "MF-HOLD-BGRID" / "engine"
sys.path.insert(0, str(MF_ENGINE))

from panel_build import PANEL_PKL, build_panel  # noqa: E402

START = "2020-01-03"
END = "2026-10-16"


def load_panel(force: bool = False):
    if force or not PANEL_PKL.exists():
        build_panel(force=True)
    import pandas as pd

    raw = pd.read_pickle(PANEL_PKL)
    P, W, G = raw["P"], raw["W"], pd.DatetimeIndex(raw["G"])
    codes = list(raw["codes"])
    gi = {g: i for i, g in enumerate(G)}
    reb = [g for g in G if g >= pd.Timestamp(START) and g <= pd.Timestamp(END)][:-1]
    return dict(P=P, W=W, G=G, codes=codes, gi=gi, reb=reb)
