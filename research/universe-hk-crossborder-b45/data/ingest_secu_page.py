#!/usr/bin/env python3
"""Ingest one zsmcp page: append SecuCode,d,c and advance offset."""
from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

from secu_fetch_lib import MIN_ROWS_TARGET, PAGE, count_rows_in_csv, load_progress, save_progress

DATA = Path(__file__).resolve().parent


def parse_rows(raw: str) -> list[str]:
    lines: list[str] = []
    for line in raw.splitlines():
        line = line.strip()
        if not line or line.startswith("(") or line.startswith("SecuCode"):
            continue
        parts = line.split("\t")
        if len(parts) >= 3:
            lines.append("\t".join(parts[:3]))
    return lines


def main() -> None:
    job = json.loads(sys.argv[1])
    raw = Path(sys.argv[2]).read_text(encoding="utf-8") if len(sys.argv) > 2 else sys.stdin.read()
    rows = parse_rows(raw)
    tsv = "\n".join(rows) + ("\n" if rows else "")
    if tsv.strip():
        subprocess.run(
            [sys.executable, str(DATA / "append_secu_tsv.py")],
            input=tsv,
            text=True,
            check=True,
        )
    code = job["secucode"]
    prog = load_progress()
    st = prog["codes"].setdefault(code, {"offset": 0, "done": False, "source": job.get("source", "nav")})
    total_after = count_rows_in_csv().get(code, 0)
    if total_after >= MIN_ROWS_TARGET or len(rows) < PAGE:
        st["done"] = True
    else:
        st["offset"] = int(job.get("offset", 0)) + PAGE
    st["source"] = job.get("source", st.get("source", "nav"))
    save_progress(prog)
    print(json.dumps({"secucode": code, "appended": len(rows), "done": st["done"]}))


if __name__ == "__main__":
    main()
