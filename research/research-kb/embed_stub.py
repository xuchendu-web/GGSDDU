#!/usr/bin/env python3
"""Optional embedding hook (stub). Swap implementations without changing ingest/search."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Protocol


@dataclass(frozen=True)
class EmbeddingRecord:
    path: str
    chunk_id: int
    vector: tuple[float, ...]


class Embedder(Protocol):
    def embed_text(self, text: str) -> tuple[float, ...]:
        ...

    def embed_document(self, path: Path, body: str) -> list[EmbeddingRecord]:
        ...


class NoOpEmbedder:
    """Default stub: no vectors stored; semantic search disabled."""

    def embed_text(self, text: str) -> tuple[float, ...]:
        return ()

    def embed_document(self, path: Path, body: str) -> list[EmbeddingRecord]:
        return []


def get_embedder(name: str = "noop") -> Embedder:
    if name in ("noop", "none", ""):
        return NoOpEmbedder()
    raise ValueError(f"unknown embedder: {name!r} (only 'noop' is available)")


def index_embeddings(_db_path: Path, _root: Path, embedder: Embedder | None = None) -> int:
    """Placeholder for a future vector sidecar. Returns number of vectors written."""
    _ = embedder or get_embedder()
    return 0
