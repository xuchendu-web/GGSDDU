#!/usr/bin/env python3
"""Minimal mom_engine for MF-HOLD-BGRID (weekly close fill, 0.2% RT)."""
from __future__ import annotations

import math
from pathlib import Path

import numpy as np
import pandas as pd

from panel_build import PANEL_PKL, build_panel

START = "2020-01-03"
END = "2026-10-16"
CPS = 0.001

_D = None


def data():
    global _D
    if _D is not None:
        return _D
    if not PANEL_PKL.exists():
        build_panel()
    raw = pd.read_pickle(PANEL_PKL)
    P, W, SIG, G = raw["P"], raw["W"], raw["SIG"], raw["G"]
    G = pd.DatetimeIndex(G)
    gi = {g: i for i, g in enumerate(G)}
    reb = [g for g in G if g >= pd.Timestamp(START) and g <= pd.Timestamp(END)][:-1]
    _D = dict(P=P, W=W, SIG=SIG, G=G, codes=list(raw["codes"]), gi=gi, reb=reb)
    return _D


def stats(s: pd.Series) -> dict:
    s = s.dropna()
    if len(s) < 2:
        return {k: float("nan") for k in ("ret", "maxDD", "CAGR", "Calmar")}
    q = (1 + s).cumprod()
    ret = float(q.iloc[-1] - 1)
    dd = float((q / q.cummax().clip(lower=1e-12) - 1).min())
    n = (s.index[-1] - s.index[0]).days
    cagr = (1 + ret) ** (365.25 / n) - 1 if n > 0 and (1 + ret) > 0 else float("nan")
    cal = cagr / abs(dd) if dd < 0 else float("nan")
    return {"ret": ret, "maxDD": dd, "CAGR": cagr, "Calmar": cal}


def yearly(s: pd.Series) -> pd.DataFrame:
    rows = []
    for y in sorted(set(s.index.year)):
        sy = s[s.index.year == y]
        if len(sy) < 2:
            continue
        qy = (1 + sy).cumprod()
        ret = float(qy.iloc[-1] - 1)
        mdd = float((qy / qy.cummax().clip(lower=1e-12) - 1).min())
        rows.append({"year": y, "ret": ret, "mdd": mdd})
    return pd.DataFrame(rows)


def run_weights(weight_fn, record=None):
    d = data()
    P, gi = d["P"], d["gi"]
    days = P.index[(P.index >= START) & (P.index <= END)]
    reb = d["reb"]
    R = P.pct_change()
    r = pd.Series(0.0, index=days)
    cur: dict[str, float] = {}
    to_total = 0.0
    expo = []
    for k, dd in enumerate(reb):
        i = gi[dd]
        raw = weight_fn(i, dd) or {}
        tgt = {
            c: w
            for c, w in raw.items()
            if w > 0 and c in P.columns and dd in P.index and not pd.isna(P.at[dd, c])
        }
        to = sum(abs(tgt.get(c, 0) - cur.get(c, 0)) for c in set(tgt) | set(cur))
        to_total += to / 2
        if dd in r.index:
            r.loc[dd] -= to * CPS
        if record is not None:
            record.setdefault("cost", {})[dd] = to * CPS
        cur = dict(tgt)
        expo.append(sum(cur.values()))
        nxt = reb[k + 1] if k + 1 < len(reb) else days[-1]
        seg = days[(days > dd) & (days <= nxt)]
        for t in seg:
            if not cur:
                continue
            rr = R.loc[t, list(cur)].fillna(0.0)
            r.loc[t] += sum(cur[c] * rr[c] for c in cur)
            if record is not None:
                record.setdefault("contrib", {})[t] = {c: cur[c] * rr[c] for c in cur}
                record.setdefault("expo", {})[t] = sum(cur.values())
            g = sum(cur[c] * (1 + rr[c]) for c in cur)
            cash = 1 - sum(cur.values())
            tot = g + cash
            if tot > 0:
                cur = {c: cur[c] * (1 + rr[c]) / tot for c in cur}
    yrs = (days[-1] - days[0]).days / 365.25
    return r, (to_total / yrs if yrs > 0 else float("nan")), float(np.mean(expo) if expo else 0)


def benches() -> dict:
    return {}
