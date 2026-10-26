#!/usr/bin/env python3
"""Shared state for per-SecuCode NAV/quote cache build."""
from __future__ import annotations

import csv
import json
from pathlib import Path
from typing import Any

DATA = Path(__file__).resolve().parent
NAV = DATA / "nav_long.csv"
META = DATA / "secu_nav_meta.json"
PROGRESS = DATA / "secu_fetch_progress.json"
DATE_START, DATE_END = "2019-11-01", "2026-10-23"
PAGE = 1000
MIN_ROWS_TARGET = 200
CODES_TARGET = 220


def load_universe() -> tuple[list[str], list[str]]:
    hk = json.loads((DATA / "universe_hk.json").read_text(encoding="utf-8"))["secucodes"]
    full = json.loads((DATA / "universe_full.json").read_text(encoding="utf-8"))["secucodes"]
    return hk, full


def load_meta() -> dict[str, Any]:
    if META.exists():
        return json.loads(META.read_text(encoding="utf-8"))
    return {"by_code": {}}


def save_meta(meta: dict[str, Any]) -> None:
    META.write_text(json.dumps(meta, ensure_ascii=False, indent=2), encoding="utf-8")


def load_progress() -> dict[str, Any]:
    if PROGRESS.exists():
        return json.loads(PROGRESS.read_text(encoding="utf-8"))
    return {"codes": {}}


def save_progress(prog: dict[str, Any]) -> None:
    PROGRESS.write_text(json.dumps(prog, ensure_ascii=False, indent=2), encoding="utf-8")


def count_rows_in_csv() -> dict[str, int]:
    counts: dict[str, int] = {}
    if not NAV.exists() or NAV.stat().st_size == 0:
        return counts
    with NAV.open(newline="", encoding="utf-8") as f:
        for row in csv.DictReader(f):
            c = row["SecuCode"].strip()
            counts[c] = counts.get(c, 0) + 1
    return counts


def codes_meeting_min(counts: dict[str, int], min_rows: int = MIN_ROWS_TARGET) -> int:
    return sum(1 for n in counts.values() if n >= min_rows)


def priority_codes(hk: list[str], full: list[str], counts: dict[str, int]) -> list[str]:
    union = list(dict.fromkeys(hk + full))
    out: list[str] = []
    for c in hk:
        if counts.get(c, 0) < MIN_ROWS_TARGET:
            out.append(c)
    for c in full:
        if c in hk:
            continue
        if counts.get(c, 0) < MIN_ROWS_TARGET:
            out.append(c)
    return out


def nav_sql(secucode: str, inner: int, offset: int) -> str:
    return (
        f"SELECT '{secucode}' AS SecuCode, DATE(TradingDay) d, UnitNVRestored c "
        f"FROM mf_fundnetvaluere WHERE InnerCode={inner} "
        f"AND TradingDay BETWEEN '{DATE_START}' AND '{DATE_END}' "
        f"ORDER BY d LIMIT {PAGE} OFFSET {offset}"
    )


def quote_sql(secucode: str, offset: int) -> str:
    return (
        f"SELECT s.SecuCode, DATE(q.TradingDay) d, q.ClosePrice c "
        f"FROM qt_dailyquote q JOIN secumain s ON s.InnerCode=q.InnerCode "
        f"WHERE s.SecuCode='{secucode}' "
        f"AND q.TradingDay BETWEEN '{DATE_START}' AND '{DATE_END}' "
        f"ORDER BY q.TradingDay LIMIT {PAGE} OFFSET {offset}"
    )


def next_job(hk: list[str], full: list[str]) -> dict[str, Any] | None:
    counts = count_rows_in_csv()
    if codes_meeting_min(counts) >= CODES_TARGET:
        return None
    meta = load_meta()
    prog = load_progress()
    for code in priority_codes(hk, full, counts):
        info = meta.get("by_code", {}).get(code)
        if not info:
            continue
        st = prog["codes"].setdefault(
            code, {"offset": 0, "done": False, "source": info.get("source", "nav")}
        )
        if st.get("done"):
            continue
        source = st.get("source") or info.get("source", "nav")
        offset = int(st.get("offset", 0))
        if source == "nav":
            inner = info.get("inner")
            if not inner:
                continue
            sql = nav_sql(code, int(inner), offset)
        else:
            sql = quote_sql(code, offset)
        return {
            "secucode": code,
            "source": source,
            "offset": offset,
            "sql": sql,
            "limit": PAGE,
        }
    return None
