#!/usr/bin/env python3
"""Append SecuCode,d,c TSV body to nav_long.csv."""
import csv
import sys
from pathlib import Path

NAV = Path(__file__).resolve().parent / "nav_long.csv"


def main() -> None:
    tsv = sys.stdin.read()
    write_header = not NAV.exists() or NAV.stat().st_size == 0
    n = 0
    with NAV.open("a", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        if write_header:
            w.writerow(["SecuCode", "d", "c"])
        for line in tsv.strip().splitlines():
            if not line.strip() or line.startswith("SecuCode"):
                continue
            parts = line.split("\t")
            if len(parts) < 3:
                continue
            w.writerow(parts[:3])
            n += 1
    print("appended", n)


if __name__ == "__main__":
    main()
