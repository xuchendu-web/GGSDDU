#!/usr/bin/env python3
"""CODE+BACKTEST: weekly dual momentum vs B45 face. No LIVE."""

from __future__ import annotations

import json
import sys
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from dual_momentum.config import (  # noqa: E402
    COST_SIDE,
    DATA,
    EVAL_END,
    EVAL_START,
    FACE_BOOK,
    RESULTS,
    DualMomConfig,
)
from dual_momentum.engine import run_dual_momentum, run_equal_weight  # noqa: E402
from dual_momentum.fourpack import render_fourpack  # noqa: E402
from dual_momentum.metrics import (  # noqa: E402
    align_face_weekly,
    book_stats,
    covers_mdd,
    segment_stats,
    yearly_stats,
)
from dual_momentum.panel import load_b45_nav, load_weekly_panel  # noqa: E402


GRID = [
    DualMomConfig(lookback=52, skip=1, n_seats=5, apply_absolute=True, name="DM-L52s1-N5"),
    DualMomConfig(lookback=52, skip=1, n_seats=5, apply_absolute=False, name="XS-L52s1-N5"),
    DualMomConfig(lookback=26, skip=1, n_seats=5, apply_absolute=True, name="DM-L26s1-N5"),
    DualMomConfig(lookback=78, skip=1, n_seats=5, apply_absolute=True, name="DM-L78s1-N5"),
    DualMomConfig(lookback=52, skip=1, n_seats=3, apply_absolute=True, name="DM-L52s1-N3"),
    DualMomConfig(lookback=52, skip=1, n_seats=8, apply_absolute=True, name="DM-L52s1-N8"),
]


def row_for(name: str, nav: pd.Series, extra: dict) -> dict:
    st = book_stats(nav)
    a = segment_stats(nav, "2020-01-03", "2022-12-31")
    b = segment_stats(nav, "2023-01-01", EVAL_END)
    out = {
        "book": name,
        "ret": st["ret"],
        "maxDD": st["maxDD"],
        "CAGR": st["CAGR"],
        "Calmar": st["Calmar"],
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
    RESULTS.mkdir(parents=True, exist_ok=True)
    panel = load_weekly_panel()
    face_daily = load_b45_nav()
    books: dict[str, object] = {}
    rows = []
    for cfg in GRID:
        res = run_dual_momentum(panel, cfg)
        books[res.name] = res
        rows.append(
            row_for(
                res.name,
                res.nav,
                {
                    "avgL": res.avg_gross,
                    "cash_week_pct": res.cash_week_pct,
                    "turnover_x": res.turnover_oneway_annual,
                    "n_reb": res.n_reb,
                },
            )
        )
        if cfg.name == "DM-L52s1-N5":
            res.holdings.to_csv(RESULTS / "holdings.csv", index=False)
            res.nav.rename("nav").to_csv(RESULTS / "nav.csv", header=True)
            yearly_stats(res.nav).to_csv(RESULTS / "yearly.csv", index=False)

    ew = run_equal_weight(panel, cost_side=COST_SIDE, name="POOL-EW")
    books[ew.name] = ew
    rows.append(
        row_for(
            ew.name,
            ew.nav,
            {
                "avgL": ew.avg_gross,
                "cash_week_pct": ew.cash_week_pct,
                "turnover_x": ew.turnover_oneway_annual,
                "n_reb": ew.n_reb,
            },
        )
    )

    main_nav = books["ABS-L52s1-N5"].nav
    face_w = align_face_weekly(face_daily, main_nav.index)
    # official daily face (same window) for judging table
    face_d = face_daily.loc[pd.Timestamp(EVAL_START) : pd.Timestamp(EVAL_END)]
    rows.append(
        row_for(
            FACE_BOOK + "-weekly",
            face_w,
            {"avgL": float("nan"), "cash_week_pct": float("nan"), "turnover_x": float("nan"), "n_reb": len(face_w)},
        )
    )
    rows.append(
        row_for(
            FACE_BOOK,
            face_d,
            {"avgL": 0.8413, "cash_week_pct": 0.4310, "turnover_x": float("nan"), "n_reb": float("nan")},
        )
    )

    metrics = pd.DataFrame(rows)
    metrics.to_csv(RESULTS / "metrics.csv", index=False)

    dm = book_stats(main_nav)
    b45 = book_stats(face_d)
    b45w = book_stats(face_w)
    post = segment_stats(main_nav, "2023-01-01", EVAL_END)
    post_b45 = segment_stats(face_d, "2023-01-01", EVAL_END)
    verdict_cover = covers_mdd(dm["ret"], dm["maxDD"], b45["ret"], b45["maxDD"])
    miss = post["ret"] < post_b45["ret"] * 0.8
    if (not verdict_cover) or miss:
        verdict = (
            f"探索证伪（不换冠）：主簿 ABS-L52s1-N5 相对 B45 face "
            f"{'Δret 未盖住 Δ|MDD|' if not verdict_cover else '盖住回撤'}；"
            f"2023–26 {post['ret']:.1%} vs B45 {post_b45['ret']:.1%}"
            f"{'，后段偏弱/踏空' if miss else ''}。"
        )
    else:
        verdict = (
            "探索记正（不换冠）：主簿相对 B45 Δret 盖住 Δ|MDD| 且 2023–26 未踏空。"
            "面层仍保留 breadth；本条不升格、不碰 LIVE。"
        )

    overlay = {
        "ABS-L52s1-N5": main_nav,
        "XS-L52s1-N5": books["XS-L52s1-N5"].nav,
        "POOL-EW": ew.nav,
        FACE_BOOK: face_w,
    }
    png = render_fourpack(
        overlay,
        FACE_BOOK,
        RESULTS / "fourpack.png",
        "周频双动量 vs B45 face · 研究池 · 2020-01-03→2026-10-23",
    )

    summary = {
        "title": "DUAL-MOM-WEEKLY vs B45 face",
        "live": False,
        "sample": f"{EVAL_START} → {EVAL_END}",
        "universe": {"n_cols": int(panel.shape[1]), "n_weeks": int(panel.shape[0])},
        "main": "ABS-L52s1-N5",
        "face": FACE_BOOK,
        "main_stats": {k: (None if pd.isna(v) else float(v)) for k, v in dm.items()},
        "b45_daily_stats": {k: (None if pd.isna(v) else float(v)) for k, v in b45.items()},
        "b45_weekly_asof_stats": {k: (None if pd.isna(v) else float(v)) for k, v in b45w.items()},
        "covers_mdd_vs_b45": bool(verdict_cover),
        "post_2023_miss": bool(miss),
        "verdict": verdict,
        "fourpack": str(png),
    }
    (RESULTS / "summary.json").write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    print(metrics.to_string(index=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
