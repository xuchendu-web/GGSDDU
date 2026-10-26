#!/usr/bin/env python3
"""MAXDD20-GATE-B45: weekly hard DD gate on B45+S20 FACE vs ungated baseline.

See criterion.md for trigger (−20%, next week flat) and recovery (−18% hysteresis).
"""
from __future__ import annotations

import importlib.util
import json
import math
import sys
import time
from pathlib import Path
from typing import Any

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

CLOUD = Path(__file__).resolve().parents[1] / "cloud_batch" / "CLOUD-BATCH-2026-10-26"
EXT_RUN = (
    Path(__file__).resolve().parents[1]
    / "cloud_batch"
    / "SPIKE-S20-EXTEND-REBASE-LIVE1430"
    / "run.py"
)
RUN_DIR = Path(__file__).resolve().parent
OUT = RUN_DIR
SCRATCH = RUN_DIR / "_scratch"

TRIGGER_DD = -0.20
RECOVER_DD = -0.18
NEIGHBOR_TRIGGERS = (-0.22, -0.18)


def load_extend():
    sys.path.insert(0, str(CLOUD / "scripts"))
    spec = importlib.util.spec_from_file_location("spike_ext", EXT_RUN)
    if spec is None or spec.loader is None:
        raise SystemExit(f"cannot load {EXT_RUN}")
    mod = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = mod
    spec.loader.exec_module(mod)
    mod.KIT = CLOUD
    mod.SCRIPTS = CLOUD / "scripts"
    mod.CACHE = CLOUD / "data" / "research_cache"
    mod.UNI_CSV = CLOUD / "data" / "universe_replace_only_436.csv"
    mod.WEEK = mod.CACHE / "week"
    mod.FACE = mod.CACHE / "holdings_ro2_extended.csv"
    mod.DAY_DIR = mod.CACHE / "day"
    mod.NOON_CSV = mod.CACHE / "fri_1430_through_20261023.csv"
    mod.SINA_DAILY = mod.CACHE / "sina_daily"
    mod.SNAP_CACHE = CLOUD / "data" / "cache_1430_snaps.json"
    mod.OUT = SCRATCH
    SCRATCH.mkdir(parents=True, exist_ok=True)
    return mod


def stats_full(s: pd.Series) -> dict[str, float]:
    if s is None or len(s) < 2:
        return {
            "ret": float("nan"),
            "maxDD": float("nan"),
            "CAGR": float("nan"),
            "Calmar": float("nan"),
            "sharpe": float("nan"),
        }
    q = (1 + s).cumprod()
    ret = float(q.iloc[-1] - 1)
    dd = float((q / q.cummax().clip(lower=1e-12) - 1).min())
    n = (s.index[-1] - s.index[0]).days
    cagr = (1 + ret) ** (365.25 / n) - 1 if n > 0 and (1 + ret) > 0 else float("nan")
    cal = cagr / abs(dd) if dd < 0 else float("nan")
    sharpe = (
        float(s.mean() / s.std(ddof=1) * np.sqrt(252))
        if len(s) > 1 and s.std(ddof=1) > 0
        else float("nan")
    )
    return {"ret": ret, "maxDD": dd, "CAGR": cagr, "Calmar": cal, "sharpe": sharpe}


def friday_week_id(ts: pd.Timestamp | pd.DatetimeIndex) -> pd.Timestamp | pd.DatetimeIndex:
    """Map each calendar day to the Friday ending its Mon–Fri week."""
    idx = pd.DatetimeIndex(ts) if not isinstance(ts, pd.DatetimeIndex) else ts
    wd = idx.day_of_week  # Mon=0 … Fri=4
    delta = (4 - wd) % 7
    return (idx + pd.to_timedelta(delta, unit="D")).normalize()


def apply_weekly_dd_gate(
    r: pd.Series,
    trigger: float = TRIGGER_DD,
    recover: float = RECOVER_DD,
) -> tuple[pd.Series, pd.Series, dict[str, Any]]:
    """Friday-close state machine; gate applies m=0 on all days of gated weeks."""
    r = r.sort_index()
    week_labels = friday_week_id(r.index)
    week_end = r.groupby(week_labels).apply(lambda x: x.index[-1], include_groups=False)
    week_end = week_end.sort_values()

    gated_nav = 1.0
    peak = 1.0
    gate_active_next = False
    n_gate_weeks = 0
    n_trigger_events = 0
    n_recover_events = 0

    week_mult: dict[pd.Timestamp, float] = {}
    for fri in week_end.values:
        fri = pd.Timestamp(fri)
        m = 0.0 if gate_active_next else 1.0
        week_mult[fri] = m
        if m == 0.0:
            n_gate_weeks += 1

        wk_id = friday_week_id(pd.DatetimeIndex([fri]))[0]
        mask = week_labels == wk_id
        wk_ret = float((1 + r.loc[mask]).prod() - 1)
        gated_nav *= 1.0 + wk_ret * m
        peak = max(peak, gated_nav)
        dd_w = gated_nav / peak - 1 if peak > 0 else 0.0

        if gate_active_next:
            if dd_w > recover:
                gate_active_next = False
                n_recover_events += 1
            else:
                gate_active_next = True
        else:
            if dd_w <= trigger:
                gate_active_next = True
                n_trigger_events += 1
            else:
                gate_active_next = False

    mult_daily = pd.Series(1.0, index=r.index, dtype=float)
    for fri, m in week_mult.items():
        wk_id = friday_week_id(pd.DatetimeIndex([fri]))[0]
        mult_daily.loc[week_labels == wk_id] = m

    gated_r = r * mult_daily
    st = stats_full(gated_r)
    meta = {
        "trigger_dd": trigger,
        "recover_dd": recover,
        "n_gate_weeks": n_gate_weeks,
        "n_trigger_events": n_trigger_events,
        "n_recover_events": n_recover_events,
        "realized_maxDD": st["maxDD"],
        "gate_ok": abs(st["maxDD"]) <= abs(trigger) + 0.005,
        "avg_exposure": float(mult_daily.mean()),
    }
    return gated_r, mult_daily, meta


def avg_turnover_weekly(hold: dict[str, list[str]], calendar: list[str], max_pos: int = 5) -> float:
    to_vals: list[float] = []
    prev: set[str] = set()
    for d in calendar[:-1]:
        cur = set(hold.get(d) or [])
        if prev or cur:
            to_vals.append(len(prev.symmetric_difference(cur)) / (2.0 * max_pos))
        prev = cur
    return float(np.mean(to_vals)) if to_vals else 0.0


def pct(x: float | None) -> str:
    if x is None or (isinstance(x, float) and (math.isnan(x) or math.isinf(x))):
        return "—"
    return f"{100 * x:.1f}%"


def metrics_row(
    name: str,
    r: pd.Series,
    sim_st: dict[str, Any],
    avg_to: float,
    gate_meta: dict[str, Any] | None = None,
) -> dict[str, Any]:
    st = stats_full(r)
    r2022 = r[(r.index >= "2020-01-01") & (r.index <= "2022-12-31")]
    r2023 = r[r.index >= "2023-01-01"]
    st2022 = stats_full(r2022) if len(r2022) > 5 else {k: float("nan") for k in st}
    st2023 = stats_full(r2023) if len(r2023) > 5 else {k: float("nan") for k in st}
    row: dict[str, Any] = {
        "book": name,
        **st,
        "2020-22_ret": st2022["ret"],
        "2020-22_DD": st2022["maxDD"],
        "2020-22_Calmar": st2022["Calmar"],
        "2023-26_ret": st2023["ret"],
        "2023-26_DD": st2023["maxDD"],
        "2023-26_Calmar": st2023["Calmar"],
        "avg_turnover": avg_to,
        "cash_week_pct": sim_st.get("cash_week_pct", float("nan")),
    }
    if gate_meta:
        for k, v in gate_meta.items():
            row[f"gate_{k}"] = v
    return row


def run_b45_pipeline(ext):
    """B45 FACE from spike_ext (same as B45-MAXDD-GATE-SPIKE-S20)."""
    EVAL_START = ext.EVAL_START
    END_S = ext.END_S
    UNI_CSV = ext.UNI_CSV
    WEEK = ext.WEEK
    FACE = ext.FACE
    NOON_CSV = ext.NOON_CSV
    DAY_DIR = ext.DAY_DIR
    SINA_DAILY = ext.SINA_DAILY
    SNAP_CACHE = ext.SNAP_CACHE
    OUT_SCR = ext.OUT

    uni = pd.read_csv(UNI_CSV)
    uni["code"] = uni["code"].astype(str).str.zfill(6)
    uni = uni[uni["aum"] >= 2].copy()
    codes = uni["code"].tolist()
    aum = {r.code: float(r.aum or 0) for r in uni.itertuples()}
    code_set = set(codes)

    noon = pd.read_csv(NOON_CSV)
    noon["code"] = noon["etf_code"].astype(str).str.split(".").str[0]
    noon["trade_date"] = noon["trade_date"].astype(str).str[:10]
    noon["friday_week_date"] = noon["friday_week_date"].astype(str).str[:10]
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
            risk_b45[d] = str(v).lower() in {"1", "true", "True"}
    for d in calendar:
        risk_b45.setdefault(d, False)
    risk_b45[calendar[-1]] = False

    raws_w: dict[str, dict] = {}
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
        alias[c] = {d: hit for d in calendar if (hit := ext.nearest_date(d, ds, 3))}

    sina = ext.load_sina_closes(codes)
    daily = ext.load_daily_closes(codes, sina)

    from collections import defaultdict

    noon_w: dict[str, dict[str, float]] = defaultdict(dict)
    blocked_empty: dict[str, set[str]] = defaultdict(set)
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

    cached = json.loads(SNAP_CACHE.read_text(encoding="utf-8"))
    by_rows = cached.get("by_code") or {}
    snaps = {c: ext.snap_index(by_rows.get(c) or []) for c in codes}

    name = "FACE-B45-S20"
    trades, hold, st = ext.simulate(
        calendar,
        snaps,
        closes_w_sig,
        alias,
        aum,
        daily,
        risk_b45,
        ext.sharpe_key,
        name,
        True,
        20,
        5,
    )

    all_codes: set[str] = set()
    for cs in hold.values():
        all_codes |= set(cs)
    px_map = {}
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
    px = pd.DataFrame(px_map).sort_index()
    px = px.loc[(px.index >= EVAL_START) & (px.index <= END_S)]
    R = px.pct_change()
    days = px.dropna(how="all").index
    days = days[(days >= EVAL_START) & (days <= END_S)]

    hd = {pd.Timestamp(d): cs for d, cs in hold.items()}
    r, L = ext.run_live_tv(hd, days, px, R, sigma_star=ext.SIGMA_STAR, cash_fill=None)
    avg_to = avg_turnover_weekly(hold, calendar, 5)

    pd.DataFrame(trades).to_csv(OUT_SCR / "trades_FACE-B45-S20.csv", index=False)
    cov = {"calendar_end": actual_end, "n_weeks": len(calendar), "n_codes": len(codes)}
    return r, L, hold, st, calendar, cov


def delta_vs_base(row: pd.Series, base: pd.Series) -> dict[str, float]:
    return {
        "d_ret_pp": (row["ret"] - base["ret"]) * 100,
        "d_abs_mdd_pp": (abs(row["maxDD"]) - abs(base["maxDD"])) * 100,
        "d_calmar": row["Calmar"] - base["Calmar"],
        "d_sharpe": row["sharpe"] - base["sharpe"],
        "d_turnover": row["avg_turnover"] - base["avg_turnover"],
    }


def judge_h1(
    base: pd.Series,
    gated: pd.Series,
    d: dict[str, float],
    gate_meta: dict[str, Any],
) -> tuple[bool, str]:
    """H1 holds (gate not worth crown) unless positive gate recorded."""
    dd15_note = (
        "旁证：DD15 **日频**压廓闸已证伪（ret 4.7% / Calmar 0.05 vs face 131.6% / 0.70，"
        "`research/cloud_batch/B45-MAXDD-GATE-SPIKE-S20/REPORT.md`）。"
    )
    n_trig = int(gate_meta.get("n_trigger_events") or 0)
    if n_trig == 0:
        return True, (
            f"**闸惰性（不记正、不换冠）**：face |MDD|={pct(abs(float(base['maxDD'])))} 未触 −20%，"
            f"周频硬闸 0 次触发，主表与 face 完全一致；无法在「压回撤↔保收益」上验收 DD20。"
            f"{dd15_note}"
        )

    ruler_cover = d["d_ret_pp"] >= d["d_abs_mdd_pp"]
    strong_ok = gated["2023-26_ret"] >= base["2023-26_ret"] * 0.9
    main_better = gated["Calmar"] > base["Calmar"] or gated["sharpe"] > base["sharpe"]
    if main_better and strong_ok and ruler_cover:
        return False, (
            f"**记正闸（不换冠）**：DD20 触发 {n_trig} 次，Calmar/Sharpe 优于 face，"
            f"2023–26 未踏空，Δret 盖住 Δ|MDD|。"
        )

    parts: list[str] = []
    if not ruler_cover:
        parts.append(f"Δret（{d['d_ret_pp']:+.1f}pp）未盖住 Δ|MDD|（{d['d_abs_mdd_pp']:+.1f}pp）")
    if not strong_ok:
        parts.append(
            f"2023–26 踏空（闸 {pct(gated['2023-26_ret'])} vs face {pct(base['2023-26_ret'])}）"
        )
    if not main_better:
        parts.append("主表 Calmar/Sharpe 未优于 face")
    return True, f"**H1 成立（证伪闸）**：{'；'.join(parts)}。{dd15_note}"


def main() -> None:
    t0 = time.time()
    OUT.mkdir(parents=True, exist_ok=True)
    ext = load_extend()
    sys.path.insert(0, str(ext.SCRIPTS))

    print("B45 FACE pipeline…", flush=True)
    r_base, _L, hold, sim_st, calendar, cov = run_b45_pipeline(ext)

    series: dict[str, pd.Series] = {"FACE-B45-S20": r_base}
    gate_meta_by: dict[str, dict[str, Any]] = {}

    rg, _exp, meta = apply_weekly_dd_gate(r_base, TRIGGER_DD, RECOVER_DD)
    series["FACE-B45-S20-DD20-WK"] = rg
    gate_meta_by["FACE-B45-S20-DD20-WK"] = meta
    print(
        f"  DD20-WK: maxDD={pct(meta['realized_maxDD'])} gate_weeks={meta['n_gate_weeks']} "
        f"triggers={meta['n_trigger_events']}",
        flush=True,
    )

    neighbor_rows: list[dict[str, Any]] = []
    for trig in NEIGHBOR_TRIGGERS:
        label = f"NEIGH-TRIG{int(abs(trig)*100)}"
        rn, _, mn = apply_weekly_dd_gate(r_base, trig, RECOVER_DD)
        neighbor_rows.append(
            {
                "label": label,
                "trigger": trig,
                **stats_full(rn),
                **{f"gate_{k}": v for k, v in mn.items()},
            }
        )

    rows = []
    for name, r in series.items():
        meta = gate_meta_by.get(name)
        to = avg_turnover_weekly(hold, calendar, 5)
        rows.append(metrics_row(name, r, sim_st, to, meta))

    df = pd.DataFrame(rows)
    df.to_csv(OUT / "table.csv", index=False)
    df.to_csv(OUT / "metrics.csv", index=False)
    pd.DataFrame(neighbor_rows).to_csv(OUT / "neighbor_triggers.csv", index=False)

    for name, r in series.items():
        (1 + r).cumprod().to_csv(OUT / f"nav_{name}.csv", header=["nav"])

    eq = pd.DataFrame({k: (1 + series[k]).cumprod() for k in series})
    eq.to_csv(OUT / "equity.csv")

    fig, ax = plt.subplots(figsize=(11, 5.5), dpi=120)
    for name in series:
        ax.plot(eq.index, eq[name], label=name, lw=1.6)
    ax.set_yscale("log")
    ax.set_title("MAXDD20-GATE-B45 (weekly hard gate)")
    ax.set_ylabel("NAV (log)")
    ax.grid(True, alpha=0.3)
    ax.legend(fontsize=8)
    fig.tight_layout()
    fig.savefig(OUT / "equity_curve.png")
    plt.close(fig)

    base = df[df.book == "FACE-B45-S20"].iloc[0]
    gated = df[df.book == "FACE-B45-S20-DD20-WK"].iloc[0]
    d20 = delta_vs_base(gated, base)
    h1_holds, verdict = judge_h1(base, gated, d20, meta)

    criterion_src = (RUN_DIR / "criterion.md").read_text(encoding="utf-8")

    summary = {
        "title": "MAXDD20-GATE-B45",
        "coverage": cov,
        "sim_stats": sim_st,
        "table": rows,
        "delta_dd20_vs_face": d20,
        "neighbor_triggers": neighbor_rows,
        "h1_holds": h1_holds,
        "verdict": verdict,
        "elapsed_sec": round(time.time() - t0, 1),
    }
    (OUT / "summary.json").write_text(
        json.dumps(summary, ensure_ascii=False, indent=2, default=str), encoding="utf-8"
    )

    def row_md(row: pd.Series) -> str:
        return (
            f"| {row['book']} | {pct(row['ret'])} | {pct(row['maxDD'])} | {pct(row['CAGR'])} | "
            f"{row['Calmar']:.2f} | {row['sharpe']:.2f} | {row['avg_turnover']:.3f} | "
            f"{pct(row['2020-22_ret'])}/{pct(row['2020-22_DD'])} | "
            f"{pct(row['2023-26_ret'])}/{pct(row['2023-26_DD'])} |"
        )

    impl = f"""- **面层冻结**：B45 + spike_ft max5 + SHARPE20 + E0 + TV25；Fri≥14:30/收盘；0.2%RT；L≤1。
- **唯一叠加（周频硬闸）**：周五收盘 `DD_w≤−20%` → **次周** `m=0`；闸内 `DD_w>−18%` → **次周** `m=1`。
- **引擎**：`SPIKE-S20-EXTEND-REBASE-LIVE1430` simulate + `run_live_tv`；数据 `CLOUD-BATCH-2026-10-26`。
- **邻档旁注**：触发阈 −22% / −18% 见 `neighbor_triggers.csv`。
- **红线**：研究池；不换冠；未写 strategy_exec / LIVE_OPS。

| 覆盖 | 值 |
|---|---|
| 样本终点 | {cov['calendar_end']} |
| 日历周 | {cov['n_weeks']} |
| 可投池 | {cov['n_codes']} |
| 闸内周数 | {meta['n_gate_weeks']} |
| 触发次数 | {meta['n_trigger_events']} |"""

    report = f"""# REPORT · MAXDD20-GATE-B45

## 1. 准则原文

```
{criterion_src.strip()}
```

## 2. 实现要点

{impl}

## 3. 主表（vs 无闸 FACE）

| book | ret | maxDD | CAGR | Calmar | Sharpe | turnover | 2020–22 ret/DD | 2023–26 ret/DD |
|---|---:|---:|---:|---:|---:|---:|---|---|
{row_md(base)}
{row_md(gated)}

### 旁证 · DD15 日频压廓闸（已证伪，同窗 face）

| book | ret | maxDD | Calmar | 2023–26 ret | 来源 |
|---|---:|---:|---:|---:|---|
| FACE-B45-S20-DD15（日频） | 4.7% | -15.0% | 0.05 | -0.1% | `B45-MAXDD-GATE-SPIKE-S20/summary.json` |

### Δ vs FACE（DD20 周频闸）

| 项 | 值 |
|---|---:|
| Δret | {d20['d_ret_pp']:+.1f}pp |
| Δ|MDD| | {d20['d_abs_mdd_pp']:+.1f}pp |
| ΔCalmar | {d20['d_calmar']:+.2f} |
| ΔSharpe | {d20['d_sharpe']:+.2f} |
| Δturnover | {d20['d_turnover']:+.3f} |
| gate_ok (|MDD|≤20.5%) | {bool(gated.get('gate_gate_ok', gated.get('gate_ok', False)))} |
| 尺子：Δret 盖住 Δ|MDD| | {d20['d_ret_pp'] >= d20['d_abs_mdd_pp']} |
| 2023–26 ≥ face×0.9 | {gated['2023-26_ret'] >= base['2023-26_ret'] * 0.9} |

## 4. 一句证伪或记正

{verdict}

耗时约 {summary['elapsed_sec']}s。
"""
    (OUT / "REPORT.md").write_text(report, encoding="utf-8")
    print("done", OUT, flush=True)
    print(verdict, flush=True)


if __name__ == "__main__":
    main()
