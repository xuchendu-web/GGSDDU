#!/usr/bin/env python3
"""Create a clean, self-contained distribution ZIP from the installed tree."""
import argparse
from pathlib import Path
from zipfile import ZIP_DEFLATED, ZipFile

root = Path(__file__).resolve().parents[1]
parser = argparse.ArgumentParser(description="Create a clean skill ZIP")
parser.add_argument("-o", "--output", help="output ZIP path")
args = parser.parse_args()
out = Path(args.output) if args.output else root.parent / "cj-industry-quadrant-monitor.zip"
skip = {".venv", ".cache", "test-output", "__pycache__", ".iqm-runtime.json", ".iqm-runtime.ps1", "assets"}
suffix_skip = {".pyc", ".html", ".xlsx", ".pdf", ".log", ".zip"}
with ZipFile(out, "w", ZIP_DEFLATED) as z:
    for p in root.rglob("*"):
        if not p.is_file() or any(x in skip for x in p.relative_to(root).parts) or p.suffix.lower() in suffix_skip:
            continue
        z.write(p, Path(root.name) / p.relative_to(root))
print(out)
