#!/usr/bin/env python3
"""SPIKE-S20-SORTINO-STYLE-GRID-LIVE1430 — post-hoc Sortino beside Sharpe/Calmar.

Reuses frozen LIVE1430 nav from B45+S20 face (BTHETA B45) and neighbors:
  TV22 / TV28 / TV33 (TV grid), B40 / B50 (BTHETA grid) when artifacts exist.

Research only — no engine rerun, no LIVE/champion/strategy_exec.
"""
from __future__ import annotations

import json
import math
import time
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parent
KIT = ROOT.parent / "CLOUD-BATCH-2026-10-26"
KNIFE_MD = KIT / "knives" / "SPIKE-S20-SORTINO-STYLE-GRID-LIVE1430.md"
BTHETA = ROOT.parent / "SPIKE-S20-BTHETA-GRID-LIVE1430"
TVGRID = ROOT.parent / "SPIKE-S20-TV-GRID-LIVE1430"

EVAL_START = "2020-01-03"
ANN = 252


def load_returns(path: Path) -> pd.Series:
    """Load daily return series from nav_* artifact (nav level or daily r)."""
    df = pd.read_csv(path)
    cols = list(df.columns)
    date_col = cols[0]
    val_col = "r" if "r" in cols else ("nav" if "nav" in cols else cols[1])
    idx = pd.to_datetime(df[date_col].astype(str).str[:10])
    s = pd.Series(df[val_col].astype(float).values, index=idx, name="r")
    s = s[~s.index.duplicated(keep="last")].sort_index()
    s = s.loc[s.index >= pd.Timestamp(EVAL_START)]
    if val_col == "r" or (s.abs().quantile(0.99) < 0.35 and s.abs().max() < 0.99):
        return s.replace([np.inf, -np.inf], np.nan).dropna()
    nav = s
    r = nav.pct_change().dropna()
    return r.replace([np.inf, -np.inf], np.nan).dropna()


def returns_to_nav(r: pd.Series) -> pd.Series:
    return (1 + r).cumprod()


def stats_full(r: pd.Series) -> dict[str, float]:
    if r is None or len(r) < 2:
        nan = float("nan")
        return {"ret": nan, "maxDD": nan, "CAGR": nan, "Calmar": nan, "Sharpe": nan, "Sortino": nan}
    q = (1 + r).cumprod()
    ret = float(q.iloc[-1] - 1)
    dd = float((q / q.cummax().clip(lower=1e-12) - 1).min())
    n = (r.index[-1] - r.index[0]).days
    cagr = (1 + ret) ** (365.25 / n) - 1 if n > 0 and (1 + ret) > 0 else float("nan")
    cal = cagr / abs(dd) if dd < 0 else float("nan")
    sharpe = sharpe_ann(r)
    sortino = sortino_ann(r)
    return {"ret": ret, "maxDD": dd, "CAGR": cagr, "Calmar": cal, "Sharpe": sharpe, "Sortino": sortino}


def sharpe_ann(r: pd.Series, rf_daily: float = 0.0) -> float:
    x = r - rf_daily
    sd = float(x.std())
    if sd <= 0 or len(x) < 2:
        return float("nan")
    return float(x.mean() / sd * math.sqrt(ANN))


def sortino_ann(r: pd.Series, rf_daily: float = 0.0) -> float:
    """Downside vol Sortino; rf=0 → target return 0."""
    x = r - rf_daily
    downside = np.minimum(x.values, 0.0)
    dd_vol = float(np.sqrt(np.mean(downside ** 2)))
    if dd_vol <= 0 or len(x) < 2:
        return float("nan")
    return float(x.mean() / dd_vol * math.sqrt(ANN))


def segment_stats(r: pd.Series, start: str, end: str | None) -> dict[str, float]:
    mask = r.index >= pd.Timestamp(start)
    if end:
        mask &= r.index <= pd.Timestamp(end)
    sub = r.loc[mask]
    return stats_full(sub) if len(sub) > 5 else {k: float("nan") for k in stats_full(r[:2])}


def pct(x: float | None) -> str:
    if x is None or (isinstance(x, float) and (math.isnan(x) or math.isinf(x))):
        return "—"
    return f"{100 * x:.1f}%"


BOOK_SPECS: list[tuple[str, str, str, Path]] = [
    ("face", "B45+S20", "LIVE1430-B45-S20-max5", BTHETA / "nav_LIVE1430-B45-S20-max5.csv"),
    ("breadth", "B40", "LIVE1430-B40-S20-max5", BTHETA / "nav_LIVE1430-B40-S20-max5.csv"),
    ("breadth", "B50", "LIVE1430-B50-S20-max5", BTHETA / "nav_LIVE1430-B50-S20-max5.csv"),
    ("tv", "TV22", "LIVE1430-TV22-S20", TVGRID / "nav_LIVE1430-TV22-S20.csv"),
    ("tv", "TV28", "LIVE1430-TV28-S20", TVGRID / "nav_LIVE1430-TV28-S20.csv"),
    ("tv", "TV33", "LIVE1430-TV33-S20", TVGRID / "nav_LIVE1430-TV33-S20.csv"),
]


def main() -> None:
    ROOT.mkdir(parents=True, exist_ok=True)
    t0 = time.time()
    rows: list[dict] = []
    nav_map: dict[str, pd.Series] = {}
    missing: list[str] = []

    for axis, label, book, nav_path in BOOK_SPECS:
        if not nav_path.exists():
            missing.append(str(nav_path.relative_to(ROOT.parent)))
            continue
        r = load_returns(nav_path)
        nav = returns_to_nav(r)
        st = stats_full(r)
        s2022 = segment_stats(r, "2020-01-01", "2022-12-31")
        s2023 = segment_stats(r, "2023-01-01", None)
        row = {
            "axis": axis,
            "label": label,
            "book": book,
            "nav_source": str(nav_path.relative_to(ROOT.parent)),
            **st,
            "2020-22_ret": s2022["ret"],
            "2020-22_DD": s2022["maxDD"],
            "2020-22_Calmar": s2022["Calmar"],
            "2020-22_Sharpe": s2022["Sharpe"],
            "2020-22_Sortino": s2022["Sortino"],
            "2023-26_ret": s2023["ret"],
            "2023-26_DD": s2023["maxDD"],
            "2023-26_Calmar": s2023["Calmar"],
            "2023-26_Sharpe": s2023["Sharpe"],
            "2023-26_Sortino": s2023["Sortino"],
            "nav_end": str(nav.index[-1].date()),
            "n_days": len(r),
        }
        rows.append(row)
        nav_map[book] = nav
        print(
            f"{book}: Sharpe={st['Sharpe']:.2f} Sortino={st['Sortino']:.2f} "
            f"Calmar={st['Calmar']:.2f} ret={pct(st['ret'])}",
            flush=True,
        )

    if not rows:
        raise SystemExit("no nav artifacts found; need BTHETA and/or TV grid outputs")

    df = pd.DataFrame(rows)
    df.to_csv(ROOT / "style_grid_dump.csv", index=False)
    df.to_csv(ROOT / "metrics.csv", index=False)

    face = df[df["axis"] == "face"].iloc[0] if (df["axis"] == "face").any() else None

    # equity curve (normalized) for face + neighbors present
    fig, ax = plt.subplots(figsize=(10, 5))
    styles = {
        "LIVE1430-B45-S20-max5": ("#1A1917", "-", 2.2),
        "LIVE1430-B40-S20-max5": ("#6B7280", "--", 1.2),
        "LIVE1430-B50-S20-max5": ("#2563EB", "--", 1.2),
        "LIVE1430-TV22-S20": ("#059669", "-.", 1.3),
        "LIVE1430-TV28-S20": ("#D97706", "-.", 1.3),
        "LIVE1430-TV33-S20": ("#DC2626", "-.", 1.3),
    }
    for book, nav in nav_map.items():
        n = nav / nav.iloc[0]
        c, ls, lw = styles.get(book, ("#444", "-", 1.0))
        tag = "face" if book == "LIVE1430-B45-S20-max5" else book.replace("LIVE1430-", "")
        ax.plot(n.index, n.values, color=c, ls=ls, lw=lw, label=tag)
    ax.set_title("SPIKE-S20 LIVE1430 · face + neighbors (nav reuse)")
    ax.set_ylabel("NAV (norm=1)")
    ax.legend(loc="upper left", fontsize=8)
    ax.grid(True, alpha=0.25)
    fig.tight_layout()
    fig.savefig(ROOT / "equity_curve.png", dpi=140)
    plt.close(fig)

    criterion_src = KNIFE_MD.read_text(encoding="utf-8") if KNIFE_MD.exists() else ""
    (ROOT / "criterion.md").write_text(
        "# Criterion · SPIKE-S20-SORTINO-STYLE-GRID-LIVE1430\n\n" + criterion_src + "\n",
        encoding="utf-8",
    )

    # ranking vs face
    notes: list[str] = []
    if face is not None:
        f_cal, f_sor = float(face["Calmar"]), float(face["Sortino"])
        for _, r in df[df["book"] != face["book"]].iterrows():
            dcal = float(r["Calmar"]) - f_cal
            dsor = float(r["Sortino"]) - f_sor
            if dcal > 0.05 and dsor > 0.05:
                notes.append(f"{r['label']} 同时在 Calmar/Sortino 上高于 face（ΔCalmar={dcal:+.2f} ΔSortino={dsor:+.2f}）")

    summary = {
        "knife_id": "SPIKE-S20-SORTINO-STYLE-GRID-LIVE1430",
        "window": f"{EVAL_START} → {df['nav_end'].max()}",
        "cost_rt": 0.002,
        "rf_sortino": 0.0,
        "books_n": len(df),
        "missing_artifacts": missing,
        "face_book": face["book"] if face is not None else None,
        "face": face.to_dict() if face is not None else None,
        "rank_notes": notes,
        "elapsed_s": round(time.time() - t0, 1),
    }
    (ROOT / "summary.json").write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")

    md_lines = [
        "# REPORT · SPIKE-S20-SORTINO-STYLE-GRID-LIVE1430（Sortino 邻域对照）",
        "",
        "## 1. 准则原文",
        "",
        "```",
        criterion_src.strip(),
        "```",
        "",
        "## 2. 实现要点",
        "",
        "- **不重跑引擎**：直接读取 BTHETA / TV-GRID 已冻结 **nav**（含 Fri≥14:30 face、0.2%RT、L≤1）。",
        "- **Sharpe / Sortino**：日收益；年化 √252；Sortino 下行偏差 sqrt(mean(min(r,0)²))，**rf=0**。",
        "- **Calmar**：CAGR/|maxDD|（与 BTHETA 主表同口径）。",
        "- **红线**：仅 `research/cloud_batch/...`；不换冠；不写 strategy_exec / LIVE。",
        "",
    ]
    if missing:
        md_lines += ["### 缺失产物（已跳过）", "", *[f"- `{m}`" for m in missing], ""]

    md_lines += [
        "## 3. 主表 · style grid（Sharpe / Sortino / Calmar）",
        "",
        "| axis | label | book | ret | maxDD | CAGR | Sharpe | Sortino | Calmar | 2020–22 S/Sor/Cal | 2023–26 S/Sor/Cal |",
        "|---|---|---|---:|---:|---:|---:|---:|---:|---|---|",
    ]
    for _, r in df.iterrows():
        face_mark = " **face**" if r["axis"] == "face" else ""
        md_lines.append(
            f"| {r['axis']} | {r['label']}{face_mark} | {r['book']} | {pct(r['ret'])} | {pct(r['maxDD'])} | "
            f"{pct(r['CAGR'])} | {r['Sharpe']:.2f} | {r['Sortino']:.2f} | {r['Calmar']:.2f} | "
            f"{r['2020-22_Sharpe']:.2f}/{r['2020-22_Sortino']:.2f}/{r['2020-22_Calmar']:.2f} | "
            f"{r['2023-26_Sharpe']:.2f}/{r['2023-26_Sortino']:.2f}/{r['2023-26_Calmar']:.2f} |"
        )

    if face is not None:
        best_cal = df.loc[df["Calmar"].idxmax()]
        best_sor = df.loc[df["Sortino"].idxmax()]
        md_lines += [
            "",
            f"**Calmar 最高**：{best_cal['book']}（{best_cal['Calmar']:.2f}）。",
            f"**Sortino 最高**：{best_sor['book']}（{best_sor['Sortino']:.2f}）。",
            f"**Face（B45+S20）**：Sharpe {face['Sharpe']:.2f} · Sortino {face['Sortino']:.2f} · Calmar {face['Calmar']:.2f}。",
        ]
        if notes:
            md_lines += ["", "### 相对 face 旁注", ""] + [f"- {n}" for n in notes]

    md_lines += [
        "",
        "## 4. 产物",
        "",
        "- `style_grid_dump.csv` / `metrics.csv` / `summary.json`",
        "- `run.py` / `criterion.md` / `REPORT.md` / `equity_curve.png`",
        "",
    ]
    (ROOT / "REPORT.md").write_text("\n".join(md_lines), encoding="utf-8")
    print(f"done in {time.time()-t0:.1f}s → {ROOT}", flush=True)


if __name__ == "__main__":
    main()
