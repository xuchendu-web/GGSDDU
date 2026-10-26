#!/usr/bin/env python3
"""Agent helper: emit next MCP jobs or ingest one page from stdin."""
from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path

from secu_fetch_lib import CODES_TARGET, MIN_ROWS_TARGET, codes_meeting_min, count_rows_in_csv

DATA = Path(__file__).resolve().parent


def cmd_next(args: argparse.Namespace) -> None:
    group = args.group
    limit = args.limit
    out = subprocess.check_output(
        [
            sys.executable,
            str(DATA / "gen_secu_batch_jobs.py"),
            "--group",
            group,
            "--limit",
            str(limit),
        ],
        text=True,
    )
    jobs = json.loads(out)
    if not jobs and group == "hk":
        out = subprocess.check_output(
            [
                sys.executable,
                str(DATA / "gen_secu_batch_jobs.py"),
                "--group",
                "full",
                "--limit",
                str(limit),
            ],
            text=True,
        )
        jobs = json.loads(out)
    print(json.dumps(jobs, ensure_ascii=False))


def cmd_store(args: argparse.Namespace) -> None:
    job = json.loads(args.job)
    raw = sys.stdin.read()
    path = DATA / "mcp_pages" / f"{job['secucode']}_{job['offset']}.tsv"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(raw, encoding="utf-8")
    subprocess.check_call(
        [sys.executable, str(DATA / "ingest_secu_page.py"), json.dumps(job, ensure_ascii=False), str(path)]
    )


def cmd_status(_: argparse.Namespace) -> None:
    counts = count_rows_in_csv()
    subprocess.check_call([sys.executable, str(DATA / "secu_fetch_status.py")])


def cmd_ready(_: argparse.Namespace) -> None:
    counts = count_rows_in_csv()
    ok = codes_meeting_min(counts) >= CODES_TARGET
    print("yes" if ok else "no")


def main() -> None:
    p = argparse.ArgumentParser()
    sub = p.add_subparsers(dest="cmd", required=True)
    n = sub.add_parser("next")
    n.add_argument("--group", choices=["hk", "full", "all"], default="hk")
    n.add_argument("--limit", type=int, default=25)
    n.set_defaults(func=cmd_next)
    s = sub.add_parser("store")
    s.add_argument("job", help="JSON job object")
    s.set_defaults(func=cmd_store)
    st = sub.add_parser("status")
    st.set_defaults(func=cmd_status)
    r = sub.add_parser("ready")
    r.set_defaults(func=cmd_ready)
    args = p.parse_args()
    args.func(args)


if __name__ == "__main__":
    main()
