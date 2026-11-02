#!/usr/bin/env python3
"""Tencent m30 bypass for Friday 14:30. Not pytdx. Not 进门/中金/Alpha派."""
from __future__ import annotations

import argparse
import csv
import json
import time
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "out"
UA = "Mozilla/5.0 research-refresh/data_v1016"


def tencent_symbol(code: str) -> str:
    c = code.split(".")[0]
    if c.startswith(("5", "6")):
        return f"sh{c}"
    return f"sz{c}"


def fetch_m30(symbol: str, timeout: float = 12.0) -> list[list]:
    url = f"https://ifzq.gtimg.cn/appstock/app/kline/mkline?param={symbol},m30,,80"
    req = urllib.request.Request(url, headers={"User-Agent": UA})
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        payload = json.loads(resp.read().decode("utf-8", "replace"))
    block = (payload.get("data") or {}).get(symbol) or {}
    return block.get("m30") or []


def pick_bar(rows: list[list], ymd: str, hhmm: str = "1430") -> dict | None:
    stamp = f"{ymd}{hhmm}"
    for row in rows:
        if not row:
            continue
        if str(row[0]) == stamp:
            return {
                "stamp": row[0],
                "open": row[1],
                "close": row[2],
                "high": row[3],
                "low": row[4],
                "volume": row[5] if len(row) > 5 else "",
            }
    return None


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--friday", default="20261030")
    ap.add_argument("--sleep", type=float, default=0.15)
    ap.add_argument(
        "--codes",
        default="510300,510500,159915,588000,512880,159981,159985,518880,510050,159901",
    )
    args = ap.parse_args()
    codes = [c.strip() for c in args.codes.split(",") if c.strip()]
    out_path = OUT / f"fri_1430_{args.friday}.csv"
    rows = []
    for code in codes:
        sym = tencent_symbol(code)
        try:
            bars = fetch_m30(sym)
            bar = pick_bar(bars, args.friday)
            rows.append(
                {
                    "etf_code": code,
                    "tencent_symbol": sym,
                    "friday": args.friday,
                    "status": "ok" if bar else "missing_1430_bar",
                    "price_1430": (bar or {}).get("close", ""),
                    "high": (bar or {}).get("high", ""),
                    "low": (bar or {}).get("low", ""),
                    "volume": (bar or {}).get("volume", ""),
                    "source": "tencent.mkline.m30",
                }
            )
        except Exception as exc:  # noqa: BLE001 — audit, keep going
            rows.append(
                {
                    "etf_code": code,
                    "tencent_symbol": sym,
                    "friday": args.friday,
                    "status": f"error:{type(exc).__name__}",
                    "price_1430": "",
                    "high": "",
                    "low": "",
                    "volume": "",
                    "source": "tencent.mkline.m30",
                }
            )
        time.sleep(args.sleep)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    with out_path.open("w", newline="") as f:
        w = csv.DictWriter(
            f,
            fieldnames=[
                "etf_code",
                "tencent_symbol",
                "friday",
                "status",
                "price_1430",
                "high",
                "low",
                "volume",
                "source",
            ],
        )
        w.writeheader()
        w.writerows(rows)
    ok = sum(1 for r in rows if r["status"] == "ok")
    print(f"wrote {out_path} ok={ok}/{len(rows)}")
    return 0 if ok else 2


if __name__ == "__main__":
    raise SystemExit(main())
