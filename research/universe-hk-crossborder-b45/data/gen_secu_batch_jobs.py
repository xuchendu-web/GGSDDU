#!/usr/bin/env python3
"""Emit JSON array of page jobs for codes not done (optional --offset-only 0)."""
from __future__ import annotations

import argparse
import json

from secu_fetch_lib import (
    MIN_ROWS_TARGET,
    count_rows_in_csv,
    load_meta,
    load_progress,
    load_universe,
    nav_sql,
    quote_sql,
)


def main() -> None:
    p = argparse.ArgumentParser()
    p.add_argument("--group", choices=["hk", "full", "all"], default="hk")
    p.add_argument("--limit", type=int, default=20)
    p.add_argument("--force-offset", type=int, default=None)
    args = p.parse_args()
    hk, full = load_universe()
    if args.group == "hk":
        codes = hk
    elif args.group == "full":
        codes = [c for c in full if c not in hk]
    else:
        codes = list(dict.fromkeys(hk + full))
    meta = load_meta()["by_code"]
    prog = load_progress()["codes"]
    counts = count_rows_in_csv()
    jobs = []
    for code in codes:
        if counts.get(code, 0) >= MIN_ROWS_TARGET and args.group != "all":
            continue
        st = prog.get(code, {})
        if st.get("done"):
            continue
        info = meta.get(code, {})
        source = st.get("source") or info.get("source", "nav")
        offset = args.force_offset if args.force_offset is not None else int(st.get("offset", 0))
        if source == "nav" and info.get("inner"):
            sql = nav_sql(code, int(info["inner"]), offset)
        else:
            sql = quote_sql(code, offset)
            source = "quote"
        jobs.append(
            {
                "secucode": code,
                "source": source,
                "offset": offset,
                "sql": sql,
                "limit": 250,
            }
        )
        if len(jobs) >= args.limit:
            break
    print(json.dumps(jobs, ensure_ascii=False))


if __name__ == "__main__":
    main()
