"""Jegadeesh-style skip-month cross-sectional momentum on weekly rebalance."""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import pandas as pd

from .config import BREADTH_GATE, CsmomConfig, EVAL_END, EVAL_START


def month_end_table(panel: pd.DataFrame) -> pd.DataFrame:
    """Last Friday close in each calendar month (research weekly calendar)."""
    idx = pd.DatetimeIndex(panel.index)
    keys = pd.Series([ (d.year, d.month) for d in idx], index=idx)
    last_pos = keys.groupby(keys).tail(1).index
    return panel.loc[last_pos].sort_index()


def _holding_month(dt: pd.Timestamp) -> tuple[int, int]:
    """Signal month t = calendar month of rebalance Friday."""
    dt = pd.Timestamp(dt)
    return int(dt.year), int(dt.month)


def _month_end_on_or_before(me_idx: pd.DatetimeIndex, year: int, month: int) -> pd.Timestamp | None:
    """Last month-end strictly before calendar month (year, month)."""
    for ts in reversed(me_idx):
        if ts.year < year or (ts.year == year and ts.month < month):
            return ts
    return None


def _offset_month(year: int, month: int, delta: int) -> tuple[int, int]:
    m = month + delta
    y = year
    while m < 1:
        m += 12
        y -= 1
    while m > 12:
        m -= 12
        y += 1
    return y, m


def formation_end_month(year: int, month: int, skip_months: int) -> tuple[int, int]:
    """Formation ends at month-end t-(1+skip): skip t-1 → end at t-2 when skip=1."""
    return _offset_month(year, month, -(1 + skip_months))


def formation_start_month(year: int, month: int, lookback_months: int) -> tuple[int, int]:
    """Price anchor at month-end t-lookback (12 → t-12)."""
    return _offset_month(year, month, -lookback_months)


def cross_section_formation(
    panel: pd.DataFrame,
    dt: pd.Timestamp,
    lookback_months: int = 12,
    skip_months: int = 1,
) -> pd.Series:
    """Return from month-end t-L to month-end t-(1+skip); skip_months=0 → through t-1."""
    me = month_end_table(panel)
    me_idx = me.index
    hy, hm = _holding_month(dt)
    end_ym = formation_end_month(hy, hm, skip_months)
    start_ym = formation_start_month(hy, hm, lookback_months)
    end_ts = _month_end_on_or_before(me_idx, end_ym[0], end_ym[1] + 1)
    start_ts = _month_end_on_or_before(me_idx, start_ym[0], start_ym[1] + 1)
    if end_ts is None or start_ts is None:
        return pd.Series(dtype=float)
    if end_ts <= start_ts:
        return pd.Series(dtype=float)
    a = me.loc[start_ts]
    b = me.loc[end_ts]
    ok = (a > 0) & (b > 0) & a.notna() & b.notna()
    return (b / a - 1.0).where(ok).dropna()


def breadth_proxy(xs: pd.Series) -> float:
    """Research proxy: share of names with positive skip-month formation return."""
    if xs.empty:
        return 0.0
    return float((xs > 0).mean())


def select_top_n(xs_ret: pd.Series, n_seats: int) -> list[str]:
    if xs_ret.empty:
        return []
    ranked = xs_ret.sort_values(ascending=False)
    return [str(c) for c in ranked.index[:n_seats]]


@dataclass
class BookResult:
    name: str
    nav: pd.Series
    weekly_ret: pd.Series
    holdings: pd.DataFrame
    turnover_oneway_annual: float
    avg_gross: float
    cash_week_pct: float
    n_reb: int


def run_csmom(
    panel: pd.DataFrame,
    cfg: CsmomConfig | None = None,
    eval_start: str = EVAL_START,
    eval_end: str = EVAL_END,
) -> BookResult:
    """Friday close signal, same-close fill, 0.2%RT on turnover, L<=1."""
    cfg = cfg or CsmomConfig()
    panel = panel.sort_index().loc[: pd.Timestamp(eval_end)]
    rets = panel.pct_change()
    weeks = panel.index
    start_ts = pd.Timestamp(eval_start)
    end_ts = pd.Timestamp(eval_end)

    nav_vals: list[float] = []
    nav_idx: list[pd.Timestamp] = []
    wret_vals: list[float] = []
    hold_rows: list[dict] = []
    weights: dict[str, float] = {}
    to_half = 0.0
    expos: list[float] = []
    n_reb = 0
    cash_weeks = 0
    equity = 1.0
    first = True

    for dt in weeks:
        if dt < start_ts or dt > end_ts:
            continue
        if first:
            nav_idx.append(dt)
            nav_vals.append(equity)
            wret_vals.append(0.0)
            first = False
        else:
            r = 0.0
            if weights:
                rr = rets.loc[dt, list(weights)].fillna(0.0)
                r = float(sum(weights[c] * float(rr[c]) for c in weights))
            equity *= 1.0 + r
            nav_idx.append(dt)
            nav_vals.append(equity)
            wret_vals.append(r)
            if weights:
                g = sum(
                    weights[c]
                    * (1.0 + float(rets.at[dt, c] if c in rets.columns and pd.notna(rets.at[dt, c]) else 0.0))
                    for c in weights
                )
                cash = 1.0 - sum(weights.values())
                tot = g + cash
                if tot > 0:
                    weights = {
                        c: weights[c]
                        * (1.0 + float(rets.at[dt, c] if c in rets.columns and pd.notna(rets.at[dt, c]) else 0.0))
                        / tot
                        for c in weights
                    }

        xs = cross_section_formation(panel, dt, cfg.lookback_months, cfg.skip_months)
        br = breadth_proxy(xs)
        risk_on = True
        if cfg.breadth_gate:
            risk_on = br >= BREADTH_GATE
        names = select_top_n(xs, cfg.n_seats) if risk_on else []
        tgt: dict[str, float] = {}
        if names:
            w = min(cfg.l_cap, 1.0) / len(names)
            tgt = {c: w for c in names if c in panel.columns and pd.notna(panel.at[dt, c])}
        to = sum(abs(tgt.get(c, 0.0) - weights.get(c, 0.0)) for c in set(tgt) | set(weights))
        cost = to * cfg.cost_side
        equity *= 1.0 - cost
        nav_vals[-1] = equity
        wret_vals[-1] -= cost
        to_half += to / 2.0
        weights = dict(tgt)
        n_reb += 1
        expos.append(sum(weights.values()))
        if not weights:
            cash_weeks += 1
        hold_rows.append(
            {
                "date": dt.strftime("%Y-%m-%d"),
                "n": len(weights),
                "gross": sum(weights.values()),
                "cash": 1.0 - sum(weights.values()),
                "breadth_proxy": br,
                "risk_on": int(risk_on),
                "codes": "|".join(weights),
                "cost": cost,
            }
        )

    nav = pd.Series(nav_vals, index=pd.DatetimeIndex(nav_idx), name=cfg.label())
    weekly_ret = pd.Series(wret_vals, index=nav.index, name=cfg.label())
    years = max((nav.index[-1] - nav.index[0]).days / 365.25, 1e-9) if len(nav) > 1 else 1.0
    return BookResult(
        name=cfg.label(),
        nav=nav,
        weekly_ret=weekly_ret,
        holdings=pd.DataFrame(hold_rows),
        turnover_oneway_annual=float(to_half / years),
        avg_gross=float(np.mean(expos) if expos else 0.0),
        cash_week_pct=float(cash_weeks / n_reb) if n_reb else float("nan"),
        n_reb=n_reb,
    )
