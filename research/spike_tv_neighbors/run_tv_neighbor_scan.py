#!/usr/bin/env python3
"""
Mechanical TV σ* neighbor scan around baseline TV25 (B45+S20+LIVE1430).

Reads baseline from data/table_bead_baseline.csv; merges optional engine output.
Without engine CSV, emits placeholder neighbor rows (clearly tagged).
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parent
DATA = ROOT / "data"
DEFAULT_BASELINE_CSV = DATA / "table_bead_baseline.csv"

SIGMA_NEIGHBORS = (0.20, 0.22, 0.28, 0.30)
BASELINE_SIGMA = 0.25
BASELINE_BOOK = "LIVE1430-B45-S20"
BASELINE_BOOK_TV = "B45+S20-TV25"

METRIC_COLS = [
    "ret",
    "maxDD",
    "CAGR",
    "Calmar",
    "2020-22_ret",
    "2020-22_DD",
    "2020-22_Calmar",
    "2023-26_ret",
    "2023-26_DD",
    "2023-26_Calmar",
    "avgL",
    "cash_week_pct",
    "risk_on_week_pct",
]


def load_baseline(path: Path) -> pd.Series:
    df = pd.read_csv(path)
    row = df.loc[df["book"] == BASELINE_BOOK]
    if row.empty:
        raise SystemExit(f"baseline book {BASELINE_BOOK!r} not found in {path}")
    return row.iloc[0]


def placeholder_neighbors(baseline: pd.Series) -> pd.DataFrame:
    rows = []
    for sigma in SIGMA_NEIGHBORS:
        book = f"B45+S20-TV{int(round(sigma * 100)):02d}"
        rows.append(
            {
                "book": book,
                "sigma": sigma,
                "data_source": "placeholder/pending_engine",
                **{c: float("nan") for c in METRIC_COLS},
                "turnover": float("nan"),
            }
        )
    return pd.DataFrame(rows)


def baseline_row(baseline: pd.Series) -> dict:
    out = {
        "book": BASELINE_BOOK_TV,
        "sigma": BASELINE_SIGMA,
        "data_source": "real/uploads_table_bead",
    }
    for c in METRIC_COLS:
        out[c] = float(baseline[c]) if c in baseline.index else float("nan")
    # proxy: trades from NOB summary reference (same B45-S20 sim_stats)
    ref = DATA / "summary_reference.json"
    turnover_proxy = float("nan")
    if ref.exists():
        sim = json.loads(ref.read_text()).get("sim_stats", {})
        st = sim.get("LIVE1430-B45-S20", {})
        n_trades = st.get("n_trades")
        n_weeks = st.get("n_calendar_weeks_ex_last")
        if n_trades and n_weeks:
            turnover_proxy = n_trades / n_weeks
    out["turnover"] = turnover_proxy
    return out


def load_engine(path: Path) -> pd.DataFrame:
    df = pd.read_csv(path)
    required = {"book", "sigma", "ret", "maxDD", "Calmar", "2023-26_ret"}
    missing = required - set(df.columns)
    if missing:
        raise SystemExit(f"engine csv missing columns: {sorted(missing)}")
    if "data_source" not in df.columns:
        df["data_source"] = "real/engine"
    if "turnover" not in df.columns:
        df["turnover"] = float("nan")
    return df


def evaluate_h1(base: dict, neighbors: pd.DataFrame) -> dict:
    """Mechanical falsify per HYPOTHESIS.md."""
    b_ret = base["ret"]
    b_mdd = base["maxDD"]
    b_2326 = base["2023-26_ret"]
    b_abs_mdd = abs(b_mdd)

    falsified_by = []
    for _, r in neighbors.iterrows():
        if r["data_source"].startswith("placeholder"):
            continue
        if pd.isna(r["ret"]) or pd.isna(r["maxDD"]) or pd.isna(r["2023-26_ret"]):
            continue
        d_ret = r["ret"] - b_ret
        d_abs_mdd = abs(r["maxDD"]) - b_abs_mdd
        covers = d_ret >= d_abs_mdd
        no_miss_bull = r["2023-26_ret"] >= b_2326
        if covers and no_miss_bull:
            falsified_by.append(
                {
                    "book": r["book"],
                    "sigma": r["sigma"],
                    "d_ret": d_ret,
                    "d_abs_mdd": d_abs_mdd,
                    "2023-26_ret": r["2023-26_ret"],
                }
            )

    if falsified_by:
        return {
            "h1_holds": False,
            "verdict": "H1 证伪：邻域不平坦（见 falsified_by）",
            "falsified_by": falsified_by,
        }
    real_rows = neighbors[~neighbors["data_source"].str.startswith("placeholder")]
    if real_rows.empty:
        return {
            "h1_holds": None,
            "verdict": "H1 未判定：邻档无引擎真数据，仅基线 TV25 可引用",
            "falsified_by": [],
        }
    return {
        "h1_holds": True,
        "verdict": "H1 成立：无邻档同时满足 Δret 盖 Δ|MDD| 且 2023–26 不踏空",
        "falsified_by": [],
    }


def fmt_pct(x: float, kind: str) -> str:
    if pd.isna(x):
        return "—"
    if kind == "ret":
        return f"{100 * x:.1f}%"
    if kind == "dd":
        return f"{100 * x:.1f}%"
    if kind == "ratio":
        return f"{x:.3f}"
    if kind == "turnover":
        return f"{x:.2f}/wk"
    return str(x)


def write_main_table(path: Path, base: dict, neighbors: pd.DataFrame, eval_out: dict) -> None:
    lines = [
        "# main_table — TV σ* 邻档 vs B45+S20-TV25",
        "",
        f"样本窗：2020-01-03 → 2026-10-23（基线来自 uploads；邻档见 `data_source`）",
        "",
        f"**机械结论**：{eval_out['verdict']}",
        "",
        "| book | σ* | ret | maxDD | Calmar | 2023–26 ret | 2023–26 Calmar | turnover | data_source |",
        "|------|-----|-----|-------|--------|-------------|----------------|----------|-------------|",
    ]

    def row_line(d: dict) -> str:
        return (
            f"| {d['book']} | {d['sigma']:.2f} | "
            f"{fmt_pct(d['ret'], 'ret')} | {fmt_pct(d['maxDD'], 'dd')} | "
            f"{fmt_pct(d['Calmar'], 'ratio')} | "
            f"{fmt_pct(d['2023-26_ret'], 'ret')} | "
            f"{fmt_pct(d['2023-26_Calmar'], 'ratio')} | "
            f"{fmt_pct(d.get('turnover', float('nan')), 'turnover')} | "
            f"{d['data_source']} |"
        )

    lines.append(row_line(base))
    for _, r in neighbors.sort_values("sigma").iterrows():
        lines.append(row_line(r.to_dict()))

    lines.extend(
        [
            "",
            "## 相对 TV25（仅 real 行可算 Δ）",
            "",
            "| book | Δret (pp) | Δ|MDD| (pp) | ΔCalmar | 盖回撤? | 2023–26≥基线? |",
            "|------|-----------|-------------|---------|---------|---------------|",
        ]
    )
    b_ret, b_abs = base["ret"], abs(base["maxDD"])
    b_c, b_2326 = base["Calmar"], base["2023-26_ret"]
    for _, r in neighbors.sort_values("sigma").iterrows():
        if str(r["data_source"]).startswith("placeholder") or pd.isna(r["ret"]):
            lines.append(f"| {r['book']} | — | — | — | — | — |")
            continue
        d_ret_pp = 100 * (r["ret"] - b_ret)
        d_abs_pp = 100 * (abs(r["maxDD"]) - b_abs)
        d_cal = r["Calmar"] - b_c
        covers = "Y" if (r["ret"] - b_ret) >= (abs(r["maxDD"]) - b_abs) else "N"
        bull = "Y" if r["2023-26_ret"] >= b_2326 else "N"
        lines.append(
            f"| {r['book']} | {d_ret_pp:+.1f} | {d_abs_pp:+.1f} | {d_cal:+.3f} | {covers} | {bull} |"
        )

    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--baseline-csv", type=Path, default=DEFAULT_BASELINE_CSV)
    ap.add_argument("--engine-csv", type=Path, default=None)
    ap.add_argument("--out-json", type=Path, default=ROOT / "scan_result.json")
    ap.add_argument("--out-md", type=Path, default=ROOT / "main_table.md")
    args = ap.parse_args()

    baseline_s = load_baseline(args.baseline_csv)
    base = baseline_row(baseline_s)

    if args.engine_csv and args.engine_csv.exists():
        eng = load_engine(args.engine_csv)
        neighbors = eng[eng["sigma"].isin(SIGMA_NEIGHBORS)].copy()
        if neighbors.empty:
            neighbors = placeholder_neighbors(baseline_s)
    else:
        neighbors = placeholder_neighbors(baseline_s)

    eval_out = evaluate_h1(base, neighbors)
    write_main_table(args.out_md, base, neighbors, eval_out)

    payload = {
        "baseline_book": BASELINE_BOOK_TV,
        "sigma_neighbors": list(SIGMA_NEIGHBORS),
        "baseline": base,
        "neighbors": neighbors.to_dict(orient="records"),
        "evaluation": eval_out,
    }
    args.out_json.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")
    print(json.dumps({"verdict": eval_out["verdict"], "out_md": str(args.out_md)}, ensure_ascii=False))


if __name__ == "__main__":
    main()
