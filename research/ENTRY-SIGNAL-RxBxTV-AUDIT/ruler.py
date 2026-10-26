#!/usr/bin/env python3
"""Strict 记正 / 证伪 ruler for ENTRY-SIGNAL R×B×TV.

Compares already-computed returns. No market data and no backtest loop.
Equality on the cover test passes. There is no 0.9 haircut and no 2pp slack.
"""

from __future__ import annotations

from typing import Any, Mapping

EPS = 1e-12


def _f(x: Any) -> float:
    v = float(x)
    if v != v:  # NaN
        raise ValueError("NaN is not a pass")
    return v


def covers(ret: float, max_dd: float, face_ret: float, face_max_dd: float) -> bool:
    """Δret >= Δ|MDD|, both in return units (not pre-rounded percentage points)."""
    delta_ret = _f(ret) - _f(face_ret)
    delta_abs_mdd = abs(_f(max_dd)) - abs(_f(face_max_dd))
    return delta_ret + EPS >= delta_abs_mdd


def window_ok(ret: float, face_ret: float) -> bool:
    return _f(ret) + EPS >= _f(face_ret)


def verdict(cell: Mapping[str, Any], face: Mapping[str, Any]) -> str:
    """Return 记正 or 证伪. Window returns are cumulative stats_full on each slice."""
    try:
        full = covers(cell["ret"], cell["maxDD"], face["ret"], face["maxDD"])
        y2020 = window_ok(cell["w2020_22"]["ret"], face["w2020_22"]["ret"])
        y2023 = window_ok(cell["w2023_26"]["ret"], face["w2023_26"]["ret"])
    except (KeyError, TypeError, ValueError):
        return "证伪"
    if full and y2020 and y2023:
        return "记正"
    return "证伪"


# Published rounded prints. These lock the comparator; they are not this cross.
# B50 vs B45: SPIKE-S20-BTHETA-GRID report. Old rear test ignored 2020–22.
_B45 = {
    "ret": 1.316,
    "maxDD": -0.188,
    "w2020_22": {"ret": 0.189},
    "w2023_26": {"ret": 0.948},
}
_B50 = {
    "ret": 1.492,
    "maxDD": -0.155,
    "w2020_22": {"ret": 0.177},
    "w2023_26": {"ret": 1.118},
}
# R40/R80 vs R60: SPIKE-S20-ENTRY-MOM-LB report. Old code used 0.9 × 2023–26.
_R60 = {
    "ret": 1.340,
    "maxDD": -0.201,
    "w2020_22": {"ret": 0.224},
    "w2023_26": {"ret": 0.912},
}
_R40 = {
    "ret": 1.420,
    "maxDD": -0.157,
    "w2020_22": {"ret": 0.300},
    "w2023_26": {"ret": 0.862},
}
_R80 = {
    "ret": 1.523,
    "maxDD": -0.181,
    "w2020_22": {"ret": 0.302},
    "w2023_26": {"ret": 0.937},
}


def _check_fixtures() -> None:
    assert verdict(_B50, _B45) == "证伪"
    assert covers(_B50["ret"], _B50["maxDD"], _B45["ret"], _B45["maxDD"])
    assert window_ok(_B50["w2023_26"]["ret"], _B45["w2023_26"]["ret"])
    assert not window_ok(_B50["w2020_22"]["ret"], _B45["w2020_22"]["ret"])

    assert verdict(_R40, _R60) == "证伪"
    assert not window_ok(_R40["w2023_26"]["ret"], _R60["w2023_26"]["ret"])
    # The retired haircut would have called this window acceptable.
    assert _R40["w2023_26"]["ret"] >= _R60["w2023_26"]["ret"] * 0.9

    assert verdict(_R80, _R60) == "记正"

    tied = {
        "ret": 1.0,
        "maxDD": -0.10,
        "w2020_22": {"ret": 0.2},
        "w2023_26": {"ret": 0.3},
    }
    assert verdict(tied, tied) == "记正"

    short = dict(tied)
    short["ret"] = 1.0 + (0.01 - 1e-6)
    short["maxDD"] = -0.11
    assert verdict(short, tied) == "证伪"


if __name__ == "__main__":
    _check_fixtures()
    print("ruler fixtures ok")
