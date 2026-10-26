#!/usr/bin/env python3
"""Generate a large stub corpus for ingest smoke tests (no research content)."""

from __future__ import annotations

import argparse
from pathlib import Path

# Fixed token so FTS smoke queries stay deterministic.
STUB_TOKEN = "CORPUS_STUB_TOKEN_X9"


def write_stub_tree(out_dir: Path, count: int, nested: int) -> int:
    out_dir.mkdir(parents=True, exist_ok=True)
    written = 0
    for i in range(count):
        sub = out_dir / f"batch-{i % nested:02d}"
        sub.mkdir(parents=True, exist_ok=True)
        path = sub / f"stub-{i:05d}.md"
        path.write_text(
            f"# stub-{i:05d}\n\n{STUB_TOKEN} index={i}\n\n"
            f"placeholder paragraph repeat {i % 17}\n",
            encoding="utf-8",
        )
        written += 1
    return written


def main() -> int:
    parser = argparse.ArgumentParser(description="Generate stub markdown corpus for ingest smoke")
    parser.add_argument(
        "--out",
        type=Path,
        default=Path(__file__).resolve().parent.parent / "_corpus_stub",
        help="Output directory (default: research/research-kb/_corpus_stub)",
    )
    parser.add_argument("--count", type=int, default=400, help="Number of stub .md files")
    parser.add_argument("--nested", type=int, default=8, help="Number of subfolders")
    args = parser.parse_args()

    n = write_stub_tree(args.out.resolve(), args.count, max(1, args.nested))
    print(f"wrote {n} stub files under {args.out}")
    print(f"query token: {STUB_TOKEN}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
