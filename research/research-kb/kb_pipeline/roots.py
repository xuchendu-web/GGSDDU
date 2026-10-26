"""Resolve ingest roots: repo research/ anchor and optional external paths."""

from __future__ import annotations

import os
from pathlib import Path

DEFAULT_PATHS_FILE = "ingest_roots.local.txt"
SKIP_DIR_NAMES = {".git", "__pycache__", ".venv", "node_modules"}
SKIP_FILE_NAMES = {"kb_index.sqlite", "kb_index.sqlite-journal", "kb_index.sqlite-wal"}


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
    return script_dir.resolve() / "kb_index.sqlite"


def logical_path(prefix: str, rel_to_root: Path) -> str:
    rel = rel_to_root.as_posix()
    if prefix:
        return f"{prefix}/{rel}" if rel != "." else prefix
    return rel


def parse_paths_file(path: Path, *, repo_root: Path | None) -> list[tuple[str, Path]]:
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
            continue
        prefix = label or p.name
        roots.append((prefix, p))
    return roots


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


def collect_ingest_targets(
    anchor: Path,
    extra_roots: list[tuple[str, Path]],
    *,
    scan_anchor: bool,
) -> list[tuple[str, Path]]:
    targets: list[tuple[str, Path]] = []
    if scan_anchor:
        targets.append(("", anchor.resolve()))
    for prefix, root in extra_roots:
        targets.append((prefix, root.resolve()))
    return targets
