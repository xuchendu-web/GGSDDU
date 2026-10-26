#!/usr/bin/env python3
"""Bond / cash-sleeve ETF inventory & materialize (no drift backfill)."""
from __future__ import annotations

import csv
import json
import urllib.parse
import urllib.request
from pathlib import Path

KIT = Path(__file__).resolve().parent.parent / "cloud_batch" / "CLOUD-BATCH-2026-10-26"
BOND_DIR = KIT / "data" / "research_cache" / "bond_daily"
CACHE = KIT / "data" / "research_cache"

# Research sleeve set (inventory-first; no 511880 in caches)
SLEEVE_CODES = ("511010", "511260")
MONEY_MARKET_CANDIDATES = ("511880", "511990", "511620", "511800", "511360")

EVAL_NEED_BY = "2019-11-01"  # ~4w lookback before 2020-01-03


def inventory_report() -> dict:
    rep: dict = {"bond_daily": {}, "week": {}, "day": {}, "sina": {}, "money_market_in_cache": []}
    for c in SLEEVE_CODES:
        fp = BOND_DIR / f"{c}.csv"
        if fp.exists():
            with fp.open() as f:
                n = sum(1 for _ in f) - 1
            rep["bond_daily"][c] = {"path": str(fp), "rows": n}
        else:
            rep["bond_daily"][c] = {"path": str(fp), "rows": 0, "missing": True}
    for c in MONEY_MARKET_CANDIDATES:
        hits = []
        for kind, sub in (("week", CACHE / "week"), ("day", CACHE / "day"), ("sina", CACHE / "sina_daily")):
            ext = ".json" if kind != "sina" else ".csv"
            if (sub / f"{c}{ext}").exists():
                hits.append(kind)
        if hits:
            rep["money_market_in_cache"].append({"code": c, "kinds": hits})
    return rep


def _fetch_eastmoney_daily(code: str) -> list[tuple[str, float]]:
    """SH bond ETF daily close via Eastmoney kline (fallback when bond_daily too short)."""
    secid = f"1.{code}"
    params = urllib.parse.urlencode(
        {
            "secid": secid,
            "fields1": "f1,f2,f3,f4,f5,f6",
            "fields2": "f51,f52,f53,f54,f55,f56,f57,f58,f59,f60,f61",
            "klt": "101",
            "fqt": "1",
            "end": "20500101",
            "lmt": "1000000",
        }
    )
    url = f"https://push2his.eastmoney.com/api/qt/stock/kline/get?{params}"
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
    with urllib.request.urlopen(req, timeout=60) as resp:
        body = json.loads(resp.read().decode())
    kl = (body.get("data") or {}).get("klines") or []
    rows: list[tuple[str, float]] = []
    for line in kl:
        parts = line.split(",")
        if len(parts) < 3:
            continue
        d, close = parts[0], float(parts[2])
        rows.append((d, close))
    return rows


def write_bond_csv(code: str, rows: list[tuple[str, float]]) -> Path:
    BOND_DIR.mkdir(parents=True, exist_ok=True)
    fp = BOND_DIR / f"{code}.csv"
    with fp.open("w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["date", "close"])
        for d, c in sorted(rows, key=lambda x: x[0]):
            w.writerow([d, c])
    return fp


def first_date_csv(fp: Path) -> str | None:
    if not fp.exists():
        return None
    with fp.open(encoding="utf-8") as f:
        r = csv.DictReader(f)
        for row in r:
            return str(row["date"])[:10]
    return None


def ensure_bond_daily(min_first: str = EVAL_NEED_BY, allow_fetch: bool = False) -> dict:
    """Ensure sleeve bonds cover min_first; fetch Eastmoney if kit CSV too short (not drift)."""
    out: dict = {"inventory": inventory_report(), "actions": [], "ok": True, "blocked": []}
    for code in SLEEVE_CODES:
        fp = BOND_DIR / f"{code}.csv"
        first = first_date_csv(fp)
        need_fetch = first is None or first > min_first
        if need_fetch and allow_fetch:
            rows = _fetch_eastmoney_daily(code)
            if not rows:
                out["ok"] = False
                out["blocked"].append(f"{code}: eastmoney fetch empty")
                continue
            write_bond_csv(code, rows)
            first = rows[0][0]
            out["actions"].append(f"fetched {code} n={len(rows)} first={first} via eastmoney")
        first = first_date_csv(fp)
        if first is None or first > min_first:
            out["ok"] = False
            out["blocked"].append(
                f"{code}: bond_daily first={first} need<={min_first} (inventory: {BOND_DIR})"
            )
    return out


if __name__ == "__main__":
    print(json.dumps(ensure_bond_daily(), ensure_ascii=False, indent=2))
