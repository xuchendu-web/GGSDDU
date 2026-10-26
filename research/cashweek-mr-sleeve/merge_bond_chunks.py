#!/usr/bin/env python3
"""Merge zsmcp TSV chunks into kit bond_daily/*.csv (no drift)."""
from __future__ import annotations

import csv
import sys
from pathlib import Path

KIT = Path(__file__).resolve().parent.parent / "cloud_batch" / "CLOUD-BATCH-2026-10-26"
OUT = KIT / "data" / "research_cache" / "bond_daily"


def merge(code: str, chunk_paths: list[Path]) -> None:
    rows: list[tuple[str, float]] = []
    for fp in chunk_paths:
        lines = fp.read_text(encoding="utf-8").strip().splitlines()
        if not lines:
            continue
        start = 1 if lines[0].lower().startswith("date") else 0
        for line in lines[start:]:
            parts = line.split("\t") if "\t" in line else line.split(",")
            if len(parts) < 2:
                continue
            d, c = parts[0].strip()[:10], float(parts[1])
            rows.append((d, c))
    rows = sorted(set(rows), key=lambda x: x[0])
    OUT.mkdir(parents=True, exist_ok=True)
    dest = OUT / f"{code}.csv"
    with dest.open("w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["date", "close"])
        w.writerows(rows)
    print(f"wrote {dest} n={len(rows)} first={rows[0][0]} last={rows[-1][0]}")


if __name__ == "__main__":
    code = sys.argv[1]
    paths = [Path(p) for p in sys.argv[2:]]
    merge(code, paths)
