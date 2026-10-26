#!/usr/bin/env python3
"""Pull bond daily TSV chunks via zsmcp query (OFFSET 0,1000,2000,3000).

Intended for Cursor Cloud agents: invoke zsmcp `query` per page and write
`bond_daily/_chunks/{code}_{offset}.tsv`, then run materialize_bond_zsmcp_pull.py.

This module exposes SQL helpers for the agent; shell cannot call zsmcp directly.
"""
from __future__ import annotations

from pathlib import Path

KIT = Path(__file__).resolve().parent.parent
CHUNK_DIR = KIT / "data" / "research_cache" / "bond_daily" / "_chunks"
CODES = ("511010", "511260")
OFFSETS = (0, 1000, 2000, 3000)


def sql_page(code: str, offset: int) -> str:
    return (
        "SELECT DATE(q.TradingDay) AS date, q.ClosePrice AS close "
        "FROM qt_dailyquote q JOIN secumain s ON q.InnerCode=s.InnerCode "
        f"WHERE s.SecuCode='{code}' AND q.TradingDay >= '2019-01-01' "
        f"ORDER BY q.TradingDay LIMIT 1000 OFFSET {offset}"
    )


def write_chunk(code: str, offset: int, tsv_text: str) -> Path:
    CHUNK_DIR.mkdir(parents=True, exist_ok=True)
    dest = CHUNK_DIR / f"{code}_{offset}.tsv"
    dest.write_text(tsv_text if tsv_text.endswith("\n") else tsv_text + "\n", encoding="utf-8")
    return dest


if __name__ == "__main__":
    print("Agent: for each code/offset call zsmcp query with sql_page(); write_chunk();")
    for code in CODES:
        for off in OFFSETS:
            print(f"  {code} OFFSET {off}:\n    {sql_page(code, off)}")
