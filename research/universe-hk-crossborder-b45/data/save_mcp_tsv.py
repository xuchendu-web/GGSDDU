#!/usr/bin/env python3
"""Save raw zsmcp TSV to mcp_pages/{secucode}_{offset}.tsv and print data-row count."""
from __future__ import annotations

import sys
from pathlib import Path

PAGES = Path(__file__).resolve().parent / "mcp_pages"


def save(secucode: str, offset: int, text: str) -> int:
    PAGES.mkdir(parents=True, exist_ok=True)
    path = PAGES / f"{secucode}_{offset}.tsv"
    if not text.endswith("\n") and text:
        text = text + "\n"
    path.write_text(text, encoding="utf-8")
    lines = [ln for ln in text.splitlines() if ln.strip()]
    n = len(lines)
    if n and lines[0].startswith("SecuCode"):
        n -= 1
    return n


def main() -> None:
    if len(sys.argv) < 2:
        print("usage: save_mcp_tsv.py SECUCODE [OFFSET]", file=sys.stderr)
        sys.exit(2)
    code = sys.argv[1]
    offset = int(sys.argv[2]) if len(sys.argv) > 2 else 0
    text = sys.stdin.read()
    n = save(code, offset, text)
    print(n)


if __name__ == "__main__":
    main()
