"""Seat rule for CLENOW-S20-SECONDARY. Not a backtest.

This module only ranks a SHARPE20 shortlist. It does not simulate NAV,
write ``out/``, or touch LIVE. ``run.py`` must keep refusing to execute.

Books (see DESIGN.md):

- off           F0, SHARPE20 order, no Clenow key
- clenow_sort   CS90S / CS60S: score = (exp(beta * 252) - 1) * R^2
- slope_ann_sort CS90R: slope_ann only, R^2 is not in the key

The window length is chosen by the caller (90 or 60). There is no ``k``
and no threshold.
"""

from __future__ import annotations

import math
from datetime import date, timedelta


ANNUALIZATION = 252
MODES = ("off", "clenow_sort", "slope_ann_sort")


class Cand:
    """One name inside an already SHARPE20-sorted candidate list."""

    def __init__(self, code: str, score: float | None = None, slope_ann: float | None = None):
        self.code = str(code)
        self.score = score
        self.slope_ann = slope_ann


def band_k(slots: int) -> int:
    """Same band as AG40S / R2-ER-SECONDARY. Use only when slots >= 1."""
    return max(2 * slots, slots + 2)


def take_band(cands_s20: list, slots: int) -> list:
    """First ``band_k`` names of a SHARPE20-sorted list. Held names already removed."""
    if slots <= 0:
        return []
    return list(cands_s20)[: band_k(slots)]


def _finite(value) -> bool:
    if value is None:
        return False
    try:
        number = float(value)
    except (TypeError, ValueError):
        return False
    return math.isfinite(number)


def ols_clenow(px) -> dict | None:
    """OLS of ln(P) on the trading-day index 0..n-1.

    Returns beta, R^2 clipped to [0, 1], slope_ann = exp(beta*252)-1,
    and score = slope_ann * R^2. Flat, non-finite, non-positive, or an
    R^2 outside [0, 1] by more than 1e-12 -> None. Not zero.
    """
    prices = [float(p) for p in px]
    n = len(prices)
    if n < 2:
        return None
    if any((not math.isfinite(p)) or p <= 0.0 for p in prices):
        return None
    y = [math.log(p) for p in prices]
    mean_t = (n - 1) / 2.0
    mean_y = sum(y) / n
    sxx = 0.0
    syy = 0.0
    sxy = 0.0
    for i, yi in enumerate(y):
        dt = i - mean_t
        dy = yi - mean_y
        sxx += dt * dt
        syy += dy * dy
        sxy += dt * dy
    if sxx <= 0.0 or syy <= 0.0 or not math.isfinite(sxx + syy + sxy):
        return None
    beta = sxy / sxx
    r2 = (sxy * sxy) / (sxx * syy)
    if not math.isfinite(beta) or not math.isfinite(r2):
        return None
    if r2 < -1e-12 or r2 > 1.0 + 1e-12:
        return None
    r2 = min(1.0, max(0.0, r2))
    slope_ann = math.exp(beta * ANNUALIZATION) - 1.0
    if not math.isfinite(slope_ann):
        return None
    score = slope_ann * r2
    if not math.isfinite(score):
        return None
    return {
        "beta": beta,
        "r2": r2,
        "slope_ann": slope_ann,
        "score": score,
    }


def clenow_on(bars, signal: date, n: int, stale_days: int = 5) -> dict | None:
    """Last ``n`` closes on or before the calendar day before ``signal``.

    ``bars`` is an iterable of ``(date, close)``. The signal day's close
    is not an input. A last bar more than ``stale_days`` calendar days
    before ``signal`` is missing. ``t_i`` is the order of those bars,
    not the calendar gap.
    """
    if n < 2:
        return None
    cutoff = signal - timedelta(days=1)
    sub = [(d, p) for d, p in bars if d <= cutoff]
    sub.sort(key=lambda item: item[0])
    if len(sub) < n:
        return None
    if (signal - sub[-1][0]).days > stale_days:
        return None
    return ols_clenow([p for _, p in sub[-n:]])


def sort_tuple(value, s20_index: int, code: str):
    """Ascending key: finite first, then higher value, then S20 order, then code."""
    if _finite(value):
        return (0, -float(value), s20_index, code)
    return (1, 0.0, s20_index, code)


def _key_of(cand: Cand, mode: str):
    if mode == "clenow_sort":
        return cand.score
    if mode == "slope_ann_sort":
        return cand.slope_ann
    raise ValueError(mode)


def pick(band, slots: int, mode: str):
    """Return ``(take, how)``.

    ``how`` is ``sorted``, ``fallback``, or ``empty``. A low or missing
    key never drops a name out of the band. ``len(take)`` is
    ``min(slots, len(band))`` whenever ``slots > 0`` and the band is
    non-empty.
    """
    if mode not in MODES:
        raise ValueError(mode)
    if slots <= 0 or not band:
        return [], "empty"
    names = list(band)
    n_take = min(slots, len(names))
    if mode == "off":
        return names[:n_take], "sorted"
    if all(not _finite(_key_of(cand, mode)) for cand in names):
        return names[:n_take], "fallback"
    order = sorted(
        range(len(names)),
        key=lambda i: sort_tuple(_key_of(names[i], mode), i, names[i].code),
    )
    return [names[i] for i in order[:n_take]], "sorted"
