from __future__ import annotations

import argparse
import sys
from pathlib import Path

from etf_fundamental_score.adapters.fixture_csv import FixtureCsvAdapter
from etf_fundamental_score.batch import score_universe_files
from etf_fundamental_score.score import ScoreEngine, load_config


def _default_config() -> Path:
    return Path(__file__).resolve().parent.parent / "config.yaml"


def _default_fixture() -> Path:
    return Path(__file__).resolve().parent.parent / "fixtures" / "universe_sample.csv"


def _cmd_score(args: argparse.Namespace) -> int:
    cfg = load_config(args.config)
    adapter = FixtureCsvAdapter(args.input)
    rows = adapter.enrich(adapter.load_universe())
    engine = ScoreEngine(cfg)
    scored = engine.score_universe(rows)
    df = engine.to_dataframe(scored)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    df.to_csv(args.output, index=False)
    print(f"Wrote {len(df)} rows to {args.output.resolve()}")
    return 0


def _cmd_batch(args: argparse.Namespace) -> int:
    inputs: list[Path] = list(args.input or [])
    if args.manifest:
        import pandas as pd

        manifest = pd.read_csv(args.manifest)
        col = "universe_csv" if "universe_csv" in manifest.columns else manifest.columns[0]
        for raw in manifest[col].astype(str):
            p = Path(raw)
            if not p.is_absolute() and args.manifest.parent:
                candidate = args.manifest.parent / p
                if candidate.is_file():
                    p = candidate
            inputs.append(p)
    if args.input_dir:
        inputs.extend(sorted(args.input_dir.glob("*.csv")))

    if not inputs:
        print("etf-score batch: provide --input, --manifest, or --input-dir", file=sys.stderr)
        return 2

    results = score_universe_files(
        inputs,
        args.config,
        args.output_dir,
        write_combined=not args.no_combined,
    )
    for r in results:
        print(f"{r.source.name}: {r.row_count} rows -> {r.output_path}")
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Score an ETF research universe (screening only; not investment advice)."
    )
    parser.add_argument(
        "-c",
        "--config",
        type=Path,
        default=_default_config(),
        help="config.yaml with factor weights",
    )
    sub = parser.add_subparsers(dest="command")

    score_p = sub.add_parser("score", help="Score a single universe CSV (default)")
    score_p.add_argument(
        "-c",
        "--config",
        type=Path,
        default=_default_config(),
        help="config.yaml with factor weights",
    )
    score_p.add_argument(
        "-i",
        "--input",
        type=Path,
        default=_default_fixture(),
        help="Universe CSV path",
    )
    score_p.add_argument(
        "-o",
        "--output",
        type=Path,
        default=Path("scores.csv"),
        help="Output scores CSV",
    )

    batch_p = sub.add_parser("batch", help="Score multiple universe CSV files")
    batch_p.add_argument(
        "-c",
        "--config",
        type=Path,
        default=_default_config(),
        help="config.yaml with factor weights",
    )
    batch_p.add_argument(
        "-i",
        "--input",
        type=Path,
        action="append",
        help="Universe CSV (repeatable)",
    )
    batch_p.add_argument(
        "-m",
        "--manifest",
        type=Path,
        help="Manifest CSV with universe_csv column",
    )
    batch_p.add_argument(
        "--input-dir",
        type=Path,
        help="Directory of *.csv universes",
    )
    batch_p.add_argument(
        "-o",
        "--output-dir",
        type=Path,
        default=Path("batch_scores"),
        help="Directory for per-universe and combined outputs",
    )
    batch_p.add_argument(
        "--no-combined",
        action="store_true",
        help="Skip writing all_scores.csv",
    )

    # Back-compat: `etf-score -i x -o y` without subcommand
    parser.add_argument("-i", "--input", type=Path, default=None, help=argparse.SUPPRESS)
    parser.add_argument("-o", "--output", type=Path, default=None, help=argparse.SUPPRESS)

    args = parser.parse_args(argv)

    try:
        if args.command == "batch":
            return _cmd_batch(args)
        if args.command == "score":
            return _cmd_score(args)
        # Legacy invocation
        legacy = argparse.Namespace(
            config=args.config,
            input=args.input or _default_fixture(),
            output=args.output or Path("scores.csv"),
        )
        return _cmd_score(legacy)
    except Exception as exc:  # noqa: BLE001 — CLI boundary
        print(f"etf-score error: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
