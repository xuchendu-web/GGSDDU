#!/usr/bin/env python3
"""Process one pending zsmcp query request in data/mcp_queue (agent-side helper)."""
from __future__ import annotations

import json
import sys
from pathlib import Path

QUEUE = Path(__file__).resolve().parent / "mcp_queue"


def next_request() -> tuple[str, dict] | None:
    if not QUEUE.exists():
        return None
    reqs = sorted(QUEUE.glob("req_*.json"))
    if not reqs:
        return None
    p = reqs[0]
    req_id = p.stem.replace("req_", "", 1)
    payload = json.loads(p.read_text(encoding="utf-8"))
    return req_id, payload


def write_response(req_id: str, tsv: str) -> None:
    (QUEUE / f"res_{req_id}.tsv").write_text(tsv, encoding="utf-8")


def write_error(req_id: str, msg: str) -> None:
    (QUEUE / f"res_{req_id}.err").write_text(msg, encoding="utf-8")


if __name__ == "__main__":
    n = next_request()
    if not n:
        print("NO_PENDING")
        sys.exit(0)
    req_id, payload = n
    print(json.dumps({"req_id": req_id, **payload}))
