"""Weekly dual momentum: absolute gate then relative top-N. Research close fill."""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import pandas as pd

from .config import DualMomConfig, EVAL_END, EVAL_START


def skip_lookback_return(px: pd.Series, loc: int, lookback: int, skip: int) -> float:
    """Return at `loc` using px[loc-skip] / px[loc-skip-lookback] - 1.

    `loc` is an integer position in a Friday-aligned series. Missing or
    non-positive prices return NaN. Skip=1 drops the most recent week.
    """
    if lookback <= 0 or skip < 0 or loc < lookback + skip:
        return float("nan")
    end = loc - skip
    start = end - lookback
    if start < 0:
        return float("nan")
    a = float(px.iloc[start])
    b = float(px.iloc[end])
    if not np.isfinite(a) or not np.isfinite(b) or a <= 0 or b <= 0:
        return float("nan")
    return b / a - 1.0


def _cross_section_returns(
    panel: pd.DataFrame, loc: int, lookback: int, skip: int
) -> pd.Series:
    if loc < lookback + skip:
        return pd.Series(dtype=float)
    end = loc - skip
    start = end - lookback
    a = panel.iloc[start]
    b = panel.iloc[end]
    ok = (a > 0) & (b > 0) & a.notna() & b.notna()
    out = (b / a - 1.0).where(ok)
    return out.dropna()


def select_names(
    xs_ret: pd.Series,
    n_seats: int,
    abs_threshold: float,
    apply_absolute: bool,
) -> list[str]:
    if xs_ret.empty:
        return []
    pool = xs_ret[xs_ret > abs_threshold] if apply_absolute else xs_ret
    if pool.empty:
        return []
    ranked = pool.sort_values(ascending=False)
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


def run_dual_momentum(
    panel: pd.DataFrame,
    cfg: DualMomConfig | None = None,
    eval_start: str = EVAL_START,
    eval_end: str = EVAL_END,
) -> BookResult:
    """Friday close signal, same-close fill, cost on turnover, L<=1 cash residual."""
    cfg = cfg or DualMomConfig()
    panel = panel.sort_index()
    panel = panel.loc[: pd.Timestamp(eval_end)]
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
    for i, dt in enumerate(weeks):
        if dt < start_ts or dt > end_ts:
            continue
        if first:
            nav_idx.append(dt)
            nav_vals.append(equity)
            wret_vals.append(0.0)
            first = False
            # fall through: first Friday may already rebalance
        else:
            # earn last week's holdings over this week's close-to-close
            r = 0.0
            if weights:
                rr = rets.loc[dt, list(weights)].fillna(0.0)
                r = float(sum(weights[c] * float(rr[c]) for c in weights))
            equity *= 1.0 + r
            nav_idx.append(dt)
            nav_vals.append(equity)
            wret_vals.append(r)
            if weights:
                g = sum(weights[c] * (1.0 + float(rets.at[dt, c] if c in rets.columns and pd.notna(rets.at[dt, c]) else 0.0)) for c in weights)
                cash = 1.0 - sum(weights.values())
                tot = g + cash
                if tot > 0:
                    weights = {c: weights[c] * (1.0 + float(rets.at[dt, c] if c in rets.columns and pd.notna(rets.at[dt, c]) else 0.0)) / tot for c in weights}

        xs = _cross_section_returns(panel, i, cfg.lookback, cfg.skip)
        names = select_names(xs, cfg.n_seats, cfg.abs_threshold, cfg.apply_absolute)
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


def run_equal_weight(
    panel: pd.DataFrame,
    eval_start: str = EVAL_START,
    eval_end: str = EVAL_END,
    cost_side: float = 0.0,
    name: str = "POOL-EW",
) -> BookResult:
    """Investable-name equal weight each Friday (listed that week). Research bench."""
    panel = panel.sort_index().loc[: pd.Timestamp(eval_end)]
    rets = panel.pct_change()
    start_ts = pd.Timestamp(eval_start)
    equity = 1.0
    nav_vals: list[float] = []
    nav_idx: list[pd.Timestamp] = []
    wret_vals: list[float] = []
    weights: dict[str, float] = {}
    to_half = 0.0
    expos: list[float] = []
    hold_rows: list[dict] = []
    first = True
    n_reb = 0
    for dt in panel.index:
        if dt < start_ts:
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
        live = panel.loc[dt].dropna()
        live = live[live > 0]
        tgt = {c: 1.0 / len(live) for c in live.index} if len(live) else {}
        to = sum(abs(tgt.get(c, 0.0) - weights.get(c, 0.0)) for c in set(tgt) | set(weights))
        cost = to * cost_side
        equity *= 1.0 - cost
        nav_vals[-1] = equity
        wret_vals[-1] -= cost
        to_half += to / 2.0
        weights = dict(tgt)
        n_reb += 1
        expos.append(sum(weights.values()))
        hold_rows.append(
            {
                "date": dt.strftime("%Y-%m-%d"),
                "n": len(weights),
                "gross": sum(weights.values()),
                "cash": 1.0 - sum(weights.values()),
                "codes": "",
                "cost": cost,
            }
        )
    nav = pd.Series(nav_vals, index=pd.DatetimeIndex(nav_idx), name=name)
    years = max((nav.index[-1] - nav.index[0]).days / 365.25, 1e-9) if len(nav) > 1 else 1.0
    return BookResult(
        name=name,
        nav=nav,
        weekly_ret=pd.Series(wret_vals, index=nav.index, name=name),
        holdings=pd.DataFrame(hold_rows),
        turnover_oneway_annual=float(to_half / years),
        avg_gross=float(np.mean(expos) if expos else 0.0),
        cash_week_pct=0.0,
        n_reb=n_reb,
    )
