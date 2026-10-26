#!/usr/bin/env python3
"""Walk notes under a root directory and build/update an SQLite FTS5 index."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from kb_pipeline.store import DEFAULT_DB_NAME, run_ingest


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Ingest Markdown/PDF notes into FTS5 index (wrapper; see cli.py ingest)."
    )
    parser.add_argument(
        "--root",
        type=Path,
        default=Path(__file__).resolve().parent,
        help="Directory to scan recursively for .md and .pdf",
    )
    parser.add_argument(
        "--db",
        type=Path,
        default=None,
        help=f"SQLite database path (default: <root>/{DEFAULT_DB_NAME})",
    )
    parser.add_argument(
        "--force",
        action="store_true",
        help="Re-index all files even if mtime/hash unchanged",
    )
    parser.add_argument(
        "--rebuild-fts",
        action="store_true",
        help="Run FTS5 rebuild after ingest",
    )
    parser.add_argument("--chunk-chars", type=int, default=2400)
    parser.add_argument("--chunk-overlap", type=int, default=200)
    args = parser.parse_args(argv)

    root = args.root.resolve()
    db_path = (args.db or root / DEFAULT_DB_NAME).resolve()

    if not root.is_dir():
        print(f"error: root not found: {root}", file=sys.stderr)
        return 1

    counts = run_ingest(
        root,
        db_path,
        force=args.force,
        rebuild=args.rebuild_fts,
        chunk_chars=args.chunk_chars,
        chunk_overlap=args.chunk_overlap,
    )
    print(
        f"ingest complete: added={counts['added']} updated={counts['updated']} "
        f"skipped={counts['skipped']} removed={counts['removed']} total={counts['total']} "
        f"chunks={counts['chunks']}"
    )
    print(f"index: {db_path}")
    return 0 if counts["total"] > 0 else 2


if __name__ == "__main__":
    raise SystemExit(main())
