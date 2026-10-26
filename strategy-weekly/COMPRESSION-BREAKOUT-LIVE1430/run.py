#!/usr/bin/env python3
"""Four-pack: FACE + compression-breakout neighbors N∈{4,6,8}. Research pool only."""
from __future__ import annotations

import json
import sys
import time
from pathlib import Path

import matplotlib.pyplot as plt
import pandas as pd

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT.parent))

from _kit.face_engine import FaceConfig, run_book  # noqa: E402

OUT = ROOT
BOOKS = [
    ("FACE-B45-S20-LIVE1430", None),
    ("CB-N4", 4),
    ("CB-N6", 6),
    ("CB-N8", 8),
]


def delta_vs_face(row: dict, face: dict) -> dict:
    return {
        "delta_ret": row.get("ret", 0) - face.get("ret", 0),
        "delta_abs_mdd": abs(row.get("maxDD", 0)) - abs(face.get("maxDD", 0)),
        "delta_calmar": (row.get("Calmar") or 0) - (face.get("Calmar") or 0),
        "delta_hit_rate": (row.get("hit_rate") or 0) - (face.get("hit_rate") or 0),
        "delta_win_size": (row.get("win_size") or 0) - (face.get("win_size") or 0),
    }


def main() -> None:
    t0 = time.time()
    results = []
    nav_frames = {}
    for name, n in BOOKS:
        cfg = FaceConfig(compression_n=n)
        out = run_book(cfg)
        m = out["metrics"]
        m["book"] = name
        results.append(m)
        nav_frames[name] = out["nav"]
        out["nav"].to_csv(OUT / f"nav_{name.replace('/', '-')}.csv", header=True)
        out["entries"].to_csv(OUT / f"entries_{name.replace('/', '-')}.csv", index=False)

    face = next(r for r in results if r["compression_n"] is None)
    rows = []
    for r in results:
        d = delta_vs_face(r, face) if r["book"] != face["book"] else {
            "delta_ret": 0.0,
            "delta_abs_mdd": 0.0,
            "delta_calmar": 0.0,
            "delta_hit_rate": 0.0,
            "delta_win_size": 0.0,
        }
        rows.append({**r, **d})

    table = pd.DataFrame(rows)
    table.to_csv(OUT / "table.csv", index=False)
    table.to_csv(OUT / "metrics.csv", index=False)

    entry_cols = ["book", "compression_n", "n_entries", "hit_rate", "win_size", "delta_hit_rate", "delta_win_size"]
    table[entry_cols].to_csv(OUT / "entry_quality_vs_face.csv", index=False)

    summary = {
        "knife_id": "COMPRESSION-BREAKOUT-LIVE1430",
        "window": "2020-01-03 → 2026-10-23",
        "cost_rt": 0.002,
        "leverage_cap": 1.0,
        "face_ref": {k: face[k] for k in ["ret", "maxDD", "CAGR", "Calmar", "hit_rate", "win_size", "n_entries"]},
        "books": rows,
        "elapsed_s": round(time.time() - t0, 2),
        "research_only": True,
    }
    (OUT / "summary.json").write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")

    plt.figure(figsize=(10, 5))
    for name, nav in nav_frames.items():
        plt.plot(nav.index, nav.values, label=name)
    plt.legend()
    plt.title("COMPRESSION-BREAKOUT-LIVE1430 · research pool")
    plt.ylabel("NAV")
    plt.tight_layout()
    plt.savefig(OUT / "equity_curve.png", dpi=120)
    plt.close()

    report = _render_report(table, face, summary["elapsed_s"])
    (OUT / "REPORT.md").write_text(report, encoding="utf-8")
    print(report)
    print(f"\nWrote four-pack under {OUT} ({summary['elapsed_s']}s)")


def _render_report(table: pd.DataFrame, face: dict, elapsed: float) -> str:
    lines = [
        "# REPORT · COMPRESSION-BREAKOUT-LIVE1430",
        "",
        "研究池四件套：FACE vs N∈{4,6,8} 周压缩突破门控（spike 填席新增）。",
        "",
        "> 数据：未设置 `RESEARCH_CACHE` 时由 yfinance 拉取研究池 ETF 日线（与 TiltFolio 全量 face 数值不可横比）；设 `RESEARCH_CACHE` 可接主库 `daily/*.parquet`。",
        "",
        "## 组合主表",
        "",
        "| book | N | ret | maxDD | Calmar | hit-rate | win-size | n_entries | Δret | Δ|MDD| | Δhit | Δwin-size |",
        "|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|",
    ]
    for _, r in table.iterrows():
        lines.append(
            f"| {r['book']} | {r['compression_n'] if pd.notna(r['compression_n']) else '—'} | "
            f"{r['ret']:.1%} | {r['maxDD']:.1%} | {r['Calmar']:.2f} | "
            f"{r['hit_rate']:.1%} | {r['win_size']:.2f} | {int(r['n_entries'])} | "
            f"{r['delta_ret']:+.1%} | {r['delta_abs_mdd']:+.1%} | {r['delta_hit_rate']:+.1%} | {r['delta_win_size']:+.2f} |"
        )
    lines.extend(
        [
            "",
            "## FACE 参照",
            f"- ret {face['ret']:.1%} · maxDD {face['maxDD']:.1%} · Calmar {face['Calmar']:.2f}",
            f"- 入场 hit-rate {face['hit_rate']:.1%} · win-size {face['win_size']:.2f} · n={int(face['n_entries'])}",
            "",
            "## 一句结论（探索记账，不换冠）",
            _verdict(table, face),
            "",
            f"耗时约 {elapsed:.1f}s。产物：`run.py` / `criterion.md` / `REPORT.md` / `summary.json` / `table.csv` / `entry_quality_vs_face.csv` / `equity_curve.png`",
        ]
    )
    return "\n".join(lines)


def _verdict(table: pd.DataFrame, face: dict) -> str:
    neigh = table[table["compression_n"].notna()]
    improved = neigh[(neigh["hit_rate"] > face["hit_rate"]) & (neigh["win_size"] > face["win_size"])]
    if len(improved):
        best = improved.sort_values("Calmar", ascending=False).iloc[0]
        return (
            f"**未换冠**：{best['book']} 在入场 hit-rate/win-size 双改善，Calmar={best['Calmar']:.2f}；"
            "组合尺子见 Δret/Δ|MDD|。"
        )
    return "**探索记账**：邻档未同时在 hit-rate 与 win-size 上优于 FACE；见主表 Δ 列。"


if __name__ == "__main__":
    main()
