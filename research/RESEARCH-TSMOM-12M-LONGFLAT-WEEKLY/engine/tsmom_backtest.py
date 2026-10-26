#!/usr/bin/env python3
"""Moskowitz-style time-series momentum: long if lookback return > 0 else flat (cash)."""
from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Callable, Literal

import numpy as np
import pandas as pd

START = "2020-01-03"
END = "2026-10-16"
COST_SIDE = 0.001  # 0.2% round-trip
TRADING_DAYS = {"6m": 126, "9m": 189, "12m": 252}
VOL_TARGET = 0.12


@dataclass
class Variant:
    key: str
    lookback: str
    seat: Literal["max5", "all_pos"]
    vol_scale: bool = False


def _mom_at(P: pd.DataFrame, dd: pd.Timestamp, code: str, lb_days: int) -> float | None:
    if code not in P.columns:
        return None
    hist = P.loc[:dd, code].dropna()
    if len(hist) < lb_days + 5:
        return None
    p0 = float(hist.iloc[-lb_days - 1])
    p1 = float(hist.iloc[-1])
    if p0 <= 0 or p1 <= 0:
        return None
    return p1 / p0 - 1.0


def weights_tsmom(
    P: pd.DataFrame,
    dd: pd.Timestamp,
    universe: list[str],
    lb_days: int,
    seat: Literal["max5", "all_pos"],
) -> dict[str, float]:
    scored: list[tuple[str, float]] = []
    for c in universe:
        m = _mom_at(P, dd, c, lb_days)
        if m is not None and m > 0:
            scored.append((c, m))
    if not scored:
        return {}
    scored.sort(key=lambda x: x[1], reverse=True)
    if seat == "max5":
        scored = scored[:5]
    w = 1.0 / len(scored)
    return {c: w for c, _ in scored}


def run_backtest(
    panel: dict,
    lb_key: str = "12m",
    seat: Literal["max5", "all_pos"] = "max5",
    vol_scale: bool = False,
    universe: list[str] | None = None,
    weight_hook: Callable[[dict[str, float], pd.Timestamp], dict[str, float]] | None = None,
) -> tuple[pd.Series, dict]:
    P = panel["P"]
    reb = panel["reb"]
    codes = universe or panel["codes"]
    lb_days = TRADING_DAYS[lb_key]
    days = P.index[(P.index >= START) & (P.index <= END)]
    R = P.pct_change()
    r = pd.Series(0.0, index=days)
    cur: dict[str, float] = {}
    to_total = 0.0
    expo: list[float] = []
    risk_on_weeks = 0
    cash_weeks = 0
    scale_hist: list[float] = []

    for k, dd in enumerate(reb):
        tgt = weights_tsmom(P, dd, codes, lb_days, seat)
        if weight_hook:
            tgt = weight_hook(tgt, dd)
        if vol_scale and tgt:
            # scale gross exposure to hit ~12% ann vol using trailing 52w portfolio vol
            port_rets = []
            look = days[(days <= dd)][-260:]
            if len(look) > 60:
                for t in look:
                    if not cur:
                        port_rets.append(0.0)
                        continue
                    rr = R.loc[t, list(cur.keys())].fillna(0.0)
                    port_rets.append(sum(cur[c] * rr[c] for c in cur))
                vol = float(np.std(port_rets) * math.sqrt(252))
                sc = min(1.0, VOL_TARGET / vol) if vol > 1e-6 else 1.0
            else:
                sc = 1.0
            tgt = {c: w * sc for c, w in tgt.items()}
            scale_hist.append(sc)
        tgt = {c: w for c, w in tgt.items() if w > 0 and c in P.columns}
        if tgt:
            risk_on_weeks += 1
        else:
            cash_weeks += 1
        to = sum(abs(tgt.get(c, 0) - cur.get(c, 0)) for c in set(tgt) | set(cur))
        to_total += to / 2
        if dd in r.index:
            r.loc[dd] -= to * COST_SIDE
        cur = dict(tgt)
        expo.append(sum(cur.values()))
        nxt = reb[k + 1] if k + 1 < len(reb) else days[-1]
        seg = days[(days > dd) & (days <= nxt)]
        for t in seg:
            if not cur:
                continue
            rr = R.loc[t, list(cur)].fillna(0.0)
            r.loc[t] += sum(cur[c] * rr[c] for c in cur)
            g = sum(cur[c] * (1 + rr[c]) for c in cur)
            cash = 1 - sum(cur.values())
            tot = g + cash
            if tot > 0:
                cur = {c: cur[c] * (1 + rr[c]) / tot for c in cur}

    yrs = (days[-1] - days[0]).days / 365.25
    meta = {
        "turnover_1y": to_total / yrs if yrs > 0 else float("nan"),
        "avg_expo": float(np.mean(expo) if expo else 0),
        "risk_on_week_pct": risk_on_weeks / len(reb) if reb else 0,
        "cash_week_pct": cash_weeks / len(reb) if reb else 0,
        "n_reb": len(reb),
        "vol_scale_mean": float(np.mean(scale_hist)) if scale_hist else float("nan"),
    }
    return r, meta


def stats(s: pd.Series) -> dict[str, float]:
    s = s.dropna()
    if len(s) < 2:
        return {k: float("nan") for k in ("ret", "maxDD", "CAGR", "Calmar", "Sharpe", "Sortino")}
    q = (1 + s).cumprod()
    ret = float(q.iloc[-1] - 1)
    dd = float((q / q.cummax().clip(lower=1e-12) - 1).min())
    n = (s.index[-1] - s.index[0]).days
    cagr = (1 + ret) ** (365.25 / n) - 1 if n > 0 and (1 + ret) > 0 else float("nan")
    cal = cagr / abs(dd) if dd < 0 else float("nan")
    ann = s.std() * math.sqrt(252) if s.std() > 0 else float("nan")
    sharpe = (s.mean() * 252) / ann if ann and not math.isnan(ann) else float("nan")
    down = s[s < 0]
    ds = down.std() * math.sqrt(252) if len(down) > 1 and down.std() > 0 else float("nan")
    sortino = (s.mean() * 252) / ds if ds and not math.isnan(ds) else float("nan")
    return {
        "ret": ret,
        "maxDD": dd,
        "CAGR": cagr,
        "Calmar": cal,
        "Sharpe": sharpe,
        "Sortino": sortino,
    }


def window_stats(s: pd.Series, end_a: str, start_b: str | None = None) -> dict[str, float]:
    a = s[s.index <= pd.Timestamp(end_a)]
    if start_b:
        b = s[s.index >= pd.Timestamp(start_b)]
    else:
        b = s[s.index > pd.Timestamp(end_a)]
    return {f"seg_a": stats(a), f"seg_b": stats(b)}


def scorecard_row(book: str, r: pd.Series, meta: dict) -> dict:
    s = stats(r)
    a = stats(r[r.index <= "2022-12-31"])
    b = stats(r[r.index >= "2023-01-01"])
    return {
        "book": book,
        "ret": s["ret"],
        "maxDD": s["maxDD"],
        "CAGR": s["CAGR"],
        "Calmar": s["Calmar"],
        "Sharpe": s["Sharpe"],
        "Sortino": s["Sortino"],
        "2020-22_ret": a["ret"],
        "2020-22_DD": a["maxDD"],
        "2020-22_Calmar": a["Calmar"],
        "2023-26_ret": b["ret"],
        "2023-26_DD": b["maxDD"],
        "2023-26_Calmar": b["Calmar"],
        "turnover": meta.get("turnover_1y"),
        "avgL": meta.get("avg_expo"),
        "risk_on_week_pct": meta.get("risk_on_week_pct"),
        "cash_week_pct": meta.get("cash_week_pct"),
    }


def exploration_ruler_vs_face(row: dict, face: dict) -> dict:
    """Δret must cover Δ|MDD|; flag 2023-26 underperformance vs face."""
    d_ret = row["ret"] - face["ret"]
    d_mdd = abs(row["maxDD"]) - abs(face["maxDD"])
    cover = d_ret >= d_mdd if not (math.isnan(d_ret) or math.isnan(d_mdd)) else False
    miss_strong = row["2023-26_ret"] < face["2023-26_ret"] * 0.85
    falsified = not cover or miss_strong
    return {
        "delta_ret": d_ret,
        "delta_abs_mdd": d_mdd,
        "ruler_cover": cover,
        "strong_seg_miss": miss_strong,
        "falsified": falsified,
    }
