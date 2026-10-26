#!/usr/bin/env python3
"""Merge zsmcp OFFSET chunks from bond_daily/_chunks into bond_daily/*.csv."""
from __future__ import annotations

import csv
import sys
from pathlib import Path

KIT = Path(__file__).resolve().parent.parent
CHUNK_DIR = KIT / "data" / "research_cache" / "bond_daily" / "_chunks"
OUT_DIR = KIT / "data" / "research_cache" / "bond_daily"
CODES = ("511010", "511260")


def parse_chunk(path: Path) -> list[tuple[str, float]]:
    lines = path.read_text(encoding="utf-8").strip().splitlines()
    if not lines:
        return []
    start = 1 if lines[0].lower().startswith("date") else 0
    rows: list[tuple[str, float]] = []
    for line in lines[start:]:
        if not line.strip():
            continue
        parts = line.split("\t") if "\t" in line else line.split(",")
        if len(parts) < 2:
            continue
        rows.append((parts[0].strip()[:10], float(parts[1])))
    return rows


def merge_code(code: str) -> tuple[str, str, int]:
    rows: list[tuple[str, float]] = []
    for off in (0, 1000, 2000, 3000):
        fp = CHUNK_DIR / f"{code}_{off}.tsv"
        if not fp.exists():
            continue
        rows.extend(parse_chunk(fp))
    rows = sorted(set(rows), key=lambda x: x[0])
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    dest = OUT_DIR / f"{code}.csv"
    with dest.open("w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["date", "close"])
        w.writerows(rows)
    if not rows:
        raise SystemExit(f"no rows for {code}; populate {CHUNK_DIR}/{code}_*.tsv via zsmcp query")
    return rows[0][0], rows[-1][0], len(rows)


def main() -> None:
    for code in CODES:
        first, last, n = merge_code(code)
        print(f"{code}: n={n} first={first} last={last}", flush=True)
        if first > "2019-11-01":
            raise SystemExit(f"{code}: first date {first} > 2019-11-01")


if __name__ == "__main__":
    main()
