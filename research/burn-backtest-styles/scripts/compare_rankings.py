#!/usr/bin/env python3
"""Run all three styles and write compare_report.md."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from shared.config import PANEL_CSV  # noqa: E402
from shared.generate_synthetic_panel import write_panel  # noqa: E402
from shared.rule_spec import rankings_to_compare_frame  # noqa: E402
from scripts.style_a_vector import run_ranking as run_a  # noqa: E402
from scripts.style_b_event import run_ranking as run_b  # noqa: E402
from scripts.style_c_pandas import run_ranking as run_c  # noqa: E402


def _top_k_agreement(a: pd.DataFrame, b: pd.DataFrame) -> tuple[float, int, int]:
    merged = a.merge(b, on="week_end", suffixes=("_a", "_b"))
    if merged.empty:
        return 0.0, 0, 0
    matches = 0
    for _, row in merged.iterrows():
        if row["top_k_a"] == row["top_k_b"]:
            matches += 1
    n = len(merged)
    return matches / n, matches, n


def _rank_list_agreement(a: pd.DataFrame, b: pd.DataFrame) -> tuple[float, int, int]:
    merged = a.merge(b, on="week_end", suffixes=("_a", "_b"))
    if merged.empty:
        return 0.0, 0, 0
    matches = 0
    for _, row in merged.iterrows():
        if row["ranks_a"] == row["ranks_b"]:
            matches += 1
    n = len(merged)
    return matches / n, matches, n


def build_report(panel_path: Path = PANEL_CSV) -> str:
    ra, rb, rc = run_a(panel_path), run_b(panel_path), run_c(panel_path)

    pairs = [
        ("A vs B", ra, rb),
        ("A vs C", ra, rc),
        ("B vs C", rb, rc),
    ]
    lines = [
        "# Burn backtest styles — ranking compare",
        "",
        f"Panel: `{panel_path}`",
        "",
        "## Agreement scores",
        "",
        "| Pair | Top-K weekly match | Full rank list match |",
        "|------|-------------------:|---------------------:|",
    ]
    top_scores = []
    full_scores = []
    for name, x, y in pairs:
        top_s, top_m, top_n = _top_k_agreement(x, y)
        full_s, full_m, full_n = _rank_list_agreement(x, y)
        top_scores.append(top_s)
        full_scores.append(full_s)
        lines.append(
            f"| {name} | {top_s:.4f} ({top_m}/{top_n}) | {full_s:.4f} ({full_m}/{full_n}) |"
        )

    min_top = min(top_scores) if top_scores else 0.0
    min_full = min(full_scores) if full_scores else 0.0
    lines.extend(
        [
            "",
            f"**Summary:** min pairwise top-K agreement = **{min_top:.4f}**; "
            f"min full-rank agreement = **{min_full:.4f}**.",
            "",
        ]
    )

    if min_top < 1.0 or min_full < 1.0:
        lines.append(
            "> Rankings diverged on at least one pair — templates only; "
            "not production parity (see HYPOTHESIS.md)."
        )
        lines.append("")
        lines.append("## Deltas (weeks where A vs B top-K differs)")
        lines.append("")
        m = ra.merge(rb, on="week_end", suffixes=("_a", "_b"))
        diff = m[m["top_k_a"] != m["top_k_b"]]
        if diff.empty:
            lines.append("_No A vs B top-K diffs (check other pairs)._")
        else:
            lines.append("| week_end | top_k A | top_k B |")
            lines.append("|----------|---------|---------|")
            for _, row in diff.iterrows():
                lines.append(
                    f"| {row['week_end'].date()} | {row['top_k_a']} | {row['top_k_b']} |"
                )
    else:
        lines.append("All three engines agree on weekly top-K and full rank order.")

    for label, rdf in [("A vector", ra), ("B event", rb), ("C pandas", rc)]:
        flat = rankings_to_compare_frame(rdf)
        lines.extend(["", f"## Rank table — {label}", ""])
        lines.append(flat.to_markdown(index=False))

    return "\n".join(lines) + "\n"


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--panel", type=Path, default=PANEL_CSV)
    parser.add_argument(
        "--output",
        type=Path,
        default=ROOT / "compare_report.md",
    )
    parser.add_argument("--ensure-data", action="store_true", default=True)
    args = parser.parse_args()
    if args.ensure_data and not args.panel.is_file():
        write_panel(args.panel)
    report = build_report(args.panel)
    args.output.write_text(report, encoding="utf-8")
    print(f"Wrote {args.output}")


if __name__ == "__main__":
    main()
