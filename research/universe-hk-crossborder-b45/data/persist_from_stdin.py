#!/usr/bin/env python3
"""Persist exact stdin TSV to mcp_pages/{code}_{offset}.tsv and print row count."""
from __future__ import annotations
import sys
from pathlib import Path

PAGES = Path("/workspace/research/universe-hk-crossborder-b45/data/mcp_pages")


def main() -> None:
    if len(sys.argv) < 2:
        print("usage: persist_from_stdin.py SECUCODE [OFFSET]", file=sys.stderr)
        sys.exit(2)
    code = sys.argv[1]
    offset = int(sys.argv[2]) if len(sys.argv) > 2 else 0
    text = sys.stdin.read()
    if text and not text.endswith("\n"):
        text += "\n"
    PAGES.mkdir(parents=True, exist_ok=True)
    path = PAGES / f"{code}_{offset}.tsv"
    path.write_text(text, encoding="utf-8")
    lines = [ln for ln in text.splitlines() if ln.strip()]
    n = len(lines)
    if n and lines[0].startswith("SecuCode"):
        n -= 1
    print(f"{path.name}\t{n}")


if __name__ == "__main__":
    main()
