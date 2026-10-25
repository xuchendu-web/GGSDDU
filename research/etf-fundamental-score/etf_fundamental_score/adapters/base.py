from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any, Iterable, Mapping, Sequence


@dataclass
class UniverseRow:
    """Normalized ETF row for scoring (adapter output)."""

    symbol: str
    name: str = ""
    fields: dict[str, Any] = field(default_factory=dict)

    def as_mapping(self) -> Mapping[str, Any]:
        out = {"symbol": self.symbol, "name": self.name}
        out.update(self.fields)
        return out


class ETFDataAdapter(ABC):
    """
    Pluggable data source for ETF fundamentals.
    Production implementations might wrap zsmcp / fund_nav / holdings APIs;
    this repo ships FixtureCsvAdapter only.
    """

    @abstractmethod
    def load_universe(self) -> Sequence[UniverseRow]:
        """Return the research universe to score."""

    def enrich(self, rows: Iterable[UniverseRow]) -> Sequence[UniverseRow]:
        """Optional second-pass enrichment (holdings, TE from returns, etc.)."""
        return list(rows)
