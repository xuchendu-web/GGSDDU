#!/usr/bin/env python3
"""Rebuild listings.json from inner_cat8.json (SecuCategory=8 only)."""
from __future__ import annotations

import json
from pathlib import Path

DATA = Path(__file__).resolve().parent


def main() -> None:
    cat8 = json.loads((DATA / "inner_cat8.json").read_text(encoding="utf-8"))
    hk = json.loads((DATA / "universe_hk.json").read_text(encoding="utf-8"))["secucodes"]
    full = json.loads((DATA / "universe_full.json").read_text(encoding="utf-8"))["secucodes"]
    union = sorted(set(hk) | set(full))
    by = cat8["by_code"]
    listings = {
        "inner_by_code": {c: int(by[c]["inner"]) for c in union},
        "listed_date": {c: by[c]["listed"] for c in union},
        "listed_by_code": {c: by[c]["listed"] for c in union},
        "source": cat8.get("source"),
        "asof": cat8.get("asof"),
    }
    (DATA / "listings.json").write_text(json.dumps(listings, ensure_ascii=False, indent=2), encoding="utf-8")
    print("codes", len(listings["inner_by_code"]))


if __name__ == "__main__":
    main()
