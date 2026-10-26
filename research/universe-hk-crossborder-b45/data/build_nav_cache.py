#!/usr/bin/env python3
"""Build nav_long.csv via zsmcp query jobs (file-queue MCP bridge)."""
from __future__ import annotations

import csv
import json
import os
import re
import sys
import time
from dataclasses import dataclass
from datetime import date
from pathlib import Path
from typing import Dict, Iterable, List, Sequence, Tuple

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "data"
QUEUE = DATA / "mcp_queue"
NAV_PATH = DATA / "nav_long.csv"
HK_JSON = DATA / "universe_hk.json"
FULL_JSON = DATA / "universe_full.json"
LISTINGS_JSON = DATA / "listings.json"

DATE_START = "2019-11-01"
DATE_END = "2026-10-23"
BATCH_SECUCODES = 15


def _quarters(start: str, end: str) -> List[Tuple[str, str]]:
    s, e = date.fromisoformat(start), date.fromisoformat(end)
    out: List[Tuple[str, str]] = []
    y, m = s.year, ((s.month - 1) // 3) * 3 + 1
    while True:
        q_start = date(y, m, 1)
        if m == 10:
            q_end = date(y, 12, 31)
            next_y, next_m = y + 1, 1
        elif m == 7:
            q_end = date(y, 9, 30)
            next_y, next_m = y, 10
        elif m == 4:
            q_end = date(y, 6, 30)
            next_y, next_m = y, 7
        else:
            q_end = date(y, 3, 31)
            next_y, next_m = y, 4
        a = max(q_start, s)
        b = min(q_end, e)
        if a <= b:
            out.append((a.isoformat(), b.isoformat()))
        if q_start > e:
            break
        y, m = next_y, next_m
    return out


def _chunks(items: Sequence[str], n: int) -> Iterable[List[str]]:
    for i in range(0, len(items), n):
        yield list(items[i : i + n])


def mcp_query(sql: str, limit: int = 1000) -> str:
    """Submit SQL to agent MCP bridge; returns raw TSV body (no header)."""
    QUEUE.mkdir(parents=True, exist_ok=True)
    req_id = f"{int(time.time() * 1000)}_{os.getpid()}"
    req_path = QUEUE / f"req_{req_id}.json"
    res_path = QUEUE / f"res_{req_id}.tsv"
    err_path = QUEUE / f"res_{req_id}.err"
    req_path.write_text(json.dumps({"sql": sql, "limit": limit}, ensure_ascii=False))
    deadline = time.time() + 120
    while time.time() < deadline:
        if err_path.exists():
            raise RuntimeError(err_path.read_text(encoding="utf-8"))
        if res_path.exists():
            text = res_path.read_text(encoding="utf-8")
            req_path.unlink(missing_ok=True)
            res_path.unlink(missing_ok=True)
            err_path.unlink(missing_ok=True)
            return text
        time.sleep(0.05)
    req_path.unlink(missing_ok=True)
    raise TimeoutError(f"MCP query timed out: {sql[:120]}...")


def parse_tsv(text: str) -> List[List[str]]:
    rows: List[List[str]] = []
    for line in text.strip().splitlines():
        line = line.strip()
        if not line or line.startswith("(") or line.startswith("InnerCode") or line.startswith("SecuCode"):
            continue
        parts = line.split("\t")
        if len(parts) >= 3:
            rows.append(parts[:3])
    return rows


def pick_primary_innercodes(rows: List[Dict]) -> Dict[str, int]:
    """Map SecuCode -> InnerCode (prefer max InnerCode per code)."""
    best: Dict[str, int] = {}
    for r in rows:
        code = str(r["SecuCode"]).zfill(6) if str(r["SecuCode"]).isdigit() else str(r["SecuCode"])
        ic = int(r["InnerCode"])
        if code not in best or ic > best[code]:
            best[code] = ic
    return best


def save_json(path: Path, obj) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(obj, ensure_ascii=False, indent=2), encoding="utf-8")


def load_universes() -> Tuple[List[str], List[str]]:
    hk = json.loads(HK_JSON.read_text(encoding="utf-8"))["secucodes"]
    full = json.loads(FULL_JSON.read_text(encoding="utf-8"))["secucodes"]
    return hk, full


def fetch_nav_for_codes(secucodes: List[str], inner_by_code: Dict[str, int]) -> None:
    del inner_by_code  # NAV joins secumain on the row that holds mf_fundnetvaluere
    write_header = not NAV_PATH.exists() or NAV_PATH.stat().st_size == 0
    mode = "a" if NAV_PATH.exists() else "w"
    quarters = _quarters(DATE_START, DATE_END)
    with NAV_PATH.open(mode, newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        if write_header:
            w.writerow(["SecuCode", "d", "c"])
        for batch in _chunks(secucodes, BATCH_SECUCODES):
            if not batch:
                continue
            codes_in = ",".join(f"'{c}'" for c in batch)
            for q0, q1 in quarters:
                offset = 0
                while True:
                    sql = (
                        "SELECT s.SecuCode, DATE(q.TradingDay) d, q.ClosePrice c "
                        "FROM qt_dailyquote q JOIN secumain s ON s.InnerCode=q.InnerCode "
                        f"WHERE s.SecuCode IN ({codes_in}) "
                        f"AND q.TradingDay BETWEEN '{q0}' AND '{q1}' "
                        "ORDER BY s.SecuCode, d "
                        f"LIMIT 1000 OFFSET {offset}"
                    )
                    tsv = mcp_query(sql, limit=1000)
                    rows = parse_tsv(tsv)
                    if not rows:
                        break
                    for secucode, d, c in rows:
                        w.writerow([secucode, d, c])
                    if len(rows) < 1000:
                        break
                    offset += 1000
            f.flush()


def main() -> None:
    if len(sys.argv) < 2:
        print("usage: build_nav_cache.py fetch-nav | agent-dispatch-once", file=sys.stderr)
        sys.exit(2)
    cmd = sys.argv[1]
    if cmd == "fetch-nav":
        listings = json.loads(LISTINGS_JSON.read_text(encoding="utf-8"))
        inner_by_code = {k: int(v) for k, v in listings["inner_by_code"].items()}
        hk, full = load_universes()
        union = sorted(set(hk) | set(full))
        fetch_nav_for_codes(union, inner_by_code)
        print(f"Wrote/appended {NAV_PATH}")
    else:
        print(f"unknown cmd {cmd}", file=sys.stderr)
        sys.exit(2)


if __name__ == "__main__":
    main()
