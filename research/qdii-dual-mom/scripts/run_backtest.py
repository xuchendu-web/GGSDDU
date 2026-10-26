#!/usr/bin/env python3
"""CODE+BACKTEST: overseas QDII dual-momentum sleeve. No LIVE / no B45 gate."""

from __future__ import annotations

import json
import sys
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from qdii_dual_mom.config import (  # noqa: E402
    COST_SIDE,
    EVAL_END,
    EVAL_START,
    FACE_BOOK,
    MA_MAIN,
    MA_NEIGHBOR,
    MAIN_BOOK,
    N_SEATS_MAIN,
    N_SEATS_TABLE,
    RESULTS,
    QdiiDmConfig,
)
from qdii_dual_mom.engine import (  # noqa: E402
    run_cash,
    run_equal_weight_bh,
    run_qdii_dual_mom,
)
from qdii_dual_mom.fourpack import render_fourpack  # noqa: E402
from qdii_dual_mom.metrics import book_stats, covers_mdd, segment_stats, yearly_stats  # noqa: E402
from qdii_dual_mom.panel import inventory_note, load_weekly_panel  # noqa: E402


GRID = [
    QdiiDmConfig(ma_weeks=MA_MAIN, n_seats=N_SEATS_MAIN, name=MAIN_BOOK),
    QdiiDmConfig(ma_weeks=MA_NEIGHBOR, n_seats=N_SEATS_MAIN, name="QDII-DM-MA10-K3"),
    QdiiDmConfig(ma_weeks=MA_MAIN, n_seats=N_SEATS_TABLE, name="QDII-DM-MA20-K5"),
    QdiiDmConfig(ma_weeks=MA_MAIN, n_seats=N_SEATS_MAIN, apply_ma=False, name="QDII-DM-noMA-K3"),
    QdiiDmConfig(ma_weeks=MA_MAIN, n_seats=N_SEATS_MAIN, apply_r12_abs=False, name="QDII-DM-MA20-noR12-K3"),
]


def row_for(name: str, nav: pd.Series, weekly_ret: pd.Series, extra: dict) -> dict:
    st = book_stats(nav, weekly_ret)
    a = segment_stats(nav, "2020-01-03", "2022-12-31")
    b = segment_stats(nav, "2023-01-01", EVAL_END)
    out = {
        "book": name,
        "ret": st["ret"],
        "maxDD": st["maxDD"],
        "CAGR": st["CAGR"],
        "Calmar": st["Calmar"],
        "Sharpe": st["Sharpe"],
        "2020-22_ret": a["ret"],
        "2020-22_DD": a["maxDD"],
        "2020-22_Calmar": a["Calmar"],
        "2023-26_ret": b["ret"],
        "2023-26_DD": b["maxDD"],
        "2023-26_Calmar": b["Calmar"],
    }
    out.update(extra)
    return out


def main() -> int:
    inv = inventory_note()
    if not inv["ok"]:
        print(json.dumps({"status": "STOP", "inventory": inv}, ensure_ascii=False, indent=2))
        return 2

    RESULTS.mkdir(parents=True, exist_ok=True)
    panel = load_weekly_panel()
    books: dict[str, object] = {}
    rows: list[dict] = []

    for cfg in GRID:
        res = run_qdii_dual_mom(panel, cfg)
        books[res.name] = res
        rows.append(
            row_for(
                res.name,
                res.nav,
                res.weekly_ret,
                {
                    "turnover": res.turnover_oneway_annual,
                    "avgL": res.avg_gross,
                    "cash_week_pct": res.cash_week_pct,
                    "n_reb": res.n_reb,
                },
            )
        )
        if cfg.name == MAIN_BOOK:
            res.holdings.to_csv(RESULTS / "holdings.csv", index=False)
            res.nav.rename("nav").to_csv(RESULTS / "nav.csv", header=True)
            yearly_stats(res.nav).to_csv(RESULTS / "yearly.csv", index=False)

    ew = run_equal_weight_bh(panel, cost_side=COST_SIDE, name=FACE_BOOK)
    books[ew.name] = ew
    rows.append(
        row_for(
            ew.name,
            ew.nav,
            ew.weekly_ret,
            {
                "turnover": ew.turnover_oneway_annual,
                "avgL": ew.avg_gross,
                "cash_week_pct": ew.cash_week_pct,
                "n_reb": ew.n_reb,
            },
        )
    )

    cash = run_cash(panel)
    books[cash.name] = cash
    rows.append(
        row_for(
            cash.name,
            cash.nav,
            cash.weekly_ret,
            {
                "turnover": 0.0,
                "avgL": 0.0,
                "cash_week_pct": 1.0,
                "n_reb": cash.n_reb,
            },
        )
    )

    metrics = pd.DataFrame(rows)
    metrics.to_csv(RESULTS / "metrics.csv", index=False)

    main_nav = books[MAIN_BOOK].nav
    main_wr = books[MAIN_BOOK].weekly_ret
    dm = book_stats(main_nav, main_wr)
    bench = book_stats(ew.nav, ew.weekly_ret)
    post = segment_stats(main_nav, "2023-01-01", EVAL_END)
    post_b = segment_stats(ew.nav, "2023-01-01", EVAL_END)
    verdict_cover = covers_mdd(dm["ret"], dm["maxDD"], bench["ret"], bench["maxDD"])
    miss = post["ret"] < post_b["ret"] * 0.8
    if (not verdict_cover) or miss:
        verdict = (
            f"袖内探索：{MAIN_BOOK} 相对 {FACE_BOOK} "
            f"{'Δret 未盖住 Δ|MDD|' if not verdict_cover else '盖住回撤差'}；"
            f"2023–26 {post['ret']:.1%} vs EW {post_b['ret']:.1%}"
            f"{'，后段偏弱' if miss else ''}。独立书，不碰 A 股冠座。"
        )
    else:
        verdict = (
            f"袖内记正：{MAIN_BOOK} 相对 {FACE_BOOK} Δret 盖住 Δ|MDD| 且 2023–26 未明显踏空。"
            "仍为研究袖，不升格、不混 B45。"
        )

    overlay = {
        MAIN_BOOK: main_nav,
        "QDII-DM-MA10-K3": books["QDII-DM-MA10-K3"].nav,
        FACE_BOOK: ew.nav,
        "CASH": cash.nav,
    }
    png = render_fourpack(
        overlay,
        FACE_BOOK,
        RESULTS / "fourpack.png",
        "海外QDII 绝对+相对动量袖 vs OX-EW · 2020-01-03→2026-10-23",
        main_name=MAIN_BOOK,
    )

    summary = {
        "title": "QDII-DUAL-MOM-SLEEVE",
        "live": False,
        "breadth_gate": False,
        "sample": f"{EVAL_START} → {EVAL_END}",
        "universe": inv,
        "main": MAIN_BOOK,
        "benchmark": FACE_BOOK,
        "cost_rt": 0.002,
        "main_stats": {k: (None if pd.isna(v) else float(v)) for k, v in dm.items()},
        "bench_stats": {k: (None if pd.isna(v) else float(v)) for k, v in bench.items()},
        "covers_mdd_vs_ew": bool(verdict_cover),
        "post_2023_miss": bool(miss),
        "verdict": verdict,
        "fourpack": str(png),
        "skipped": ["VS-TSMOM multi-sleeve PR#84", "Dual-TF A-share face PR#63"],
    }
    (RESULTS / "summary.json").write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    print(metrics.to_string(index=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
