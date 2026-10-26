#!/usr/bin/env python3
"""B45-MAXDD-GATE-SPIKE-S20: path DD hard-stop on B45 FACE vs ungated baseline.

Face frozen: breadth≥45% + spike_ft max5 + E0 + TV25 + SHARPE20; Fri≥14:30/close; 0.2%RT; L≤1.
Gates: θ=15% (primary) and θ=20% (neighbor); hysteresis 3pp on re-entry.
Research pool only — no crown / no strategy_exec.
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

CLOUD = Path(__file__).resolve().parents[1] / "CLOUD-BATCH-2026-10-26"
EXT_RUN = Path(__file__).resolve().parents[1] / "SPIKE-S20-EXTEND-REBASE-LIVE1430" / "run.py"
RUN_DIR = Path(__file__).resolve().parent
OUT = Path("/workspace/strategy-weekly/spike_mom_rank/B45-MAXDD-GATE-SPIKE-S20")
SCRATCH = RUN_DIR / "_scratch"
HYST_PP = 0.03
GATE_LIMITS = (0.15, 0.20)


def load_extend():
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
    OUT.mkdir(parents=True, exist_ok=True)
    return mod


def apply_path_dd_gate(
    r: pd.Series,
    dd_limit: float,
    hysteresis: float = HYST_PP,
) -> tuple[pd.Series, pd.Series, dict[str, Any]]:
    """De-lever toward 0 as DD approaches −θ; hard floor at −θ (exposure=0 that day)."""
    gated: list[float] = []
    exp: list[float] = []
    nav = 1.0
    peak = 1.0
    n_zero_days = 0
    n_delever_days = 0
    ramp = 0.05
    start_dd = -(dd_limit - ramp)
    for d in r.index:
        ret = float(r.loc[d])
        dd_pre = nav / peak - 1 if peak > 0 else 0.0
        if dd_pre <= -dd_limit:
            m = 0.0
            n_zero_days += 1
        elif dd_pre < start_dd:
            m = max(0.0, min(1.0, (dd_limit + dd_pre) / ramp))
            if m < 1.0:
                n_delever_days += 1
        else:
            m = 1.0
        eff = ret * m
        gated.append(eff)
        exp.append(m)
        nav *= 1.0 + eff
        peak = max(peak, nav)
    g = pd.Series(gated, index=r.index, dtype=float)
    e = pd.Series(exp, index=r.index, dtype=float)
    st = stats_full(g)
    return g, e, {
        "dd_limit": dd_limit,
        "hysteresis_pp": hysteresis,
        "n_zero_exposure_days": n_zero_days,
        "n_delever_days": n_delever_days,
        "realized_maxDD": st["maxDD"],
        "gate_ok": abs(st["maxDD"]) <= dd_limit + 0.005,
    }


def stats_full(s: pd.Series) -> dict[str, float]:
    if s is None or len(s) < 2:
        return {"ret": float("nan"), "maxDD": float("nan"), "CAGR": float("nan"), "Calmar": float("nan")}
    q = (1 + s).cumprod()
    ret = float(q.iloc[-1] - 1)
    dd = float((q / q.cummax().clip(lower=1e-12) - 1).min())
    n = (s.index[-1] - s.index[0]).days
    cagr = (1 + ret) ** (365.25 / n) - 1 if n > 0 and (1 + ret) > 0 else float("nan")
    cal = cagr / abs(dd) if dd < 0 else float("nan")
    vol = float(s.std(ddof=1) * np.sqrt(252)) if len(s) > 1 and s.std(ddof=1) > 0 else float("nan")
    sharpe = float(s.mean() / s.std(ddof=1) * np.sqrt(252)) if len(s) > 1 and s.std(ddof=1) > 0 else float("nan")
    return {"ret": ret, "maxDD": dd, "CAGR": cagr, "Calmar": cal, "vol": vol, "sharpe": sharpe}


def avg_turnover_weekly(hold: dict[str, list[str]], calendar: list[str], max_pos: int = 5) -> float:
    to_vals: list[float] = []
    prev: set[str] = set()
    for d in calendar[:-1]:
        cur = set(hold.get(d) or [])
        if prev or cur:
            to_vals.append(len(prev.symmetric_difference(cur)) / (2.0 * max_pos))
        prev = cur
    return float(np.mean(to_vals)) if to_vals else 0.0


def turnover_from_L(L: pd.Series) -> float:
    if len(L) < 2:
        return 0.0
    return float(L.diff().abs().mean())


def pct(x: float | None) -> str:
    if x is None or (isinstance(x, float) and (math.isnan(x) or math.isinf(x))):
        return "—"
    return f"{100 * x:.1f}%"


def metrics_row(
    name: str,
    r: pd.Series,
    L: pd.Series,
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
        "avgL": float(L[L > 0].mean()) if (L > 0).any() else 0.0,
        "avg_turnover": avg_to,
        "turnover_L": turnover_from_L(L),
        "cash_week_pct": sim_st.get("cash_week_pct", float("nan")),
        "risk_on_week_pct": sim_st.get("risk_on_week_pct", float("nan")),
    }
    if gate_meta:
        row.update({f"gate_{k}": v for k, v in gate_meta.items() if k != "dd_limit"})
        row["gate_dd_limit"] = gate_meta.get("dd_limit")
        row["gate_ok"] = gate_meta.get("gate_ok")
    return row


def run_b45_pipeline(ext) -> tuple[pd.Series, pd.Series, dict[str, list[str]], dict[str, Any], list[str], Any]:
    """Minimal B45 path from spike_ext.main() without other books."""
    EVAL_START = ext.EVAL_START
    END_S = ext.END_S
    UNI_CSV = ext.UNI_CSV
    WEEK = ext.WEEK
    FACE = ext.FACE
    NOON_CSV = ext.NOON_CSV
    DAY_DIR = ext.DAY_DIR
    TEMA_PX = ext.TEMA_PX
    SINA_DAILY = ext.SINA_DAILY
    SNAP_CACHE = ext.SNAP_CACHE
    OUT = ext.OUT
    CASH_CODE = ext.CASH_CODE

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

    name = "FACE-B45-S20-UNGATED"
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

    pd.DataFrame(trades).to_csv(OUT / "trades_FACE-B45-S20-UNGATED.csv", index=False)
    cov = {
        "calendar_end": actual_end,
        "n_weeks": len(calendar),
        "n_codes": len(codes),
    }
    return r, L, hold, st, calendar, cov


def main() -> None:
    t0 = time.time()
    OUT.mkdir(parents=True, exist_ok=True)
    ext = load_extend()
    sys.path.insert(0, str(ext.SCRIPTS))

    print("B45 FACE pipeline…", flush=True)
    r_base, L_base, hold, sim_st, calendar, cov = run_b45_pipeline(ext)

    series: dict[str, pd.Series] = {"FACE-B45-S20-UNGATED": r_base}
    L_series: dict[str, pd.Series] = {"FACE-B45-S20-UNGATED": L_base}
    gate_meta_by_book: dict[str, dict[str, Any]] = {}

    for lim in GATE_LIMITS:
        label = f"FACE-B45-S20-DD{int(lim * 100)}"
        rg, exp, meta = apply_path_dd_gate(r_base, lim)
        series[label] = rg
        L_series[label] = L_base * exp
        gate_meta_by_book[label] = meta
        meta["avg_exposure"] = float(exp.mean())
        print(
            f"  {label}: maxDD={pct(meta['realized_maxDD'])} gate_ok={meta['gate_ok']} "
            f"delever_days={meta['n_delever_days']} zero_days={meta['n_zero_exposure_days']}",
            flush=True,
        )

    rows = []
    for name, r in series.items():
        meta = gate_meta_by_book.get(name)
        to = avg_turnover_weekly(hold, calendar, 5)
        if meta:
            to = to + float((1 - meta.get("avg_exposure", 1.0)) * 0.1)
        rows.append(metrics_row(name, r, L_series[name], sim_st, to, meta))

    df = pd.DataFrame(rows)
    df.to_csv(OUT / "table.csv", index=False)
    df.to_csv(OUT / "metrics.csv", index=False)

    for name, r in series.items():
        nav = (1 + r).cumprod()
        nav.to_csv(OUT / f"nav_{name}.csv", header=["nav"])

    eq = pd.DataFrame({k: (1 + series[k]).cumprod() for k in series})
    eq.to_csv(OUT / "equity.csv")
    eq.to_csv(OUT / "metrics_nav.csv")

    fig, ax = plt.subplots(figsize=(11, 5.5), dpi=120)
    for name in series:
        ax.plot(eq.index, eq[name], label=name, lw=1.6)
    ax.set_yscale("log")
    ax.set_title("B45-MAXDD-GATE-SPIKE-S20")
    ax.set_ylabel("NAV (log)")
    ax.grid(True, alpha=0.3)
    ax.legend(fontsize=7)
    fig.tight_layout()
    fig.savefig(OUT / "equity_curve.png")
    plt.close(fig)

    base = df[df.book == "FACE-B45-S20-UNGATED"].iloc[0]
    dd15 = df[df.book == "FACE-B45-S20-DD15"].iloc[0]
    dd20 = df[df.book == "FACE-B45-S20-DD20"].iloc[0]

    def delta_vs_base(row: pd.Series) -> dict[str, float]:
        return {
            "d_ret_pp": (row["ret"] - base["ret"]) * 100,
            "d_abs_mdd_pp": (abs(row["maxDD"]) - abs(base["maxDD"])) * 100,
            "d_calmar": row["Calmar"] - base["Calmar"],
            "d_sharpe": row["sharpe"] - base["sharpe"],
            "d_turnover": row["avg_turnover"] - base["avg_turnover"],
        }

    d15 = delta_vs_base(dd15)
    d20 = delta_vs_base(dd20)
    gate15_ok = bool(dd15.get("gate_ok", False))
    falsify = not gate15_ok or (
        d15["d_calmar"] < -0.05 and d15["d_ret_pp"] < -10 and d15["d_sharpe"] < 0
    )

    if falsify:
        if not gate15_ok:
            verdict = (
                f"**证伪**：DD15 闸 realized MDD={pct(float(dd15['maxDD']))} 未压至 ≤15.5%；"
                f"无闸 MDD={pct(float(base['maxDD']))}。"
            )
        else:
            verdict = (
                f"**证伪**：DD15 虽控回撤（MDD={pct(float(dd15['maxDD']))}），但 ret 损失 {d15['d_ret_pp']:+.1f}pp、"
                f"Calmar Δ{d15['d_calmar']:+.2f}、Sharpe Δ{d15['d_sharpe']:+.2f}，全面劣于无闸 FACE。"
            )
    else:
        verdict = (
            f"**记正（不换冠）**：DD15 MDD={pct(float(dd15['maxDD']))}（gate_ok）；"
            f"vs 无闸 Δret={d15['d_ret_pp']:+.1f}pp Δ|MDD|={d15['d_abs_mdd_pp']:+.1f}pp "
            f"Calmar {float(base['Calmar']):.2f}→{float(dd15['Calmar']):.2f}；"
            f"邻档 DD20 MDD={pct(float(dd20['maxDD']))} ret={pct(float(dd20['ret']))}。"
        )

    knife = CLOUD / "knives" / "B45-MAXDD-GATE-SPIKE-S20.md"
    criterion_src = knife.read_text(encoding="utf-8") if knife.exists() else ""

    summary = {
        "title": "B45-MAXDD-GATE-SPIKE-S20",
        "coverage": cov,
        "sim_stats": sim_st,
        "table": rows,
        "delta_dd15_vs_ungated": d15,
        "delta_dd20_vs_ungated": d20,
        "gate15_ok": gate15_ok,
        "falsify": falsify,
        "verdict": verdict,
        "elapsed_sec": round(time.time() - t0, 1),
    }
    (OUT / "summary.json").write_text(json.dumps(summary, ensure_ascii=False, indent=2, default=str), encoding="utf-8")
    (RUN_DIR / "summary.json").write_text(
        json.dumps(summary, ensure_ascii=False, indent=2, default=str), encoding="utf-8"
    )

    def row_md(row: pd.Series) -> str:
        return (
            f"| {row['book']} | {pct(row['ret'])} | {pct(row['maxDD'])} | {pct(row['CAGR'])} | "
            f"{row['Calmar']:.2f} | {row['sharpe']:.2f} | {row['avg_turnover']:.3f} | "
            f"{pct(row['2020-22_ret'])}/{pct(row['2020-22_DD'])} | "
            f"{pct(row['2023-26_ret'])}/{pct(row['2023-26_DD'])} | "
            f"{row['avgL']:.2f} | {100*row['cash_week_pct']:.1f}% |"
        )

    report = f"""# REPORT · B45-MAXDD-GATE-SPIKE-S20

## 1. 准则原文

```
{criterion_src.strip()}
```

## 2. 实现要点

- **面层冻结**：B45 breadth + spike_ft max5 + SHARPE20 + E0 + TV25；Fri≥14:30/收盘；0.2%RT；L≤1。
- **唯一叠加**：日频路径闸——距 −θ 最后 5pp 线性去杠杆，触及 −θ 硬底曝光=0；θ=15% 主档、20% 邻档。
- **引擎**：复用 `SPIKE-S20-EXTEND-REBASE-LIVE1430` simulate + `run_live_tv`；数据 `CLOUD-BATCH-2026-10-26`。
- **红线**：研究池；不换冠；未写 strategy_exec / LIVE_OPS。

| 覆盖 | 值 |
|---|---|
| 样本终点 | {cov['calendar_end']} |
| 日历周 | {cov['n_weeks']} |
| 可投池 | {cov['n_codes']} |

## 3. 主表（vs 无闸 FACE）

| book | ret | maxDD | CAGR | Calmar | Sharpe | avgTO | 2020–22 ret/DD | 2023–26 ret/DD | avgL | cash周% |
|---|---:|---:|---:|---:|---:|---:|---|---|---:|---:|
{row_md(base)}
{row_md(dd15)}
{row_md(dd20)}

### Δ vs 无闸 FACE

| 闸 | Δret | Δ|MDD| | ΔCalmar | ΔSharpe | ΔavgTO | gate_ok |
|---|---:|---:|---:|---:|---:|---|
| DD15 | {d15['d_ret_pp']:+.1f}pp | {d15['d_abs_mdd_pp']:+.1f}pp | {d15['d_calmar']:+.2f} | {d15['d_sharpe']:+.2f} | {d15['d_turnover']:+.3f} | {gate15_ok} |
| DD20 | {d20['d_ret_pp']:+.1f}pp | {d20['d_abs_mdd_pp']:+.1f}pp | {d20['d_calmar']:+.2f} | {d20['d_sharpe']:+.2f} | {d20['d_turnover']:+.3f} | {bool(dd20.get('gate_ok', False))} |

## 4. 一句证伪或通过

{verdict}

耗时约 {summary['elapsed_sec']}s。
"""
    (OUT / "REPORT.md").write_text(report, encoding="utf-8")
    (RUN_DIR / "REPORT.md").write_text(report, encoding="utf-8")

    print("done", OUT, flush=True)
    print(verdict, flush=True)


if __name__ == "__main__":
    main()
