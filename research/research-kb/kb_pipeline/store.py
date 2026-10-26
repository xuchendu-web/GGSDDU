"""SQLite schema, ingest, and FTS5 maintenance."""

from __future__ import annotations

import hashlib
import sqlite3
from datetime import datetime, timezone
from pathlib import Path

from .chunking import chunk_text
from .extract import extract_document_text, iter_indexable_files

DEFAULT_DB_NAME = "kb_index.sqlite"
SCHEMA_VERSION = "2"

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
    source_type TEXT NOT NULL DEFAULT 'md',
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

CREATE TABLE IF NOT EXISTS chunks (
    id INTEGER PRIMARY KEY,
    document_id INTEGER NOT NULL,
    chunk_index INTEGER NOT NULL,
    char_start INTEGER NOT NULL,
    char_end INTEGER NOT NULL,
    body TEXT NOT NULL,
    UNIQUE(document_id, chunk_index),
    FOREIGN KEY(document_id) REFERENCES documents(id) ON DELETE CASCADE
);

CREATE VIRTUAL TABLE IF NOT EXISTS chunks_fts USING fts5(
    body,
    content='chunks',
    content_rowid='id',
    tokenize='unicode61 remove_diacritics 2'
);

CREATE TRIGGER IF NOT EXISTS chunks_ai AFTER INSERT ON chunks BEGIN
    INSERT INTO chunks_fts(rowid, body) VALUES (new.id, new.body);
END;

CREATE TRIGGER IF NOT EXISTS chunks_ad AFTER DELETE ON chunks BEGIN
    INSERT INTO chunks_fts(chunks_fts, rowid, body)
        VALUES ('delete', old.id, old.body);
END;

CREATE TRIGGER IF NOT EXISTS chunks_au AFTER UPDATE ON chunks BEGIN
    INSERT INTO chunks_fts(chunks_fts, rowid, body)
        VALUES ('delete', old.id, old.body);
    INSERT INTO chunks_fts(rowid, body) VALUES (new.id, new.body);
END;
"""


def content_hash(body: str) -> str:
    return hashlib.sha256(body.encode("utf-8")).hexdigest()


def _migrate_documents(conn: sqlite3.Connection) -> None:
    cols = {row[1] for row in conn.execute("PRAGMA table_info(documents)")}
    if cols and "source_type" not in cols:
        conn.execute(
            "ALTER TABLE documents ADD COLUMN source_type TEXT NOT NULL DEFAULT 'md'"
        )


def init_db(conn: sqlite3.Connection) -> None:
    conn.executescript(SCHEMA)
    _migrate_documents(conn)
    conn.execute(
        "INSERT INTO meta(key, value) VALUES(?, ?) "
        "ON CONFLICT(key) DO UPDATE SET value = excluded.value",
        ("schema_version", SCHEMA_VERSION),
    )
    conn.commit()


def rebuild_fts(conn: sqlite3.Connection) -> None:
    """Rebuild external-content FTS5 indexes from backing tables."""
    conn.execute("INSERT INTO documents_fts(documents_fts) VALUES('rebuild')")
    conn.execute("INSERT INTO chunks_fts(chunks_fts) VALUES('rebuild')")
    conn.commit()


def _replace_chunks(
    conn: sqlite3.Connection,
    document_id: int,
    body: str,
    *,
    chunk_chars: int,
    chunk_overlap: int,
) -> int:
    conn.execute("DELETE FROM chunks WHERE document_id = ?", (document_id,))
    written = 0
    for idx, (char_start, char_end, piece) in enumerate(
        chunk_text(body, chunk_chars=chunk_chars, overlap=chunk_overlap)
    ):
        conn.execute(
            """
            INSERT INTO chunks (document_id, chunk_index, char_start, char_end, body)
            VALUES (?, ?, ?, ?, ?)
            """,
            (document_id, idx, char_start, char_end, piece),
        )
        written += 1
    return written


def ingest_file(
    conn: sqlite3.Connection,
    root: Path,
    path: Path,
    *,
    force: bool,
    chunk_chars: int,
    chunk_overlap: int,
) -> str:
    extracted = extract_document_text(root, path)
    if extracted is None:
        return "skipped"

    stat = path.stat()
    digest = content_hash(extracted.body)

    row = conn.execute(
        "SELECT id, mtime, content_hash FROM documents WHERE path = ?",
        (extracted.rel_path,),
    ).fetchone()

    if row and not force:
        doc_id, old_mtime, old_hash = row
        if old_mtime == stat.st_mtime and old_hash == digest:
            chunk_n = conn.execute(
                "SELECT COUNT(*) FROM chunks WHERE document_id = ?", (doc_id,)
            ).fetchone()[0]
            if chunk_n:
                return "skipped"
            _replace_chunks(
                conn,
                doc_id,
                extracted.body,
                chunk_chars=chunk_chars,
                chunk_overlap=chunk_overlap,
            )
            return "updated"

    if row:
        doc_id = row[0]
        conn.execute(
            """
            UPDATE documents
            SET title = ?, body = ?, source_type = ?, mtime = ?, size = ?, content_hash = ?
            WHERE id = ?
            """,
            (
                extracted.title,
                extracted.body,
                extracted.source_type,
                stat.st_mtime,
                stat.st_size,
                digest,
                doc_id,
            ),
        )
        _replace_chunks(
            conn,
            doc_id,
            extracted.body,
            chunk_chars=chunk_chars,
            chunk_overlap=chunk_overlap,
        )
        return "updated"

    cur = conn.execute(
        """
        INSERT INTO documents (path, title, body, source_type, mtime, size, content_hash)
        VALUES (?, ?, ?, ?, ?, ?, ?)
        """,
        (
            extracted.rel_path,
            extracted.title,
            extracted.body,
            extracted.source_type,
            stat.st_mtime,
            stat.st_size,
            digest,
        ),
    )
    doc_id = int(cur.lastrowid)
    _replace_chunks(
        conn,
        doc_id,
        extracted.body,
        chunk_chars=chunk_chars,
        chunk_overlap=chunk_overlap,
    )
    return "added"


def run_ingest(
    root: Path,
    db_path: Path,
    *,
    force: bool = False,
    rebuild: bool = False,
    chunk_chars: int = 2400,
    chunk_overlap: int = 200,
) -> dict[str, int]:
    root = root.resolve()
    db_path.parent.mkdir(parents=True, exist_ok=True)

    conn = sqlite3.connect(db_path)
    try:
        init_db(conn)
        counts: dict[str, int] = {
            "added": 0,
            "updated": 0,
            "skipped": 0,
            "removed": 0,
            "chunks": 0,
        }

        seen_paths: set[str] = set()
        for file_path in iter_indexable_files(root):
            rel = file_path.relative_to(root).as_posix()
            seen_paths.add(rel)
            status = ingest_file(
                conn,
                root,
                file_path,
                force=force,
                chunk_chars=chunk_chars,
                chunk_overlap=chunk_overlap,
            )
            counts[status] = counts.get(status, 0) + 1

        stale = conn.execute("SELECT path FROM documents").fetchall()
        for (rel_path,) in stale:
            if rel_path not in seen_paths:
                conn.execute("DELETE FROM documents WHERE path = ?", (rel_path,))
                counts["removed"] += 1

        if rebuild:
            rebuild_fts(conn)

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

        counts["total"] = int(conn.execute("SELECT COUNT(*) FROM documents").fetchone()[0])
        counts["chunks"] = int(conn.execute("SELECT COUNT(*) FROM chunks").fetchone()[0])
        return counts
    finally:
        conn.close()


def fts_rebuild_only(db_path: Path) -> None:
    conn = sqlite3.connect(db_path)
    try:
        init_db(conn)
        rebuild_fts(conn)
    finally:
        conn.close()
