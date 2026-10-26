#!/usr/bin/env python3
"""CODE+BACKTEST: skip-month CSMOM vs no-skip vs B45 face. No LIVE."""

from __future__ import annotations

import json
import sys
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from skip_month_csmom.config import (  # noqa: E402
    EVAL_END,
    EVAL_START,
    FACE_BOOK,
    RESULTS,
    CsmomConfig,
)
from skip_month_csmom.engine import run_csmom  # noqa: E402
from skip_month_csmom.fourpack import render_fourpack  # noqa: E402
from skip_month_csmom.metrics import (  # noqa: E402
    align_face_weekly,
    book_stats,
    covers_mdd,
    segment_stats,
    yearly_stats,
)
from skip_month_csmom.panel import load_b45_nav, load_weekly_panel  # noqa: E402

MAIN_LABEL = "CSMOM-M12s1-N5"

GRID = [
    CsmomConfig(skip_months=1, n_seats=5),
    CsmomConfig(skip_months=0, n_seats=5),
    CsmomConfig(skip_months=1, n_seats=3),
    CsmomConfig(skip_months=1, n_seats=7),
    CsmomConfig(skip_months=1, n_seats=5, breadth_gate=True),
]


def row_for(name: str, nav: pd.Series, weekly_ret: pd.Series, extra: dict) -> dict:
    st = book_stats(nav, weekly_ret)
    a = segment_stats(nav, "2020-01-03", "2022-12-31")
    b = segment_stats(nav, "2023-01-01", EVAL_END)
    out = {
        "book": name,
        "ret": st["ret"],
        "maxDD": st["maxDD"],
        "Calmar": st["Calmar"],
        "Sharpe": st.get("Sharpe", float("nan")),
        "Sortino": st.get("Sortino", float("nan")),
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
    books_nav: dict[str, pd.Series] = {}
    rows = []
    results_by_name: dict[str, object] = {}

    for cfg in GRID:
        res = run_csmom(panel, cfg)
        results_by_name[res.name] = res
        books_nav[res.name] = res.nav
        rows.append(
            row_for(
                res.name,
                res.nav,
                res.weekly_ret,
                {
                    "avgL": res.avg_gross,
                    "cash_week_pct": res.cash_week_pct,
                    "turnover_x": res.turnover_oneway_annual,
                    "n_reb": res.n_reb,
                },
            )
        )
        if res.name == MAIN_LABEL:
            res.holdings.to_csv(RESULTS / "holdings.csv", index=False)
            res.nav.rename("nav").to_csv(RESULTS / "nav.csv", header=True)
            yearly_stats(res.nav).to_csv(RESULTS / "yearly.csv", index=False)

    main_res = results_by_name[MAIN_LABEL]
    face_w = align_face_weekly(face_daily, main_res.nav.index)
    face_d = face_daily.loc[pd.Timestamp(EVAL_START) : pd.Timestamp(EVAL_END)]
    rows.append(
        row_for(
            FACE_BOOK + "-weekly",
            face_w,
            face_w.pct_change().fillna(0.0),
            {
                "avgL": float("nan"),
                "cash_week_pct": float("nan"),
                "turnover_x": float("nan"),
                "n_reb": len(face_w),
            },
        )
    )
    rows.append(
        row_for(
            FACE_BOOK,
            face_d,
            face_d.pct_change().fillna(0.0),
            {
                "avgL": 0.8413,
                "cash_week_pct": 0.4310,
                "turnover_x": float("nan"),
                "n_reb": float("nan"),
            },
        )
    )

    metrics = pd.DataFrame(rows)
    metrics.to_csv(RESULTS / "metrics.csv", index=False)

    skip = results_by_name[MAIN_LABEL]
    noskip = results_by_name["CSMOM-M12s0-N5"]
    st_skip = book_stats(skip.nav, skip.weekly_ret)
    st_noskip = book_stats(noskip.nav, noskip.weekly_ret)
    b45 = book_stats(face_d, face_d.pct_change().fillna(0.0))
    post_skip = segment_stats(skip.nav, "2023-01-01", EVAL_END)
    post_b45 = segment_stats(face_d, "2023-01-01", EVAL_END)
    verdict_cover = covers_mdd(st_skip["ret"], st_skip["maxDD"], b45["ret"], b45["maxDD"])
    skip_beats_noskip = st_skip["Calmar"] > st_noskip["Calmar"] and st_skip["ret"] >= st_noskip["ret"] - 0.02
    miss_post = post_skip["ret"] < post_b45["ret"] * 0.8

    if (not skip_beats_noskip) or (not verdict_cover) or miss_post:
        parts = []
        if not skip_beats_noskip:
            parts.append(
                f"跳月未稳赢无跳月（ret {st_skip['ret']:.1%} vs {st_noskip['ret']:.1%}，"
                f"Calmar {st_skip['Calmar']:.2f} vs {st_noskip['Calmar']:.2f}）"
            )
        if not verdict_cover:
            parts.append("相对 B45 Δret 未盖住 Δ|MDD|")
        if miss_post:
            parts.append(f"2023–26 {post_skip['ret']:.1%} vs B45 {post_b45['ret']:.1%}")
        verdict = "探索证伪（不换冠）：" + "；".join(parts) + "。"
    else:
        verdict = (
            "探索记正（不换冠）：跳月优于无跳月且相对 B45 盖住回撤、后段未踏空。"
            "不升格、不碰 LIVE。"
        )

    overlay = {
        MAIN_LABEL: skip.nav,
        "CSMOM-M12s0-N5": noskip.nav,
        FACE_BOOK: face_w,
    }
    png = render_fourpack(
        overlay,
        FACE_BOOK,
        RESULTS / "fourpack.png",
        "跳月截面动量 vs B45 face · 研究池 · 2020-01-03→2026-10-23",
    )

    summary = {
        "knife_id": "RESEARCH-SKIP-MONTH-CSMOM-WEEKLY",
        "live": False,
        "sample": f"{EVAL_START} → {EVAL_END}",
        "universe": {"n_cols": int(panel.shape[1]), "n_weeks": int(panel.shape[0])},
        "main": MAIN_LABEL,
        "face": FACE_BOOK,
        "skip_vs_noskip": {
            "skip_ret": float(st_skip["ret"]),
            "noskip_ret": float(st_noskip["ret"]),
            "skip_calmar": float(st_skip["Calmar"]),
            "noskip_calmar": float(st_noskip["Calmar"]),
            "skip_beats_noskip": bool(skip_beats_noskip),
        },
        "main_stats": {k: (None if pd.isna(v) else float(v)) for k, v in st_skip.items()},
        "b45_daily_stats": {k: (None if pd.isna(v) else float(v)) for k, v in b45.items()},
        "covers_mdd_vs_b45": bool(verdict_cover),
        "post_2023_miss": bool(miss_post),
        "verdict": verdict,
        "fourpack": str(png),
    }
    (RESULTS / "summary.json").write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    print(metrics.to_string(index=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
