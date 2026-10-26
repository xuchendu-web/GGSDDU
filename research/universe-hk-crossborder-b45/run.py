#!/usr/bin/env python3
"""UNIVERSE-HK-CROSSBORDER-B45 · LIVE1430 face batch (research pool only)."""
from __future__ import annotations

import argparse
import csv
import json
import sys
import time
from collections import defaultdict
from datetime import date
from pathlib import Path

import matplotlib.pyplot as plt
import pandas as pd

ROOT = Path(__file__).resolve().parent
DATA = ROOT / "data"
sys.path.insert(0, str(ROOT.parent.parent))

from research._kit.face_live1430 import FaceConfig, pit_filter, run_face_backtest  # noqa: E402

DATE_START = "2020-01-03"
DATE_END = "2026-10-23"
WIDE_BASE = ["510300", "510500", "159915", "159919", "159922"]
MIN_ROWS = 200


def load_nav(path: Path) -> pd.DataFrame:
    rows = []
    with path.open(newline="", encoding="utf-8") as f:
        r = csv.DictReader(f)
        for row in r:
            rows.append(
                {
                    "SecuCode": row["SecuCode"].strip(),
                    "d": pd.Timestamp(row["d"].strip()[:10]),
                    "c": float(row["c"]),
                }
            )
    if not rows:
        return pd.DataFrame(columns=["SecuCode", "d", "c"])
    df = pd.DataFrame(rows)
    wide = df.pivot_table(index="d", columns="SecuCode", values="c", aggfunc="last").sort_index()
    wide = wide.ffill()
    return wide


def load_listings() -> dict[str, pd.Timestamp]:
    p = DATA / "listings.json"
    if not p.exists():
        return {}
    obj = json.loads(p.read_text(encoding="utf-8"))
    out = {}
    for code, inner in obj.get("inner_by_code", {}).items():
        ld = obj.get("listed_by_code", {}).get(code)
        if ld:
            out[code] = pd.Timestamp(ld)
    return out


def investable_schedule(codes: list[str], listings: dict[str, pd.Timestamp], fridays: pd.DatetimeIndex) -> dict:
    sched = {}
    for fri in fridays:
        sched[fri] = pit_filter(listings, fri, codes)
    return sched


def fmt_pct(x: float) -> str:
    return f"{100 * x:.1f}%"


def judge_h1(full: dict, slice_: dict) -> dict:
    """H1: slice cannot simultaneously beat full on Calmar and not miss 2023–26."""
    d_cal = slice_.get("Calmar", 0) - full.get("Calmar", 0)
    seg_f = full.get("2023-26", {}) or {}
    seg_s = slice_.get("2023-26", {}) or {}
    ret_f = seg_f.get("ret", 0.0)
    ret_s = seg_s.get("ret", 0.0)
    miss = ret_s < ret_f * 0.9 if ret_f > 0 else ret_s < ret_f
    improved_calmar = d_cal > 0
    falsified = improved_calmar and not miss
    return {
        "delta_calmar": d_cal,
        "slice_calmar_better": improved_calmar,
        "slice_2023_26_miss_vs_full": miss,
        "h1_falsified": falsified,
        "h1_verdict": "FALSIFIED" if falsified else "NOT_FALSIFIED",
    }


def run_book(
    label: str,
    close: pd.DataFrame,
    invest_codes: list[str],
    breadth_codes: list[str],
    listings: dict[str, pd.Timestamp],
) -> tuple[pd.Series, dict]:
    fridays = pd.DatetimeIndex(
        [d for d in close.index if d.dayofweek == 4 and DATE_START <= str(d.date()) <= DATE_END]
    )
    sched = investable_schedule(invest_codes, listings, fridays)
    nav, weekly, stats = run_face_backtest(
        close,
        sched,
        breadth_codes=breadth_codes,
        cfg=FaceConfig(),
        start=DATE_START,
        end=DATE_END,
    )
    stats["book"] = label
    stats["avgL"] = float(weekly["avgL"].mean()) if len(weekly) else 0.0
    stats["cash_week_pct"] = float((~weekly["risk_on"]).mean()) if len(weekly) else 0.0
    return nav, stats


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--cache", type=Path, default=DATA / "nav_long.csv")
    ap.add_argument("--out", type=Path, default=ROOT / "output")
    ap.add_argument("--allow-partial", action="store_true", help="Allow reduced universe coverage for dry-run")
    args = ap.parse_args()
    t0 = time.time()

    hk = json.loads((DATA / "universe_hk.json").read_text(encoding="utf-8"))["secucodes"]
    full = json.loads((DATA / "universe_full.json").read_text(encoding="utf-8"))["secucodes"]
    listings = load_listings()

    close = load_nav(args.cache)
    if close.empty:
        summary = {"verdict": "fail_no_cache", "cache": str(args.cache)}
        (args.out / "summary.json").write_text(json.dumps(summary, indent=2), encoding="utf-8")
        print(json.dumps(summary, indent=2))
        sys.exit(1)

    codes_ok = [c for c in close.columns if close[c].notna().sum() >= MIN_ROWS]
    hk_ok = [c for c in hk if c in codes_ok]
    full_ok = [c for c in full if c in codes_ok]
    allow_partial = args.allow_partial
    hk_ratio = len(hk_ok) / max(1, len(hk))
    full_ratio = len(full_ok) / max(1, len(full))
    if not allow_partial and (hk_ratio < 0.85 or full_ratio < 0.7):
        summary = {
            "verdict": "incomplete_cache",
            "nav_codes": len(codes_ok),
            "hk_ok": len(hk_ok),
            "hk_total": len(hk),
            "full_ok": len(full_ok),
            "full_total": len(full),
        }
        (args.out / "summary.json").write_text(json.dumps(summary, indent=2), encoding="utf-8")
        print(json.dumps(summary, indent=2))
        sys.exit(2)
    if allow_partial and (hk_ratio < 0.5 or full_ratio < 0.35):
        summary = {
            "verdict": "incomplete_cache",
            "hk_ratio": hk_ratio,
            "full_ratio": full_ratio,
            "note": "partial run needs hk>=50% and full>=35%",
        }
        (args.out / "summary.json").write_text(json.dumps(summary, indent=2), encoding="utf-8")
        print(json.dumps(summary, indent=2))
        sys.exit(2)

    # Frozen: breadth on full research pool (full_ok);旁注 slice-internal in REPORT
    breadth_full = full_ok
    breadth_slice_note_codes = hk_ok

    face_full_nav, face_full = run_book("FACE-FULL-B45-S20-LIVE1430", close, full_ok, breadth_full, listings)
    slice_nav, slice_stats = run_book("SLICE-HK-XB-B45-S20-LIVE1430", close, hk_ok, breadth_full, listings)

    wide_rows = []
    for wb in WIDE_BASE:
        if wb not in codes_ok:
            continue
        one_close = close[[wb]].dropna(how="all")
        fridays = one_close.index[one_close.index.dayofweek == 4]
        sched = {f: [wb] for f in fridays}
        nav, st = run_face_backtest(one_close, sched, breadth_full, start=DATE_START, end=DATE_END)
        st["book"] = f"WIDE-{wb}"
        wide_rows.append(st)

    h1 = judge_h1(face_full, slice_stats)
    verdict = h1["h1_verdict"]

    args.out.mkdir(parents=True, exist_ok=True)
    table = [face_full, slice_stats] + wide_rows
    table_path = args.out / "table.csv"
    with table_path.open("w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(
            [
                "book",
                "ret",
                "maxDD",
                "CAGR",
                "Calmar",
                "2020-22_ret",
                "2020-22_Calmar",
                "2023-26_ret",
                "2023-26_Calmar",
                "avgL",
                "cash_week_pct",
            ]
        )
        for row in table:
            s22 = row.get("2020-22", {}) or {}
            s26 = row.get("2023-26", {}) or {}
            w.writerow(
                [
                    row.get("book"),
                    row.get("ret"),
                    row.get("maxDD"),
                    row.get("CAGR"),
                    row.get("Calmar"),
                    s22.get("ret"),
                    s22.get("Calmar"),
                    s26.get("ret"),
                    s26.get("Calmar"),
                    row.get("avgL"),
                    row.get("cash_week_pct"),
                ]
            )

    face_full_nav.to_csv(args.out / "nav_face_full.csv")
    slice_nav.to_csv(args.out / "nav_slice.csv")

    plt.figure(figsize=(10, 5))
    plt.plot(face_full_nav.index, face_full_nav.values, label="FACE full pool")
    plt.plot(slice_nav.index, slice_nav.values, label="HK+XB slice")
    plt.title("LIVE1430 B45+S20 face · full vs HK/XB slice")
    plt.legend()
    plt.grid(True, alpha=0.3)
    plt.tight_layout()
    plt.savefig(args.out / "equity_curve.png", dpi=120)
    plt.close()

    summary = {
        "knife_id": "UNIVERSE-HK-CROSSBORDER-B45",
        "window": f"{DATE_START} → {DATE_END}",
        "cost_rt": 0.002,
        "leverage_cap": 1.0,
        "breadth_mother_pool": "full_pool_frozen",
        "breadth_side_note": "slice_internal_ma20_width_not_primary",
        "face_layer": "spike_ft max5+E0+TV25+SHARPE20; Fri close (14:30 proxy); 0.2%RT; L≤1",
        "data_source": "zsmcp mf_fundnetvaluere / qt_dailyquote close",
        "verdict": verdict,
        "h1": h1,
        "face_full": face_full,
        "slice_hk_xb": slice_stats,
        "wide_base_side": wide_rows,
        "coverage": {
            "hk_ok": len(hk_ok),
            "full_ok": len(full_ok),
            "nav_codes": len(codes_ok),
        },
        "elapsed_s": round(time.time() - t0, 2),
    }
    (args.out / "summary.json").write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
    (ROOT / "summary.json").write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")

    report = build_report(summary, table)
    (ROOT / "REPORT.md").write_text(report, encoding="utf-8")
    print(json.dumps(summary, ensure_ascii=False, indent=2))


def build_report(summary: dict, table: list) -> str:
    ff = summary["face_full"]
    sl = summary["slice_hk_xb"]
    h1 = summary["h1"]
    lines = [
        "# REPORT · UNIVERSE-HK-CROSSBORDER-B45",
        "",
        "研究池刀：港股+跨境权益 ETF 宇宙切片 vs 全池 FACE（B45+S20 LIVE1430）。不换冠、不碰 LIVE_OPS。",
        "",
        "## 面层（冻结）",
        "",
        "B45 + spike_ft max5 + E0 + TV25 + SHARPE20；周五信号→收盘成交（本云批次用日收盘近似 Fri≥14:30）；0.2%RT；L≤1。",
        "",
        "## 宇宙与 breadth",
        "",
        "- **切片**：`data/universe_hk.json`（港股/跨境权益 ETF，聚源标签+名称规则，见 `universe.sql`）。",
        "- **全池 face 对照**：`data/universe_full.json`（~280 流动性筛 equity ETF）。",
        "- **breadth 母池（写死）**：全池 `full_ok` 的 MA20 宽度 ≥45% 才 risk-on；**旁注**：切片内 MA20 宽度未作主口径。",
        "",
        "## 主表",
        "",
        "| book | ret | maxDD | Calmar | 2023–26 ret | 2023–26 Calmar | avgL | 空仓周占比 |",
        "|---|---:|---:|---:|---:|---:|---:|---:|",
        f"| FACE-FULL | {fmt_pct(ff['ret'])} | {fmt_pct(ff['maxDD'])} | {ff['Calmar']:.2f} | "
        f"{fmt_pct((ff.get('2023-26') or {}).get('ret', 0))} | {(ff.get('2023-26') or {}).get('Calmar', 0):.2f} | "
        f"{ff.get('avgL', 0):.2f} | {fmt_pct(ff.get('cash_week_pct', 0))} |",
        f"| SLICE-HK-XB | {fmt_pct(sl['ret'])} | {fmt_pct(sl['maxDD'])} | {sl['Calmar']:.2f} | "
        f"{fmt_pct((sl.get('2023-26') or {}).get('ret', 0))} | {(sl.get('2023-26') or {}).get('Calmar', 0):.2f} | "
        f"{sl.get('avgL', 0):.2f} | {fmt_pct(sl.get('cash_week_pct', 0))} |",
        "",
        "## H1",
        "",
        f"假设：切片相对全池 face **不能**同时改善 Calmar 且 2023–26 不踏空。",
        f"**{h1['h1_verdict']}**（ΔCalmar={h1['delta_calmar']:.3f}；切片后段踏空={h1['slice_2023_26_miss_vs_full']}）。",
        "",
        "## 宽基旁注",
        "",
    ]
    for wb in summary.get("wide_base_side", []):
        lines.append(
            f"- {wb.get('book')}: ret {fmt_pct(wb.get('ret', 0))}, Calmar {wb.get('Calmar', 0):.2f}"
        )
    lines += [
        "",
        "## 数据与复现",
        "",
        "数据源：**zsmcp**（未用进门/中金/Alpha派）。`python3 run.py --cache data/nav_long.csv`。",
        "缓存不足时先按 `data/build_nav_cache.py` 说明补全 `nav_long.csv`。",
        "",
        f"耗时约 {summary.get('elapsed_s')}s。产物：`run.py` / `criterion.md` / `REPORT.md` / `summary.json` / `output/table.csv` / `output/equity_curve.png`。",
    ]
    return "\n".join(lines)


if __name__ == "__main__":
    main()
