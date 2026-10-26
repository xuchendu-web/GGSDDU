#!/usr/bin/env python3
"""CLI for research notes KB: ingest, FTS rebuild, and search."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from kb_pipeline.chunking import DEFAULT_CHUNK_CHARS, DEFAULT_CHUNK_OVERLAP
from kb_pipeline.store import DEFAULT_DB_NAME, fts_rebuild_only, run_ingest


def cmd_ingest(args: argparse.Namespace) -> int:
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
        f"skipped={counts['skipped']} removed={counts['removed']} "
        f"documents={counts['total']} chunks={counts['chunks']}"
    )
    print(f"index: {db_path}")
    return 0 if counts["total"] > 0 else 2


def cmd_rebuild_fts(args: argparse.Namespace) -> int:
    root = args.root.resolve()
    db_path = (args.db or root / DEFAULT_DB_NAME).resolve()
    if not db_path.is_file():
        print(f"error: index not found at {db_path}", file=sys.stderr)
        return 1
    fts_rebuild_only(db_path)
    print(f"fts rebuild complete: {db_path}")
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Research notes knowledge base CLI")
    sub = parser.add_subparsers(dest="command", required=True)

    ingest_p = sub.add_parser("ingest", help="Scan notes tree and update SQLite FTS index")
    ingest_p.add_argument(
        "--root",
        type=Path,
        default=Path(__file__).resolve().parent,
        help="Directory to scan recursively for .md / .pdf",
    )
    ingest_p.add_argument("--db", type=Path, default=None, help="SQLite database path")
    ingest_p.add_argument("--force", action="store_true", help="Re-index all files")
    ingest_p.add_argument(
        "--rebuild-fts",
        action="store_true",
        help="After ingest, run FTS5 rebuild on documents_fts and chunks_fts",
    )
    ingest_p.add_argument(
        "--chunk-chars",
        type=int,
        default=DEFAULT_CHUNK_CHARS,
        help="Target chunk size in characters",
    )
    ingest_p.add_argument(
        "--chunk-overlap",
        type=int,
        default=DEFAULT_CHUNK_OVERLAP,
        help="Chunk overlap in characters",
    )
    ingest_p.set_defaults(func=cmd_ingest)

    rebuild_p = sub.add_parser("rebuild-fts", help="Rebuild FTS5 indexes from backing tables")
    rebuild_p.add_argument("--root", type=Path, default=Path(__file__).resolve().parent)
    rebuild_p.add_argument("--db", type=Path, default=None)
    rebuild_p.set_defaults(func=cmd_rebuild_fts)

    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    return int(args.func(args))


if __name__ == "__main__":
    raise SystemExit(main())
