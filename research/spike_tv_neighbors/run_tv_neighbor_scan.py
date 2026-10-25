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
DEFAULT_ENGINE_CSV = DATA / "tv_neighbor_engine.csv"
DEFAULT_ENGINE_FULL_CSV = DATA / "tv_neighbor_engine_full.csv"
SAMPLE_WINDOW = "2020-01-03 → 2026-09-24"

SIGMA_NEIGHBORS = (0.20, 0.22, 0.28, 0.30)
SIGMA_ANNEX = (0.33,)  # H1 集外旁注（引擎有跑、不在 H1 四邻档）
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


def normalize_engine_df(df: pd.DataFrame) -> pd.DataFrame:
    df = df.copy()
    if "sigma_star" in df.columns:
        df["sigma"] = df["sigma_star"]
    if "turnover" not in df.columns:
        if "avg_turnover" in df.columns:
            df["turnover"] = df["avg_turnover"]
        elif "avg_turnover_1way" in df.columns:
            df["turnover"] = df["avg_turnover_1way"]
    if "data_source" not in df.columns:
        df["data_source"] = "real/engine_live1430_tv_neighbor"
    for c in METRIC_COLS:
        if c not in df.columns:
            df[c] = float("nan")
    return df


def load_engine(path: Path, full_path: Path | None = None) -> pd.DataFrame:
    if full_path and full_path.exists():
        df = normalize_engine_df(pd.read_csv(full_path))
    else:
        df = normalize_engine_df(pd.read_csv(path))
    compact = normalize_engine_df(pd.read_csv(path))
    missing_books = set(compact["book"]) - set(df["book"])
    if missing_books:
        df = pd.concat([df, compact.loc[compact["book"].isin(missing_books)]], ignore_index=True)
    required = {"book", "sigma", "ret", "maxDD", "Calmar", "2023-26_ret"}
    missing = required - set(df.columns)
    if missing:
        raise SystemExit(f"engine csv missing columns: {sorted(missing)}")
    return df


def row_from_engine(rec: pd.Series, display_book: str | None = None, sigma: float | None = None) -> dict:
    sig = sigma
    if sig is None:
        if "sigma" in rec.index and pd.notna(rec["sigma"]):
            sig = float(rec["sigma"])
        elif pd.notna(rec.name):
            sig = float(rec.name)
        else:
            sig = float("nan")
    out = {
        "book": display_book or rec["book"],
        "sigma": sig,
        "data_source": rec.get("data_source", "real/engine_live1430_tv_neighbor"),
    }
    for c in METRIC_COLS:
        out[c] = float(rec[c]) if c in rec.index and pd.notna(rec[c]) else float("nan")
    out["turnover"] = float(rec["turnover"]) if "turnover" in rec.index and pd.notna(rec["turnover"]) else float("nan")
    return out


def neighbors_from_engine(eng: pd.DataFrame) -> pd.DataFrame:
    rows = []
    by_sigma = eng.set_index("sigma")
    for sigma in SIGMA_NEIGHBORS:
        label = f"B45+S20-TV{int(round(sigma * 100)):02d}"
        if sigma in by_sigma.index:
            rows.append(row_from_engine(by_sigma.loc[sigma], display_book=label, sigma=sigma))
        else:
            rows.append(
                {
                    "book": label,
                    "sigma": sigma,
                    "data_source": "not_run/missing_engine_row",
                    **{c: float("nan") for c in METRIC_COLS},
                    "turnover": float("nan"),
                }
            )
    return pd.DataFrame(rows)


def annex_from_engine(eng: pd.DataFrame) -> pd.DataFrame:
    rows = []
    for sigma in SIGMA_ANNEX:
        sub = eng.loc[eng["sigma"] == sigma]
        if sub.empty:
            continue
        rec = sub.iloc[0]
        rows.append(row_from_engine(rec, display_book=f"B45+S20-TV{int(round(sigma * 100)):02d}"))
    return pd.DataFrame(rows)


def evaluate_h1(base: dict, neighbors: pd.DataFrame) -> dict:
    """Mechanical falsify per HYPOTHESIS.md."""
    b_ret = base["ret"]
    b_mdd = base["maxDD"]
    b_2326 = base["2023-26_ret"]
    b_abs_mdd = abs(b_mdd)

    falsified_by = []
    for _, r in neighbors.iterrows():
        src = str(r["data_source"])
        if src.startswith("placeholder") or src.startswith("not_run"):
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
        names = ", ".join(f"{x['book']}(σ*={x['sigma']:.2f})" for x in falsified_by)
        return {
            "h1_holds": False,
            "verdict": f"H1 证伪：邻域不平坦 — {names}",
            "falsified_by": falsified_by,
        }
    real_rows = neighbors[
        ~neighbors["data_source"].str.startswith("placeholder")
        & ~neighbors["data_source"].str.startswith("not_run")
    ]
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


def write_main_table(
    path: Path,
    base: dict,
    neighbors: pd.DataFrame,
    eval_out: dict,
    annex: pd.DataFrame | None = None,
) -> None:
    lines = [
        "# main_table — TV σ* 邻档 vs B45+S20-TV25",
        "",
        f"样本窗：{SAMPLE_WINDOW}（SPIKE-S20-TV22-LIVE1430 引擎；`data/tv_neighbor_engine_full.csv`）",
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
        src = str(r["data_source"])
        if src.startswith("placeholder") or src.startswith("not_run") or pd.isna(r["ret"]):
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

    if annex is not None and not annex.empty:
        lines.extend(
            [
                "",
                "## H1 集外旁注（引擎有跑，不参与 H1 四邻档判定）",
                "",
                "| book | σ* | ret | maxDD | Calmar | 2023–26 ret | turnover |",
                "|------|-----|-----|-------|--------|-------------|----------|",
            ]
        )
        for _, r in annex.sort_values("sigma").iterrows():
            lines.append(
                f"| {r['book']} | {r['sigma']:.2f} | {fmt_pct(r['ret'], 'ret')} | "
                f"{fmt_pct(r['maxDD'], 'dd')} | {fmt_pct(r['Calmar'], 'ratio')} | "
                f"{fmt_pct(r['2023-26_ret'], 'ret')} | {fmt_pct(r.get('turnover', float('nan')), 'turnover')} |"
            )

    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--baseline-csv", type=Path, default=DEFAULT_BASELINE_CSV)
    ap.add_argument("--engine-csv", type=Path, default=DEFAULT_ENGINE_CSV)
    ap.add_argument("--engine-full-csv", type=Path, default=DEFAULT_ENGINE_FULL_CSV)
    ap.add_argument("--out-json", type=Path, default=ROOT / "scan_result.json")
    ap.add_argument("--out-md", type=Path, default=ROOT / "main_table.md")
    args = ap.parse_args()

    annex = pd.DataFrame()
    if args.engine_csv.exists():
        eng = load_engine(args.engine_csv, args.engine_full_csv)
        base_row = eng.loc[eng["sigma"] == BASELINE_SIGMA]
        if base_row.empty:
            base_row = eng.loc[eng["book"] == BASELINE_BOOK]
        if base_row.empty:
            raise SystemExit("engine missing TV25 baseline row")
        base = row_from_engine(base_row.iloc[0], display_book=BASELINE_BOOK_TV)
        neighbors = neighbors_from_engine(eng)
        annex = annex_from_engine(eng)
    else:
        baseline_s = load_baseline(args.baseline_csv)
        base = baseline_row(baseline_s)
        neighbors = placeholder_neighbors(baseline_s)

    eval_out = evaluate_h1(base, neighbors)
    write_main_table(args.out_md, base, neighbors, eval_out, annex=annex)

    payload = {
        "sample_window": SAMPLE_WINDOW,
        "baseline_book": BASELINE_BOOK_TV,
        "sigma_neighbors": list(SIGMA_NEIGHBORS),
        "baseline": base,
        "neighbors": neighbors.to_dict(orient="records"),
        "annex": annex.to_dict(orient="records"),
        "evaluation": eval_out,
        "engine_sources": {
            "compact": str(args.engine_csv),
            "full": str(args.engine_full_csv),
            "summary": str(DATA / "tv22_summary.json"),
        },
    }
    args.out_json.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")
    print(json.dumps({"verdict": eval_out["verdict"], "out_md": str(args.out_md)}, ensure_ascii=False))


if __name__ == "__main__":
    main()
