#!/usr/bin/env python3
"""Build Friday-aligned weekly panel from research_cache week jsons. Research only."""

from __future__ import annotations

import argparse
import shutil
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from dual_momentum.config import DATA  # noqa: E402
from dual_momentum.panel import build_weekly_panel, load_universe  # noqa: E402


def main() -> int:
    p = argparse.ArgumentParser()
    p.add_argument("--week-dir", required=True, help="research_cache/week directory")
    p.add_argument("--universe", required=True, help="universe_replace_only_436.csv")
    p.add_argument("--b45-nav", default="", help="nav_LIVE1430-B45-S20.csv")
    args = p.parse_args()
    DATA.mkdir(parents=True, exist_ok=True)
    uni_src = Path(args.universe)
    shutil.copy2(uni_src, DATA / "universe.csv")
    uni = load_universe(DATA / "universe.csv")
    panel = build_weekly_panel(Path(args.week_dir), list(uni["code"]))
    out = DATA / "weekly_panel.parquet"
    panel.to_parquet(out)
    if args.b45_nav:
        shutil.copy2(args.b45_nav, DATA / "nav_LIVE1430-B45-S20.csv")
    print(
        f"panel {panel.shape} {panel.index.min().date()}→{panel.index.max().date()} -> {out}",
        flush=True,
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
