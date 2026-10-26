#!/usr/bin/env python3
"""Inventory roll/basis/term-structure data for commodity carry research (evidence only)."""
from __future__ import annotations

import json
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
OUT = Path(__file__).resolve().parents[1] / "inventory_evidence.json"

LOCAL_PATHS = [
    "/cj-data",
    "/pyas-data-discovery",
    "/data",
    "/mnt/cj-data",
]

GIT_PATTERNS = [
    "roll_yield",
    "carry_signal",
    "term_structure",
    "basis_",
    "contango",
    "backwardation",
    "展期",
    "基差",
    "期限结构",
]

COMMODITY_POOL_NOTE = {
    "source_ref": "origin/cursor/universe-commodity-bond-cash-live1430-1848:etf-correlation/data/research_pool_v2.csv",
    "l0_filter": "商品",
    "codes_aum_ge_2": [
        {"code": "518880", "name": "华安黄金ETF", "family": "黄金现货", "index": "Au9999.SGE"},
        {"code": "518600", "name": "广发上海金ETF", "family": "黄金现货", "index": "SHAU.SGE"},
        {"code": "159980", "name": "大成有色金属期货ETF", "family": "期货·有色", "index": "IMCI.SHF"},
        {"code": "159985", "name": "华夏饲料豆粕期货ETF", "family": "期货·农产品", "index": "DCESMFI.DCE"},
        {"code": "159981", "name": "建信易盛郑商所能源化工期货ETF", "family": "期货·能化", "index": "000201.CZC"},
    ],
    "excluded_low_aum": [{"code": "510170", "name": "国联安上证商品ETF", "note": "l0=中国权益·周期资源，非商品袖主池"}],
}


def path_exists(p: str) -> dict:
    path = Path(p)
    if not path.exists():
        return {"path": p, "exists": False}
    try:
        children = sorted(x.name for x in path.iterdir())[:20]
    except OSError as e:
        return {"path": p, "exists": True, "list_error": str(e)}
    return {"path": p, "exists": True, "sample_entries": children}


def git_grep_repo() -> dict:
    try:
        subprocess.run(["git", "fetch", "origin", "main"], cwd=ROOT, capture_output=True, timeout=120)
    except (subprocess.TimeoutExpired, FileNotFoundError):
        pass
    hits: list[str] = []
    for pat in GIT_PATTERNS:
        try:
            r = subprocess.run(
                [
                    "git",
                    "grep",
                    "-i",
                    "-l",
                    pat,
                    "refs/remotes/origin/main",
                    "refs/remotes/origin/cursor/universe-commodity-bond-cash-live1430-1848",
                ],
                cwd=ROOT,
                capture_output=True,
                text=True,
                timeout=60,
            )
            if r.stdout.strip():
                hits.extend(r.stdout.strip().split("\n"))
        except (subprocess.TimeoutExpired, FileNotFoundError):
            continue
    unique = sorted(set(hits))
    return {"patterns": GIT_PATTERNS, "matching_paths_count": len(unique), "matching_paths_sample": unique[:30]}


def _remote_day_bar_sample(code: str = "159980") -> dict | None:
    ref = "origin/cursor/universe-commodity-bond-cash-live1430-1848"
    path = (
        f"research/cloud_batch/CLOUD-BATCH-2026-10-26/data/research_cache/day/{code}.json"
    )
    try:
        r = subprocess.run(
            ["git", "show", f"{ref}:{path}"],
            cwd=ROOT,
            capture_output=True,
            text=True,
            timeout=30,
        )
        if r.returncode != 0:
            return None
        data = json.loads(r.stdout)
        bar = (data.get("bars") or [{}])[0]
        return {"git_ref": ref, "path": path, "bar_fields": sorted(bar.keys())}
    except (subprocess.TimeoutExpired, json.JSONDecodeError, FileNotFoundError):
        return None


def cloud_cache_fields() -> dict:
    """If CLOUD-BATCH tree absent on branch, note from remote-only inspection."""
    cache = ROOT / "research" / "cloud_batch" / "CLOUD-BATCH-2026-10-26" / "data" / "research_cache"
    remote_sample = _remote_day_bar_sample()
    if not cache.exists():
        out = {
            "cloud_batch_present_on_branch": False,
            "note": "CLOUD-BATCH lives on research branches (e.g. PR#56); main has no kit checkout.",
            "known_day_bar_schema": ["date", "o", "h", "l", "c"],
            "carry_fields_present": False,
        }
        if remote_sample:
            out["remote_day_bar_sample"] = remote_sample
            carry_keys = {"roll_yield", "basis", "near", "far", "carry"}
            out["carry_fields_present"] = bool(carry_keys & set(remote_sample.get("bar_fields", [])))
        return out
    sample = cache / "day" / "159980.json"
    fields = set()
    if sample.exists():
        data = json.loads(sample.read_text(encoding="utf-8"))
        if data.get("bars"):
            fields = set(data["bars"][0].keys())
    return {
        "cloud_batch_present_on_branch": True,
        "sample_file": str(sample.relative_to(ROOT)) if sample.exists() else None,
        "bar_fields": sorted(fields),
        "carry_fields_present": bool(fields & {"roll_yield", "basis", "near", "far", "carry"}),
    }


def main() -> int:
    evidence = {
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "task": "RESEARCH-COMMODITY-CARRY-ROLL-WEEKLY",
        "verdict": "SKIP",
        "local_data_paths": [path_exists(p) for p in LOCAL_PATHS],
        "git_content_search": git_grep_repo(),
        "cloud_batch_price_cache": cloud_cache_fields(),
        "commodity_universe_ref": COMMODITY_POOL_NOTE,
        "pr56_context": {
            "pr": 56,
            "finding": "商品袖 SPIKE-S20 Calmar 0.23 vs face 0.70; 动量适配偏弱",
            "branch": "cursor/universe-commodity-bond-cash-live1430-1848",
        },
    }
    OUT.write_text(json.dumps(evidence, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"wrote {OUT}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
