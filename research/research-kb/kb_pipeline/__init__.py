"""Research notes KB ingest pipeline (extract → chunk → SQLite FTS5)."""

from .chunking import chunk_text
from .extract import extract_document_text, iter_indexable_files
from .store import DEFAULT_DB_NAME, fts_rebuild_only, init_db, rebuild_fts, run_ingest

__all__ = [
    "DEFAULT_DB_NAME",
    "chunk_text",
    "extract_document_text",
    "fts_rebuild_only",
    "init_db",
    "iter_indexable_files",
    "rebuild_fts",
    "run_ingest",
]
