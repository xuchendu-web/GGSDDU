#!/usr/bin/env python3
"""CLI for research notes KB: ingest, FTS rebuild."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from kb_pipeline.chunking import DEFAULT_CHUNK_CHARS, DEFAULT_CHUNK_OVERLAP
from kb_pipeline.roots import (
    DEFAULT_PATHS_FILE,
    collect_ingest_targets,
    default_anchor,
    default_db_location,
    find_repo_root,
    parse_extra_root_arg,
    parse_paths_file,
)
from kb_pipeline.store import DEFAULT_DB_NAME, fts_rebuild_only, run_ingest


def _resolve_targets(args: argparse.Namespace, script_dir: Path) -> list[tuple[str, Path]]:
    repo_root = find_repo_root(script_dir)
    anchor = (args.anchor or args.root or default_anchor(script_dir)).resolve()
    extra: list[tuple[str, Path]] = []
    paths_files: list[Path] = []
    if args.paths_file:
        paths_files.append(args.paths_file.resolve())
    local_paths = script_dir / DEFAULT_PATHS_FILE
    if local_paths.is_file():
        paths_files.append(local_paths)
    for pf in paths_files:
        extra.extend(parse_paths_file(pf, repo_root=repo_root))
    for raw in args.extra_root:
        label, p = parse_extra_root_arg(raw, repo_root)
        if not p.is_dir():
            raise FileNotFoundError(p)
        extra.append((label, p))
    return collect_ingest_targets(anchor, extra, scan_anchor=not args.no_anchor_scan)


def cmd_ingest(args: argparse.Namespace) -> int:
    script_dir = Path(__file__).resolve().parent
    db_path = (args.db or default_db_location(script_dir)).resolve()
    try:
        targets = _resolve_targets(args, script_dir)
    except FileNotFoundError as exc:
        print(f"error: extra root not found: {exc}", file=sys.stderr)
        return 1
    if not targets:
        print("error: nothing to ingest", file=sys.stderr)
        return 1

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
        f"skipped={counts['skipped']} removed={counts['removed']} "
        f"documents={counts['total']} chunks={counts['chunks']}"
    )
    print(f"index: {db_path}")
    return 0 if counts["total"] > 0 else 2


def cmd_rebuild_fts(args: argparse.Namespace) -> int:
    script_dir = Path(__file__).resolve().parent
    db_path = (args.db or default_db_location(script_dir)).resolve()
    if not db_path.is_file():
        print(f"error: index not found at {db_path}", file=sys.stderr)
        return 1
    fts_rebuild_only(db_path)
    print(f"fts rebuild complete: {db_path}")
    return 0


def build_parser() -> argparse.ArgumentParser:
    script_dir = Path(__file__).resolve().parent
    parser = argparse.ArgumentParser(description="Research notes knowledge base CLI")
    sub = parser.add_subparsers(dest="command", required=True)

    common = argparse.ArgumentParser(add_help=False)
    common.add_argument("--anchor", type=Path, default=None)
    common.add_argument("--root", type=Path, default=None)
    common.add_argument("--no-anchor-scan", action="store_true")
    common.add_argument("--extra-root", action="append", default=[])
    common.add_argument("--paths-file", type=Path, default=None)
    common.add_argument("--db", type=Path, default=None)

    ingest_p = sub.add_parser("ingest", parents=[common], help="Scan notes and update index")
    ingest_p.add_argument("--force", action="store_true")
    ingest_p.add_argument("--rebuild-fts", action="store_true")
    ingest_p.add_argument("--chunk-chars", type=int, default=DEFAULT_CHUNK_CHARS)
    ingest_p.add_argument("--chunk-overlap", type=int, default=DEFAULT_CHUNK_OVERLAP)
    ingest_p.set_defaults(func=cmd_ingest)

    rebuild_p = sub.add_parser("rebuild-fts", parents=[common], help="Rebuild FTS5 indexes")
    rebuild_p.set_defaults(func=cmd_rebuild_fts)

    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    return int(args.func(args))


if __name__ == "__main__":
    raise SystemExit(main())
