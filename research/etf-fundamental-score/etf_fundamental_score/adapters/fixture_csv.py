from __future__ import annotations

from pathlib import Path
from typing import Sequence

import pandas as pd

from etf_fundamental_score.adapters.base import ETFDataAdapter, UniverseRow

REQUIRED_COLUMNS = ("symbol",)


class FixtureCsvAdapter(ETFDataAdapter):
    """Load universe from a CSV fixture (synthetic or exported research pool)."""

    def __init__(self, path: str | Path) -> None:
        self.path = Path(path)

    def load_universe(self) -> Sequence[UniverseRow]:
        if not self.path.is_file():
            raise FileNotFoundError(f"universe CSV not found: {self.path}")
        df = pd.read_csv(self.path)
        for col in REQUIRED_COLUMNS:
            if col not in df.columns:
                raise ValueError(f"CSV missing required column: {col}")

        rows: list[UniverseRow] = []
        for _, rec in df.iterrows():
            symbol = str(rec["symbol"]).strip()
            name = str(rec.get("name", "") or "").strip()
            fields = {
                k: (None if pd.isna(v) else v)
                for k, v in rec.items()
                if k not in ("symbol", "name")
            }
            rows.append(UniverseRow(symbol=symbol, name=name, fields=fields))
        return rows
