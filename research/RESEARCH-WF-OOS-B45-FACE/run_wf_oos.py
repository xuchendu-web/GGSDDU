#!/usr/bin/env python3
"""RESEARCH-WF-OOS-B45-FACE: rolling walk-forward on frozen B45 face book.

Train 104w / test 26w / step 26w; light retune TV σ* ∈ {22,25,28,33} on train only.
"""
from __future__ import annotations

import json
import math
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

from face_run import (
    DAY_DIR,
    EVAL_START,
    END_S,
    FACE,
    KIT,
    MAX_POS,
    NOON_CSV,
    SINA_DAILY,
    SNAP_CACHE,
    TEMA_PX,
    UNI_CSV,
    WEEK,
    classify_modified,
    load_daily_closes,
    load_sina_closes,
    nearest_date,
    run_live_tv,
    sharpe_key,
    simulate,
    snap_index,
    stats_full,
)

ROOT = Path(__file__).resolve().parent
OUT = ROOT / "data"
KNIFE_ID = "RESEARCH-WF-OOS-B45-FACE"

TRAIN_W = 104
TEST_W = 26
STEP_W = 26
TV_GRID: dict[str, float] = {"TV22": 0.22, "TV25": 0.25, "TV28": 0.28, "TV33": 0.33}
FACE_SIGMA = 0.25
OVERFIT_RATIO = 0.50  # OOS Calmar < ratio × full-sample → collapse flag


@dataclass
class FaceContext:
    calendar: list[str]
    risk_b45: dict[str, bool]
    snaps: dict[str, dict[str, dict[str, Any]]]
    closes_w_sig: dict[str, dict[str, float]]
    alias: dict[str, dict[str, str]]
    aum: dict[str, float]
    daily: dict[str, pd.Series]
    days: pd.DatetimeIndex
    px: pd.DataFrame
    R: pd.DataFrame
    hold_full: dict[str, list[str]]
    coverage: dict[str, Any]


def load_face_context() -> FaceContext:
    for p in (WEEK, FACE, DAY_DIR, NOON_CSV, SINA_DAILY):
        if not Path(p).exists():
            raise SystemExit(f"missing research cache path {p}")

    print("load universe + 14:30 + week…", flush=True)
    uni = pd.read_csv(UNI_CSV)
    uni["code"] = uni["code"].astype(str).str.zfill(6)
    uni = uni[uni["aum"] >= 2].copy()
    codes = uni["code"].tolist()
    aum = {r.code: float(r.aum or 0) for r in uni.itertuples()}
    code_set = set(codes)

    noon = pd.read_csv(NOON_CSV)
    noon["code"] = noon["etf_code"].astype(str).str.split(".").str[0]
    noon["trade_date"] = noon["trade_date"].astype(str).str[:10]
    noon = noon[noon["code"].isin(code_set)].copy()
    if "price_1430" in noon.columns and "price_1130" not in noon.columns:
        noon["price_1130"] = noon["price_1430"]

    face = pd.read_csv(FACE)
    face["date"] = face["date"].astype(str).str[:10]
    face = face[(face["date"] >= EVAL_START) & (face["date"] <= END_S)].copy()
    calendar = sorted(face["date"].unique().tolist())
    actual_end = calendar[-1]

    risk_b45: dict[str, bool] = {}
    for _, row in face.iterrows():
        d = str(row["date"])[:10]
        v = row["risk_on"]
        if isinstance(v, (bool, np.bool_)):
            risk_b45[d] = bool(v)
        else:
            risk_b45[d] = str(v).lower() in {"1", "true"}
    for d in calendar:
        risk_b45.setdefault(d, False)
    risk_b45[calendar[-1]] = False

    raws_w: dict[str, dict[str, Any]] = {}
    closes_w_close: dict[str, dict[str, float]] = {}
    for c in codes:
        fp = WEEK / f"{c}.json"
        if not fp.exists():
            raws_w[c] = {"bars": []}
            closes_w_close[c] = {}
            continue
        rec = json.loads(fp.read_text(encoding="utf-8"))
        raws_w[c] = rec
        closes_w_close[c] = {
            b["date"]: float(b["c"])
            for b in (rec.get("bars") or [])
            if b.get("date") and b["date"] <= END_S and float(b["c"]) > 0
        }

    alias: dict[str, dict[str, str]] = {}
    for c in codes:
        ds = sorted(closes_w_close.get(c, {}))
        if not ds:
            continue
        alias[c] = {d: hit for d in calendar if (hit := nearest_date(d, ds, 3))}

    sina = load_sina_closes(codes)
    daily = load_daily_closes(codes, sina)

    from collections import defaultdict

    noon_w: dict[str, dict[str, float]] = defaultdict(dict)
    blocked_empty: dict[str, set[str]] = defaultdict(set)
    n_map = 0
    for r in noon.itertuples():
        td = r.trade_date
        if td < EVAL_START or td > END_S:
            continue
        if r.status == "empty" or (
            r.status == "ok"
            and (r.price_1130 is None or (isinstance(r.price_1130, float) and math.isnan(r.price_1130)))
        ):
            blocked_empty[td].add(r.code)
            continue
        if r.status != "ok":
            continue
        q = None
        if r.code in daily:
            ser = daily[r.code]
            ts = pd.Timestamp(td)
            if ts in ser.index:
                q = float(ser.loc[ts])
            else:
                sub = ser.loc[:ts]
                if len(sub) and (ts - sub.index[-1]).days <= 3:
                    q = float(sub.iloc[-1])
        b = (sina.get(r.code) or {}).get(td)
        if not b or b <= 0:
            blocked_empty[td].add(r.code)
            continue
        if not q or q <= 0:
            q = float(b)
        qn = float(r.price_1130) * (q / b)
        noon_w[r.code][(alias.get(r.code) or {}).get(td) or td] = qn
        n_map += 1

    listed = noon[noon["status"] != "not_listed"]
    listed = listed[(listed.trade_date >= EVAL_START) & (listed.trade_date <= END_S)]
    nonnull_rate = float(listed["price_1130"].notna().mean()) if len(listed) else 0.0

    closes_w_sig: dict[str, dict[str, float]] = {}
    for c in codes:
        cm = dict(closes_w_close.get(c) or {})
        cm.update({d: v for d, v in (noon_w.get(c) or {}).items() if v and v > 0})
        closes_w_sig[c] = cm
    for d, blk in blocked_empty.items():
        for c in blk:
            key = (alias.get(c) or {}).get(d) or d
            if c in closes_w_sig:
                closes_w_sig[c].pop(key, None)

    if SNAP_CACHE.exists():
        cached = json.loads(SNAP_CACHE.read_text(encoding="utf-8"))
        if cached.get("end") == actual_end:
            by_rows = cached.get("by_code") or {}
            snaps = {c: snap_index(by_rows.get(c) or []) for c in codes}
        else:
            snaps = _rebuild_snaps(raws_w, noon_w, codes, actual_end)
    else:
        snaps = _rebuild_snaps(raws_w, noon_w, codes, actual_end)

    hold_full, _ = simulate_b45(
        calendar,
        ctx_snaps=snaps,
        closes=closes_w_sig,
        alias=alias,
        aum=aum,
        daily=daily,
        risk=risk_b45,
    )
    _px_map, days, px, R = build_price_panel(hold_full, daily)

    cov = {
        "knife_id": KNIFE_ID,
        "kit": str(KIT),
        "calendar": f"{calendar[0]} → {actual_end}",
        "n_weeks": len(calendar),
        "n_codes_aum2": len(codes),
        "listed_1430_nonnull_rate": nonnull_rate,
        "n_qfq_1430_mapped": n_map,
        "retune_axis": "TV_sigma",
        "tv_grid": TV_GRID,
        "wf": {"train_w": TRAIN_W, "test_w": TEST_W, "step_w": STEP_W},
    }
    return FaceContext(
        calendar=calendar,
        risk_b45=risk_b45,
        snaps=snaps,
        closes_w_sig=closes_w_sig,
        alias=alias,
        aum=aum,
        daily=daily,
        days=days,
        px=px,
        R=R,
        hold_full=hold_full,
        coverage=cov,
    )


def _rebuild_snaps(
    raws_w: dict[str, dict[str, Any]],
    noon_w: dict[str, dict[str, float]],
    codes: list[str],
    actual_end: str,
) -> dict[str, dict[str, dict[str, Any]]]:
    print("14:30 classify_modified (rebuild)…", flush=True)
    by = classify_modified(raws_w, dict(noon_w))
    by_rows = {c: by.get(c) or [] for c in codes}
    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / "cache_1430_snaps.json").write_text(
        json.dumps({"by_code": by_rows, "end": actual_end, "start": EVAL_START}, ensure_ascii=False),
        encoding="utf-8",
    )
    return {c: snap_index(by_rows.get(c) or []) for c in codes}


def simulate_b45(
    calendar: list[str],
    *,
    ctx_snaps: dict[str, dict[str, dict[str, Any]]],
    closes: dict[str, dict[str, float]],
    alias: dict[str, dict[str, str]],
    aum: dict[str, float],
    daily: dict[str, pd.Series],
    risk: dict[str, bool],
) -> tuple[dict[str, list[str]], dict[str, Any]]:
    _trades, hold, st = simulate(
        calendar,
        ctx_snaps,
        closes,
        alias,
        aum,
        daily,
        risk,
        sharpe_key,
        "B45-FACE",
        True,
        20,
        MAX_POS,
    )
    return hold, st


def build_price_panel(
    hold: dict[str, list[str]], daily: dict[str, pd.Series]
) -> tuple[dict[str, pd.Series], pd.DatetimeIndex, pd.DataFrame, pd.DataFrame]:
    all_codes: set[str] = set()
    for cs in hold.values():
        all_codes |= set(cs)
    px_map: dict[str, pd.Series] = {}
    for c in sorted(all_codes):
        if c in daily:
            px_map[c] = daily[c]
        else:
            fday = DAY_DIR / f"{c}.json"
            if fday.exists():
                j = json.loads(fday.read_text(encoding="utf-8"))
                bars = j.get("bars") if isinstance(j, dict) else j
                if bars:
                    idx = pd.to_datetime([b["date"] for b in bars])
                    px_map[c] = pd.Series([float(b["c"]) for b in bars], index=idx, dtype=float).sort_index()
            elif (TEMA_PX / f"{c}.csv").exists():
                df = pd.read_csv(TEMA_PX / f"{c}.csv", parse_dates=["Date"])
                px_map[c] = df.set_index("Date")["Close"].astype(float).sort_index()
    px = pd.DataFrame(px_map).sort_index()
    px = px.loc[(px.index >= EVAL_START) & (px.index <= END_S)]
    R = px.pct_change()
    if "510300" in px.columns:
        days = px["510300"].dropna().index
    else:
        days = px.dropna(how="all").index
    days = days[(days >= EVAL_START) & (days <= END_S)]
    return px_map, days, px, R


def daily_returns_for_hold(
    hold: dict[str, list[str]],
    days: pd.DatetimeIndex,
    px: pd.DataFrame,
    R: pd.DataFrame,
    sigma: float,
) -> pd.Series:
    hd = {pd.Timestamp(d): cs for d, cs in hold.items()}
    r, _L = run_live_tv(hd, days, px, R, sigma_star=sigma, cash_fill=None)
    return r


def metrics_from_returns(r: pd.Series) -> dict[str, float]:
    st = stats_full(r)
    if len(r) < 2:
        return {**st, "sharpe": float("nan"), "hit_rate_weekly": float("nan")}
    sharpe = float(r.mean() / r.std() * np.sqrt(252)) if r.std() > 0 else float("nan")
    wk = r.resample("W-FRI").apply(lambda x: (1 + x).prod() - 1)
    wk = wk[wk.notna() & (wk != 0)]
    hit = float((wk > 0).mean()) if len(wk) else float("nan")
    return {**st, "sharpe": sharpe, "hit_rate_weekly": hit}


def run_walk_forward(ctx: FaceContext) -> dict[str, Any]:
    cal = ctx.calendar
    n = len(cal)
    need = TRAIN_W + TEST_W
    folds: list[dict[str, Any]] = []
    oos_parts: list[pd.Series] = []
    is_parts: list[pd.Series] = []

    starts = list(range(0, n - need + 1, STEP_W))
    print(f"WF folds: {len(starts)} (calendar weeks={n})", flush=True)

    for fi, s in enumerate(starts):
        train_cal = cal[s : s + TRAIN_W]
        test_cal = cal[s + TRAIN_W : s + TRAIN_W + TEST_W]
        span_cal = cal[s : s + TRAIN_W + TEST_W]
        hold_span, _ = simulate_b45(
            span_cal,
            ctx_snaps=ctx.snaps,
            closes=ctx.closes_w_sig,
            alias=ctx.alias,
            aum=ctx.aum,
            daily=ctx.daily,
            risk=ctx.risk_b45,
        )
        train_end = pd.Timestamp(train_cal[-1])
        test_start = pd.Timestamp(test_cal[0])
        test_end = pd.Timestamp(test_cal[-1])

        best_tv = "TV25"
        best_cal = -1e9
        train_scores: dict[str, float] = {}
        for label, sig in TV_GRID.items():
            r_train = daily_returns_for_hold(hold_span, ctx.days, ctx.px, ctx.R, sig)
            r_train = r_train[(r_train.index > pd.Timestamp(train_cal[0])) & (r_train.index <= train_end)]
            calmar = stats_full(r_train)["Calmar"]
            train_scores[label] = calmar
            if calmar is not None and not math.isnan(calmar) and calmar > best_cal:
                best_cal = calmar
                best_tv = label

        sigma_oos = TV_GRID[best_tv]
        r_span = daily_returns_for_hold(hold_span, ctx.days, ctx.px, ctx.R, sigma_oos)
        r_test = r_span[(r_span.index >= test_start) & (r_span.index <= test_end)]
        r_train_oos_rule = r_span[
            (r_span.index > pd.Timestamp(train_cal[0])) & (r_span.index <= train_end)
        ]
        oos_parts.append(r_test)
        is_parts.append(r_train_oos_rule)

        folds.append(
            {
                "fold": fi,
                "train_start": train_cal[0],
                "train_end": train_cal[-1],
                "test_start": test_cal[0],
                "test_end": test_cal[-1],
                "chosen_tv": best_tv,
                "sigma": sigma_oos,
                "train_calmar_by_tv": train_scores,
                "train_calmar_chosen": best_cal,
            }
        )
        print(
            f"  fold {fi}: train {train_cal[0]}..{train_cal[-1]} → {best_tv} "
            f"| test {test_cal[0]}..{test_cal[-1]}",
            flush=True,
        )

    oos_r = pd.concat(oos_parts).sort_index()
    oos_r = oos_r[~oos_r.index.duplicated(keep="first")]
    is_r = pd.concat(is_parts).sort_index()
    is_r = is_r[~is_r.index.duplicated(keep="first")]

    r_full = daily_returns_for_hold(ctx.hold_full, ctx.days, ctx.px, ctx.R, FACE_SIGMA)

    m_oos = metrics_from_returns(oos_r)
    m_is = metrics_from_returns(is_r)
    m_full = metrics_from_returns(r_full)

    overfit = False
    reasons: list[str] = []
    if not math.isnan(m_full["Calmar"]) and m_full["Calmar"] > 0:
        if math.isnan(m_oos["Calmar"]) or m_oos["Calmar"] < OVERFIT_RATIO * m_full["Calmar"]:
            overfit = True
            reasons.append(f"OOS Calmar {m_oos['Calmar']:.3f} < {OVERFIT_RATIO}× full-sample {m_full['Calmar']:.3f}")
    if not math.isnan(m_full["Calmar"]) and m_full["Calmar"] > 0.3 and (
        math.isnan(m_oos["Calmar"]) or m_oos["Calmar"] < 0.15
    ):
        overfit = True
        reasons.append("OOS Calmar collapsed below 0.15 while full-sample > 0.3")

    return {
        "knife_id": KNIFE_ID,
        "face_book": "B45-FACE (breadth≥45% risk_on, spike_ft max5, SHARPE20, E0, Fri≥14:30/close, 0.2%RT, L≤1)",
        "coverage": ctx.coverage,
        "folds": folds,
        "metrics": {
            "oos_concat": m_oos,
            "is_concat_train_segments": m_is,
            "full_sample_frozen_TV25": m_full,
        },
        "comparison": {
            "full_sample_calmar": m_full["Calmar"],
            "oos_calmar": m_oos["Calmar"],
            "oos_vs_full_calmar_ratio": (
                m_oos["Calmar"] / m_full["Calmar"]
                if m_full["Calmar"] and not math.isnan(m_full["Calmar"]) and m_full["Calmar"] != 0
                else float("nan")
            ),
            "overfit_flag": overfit,
            "overfit_reasons": reasons,
        },
        "series_paths": {
            "oos_daily_csv": "data/oos_daily_returns.csv",
            "full_daily_csv": "data/full_daily_returns.csv",
        },
    }


def write_four_pack(result: dict[str, Any], elapsed: float) -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / "wf_result.json").write_text(json.dumps(result, ensure_ascii=False, indent=2, default=str), encoding="utf-8")

    m_oos = result["metrics"]["oos_concat"]
    m_is = result["metrics"]["is_concat_train_segments"]
    m_full = result["metrics"]["full_sample_frozen_TV25"]
    cmp_ = result["comparison"]

    hyp = rf"""# HYPOTHESIS · {KNIFE_ID}

## 冻结面层（B45 face book）

| 维度 | 设定 |
|------|------|
| Breadth | **B45**（face `risk_on`，宽基 breadth≥45%） |
| 池 / 填席 | `spike_ft` **max5** + **SHARPE20** |
| 出场 | **E0** |
| 总暴露 | **TV25**（σ\*=0.25）为全样本对照；WF 内仅轻调 TV |
| 信号 / 成交 | Fri≥14:30 → 当周收盘（LIVE1430 研究口径） |
| 成本 / 杠杆 | **0.2% RT**；**L≤1** |
| 池 | 研究池（AUM≥2亿），非实盘 / 非 champion |

## Walk-forward 协议（kovainvest 式）

- **Train / Test / Step**：{TRAIN_W} 周 / {TEST_W} 周 / {STEP_W} 周，滚动前进。
- **轻调轴（本刀唯一）**：**TV σ\*** ∈ {{22, 25, 28, 33}}（映射 0.22–0.33）；不在 WF 内动 breadth / 填席 / 出场。
- **Train 内选型**：各 TV 在 train 窗拼接日收益上取 **Calmar 最大**；胜出 σ\* 用于紧随其后的 **26 周 OOS**，无 test 窥视。
- **评判**：以 **OOS 拼接净值** 的 Calmar / Sharpe / maxDD / 周胜率 为准；全样本冻结 TV25 仅作过拟合对照。

## 过拟合红旗（机械）

1. OOS Calmar < **{OVERFIT_RATIO:.0%}** × 全样本 face Calmar；或
2. 全样本 Calmar > 0.3 且 OOS Calmar < 0.15。

**本跑结论**：overfit_flag = **{cmp_['overfit_flag']}** — {'；'.join(cmp_['overfit_reasons']) or '未触发红旗'}。
"""
    (ROOT / "HYPOTHESIS.md").write_text(hyp, encoding="utf-8")

    main = rf"""# 主表 · {KNIFE_ID}

样本日历：{result['coverage']['calendar']}（{result['coverage']['n_weeks']} 周）  
WF：train {TRAIN_W}w / test {TEST_W}w / step {STEP_W}w；折数 {len(result['folds'])}；轻调轴 TV σ\*。

| 切片 | ret | maxDD | Calmar | Sharpe | 周胜率 |
|------|-----:|------:|-------:|-------:|------:|
| **OOS 拼接**（主评判） | {pct(m_oos['ret'])} | {pct(m_oos['maxDD'])} | {fmt(m_oos['Calmar'])} | {fmt(m_oos['sharpe'])} | {pct(m_oos['hit_rate_weekly'])} |
| IS（各折 train 段，按折选型 TV） | {pct(m_is['ret'])} | {pct(m_is['maxDD'])} | {fmt(m_is['Calmar'])} | {fmt(m_is['sharpe'])} | {pct(m_is['hit_rate_weekly'])} |
| 全样本冻结 **TV25** face | {pct(m_full['ret'])} | {pct(m_full['maxDD'])} | {fmt(m_full['Calmar'])} | {fmt(m_full['sharpe'])} | {pct(m_full['hit_rate_weekly'])} |

## OOS vs 全样本 Calmar

| 指标 | 值 |
|------|---:|
| 全样本 Calmar (TV25) | {fmt(m_full['Calmar'])} |
| OOS 拼接 Calmar | {fmt(m_oos['Calmar'])} |
| OOS / 全样本 | {fmt(cmp_['oos_vs_full_calmar_ratio'])} |
| 过拟合红旗 | **{'是' if cmp_['overfit_flag'] else '否'}** |

### 各折选型

| fold | train_end | test_end | chosen_TV |
|------|-----------|----------|-----------|
"""
    for f in result["folds"]:
        main += f"| {f['fold']} | {f['train_end']} | {f['test_end']} | {f['chosen_tv']} |\n"
    main += f"\n耗时约 {elapsed:.1f}s。详情见 `data/wf_result.json`。\n"
    (ROOT / "main_table.md").write_text(main, encoding="utf-8")

    notes = f"""# NOTES · {KNIFE_ID}

- **引擎**：`face_run.py` + `CLOUD-BATCH-2026-10-26` 研究缓存（classify / 14:30 / face）。
- **持仓路径**：每周 `simulate()`（B45 risk_on + spike_ft max5 + SHARPE20）；**TV 仅进入** `run_live_tv` 杠杆层。
- **WF 实现**：每折在 train+test 连续日历上重跑 simulate（仓位跨 train→test 连续），TV 在 train 日收益上选型后固定用于该折 test 日收益；OOS 段按时间拼接。
- **未改**：`strategy_exec` / LIVE / champion；本目录纯研究。
- **Kit**：`{result['coverage']['kit']}`

## 覆盖

```json
{json.dumps(result['coverage'], ensure_ascii=False, indent=2)}
```
"""
    (ROOT / "NOTES.md").write_text(notes, encoding="utf-8")


def pct(x: float) -> str:
    if x is None or (isinstance(x, float) and math.isnan(x)):
        return "—"
    return f"{100 * x:.1f}%"


def fmt(x: float) -> str:
    if x is None or (isinstance(x, float) and math.isnan(x)):
        return "—"
    return f"{x:.2f}"


def main() -> None:
    t0 = time.time()
    ctx = load_face_context()
    result = run_walk_forward(ctx)

    r_full = daily_returns_for_hold(ctx.hold_full, ctx.days, ctx.px, ctx.R, FACE_SIGMA)
    oos_parts = []
    for f in result["folds"]:
        span_cal = [d for d in ctx.calendar if f["train_start"] <= d <= f["test_end"]]
        hold_span, _ = simulate_b45(
            span_cal,
            ctx_snaps=ctx.snaps,
            closes=ctx.closes_w_sig,
            alias=ctx.alias,
            aum=ctx.aum,
            daily=ctx.daily,
            risk=ctx.risk_b45,
        )
        sig = f["sigma"]
        r_span = daily_returns_for_hold(hold_span, ctx.days, ctx.px, ctx.R, sig)
        r_test = r_span[
            (r_span.index >= pd.Timestamp(f["test_start"]))
            & (r_span.index <= pd.Timestamp(f["test_end"]))
        ]
        oos_parts.append(r_test)
    oos_r = pd.concat(oos_parts).sort_index()
    oos_r = oos_r[~oos_r.index.duplicated(keep="first")]

    OUT.mkdir(parents=True, exist_ok=True)
    oos_r.to_csv(OUT / "oos_daily_returns.csv", header=["ret"])
    r_full.to_csv(OUT / "full_daily_returns.csv", header=["ret"])
    pd.DataFrame(result["folds"]).to_csv(OUT / "wf_folds.csv", index=False)

    write_four_pack(result, time.time() - t0)
    print("done", ROOT, flush=True)
    print(json.dumps(result["comparison"], indent=2), flush=True)


if __name__ == "__main__":
    main()
