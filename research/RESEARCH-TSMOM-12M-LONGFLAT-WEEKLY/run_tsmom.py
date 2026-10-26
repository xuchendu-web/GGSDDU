#!/usr/bin/env python3
"""RESEARCH-TSMOM-12M-LONGFLAT-WEEKLY — Moskowitz TSMOM on research ETF pool."""
from __future__ import annotations

import json
import sys
from pathlib import Path

import numpy as np
import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import pandas as pd

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT / "engine"))

from panel import load_panel  # noqa: E402
from tsmom_backtest import (  # noqa: E402
    exploration_ruler_vs_face,
    run_backtest,
    scorecard_row,
    stats,
)

OUT = ROOT
DATA = ROOT / "data"
POOL_CSV = Path("/workspace/etf-correlation/data/research_pool_v2.csv")
FACE_CSV = DATA / "b45_face_reference.csv"
START, END = "2020-01-03", "2026-10-16"

CASH_CODES = frozenset({"511880", "511010", "511260"})


def research_universe(panel: dict) -> list[str]:
    codes = set(panel["codes"])
    if POOL_CSV.exists():
        pool = pd.read_csv(POOL_CSV, dtype={"code": str})
        pool["code"] = pool.code.str.zfill(6)
        codes &= set(pool["code"])
    return sorted(c for c in codes if c not in CASH_CODES)


def main() -> None:
    print("Building panel…", flush=True)
    pkl = Path("/workspace/research/cloud_batch/panel/mf_panel_v1.pkl")
    panel = load_panel(force=not pkl.exists())
    uni = research_universe(panel)
    print(f"Universe n={len(uni)}", flush=True)

    face = pd.read_csv(FACE_CSV).iloc[0].to_dict()

    books: list[dict] = []
    navs: dict[str, pd.Series] = {}

    specs = [
        ("TSMOM-12M-max5", "12m", "max5", False),
        ("TSMOM-12M-allpos", "12m", "all_pos", False),
        ("TSMOM-6M-max5", "6m", "max5", False),
        ("TSMOM-9M-max5", "9m", "max5", False),
    ]
    side_vol: list[dict] = []

    for book, lb, seat, vol in specs:
        r, meta = run_backtest(panel, lb_key=lb, seat=seat, vol_scale=vol, universe=uni)
        row = scorecard_row(book, r, meta)
        row["lookback"] = lb
        row["seat"] = seat
        row.update(exploration_ruler_vs_face(row, face))
        books.append(row)
        navs[book] = (1 + r).cumprod()

    # vol-scale side table (12m max5 only)
    for vol in (True,):
        book = "TSMOM-12M-max5-vol12"
        r, meta = run_backtest(panel, lb_key="12m", seat="max5", vol_scale=True, universe=uni)
        row = scorecard_row(book, r, meta)
        row["lookback"] = "12m"
        row["seat"] = "max5"
        row["vol_scale"] = True
        side_vol.append(row)
        navs[book] = (1 + r).cumprod()

    df = pd.DataFrame(books)
    face_row = {"book": "B45+S20-LIVE1430-face"}
    for c in df.columns:
        if c == "book":
            continue
        face_row[c] = face.get(c, float("nan"))
    face_row["Sharpe"] = float("nan")
    face_row["Sortino"] = float("nan")
    face_row["turnover"] = float("nan")
    face_row["falsified"] = False
    face_row["ruler_cover"] = True
    face_row["strong_seg_miss"] = False
    face_row["delta_ret"] = 0.0
    face_row["delta_abs_mdd"] = 0.0

    scorecard = pd.concat([pd.DataFrame([face_row]), df], ignore_index=True)
    scorecard.to_csv(OUT / "scorecard.csv", index=False)

    pd.DataFrame(side_vol).to_csv(OUT / "vol_scale_side_table.csv", index=False)

    primary = df[df["book"] == "TSMOM-12M-max5"].iloc[0]
    verdict = "FALSIFIED" if primary["falsified"] else "EXPLORATION_HOLD"
    def _jsonify(obj):
        if isinstance(obj, dict):
            return {k: _jsonify(v) for k, v in obj.items()}
        if isinstance(obj, (np.bool_,)):
            return bool(obj)
        if isinstance(obj, (np.integer, np.floating)):
            return obj.item()
        if isinstance(obj, (bool, int, float, str)) or obj is None:
            return obj
        return float(obj)

    summary = _jsonify(
        {
            "knife_id": "RESEARCH-TSMOM-12M-LONGFLAT-WEEKLY",
            "window": f"{START} → {END}",
            "cost_rt": 0.002,
            "leverage_cap": 1.0,
            "universe_n": len(uni),
            "primary_book": "TSMOM-12M-max5",
            "verdict": verdict,
            "primary": {k: primary[k] for k in primary.index if k != "book"},
            "face_ref": {k: face[k] for k in face if k != "book"},
        }
    )
    (OUT / "summary.json").write_text(json.dumps(summary, indent=2, ensure_ascii=False), encoding="utf-8")

    # NAV chart
    fig, ax = plt.subplots(figsize=(10, 5))
    for book in ("TSMOM-12M-max5", "TSMOM-12M-allpos"):
        if book in navs:
            navs[book].plot(ax=ax, label=book)
    ax.set_title("TSMOM vs research window (weekly, 0.2% RT)")
    ax.legend()
    ax.grid(True, alpha=0.3)
    fig.tight_layout()
    fig.savefig(OUT / "nav_primary.png", dpi=120)
    plt.close(fig)

    nav_out = pd.DataFrame({k: v for k, v in navs.items() if k.startswith("TSMOM-12M")})
    nav_out.to_csv(OUT / "nav_daily.csv")

    write_report(scorecard, side_vol, summary, verdict)
    print(scorecard.to_string(index=False))
    print("VERDICT:", verdict)


def write_report(scorecard: pd.DataFrame, side_vol: list, summary: dict, verdict: str) -> None:
    p = scorecard[scorecard["book"] == "TSMOM-12M-max5"].iloc[0]
    f = scorecard[scorecard["book"] == "B45+S20-LIVE1430-face"].iloc[0]

    def pct(x):
        return f"{100 * x:.1f}%" if pd.notna(x) else "—"

    report = f"""# REPORT · RESEARCH-TSMOM-12M-LONGFLAT-WEEKLY

## 结论
**{verdict}**（主刀 TSMOM-12M-max5 vs B45+S20 研究面）

## 主表（scorecard vs B45 face）
| book | ret | maxDD | Calmar | Sharpe | Sortino | 2020–22 ret | 2023–26 ret | turnover |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| B45+S20 face（参照） | {pct(f['ret'])} | {pct(f['maxDD'])} | {f['Calmar']:.2f} | — | — | {pct(f['2020-22_ret'])} | {pct(f['2023-26_ret'])} | — |
| **TSMOM-12M-max5** | {pct(p['ret'])} | {pct(p['maxDD'])} | {p['Calmar']:.2f} | {p['Sharpe']:.2f} | {p['Sortino']:.2f} | {pct(p['2020-22_ret'])} | {pct(p['2023-26_ret'])} | {p['turnover']:.1f}x |
| TSMOM-12M-allpos | {pct(scorecard.loc[scorecard.book=='TSMOM-12M-allpos','ret'].iloc[0])} | {pct(scorecard.loc[scorecard.book=='TSMOM-12M-allpos','maxDD'].iloc[0])} | {scorecard.loc[scorecard.book=='TSMOM-12M-allpos','Calmar'].iloc[0]:.2f} | — | — | — | — | — |

## 探索尺子
- Δret vs face: {pct(p['delta_ret'])}；Δ|MDD|: {pct(p['delta_abs_mdd'])}
- 尺子盖住（Δret ≥ Δ|MDD|）: **{p['ruler_cover']}**
- 2023–26 踏空（< face×0.85）: **{p['strong_seg_miss']}**

## 邻档 & 旁注
见 `scorecard.csv`（6M/9M max5）；波动率缩放 12% ann 见 `vol_scale_side_table.csv`。

## 实现
- 信号：日频收盘价 {summary['window']} 回看 6/9/12 月总收益 >0 则 risk-on，否则现金。
- 调仓：研究周历（510300 week grid）；0.2% RT；L≤1。
- 主刀权重：正动量按 12m 收益取前 5 等权；对照 all-positive 等权全持。

产物目录：`research/RESEARCH-TSMOM-12M-LONGFLAT-WEEKLY/`
"""
    (OUT / "REPORT.md").write_text(report, encoding="utf-8")


if __name__ == "__main__":
    main()
