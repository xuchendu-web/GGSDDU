from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
UNIVERSE_PATH = ROOT / "universe.json"


def load_universe(path: Path | None = None) -> list[dict]:
    data = json.loads((path or UNIVERSE_PATH).read_text(encoding="utf-8"))
    etfs = data.get("etfs") or []
    if len(etfs) < 20:
        raise ValueError(f"样本不足 20：{len(etfs)}")
    return etfs
