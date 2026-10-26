#!/usr/bin/env python3
"""Reject a grid that re-opens a one-axis single or adds an interpolated level."""

from __future__ import annotations

import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
ALLOWED_R = {None, 40, 80}
ALLOWED_B = {0.45, 0.50}
ALLOWED_TV = {0.25, 0.33}
FACE = {"R": None, "B": 0.45, "TV": 0.25}
BANNED_ONE_AXIS = (
    {"R": 40, "B": 0.45, "TV": 0.25},
    {"R": 60, "B": 0.45, "TV": 0.25},
    {"R": 80, "B": 0.45, "TV": 0.25},
    {"R": None, "B": 0.40, "TV": 0.25},
    {"R": None, "B": 0.50, "TV": 0.25},
    {"R": None, "B": 0.55, "TV": 0.25},
    {"R": None, "B": 0.45, "TV": 0.20},
    {"R": None, "B": 0.45, "TV": 0.22},
    {"R": None, "B": 0.45, "TV": 0.28},
    {"R": None, "B": 0.45, "TV": 0.30},
    {"R": None, "B": 0.45, "TV": 0.33},
)


def _key(cell: dict) -> tuple:
    return (cell["R"], round(float(cell["B"]), 2), round(float(cell["TV"]), 2))


def _axes_off_face(cell: dict) -> int:
    n = 0
    if cell["R"] != FACE["R"]:
        n += 1
    if round(float(cell["B"]), 2) != FACE["B"]:
        n += 1
    if round(float(cell["TV"]), 2) != FACE["TV"]:
        n += 1
    return n


def validate(doc: dict) -> None:
    levels = doc["levels"]
    if levels["R"] != [None, 40, 80]:
        raise SystemExit("levels.R drifted")
    if [round(float(x), 2) for x in levels["B"]] != [0.45, 0.50]:
        raise SystemExit("levels.B drifted")
    if [round(float(x), 2) for x in levels["TV"]] != [0.25, 0.33]:
        raise SystemExit("levels.TV drifted")
    face = doc["face"]
    if face["R"] is not None or round(float(face["B"]), 2) != 0.45 or round(float(face["TV"]), 2) != 0.25:
        raise SystemExit("face drifted")
    cells = doc["cells"]
    if not 1 <= len(cells) <= 9:
        raise SystemExit(f"grid size {len(cells)} outside 1..9")
    ids = [c["id"] for c in cells]
    if len(ids) != len(set(ids)):
        raise SystemExit("duplicate id")
    if ids[0] != "F0":
        raise SystemExit("F0 must be the first cell")
    books = [c["book"] for c in cells]
    if len(books) != len(set(books)):
        raise SystemExit("duplicate book")
    seen = set()
    for c in cells:
        if c["R"] not in ALLOWED_R or round(float(c["B"]), 2) not in ALLOWED_B:
            raise SystemExit(f"{c['id']} level not in the frozen set")
        if round(float(c["TV"]), 2) not in ALLOWED_TV:
            raise SystemExit(f"{c['id']} TV level not in the frozen set")
        key = _key(c)
        if key in seen:
            raise SystemExit(f"duplicate coordinate {c['id']}")
        seen.add(key)
        off = _axes_off_face(c)
        if c["id"] == "F0":
            if off != 0:
                raise SystemExit("F0 moved off the face")
        elif off < 2:
            raise SystemExit(f"{c['id']} changes {off} axis; closed singles stay closed")
    banned = {(b["R"], round(float(b["B"]), 2), round(float(b["TV"]), 2)) for b in BANNED_ONE_AXIS}
    hit = seen & banned
    if hit:
        raise SystemExit(f"banned single in grid: {hit}")


def main() -> None:
    doc = json.loads((HERE / "cells.json").read_text(encoding="utf-8"))
    validate(doc)
    print(f"grid ok: {len(doc['cells'])} cells")


if __name__ == "__main__":
    main()
