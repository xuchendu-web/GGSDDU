"""Split document bodies into overlapping chunks for FTS5."""

from __future__ import annotations

import re

DEFAULT_CHUNK_CHARS = 2400
DEFAULT_CHUNK_OVERLAP = 200


def _paragraph_spans(text: str) -> list[tuple[int, int]]:
    spans: list[tuple[int, int]] = []
    for match in re.finditer(r"\n\s*\n+", text):
        spans.append((match.start(), match.end()))
    return spans


def chunk_text(
    body: str,
    *,
    chunk_chars: int = DEFAULT_CHUNK_CHARS,
    overlap: int = DEFAULT_CHUNK_OVERLAP,
) -> list[tuple[int, int, str]]:
    """
    Return list of (char_start, char_end, chunk_body).

    Prefers breaking on blank lines; falls back to fixed windows with overlap.
    """
    body = body or ""
    if not body.strip():
        return []

    if len(body) <= chunk_chars:
        return [(0, len(body), body)]

    chunks: list[tuple[int, int, str]] = []
    start = 0
    n = len(body)

    while start < n:
        end = min(start + chunk_chars, n)
        if end < n:
            window = body[start:end]
            break_at = window.rfind("\n\n")
            if break_at > chunk_chars // 3:
                end = start + break_at
        piece = body[start:end].strip()
        if piece:
            chunks.append((start, end, piece))
        if end >= n:
            break
        start = max(end - overlap, start + 1)

    return chunks
