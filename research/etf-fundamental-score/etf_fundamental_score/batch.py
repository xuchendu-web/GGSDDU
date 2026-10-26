from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any, Sequence

import pandas as pd

from etf_fundamental_score.adapters.fixture_csv import FixtureCsvAdapter
from etf_fundamental_score.score import ScoreEngine, load_config


@dataclass(frozen=True)
class BatchResult:
    source: Path
    output_path: Path
    row_count: int


def _read_manifest(path: Path) -> list[Path]:
    df = pd.read_csv(path)
    col = "universe_csv" if "universe_csv" in df.columns else df.columns[0]
    roots = [Path(p) for p in df[col].astype(str)]
    return roots


def score_universe_files(
    inputs: Sequence[Path],
    config_path: Path,
    output_dir: Path,
    *,
    write_combined: bool = True,
) -> list[BatchResult]:
    cfg = load_config(config_path)
    engine = ScoreEngine(cfg)
    output_dir.mkdir(parents=True, exist_ok=True)

    results: list[BatchResult] = []
    combined: list[pd.DataFrame] = []

    for inp in inputs:
        if not inp.is_file():
            raise FileNotFoundError(f"universe not found: {inp}")
        adapter = FixtureCsvAdapter(inp)
        rows = adapter.enrich(adapter.load_universe())
        scored = engine.score_universe(rows)
        df = engine.to_dataframe(scored)
        df.insert(0, "universe_source", inp.name)
        out_path = output_dir / f"{inp.stem}_scores.csv"
        df.to_csv(out_path, index=False)
        results.append(BatchResult(source=inp.resolve(), output_path=out_path.resolve(), row_count=len(df)))
        combined.append(df)

    if write_combined and combined:
        all_df = pd.concat(combined, ignore_index=True)
        all_path = output_dir / "all_scores.csv"
        all_df.to_csv(all_path, index=False)

    return results
