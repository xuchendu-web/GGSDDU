#!/usr/bin/env python3
"""Walk Markdown/PDF notes under configured roots and build/update an SQLite FTS5 index."""

from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

from kb_pipeline.roots import (
    DEFAULT_PATHS_FILE,
    collect_ingest_targets,
    default_anchor,
    default_db_location,
    find_repo_root,
    parse_extra_root_arg,
    parse_paths_file,
)
from kb_pipeline.store import DEFAULT_DB_NAME, run_ingest


def main(argv: list[str] | None = None) -> int:
    script_dir = Path(__file__).resolve().parent
    repo_root = find_repo_root(script_dir)

    parser = argparse.ArgumentParser(description="Ingest Markdown/PDF notes into FTS5 index.")
    parser.add_argument(
        "--anchor",
        type=Path,
        default=None,
        help="Scan *.md / *.pdf under this directory (default: <repo>/research if present)",
    )
    parser.add_argument(
        "--root",
        type=Path,
        default=None,
        help="Alias for --anchor (legacy single-root flag)",
    )
    parser.add_argument(
        "--no-anchor-scan",
        action="store_true",
        help="Do not scan --anchor; only use --extra-root / --paths-file entries",
    )
    parser.add_argument(
        "--extra-root",
        action="append",
        default=[],
        metavar="LABEL:PATH",
        help="Additional directory to index (repeatable)",
    )
    parser.add_argument(
        "--paths-file",
        type=Path,
        default=None,
        help=f"Optional file listing extra roots (also reads {DEFAULT_PATHS_FILE} if present)",
    )
    parser.add_argument(
        "--db",
        type=Path,
        default=None,
        help=f"SQLite database path (default: {DEFAULT_DB_NAME} beside scripts)",
    )
    parser.add_argument("--force", action="store_true", help="Re-index all files")
    parser.add_argument(
        "--rebuild-fts",
        action="store_true",
        help="Run FTS5 rebuild after ingest",
    )
    parser.add_argument("--chunk-chars", type=int, default=2400)
    parser.add_argument("--chunk-overlap", type=int, default=200)
    args = parser.parse_args(argv)

    anchor = (args.anchor or args.root or default_anchor(script_dir)).resolve()
    db_path = (args.db or default_db_location(script_dir)).resolve()

    extra: list[tuple[str, Path]] = []
    paths_files: list[Path] = []
    if args.paths_file:
        paths_files.append(args.paths_file.resolve())
    local_paths = script_dir / DEFAULT_PATHS_FILE
    if local_paths.is_file():
        paths_files.append(local_paths)

    for pf in paths_files:
        for prefix, p in parse_paths_file(pf, repo_root=repo_root):
            extra.append((prefix, p))

    for raw in args.extra_root:
        try:
            label, p = parse_extra_root_arg(raw, repo_root)
        except Exception as exc:  # noqa: BLE001
            print(f"error: bad --extra-root {raw!r}: {exc}", file=sys.stderr)
            return 1
        if not p.is_dir():
            print(f"error: extra root not found: {p}", file=sys.stderr)
            return 1
        extra.append((label, p))

    scan_anchor = not args.no_anchor_scan
    if not scan_anchor and not extra:
        print("error: nothing to ingest (use --anchor scan or --extra-root)", file=sys.stderr)
        return 1

    targets = collect_ingest_targets(anchor, extra, scan_anchor=scan_anchor)

    counts = run_ingest(
        targets,
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
    if scan_anchor:
        print(f"anchor: {anchor}")
    if extra:
        print(f"extra roots: {len(extra)}")
    return 0 if counts["total"] > 0 else 2


if __name__ == "__main__":
    raise SystemExit(main())
