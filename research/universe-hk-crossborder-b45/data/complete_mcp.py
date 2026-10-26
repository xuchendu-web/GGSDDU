#!/usr/bin/env python3
"""Write MCP query response TSV for a pending queue request."""
import sys
from pathlib import Path

QUEUE = Path(__file__).resolve().parent / "mcp_queue"


def main() -> None:
    if len(sys.argv) < 3:
        print("usage: complete_mcp.py <req_id> <tsv_path|-", file=sys.stderr)
        sys.exit(2)
    req_id, src = sys.argv[1], sys.argv[2]
    if src == "-":
        tsv = sys.stdin.read()
    else:
        tsv = Path(src).read_text(encoding="utf-8")
    (QUEUE / f"res_{req_id}.tsv").write_text(tsv, encoding="utf-8")
    (QUEUE / f"req_{req_id}.json").unlink(missing_ok=True)
    print("OK", req_id, len(tsv.splitlines()))


if __name__ == "__main__":
    main()
