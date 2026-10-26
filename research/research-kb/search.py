#!/usr/bin/env python3
"""CLI full-text search over the research knowledge base (SQLite FTS5)."""

from __future__ import annotations

import argparse
import json
import re
import sqlite3
import sys
from pathlib import Path

from ingest import DEFAULT_DB_NAME

SNIPPET_MARKERS = ("<b>", "</b>", "...")


def escape_fts_query(raw: str) -> str:
    """Turn user input into a safe FTS5 AND query over tokens."""
    tokens = re.findall(r'"[^"]+"|\S+', raw.strip())
    if not tokens:
        return ""
    parts: list[str] = []
    for tok in tokens:
        if tok.startswith('"') and tok.endswith('"'):
            inner = tok[1:-1].replace('"', '""')
            parts.append(f'"{inner}"')
        else:
            cleaned = re.sub(r'[^\w\-\*]', '', tok, flags=re.UNICODE)
            if cleaned:
                parts.append(cleaned)
    return " AND ".join(parts)


def search(
    db_path: Path,
    query: str,
    *,
    limit: int = 10,
    json_out: bool = False,
    mode: str = "chunks",
) -> list[dict]:
    fts_q = escape_fts_query(query)
    if not fts_q:
        return []

    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    try:
        if mode == "documents":
            sql = """
            SELECT
                d.path,
                d.title,
                bm25(documents_fts) AS score,
                snippet(documents_fts, 1, ?, ?, ?, 64) AS snippet,
                NULL AS chunk_index
            FROM documents_fts
            JOIN documents d ON d.id = documents_fts.rowid
            WHERE documents_fts MATCH ?
            ORDER BY score
            LIMIT ?
            """
        else:
            sql = """
            SELECT
                d.path,
                d.title,
                bm25(chunks_fts) AS score,
                snippet(chunks_fts, 0, ?, ?, ?, 64) AS snippet,
                c.chunk_index AS chunk_index
            FROM chunks_fts
            JOIN chunks c ON c.id = chunks_fts.rowid
            JOIN documents d ON d.id = c.document_id
            WHERE chunks_fts MATCH ?
            ORDER BY score
            LIMIT ?
            """
        rows = conn.execute(
            sql,
            (*SNIPPET_MARKERS, fts_q, limit),
        ).fetchall()
        hits = [
            {
                "path": row["path"],
                "title": row["title"],
                "score": float(row["score"]),
                "snippet": row["snippet"],
                "chunk_index": row["chunk_index"],
            }
            for row in rows
        ]
        return hits
    finally:
        conn.close()


def format_text_hits(hits: list[dict], root: Path) -> str:
    if not hits:
        return "No matches."
    lines: list[str] = []
    for i, hit in enumerate(hits, start=1):
        abs_path = (root / hit["path"]).resolve()
        snippet = hit["snippet"].replace("<b>", "**").replace("</b>", "**")
        lines.append(f"{i}. {hit['path']}")
        lines.append(f"   title: {hit['title']}")
        lines.append(f"   score: {hit['score']:.4f}")
        if hit.get("chunk_index") is not None:
            lines.append(f"   chunk: {hit['chunk_index']}")
        lines.append(f"   snippet: {snippet}")
        lines.append(f"   cite: {abs_path}")
        lines.append("")
    return "\n".join(lines).rstrip()


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Search indexed Markdown notes.")
    parser.add_argument("query", nargs="+", help="Search terms (AND by default; use quotes for phrases)")
    parser.add_argument(
        "--root",
        type=Path,
        default=Path(__file__).resolve().parent,
        help="Notes root (for citation paths)",
    )
    parser.add_argument(
        "--db",
        type=Path,
        default=None,
        help=f"SQLite database (default: <root>/{DEFAULT_DB_NAME})",
    )
    parser.add_argument("--limit", type=int, default=10, help="Max hits (default: 10)")
    parser.add_argument(
        "--mode",
        choices=("chunks", "documents"),
        default="chunks",
        help="Search chunked FTS (default) or whole-document FTS",
    )
    parser.add_argument("--json", action="store_true", help="Emit JSON lines")
    args = parser.parse_args(argv)

    root = args.root.resolve()
    db_path = (args.db or root / DEFAULT_DB_NAME).resolve()
    query = " ".join(args.query)

    if not db_path.is_file():
        print(f"error: index not found at {db_path}; run ingest.py first", file=sys.stderr)
        return 1

    hits = search(db_path, query, limit=args.limit, json_out=args.json, mode=args.mode)
    if args.json:
        for hit in hits:
            hit_out = {**hit, "cite": str((root / hit["path"]).resolve())}
            print(json.dumps(hit_out, ensure_ascii=False))
    else:
        print(format_text_hits(hits, root))
    return 0 if hits else 2


if __name__ == "__main__":
    raise SystemExit(main())
