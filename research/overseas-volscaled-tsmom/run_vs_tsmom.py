#!/usr/bin/env python3
"""VS-TSMOM four-pack backtest. Requires inventory.json (non-BLOCKED)."""

from __future__ import annotations

import json
import math
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

from vs_tsmom_lib import (
    CMD,
    COST_SIDE,
    EVAL_END,
    EVAL_START,
    HERE,
    OX,
    OXHK_EXTRA,
    OUT_DIR,
    RATES,
    BookSpec,
    compute_u_weights,
    daily_to_weekly_close,
    load_daily_close,
    load_listing_date,
    load_rebalance_fridays,
    name_eligible,
    r52,
    sleeve_budget_equal,
    sleeve_of,
    sigma_i,
    weekly_simple_returns,
)

INV_PATH = HERE / "inventory.json"

BOOK_ORDER = [
    "VS-TSMOM-12",
    "TSMOM-UNSCALED",
    "EW-BH",
    "VS-TSMOM-ERC",
    "VS-BH-12",
    "VS-TSMOM-OXONLY",
    "VS-TSMOM-OXHK",
]


def align_weekly_on_grid(daily: pd.Series, weeks: pd.DatetimeIndex) -> pd.Series:
    w = daily_to_weekly_close(daily)
    if w.empty:
        return pd.Series(index=weeks, dtype=float)
    return w.reindex(weeks, method="ffill")


def mode_for_book(key: str) -> str:
    return {
        "VS-TSMOM-12": "VS",
        "TSMOM-UNSCALED": "U",
        "EW-BH": "H",
        "VS-TSMOM-ERC": "ERC",
        "VS-BH-12": "VS_BH",
        "VS-TSMOM-OXONLY": "VS",
        "VS-TSMOM-OXHK": "VS",
    }[key]


def spec_for_book(key: str, inv: dict) -> BookSpec:
    declared = set(inv["declared_sleeves"])
    if key == "VS-TSMOM-OXONLY":
        declared = {"OX"}
    ox_codes = set(OX)
    if key == "VS-TSMOM-OXHK":
        ox_codes = set(OX) | set(OXHK_EXTRA)
    return BookSpec(key=key, mode=mode_for_book(key), declared=frozenset(declared), ox_codes=frozenset(ox_codes))


def eligible_by_sleeve(
    week_i: int,
    weeks: pd.DatetimeIndex,
    weekly: dict[str, pd.Series],
    listings: dict[str, pd.Timestamp | None],
    spec: BookSpec,
) -> dict[str, list[str]]:
    out: dict[str, list[str]] = {s: [] for s in spec.declared}
    codes = set()
    for s in spec.declared:
        if s == "OX":
            codes |= spec.ox_codes
        elif s == "CMD":
            codes |= CMD
        elif s == "RATES":
            codes |= RATES
    for code in codes:
        sl = sleeve_of(code, set(spec.declared), set(spec.ox_codes))
        if sl is None:
            continue
        if name_eligible(code, week_i, weeks, weekly[code], listings.get(code)):
            out[sl].append(code)
    for sl in out:
        out[sl] = sorted(out[sl])
    return out


def ew_bh_sleeve_weekly_return(
    week_i: int,
    weeks: pd.DatetimeIndex,
    weekly: dict[str, pd.Series],
    elig: dict[str, list[str]],
    n_declared: int,
) -> dict[str, float]:
    """Per-sleeve EW-BH portfolio simple return for week ending at week_i."""
    if week_i < 1:
        return {s: 0.0 for s in elig}
    dt0, dt1 = weeks[week_i - 1], weeks[week_i]
    B = sleeve_budget_equal(n_declared)
    rets: dict[str, float] = {}
    for sl, codes in elig.items():
        if not codes:
            rets[sl] = 0.0
            continue
        w = B / len(codes)
        r = 0.0
        for c in codes:
            p0 = weekly[c].get(dt0, np.nan)
            p1 = weekly[c].get(dt1, np.nan)
            if math.isfinite(p0) and math.isfinite(p1) and p0 > 0:
                r += w * (p1 / p0 - 1.0)
        rets[sl] = r
    return rets


def compute_budgets(
    spec: BookSpec,
    week_i: int,
    weeks: pd.DatetimeIndex,
    weekly: dict[str, pd.Series],
    elig: dict[str, list[str]],
    n_declared: int,
    ew_sleeve_hist: dict[str, list[float]],
    erc_fallback: list[int],
) -> dict[str, float]:
    declared = list(spec.declared)
    if spec.mode != "ERC":
        B = sleeve_budget_equal(n_declared)
        return {s: B for s in declared}

    sig_inv: dict[str, float] = {}
    for sl in declared:
        hist = ew_sleeve_hist.get(sl, [])
        if len(hist) < VOL_W:
            erc_fallback.append(week_i)
            B = sleeve_budget_equal(n_declared)
            return {s: B for s in declared}
        seg = np.array(hist[-VOL_W:], dtype=float)
        sig = float(np.std(seg, ddof=1) * math.sqrt(52))
        if not math.isfinite(sig) or sig <= 0:
            erc_fallback.append(week_i)
            B = sleeve_budget_equal(n_declared)
            return {s: B for s in declared}
        sig_inv[sl] = 1.0 / sig
    tot = sum(sig_inv.values())
    return {sl: sig_inv[sl] / tot for sl in declared}


VOL_W = 60


def target_weights(
    spec: BookSpec,
    week_i: int,
    weeks: pd.DatetimeIndex,
    weekly: dict[str, pd.Series],
    elig: dict[str, list[str]],
    budgets: dict[str, float],
) -> dict[str, float]:
    mode = spec.mode
    if mode == "ERC":
        u_mode = "VS"
    elif mode == "VS_BH":
        u_mode = "VS_BH"
    elif mode == "U":
        u_mode = "U"
    elif mode == "H":
        u_mode = "H"
    else:
        u_mode = "VS"

    weights: dict[str, float] = {}
    for sl, codes in elig.items():
        Bs = budgets.get(sl, 0.0)
        if not codes or Bs <= 0:
            continue
        if u_mode == "VS_BH":
            u = compute_u_weights(codes, weekly, weeks, week_i, "VS_BH")
            # direction always 1
            n_s = len(codes)
            u = {}
            for c in codes:
                sig = sigma_i(weekly[c], weeks, week_i)
                if not math.isfinite(sig) or sig <= 0:
                    continue
                u[c] = (1.0 / n_s) * min(1.0, SIGMA_STAR / sig)
        else:
            u = compute_u_weights(codes, weekly, weeks, week_i, u_mode)
        for c, ui in u.items():
            weights[c] = weights.get(c, 0.0) + Bs * ui
    return weights


SIGMA_STAR = 0.12


@dataclass
class SimResult:
    book: str
    nav_w: pd.Series
    weekly_ret: pd.Series
    daily_ret: pd.Series
    holdings: pd.DataFrame
    sleeve_w: pd.DataFrame
    eligibility_rows: list[dict]
    avg_to: float
    ann_to: float
    avg_gross: float
    cash_week_pct: float
    erc_fallback_weeks: int


def _daily_portfolio_return(weights: dict[str, float], daily: dict[str, pd.Series], d: pd.Timestamp) -> float:
    dr = 0.0
    for c, w in weights.items():
        s = daily.get(c)
        if s is None or s.empty:
            continue
        idx = s.index
        if d not in idx:
            continue
        loc = idx.get_loc(d)
        if isinstance(loc, slice):
            loc = loc.start
        if loc == 0:
            continue
        p1 = float(s.iloc[loc])
        p0 = float(s.iloc[loc - 1])
        if math.isfinite(p0) and math.isfinite(p1) and p0 > 0:
            dr += w * (p1 / p0 - 1.0)
    return dr


def simulate_book(
    spec: BookSpec,
    weeks: pd.DatetimeIndex,
    weekly: dict[str, pd.Series],
    daily: dict[str, pd.Series],
    listings: dict[str, pd.Timestamp | None],
    n_declared: int,
) -> SimResult:
    schedule: list[tuple[pd.Timestamp, dict[str, float], float]] = []
    hold_rows: list[dict] = []
    sleeve_rows: list[dict] = []
    elig_rows: list[dict] = []
    to_half = 0.0
    gross_list: list[float] = []
    cash_weeks = 0
    erc_fallback_idx: list[int] = []
    ew_sleeve_hist: dict[str, list[float]] = {s: [] for s in spec.declared}
    prev_w: dict[str, float] = {}

    for i, dt in enumerate(weeks):
        elig = eligible_by_sleeve(i, weeks, weekly, listings, spec)
        for sl, codes in elig.items():
            elig_rows.append({"date": dt.strftime("%Y-%m-%d"), "sleeve": sl, "n_s": len(codes), "codes": "|".join(codes)})

        if i > 0:
            ew_elig = eligible_by_sleeve(i, weeks, weekly, listings, spec)
            sr = ew_bh_sleeve_weekly_return(i, weeks, weekly, ew_elig, n_declared)
            for sl, rv in sr.items():
                ew_sleeve_hist.setdefault(sl, []).append(rv)

        budgets = compute_budgets(spec, i, weeks, weekly, elig, n_declared, ew_sleeve_hist, erc_fallback_idx)
        tgt = target_weights(spec, i, weeks, weekly, elig, budgets)
        to = sum(abs(tgt.get(c, 0.0) - prev_w.get(c, 0.0)) for c in set(tgt) | set(prev_w))
        cost = to * COST_SIDE
        to_half += to / 2.0
        gross = sum(tgt.values())
        gross_list.append(gross)
        if gross < 1e-12:
            cash_weeks += 1
        schedule.append((dt, dict(tgt), cost))
        prev_w = dict(tgt)

        sw = {f"w_{sl}": 0.0 for sl in ("OX", "CMD", "RATES")}
        for c, w in tgt.items():
            sl = sleeve_of(c, set(spec.declared), set(spec.ox_codes))
            if sl:
                sw[f"w_{sl}"] = sw.get(f"w_{sl}", 0.0) + w
        sleeve_rows.append({"date": dt.strftime("%Y-%m-%d"), **sw, "gross": gross, "w_cash": 1.0 - gross})
        hold_rows.append({"date": dt.strftime("%Y-%m-%d"), "gross": gross, "weights": json.dumps(tgt, sort_keys=True)})

    all_days = sorted(
        {d for s in daily.values() for d in s.index if pd.Timestamp(EVAL_START) <= d <= pd.Timestamp(EVAL_END)}
    )
    daily_idx = pd.DatetimeIndex(all_days)
    daily_r = pd.Series(0.0, index=daily_idx)
    weights: dict[str, float] = {}
    next_cost = 0.0
    sched_i = 0
    for d in daily_idx:
        while sched_i < len(schedule) and schedule[sched_i][0] <= d:
            weights = schedule[sched_i][1]
            next_cost = schedule[sched_i][2]
            sched_i += 1
        r = _daily_portfolio_return(weights, daily, d)
        if sched_i > 0 and schedule[sched_i - 1][0] == d:
            r -= next_cost
        daily_r.loc[d] = r

    nav_d = (1.0 + daily_r).cumprod()
    weekly_ret_vals: list[float] = []
    nav_w_vals: list[float] = []
    for dt in weeks:
        sub = nav_d[nav_d.index <= dt]
        nav_w_vals.append(float(sub.iloc[-1]) if len(sub) else 1.0)
    for i, dt in enumerate(weeks):
        if i == 0:
            weekly_ret_vals.append(0.0)
            continue
        a = nav_w_vals[i - 1]
        b = nav_w_vals[i]
        weekly_ret_vals.append(b / a - 1.0 if a > 0 else 0.0)

    nav_w = pd.Series(nav_w_vals, index=weeks)
    weekly_ret = pd.Series(weekly_ret_vals, index=weeks)
    n_weeks = max(len(weeks) - 1, 1)
    return SimResult(
        book=spec.key,
        nav_w=nav_w,
        weekly_ret=weekly_ret,
        daily_ret=daily_r,
        holdings=pd.DataFrame(hold_rows),
        sleeve_w=pd.DataFrame(sleeve_rows),
        eligibility_rows=elig_rows,
        avg_to=to_half / n_weeks,
        ann_to=to_half / n_weeks * 52,
        avg_gross=float(np.mean(gross_list) if gross_list else 0.0),
        cash_week_pct=cash_weeks / len(weeks) if weeks.size else 0.0,
        erc_fallback_weeks=len(set(erc_fallback_idx)),
    )


def metrics_from_returns(daily_r: pd.Series, weekly_ret: pd.Series, sim: SimResult) -> dict[str, Any]:
    daily_r = daily_r.dropna()
    daily_r = daily_r[daily_r.index >= pd.Timestamp(EVAL_START)]
    nav_d = (1.0 + daily_r).cumprod()
    if nav_d.empty:
        nav_d = (1.0 + weekly_ret).cumprod()
    ret = float(nav_d.iloc[-1] - 1.0) if len(nav_d) else float("nan")
    peak = nav_d.cummax()
    dd = nav_d / peak - 1.0
    max_dd = float(dd.min()) if len(dd) else float("nan")
    days = max((nav_d.index[-1] - nav_d.index[0]).days, 1) if len(nav_d) > 1 else 1
    cagr = float((1.0 + ret) ** (365.25 / days) - 1.0) if days > 0 else float("nan")
    calmar = float(cagr / abs(max_dd)) if max_dd < 0 else float("nan")
    mu = float(daily_r.mean())
    sd = float(daily_r.std(ddof=1))
    sharpe = float(mu / sd * math.sqrt(252)) if sd > 0 else float("nan")
    wmu = weekly_ret.dropna()
    wvol = float(wmu.std(ddof=1) * math.sqrt(52)) if len(wmu) > 1 else float("nan")

    def seg_metrics(start: str, end: str | None = None) -> tuple[float, float, float]:
        s = pd.Timestamp(start)
        e = pd.Timestamp(end) if end else nav_d.index[-1]
        sub = daily_r[(daily_r.index >= s) & (daily_r.index <= e)]
        if sub.empty:
            return float("nan"), float("nan"), float("nan")
        nav = (1.0 + sub).cumprod()
        r = float(nav.iloc[-1] - 1.0)
        pk = nav.cummax()
        mdd = float((nav / pk - 1.0).min())
        d = max((sub.index[-1] - sub.index[0]).days, 1)
        cg = float((1.0 + r) ** (365.25 / d) - 1.0)
        cal = float(cg / abs(mdd)) if mdd < 0 else float("nan")
        return r, mdd, cal

    r2020, m2020, c2020 = seg_metrics("2020-01-01", "2022-12-31")
    r2023, m2023, c2023 = seg_metrics("2023-01-01", None)

    return {
        "ret": ret,
        "maxDD": max_dd,
        "CAGR": cagr,
        "Calmar": calmar,
        "Sharpe": sharpe,
        "vol": wvol,
        "avgTO": sim.avg_to,
        "annTO": sim.ann_to,
        "ret_2020_22": r2020,
        "maxDD_2020_22": m2020,
        "Calmar_2020_22": c2020,
        "ret_2023_26": r2023,
        "maxDD_2023_26": m2023,
        "Calmar_2023_26": c2023,
        "avg_gross_exposure": sim.avg_gross,
        "cash_week_pct": sim.cash_week_pct,
        "erc_fallback_weeks": sim.erc_fallback_weeks,
    }


def run_sleeve_metrics(
    book_key: str,
    weeks: pd.DatetimeIndex,
    weekly: dict[str, pd.Series],
    daily: dict[str, pd.Series],
    listings: dict[str, pd.Timestamp | None],
    inv: dict,
) -> pd.DataFrame:
    rows = []
    for sl in ("OX", "CMD", "RATES"):
        if sl not in inv["declared_sleeves"] and sl != "RATES":
            if sl == "RATES" and inv["rates"]["status"] != "OK":
                continue
        if sl == "RATES" and inv["rates"]["status"] != "OK":
            continue
        for sub_book, mode in [("VS-TSMOM-12", "VS"), ("TSMOM-UNSCALED", "U"), ("EW-BH", "H")]:
            spec = BookSpec(
                key=f"{book_key}-{sl}",
                mode=mode,
                declared=frozenset([sl]),
                ox_codes=frozenset(OX | OXHK_EXTRA),
            )
            sim = simulate_book(spec, weeks, weekly, daily, listings, 1)
            m = metrics_from_returns(sim.daily_ret, sim.weekly_ret, sim)
            rows.append({"book": sub_book, "sleeve": sl, **{k: m[k] for k in ("ret", "maxDD", "Calmar", "Sharpe", "vol")}})
    return pd.DataFrame(rows)


def yearly_metrics(sim: SimResult) -> list[dict]:
    rows: list[dict] = []
    dr = sim.daily_ret.dropna()
    if dr.empty:
        return rows
    nav = (1.0 + dr).cumprod()
    for year in sorted(set(dr.index.year)):
        sub_r = dr[dr.index.year == year]
        if sub_r.empty:
            continue
        sub_nav = (1.0 + sub_r).cumprod()
        ret = float(sub_nav.iloc[-1] - 1.0)
        pk = sub_nav.cummax()
        mdd = float((sub_nav / pk - 1.0).min())
        vol = float(sub_r.std(ddof=1) * math.sqrt(252)) if len(sub_r) > 1 else float("nan")
        mu = float(sub_r.mean())
        sd = float(sub_r.std(ddof=1))
        sharpe = float(mu / sd * math.sqrt(252)) if sd > 0 else float("nan")
        days = max((sub_r.index[-1] - sub_r.index[0]).days, 1)
        cagr = float((1.0 + ret) ** (365.25 / days) - 1.0)
        calmar = float(cagr / abs(mdd)) if mdd < 0 else float("nan")
        rows.append(
            {
                "book": sim.book,
                "year": year,
                "ret": ret,
                "mdd": mdd,
                "vol": vol,
                "sharpe": sharpe,
                "calmar": calmar,
            }
        )
    return rows


def evaluate_gates(mP: dict, mU: dict, mH: dict) -> dict[str, bool]:
    g1 = mP["Sharpe"] >= mU["Sharpe"] and mP["Calmar"] >= mU["Calmar"]
    d_ret = mP["ret"] - mH["ret"]
    d_mdd = abs(mP["maxDD"]) - abs(mH["maxDD"])
    g2 = mP["Calmar"] >= mH["Calmar"] or d_ret >= d_mdd
    g3 = mP["ret_2023_26"] >= min(mU["ret_2023_26"], mH["ret_2023_26"])
    g4 = mP["vol"] < mU["vol"]
    return {"G1": g1, "G2": g2, "G3": g3, "G4": g4}


def verdict_from_gates(gates: dict[str, bool]) -> str:
    if all(gates.values()):
        return "记正"
    return "证伪"


def write_report(inv: dict, metrics: pd.DataFrame, gates: dict[str, bool], verdict: str, price_sources: set[str]) -> None:
    mP = metrics.loc[metrics["book"] == "VS-TSMOM-12"].iloc[0]
    mU = metrics.loc[metrics["book"] == "TSMOM-UNSCALED"].iloc[0]
    mH = metrics.loc[metrics["book"] == "EW-BH"].iloc[0]
    failed = [k for k, v in gates.items() if not v]
    triple = inv.get("triple_sleeve_claim") == "SKIP"

    try:
        table_md = metrics.to_markdown(index=False)
    except ImportError:
        table_md = metrics.to_string(index=False)

    lines = [
        "# VS-TSMOM-SLEEVE · REPORT",
        "",
        "## 1. 准则原文（可执行摘要）",
        "",
        f"- 主簿 VS-TSMOM-12；`n_declared={inv['n_declared']}`，宣布袖：{', '.join(inv['declared_sleeves'])}。",
        f"- RATES 库存：`{inv['rates']['status']}`（{inv['rates'].get('reason', '')}）。",
        "- σ*=12%，52 周方向 / 60 周波动，L≤1 只缩不放；成本 0.2% 往返。",
        "- 四闸相对同窗 TSMOM-UNSCALED（U）与 EW-BH（H），不与 FACE 绝对值横比。",
        "",
        "## 2. 实现要点",
        "",
        f"- 评窗：{EVAL_START} → {EVAL_END}；研究周五网格来自 `weekly_panel.parquet`。",
        f"- OX 十六只 / CMD 五只已按研究池核对；价格来源示例：{', '.join(sorted(price_sources)[:8])}…",
        f"- 平均 gross exposure（主簿）：{mP['avg_gross_exposure']:.4f}；现金周占比：{mP['cash_week_pct']:.2%}。",
        "- 未读入 FACE / LIVE1430 净值。",
        "",
        "## 3. 主表",
        "",
        table_md,
        "",
        "### 四闸（主簿 vs U/H）",
        "",
        f"- G1 缩放增量：Sharpe {mP['Sharpe']:.3f} vs U {mU['Sharpe']:.3f}；Calmar {mP['Calmar']:.3f} vs U {mU['Calmar']:.3f} → {'过' if gates['G1'] else '未过'}",
        f"- G2 趋势增量：Calmar_P {mP['Calmar']:.3f} vs H {mH['Calmar']:.3f}；Δret(P−H)={mP['ret']-mH['ret']:.4f}，Δ|MDD|={abs(mP['maxDD'])-abs(mH['maxDD']):.4f} → {'过' if gates['G2'] else '未过'}",
        f"- G3 后段 2023–26：ret_P {mP['ret_2023_26']:.4f} vs min(U,H) {min(mU['ret_2023_26'], mH['ret_2023_26']):.4f} → {'过' if gates['G3'] else '未过'}",
        f"- G4 缩放绑定：vol_P {mP['vol']:.4f} vs vol_U {mU['vol']:.4f} → {'过' if gates['G4'] else '未过'}",
        "",
        "邻档四本见上表各行；旁注不升格主簿判词。",
        "",
        "## 4. 判词",
        "",
    ]
    if verdict == "记正":
        lines.append(
            f"记正（不换冠）：VS-TSMOM-12 相对同窗未缩放 TSMOM 与等权 BH 四闸全过。"
            f" Sharpe Δ(P−U)={mP['Sharpe']-mU['Sharpe']:.3f}，Calmar Δ(P−U)={mP['Calmar']-mU['Calmar']:.3f}，"
            f"vol Δ(P−U)={mP['vol']-mU['vol']:.4f}，2023–26 ret_P={mP['ret_2023_26']:.4f}。"
            f" 未与 FACE 绝对值横比。"
        )
    else:
        gx = failed[0] if failed else "G?"
        lines.append(
            f"证伪（不换冠）：VS-TSMOM-12 未过闸 {','.join(failed) or gx}。"
            f" G1–G4 见上。未与 FACE 绝对值横比。"
        )
    if triple:
        lines.append("三袖普遍性 SKIP，利率债面板不够 2019 起评。")
    (OUT_DIR / "REPORT.md").write_text("\n".join(lines), encoding="utf-8")


def main() -> int:
    if not INV_PATH.is_file():
        print("missing inventory.json", file=sys.stderr)
        return 1
    inv = json.loads(INV_PATH.read_text(encoding="utf-8"))
    if inv.get("verdict_if_stop") == "BLOCKED":
        print("inventory BLOCKED", file=sys.stderr)
        return 1

    weeks = load_rebalance_fridays()
    all_codes = set(OX) | set(CMD) | set(OXHK_EXTRA)
    if inv["rates"]["status"] == "OK":
        all_codes |= RATES

    daily: dict[str, pd.Series] = {}
    weekly: dict[str, pd.Series] = {}
    listings: dict[str, pd.Timestamp | None] = {}
    price_sources: set[str] = set()
    for c in sorted(all_codes):
        s, src, _ = load_daily_close(c)
        daily[c] = s
        weekly[c] = align_weekly_on_grid(s, weeks)
        listings[c] = load_listing_date(c)
        if src:
            price_sources.add(src)

    OUT_DIR.mkdir(parents=True, exist_ok=True)
    results: dict[str, SimResult] = {}
    metric_rows = []
    for key in BOOK_ORDER:
        if key == "VS-TSMOM-OXONLY":
            n_decl = 1
        else:
            n_decl = inv["n_declared"]
        spec = spec_for_book(key, inv)
        sim = simulate_book(spec, weeks, weekly, daily, listings, n_decl)
        results[key] = sim
        m = metrics_from_returns(sim.daily_ret, sim.weekly_ret, sim)
        metric_rows.append({"book": key, **m})
        sim.nav_w.rename("nav").to_frame().reset_index().rename(columns={"index": "date"}).to_csv(
            OUT_DIR / f"nav_{key}.csv", index=False
        )
        sim.sleeve_w.to_csv(OUT_DIR / f"weights_{key}.csv", index=False)
        # holdings wide
        hrows = []
        for _, row in sim.holdings.iterrows():
            wdict = json.loads(row["weights"])
            for code, wt in wdict.items():
                hrows.append({"date": row["date"], "code": code, "weight": wt})
        pd.DataFrame(hrows).to_csv(OUT_DIR / f"holdings_{key}.csv", index=False)

    metrics = pd.DataFrame(metric_rows)
    metrics.to_csv(OUT_DIR / "metrics.csv", index=False)
    metrics.to_csv(OUT_DIR / "table.csv", index=False)

    elig = pd.DataFrame(results["VS-TSMOM-12"].eligibility_rows)
    elig.to_csv(OUT_DIR / "eligibility.csv", index=False)

    sleeve_m = run_sleeve_metrics("VS-TSMOM-12", weeks, weekly, daily, listings, inv)
    sleeve_m.to_csv(OUT_DIR / "sleeve_metrics.csv", index=False)

    yearly_rows: list[dict] = []
    for sim in results.values():
        yearly_rows.extend(yearly_metrics(sim))
    pd.DataFrame(yearly_rows).to_csv(OUT_DIR / "yearly.csv", index=False)

    mP = metrics.loc[metrics["book"] == "VS-TSMOM-12"].iloc[0].to_dict()
    mU = metrics.loc[metrics["book"] == "TSMOM-UNSCALED"].iloc[0].to_dict()
    mH = metrics.loc[metrics["book"] == "EW-BH"].iloc[0].to_dict()
    gates = evaluate_gates(mP, mU, mH)
    verdict = verdict_from_gates(gates)

    summary = {
        "n_declared": inv["n_declared"],
        "declared_sleeves": inv["declared_sleeves"],
        "rates_status": inv["rates"]["status"],
        "triple_sleeve_claim": inv["triple_sleeve_claim"],
        "gates": gates,
        "verdict": verdict,
        "erc_fallback_weeks": int(metrics.loc[metrics["book"] == "VS-TSMOM-ERC", "erc_fallback_weeks"].iloc[0]),
    }
    (OUT_DIR / "summary.json").write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")

    # equity curve
    plt.figure(figsize=(10, 5))
    for key, label in [("VS-TSMOM-12", "P"), ("TSMOM-UNSCALED", "U"), ("EW-BH", "H")]:
        nav = results[key].nav_w
        plt.plot(nav.index, nav.values, label=label)
    plt.legend()
    plt.title("VS-TSMOM vs U vs H (weekly NAV)")
    plt.tight_layout()
    plt.savefig(OUT_DIR / "equity_curve.png", dpi=120)
    plt.close()

    write_report(inv, metrics, gates, verdict, price_sources)
    print(f"verdict={verdict} gates={gates}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
