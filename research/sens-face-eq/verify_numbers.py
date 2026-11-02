#!/usr/bin/env python3
"""Pin T-1 Face EQ to PR#50 published numbers. Research-only check."""
from __future__ import annotations

from pathlib import Path

import pandas as pd

OUT = Path(__file__).resolve().parent / "out"


def main() -> None:
    table = pd.read_csv(OUT / "table.csv").set_index("book")
    t1 = table.loc["FACE-EQ-T1"]
    # PR#50 LIVE1430-EQ-S20
    assert abs(float(t1["ret"]) - 1.5828517647807212) < 1e-12, t1["ret"]
    assert abs(float(t1["maxDD"]) + 0.1586573855560559) < 1e-12, t1["maxDD"]
    assert abs(float(t1["Calmar"]) - 0.9433195032091667) < 1e-12, t1["Calmar"]
    prov = pd.read_csv(OUT / "provenance_pr50_face_eq_t1.csv", index_col=0)
    eq = pd.read_csv(OUT / "equity.csv", index_col=0)
    assert abs(float(prov.iloc[-1, 0]) - float(eq["FACE-EQ-T1"].iloc[-1])) < 1e-12
    ag = pd.read_csv(OUT / "ag40s_equity.csv", index_col=0)
    # PR#106 AG40S last NAV → 235.6% from 1.0
    assert abs(float(ag["AG40S-max5"].iloc[-1]) - 3.355820058517372) < 1e-9
    print("verify_ok T-1 Face EQ 158.3%/-15.9%/C0.94 ; AG40S last NAV 3.3558")


if __name__ == "__main__":
    main()
