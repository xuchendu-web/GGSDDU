#!/usr/bin/env python3
"""Build QDII-only weekly panel from kit cache."""

from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
_REPO = ROOT.parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(_REPO / "research" / "overseas-volscaled-tsmom"))

from qdii_dual_mom.config import DATA  # noqa: E402
from qdii_dual_mom.panel import (  # noqa: E402
    build_weekly_panel,
    inventory_note,
    load_universe_from_pool,
)
from vs_tsmom_lib import load_rebalance_fridays  # noqa: E402


def main() -> int:
    inv = inventory_note()
    DATA.mkdir(parents=True, exist_ok=True)
    (DATA / "inventory.json").write_text(json.dumps(inv, ensure_ascii=False, indent=2), encoding="utf-8")
    if not inv["ok"]:
        print(json.dumps({"status": "STOP", "reason": "universe < 8", **inv}, ensure_ascii=False, indent=2))
        return 2
    uni = load_universe_from_pool()
    uni.to_csv(DATA / "universe.csv", index=False)
    weeks = load_rebalance_fridays()
    panel = build_weekly_panel(uni["code"].tolist(), weeks)
    panel.to_parquet(DATA / "weekly_panel.parquet")
    print(
        json.dumps(
            {
                "status": "OK",
                "n_codes": int(panel.shape[1]),
                "n_weeks": int(panel.shape[0]),
                "codes": list(panel.columns),
            },
            ensure_ascii=False,
            indent=2,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
