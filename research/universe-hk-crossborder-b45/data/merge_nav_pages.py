#!/usr/bin/env python3
"""Merge data/mcp_pages/*.tsv into nav_long.csv. Dedup by (SecuCode, d). Never invent rows."""
from __future__ import annotations

import csv
import json
import re
from pathlib import Path

DATA = Path(__file__).resolve().parent
PAGES = DATA / "mcp_pages"
NAV = DATA / "nav_long.csv"
CODE_RE = re.compile(r"^(\d{6})_")


def parse_page(path: Path) -> list[tuple[str, str, str]]:
    name_code = None
    m = CODE_RE.match(path.name)
    if m:
        name_code = m.group(1)
    rows: list[tuple[str, str, str]] = []
    text = path.read_text(encoding="utf-8")
    for line in text.splitlines():
        line = line.strip()
        if not line or line.startswith("(") or line.startswith("SecuCode") or line.startswith("d\t"):
            continue
        parts = [p.strip() for p in line.replace(",", "\t").split("\t") if p.strip()]
        if len(parts) == 2 and name_code:
            d, c = parts
            code = name_code
        elif len(parts) >= 3:
            code, d, c = parts[0], parts[1], parts[2]
            if not re.fullmatch(r"\d{6}", code) and name_code:
                code, d, c = name_code, parts[0], parts[1]
        else:
            continue
        d = d[:10]
        if not re.fullmatch(r"\d{4}-\d{2}-\d{2}", d):
            continue
        try:
            float(c)
        except ValueError:
            continue
        if not re.fullmatch(r"\d{6}", code):
            continue
        rows.append((code, d, c))
    return rows


def main() -> None:
    seen: dict[tuple[str, str], str] = {}
    files = sorted(PAGES.glob("*.tsv")) if PAGES.exists() else []
    if NAV.exists() and NAV.stat().st_size > 0:
        with NAV.open(newline="", encoding="utf-8") as f:
            for row in csv.DictReader(f):
                code, d, c = row["SecuCode"].strip(), row["d"].strip()[:10], row["c"].strip()
                if code and d:
                    seen[(code, d)] = c
    for path in files:
        for code, d, c in parse_page(path):
            seen[(code, d)] = c
    tmp = NAV.with_suffix(".csv.tmp")
    with tmp.open("w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["SecuCode", "d", "c"])
        for code, d in sorted(seen):
            w.writerow([code, d, seen[(code, d)]])
    tmp.replace(NAV)
    counts: dict[str, int] = {}
    for code, _d in seen:
        counts[code] = counts.get(code, 0) + 1
    hk = json.loads((DATA / "universe_hk.json").read_text(encoding="utf-8"))["secucodes"]
    full = json.loads((DATA / "universe_full.json").read_text(encoding="utf-8"))["secucodes"]
    status = {
        "rows": len(seen),
        "codes": len(counts),
        "hk_ge200": sum(1 for c in hk if counts.get(c, 0) >= 200),
        "hk_total": len(hk),
        "full_ge200": sum(1 for c in full if counts.get(c, 0) >= 200),
        "full_total": len(full),
        "pages": len(files),
    }
    print(json.dumps(status, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
