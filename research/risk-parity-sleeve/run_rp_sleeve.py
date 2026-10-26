#!/usr/bin/env python3
"""RP-SLEEVE-IV60: sleeve inverse-vol weekly vs FACE LIVE1430-B45-S20.

Research only. Does not write strategy_exec / LIVE / champion.
"""
from __future__ import annotations

import json
import math
import subprocess
import sys
from pathlib import Path
from typing import Any

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[1]
KIT = REPO / "research" / "cloud_batch" / "CLOUD-BATCH-2026-10-26"
CACHE = KIT / "data" / "research_cache"
OUT = HERE / "RP-SLEEVE-IV60-LIVE1430"
READONLY = HERE / "_readonly_face"

EVAL_START = "2020-01-03"
END_S = "2026-10-23"
LIVE_COST_RT = 0.002
SIGMA_STAR = 0.25
LCAP = 1.0
MIN_BARS_BEFORE = 21
CMD_CODES = {"518880", "518600", "159980", "159985", "159981"}
EQ_FAMILIES = {
    "港股·宽基",
    "海外·美股核心",
    "海外·美股成长",
    "海外·日本",
    "海外·欧洲",
    "海外·其他",
}
SLEEVES = ("EQ", "SEC", "CMD")
BOOKS = [
    "FACE",
    "RP-IV60",
    "RP-IV20",
    "RP-IV60-CAP40",
    "RP-ERC60",
    "RP-IV60-EQONLY",
]
ANCHOR_RET = 1.316
ANCHOR_MDD = 0.188
ANCHOR_SHARPE = 0.82
FACE_TO_LO, FACE_TO_HI = 0.10, 0.40

GIT_FACE = "origin/cursor/spike-s20-extend-rebase-live1430-27f1"
GIT_TV = "origin/cursor/s20-tv-grid-live1430-26c5"
GIT_FACE_DIR = "research/cloud_batch/SPIKE-S20-EXTEND-REBASE-LIVE1430"
GIT_LISTING = (
    "research/cloud_batch/CLOUD-BATCH-2026-10-26/data/research_cache/listing.json"
)


def sleeve_of(l0: str, family: str) -> str:
    if l0 == "商品":
        return "CMD"
    if str(family).startswith("宽基") or family in EQ_FAMILIES:
        return "EQ"
    if l0 in {"中国权益", "港股中资离岸", "海外权益"}:
        return "SEC"
    raise ValueError(f"unmapped {l0} {family}")


def first_existing(paths: list[Path]) -> Path | None:
    for p in paths:
        if p is not None and p.exists():
            return p
    return None


def git_show(spec: str, dest: Path) -> Path:
    dest.parent.mkdir(parents=True, exist_ok=True)
    data = subprocess.check_output(["git", "show", spec], cwd=str(REPO))
    dest.write_bytes(data)
    return dest


def ensure_readonly() -> dict[str, Path]:
    READONLY.mkdir(parents=True, exist_ok=True)
    files = {
        "nav": (
            READONLY / "nav_LIVE1430-B45-S20.csv",
            f"{GIT_FACE}:{GIT_FACE_DIR}/nav_LIVE1430-B45-S20.csv",
        ),
        "hold": (
            READONLY / "holdings_LIVE1430-B45-S20.csv",
            f"{GIT_FACE}:{GIT_FACE_DIR}/holdings_LIVE1430-B45-S20.csv",
        ),
        "metrics": (
            READONLY / "metrics.csv",
            f"{GIT_FACE}:{GIT_FACE_DIR}/metrics.csv",
        ),
        "listing": (
            first_existing([CACHE / "listing.json", READONLY / "listing.json"])
            or (READONLY / "listing.json"),
            f"{GIT_TV}:{GIT_LISTING}",
        ),
    }
    out: dict[str, Path] = {}
    for key, (path, spec) in files.items():
        p = Path(path)
        if not p.exists():
            git_show(spec, p)
        out[key] = p
    return out


def find_universe() -> Path:
    p = first_existing(
        [
            Path("/workspace/strategy-weekly/etf_replace_only_436/universe_replace_only_436.csv"),
            KIT / "data" / "universe_replace_only_436.csv",
        ]
    )
    if p is None:
        dest = READONLY / "universe_replace_only_436.csv"
        git_show(
            f"{GIT_TV}:research/cloud_batch/CLOUD-BATCH-2026-10-26/data/universe_replace_only_436.csv",
            dest,
        )
        return dest
    return p


def find_face_calendar() -> Path | None:
    return first_existing(
        [
            CACHE / "holdings_ro2_extended.csv",
            Path("/workspace/strategy-weekly/etf_replace_only_436/from2016_aum2/holdings_ro2_from2016.csv"),
        ]
    )


def pct(x: float | None) -> str:
    if x is None or (isinstance(x, float) and (math.isnan(x) or math.isinf(x))):
        return "—"
    return f"{100 * x:.1f}%"


def num(x: float | None, nd: int = 2) -> str:
    if x is None or (isinstance(x, float) and (math.isnan(x) or math.isinf(x))):
        return "—"
    return f"{x:.{nd}f}"


def load_listing(path: Path) -> dict[str, pd.Timestamp]:
    obj = json.loads(path.read_text(encoding="utf-8"))
    out: dict[str, pd.Timestamp] = {}
    if not isinstance(obj, dict):
        return out
    for k, v in obj.items():
        code = str(k).zfill(6)
        raw = None
        if isinstance(v, dict):
            raw = v.get("ipo_bs") or v.get("listing") or v.get("first_sina")
        elif isinstance(v, str):
            raw = v
        if raw:
            try:
                out[code] = pd.Timestamp(str(raw)[:10])
            except Exception:
                pass
    return out


def load_prices(codes: list[str]) -> tuple[pd.DataFrame, int]:
    sina_dir = CACHE / "sina_daily"
    day_dir = CACHE / "day"
    series: dict[str, pd.Series] = {}
    missing = 0
    for c in codes:
        s = None
        fp = sina_dir / f"{c}.csv"
        if fp.exists():
            df = pd.read_csv(fp)
            if "date" in df.columns and "close" in df.columns:
                idx = pd.to_datetime(df["date"].astype(str).str[:10])
                s = pd.Series(df["close"].astype(float).values, index=idx, dtype=float)
                s = s[s > 0]
                s = s[~s.index.duplicated(keep="last")].sort_index()
        fday = day_dir / f"{c}.json"
        if s is None and fday.exists():
            j = json.loads(fday.read_text(encoding="utf-8"))
            bars = j.get("bars") if isinstance(j, dict) else j
            if bars:
                idx = pd.to_datetime([b["date"] for b in bars])
                s = pd.Series([float(b["c"]) for b in bars], index=idx, dtype=float)
                s = s[s > 0]
                s = s[~s.index.duplicated(keep="last")].sort_index()
        if s is None or len(s) < 10:
            missing += 1
            continue
        series[c] = s
    px = pd.DataFrame(series).sort_index()
    return px, missing


def stats_from_returns(r: pd.Series) -> dict[str, float]:
    r = r.astype(float).fillna(0.0)
    q = (1.0 + r).cumprod()
    ret = float(q.iloc[-1] - 1.0) if len(q) else float("nan")
    dd = float((q / q.cummax().clip(lower=1e-12) - 1.0).min()) if len(q) else float("nan")
    n = int((r.index[-1] - r.index[0]).days) if len(r) else 0
    cagr = (1.0 + ret) ** (365.25 / n) - 1.0 if n > 0 and (1.0 + ret) > 0 else float("nan")
    cal = cagr / abs(dd) if dd < 0 else float("nan")
    std = float(r.std(ddof=1)) if len(r) > 1 else float("nan")
    sharpe = float(r.mean() / std * math.sqrt(252)) if std and std > 0 else float("nan")
    return {"ret": ret, "maxDD": dd, "CAGR": cagr, "Calmar": cal, "Sharpe": sharpe}


def window_stats(r: pd.Series, start: str, end: str | None) -> dict[str, float]:
    sub = r[(r.index >= pd.Timestamp(start))]
    if end:
        sub = sub[sub.index <= pd.Timestamp(end)]
    st = stats_from_returns(sub)
    return {"ret": st["ret"], "maxDD": st["maxDD"], "Calmar": st["Calmar"]}


def yearly_rows(book: str, r: pd.Series) -> list[dict[str, Any]]:
    rows = []
    for y, sy in r.groupby(r.index.year):
        if len(sy) < 2:
            continue
        qy = (1.0 + sy).cumprod()
        ret = float(qy.iloc[-1] - 1.0)
        mdd = float((qy / qy.cummax().clip(lower=1e-12) - 1.0).min())
        vol = float(sy.std(ddof=1) * math.sqrt(252)) if len(sy) > 1 else float("nan")
        sharpe = (
            float(sy.mean() / sy.std(ddof=1) * math.sqrt(252))
            if sy.std(ddof=1) > 0
            else float("nan")
        )
        calmar = ret / abs(mdd) if mdd < 0 else float("nan")
        rows.append(
            {
                "book": book,
                "year": int(y),
                "ret": ret,
                "mdd": mdd,
                "vol": vol,
                "sharpe": sharpe,
                "calmar": calmar,
            }
        )
    return rows


def inv_vol_weights(sigmas: dict[str, float]) -> dict[str, float]:
    inv = {s: 1.0 / sig for s, sig in sigmas.items() if sig > 0 and math.isfinite(sig)}
    z = sum(inv.values())
    if z <= 0:
        return {}
    return {s: v / z for s, v in inv.items()}


def apply_cap40(w: dict[str, float], cap: float = 0.40) -> dict[str, float]:
    w = {s: float(v) for s, v in w.items()}
    for _ in range(100):
        over = [s for s, v in w.items() if v > cap + 1e-12]
        if not over:
            break
        excess = sum(w[s] - cap for s in over)
        for s in over:
            w[s] = cap
        free = [s for s in w if w[s] < cap - 1e-12]
        if not free:
            break
        tot = sum(w[s] for s in free)
        if tot <= 0:
            share = excess / len(free)
            for s in free:
                w[s] += share
        else:
            for s in free:
                w[s] += excess * (w[s] / tot)
    return w


def erc_weights(
    week_map: dict[str, np.ndarray], w0: dict[str, float]
) -> tuple[dict[str, float], bool]:
    sleeves = [s for s in SLEEVES if s in week_map]
    if len(sleeves) == 1:
        return {sleeves[0]: 1.0}, False
    if not sleeves:
        return {}, False
    X = np.column_stack([week_map[s] for s in sleeves])
    cov = np.cov(X, rowvar=False, ddof=1)
    if np.ndim(cov) == 0:
        cov = np.array([[float(cov)]])
    cov = np.asarray(cov, dtype=float) + 1e-8 * np.eye(len(sleeves))
    w = np.array([w0.get(s, 1.0 / len(sleeves)) for s in sleeves], dtype=float)
    if w.sum() <= 0 or not np.all(np.isfinite(w)):
        return dict(w0), True
    w = w / w.sum()
    for _ in range(500):
        m = cov @ w
        if (not np.all(np.isfinite(m))) or np.any(m <= 0):
            return dict(w0), True
        invm = 1.0 / m
        w_new = invm / invm.sum()
        if (not np.all(np.isfinite(w_new))) or np.any(w_new < 0):
            return dict(w0), True
        rc = w_new * (cov @ w_new)
        mu = float(rc.mean())
        if not math.isfinite(mu) or mu == 0:
            return dict(w0), True
        w = w_new
        if float(np.max(np.abs(rc - mu))) < 1e-8 * mu:
            return {s: float(x) for s, x in zip(sleeves, w)}, False
    return dict(w0), True


def pick_reps(
    sleeve_df: pd.DataFrame,
    cutoff: pd.Timestamp,
    px: pd.DataFrame,
    listing: dict[str, pd.Timestamp],
) -> list[str]:
    by_fam: dict[str, tuple[float, str]] = {}
    for r in sleeve_df.itertuples():
        c = str(r.code)
        if c not in px.columns:
            continue
        ser = px[c].dropna()
        if cutoff not in ser.index:
            continue
        listed = listing.get(c)
        if listed is None and len(ser):
            listed = ser.index[0]
        if listed is not None and cutoff < listed:
            continue
        before = ser.loc[ser.index < cutoff]
        if len(before) < MIN_BARS_BEFORE:
            continue
        fam = str(r.family)
        aum = float(r.aum)
        prev = by_fam.get(fam)
        if prev is None or aum > prev[0] or (aum == prev[0] and c < prev[1]):
            by_fam[fam] = (aum, c)
    return [code for _, code in by_fam.values()]


def week_segments(
    grid: list[pd.Timestamp], days: pd.DatetimeIndex
) -> list[tuple[pd.Timestamp, pd.DatetimeIndex]]:
    out: list[tuple[pd.Timestamp, pd.DatetimeIndex]] = []
    for i in range(1, len(grid)):
        a, b = grid[i - 1], grid[i]
        seg = days[(days > a) & (days <= b)]
        if len(seg):
            out.append((b, seg))
    return out


def week_returns(
    basket: pd.Series, segs: list[tuple[pd.Timestamp, pd.DatetimeIndex]]
) -> list[tuple[pd.Timestamp, float]]:
    out: list[tuple[pd.Timestamp, float]] = []
    for end, seg in segs:
        sub = basket.reindex(seg)
        if sub.notna().sum() == 0:
            continue
        wr = float((1.0 + sub.fillna(0.0)).prod() - 1.0)
        out.append((end, wr))
    return out


def run_live_tv(
    hold: dict[pd.Timestamp, list[str]],
    days: pd.DatetimeIndex,
    R: pd.DataFrame,
) -> tuple[pd.Series, pd.Series, list[float]]:
    reb = sorted(hold)
    rp = pd.Series(0.0, index=days)
    Ls = pd.Series(0.0, index=days)
    prev: dict[str, float] = {}
    cst = pd.Series(0.0, index=days)
    tos: list[float] = []
    R2 = R.reindex(days)
    for i, d in enumerate(reb):
        cs = [c for c in hold[d] if c in R2.columns]
        nxt = reb[i + 1] if i + 1 < len(reb) else days[-1] + pd.Timedelta(days=1)
        seg = days[(days > d) & (days <= nxt)]
        if not cs:
            w: dict[str, float] = {}
            L = 0.0
        else:
            w = {c: 1.0 / len(cs) for c in cs}
            past = rp[rp.index <= d]
            past = past[past != 0]
            if len(past) < 2:
                L = 1.0
            else:
                s20 = float(past.iloc[-20:].std(ddof=1) * math.sqrt(252))
                s60 = float(past.iloc[-60:].std(ddof=1) * math.sqrt(252))
                sh = max(s20, s60)
                L = float(min(LCAP, SIGMA_STAR / sh)) if sh and sh > 0 else 1.0
        wt = {c: L * v for c, v in w.items()}
        to = sum(abs(wt.get(k, 0.0) - prev.get(k, 0.0)) for k in set(wt) | set(prev))
        tos.append(to / 2.0)
        prev = wt
        if d in cst.index:
            cst.loc[d] = to * LIVE_COST_RT / 2.0
        if w and len(seg):
            cols = [c for c in w if c in R2.columns]
            if cols:
                ww = pd.Series({c: w[c] for c in cols})
                rp.loc[seg] = (R2.loc[seg, cols].fillna(0.0) @ ww).values
                Ls.loc[seg] = L
    r = rp * Ls - cst
    return r, Ls, tos


def face_from_published(
    nav_path: Path,
    hold_path: Path,
    days: pd.DatetimeIndex,
    R: pd.DataFrame,
) -> dict[str, Any]:
    nav = pd.read_csv(nav_path, index_col=0)
    nav.index = pd.to_datetime(nav.index)
    s = nav.iloc[:, 0].astype(float).sort_index()
    s = s[(s.index >= EVAL_START) & (s.index <= END_S)]
    r = s.pct_change()
    r.iloc[0] = float(s.iloc[0] - 1.0)
    r = r.reindex(days).fillna(0.0)
    r = r[(r.index >= s.index[0]) & (r.index <= s.index[-1])]
    hold_df = pd.read_csv(hold_path)
    hold_df["date"] = pd.to_datetime(hold_df["date"].astype(str).str[:10])
    hold: dict[pd.Timestamp, list[str]] = {}
    ew_prev: dict[str, float] = {}
    ew_tos: list[float] = []
    n_cash = 0
    for row in hold_df.itertuples():
        raw = "" if pd.isna(row.codes) else str(row.codes)
        cs = [
            c.strip().zfill(6)
            for c in raw.split(",")
            if c.strip() and c.strip().lower() != "nan"
        ]
        hold[pd.Timestamp(row.date)] = cs
        w = {c: 1.0 / len(cs) for c in cs} if cs else {}
        ew_tos.append(
            sum(abs(w.get(k, 0.0) - ew_prev.get(k, 0.0)) for k in set(w) | set(ew_prev))
            / 2.0
        )
        ew_prev = w
        if not cs:
            n_cash += 1
    r_tv, Ls, engine_tos = run_live_tv(hold, days, R)
    avgL = float(Ls[Ls > 0].mean()) if (Ls > 0).any() else 0.0
    return {
        "r": r,
        "nav": (1.0 + r).cumprod(),
        "hold": hold,
        "avgTO": float(np.mean(engine_tos)) if engine_tos else float("nan"),
        "ewTO": float(np.mean(ew_tos)) if ew_tos else float("nan"),
        "avgL": avgL,
        "cash_week_pct": n_cash / len(hold_df) if len(hold_df) else float("nan"),
        "n_weeks": int(len(hold_df)),
        "replay_r": r_tv.reindex(r.index).fillna(0.0),
    }


def simulate_rp(
    book: str,
    grid: list[pd.Timestamp],
    reb: list[pd.Timestamp],
    days: pd.DatetimeIndex,
    R: pd.DataFrame,
    px: pd.DataFrame,
    by_sleeve: dict[str, pd.DataFrame],
    listing: dict[str, pd.Timestamp],
) -> dict[str, Any]:
    lookback = 20 if book == "RP-IV20" else 60
    min_weeks = 12 if book == "RP-IV20" else 60
    use_cap = book == "RP-IV60-CAP40"
    use_erc = book == "RP-ERC60"
    eq_only = book == "RP-IV60-EQONLY"
    active = ("EQ", "SEC") if eq_only else SLEEVES

    rp = pd.Series(0.0, index=days)
    Ls = pd.Series(0.0, index=days)
    cst = pd.Series(0.0, index=days)
    prev_name: dict[str, float] = {}
    tos: list[float] = []
    weight_rows: list[dict[str, Any]] = []
    holding_rows: list[dict[str, Any]] = []
    sleeve_w_hist: dict[str, list[float]] = {s: [] for s in SLEEVES}
    missing_flags: list[bool] = []
    missing_by: dict[str, int] = {s: 0 for s in SLEEVES}
    first_ok: dict[str, str | None] = {s: None for s in SLEEVES}
    erc_fallback = 0
    segs = week_segments(grid, days)

    for i, d in enumerate(reb):
        cutoff_cands = days[days < d]
        if not len(cutoff_cands):
            continue
        cutoff = cutoff_cands[-1]
        sigmas: dict[str, float] = {}
        reps: dict[str, list[str]] = {}
        week_map: dict[str, np.ndarray] = {}
        for s in active:
            rs = pick_reps(by_sleeve[s], cutoff, px, listing)
            reps[s] = rs
            if not rs:
                missing_by[s] += 1
                continue
            basket = R[rs].mean(axis=1, skipna=True)
            prior = [sg for sg in segs if sg[0] < d]
            wrs = week_returns(basket, prior[-(lookback + 4) :])
            done = [wr for _end, wr in wrs]
            if len(done) < min_weeks:
                missing_by[s] += 1
                continue
            use = done[-lookback:] if len(done) >= lookback else done
            arr = np.asarray(use, dtype=float)
            sig = float(arr.std(ddof=1) * math.sqrt(52))
            if not math.isfinite(sig) or sig <= 0:
                missing_by[s] += 1
                continue
            sigmas[s] = sig
            week_map[s] = arr
            if first_ok[s] is None:
                first_ok[s] = str(d.date())

        any_missing = any(s not in sigmas for s in active)
        missing_flags.append(any_missing)
        w_s = inv_vol_weights(sigmas)
        if use_erc and w_s:
            w_s, fell = erc_weights(week_map, w_s)
            if fell:
                erc_fallback += 1
                w_s = inv_vol_weights(sigmas)
        if use_cap and w_s:
            w_s = apply_cap40(w_s)
        for s in SLEEVES:
            sleeve_w_hist[s].append(float(w_s.get(s, 0.0)))

        nxt = reb[i + 1] if i + 1 < len(reb) else days[-1] + pd.Timedelta(days=1)
        seg = days[(days > d) & (days <= nxt)]
        if not w_s:
            L = 0.0
            name_w: dict[str, float] = {}
        else:
            past = rp[rp.index <= d]
            past = past[past != 0]
            if len(past) < 2:
                L = 1.0
            else:
                s20 = float(past.iloc[-20:].std(ddof=1) * math.sqrt(252))
                s60 = float(past.iloc[-60:].std(ddof=1) * math.sqrt(252))
                sh = max(s20, s60)
                L = float(min(LCAP, SIGMA_STAR / sh)) if sh and sh > 0 else 1.0
            name_w = {}
            for s, ws in w_s.items():
                rs = reps.get(s) or []
                if not rs:
                    continue
                share = ws / len(rs)
                for c in rs:
                    name_w[c] = name_w.get(c, 0.0) + share
        wt = {c: L * v for c, v in name_w.items()}
        to = sum(abs(wt.get(k, 0.0) - prev_name.get(k, 0.0)) for k in set(wt) | set(prev_name))
        tos.append(to / 2.0)
        prev_name = wt
        if d in cst.index:
            cst.loc[d] = to * LIVE_COST_RT / 2.0
        if name_w and len(seg):
            cols = [c for c in name_w if c in R.columns]
            if cols:
                ww = pd.Series({c: name_w[c] for c in cols})
                rp.loc[seg] = (R.loc[seg, cols].fillna(0.0) @ ww).values
                Ls.loc[seg] = L
        w_eq, w_sec, w_cmd = (w_s.get("EQ", 0.0), w_s.get("SEC", 0.0), w_s.get("CMD", 0.0))
        w_sum = w_eq + w_sec + w_cmd
        weight_rows.append(
            {
                "date": str(d.date()),
                "w_EQ": w_eq,
                "w_SEC": w_sec,
                "w_CMD": w_cmd,
                "L": L,
                "w_cash": 1.0 - L * w_sum,
            }
        )
        for c, v in wt.items():
            holding_rows.append({"date": str(d.date()), "code": c, "weight": v})

    r = rp * Ls - cst
    r = r[(r.index >= EVAL_START) & (r.index <= END_S)]
    avgL = float(Ls[Ls > 0].mean()) if (Ls > 0).any() else 0.0
    cash_week = (
        float(np.mean([row["w_cash"] >= 0.999 for row in weight_rows]))
        if weight_rows
        else float("nan")
    )
    max_sw = max((float(np.mean(v)) if v else 0.0) for v in sleeve_w_hist.values())
    return {
        "r": r,
        "nav": (1.0 + r).cumprod(),
        "avgTO": float(np.mean(tos)) if tos else float("nan"),
        "avgL": avgL,
        "cash_week_pct": cash_week,
        "max_sleeve_avg_w": max_sw,
        "sleeve_avg_w": {s: float(np.mean(v)) if v else 0.0 for s, v in sleeve_w_hist.items()},
        "sleeve_missing_week_pct": {
            s: missing_by[s] / len(reb) if reb else float("nan") for s in SLEEVES
        },
        "any_missing_week_pct": float(np.mean(missing_flags)) if missing_flags else float("nan"),
        "first_ok": first_ok,
        "erc_fallback_weeks": erc_fallback,
        "weight_rows": weight_rows,
        "holding_rows": holding_rows,
        "n_weeks": len(reb),
    }


def gates(book: dict[str, float], face: dict[str, float]) -> dict[str, Any]:
    d_ret = book["ret"] - face["ret"]
    d_mdd = abs(book["maxDD"]) - abs(face["maxDD"])
    g1 = d_ret >= d_mdd
    g2 = book["Calmar"] >= face["Calmar"] if math.isfinite(book["Calmar"]) else False
    g3 = book["Sharpe"] >= face["Sharpe"] if math.isfinite(book["Sharpe"]) else False
    g4 = book["ret_2023_26"] >= face["ret_2023_26"] and book["ret_2023_26"] > 0
    return {
        "G1": bool(g1),
        "G2": bool(g2),
        "G3": bool(g3),
        "G4": bool(g4),
        "d_ret": float(d_ret),
        "d_mdd": float(d_mdd),
        "d_sharpe": float(book["Sharpe"] - face["Sharpe"]),
        "d_calmar": float(book["Calmar"] - face["Calmar"]),
        "d_ret_2023": float(book["ret_2023_26"] - face["ret_2023_26"]),
        "d_to": float(book["avgTO"] - face["avgTO"]),
    }


def row_metrics(name: str, pack: dict[str, Any], extra: dict[str, Any] | None = None) -> dict[str, Any]:
    r: pd.Series = pack["r"]
    st = stats_from_returns(r)
    w20 = window_stats(r, "2020-01-01", "2022-12-31")
    w23 = window_stats(r, "2023-01-01", None)
    out = {
        "book": name,
        "ret": st["ret"],
        "maxDD": st["maxDD"],
        "CAGR": st["CAGR"],
        "Calmar": st["Calmar"],
        "Sharpe": st["Sharpe"],
        "avgTO": pack.get("avgTO", float("nan")),
        "annTO": pack.get("avgTO", float("nan")) * 52.0,
        "ret_2020_22": w20["ret"],
        "DD_2020_22": w20["maxDD"],
        "Calmar_2020_22": w20["Calmar"],
        "ret_2023_26": w23["ret"],
        "DD_2023_26": w23["maxDD"],
        "Calmar_2023_26": w23["Calmar"],
        "avgL": pack.get("avgL", float("nan")),
        "cash_week_pct": pack.get("cash_week_pct", float("nan")),
        "max_sleeve_avg_w": pack.get("max_sleeve_avg_w", float("nan")),
        "erc_fallback_weeks": pack.get("erc_fallback_weeks", 0),
    }
    if extra:
        out.update(extra)
    return out


def write_report(
    metrics: pd.DataFrame,
    summary: dict[str, Any],
    neighbor_notes: list[str],
) -> str:
    main = metrics[metrics.book == "RP-IV60"].iloc[0]
    cols = [
        ("book", "簿", lambda r: r.book),
        ("ret", "ret", lambda r: pct(r.ret)),
        ("maxDD", "maxDD", lambda r: pct(r.maxDD)),
        ("CAGR", "CAGR", lambda r: pct(r.CAGR)),
        ("Calmar", "Calmar", lambda r: num(r.Calmar)),
        ("Sharpe", "Sharpe", lambda r: num(r.Sharpe)),
        ("avgTO", "一手换手", lambda r: num(r.avgTO, 3)),
        ("annTO", "年化换手", lambda r: num(r.annTO, 2)),
        ("ret_2020_22", "2020–22 ret", lambda r: pct(r.ret_2020_22)),
        ("DD_2020_22", "2020–22 DD", lambda r: pct(r.DD_2020_22)),
        ("Calmar_2020_22", "2020–22 Calmar", lambda r: num(r.Calmar_2020_22)),
        ("ret_2023_26", "2023–26 ret", lambda r: pct(r.ret_2023_26)),
        ("DD_2023_26", "2023–26 DD", lambda r: pct(r.DD_2023_26)),
        ("Calmar_2023_26", "2023–26 Calmar", lambda r: num(r.Calmar_2023_26)),
        ("avgL", "avgL", lambda r: num(r.avgL)),
        ("cash_week_pct", "现金周", lambda r: pct(r.cash_week_pct)),
        ("max_sleeve_avg_w", "单袖最大均权", lambda r: num(r.max_sleeve_avg_w)),
        ("erc_fallback_weeks", "ERC回退周", lambda r: str(int(r.erc_fallback_weeks))),
    ]
    header = "| " + " | ".join(c[1] for c in cols) + " |"
    sep = "|" + "|".join("---:" if c[0] != "book" else "---" for c in cols) + "|"
    body = "\n".join("| " + " | ".join(c[2](r) for c in cols) + " |" for r in metrics.itertuples())
    table = f"{header}\n{sep}\n{body}"
    g = summary["gates"]
    cov = summary["coverage"]
    verdict = summary["verdict"]
    sentence = summary["verdict_sentence"]
    notes = "\n".join(f"- {n}" for n in neighbor_notes)
    return f"""# REPORT · RP-SLEEVE-IV60（袖子逆波动周频对照 FACE）

- 编号：RP-SLEEVE-IV60 / 2026-10-26 / 对照 LIVE1430-B45-S20
- 性质：研究池探索。记正不换冠。未改 strategy_exec / LIVE / champion。

## 1. 准则原文

同一研究池（aum≥2，324 只）、同一 FACE 日历周、周五收盘成交、TV25 且 L≤1、0.2% 往返。主簿不做 14:30 classify。

袖子划分（无重叠）：EQ 宽基权益 59 / SEC 行业风格主题 260 / CMD 商品 5（518880, 518600, 159980, 159985, 159981）。现金袖收益 0，不引入债券或 511010/511260/512890。

每个信号周、每个袖：可投名字须在截止日（信号日前一交易日）有价，且截止日前至少 21 根日收盘；每个 family 留 aum 最大的一只（并列取较小 code）。篮子日收益 = 当周代表等权，缺价当天在其余代表上归一；回看窗内不重组代表。

波动用篮子周收益（相邻 FACE 日历周复合），σ = std(ddof=1)×√52。主簿回看 60 根已完成周（不足则该袖当周不可投）；对角逆波动归一。缺袖在其余可投袖上重归一。之后套 TV25：L = min(1, 0.25 / max(σ20, σ60))，σ 为乘 L 之前满仓袖子组合日收益的年化标准差。名字权重 = L × w_s / n_s。成本打在乘 L 之后的名字权重：cost = Σ|Δw| × 0.002 / 2。

邻档只跑四本：RP-IV20（20 周、最少 12）；RP-IV60-CAP40（单袖 40% 帽，残差留现金）；RP-ERC60（60 周等风险贡献，岭 1e-8，最多 500 步，失败回退逆波动）；RP-IV60-EQONLY（去掉 CMD）。

四闸相对当次重放 FACE：G1 Δret ≥ Δ|MDD|；G2 Calmar ≥ FACE；G3 日频 Sharpe ≥ FACE；G4 2023–26 累计收益 ≥ FACE 且为正。主簿四闸都过且单袖均权 >70% 时，须 CAP40 也过 G1+G3，否则证伪「结果来自单袖低波」。记正不换冠。

## 2. 实现要点

- 唯一被测机制：袖子篮子对角逆波动（不是个股 INVVOL-WEIGHT，不重开）。
- 袖子核对：可投 {cov['n_investable']}，EQ {cov['n_EQ']} / SEC {cov['n_SEC']} / CMD {cov['n_CMD']}，商品代码 {cov['cmd_codes']}。
- 日历：{cov['sample_start']} → {cov['sample_end']}，信号周 {cov['n_weeks']}，日频 {cov['n_days']}。
- 价格：本机 `research_cache/sina_daily` 既有日频，缺 {cov['n_price_missing']} 只；未用 yfinance。上市日：{cov['listing_source']}。
- FACE：读延窗已发布净值 `nav_LIVE1430-B45-S20.csv`，日收益第一根按 nav0−1 对齐 ret=nav_end−1。引擎一手换手用官方持仓 + 同公式 TV25 复算。
- 锚偏差：Δret={summary['anchor']['d_ret_pp']:+.2f}pp，Δ|MDD|={summary['anchor']['d_mdd_pp']:+.2f}pp，ΔSharpe={summary['anchor']['d_sharpe']:+.3f}，引擎一手换手={summary['anchor']['engine_to']:.3f}（名单等权={summary['anchor']['ew_to']:.3f}）。
- 各袖首个可投周五：EQ {summary['first_ok']['EQ']} / SEC {summary['first_ok']['SEC']} / CMD {summary['first_ok']['CMD']}。
- 缺袖周占比：EQ {pct(summary['sleeve_missing_week_pct']['EQ'])} / SEC {pct(summary['sleeve_missing_week_pct']['SEC'])} / CMD {pct(summary['sleeve_missing_week_pct']['CMD'])}。
- ERC 回退周：{summary['erc_fallback_weeks']}。

## 3. 主表

{table}

邻档四闸（不改判词）：
{notes}

主簿相对 FACE：Δret={g['d_ret']*100:+.1f}pp，Δ|MDD|={g['d_mdd']*100:+.1f}pp，ΔSharpe={g['d_sharpe']:+.2f}，ΔCalmar={g['d_calmar']:+.2f}，Δ2023–26={g['d_ret_2023']*100:+.1f}pp，Δ一手换手={g['d_to']:+.3f}。
G1 {g['G1']} / G2 {g['G2']} / G3 {g['G3']} / G4 {g['G4']}。单袖最大均权 {num(main.max_sleeve_avg_w)}。

## 4. 一句判词

{sentence}

红线：未改 strategy_exec / LIVE_OPS / 冠军主钉 / 实盘池 / 固收+ / 红利袖。champion_swap=false。判词={verdict}。
"""


def main() -> int:
    OUT.mkdir(parents=True, exist_ok=True)
    blocked_reasons: list[str] = []
    ro = ensure_readonly()
    uni_path = find_universe()
    cal_path = find_face_calendar()
    if cal_path is None:
        blocked_reasons.append("缺少 holdings_ro2_extended 日历")

    uni = pd.read_csv(uni_path)
    uni["code"] = uni["code"].astype(str).str.zfill(6)
    inv = uni[uni["aum"] >= 2].copy()
    try:
        inv["sleeve"] = [sleeve_of(str(r.l0), str(r.family)) for r in inv.itertuples()]
    except ValueError as e:
        (OUT / "REPORT.md").write_text(f"# REPORT · BLOCKED\n\n袖子映射失败：{e}\n", encoding="utf-8")
        print(f"BLOCKED sleeve map: {e}", flush=True)
        return 1

    n_eq = int((inv.sleeve == "EQ").sum())
    n_sec = int((inv.sleeve == "SEC").sum())
    n_cmd = int((inv.sleeve == "CMD").sum())
    cmd_set = set(inv.loc[inv.sleeve == "CMD", "code"])
    ok_split = len(inv) == 324 and n_eq == 59 and n_sec == 260 and n_cmd == 5 and cmd_set == CMD_CODES
    if not ok_split:
        msg = (
            f"袖子划分失败 investable={len(inv)} EQ={n_eq} SEC={n_sec} "
            f"CMD={n_cmd} codes={sorted(cmd_set)}"
        )
        (OUT / "REPORT.md").write_text(f"# REPORT · BLOCKED\n\n{msg}\n", encoding="utf-8")
        print(f"BLOCKED {msg}", flush=True)
        return 1

    sleeve_map = inv[["code", "name", "l0", "family", "aum", "sleeve"]].copy()
    sleeve_map.to_csv(OUT / "sleeve_map.csv", index=False, encoding="utf-8-sig")

    listing = load_listing(ro["listing"])
    listing_source = "listing.json ipo_bs" if listing else "第一根可用价格日"
    print(f"load prices {len(inv)} codes…", flush=True)
    px, n_miss = load_prices(inv["code"].tolist())
    if px.empty:
        blocked_reasons.append("价格缓存为空")
    R = px.pct_change()
    days = px.index[(px.index >= "2016-01-01") & (px.index <= END_S)]
    px = px.reindex(days)
    R = R.reindex(days)

    if cal_path is not None:
        cal = pd.read_csv(cal_path)
        cal["date"] = pd.to_datetime(cal["date"].astype(str).str[:10])
        grid = sorted(cal["date"].unique().tolist())
    else:
        grid = []
    grid = [pd.Timestamp(d) for d in grid if pd.Timestamp(d) <= pd.Timestamp(END_S)]

    hold_df = pd.read_csv(ro["hold"])
    hold_df["date"] = pd.to_datetime(hold_df["date"].astype(str).str[:10])
    reb = list(sorted(hold_df["date"].tolist()))

    print(
        f"calendar reb {reb[0].date() if reb else None} → {reb[-1].date() if reb else None} n={len(reb)}",
        flush=True,
    )
    print("FACE from published nav…", flush=True)
    eval_days = days[(days >= EVAL_START) & (days <= END_S)]
    face_pack = face_from_published(ro["nav"], ro["hold"], eval_days, R)
    face_row = row_metrics("FACE", face_pack, {"max_sleeve_avg_w": float("nan"), "erc_fallback_weeks": 0})

    d_ret_pp = (face_row["ret"] - ANCHOR_RET) * 100
    d_mdd_pp = (abs(face_row["maxDD"]) - ANCHOR_MDD) * 100
    d_sh = face_row["Sharpe"] - ANCHOR_SHARPE
    engine_to = face_pack["avgTO"]
    if abs(face_row["ret"] - ANCHOR_RET) > 0.020:
        blocked_reasons.append(f"FACE ret {face_row['ret']:.4f} 对不齐锚 131.6%")
    if abs(abs(face_row["maxDD"]) - ANCHOR_MDD) > 0.010:
        blocked_reasons.append(f"FACE |MDD| {abs(face_row['maxDD']):.4f} 对不齐锚 18.8%")
    if abs(d_sh) > 0.03:
        blocked_reasons.append(f"FACE Sharpe {face_row['Sharpe']:.3f} 对不齐锚 0.82")
    if not (FACE_TO_LO <= engine_to <= FACE_TO_HI):
        blocked_reasons.append(f"FACE 引擎一手换手 {engine_to:.3f} 落在 0.10–0.40 外")
    if px.empty or not reb:
        blocked_reasons.append("输入缓存缺失")

    by_sleeve = {s: inv[inv.sleeve == s].copy() for s in SLEEVES}
    packs: dict[str, dict[str, Any]] = {"FACE": face_pack}
    rows = [face_row]
    yearly: list[dict[str, Any]] = yearly_rows("FACE", face_pack["r"])

    for book in BOOKS[1:]:
        print(f"simulate {book}…", flush=True)
        pack = simulate_rp(book, grid, reb, days, R, px, by_sleeve, listing)
        packs[book] = pack
        rows.append(row_metrics(book, pack))
        yearly.extend(yearly_rows(book, pack["r"]))
        pd.DataFrame({"date": pack["nav"].index.strftime("%Y-%m-%d"), "nav": pack["nav"].values}).to_csv(
            OUT / f"nav_{book}.csv", index=False
        )
        pd.DataFrame(pack["weight_rows"]).to_csv(OUT / f"weights_{book}.csv", index=False)
        pd.DataFrame(pack["holding_rows"]).to_csv(OUT / f"holdings_{book}.csv", index=False)

    fnav = (1.0 + face_pack["r"]).cumprod()
    pd.DataFrame({"date": fnav.index.strftime("%Y-%m-%d"), "nav": fnav.values}).to_csv(
        OUT / "nav_FACE.csv", index=False
    )

    metrics = pd.DataFrame(rows)
    metrics.to_csv(OUT / "metrics.csv", index=False)
    metrics.to_csv(OUT / "table.csv", index=False)
    pd.DataFrame(yearly).to_csv(OUT / "yearly.csv", index=False)

    face_m = metrics[metrics.book == "FACE"].iloc[0].to_dict()
    main_m = metrics[metrics.book == "RP-IV60"].iloc[0].to_dict()
    cap_m = metrics[metrics.book == "RP-IV60-CAP40"].iloc[0].to_dict()
    g_main = gates(main_m, face_m)
    neighbor_notes = []
    for b in BOOKS[1:]:
        gm = gates(metrics[metrics.book == b].iloc[0].to_dict(), face_m)
        flags = ",".join(k for k in ("G1", "G2", "G3", "G4") if gm[k]) or "无"
        miss = ",".join(k for k in ("G1", "G2", "G3", "G4") if not gm[k]) or "—"
        neighbor_notes.append(f"{b} 过 {flags}；未过 {miss}")

    conc = float(main_m["max_sleeve_avg_w"])
    cap_g = gates(cap_m, face_m)
    four = all(g_main[k] for k in ("G1", "G2", "G3", "G4"))
    if blocked_reasons:
        verdict = "BLOCKED"
        sentence = (
            "BLOCKED（不换冠）："
            + "；".join(blocked_reasons)
            + "。不许拿漂移后的对照给风险平价记账。"
        )
    elif four and conc > 0.70 and not (cap_g["G1"] and cap_g["G3"]):
        verdict = "证伪"
        sentence = (
            f"证伪（不换冠）：RP-IV60 四闸全过但结果来自单袖低波"
            f"（单袖均权 {conc:.1%}，CAP40 G1={cap_g['G1']} G3={cap_g['G3']}）。"
            f"G1 Δret={g_main['d_ret']*100:+.1f}pp vs Δ|MDD|={g_main['d_mdd']*100:+.1f}pp；"
            f"G2 Calmar {main_m['Calmar']:.2f} vs {face_m['Calmar']:.2f}；"
            f"G3 Sharpe {main_m['Sharpe']:.2f} vs {face_m['Sharpe']:.2f}；"
            f"G4 2023–26 {pct(main_m['ret_2023_26'])} vs {pct(face_m['ret_2023_26'])}。"
            "邻档即使全过也不升格。"
        )
    elif four:
        verdict = "记正"
        sentence = (
            f"记正（不换冠）：RP-IV60 四闸全过。"
            f"Δret={g_main['d_ret']*100:+.1f}pp，Δ|MDD|={g_main['d_mdd']*100:+.1f}pp，"
            f"ΔSharpe={g_main['d_sharpe']:+.2f}，ΔCalmar={g_main['d_calmar']:+.2f}，"
            f"Δ2023–26={g_main['d_ret_2023']*100:+.1f}pp，Δ一手换手={g_main['d_to']:+.3f}。"
            "邻档只旁注。"
        )
    else:
        verdict = "证伪"
        failed = ",".join(k for k in ("G1", "G2", "G3", "G4") if not g_main[k])
        sentence = (
            f"证伪（不换冠）：RP-IV60 未过闸 {failed}。"
            f"G1 Δret={g_main['d_ret']*100:+.1f}pp vs Δ|MDD|={g_main['d_mdd']*100:+.1f}pp（{g_main['G1']}）；"
            f"G2 Calmar {main_m['Calmar']:.2f} vs {face_m['Calmar']:.2f}（{g_main['G2']}）；"
            f"G3 Sharpe {main_m['Sharpe']:.2f} vs {face_m['Sharpe']:.2f}（{g_main['G3']}）；"
            f"G4 2023–26 {pct(main_m['ret_2023_26'])} vs {pct(face_m['ret_2023_26'])}（{g_main['G4']}）。"
            "邻档即使全过也不升格。"
        )

    first_ok = packs["RP-IV60"]["first_ok"]
    miss_pct = packs["RP-IV60"]["sleeve_missing_week_pct"]
    summary = {
        "batch": "RP-SLEEVE-IV60",
        "champion_swap": False,
        "crown": "NO",
        "sample": [EVAL_START, END_S],
        "verdict": verdict,
        "verdict_sentence": sentence,
        "gates": {k: (bool(v) if isinstance(v, (bool, np.bool_)) else v) for k, v in g_main.items()},
        "cap40_gates": {
            k: (bool(v) if isinstance(v, (bool, np.bool_)) else v)
            for k, v in cap_g.items()
            if k.startswith("G")
        },
        "concentration_block": bool(four and conc > 0.70 and not (cap_g["G1"] and cap_g["G3"])),
        "anchor": {
            "ret": face_row["ret"],
            "maxDD": face_row["maxDD"],
            "Sharpe": face_row["Sharpe"],
            "d_ret_pp": d_ret_pp,
            "d_mdd_pp": d_mdd_pp,
            "d_sharpe": d_sh,
            "engine_to": engine_to,
            "ew_to": face_pack["ewTO"],
            "pass": not blocked_reasons,
        },
        "first_ok": first_ok,
        "sleeve_missing_week_pct": miss_pct,
        "erc_fallback_weeks": int(packs["RP-ERC60"]["erc_fallback_weeks"]),
        "coverage": {
            "n_investable": int(len(inv)),
            "n_EQ": n_eq,
            "n_SEC": n_sec,
            "n_CMD": n_cmd,
            "cmd_codes": sorted(cmd_set),
            "sample_start": EVAL_START,
            "sample_end": END_S,
            "n_weeks": int(len(reb)),
            "n_days": int(len(eval_days)),
            "n_price_missing": int(n_miss),
            "listing_source": listing_source,
        },
        "books": metrics.to_dict(orient="records"),
        "blocked_reasons": blocked_reasons,
    }
    (OUT / "summary.json").write_text(
        json.dumps(summary, ensure_ascii=False, indent=2, default=float), encoding="utf-8"
    )
    report = write_report(metrics, summary, neighbor_notes)
    (OUT / "REPORT.md").write_text(report, encoding="utf-8")
    (HERE / "criterion.md").write_text(
        "# Criterion · RP-SLEEVE-IV60\n\n"
        "见同目录 `DESIGN.md` 第 2–4 节（规则 / 邻档 / 四闸）。\n"
        "实施按 `COMPOSER.md`。本卡记正不换冠。\n",
        encoding="utf-8",
    )

    fig, ax = plt.subplots(figsize=(10, 5))
    for name, lw, style, color in (
        ("FACE", 1.6, "-", "#444444"),
        ("RP-IV60", 2.0, "-", "#ff6a39"),
        ("RP-ERC60", 1.4, "--", "#1f77b4"),
    ):
        nav = packs[name]["nav"] if name != "FACE" else fnav
        ax.plot(nav.index, nav.values, style, lw=lw, color=color, label=name)
    ax.set_title("RP-SLEEVE-IV60 vs FACE LIVE1430-B45-S20")
    ax.set_ylabel("NAV")
    ax.legend()
    ax.grid(True, alpha=0.3)
    fig.tight_layout()
    fig.savefig(OUT / "equity_curve.png", dpi=140)
    plt.close(fig)

    print(sentence, flush=True)
    print(f"wrote {OUT}", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
