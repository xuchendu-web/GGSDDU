"""Safe text extraction from Markdown and PDF files under a notes root."""

from __future__ import annotations

import re
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path

# Safety limits for PDF ingestion (best-effort text only).
MAX_PDF_BYTES = 25 * 1024 * 1024
MAX_PDF_PAGES = 500
PDF_EXTRACT_TIMEOUT_SEC = 60

INDEX_SUFFIXES = {".md", ".pdf"}
SKIP_DIR_NAMES = {
    "__pycache__",
    ".git",
    "fixtures",
    "_corpus_stub",
    "kb_pipeline",
}
SKIP_FILE_NAMES = {
    "kb_index.sqlite",
    "kb_index.sqlite-journal",
    "kb_index.sqlite-wal",
}


@dataclass(frozen=True)
class ExtractedDocument:
    rel_path: str
    source_type: str
    title: str
    body: str


def extract_title(text: str, fallback: str) -> str:
    for line in text.splitlines():
        stripped = line.strip()
        if stripped.startswith("#"):
            return stripped.lstrip("#").strip() or fallback
    return fallback


def _read_markdown(path: Path) -> str:
    return path.read_text(encoding="utf-8", errors="replace")


def _pdf_header_ok(path: Path) -> bool:
    try:
        with path.open("rb") as fh:
            head = fh.read(8)
        return head.startswith(b"%PDF-")
    except OSError:
        return False


def _extract_pdf_pypdf(path: Path) -> str | None:
    try:
        from pypdf import PdfReader  # type: ignore[import-not-found]
    except ImportError:
        return None

    try:
        reader = PdfReader(str(path))
        if reader.is_encrypted:
            return None
        pages = reader.pages[:MAX_PDF_PAGES]
        parts: list[str] = []
        for page in pages:
            text = page.extract_text() or ""
            if text.strip():
                parts.append(text)
        return "\n\n".join(parts).strip()
    except Exception:
        return None


def _extract_pdf_pdftotext(path: Path) -> str | None:
    import shutil

    binary = shutil.which("pdftotext")
    if not binary:
        return None
    try:
        proc = subprocess.run(
            [binary, "-layout", "-enc", "UTF-8", str(path), "-"],
            capture_output=True,
            timeout=PDF_EXTRACT_TIMEOUT_SEC,
            check=False,
        )
    except (OSError, subprocess.TimeoutExpired):
        return None
    if proc.returncode != 0:
        return None
    return proc.stdout.decode("utf-8", errors="replace").strip()


def extract_pdf_text(path: Path) -> str | None:
    """Return extracted PDF text or None if extraction is unsafe or unavailable."""
    if not path.is_file():
        return None
    size = path.stat().st_size
    if size <= 0 or size > MAX_PDF_BYTES:
        return None
    if not _pdf_header_ok(path):
        return None

    text = _extract_pdf_pypdf(path)
    if text:
        return text
    text = _extract_pdf_pdftotext(path)
    if text:
        return text
    return None


def extract_document_text(
    root: Path,
    path: Path,
    *,
    logical: str | None = None,
) -> ExtractedDocument | None:
    rel = logical if logical is not None else path.relative_to(root).as_posix()
    suffix = path.suffix.lower()

    if suffix == ".md":
        body = _read_markdown(path)
        title = extract_title(body, path.stem)
        return ExtractedDocument(rel_path=rel, source_type="md", title=title, body=body)

    if suffix == ".pdf":
        body = extract_pdf_text(path)
        if body is None:
            print(f"skip pdf (no safe text): {rel}", file=sys.stderr)
            return None
        title = path.stem
        first_line = next((ln.strip() for ln in body.splitlines() if ln.strip()), "")
        if first_line and len(first_line) < 200:
            title = first_line[:200]
        return ExtractedDocument(rel_path=rel, source_type="pdf", title=title, body=body)

    return None


def iter_indexable_files(root: Path) -> list[Path]:
    """Recursively list .md and .pdf files, skipping pipeline and fixture dirs."""
    root = root.resolve()
    files: list[Path] = []
    for path in sorted(root.rglob("*")):
        if not path.is_file():
            continue
        if path.name.startswith("."):
            continue
        if path.name in SKIP_FILE_NAMES:
            continue
        if path.suffix.lower() not in INDEX_SUFFIXES:
            continue
        rel_parts = path.relative_to(root).parts
        if any(part in SKIP_DIR_NAMES for part in rel_parts):
            continue
        files.append(path)
    return files
