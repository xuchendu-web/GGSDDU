#!/usr/bin/env python3
"""Run all engine styles and write compare_report.md with agreement matrices."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from shared.compare_utils import agreement_matrix, top_k_agreement  # noqa: E402
from shared.config import PANEL_CSV  # noqa: E402
from shared.engine_registry import engine_ids, engine_labels, load_runner  # noqa: E402
from shared.generate_synthetic_panel import write_panel  # noqa: E402
from shared.rule_spec import rankings_to_compare_frame  # noqa: E402


def _collect_results(panel_path: Path) -> tuple[dict[str, pd.DataFrame], list[str]]:
    results: dict[str, pd.DataFrame] = {}
    skipped: list[str] = []
    for eid in engine_ids():
        try:
            results[eid] = load_runner(eid)(panel_path)
        except ImportError as exc:
            skipped.append(f"{eid}: {exc}")
    return results, skipped


def _matrix_markdown(mat: pd.DataFrame) -> str:
    labels = [f"{engine_labels().get(i, '?')} `{i}`" for i in mat.index]
    header = "| | " + " | ".join(labels) + " |"
    sep = "|---|" + "|".join(["---:"] * len(labels)) + "|"
    rows = [header, sep]
    for i, row_name in enumerate(mat.index):
        cells = [labels[i]]
        for j in range(len(mat.columns)):
            cells.append(f"{mat.iloc[i, j]:.4f}")
        rows.append("| " + " | ".join(cells) + " |")
    return "\n".join(rows)


def build_report(panel_path: Path = PANEL_CSV) -> str:
    results, skipped = _collect_results(panel_path)
    if len(results) < 2:
        raise RuntimeError(f"Need at least two engines; skipped={skipped}")

    top_mat = agreement_matrix(results, metric="top_k")
    full_mat = agreement_matrix(results, metric="full")

    off_diag = []
    for i in top_mat.index:
        for j in top_mat.columns:
            if i != j:
                off_diag.append(top_mat.loc[i, j])
    min_top = min(off_diag) if off_diag else 1.0
    off_diag_full = []
    for i in full_mat.index:
        for j in full_mat.columns:
            if i != j:
                off_diag_full.append(full_mat.loc[i, j])
    min_full = min(off_diag_full) if off_diag_full else 1.0

    lines = [
        "# Burn backtest styles — ranking compare",
        "",
        f"Panel: `{panel_path}`",
        f"Engines run: **{len(results)}** ({', '.join(sorted(results.keys()))})",
        "",
    ]
    if skipped:
        lines.extend(["## Skipped (optional deps)", ""])
        for s in skipped:
            lines.append(f"- {s}")
        lines.append("")

    lines.extend(
        [
            "## Top-K agreement matrix",
            "",
            _matrix_markdown(top_mat),
            "",
            "## Full rank-list agreement matrix",
            "",
            _matrix_markdown(full_mat),
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
        ref_id = "vector"
        if ref_id in results:
            for eid, rdf in sorted(results.items()):
                if eid == ref_id:
                    continue
                rate, m, n = top_k_agreement(results[ref_id], rdf)
                if rate < 1.0:
                    lines.append(f"### Deltas: `{ref_id}` vs `{eid}` top-K")
                    lines.append("")
                    merged = results[ref_id].merge(rdf, on="week_end", suffixes=("_a", "_b"))
                    diff = merged[merged["top_k_a"] != merged["top_k_b"]]
                    if diff.empty:
                        lines.append("_No top-K diffs (check full rank)._")
                    else:
                        lines.append("| week_end | top_k ref | top_k other |")
                        lines.append("|----------|-----------|-------------|")
                        for _, row in diff.head(20).iterrows():
                            lines.append(
                                f"| {row['week_end'].date()} | {row['top_k_a']} | {row['top_k_b']} |"
                            )
                    lines.append("")
    else:
        lines.append("All engines agree on weekly top-K and full rank order.")

    for eid in sorted(results.keys()):
        label = engine_labels().get(eid, eid)
        flat = rankings_to_compare_frame(results[eid])
        lines.extend(["", f"## Rank table — {label} `{eid}`", ""])
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
