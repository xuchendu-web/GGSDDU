#!/usr/bin/env python3
"""Write zsmcp TSV chunk from stdin to bond_daily/_chunks/{code}_{offset}.tsv"""
import sys
from pathlib import Path

KIT = Path(__file__).resolve().parent.parent
OUT = KIT / "data" / "research_cache" / "bond_daily" / "_chunks"


def main() -> None:
    if len(sys.argv) != 3:
        raise SystemExit("usage: _write_chunk.py <code> <offset>")
    code, off = sys.argv[1], sys.argv[2]
    OUT.mkdir(parents=True, exist_ok=True)
    dest = OUT / f"{code}_{off}.tsv"
    dest.write_text(sys.stdin.read(), encoding="utf-8")
    lines = [ln for ln in dest.read_text(encoding="utf-8").splitlines() if ln.strip()]
    print(f"wrote {dest} lines={len(lines)}")


if __name__ == "__main__":
    main()
