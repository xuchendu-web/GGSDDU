"""Weekly dual momentum on QDII sleeve: MA trend + R12w absolute, rank by R12w."""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import pandas as pd

from .config import EVAL_END, EVAL_START, QdiiDmConfig


def r12w_at(panel: pd.DataFrame, loc: int, lookback: int, skip: int) -> pd.Series:
    if lookback <= 0 or loc < lookback + skip:
        return pd.Series(dtype=float)
    end = loc - skip
    start = end - lookback
    if start < 0:
        return pd.Series(dtype=float)
    a = panel.iloc[start]
    b = panel.iloc[end]
    ok = (a > 0) & (b > 0) & a.notna() & b.notna()
    return (b / a - 1.0).where(ok).dropna()


def ma_at(panel: pd.DataFrame, loc: int, window: int) -> pd.Series:
    if window <= 0 or loc < window - 1:
        return pd.Series(dtype=float)
    seg = panel.iloc[loc - window + 1 : loc + 1]
    return seg.mean(axis=0).dropna()


def select_names(
    panel: pd.DataFrame,
    loc: int,
    cfg: QdiiDmConfig,
) -> list[str]:
    r12 = r12w_at(panel, loc, cfg.r12_lookback, cfg.r12_skip)
    if r12.empty:
        return []
    px = panel.iloc[loc]
    pool = r12.copy()
    if cfg.apply_r12_abs:
        pool = pool[pool > 0]
    if pool.empty:
        return []
    if cfg.apply_ma:
        ma = ma_at(panel, loc, cfg.ma_weeks)
        common = pool.index.intersection(ma.index).intersection(px.dropna().index)
        if len(common) == 0:
            return []
        ok = px.reindex(common) > ma.reindex(common)
        pool = pool.reindex(common)[ok]
        pool = pool.dropna()
    if pool.empty:
        return []
    ranked = pool.sort_values(ascending=False)
    return [str(c) for c in ranked.index[: cfg.n_seats]]


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


def _run_book(
    panel: pd.DataFrame,
    cfg: QdiiDmConfig,
    eval_start: str,
    eval_end: str,
    select_fn,
) -> BookResult:
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
    label = cfg.label()

    for i, dt in enumerate(weeks):
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
                    * (
                        1.0
                        + float(
                            rets.at[dt, c]
                            if c in rets.columns and pd.notna(rets.at[dt, c])
                            else 0.0
                        )
                    )
                    for c in weights
                )
                cash = 1.0 - sum(weights.values())
                tot = g + cash
                if tot > 0:
                    weights = {
                        c: weights[c]
                        * (
                            1.0
                            + float(
                                rets.at[dt, c]
                                if c in rets.columns and pd.notna(rets.at[dt, c])
                                else 0.0
                            )
                        )
                        / tot
                        for c in weights
                    }

        names = select_fn(panel, i, cfg)
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
                "codes": "|".join(sorted(weights)),
                "cost": cost,
            }
        )

    nav = pd.Series(nav_vals, index=pd.DatetimeIndex(nav_idx), name=label)
    weekly_ret = pd.Series(wret_vals, index=nav.index, name=label)
    years = max((nav.index[-1] - nav.index[0]).days / 365.25, 1e-9) if len(nav) > 1 else 1.0
    return BookResult(
        name=label,
        nav=nav,
        weekly_ret=weekly_ret,
        holdings=pd.DataFrame(hold_rows),
        turnover_oneway_annual=float(to_half / years),
        avg_gross=float(np.mean(expos) if expos else 0.0),
        cash_week_pct=float(cash_weeks / n_reb) if n_reb else float("nan"),
        n_reb=n_reb,
    )


def run_qdii_dual_mom(
    panel: pd.DataFrame,
    cfg: QdiiDmConfig | None = None,
    eval_start: str = EVAL_START,
    eval_end: str = EVAL_END,
) -> BookResult:
    cfg = cfg or QdiiDmConfig()
    return _run_book(panel, cfg, eval_start, eval_end, select_names)


def run_equal_weight_bh(
    panel: pd.DataFrame,
    eval_start: str = EVAL_START,
    eval_end: str = EVAL_END,
    cost_side: float = 0.0,
    name: str = "OX-EW-BH",
) -> BookResult:
    """Full sleeve equal-weight each Friday; residual cash when names missing."""
    cfg = QdiiDmConfig(cost_side=cost_side, name=name)

    def _ew_select(p: pd.DataFrame, loc: int, _cfg: QdiiDmConfig) -> list[str]:
        row = p.iloc[loc].dropna()
        row = row[row > 0]
        return [str(c) for c in row.index]

    res = _run_book(panel, cfg, eval_start, eval_end, _ew_select)
    res.name = name
    res.nav.name = name
    res.weekly_ret.name = name
    return res


def run_cash(
    panel: pd.DataFrame,
    eval_start: str = EVAL_START,
    eval_end: str = EVAL_END,
    name: str = "CASH",
) -> BookResult:
    weeks = panel.index[(panel.index >= pd.Timestamp(eval_start)) & (panel.index <= pd.Timestamp(eval_end))]
    nav = pd.Series(1.0, index=weeks, name=name)
    wr = pd.Series(0.0, index=weeks, name=name)
    hold = pd.DataFrame(
        {
            "date": [d.strftime("%Y-%m-%d") for d in weeks],
            "n": 0,
            "gross": 0.0,
            "cash": 1.0,
            "codes": "",
            "cost": 0.0,
        }
    )
    return BookResult(
        name=name,
        nav=nav,
        weekly_ret=wr,
        holdings=hold,
        turnover_oneway_annual=0.0,
        avg_gross=0.0,
        cash_week_pct=1.0,
        n_reb=len(weeks),
    )
