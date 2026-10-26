#!/usr/bin/env python3
"""Write bond ETF daily closes into research_cache/bond_daily/ (zsmcp qt_dailyquote).

Run inside Cursor Cloud (zsmcp MCP available to the agent). This script is invoked
by SPIKE-S20-CASH-BOND-SLEEVE-LIVE1430/run.py when CSVs are missing.
"""
from __future__ import annotations

import csv
import json
import sys
from pathlib import Path

KIT = Path(__file__).resolve().parent.parent
OUT_DIR = KIT / "data" / "research_cache" / "bond_daily"

# InnerCode from secumain (zsmcp)
BONDS = {
    "511010": 22195,
    "511260": 135270,
}

CHUNKS = [
    ("2019-12-01", "2023-01-01"),
    ("2023-01-01", "2025-01-01"),
    ("2025-01-01", "2026-11-01"),
]


def write_csv(code: str, rows: list[tuple[str, float]]) -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    fp = OUT_DIR / f"{code}.csv"
    with fp.open("w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["date", "close"])
        for d, c in sorted(rows, key=lambda x: x[0]):
            w.writerow([d, c])
    print(f"wrote {fp} n={len(rows)}", flush=True)


def fetch_via_mcp() -> dict[str, list[tuple[str, float]]]:
    """Placeholder: agent should populate bond_daily/*.csv via zsmcp query chunks."""
    raise SystemExit(
        "bond_daily CSV missing. Agent: run zsmcp query per CHUNKS in materialize_bond_daily.py "
        "and write bond_daily/{code}.csv, or copy from sina_daily after fetch."
    )


def load_existing() -> bool:
    ok = all((OUT_DIR / f"{c}.csv").exists() for c in BONDS)
    return ok


def merge_sina_fallback() -> None:
    sina = KIT / "data" / "research_cache" / "sina_daily"
    for code in BONDS:
        src = sina / f"{code}.csv"
        dst = OUT_DIR / f"{code}.csv"
        if dst.exists() or not src.exists():
            continue
        dst.parent.mkdir(parents=True, exist_ok=True)
        dst.write_bytes(src.read_bytes())
        print(f"copied sina -> {dst}", flush=True)


if __name__ == "__main__":
    merge_sina_fallback()
    if load_existing():
        print("bond_daily OK", flush=True)
        sys.exit(0)
    fetch_via_mcp()
