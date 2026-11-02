#!/usr/bin/env python3
"""Audit data_v1016 refresh artifacts. Fail on invented 930950 2026-10-30."""
from __future__ import annotations

import csv
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "out"
TARGET = "2026-10-30"
PRIOR = "2026-10-23"
BM_LAST = "2026-10-29"


def _dates(path: Path, col: str) -> list[str]:
    with path.open() as f:
        return [r[col] for r in csv.DictReader(f)]


def main() -> int:
    errors: list[str] = []
    listing = json.loads((OUT / "listing_436.json").read_text())
    if len(listing) != 436:
        errors.append(f"listing size {len(listing)} != 436")

    cal = json.loads((OUT / "calendar_expected.json").read_text())
    if cal["target_complete_session"] != TARGET:
        errors.append("calendar target mismatch")
    if "2026-10-01" in cal["oct_2026_complete_sessions_from_000985"]:
        errors.append("invented National Day session")

    d985 = _dates(OUT / "000985_csi.csv", "tradingday")
    if d985[-1] != TARGET:
        errors.append(f"000985 last {d985[-1]} != {TARGET}")
    if "2026-11-02" in d985:
        errors.append("000985 must not include in-progress 2026-11-02 as complete")

    d950 = _dates(OUT / "bm_930950.csv", "tradingday")
    if TARGET in d950:
        errors.append("invented 930950 2026-10-30 — CSI table had no bar")
    if d950[-1] != BM_LAST:
        errors.append(f"930950 last {d950[-1]} != {BM_LAST}")

    panel = list(csv.DictReader((OUT / "panel_core_tail.csv").open()))
    by_code: dict[str, list[str]] = {}
    for r in panel:
        by_code.setdefault(r["secucode"], []).append(r["tradingday"])
    for code, days in by_code.items():
        if days[-1] != TARGET:
            errors.append(f"panel {code} last {days[-1]}")
        if PRIOR in days:
            errors.append(f"panel tail should start after {PRIOR}: {code}")

    p510 = [r for r in panel if r["secucode"] == "510300"]
    close_1023_cache = 4.178  # CLOUD-BATCH day/510300.json last bar
    # tail starts 10-26; 10-23 stays in old cache
    if p510[-1]["close"] != "4.065":
        errors.append(f"510300 10-30 close {p510[-1]['close']} != 4.065")

    champ = list(csv.DictReader((OUT / "champ_equity_asof_20261023.csv").open()))
    if champ[-1][""] != PRIOR and list(champ[-1].values())[0] != PRIOR:
        last = champ[-1].get("") or list(champ[-1].values())[0]
        if last != PRIOR:
            errors.append(f"champ last {last} != {PRIOR}")

    fri = OUT / "fri_1430_20261030.csv"
    if not fri.exists():
        errors.append("missing fri_1430_20261030.csv — run tencent_fri1430.py")
    else:
        frows = list(csv.DictReader(fri.open()))
        hit = next((r for r in frows if r["etf_code"] == "510300"), None)
        if not hit or hit.get("status") != "ok":
            errors.append("510300 Friday 14:30 not ok")
        elif not hit.get("price_1430"):
            errors.append("510300 Friday 14:30 empty price")

    status = json.loads((OUT / "status.json").read_text())
    if status["bm_930950"]["color"] != "YELLOW":
        errors.append("930950 must stay YELLOW while 10-30 is absent")
    if status["forbidden_sources_used"]:
        errors.append("forbidden sources marked used")

    print("listing", len(listing))
    print("000985", d985[0], "->", d985[-1], "n", len(d985))
    print("930950", d950[0], "->", d950[-1], "n", len(d950))
    print("panel_core codes", sorted(by_code))
    print("cache_510300_20261023", close_1023_cache, "(not rewritten)")
    if errors:
        print("FAIL")
        for e in errors:
            print(" -", e)
        return 1
    print("PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
