#!/usr/bin/env python3
"""
TV σ* threshold neighbors on spike face: TV22 / TV28 / TV33 vs baseline TV25.

Frozen: B45 + spike_ft max5 + S20 + E0 + LIVE1430 + 0.2%RT + L≤1.
Research only — no champion swap.
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parent
SIBLING_DATA = ROOT.parent / "spike_tv_neighbors" / "data"
DATA = SIBLING_DATA if SIBLING_DATA.exists() else ROOT / "data"

DEFAULT_ENGINE_CSV = DATA / "tv_neighbor_engine.csv"
DEFAULT_ENGINE_FULL_CSV = DATA / "tv_neighbor_engine_full.csv"
SAMPLE_WINDOW = "2020-01-03 → 2026-09-24"

# Spike-face threshold ring (promotes TV33 into H1 set; drops TV20/TV30)
SIGMA_NEIGHBORS = (0.22, 0.28, 0.33)
BASELINE_SIGMA = 0.25
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


def load_engine(path: Path, full_path: Path | None) -> pd.DataFrame:
    if full_path and full_path.exists():
        df = normalize_engine_df(pd.read_csv(full_path))
    else:
        df = normalize_engine_df(pd.read_csv(path))
    compact = normalize_engine_df(pd.read_csv(path))
    missing_books = set(compact["book"].astype(str)) - set(df["book"].astype(str))
    if missing_books:
        df = pd.concat([df, compact.loc[compact["book"].isin(missing_books)]], ignore_index=True)
    return df


def row_from_engine(rec: pd.Series, display_book: str, sigma: float) -> dict:
    out = {
        "book": display_book,
        "sigma": sigma,
        "data_source": rec.get("data_source", "real/engine_live1430_tv_neighbor"),
    }
    for c in METRIC_COLS:
        out[c] = float(rec[c]) if c in rec.index and pd.notna(rec[c]) else float("nan")
    out["turnover"] = (
        float(rec["turnover"]) if "turnover" in rec.index and pd.notna(rec["turnover"]) else float("nan")
    )
    return out


def neighbors_from_engine(eng: pd.DataFrame) -> pd.DataFrame:
    by_sigma = eng.set_index("sigma")
    rows = []
    for sigma in SIGMA_NEIGHBORS:
        label = f"B45+S20-TV{int(round(sigma * 100)):02d}"
        if sigma in by_sigma.index:
            rows.append(row_from_engine(by_sigma.loc[sigma], label, sigma))
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


def evaluate_h1(base: dict, neighbors: pd.DataFrame) -> dict:
    b_ret, b_abs_mdd, b_2326 = base["ret"], abs(base["maxDD"]), base["2023-26_ret"]
    falsified_by = []
    for _, r in neighbors.iterrows():
        src = str(r["data_source"])
        if src.startswith("not_run") or pd.isna(r["ret"]) or pd.isna(r["maxDD"]) or pd.isna(r["2023-26_ret"]):
            continue
        d_ret = r["ret"] - b_ret
        d_abs_mdd = abs(r["maxDD"]) - b_abs_mdd
        if d_ret >= d_abs_mdd and r["2023-26_ret"] >= b_2326:
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
        return {"h1_holds": False, "verdict": f"H1 证伪：阈值邻域不平坦 — {names}", "falsified_by": falsified_by}
    real = neighbors[~neighbors["data_source"].str.startswith("not_run")]
    if real.empty or real["ret"].isna().all():
        return {"h1_holds": None, "verdict": "H1 未判定：缺引擎行", "falsified_by": []}
    return {
        "h1_holds": True,
        "verdict": "H1 成立：TV22/TV28/TV33 无档同时盖回撤且不踏空",
        "falsified_by": [],
    }


def fmt_pct(x: float, kind: str) -> str:
    if pd.isna(x):
        return "—"
    if kind in ("ret", "dd"):
        return f"{100 * x:.1f}%"
    if kind == "ratio":
        return f"{x:.3f}"
    if kind == "turnover":
        return f"{x:.2f}/wk"
    return str(x)


def write_main_table(path: Path, base: dict, neighbors: pd.DataFrame, eval_out: dict) -> None:
    lines = [
        "# main_table — spike face TV 阈值邻档（TV22 / TV28 / TV33）vs TV25",
        "",
        f"冻结面层：**B45 + spike_ft max5 + S20 + E0**；样本窗 {SAMPLE_WINDOW}。",
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
            "## 相对 TV25",
            "",
            "| book | Δret (pp) | Δ|MDD| (pp) | ΔCalmar | 盖回撤? | 2023–26≥基线? | 对照既有记注 |",
            "|------|-----------|-------------|---------|---------|---------------|--------------|",
        ]
    )
    b_ret, b_abs, b_c, b_2326 = base["ret"], abs(base["maxDD"]), base["Calmar"], base["2023-26_ret"]
    notes = {
        "B45+S20-TV22": "E08 证伪降 σ*（tv22_summary）",
        "B45+S20-TV28": "邻域上档；本扫记正（盖回撤+后段）",
        "B45+S20-TV33": "E09 记正腿（EXTEND-REBASE 清单 #3）",
    }
    for _, r in neighbors.sort_values("sigma").iterrows():
        if str(r["data_source"]).startswith("not_run") or pd.isna(r["ret"]):
            lines.append(f"| {r['book']} | — | — | — | — | — | {notes.get(r['book'], '')} |")
            continue
        d_ret_pp = 100 * (r["ret"] - b_ret)
        d_abs_pp = 100 * (abs(r["maxDD"]) - b_abs)
        covers = "Y" if (r["ret"] - b_ret) >= (abs(r["maxDD"]) - b_abs) else "N"
        bull = "Y" if r["2023-26_ret"] >= b_2326 else "N"
        lines.append(
            f"| {r['book']} | {d_ret_pp:+.1f} | {d_abs_pp:+.1f} | "
            f"{r['Calmar'] - b_c:+.3f} | {covers} | {bull} | {notes.get(r['book'], '')} |"
        )
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--engine-csv", type=Path, default=DEFAULT_ENGINE_CSV)
    ap.add_argument("--engine-full-csv", type=Path, default=DEFAULT_ENGINE_FULL_CSV)
    ap.add_argument("--out-json", type=Path, default=ROOT / "scan_result.json")
    ap.add_argument("--out-md", type=Path, default=ROOT / "main_table.md")
    args = ap.parse_args()

    if not args.engine_csv.exists():
        raise SystemExit(f"engine csv missing: {args.engine_csv}")

    eng = load_engine(args.engine_csv, args.engine_full_csv)
    base_row = eng.loc[eng["sigma"] == BASELINE_SIGMA]
    if base_row.empty:
        raise SystemExit("engine missing TV25 baseline")
    base = row_from_engine(base_row.iloc[0], BASELINE_BOOK_TV, BASELINE_SIGMA)
    neighbors = neighbors_from_engine(eng)
    eval_out = evaluate_h1(base, neighbors)
    write_main_table(args.out_md, base, neighbors, eval_out)

    payload = {
        "pack": "spike_tv_face_threshold_four_pack",
        "sample_window": SAMPLE_WINDOW,
        "frozen_face": "B45 + spike_ft max5 + S20 + E0 + LIVE1430 + 0.2%RT + L≤1",
        "baseline_book": BASELINE_BOOK_TV,
        "sigma_neighbors": list(SIGMA_NEIGHBORS),
        "champion_swap": False,
        "baseline": base,
        "neighbors": neighbors.to_dict(orient="records"),
        "evaluation": eval_out,
        "engine_sources": {
            "compact": str(args.engine_csv),
            "full": str(args.engine_full_csv),
            "summary": str(DATA / "tv22_summary.json"),
        },
        "cross_ref": "../spike_tv_neighbors",
    }
    args.out_json.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")
    print(json.dumps({"verdict": eval_out["verdict"], "out_md": str(args.out_md)}, ensure_ascii=False))


if __name__ == "__main__":
    main()
