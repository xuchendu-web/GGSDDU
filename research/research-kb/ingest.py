#!/usr/bin/env python3
"""Walk Markdown notes under configured roots and build/update an SQLite FTS5 index."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import sqlite3
import sys
from datetime import datetime, timezone
from pathlib import Path

DEFAULT_DB_NAME = "kb_index.sqlite"
DEFAULT_PATHS_FILE = "ingest_roots.local.txt"
SKIP_DIR_NAMES = {".git", "__pycache__", ".venv", "node_modules"}
SKIP_FILE_NAMES = {DEFAULT_DB_NAME, "kb_index.sqlite-journal", "kb_index.sqlite-wal"}

SCHEMA = """
CREATE TABLE IF NOT EXISTS meta (
    key TEXT PRIMARY KEY,
    value TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS documents (
    id INTEGER PRIMARY KEY,
    path TEXT NOT NULL UNIQUE,
    title TEXT NOT NULL,
    body TEXT NOT NULL,
    mtime REAL NOT NULL,
    size INTEGER NOT NULL,
    content_hash TEXT NOT NULL,
    source_root TEXT NOT NULL DEFAULT ''
);

CREATE VIRTUAL TABLE IF NOT EXISTS documents_fts USING fts5(
    title,
    body,
    content='documents',
    content_rowid='id',
    tokenize='unicode61 remove_diacritics 2'
);

CREATE TRIGGER IF NOT EXISTS documents_ai AFTER INSERT ON documents BEGIN
    INSERT INTO documents_fts(rowid, title, body) VALUES (new.id, new.title, new.body);
END;

CREATE TRIGGER IF NOT EXISTS documents_ad AFTER DELETE ON documents BEGIN
    INSERT INTO documents_fts(documents_fts, rowid, title, body)
        VALUES ('delete', old.id, old.title, old.body);
END;

CREATE TRIGGER IF NOT EXISTS documents_au AFTER UPDATE ON documents BEGIN
    INSERT INTO documents_fts(documents_fts, rowid, title, body)
        VALUES ('delete', old.id, old.title, old.body);
    INSERT INTO documents_fts(rowid, title, body) VALUES (new.id, new.title, new.body);
END;
"""


def extract_title(text: str, fallback: str) -> str:
    for line in text.splitlines():
        stripped = line.strip()
        if stripped.startswith("#"):
            return stripped.lstrip("#").strip() or fallback
    return fallback


def content_hash(body: str) -> str:
    return hashlib.sha256(body.encode("utf-8")).hexdigest()


def find_repo_root(start: Path) -> Path | None:
    cur = start.resolve()
    for _ in range(12):
        if (cur / ".git").is_dir():
            return cur
        if cur.parent == cur:
            break
        cur = cur.parent
    return None


def default_anchor(script_dir: Path) -> Path:
    repo = find_repo_root(script_dir)
    if repo is not None:
        research = repo / "research"
        if research.is_dir():
            return research.resolve()
    return script_dir.resolve()


def default_db_location(script_dir: Path) -> Path:
    return script_dir.resolve() / DEFAULT_DB_NAME


def migrate_schema(conn: sqlite3.Connection) -> None:
    cols = {row[1] for row in conn.execute("PRAGMA table_info(documents)")}
    if "source_root" not in cols:
        conn.execute("ALTER TABLE documents ADD COLUMN source_root TEXT NOT NULL DEFAULT ''")
        conn.commit()


def init_db(conn: sqlite3.Connection) -> None:
    conn.executescript(SCHEMA)
    migrate_schema(conn)
    conn.commit()


def should_skip_path(path: Path) -> bool:
    if path.name.startswith("."):
        return True
    if path.name in SKIP_FILE_NAMES:
        return True
    for part in path.parts:
        if part in SKIP_DIR_NAMES:
            return True
    return False


def iter_markdown_under(root: Path) -> list[Path]:
    files: list[Path] = []
    root = root.resolve()
    for path in sorted(root.rglob("*.md")):
        if not path.is_file():
            continue
        if should_skip_path(path):
            continue
        try:
            path.relative_to(root)
        except ValueError:
            continue
        files.append(path)
    return files


def parse_paths_file(
    path: Path,
    *,
    repo_root: Path | None,
) -> list[tuple[str, Path]]:
    """Return (logical_prefix, absolute_root) pairs from a paths file."""
    roots: list[tuple[str, Path]] = []
    if not path.is_file():
        return roots
    for raw in path.read_text(encoding="utf-8", errors="replace").splitlines():
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        label = ""
        spec = line
        if "|" in line:
            label, spec = line.split("|", 1)
            label, spec = label.strip(), spec.strip()
        elif ":" in line:
            left, right = line.split(":", 1)
            right = right.strip()
            if right.startswith(("/", "~")) or "\\" in right:
                label, spec = left.strip(), right
        spec = os.path.expanduser(spec.strip())
        p = Path(spec)
        if not p.is_absolute() and repo_root is not None:
            p = (repo_root / p).resolve()
        else:
            p = p.resolve()
        if not p.is_dir():
            print(f"warning: skip missing ingest root: {line} -> {p}", file=sys.stderr)
            continue
        prefix = label or p.name
        roots.append((prefix, p))
    return roots


def collect_ingest_targets(
    anchor: Path,
    extra_roots: list[tuple[str, Path]],
    *,
    scan_anchor: bool,
) -> list[tuple[str, Path]]:
    """Each entry: (path_prefix, source_root). Empty prefix => paths relative to anchor only."""
    targets: list[tuple[str, Path]] = []
    if scan_anchor:
        targets.append(("", anchor.resolve()))
    for prefix, root in extra_roots:
        targets.append((prefix, root.resolve()))
    return targets


def logical_path(prefix: str, rel_to_root: Path) -> str:
    rel = rel_to_root.as_posix()
    if prefix:
        return f"{prefix}/{rel}" if rel != "." else prefix
    return rel


def ingest_file(
    conn: sqlite3.Connection,
    source_root: Path,
    logical: str,
    path: Path,
    force: bool,
) -> str:
    stat = path.stat()
    body = path.read_text(encoding="utf-8", errors="replace")
    title = extract_title(body, path.stem)
    digest = content_hash(body)
    root_s = str(source_root.resolve())

    row = conn.execute(
        "SELECT id, mtime, content_hash FROM documents WHERE path = ?",
        (logical,),
    ).fetchone()

    if row and not force:
        _doc_id, old_mtime, old_hash = row
        if old_mtime == stat.st_mtime and old_hash == digest:
            return "skipped"

    if row:
        conn.execute(
            """
            UPDATE documents
            SET title = ?, body = ?, mtime = ?, size = ?, content_hash = ?, source_root = ?
            WHERE path = ?
            """,
            (title, body, stat.st_mtime, stat.st_size, digest, root_s, logical),
        )
        return "updated"

    conn.execute(
        """
        INSERT INTO documents (path, title, body, mtime, size, content_hash, source_root)
        VALUES (?, ?, ?, ?, ?, ?, ?)
        """,
        (logical, title, body, stat.st_mtime, stat.st_size, digest, root_s),
    )
    return "added"


def run_ingest(
    targets: list[tuple[str, Path]],
    db_path: Path,
    force: bool,
) -> dict[str, int]:
    db_path.parent.mkdir(parents=True, exist_ok=True)

    conn = sqlite3.connect(db_path)
    try:
        init_db(conn)
        counts = {"added": 0, "updated": 0, "skipped": 0, "removed": 0}

        seen_paths: set[str] = set()
        for prefix, source_root in targets:
            for md_path in iter_markdown_under(source_root):
                rel = md_path.relative_to(source_root)
                logical = logical_path(prefix, rel)
                status = ingest_file(conn, source_root, logical, md_path, force=force)
                counts[status] += 1
                seen_paths.add(logical)

        stale = conn.execute("SELECT path FROM documents").fetchall()
        for (rel_path,) in stale:
            if rel_path not in seen_paths:
                conn.execute("DELETE FROM documents WHERE path = ?", (rel_path,))
                counts["removed"] += 1

        roots_meta = [
            {"prefix": prefix, "root": str(root)} for prefix, root in targets
        ]
        conn.execute(
            "INSERT INTO meta(key, value) VALUES(?, ?) "
            "ON CONFLICT(key) DO UPDATE SET value = excluded.value",
            ("last_ingest_utc", datetime.now(timezone.utc).isoformat()),
        )
        conn.execute(
            "INSERT INTO meta(key, value) VALUES(?, ?) "
            "ON CONFLICT(key) DO UPDATE SET value = excluded.value",
            ("ingest_roots", json.dumps(roots_meta, ensure_ascii=False)),
        )
        conn.commit()

        total = conn.execute("SELECT COUNT(*) FROM documents").fetchone()[0]
        counts["total"] = int(total)
        return counts
    finally:
        conn.close()


def parse_extra_root_arg(raw: str, repo_root: Path | None) -> tuple[str, Path]:
    if ":" in raw:
        label, spec = raw.split(":", 1)
        label = label.strip()
        spec = spec.strip()
    else:
        spec = raw.strip()
        label = ""
    spec = os.path.expanduser(spec)
    p = Path(spec)
    if not p.is_absolute() and repo_root is not None:
        p = (repo_root / p).resolve()
    else:
        p = p.resolve()
    if not label:
        label = p.name
    return label, p


def main(argv: list[str] | None = None) -> int:
    script_dir = Path(__file__).resolve().parent
    repo_root = find_repo_root(script_dir)

    parser = argparse.ArgumentParser(description="Ingest Markdown notes into FTS5 index.")
    parser.add_argument(
        "--anchor",
        type=Path,
        default=None,
        help="Scan all *.md under this directory (default: <repo>/research if present, else script dir)",
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
        help="Additional directory to index (repeatable). PATH may be absolute or repo-relative.",
    )
    parser.add_argument(
        "--paths-file",
        type=Path,
        default=None,
        help=f"Optional file listing extra roots (default: also reads {DEFAULT_PATHS_FILE} if present)",
    )
    parser.add_argument(
        "--db",
        type=Path,
        default=None,
        help=f"SQLite database path (default: {script_dir.name}/{DEFAULT_DB_NAME})",
    )
    parser.add_argument(
        "--force",
        action="store_true",
        help="Re-index all files even if mtime/hash unchanged",
    )
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
        extra.extend(parse_paths_file(pf, repo_root=repo_root))

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

    counts = run_ingest(targets, db_path, force=args.force)
    print(
        f"ingest complete: added={counts['added']} updated={counts['updated']} "
        f"skipped={counts['skipped']} removed={counts['removed']} total={counts['total']}"
    )
    print(f"index: {db_path}")
    if scan_anchor:
        print(f"anchor: {anchor}")
    if extra:
        print(f"extra roots: {len(extra)}")
    return 0 if counts["total"] > 0 else 2


if __name__ == "__main__":
    raise SystemExit(main())
