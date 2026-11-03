#!/usr/bin/env python3
"""Report NAV coverage from mcp_pages/*.tsv + nav_long.csv. Never invent rows."""
from __future__ import annotations

import csv
import json
import re
from collections import Counter
from pathlib import Path

from merge_nav_pages import parse_page

DATA = Path(__file__).resolve().parent
NAV = DATA / "nav_long.csv"
PAGES = DATA / "mcp_pages"
CODE_RE = re.compile(r"^(\d{6})_")
MIN_ROWS = 200


def counts() -> dict[str, int]:
    seen: dict[tuple[str, str], str] = {}
    if NAV.exists() and NAV.stat().st_size:
        with NAV.open(newline="", encoding="utf-8") as f:
            for row in csv.DictReader(f):
                code = row.get("SecuCode", "").strip()
                d = (row.get("d") or "")[:10]
                if code and d:
                    seen[(code, d)] = row.get("c", "")
    if PAGES.exists():
        for path in PAGES.glob("*.tsv"):
            for code, d, _v in parse_page(path):
                seen[(code, d)] = _v
    c: Counter[str] = Counter()
    for code, _d in seen:
        c[code] += 1
    return dict(c)


def main() -> None:
    hk = json.loads((DATA / "universe_hk.json").read_text(encoding="utf-8"))["secucodes"]
    full = json.loads((DATA / "universe_full.json").read_text(encoding="utf-8"))["secucodes"]
    cnt = counts()
    hk_ok = [x for x in hk if cnt.get(x, 0) >= MIN_ROWS]
    full_ok = [x for x in full if cnt.get(x, 0) >= MIN_ROWS]
    hk_short = {x: cnt.get(x, 0) for x in hk if cnt.get(x, 0) < MIN_ROWS}
    pages = list(PAGES.glob("*.tsv")) if PAGES.exists() else []
    out = {
        "rows_approx": sum(cnt.values()),
        "codes_with_any": len(cnt),
        "pages": len(pages),
        "hk_ge200": len(hk_ok),
        "hk_total": len(hk),
        "hk_ratio": round(len(hk_ok) / max(1, len(hk)), 4),
        "full_ge200": len(full_ok),
        "full_total": len(full),
        "full_ratio": round(len(full_ok) / max(1, len(full)), 4),
        "ready": len(hk_ok) / max(1, len(hk)) >= 0.85 and len(full_ok) / max(1, len(full)) >= 0.7,
        "hk_short": hk_short,
    }
    print(json.dumps(out, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
