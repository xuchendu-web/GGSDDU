#!/usr/bin/env python3
"""
Mechanical breadth θ neighbor scan around baseline B45 (spike_ft max5 + S20 + TV25).

Reads engine metrics from data/btheta_neighbor_engine.csv; emits main_table.md + scan_result.json.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parent
DATA = ROOT / "data"
DEFAULT_ENGINE_CSV = DATA / "btheta_neighbor_engine.csv"
DEFAULT_YEARLY_CSV = DATA / "yearly_b40_b50.csv"
SAMPLE_WINDOW = "2020-01-03 → 2026-10-23"

THETA_NEIGHBORS = (0.40, 0.50)
THETA_ANNEX = (0.55,)
BASELINE_THETA = 0.45
BASELINE_BOOK_ENGINE = "LIVE1430-B45-S20-max5"
BASELINE_BOOK_DISPLAY = "B45+S20+TV25-max5"

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


def display_book(theta: float) -> str:
    pct = int(round(theta * 100))
    return f"B{pct}+S20+TV25-max5"


def load_engine(path: Path) -> pd.DataFrame:
    df = pd.read_csv(path)
    required = {"book", "theta", "ret", "maxDD", "Calmar", "2023-26_ret"}
    missing = required - set(df.columns)
    if missing:
        raise SystemExit(f"engine csv missing columns: {sorted(missing)}")
    if "data_source" not in df.columns:
        df["data_source"] = "real/engine_live1430_btheta_grid"
    if "turnover" not in df.columns:
        df["turnover"] = float("nan")
    return df


def row_from_engine(rec: pd.Series, label: str | None = None, theta: float | None = None) -> dict:
    if theta is None:
        if "theta" in rec.index and pd.notna(rec["theta"]):
            theta = float(rec["theta"])
        elif pd.notna(rec.name):
            theta = float(rec.name)
        else:
            theta = float("nan")
    out = {
        "book": label or display_book(theta),
        "theta": theta,
        "engine_book": rec["book"],
        "data_source": rec.get("data_source", "real/engine_live1430_btheta_grid"),
    }
    for c in METRIC_COLS:
        out[c] = float(rec[c]) if c in rec.index and pd.notna(rec[c]) else float("nan")
    out["turnover"] = float(rec["turnover"]) if pd.notna(rec.get("turnover")) else float("nan")
    return out


def neighbors_from_engine(eng: pd.DataFrame) -> pd.DataFrame:
    by_theta = eng.set_index("theta")
    rows = []
    for theta in THETA_NEIGHBORS:
        if theta in by_theta.index:
            rows.append(row_from_engine(by_theta.loc[theta], label=display_book(theta), theta=theta))
        else:
            rows.append(
                {
                    "book": display_book(theta),
                    "theta": theta,
                    "engine_book": "",
                    "data_source": "not_run/missing_engine_row",
                    **{c: float("nan") for c in METRIC_COLS},
                    "turnover": float("nan"),
                }
            )
    return pd.DataFrame(rows)


def annex_from_engine(eng: pd.DataFrame) -> pd.DataFrame:
    rows = []
    for theta in THETA_ANNEX:
        sub = eng.loc[eng["theta"] == theta]
        if sub.empty:
            continue
        rows.append(row_from_engine(sub.iloc[0]))
    return pd.DataFrame(rows)


def evaluate_upgrade_candidates(base: dict, neighbors: pd.DataFrame) -> dict:
    """Mechanical upgrade vs B45: Δret covers Δ|MDD| and 2023–26 not missing bull."""
    b_ret = base["ret"]
    b_abs_mdd = abs(base["maxDD"])
    b_2326 = base["2023-26_ret"]
    upgraded = []
    for _, r in neighbors.iterrows():
        src = str(r["data_source"])
        if src.startswith("not_run") or pd.isna(r["ret"]):
            continue
        d_ret = r["ret"] - b_ret
        d_abs_mdd = abs(r["maxDD"]) - b_abs_mdd
        covers = d_ret >= d_abs_mdd
        no_miss_bull = r["2023-26_ret"] >= b_2326
        if covers and no_miss_bull:
            upgraded.append(
                {
                    "book": r["book"],
                    "theta": r["theta"],
                    "d_ret": d_ret,
                    "d_abs_mdd": d_abs_mdd,
                    "2023-26_ret": r["2023-26_ret"],
                }
            )
    return {"upgrade_candidates": upgraded}


def evaluate_neighbor_stability(eng: pd.DataFrame, yearly_path: Path) -> dict:
    """θ∈{0.40,0.45,0.50}: monotonic full-sample ret & Calmar; yearly B50−B45 sign churn."""
    core = eng.loc[eng["theta"].isin([0.40, 0.45, 0.50])].sort_values("theta")
    rets = core["ret"].tolist()
    calmars = core["Calmar"].tolist()
    ret_monotone = all(rets[i] <= rets[i + 1] for i in range(len(rets) - 1))
    calmar_monotone = all(calmars[i] <= calmars[i + 1] for i in range(len(calmars) - 1))
    best_theta = float(core.loc[core["Calmar"].idxmax(), "theta"])

    yearly = pd.read_csv(yearly_path) if yearly_path.exists() else pd.DataFrame()
    delta_signs = []
    if not yearly.empty and "delta_b50_vs_b45_pp" in yearly.columns:
        delta_signs = [1 if x > 0 else (-1 if x < 0 else 0) for x in yearly["delta_b50_vs_b45_pp"]]
    n_flip = sum(1 for i in range(1, len(delta_signs)) if delta_signs[i] != delta_signs[i - 1] and delta_signs[i] != 0 and delta_signs[i - 1] != 0)

    stable = ret_monotone and calmar_monotone and best_theta == 0.50
    verdict = (
        "θ↑ 全样本 ret/Calmar 单调，Calmar 峰在 B50"
        if stable
        else "单调或峰值检验未通过"
    )
    return {
        "ret_monotone_b40_b45_b50": ret_monotone,
        "calmar_monotone_b40_b45_b50": calmar_monotone,
        "best_calmar_theta": best_theta,
        "yearly_b50_minus_b45_sign_flips": n_flip,
        "stable": stable,
        "verdict": verdict,
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
    if kind == "theta":
        return f"{x:.2f}"
    return str(x)


def write_main_table(
    path: Path,
    base: dict,
    neighbors: pd.DataFrame,
    upgrade: dict,
    stability: dict,
    annex: pd.DataFrame | None = None,
) -> None:
    up_names = ", ".join(u["book"] for u in upgrade["upgrade_candidates"]) or "（无）"
    lines = [
        "# main_table — breadth θ 邻档 vs B45+S20+TV25-max5",
        "",
        f"样本窗：{SAMPLE_WINDOW}（`SPIKE-S20-BTHETA-GRID-LIVE1430` → `data/btheta_neighbor_engine.csv`）",
        "",
        f"**机械升格（相对 B45）**：{up_names}",
        "",
        f"**邻域稳定**：{stability['verdict']}",
        "",
        "| book | θ | ret | maxDD | Calmar | 2023–26 ret | 2023–26 Calmar | turnover | data_source |",
        "|------|-----|-----|-------|--------|-------------|----------------|----------|-------------|",
    ]

    def row_line(d: dict) -> str:
        return (
            f"| {d['book']} | {fmt_pct(d['theta'], 'theta')} | "
            f"{fmt_pct(d['ret'], 'ret')} | {fmt_pct(d['maxDD'], 'dd')} | "
            f"{fmt_pct(d['Calmar'], 'ratio')} | "
            f"{fmt_pct(d['2023-26_ret'], 'ret')} | "
            f"{fmt_pct(d['2023-26_Calmar'], 'ratio')} | "
            f"{fmt_pct(d.get('turnover', float('nan')), 'turnover')} | "
            f"{d['data_source']} |"
        )

    lines.append(row_line(base))
    for _, r in neighbors.sort_values("theta").iterrows():
        lines.append(row_line(r.to_dict()))

    lines.extend(
        [
            "",
            "## 相对 B45（Δ）",
            "",
            "| book | Δret (pp) | Δ|MDD| (pp) | ΔCalmar | 盖回撤? | 2023–26≥基线? |",
            "|------|-----------|-------------|---------|---------|---------------|",
        ]
    )
    b_ret, b_abs = base["ret"], abs(base["maxDD"])
    b_c, b_2326 = base["Calmar"], base["2023-26_ret"]
    for _, r in neighbors.sort_values("theta").iterrows():
        if pd.isna(r["ret"]):
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

    lines.extend(
        [
            "",
            "## 邻域稳定（B40→B45→B50）",
            "",
            f"- 全样本 ret 单调：{'Y' if stability['ret_monotone_b40_b45_b50'] else 'N'}",
            f"- 全样本 Calmar 单调：{'Y' if stability['calmar_monotone_b40_b45_b50'] else 'N'}",
            f"- Calmar 峰值 θ：{stability['best_calmar_theta']:.2f}",
            f"- 历年 Δ(B50−B45) 符号翻转次数：{stability['yearly_b50_minus_b45_sign_flips']}",
        ]
    )

    if annex is not None and not annex.empty:
        lines.extend(
            [
                "",
                "## 集外旁注（B55，不参与 B40/B45/B50 邻档判定）",
                "",
                "| book | θ | ret | maxDD | Calmar | 2023–26 ret |",
                "|------|-----|-----|-------|--------|-------------|",
            ]
        )
        for _, r in annex.sort_values("theta").iterrows():
            lines.append(
                f"| {r['book']} | {r['theta']:.2f} | {fmt_pct(r['ret'], 'ret')} | "
                f"{fmt_pct(r['maxDD'], 'dd')} | {fmt_pct(r['Calmar'], 'ratio')} | "
                f"{fmt_pct(r['2023-26_ret'], 'ret')} |"
            )

    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--engine-csv", type=Path, default=DEFAULT_ENGINE_CSV)
    ap.add_argument("--yearly-csv", type=Path, default=DEFAULT_YEARLY_CSV)
    ap.add_argument("--out-json", type=Path, default=ROOT / "scan_result.json")
    ap.add_argument("--out-md", type=Path, default=ROOT / "main_table.md")
    args = ap.parse_args()

    eng = load_engine(args.engine_csv)
    base_row = eng.loc[eng["theta"] == BASELINE_THETA]
    if base_row.empty:
        raise SystemExit(f"baseline theta {BASELINE_THETA} missing")
    base = row_from_engine(base_row.iloc[0], label=BASELINE_BOOK_DISPLAY)
    neighbors = neighbors_from_engine(eng)
    annex = annex_from_engine(eng)
    upgrade = evaluate_upgrade_candidates(base, neighbors)
    stability = evaluate_neighbor_stability(eng, args.yearly_csv)
    write_main_table(args.out_md, base, neighbors, upgrade, stability, annex=annex)

    payload = {
        "sample_window": SAMPLE_WINDOW,
        "baseline_book": BASELINE_BOOK_DISPLAY,
        "theta_neighbors": list(THETA_NEIGHBORS),
        "baseline": base,
        "neighbors": neighbors.to_dict(orient="records"),
        "annex": annex.to_dict(orient="records"),
        "upgrade_vs_b45": upgrade,
        "neighbor_stability": stability,
        "engine_source": "SPIKE-S20-BTHETA-GRID-LIVE1430/metrics.csv",
    }
    args.out_json.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(args.out_json)
    print(args.out_md)


if __name__ == "__main__":
    main()
