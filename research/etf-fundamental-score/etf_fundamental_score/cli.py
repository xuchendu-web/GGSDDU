from __future__ import annotations

import argparse
import sys
from pathlib import Path

from etf_fundamental_score.adapters.fixture_csv import FixtureCsvAdapter
from etf_fundamental_score.score import ScoreEngine, load_config


def _default_config() -> Path:
    return Path(__file__).resolve().parent.parent / "config.yaml"


def _default_fixture() -> Path:
    return Path(__file__).resolve().parent.parent / "fixtures" / "universe_sample.csv"


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Score an ETF research universe (screening only; not investment advice)."
    )
    parser.add_argument(
        "-i",
        "--input",
        type=Path,
        default=_default_fixture(),
        help="Universe CSV path",
    )
    parser.add_argument(
        "-c",
        "--config",
        type=Path,
        default=_default_config(),
        help="config.yaml with factor weights",
    )
    parser.add_argument(
        "-o",
        "--output",
        type=Path,
        default=Path("scores.csv"),
        help="Output scores CSV",
    )
    args = parser.parse_args(argv)

    try:
        cfg = load_config(args.config)
        adapter = FixtureCsvAdapter(args.input)
        rows = adapter.enrich(adapter.load_universe())
        engine = ScoreEngine(cfg)
        scored = engine.score_universe(rows)
        df = engine.to_dataframe(scored)
        args.output.parent.mkdir(parents=True, exist_ok=True)
        df.to_csv(args.output, index=False)
    except Exception as exc:  # noqa: BLE001 — CLI boundary
        print(f"etf-score error: {exc}", file=sys.stderr)
        return 1

    print(f"Wrote {len(df)} rows to {args.output.resolve()}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
