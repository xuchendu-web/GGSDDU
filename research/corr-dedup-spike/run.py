#!/usr/bin/env python3
"""corr-dedup-spike: B45 spike_ft max5 + E0 + TV25 + SHARPE20; 60w Pearson seat dedup.

Four books: F0 (off) + DEDUP-R85 / R75 / R90. Engine pin 05f0f8a4 (btheta LIVE1430).
Research only — champion_swap=false, crown=NO.
"""
from __future__ import annotations

import json
import math
import re
import sys
import time
from collections import Counter, defaultdict
from concurrent.futures import ThreadPoolExecutor, as_completed
from copy import deepcopy
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parent
KIT = ROOT.parent / "cloud_batch" / "CLOUD-BATCH-2026-10-26"
SCRIPTS = KIT / "scripts"
sys.path.insert(0, str(SCRIPTS))

from backtest import KEEP, LIVE_PHASE, MIN_BARS, Position, nearest_date, snap_index  # noqa: E402
from build_scan import Bar, classify  # noqa: E402

OUT = ROOT / "out"
CACHE = KIT / "data" / "research_cache"
UNI_CSV = KIT / "data" / "universe_replace_only_436.csv"
WEEK = CACHE / "week"
FACE = CACHE / "holdings_ro2_extended.csv"
DAY_DIR = CACHE / "day"
TEMA_PX = Path("/workspace/tema_etf_scan_2018/prices_daily")
NOON_CSV = CACHE / "fri_1430_through_20261023.csv"
SINA_DAILY = CACHE / "sina_daily"
CLASSIFY_FROM = "2019-07-01"
SNAP_CACHE = KIT / "data" / "cache_1430_snaps.json"
SOURCE_SHA = "05f0f8a4f778fde886f3e7b2976646ff4b7d777b"
BREADTH_THETA = 0.45
ANCHOR = {"ret": 1.316, "maxDD": -0.188, "Calmar": 0.70, "n_weeks": 349, "T": 348, "n_codes": 324}
ANCH_TOL = {"ret": 0.005, "maxDD": 0.002, "Calmar": 0.02}
LOOKBACK_WEEKS = 60
MIN_OVERLAP = 40
PRIMARY_RHO = 0.85

BOOK_SPECS = [
    {"id": "F0", "book": "LIVE1430-DEDUP-off-B45-TV25", "rho_star": None},
    {"id": "DEDUP-R85", "book": "LIVE1430-DEDUP-R85-B45-TV25", "rho_star": 0.85},
    {"id": "DEDUP-R75", "book": "LIVE1430-DEDUP-R75-B45-TV25", "rho_star": 0.75},
    {"id": "DEDUP-R90", "book": "LIVE1430-DEDUP-R90-B45-TV25", "rho_star": 0.90},
]

EVAL_START = "2020-01-03"
END_S = "2026-10-23"
COST_SIDE = 0.001
SIGMA_STAR = 0.25
LCAP = 1.0
LIVE_COST_RT = 0.002
CLASSIFY_WORKERS = 8

SKIP_PATHS = [
    Path("research/research-kb/CORR-R3.md"),
    Path("etf-correlation/data/research_pool_v2.csv"),
    Path("charts/chart_corr_heatmap.png"),
]


@dataclass
class Cand:
    code: str
    px: float
    fz: float | None
    aum: float
    sharpe: float | None


def is_spike(snap: dict[str, Any] | None) -> bool:
    if not snap:
        return False
    if snap.get("pending_second_week") or snap.get("in_play_kind") == "box_pending":
        return False
    return bool(snap.get("in_play")) and snap.get("in_play_kind") == "spike_ft"


def sharpe_key(c: Cand, pool: list[Cand]) -> tuple:
    miss = 0 if c.sharpe is not None else 1
    return (miss, -(c.sharpe if c.sharpe is not None else 0.0), c.code)


def weekly_returns(closes: pd.Series, fridays: list[pd.Timestamp]) -> pd.Series:
    px = []
    for fri in fridays:
        sub = closes.loc[:fri]
        px.append(float(sub.iloc[-1]) if len(sub) else float("nan"))
    p = pd.Series(px, index=pd.DatetimeIndex(fridays), dtype=float)
    return p.pct_change()


def pearson_60w(
    r_i: pd.Series,
    r_j: pd.Series,
    t: pd.Timestamp,
    lookback: int = LOOKBACK_WEEKS,
    min_overlap: int = MIN_OVERLAP,
) -> float | None:
    prev = r_i.index[r_i.index < t]
    if len(prev) < 1:
        return None
    end = prev[-1]
    win_idx = r_i.index[r_i.index <= end][-lookback:]
    if len(win_idx) < lookback:
        return None
    a = r_i.reindex(win_idx)
    b = r_j.reindex(win_idx)
    pair = pd.concat([a, b], axis=1).dropna()
    if len(pair) < min_overlap:
        return None
    rho = float(pair.iloc[:, 0].corr(pair.iloc[:, 1], method="pearson"))
    if not np.isfinite(rho):
        return None
    return rho


def greedy_fill(
    incumbents: list[str],
    ranked: list[str],
    rho_of: Callable[[str, str], float | None],
    rho_star: float,
    max_pos: int = 5,
) -> tuple[list[str], int, int]:
    selected = list(incumbents)
    n_skip = 0
    n_na = 0
    for c in ranked:
        if len(selected) >= max_pos:
            break
        blocked = False
        for s in selected:
            rho = rho_of(c, s)
            if rho is None:
                n_na += 1
                continue
            if rho > rho_star:
                blocked = True
                break
        if blocked:
            n_skip += 1
            continue
        selected.append(c)
    return selected, n_skip, n_na


def run_fixtures() -> None:
    fri = pd.date_range("2018-01-05", periods=122, freq="W-FRI")
    px = pd.Series(np.exp(np.cumsum([0.01] * len(fri))), index=fri, dtype=float)
    r = px.pct_change().iloc[1:]
    r2 = r.copy()
    t = fri[-1]
    rho = pearson_60w(r, r2, t)
    assert rho is not None and 0.999999 <= rho <= 1.000001
    sel, sk, _ = greedy_fill([], ["A", "B"], lambda i, j: rho, 0.85, 5)
    assert sk == 1 and sel == ["A"]

    va = np.tile(np.array([1.0, -1.0] * 30), int(np.ceil(len(r) / 60)))[: len(r)]
    vb = np.tile(np.array([1.0, 1.0, -1.0, -1.0] * 15), int(np.ceil(len(r) / 60)))[: len(r)]
    ra = pd.Series(va * 0.01, index=r.index)
    rb = pd.Series(vb * 0.01, index=r.index)
    rho0 = pearson_60w(ra, rb, t)
    assert rho0 is not None and -1e-12 <= rho0 <= 1e-12
    for rs in (0.75, 0.85, 0.90):
        sel2, sk2, _ = greedy_fill([], ["X", "Y"], lambda i, j: rho0, rs, 5)
        assert sk2 == 0 and len(sel2) == 2

    rs = r.copy()
    rs.iloc[-22:] = np.nan
    rho_na = pearson_60w(r, rs, t)
    assert rho_na is None
    sel3, _, na3 = greedy_fill([], ["P", "Q"], lambda i, j: None, 0.85, 5)
    assert na3 >= 1 and len(sel3) == 2


def scan_inventory() -> dict[str, Any]:
    skipped: list[str] = []
    for p in SKIP_PATHS:
        full = Path(__file__).resolve().parents[2] / p if not p.is_absolute() else p
        alt = ROOT.parents[1] / p
        for fp in (full, alt, Path.cwd() / p):
            if fp.exists():
                skipped.append(str(p).replace("\\", "/"))
                break

    precomputed: list[Path] = []
    for base in (ROOT.parent, ROOT.parents[1]):
        if not base.exists():
            continue
        precomputed.extend(base.glob("**/corr*60w*"))
        precomputed.extend(base.glob("etf-correlation/**/*corr*"))

    corr_matrix_path = None
    corr_source = "missing"
    price_cache_path = ""
    pool_label_path = ""

    if precomputed:
        for fp in precomputed:
            if fp.suffix in {".csv", ".parquet", ".json", ".npy"} and "60" in fp.name.lower():
                corr_source = "precomputed"
                corr_matrix_path = str(fp)
                break

    day_ok = DAY_DIR.exists() and any(DAY_DIR.glob("*.json"))
    sina_ok = SINA_DAILY.exists() and any(SINA_DAILY.glob("*.csv"))
    if corr_source == "missing" and day_ok and sina_ok:
        corr_source = "computed_from_cache"
        price_cache_path = f"{DAY_DIR};{SINA_DAILY}"

    if UNI_CSV.exists():
        pool_label_path = str(UNI_CSV)
    else:
        rp2 = ROOT.parents[1] / "etf-correlation/data/research_pool_v2.csv"
        if rp2.exists():
            pool_label_path = str(rp2)

    return {
        "corr_source": corr_source,
        "corr_matrix_path": corr_matrix_path,
        "price_cache_path": price_cache_path,
        "pool_label_path": pool_label_path,
        "skipped": skipped,
    }


def write_blocked(inventory: dict[str, Any], reason: str) -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    design = ROOT / "DESIGN.md"
    headline = "请拍板：维持面层 B45 + spike_ft max5 + E0 + TV25 + SHARPE20，只在填席时对已入选名字做 60 周收益相关去重（主档 ρ*=0.85），无论记正与否都不换冠。"
    h1_block = ""
    if design.exists():
        m = re.search(r"## H1\s+```\n(.*?)```", design.read_text(encoding="utf-8"), re.S)
        if m:
            h1_block = m.group(1).strip()

    summary = {
        "batch": "corr-dedup-spike",
        "champion_swap": False,
        "crown": "NO",
        "source_sha": SOURCE_SHA,
        "sample": [EVAL_START, END_S],
        "anchor_pass": False,
        "anchor": ANCHOR,
        "face_id": "F0",
        "lookback_weeks": LOOKBACK_WEEKS,
        "min_overlap": MIN_OVERLAP,
        "primary_rho": PRIMARY_RHO,
        "inventory": inventory,
        "h1": "DEDUP-R85 证伪",
        "family_verdict": "BLOCKED",
        "positive_ids": [],
        "cells": [],
    }
    (OUT / "summary.json").write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
    report = f"""{headline}

```
{h1_block}
```

## 库存

- `corr_source` = **{inventory['corr_source']}**
- 原因：{reason}
- `skipped`：{inventory.get('skipped') or '[]'}

## 锚点门

库存未过 → `family_verdict=BLOCKED`，未跑四本书净值。

## 红线

不换冠；未新抓数。
"""
    (OUT / "REPORT.md").write_text(report, encoding="utf-8")


def load_daily_closes(
    codes: list[str], sina: dict[str, dict[str, float]] | None = None
) -> dict[str, pd.Series]:
    out: dict[str, pd.Series] = {}
    for c in codes:
        s = None
        ftema = TEMA_PX / f"{c}.csv"
        if TEMA_PX.exists() and ftema.exists():
            df = pd.read_csv(ftema, parse_dates=["Date"])
            s = df.set_index("Date")["Close"].astype(float).sort_index()
            s = s[~s.index.duplicated(keep="last")]
        fday = DAY_DIR / f"{c}.json"
        if fday.exists():
            j = json.loads(fday.read_text(encoding="utf-8"))
            bars = j.get("bars") if isinstance(j, dict) else j
            if bars:
                idx = pd.to_datetime([b["date"] for b in bars])
                px = pd.Series([float(b["c"]) for b in bars], index=idx, dtype=float)
                px = px[~px.index.duplicated(keep="last")].sort_index()
                s = px if s is None else px.combine_first(s).sort_index()
        if s is None and sina and c in sina and len(sina[c]) >= 10:
            idx = pd.to_datetime(sorted(sina[c]))
            s = pd.Series([sina[c][d.strftime("%Y-%m-%d")] for d in idx], index=idx, dtype=float)
        if s is not None and len(s) >= 10:
            out[c] = s
    return out


def qfq_close_on(
    code: str,
    td: str,
    daily: dict[str, pd.Series],
    closes_w: dict[str, dict[str, float]],
) -> float | None:
    if code in daily:
        ser = daily[code]
        ts = pd.Timestamp(td)
        if ts in ser.index:
            return float(ser.loc[ts])
        sub = ser.loc[:ts]
        if len(sub) and (ts - sub.index[-1]).days <= 3:
            return float(sub.iloc[-1])
    wc = closes_w.get(code) or {}
    if td in wc:
        return float(wc[td])
    ds = sorted(wc)
    if ds:
        hit = nearest_date(td, ds, 3)
        if hit:
            return float(wc[hit])
    return None


def load_sina_closes(codes: list[str]) -> dict[str, dict[str, float]]:
    out: dict[str, dict[str, float]] = {}
    for c in codes:
        fp = SINA_DAILY / f"{c}.csv"
        if not fp.exists():
            continue
        df = pd.read_csv(fp)
        if "date" not in df.columns or "close" not in df.columns:
            continue
        out[c] = {
            str(r.date)[:10]: float(r.close)
            for r in df.itertuples()
            if r.close and float(r.close) > 0
        }
    return out


def sharpe_n_on(closes: pd.Series, d: str, n: int) -> float | None:
    ts = pd.Timestamp(d)
    sub = closes.loc[: ts - pd.Timedelta(days=1)]
    if len(sub) < n + 1:
        return None
    if (ts - sub.index[-1]).days > 5:
        return None
    window = sub.iloc[-(n + 1) :]
    rets = window.pct_change().dropna()
    if len(rets) < n:
        return None
    rets = rets.iloc[-n:]
    sigma = float(rets.std(ddof=1)) if len(rets) > 1 else 0.0
    if sigma <= 0 or not np.isfinite(sigma):
        return None
    mu = float(rets.mean())
    if not np.isfinite(mu):
        return None
    return mu / sigma * np.sqrt(252)


def simulate(
    calendar: list[str],
    fridays: list[pd.Timestamp],
    snaps: dict[str, dict[str, dict[str, Any]]],
    closes_w: dict[str, dict[str, float]],
    alias: dict[str, dict[str, str]],
    aum: dict[str, float],
    daily: dict[str, pd.Series],
    weekly_rets: dict[str, pd.Series],
    family_of: dict[str, str],
    risk_on_by_fri: dict[str, bool],
    variant: str,
    rho_star: float | None,
    max_pos: int = 5,
) -> tuple[list[dict[str, Any]], dict[str, list[str]], dict[str, Any]]:
    cash = 1.0
    positions: dict[str, Position] = {}
    trades: list[dict[str, Any]] = []
    picks: dict[str, list[str]] = {}
    n_tight = 0
    n_feat = 0
    n_entries = 0
    n_dedup_skip = 0
    n_corr_na = 0
    n_incumbent_over_rho = 0
    sel_sizes: list[int] = []
    max_pair_corrs: list[float] = []
    max_families: list[float] = []
    skip_rows: list[dict[str, Any]] = []

    def px_on(code: str, d: str) -> float | None:
        return closes_w.get(code, {}).get((alias.get(code) or {}).get(d) or d)

    def snap_at(code: str, d: str) -> dict[str, Any] | None:
        key = (alias.get(code) or {}).get(d) or d
        return snaps.get(code, {}).get(key)

    def equity_now() -> float:
        return cash + sum(p.shares * p.last_px for p in positions.values())

    def build_cands(d: str, skip: set[str]) -> list[Cand]:
        out: list[Cand] = []
        for code in snaps:
            if code in skip:
                continue
            sn = snap_at(code, d)
            if not is_spike(sn):
                continue
            px = px_on(code, d)
            if px is None or px <= 0:
                continue
            sh = sharpe_n_on(daily[code], d, 20) if code in daily else None
            fz = sn.get("falsify_close") if sn else None
            out.append(
                Cand(
                    code=code,
                    px=px,
                    fz=float(fz) if fz is not None else None,
                    aum=aum.get(code) or 0.0,
                    sharpe=sh,
                )
            )
        return out

    def rho_of(i: str, j: str, t: pd.Timestamp) -> float | None:
        ri = weekly_rets.get(i)
        rj = weekly_rets.get(j)
        if ri is None or rj is None:
            return None
        return pearson_60w(ri, rj, t)

    def max_pair_rho(codes: list[str], t: pd.Timestamp) -> float | None:
        best = None
        for a in range(len(codes)):
            for b in range(a + 1, len(codes)):
                rho = rho_of(codes[a], codes[b], t)
                if rho is None or not np.isfinite(rho):
                    continue
                best = rho if best is None else max(best, rho)
        return best

    last_i = len(calendar) - 1
    for i, d in enumerate(calendar):
        for p in positions.values():
            px = px_on(p.code, d)
            if px is not None:
                p.last_px = px

        last_bar = i == last_i
        risk_on = False if last_bar else bool(risk_on_by_fri.get(d, False))
        t_fri = pd.Timestamp(d)

        exiting: list[tuple[str, str, float]] = []
        for code, p in list(positions.items()):
            px = px_on(code, d)
            if last_bar:
                exiting.append((code, "eod_eval", px if px is not None else p.last_px))
                continue
            if not risk_on:
                exiting.append((code, "breadth_off", px if px is not None else p.last_px))
                continue
            if px is None:
                continue
            reason = None
            sn = snap_at(code, d)
            if sn:
                fz = sn.get("falsify_close")
                if fz is not None and px < float(fz):
                    reason = "falsify"
                elif sn.get("always_in") != "Long":
                    reason = "always_in_flip"
                elif (not sn.get("in_play")) and sn.get("phase") not in LIVE_PHASE:
                    reason = "left_structure"
            if reason:
                exiting.append((code, reason, px))
            else:
                p.weeks += 1

        for code, reason, px in exiting:
            p = positions.pop(code)
            cash += p.shares * px * (1.0 - COST_SIDE)
            trades.append(
                {
                    "variant": variant,
                    "code": code,
                    "entry_date": p.entry_date,
                    "exit_date": d,
                    "exit_reason": reason,
                    "weeks_held": p.weeks + 1,
                }
            )

        take: list[Cand] = []
        if not last_bar and risk_on:
            pool = build_cands(d, set(positions))
            slots = max_pos - len(positions)
            if pool:
                n_feat += 1
            if slots > 0 and len(pool) > slots:
                n_tight += 1
            if slots > 0 and pool:
                pool_rank_list = [c for c in pool if c.sharpe is not None]
                pool_rank = sorted(pool_rank_list, key=lambda c: sharpe_key(c, pool_rank_list))
                if rho_star is None:
                    take = pool_rank[:slots]
                else:
                    incumbents = [code for code in positions if is_spike(snap_at(code, d))]
                    if rho_star is not None and len(incumbents) >= 2:
                        over = False
                        for a in range(len(incumbents)):
                            for b in range(a + 1, len(incumbents)):
                                rho = rho_of(incumbents[a], incumbents[b], t_fri)
                                if rho is not None and rho > rho_star:
                                    over = True
                                    break
                            if over:
                                break
                        if over:
                            n_incumbent_over_rho += 1

                    selected_codes = list(incumbents)
                    for c in pool_rank:
                        if len(take) >= slots:
                            break
                        if len(selected_codes) >= max_pos:
                            break
                        blocked = False
                        for s in selected_codes:
                            rho = rho_of(c.code, s, t_fri)
                            if rho is None:
                                n_corr_na += 1
                                continue
                            if rho > rho_star:
                                blocked = True
                                break
                        if blocked:
                            n_dedup_skip += 1
                            skip_rows.append({"date": d, "code": c.code, "variant": variant})
                            continue
                        take.append(c)
                        selected_codes.append(c.code)

                for c in take:
                    n_entries += 1

        picks[d] = [c.code for c in take]

        if take:
            eq = equity_now()
            n_after = len(positions) + len(take)
            if n_after > max_pos:
                raise SystemExit(f"overflow {variant} {d} n={n_after}")
            target = eq / n_after if n_after else 0.0
            for p in positions.values():
                if p.last_px > 0:
                    p.shares = target / p.last_px
            for c in take:
                positions[c.code] = Position(
                    code=c.code,
                    kind="spike_ft",
                    entry_date=d,
                    entry_px=c.px,
                    entry_falsify=c.fz,
                    shares=(target * (1.0 - COST_SIDE)) / c.px,
                    last_px=c.px,
                    weeks=0,
                )
            cash = 0.0
        elif positions:
            eq = equity_now()
            target = eq / len(positions)
            for p in positions.values():
                if p.last_px > 0:
                    p.shares = target / p.last_px
            cash = 0.0
        else:
            cash = equity_now()

        if not last_bar:
            held = sorted(positions.keys())
            sel_sizes.append(len(held))
            if len(held) >= 2 and rho_star is not None:
                mp = max_pair_rho(held, t_fri)
                if mp is not None:
                    max_pair_corrs.append(mp)
            elif len(held) >= 2 and rho_star is None:
                mp = max_pair_rho(held, t_fri)
                if mp is not None:
                    max_pair_corrs.append(mp)
            if held:
                fam_ct = Counter(family_of.get(c, "unknown") for c in held)
                max_families.append(float(max(fam_ct.values())))

    hold: dict[str, list[str]] = {d: [] for d in calendar}
    open_codes: set[str] = set()
    exits_by_day: dict[str, list[str]] = {}
    for t in trades:
        exits_by_day.setdefault(t["exit_date"], []).append(t["code"])
    for d in calendar:
        for code in exits_by_day.get(d, []):
            open_codes.discard(code)
        for code in picks.get(d, []):
            open_codes.add(code)
        hold[d] = sorted(open_codes)

    n_cash = sum(1 for d in calendar[:-1] if not (hold.get(d) or []))
    stats = {
        "n_fridays_queue_gt_seats": n_tight,
        "n_fridays_with_cands": n_feat,
        "n_entries": n_entries,
        "n_trades": len(trades),
        "max_pos": max_pos,
        "n_cash_weeks": n_cash,
        "n_dedup_skip": n_dedup_skip,
        "n_corr_na": n_corr_na,
        "n_incumbent_over_rho": n_incumbent_over_rho,
        "avg_selected": float(np.mean(sel_sizes)) if sel_sizes else 0.0,
        "avg_max_pair_corr": float(np.mean(max_pair_corrs)) if max_pair_corrs else float("nan"),
        "avg_max_family": float(np.mean(max_families)) if max_families else float("nan"),
    }
    if skip_rows:
        pd.DataFrame(skip_rows).to_csv(OUT / f"skips_{variant.replace('/', '_')}.csv", index=False)
    return trades, hold, stats


def run_live_tv(
    hold: dict[pd.Timestamp, list[str]], days: pd.DatetimeIndex, px: pd.DataFrame, R: pd.DataFrame
) -> tuple[pd.Series, pd.Series, float]:
    reb = sorted(hold)
    rp = pd.Series(0.0, index=days)
    Ls = pd.Series(0.0, index=days)
    prev: dict[str, float] = {}
    cst = pd.Series(0.0, index=days)
    R2 = R.reindex(days)
    to_sum = 0.0
    to_n = 0

    for i, d in enumerate(reb):
        cs = [c for c in hold[d] if c in px.columns]
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
                s20 = past.iloc[-20:].std() * np.sqrt(252)
                s60 = past.iloc[-60:].std() * np.sqrt(252)
                sh = np.nanmax([s20, s60])
                L = float(min(LCAP, SIGMA_STAR / sh)) if sh and sh > 0 else 1.0
        wt = {c: L * v for c, v in w.items()}
        to = sum(abs(wt.get(k, 0) - prev.get(k, 0)) for k in set(wt) | set(prev))
        to_sum += to
        to_n += 1
        prev = wt
        if d in cst.index:
            cst.loc[d] = to * LIVE_COST_RT / 2
        if w and len(seg):
            rp.loc[seg] = (R2.loc[seg, list(w)].fillna(0) @ pd.Series(w)).values
            Ls.loc[seg] = L
    r = rp * Ls - cst
    avg_to = (to_sum / to_n / 2.0) if to_n else 0.0
    return r, Ls, avg_to


def stats_full(s: pd.Series) -> dict[str, float]:
    if s is None or len(s) < 2:
        return {"ret": float("nan"), "maxDD": float("nan"), "CAGR": float("nan"), "Calmar": float("nan")}
    q = (1 + s).cumprod()
    ret = float(q.iloc[-1] - 1)
    dd = float((q / q.cummax().clip(lower=1e-12) - 1).min())
    n = (s.index[-1] - s.index[0]).days
    cagr = (1 + ret) ** (365.25 / n) - 1 if n > 0 and (1 + ret) > 0 else float("nan")
    cal = cagr / abs(dd) if dd < 0 else float("nan")
    return {"ret": ret, "maxDD": dd, "CAGR": cagr, "Calmar": cal}


def pct(x: float | None) -> str:
    if x is None or (isinstance(x, float) and (math.isnan(x) or math.isinf(x))):
        return "—"
    return f"{100 * x:.1f}%"


def check_anchor(st: dict[str, float], n_weeks: int, T: int, n_codes: int, end_s: str) -> bool:
    if end_s != END_S:
        return False
    if n_weeks != ANCHOR["n_weeks"]:
        return False
    if T != ANCHOR["T"]:
        return False
    if n_codes != ANCHOR["n_codes"]:
        return False
    if abs(st["ret"] - ANCHOR["ret"]) > ANCH_TOL["ret"]:
        return False
    if abs(st["maxDD"] - ANCHOR["maxDD"]) > ANCH_TOL["maxDD"]:
        return False
    if abs(st["Calmar"] - ANCHOR["Calmar"]) > ANCH_TOL["Calmar"]:
        return False
    return True


def judge_cell(cell: dict[str, Any], f0: dict[str, Any]) -> None:
    if cell["id"] == "F0":
        cell["delta_ret"] = 0.0
        cell["delta_abs_mdd"] = 0.0
        cell["g1_covers"] = True
        cell["g2_2023_26"] = True
        cell["g3_2020_22"] = True
        cell["verdict"] = "ANCHOR"
        return
    dret = cell["ret"] - f0["ret"]
    d_abs = abs(cell["maxDD"]) - abs(f0["maxDD"])
    cell["delta_ret"] = dret
    cell["delta_abs_mdd"] = d_abs
    g1 = dret >= d_abs
    g3 = cell["w2020_22"]["ret"] >= f0["w2020_22"]["ret"]
    g2 = cell["w2023_26"]["ret"] >= f0["w2023_26"]["ret"]
    cell["g1_covers"] = g1
    cell["g2_2023_26"] = g2
    cell["g3_2020_22"] = g3
    if any(math.isnan(x) for x in (cell["ret"], cell["maxDD"], dret, d_abs)):
        cell["verdict"] = "证伪"
    elif g1 and g2 and g3:
        cell["verdict"] = "记正"
    else:
        cell["verdict"] = "证伪"


def main() -> None:
    run_fixtures()
    print("fixtures OK", flush=True)

    inventory = scan_inventory()
    print("inventory", inventory, flush=True)

    if inventory["corr_source"] == "missing":
        write_blocked(inventory, "CLOUD-BATCH day/sina 缓存不足，无法现场算 60 周 Pearson")
        raise SystemExit(2)

    OUT.mkdir(parents=True, exist_ok=True)
    t0 = time.time()
    for p in (WEEK, FACE, DAY_DIR, NOON_CSV, SINA_DAILY, SNAP_CACHE):
        if not Path(p).exists():
            write_blocked(inventory, f"missing kit path {p}")
            raise SystemExit(2)

    uni = pd.read_csv(UNI_CSV)
    uni["code"] = uni["code"].astype(str).str.zfill(6)
    uni = uni[uni["aum"] >= 2].copy()
    codes = uni["code"].tolist()
    aum = {r.code: float(r.aum or 0) for r in uni.itertuples()}
    family_of = {r.code: str(r.family) for r in uni.itertuples()}
    code_set = set(codes)

    noon = pd.read_csv(NOON_CSV)
    noon["code"] = noon["etf_code"].astype(str).str.split(".").str[0]
    noon["trade_date"] = noon["trade_date"].astype(str).str[:10]
    noon = noon[noon["code"].isin(code_set)].copy()
    if "price_1430" in noon.columns and "price_1130" not in noon.columns:
        noon["price_1130"] = noon["price_1430"]

    face = pd.read_csv(FACE)
    face["date"] = face["date"].astype(str).str[:10]
    face = face[(face["date"] >= EVAL_START) & (face["date"] <= END_S)].copy()
    calendar = sorted(face["date"].unique().tolist())
    fridays = [pd.Timestamp(d) for d in calendar]
    actual_end = calendar[-1]

    risk_on_by_fri: dict[str, bool] = {}
    for d in calendar:
        row = face[face["date"] == d].iloc[0]
        bv = row.get("b")
        risk_on_by_fri[d] = bool(bv is not None and not (isinstance(bv, float) and math.isnan(bv)) and float(bv) >= BREADTH_THETA)
    risk_on_by_fri[calendar[-1]] = False

    raws_w: dict[str, dict[str, Any]] = {}
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
        if ds:
            alias[c] = {d: hit for d in calendar if (hit := nearest_date(d, ds, 3))}

    sina = load_sina_closes(codes)
    daily = load_daily_closes(codes, sina)

    print("weekly returns for correlation…", flush=True)
    weekly_rets: dict[str, pd.Series] = {}
    for c in codes:
        if c in daily:
            weekly_rets[c] = weekly_returns(daily[c], fridays)

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
        q = qfq_close_on(r.code, td, daily, closes_w_close)
        b = (sina.get(r.code) or {}).get(td)
        if not q or not b or b <= 0:
            blocked_empty[td].add(r.code)
            continue
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
    snaps = {c: snap_index(by_rows.get(c) or []) for c in codes}

    hold_by: dict[str, dict[str, list[str]]] = {}
    sim_stats: dict[str, Any] = {}
    for spec in BOOK_SPECS:
        name = spec["book"]
        print(f"simulate {spec['id']}…", flush=True)
        trades, hold, st = simulate(
            calendar=calendar,
            fridays=fridays,
            snaps=snaps,
            closes_w=closes_w_sig,
            alias=alias,
            aum=aum,
            daily=daily,
            weekly_rets=weekly_rets,
            family_of=family_of,
            risk_on_by_fri=risk_on_by_fri,
            variant=name,
            rho_star=spec["rho_star"],
        )
        hold_by[name] = hold
        sim_stats[name] = st
        rows = []
        for d in calendar[:-1]:
            codes_h = hold.get(d) or []
            rows.append({"date": d, "risk_on": int(risk_on_by_fri.get(d, False)), "n_held": len(codes_h), "codes": ",".join(codes_h)})
        pd.DataFrame(rows).to_csv(OUT / f"holdings_{spec['id']}.csv", index=False)
        pd.DataFrame(trades).to_csv(OUT / f"trades_{spec['id']}.csv", index=False)

    all_codes: set[str] = set()
    for h in hold_by.values():
        for cs in h.values():
            all_codes |= set(cs)
    px_map = {c: daily[c] for c in sorted(all_codes) if c in daily}
    px = pd.DataFrame(px_map).sort_index()
    px = px.loc[(px.index >= EVAL_START) & (px.index <= END_S)]
    R = px.pct_change()
    days = px.dropna(how="all").index
    days = days[(days >= EVAL_START) & (days <= END_S)]

    cells: list[dict[str, Any]] = []
    series: dict[str, pd.Series] = {}
    for spec in BOOK_SPECS:
        name = spec["book"]
        hd = {pd.Timestamp(d): cs for d, cs in hold_by[name].items()}
        r, L, avg_to = run_live_tv(hd, days, px, R)
        series[name] = r
        st = stats_full(r)
        r2022 = r[(r.index >= "2020-01-01") & (r.index <= "2022-12-31")]
        r2023 = r[r.index >= "2023-01-01"]
        st2022 = stats_full(r2022) if len(r2022) > 5 else {k: float("nan") for k in st}
        st2023 = stats_full(r2023) if len(r2023) > 5 else {k: float("nan") for k in st}
        sim = sim_stats[name]
        cell = {
            "id": spec["id"],
            "book": name,
            "rho_star": spec["rho_star"],
            "ret": st["ret"],
            "maxDD": st["maxDD"],
            "CAGR": st["CAGR"],
            "Calmar": st["Calmar"],
            "avgL": float(L[L > 0].mean()) if (L > 0).any() else 0.0,
            "avg_turnover_1way": avg_to,
            "n_cash_weeks": sim["n_cash_weeks"],
            "avg_selected": sim["avg_selected"],
            "n_dedup_skip": sim["n_dedup_skip"],
            "n_corr_na": sim["n_corr_na"],
            "avg_max_pair_corr": sim["avg_max_pair_corr"],
            "avg_max_family": sim["avg_max_family"],
            "n_incumbent_over_rho": sim["n_incumbent_over_rho"],
            "w2020_22": {"ret": st2022["ret"], "maxDD": st2022["maxDD"], "Calmar": st2022["Calmar"]},
            "w2023_26": {"ret": st2023["ret"], "maxDD": st2023["maxDD"], "Calmar": st2023["Calmar"]},
        }
        cells.append(cell)
        print(f"  {spec['id']}: ret={pct(st['ret'])} dd={pct(st['maxDD'])} Calmar={st['Calmar']:.2f}", flush=True)

    f0_cell = next(c for c in cells if c["id"] == "F0")
    T = len(calendar) - 1
    anchor_pass = check_anchor(f0_cell, len(calendar), T, len(codes), actual_end)
    print(f"anchor_pass={anchor_pass}", flush=True)

    blocked_run = not anchor_pass or inventory["corr_source"] == "missing"
    for c in cells:
        if blocked_run:
            c["delta_ret"] = 0.0
            c["delta_abs_mdd"] = 0.0
            c["g1_covers"] = False
            c["g2_2023_26"] = False
            c["g3_2020_22"] = False
            c["verdict"] = "BLOCKED"
        else:
            judge_cell(c, f0_cell)

    primary = next(c for c in cells if c["id"] == "DEDUP-R85")
    positive_ids = ["DEDUP-R85"] if primary["verdict"] == "记正" else []
    if blocked_run:
        family_verdict = "BLOCKED"
    elif positive_ids:
        family_verdict = "H1_REJECT"
    else:
        family_verdict = "H1_HOLD"

    table_rows = []
    for c in cells:
        rs = c["rho_star"]
        table_rows.append(
            {
                "id": c["id"],
                "book": c["book"],
                "rho_star": "off" if rs is None else rs,
                "ret": c["ret"],
                "maxDD": c["maxDD"],
                "CAGR": c["CAGR"],
                "Calmar": c["Calmar"],
                "w2020_22_ret": c["w2020_22"]["ret"],
                "w2020_22_maxDD": c["w2020_22"]["maxDD"],
                "w2020_22_Calmar": c["w2020_22"]["Calmar"],
                "w2023_26_ret": c["w2023_26"]["ret"],
                "w2023_26_maxDD": c["w2023_26"]["maxDD"],
                "w2023_26_Calmar": c["w2023_26"]["Calmar"],
                "avgL": c["avgL"],
                "avg_turnover_1way": c["avg_turnover_1way"],
                "n_cash_weeks": c["n_cash_weeks"],
                "avg_selected": c["avg_selected"],
                "n_dedup_skip": c["n_dedup_skip"],
                "n_corr_na": c["n_corr_na"],
                "avg_max_pair_corr": c["avg_max_pair_corr"],
                "avg_max_family": c["avg_max_family"],
                "n_incumbent_over_rho": c["n_incumbent_over_rho"],
                "delta_ret": c["delta_ret"],
                "delta_abs_mdd": c["delta_abs_mdd"],
                "g1_covers": c["g1_covers"],
                "g2_2023_26": c["g2_2023_26"],
                "g3_2020_22": c["g3_2020_22"],
                "verdict": c["verdict"],
            }
        )
    pd.DataFrame(table_rows).to_csv(OUT / "table.csv", index=False)

    eq_long = []
    for spec in BOOK_SPECS:
        name = spec["book"]
        nav = (1 + series[name]).cumprod()
        for dt, nv in nav.items():
            eq_long.append({"date": dt.strftime("%Y-%m-%d"), "book": name, "nav": float(nv)})
    pd.DataFrame(eq_long).to_csv(OUT / "equity.csv", index=False)

    fig, ax = plt.subplots(figsize=(11, 5.5), dpi=120)
    f0_name = BOOK_SPECS[0]["book"]
    nav_f0 = (1 + series[f0_name]).cumprod()
    ax.plot(nav_f0.index, nav_f0.values, color="black", lw=2.2, label="F0")
    for spec in BOOK_SPECS[1:]:
        nav = (1 + series[spec["book"]]).cumprod()
        ax.plot(nav.index, nav.values, color="gray", lw=1.0, alpha=0.85, label=spec["id"])
    ax.set_yscale("log")
    ax.set_title("corr-dedup-spike（F0 黑线 vs 去重邻档）")
    ax.set_ylabel("净值（对数）")
    ax.grid(True, alpha=0.3)
    ax.legend(fontsize=8)
    fig.tight_layout()
    fig.savefig(OUT / "equity_curve.png")
    plt.close(fig)

    design = (ROOT / "DESIGN.md").read_text(encoding="utf-8")
    headline = "请拍板：维持面层 B45 + spike_ft max5 + E0 + TV25 + SHARPE20，只在填席时对已入选名字做 60 周收益相关去重（主档 ρ*=0.85），无论记正与否都不换冠。"
    h1_m = re.search(r"## H1\s+```\n(.*?)```", design, re.S)
    h1_block = h1_m.group(1).strip() if h1_m else ""

    summary = {
        "batch": "corr-dedup-spike",
        "champion_swap": False,
        "crown": "NO",
        "source_sha": SOURCE_SHA,
        "sample": [EVAL_START, actual_end],
        "anchor_pass": anchor_pass,
        "anchor": {**ANCHOR, "n_weeks": len(calendar), "T": T},
        "face_id": "F0",
        "lookback_weeks": LOOKBACK_WEEKS,
        "min_overlap": MIN_OVERLAP,
        "primary_rho": PRIMARY_RHO,
        "inventory": inventory,
        "h1": "DEDUP-R85 证伪" if family_verdict == "H1_HOLD" else ("DEDUP-R85 记正" if family_verdict == "H1_REJECT" else "BLOCKED"),
        "family_verdict": family_verdict,
        "positive_ids": positive_ids,
        "cells": cells,
        "elapsed_sec": round(time.time() - t0, 1),
    }
    (OUT / "summary.json").write_text(json.dumps(summary, ensure_ascii=False, indent=2, default=str), encoding="utf-8")

    def tbl(c: dict[str, Any]) -> str:
        rs = "off" if c["rho_star"] is None else str(c["rho_star"])
        return (
            f"| {c['id']} | {rs} | {pct(c['ret'])} | {pct(c['maxDD'])} | {c['Calmar']:.2f} | "
            f"{pct(c['w2020_22']['ret'])}/{pct(c['w2023_26']['ret'])} | "
            f"{c['n_dedup_skip']} | {c['avg_max_pair_corr']:.3f} | {c['avg_max_family']:.2f} | {c['verdict']} |"
        )

    anchor_note = (
        f"F0 ret={pct(f0_cell['ret'])} maxDD={pct(f0_cell['maxDD'])} Calmar={f0_cell['Calmar']:.2f} "
        f"（锚 131.6% / −18.8% / 0.70）→ {'通过' if anchor_pass else '未通过'}。"
    )
    if family_verdict == "H1_HOLD":
        verdict_line = "**H1 成立（不换冠）**：主档 DEDUP-R85 证伪，spike 池内 60 周相关去重无记正。"
    elif family_verdict == "H1_REJECT":
        verdict_line = "**H1 证伪（不换冠）**：主档 DEDUP-R85 记正（G1/G2/G3）。"
    else:
        verdict_line = "**BLOCKED（不换冠）**：锚点或库存未过，不解读家族句。"

    report = f"""{headline}

```
{h1_block}
```

## 库存

- `corr_source` = **{inventory['corr_source']}**
- `price_cache_path` = `{inventory.get('price_cache_path')}`
- `pool_label_path` = `{inventory.get('pool_label_path')}`
- `skipped` = {json.dumps(inventory.get('skipped') or [], ensure_ascii=False)}

## 锚点门

{anchor_note}

## 主表

| id | ρ* | ret | maxDD | Calmar | 2020–22 / 2023–26 ret | n_dedup_skip | avg_max_ρ | avg_max_family | verdict |
|---|---:|---:|---:|---:|---|---:|---:|---:|---|
{chr(10).join(tbl(c) for c in cells)}

### Δ / 闸（相对本次 F0）

| id | Δret pp | Δ|MDD| pp | G1 | G2 2023–26 | G3 2020–22 | verdict |
|---|---:|---:|:---:|:---:|:---:|---|
"""
    for c in cells:
        if c["id"] == "F0":
            continue
        report += (
            f"| {c['id']} | {100*c['delta_ret']:+.1f} | {100*c['delta_abs_mdd']:+.1f} | "
            f"{str(c['g1_covers']).lower()} | {str(c['g2_2023_26']).lower()} | {str(c['g3_2020_22']).lower()} | {c['verdict']} |\n"
        )

    report += f"""
### 扎堆旁注

- F0 `avg_max_pair_corr`={f0_cell['avg_max_pair_corr']:.3f}，`avg_max_family`={f0_cell['avg_max_family']:.2f}，`n_incumbent_over_rho`（主档口径）见各格。
- 邻档记正 **不** 写入 `positive_ids`，不翻转 `family_verdict`。

## 证伪段

{verdict_line}

## 红线

`champion_swap=false`；`crown=NO`；未改 LIVE_OPS / champion_mast；未新抓数；未混用 158.3%/0.94 或 68.1%/0.31 锚。

source_sha={SOURCE_SHA}；family_verdict={family_verdict}；耗时 {summary['elapsed_sec']}s。
"""
    (OUT / "REPORT.md").write_text(report, encoding="utf-8")
    print("done", OUT, flush=True)


if __name__ == "__main__":
    main()
