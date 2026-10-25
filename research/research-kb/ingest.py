#!/usr/bin/env python3
"""Walk Markdown notes under a root directory and build/update an SQLite FTS5 index."""

from __future__ import annotations

import argparse
import hashlib
import sqlite3
import sys
from datetime import datetime, timezone
from pathlib import Path

DEFAULT_DB_NAME = "kb_index.sqlite"

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
    content_hash TEXT NOT NULL
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


def init_db(conn: sqlite3.Connection) -> None:
    conn.executescript(SCHEMA)
    conn.commit()


def iter_markdown_files(root: Path) -> list[Path]:
    skip_names = {DEFAULT_DB_NAME, "kb_index.sqlite-journal", "kb_index.sqlite-wal"}
    files: list[Path] = []
    for path in sorted(root.rglob("*.md")):
        if path.name.startswith("."):
            continue
        if path.name in skip_names:
            continue
        if path.is_file():
            files.append(path)
    return files


def ingest_file(conn: sqlite3.Connection, root: Path, path: Path, force: bool) -> str:
    rel = path.relative_to(root).as_posix()
    stat = path.stat()
    body = path.read_text(encoding="utf-8", errors="replace")
    title = extract_title(body, path.stem)
    digest = content_hash(body)

    row = conn.execute(
        "SELECT id, mtime, content_hash FROM documents WHERE path = ?",
        (rel,),
    ).fetchone()

    if row and not force:
        _doc_id, old_mtime, old_hash = row
        if old_mtime == stat.st_mtime and old_hash == digest:
            return "skipped"

    if row:
        conn.execute(
            """
            UPDATE documents
            SET title = ?, body = ?, mtime = ?, size = ?, content_hash = ?
            WHERE path = ?
            """,
            (title, body, stat.st_mtime, stat.st_size, digest, rel),
        )
        return "updated"

    conn.execute(
        """
        INSERT INTO documents (path, title, body, mtime, size, content_hash)
        VALUES (?, ?, ?, ?, ?, ?)
        """,
        (rel, title, body, stat.st_mtime, stat.st_size, digest),
    )
    return "added"


def run_ingest(root: Path, db_path: Path, force: bool) -> dict[str, int]:
    root = root.resolve()
    db_path.parent.mkdir(parents=True, exist_ok=True)

    conn = sqlite3.connect(db_path)
    try:
        init_db(conn)
        counts = {"added": 0, "updated": 0, "skipped": 0, "removed": 0}

        seen_paths: set[str] = set()
        for md_path in iter_markdown_files(root):
            status = ingest_file(conn, root, md_path, force=force)
            counts[status] += 1
            seen_paths.add(md_path.relative_to(root).as_posix())

        stale = conn.execute("SELECT path FROM documents").fetchall()
        for (rel_path,) in stale:
            if rel_path not in seen_paths:
                conn.execute("DELETE FROM documents WHERE path = ?", (rel_path,))
                counts["removed"] += 1

        conn.execute(
            "INSERT INTO meta(key, value) VALUES(?, ?) "
            "ON CONFLICT(key) DO UPDATE SET value = excluded.value",
            ("last_ingest_utc", datetime.now(timezone.utc).isoformat()),
        )
        conn.execute(
            "INSERT INTO meta(key, value) VALUES(?, ?) "
            "ON CONFLICT(key) DO UPDATE SET value = excluded.value",
            ("root", str(root)),
        )
        conn.commit()

        total = conn.execute("SELECT COUNT(*) FROM documents").fetchone()[0]
        counts["total"] = int(total)
        return counts
    finally:
        conn.close()


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Ingest Markdown notes into FTS5 index.")
    parser.add_argument(
        "--root",
        type=Path,
        default=Path(__file__).resolve().parent,
        help="Directory to scan for .md files (default: script directory)",
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
    args = parser.parse_args(argv)

    root = args.root.resolve()
    db_path = (args.db or root / DEFAULT_DB_NAME).resolve()

    if not root.is_dir():
        print(f"error: root not found: {root}", file=sys.stderr)
        return 1

    counts = run_ingest(root, db_path, force=args.force)
    print(
        f"ingest complete: added={counts['added']} updated={counts['updated']} "
        f"skipped={counts['skipped']} removed={counts['removed']} total={counts['total']}"
    )
    print(f"index: {db_path}")
    return 0 if counts["total"] > 0 else 2


if __name__ == "__main__":
    raise SystemExit(main())
