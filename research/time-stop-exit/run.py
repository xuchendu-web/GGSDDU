#!/usr/bin/env python3
"""time-stop-exit: B45 spike_ft max5 + E0 + TV25 + SHARPE20; single-name max-hold overlay.

Four books: F0 (off) + TS-MH8 / TS-MH6 / TS-MH12 (K=0). Engine pin 05f0f8a4 (btheta LIVE1430).
Research only — champion_swap=false, crown=NO.
"""
from __future__ import annotations

import json
import math
import re
import subprocess
import sys
import time
from collections import defaultdict
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parent
KIT = ROOT.parent / "cloud_batch" / "CLOUD-BATCH-2026-10-26"
SCRIPTS = KIT / "scripts"
sys.path.insert(0, str(SCRIPTS))

from backtest import LIVE_PHASE, Position, nearest_date, snap_index  # noqa: E402

OUT = ROOT / "out"
CACHE = KIT / "data" / "research_cache"
UNI_CSV = KIT / "data" / "universe_replace_only_436.csv"
WEEK = CACHE / "week"
FACE = CACHE / "holdings_ro2_extended.csv"
DAY_DIR = CACHE / "day"
TEMA_PX = Path("/workspace/tema_etf_scan_2018/prices_daily")
NOON_CSV = CACHE / "fri_1430_through_20261023.csv"
SINA_DAILY = CACHE / "sina_daily"
SNAP_CACHE = KIT / "data" / "cache_1430_snaps.json"
SOURCE_SHA = "05f0f8a4f778fde886f3e7b2976646ff4b7d777b"
BREADTH_THETA = 0.45
ANCHOR = {"ret": 1.316, "maxDD": -0.188, "Calmar": 0.70, "n_weeks": 349, "T": 348, "n_codes": 324}
ANCH_TOL = {"ret": 0.02, "maxDD": 0.01, "sharpe": 0.03}
EVAL_START = "2020-01-03"
END_S = "2026-10-23"
COST_SIDE = 0.001
SIGMA_STAR = 0.25
LCAP = 1.0
LIVE_COST_RT = 0.002
MAX_POS = 5

BOOK_SPECS = [
    {"id": "F0", "book": "LIVE1430-TSMH-off-B45-TV25", "N": None, "K": None},
    {"id": "TS-MH8", "book": "LIVE1430-TSMH-N8-K0-B45-TV25", "N": 8, "K": 0},
    {"id": "TS-MH6", "book": "LIVE1430-TSMH-N6-K0-B45-TV25", "N": 6, "K": 0},
    {"id": "TS-MH12", "book": "LIVE1430-TSMH-N12-K0-B45-TV25", "N": 12, "K": 0},
]

SKIP_PATHS = [
    Path("research/exit-atr-chandelier"),
    Path("research/cloud_batch/SPIKE-MAXHOLD-SWEEP-LIVE1430"),
    Path("research/SPIKE-S20-EXIT-CROSS-MH6-RANKDROP-LIVE1430"),
    Path("research/SPIKE-S20-EXIT-CROSS-PT15-COOL6-LIVE1430"),
    Path("research/cloud_batch/SPIKE-PROFIT-TAKE-SWEEP-LIVE1430"),
    Path("strategy-weekly/_kit/face_engine.py"),
]

ENGINE_A = Path("research/cloud_batch/SPIKE-S20-BTHETA-GRID-LIVE1430/run.py")
ENGINE_B = Path("research/cloud_batch/SPIKE-S20-EXTEND-REBASE-LIVE1430/run.py")
NAV_D = Path("research/cloud_batch/SPIKE-S20-EXTEND-REBASE-LIVE1430/nav_LIVE1430-B45-S20.csv")
HEADLINE = (
    "请拍板：维持面层 B45 + spike_ft max5 + E0 + TV25 + SHARPE20，只叠一层单票时停："
    "连续持有 ≥ N 周的名字在当周周五再平衡被强制清出，必须重新挣席。主档 N=8、冷静 K=0。无论记正与否都不换冠。"
)
H1_TEXT = (
    "主簿 `TS-MH8` 相对 **当次重放的 F0**，全样本满足 Δret ≥ Δ|MDD|，"
    "且 2023–26 累计收益不低于 F0 的 2023–26（强势段不踏空，且自身为正）。"
)


@dataclass
class Cand:
    code: str
    px: float
    fz: float | None
    aum: float
    sharpe: float | None


def time_stop_trigger(*, weeks: int, n: int) -> bool:
    """入场当周 weeks=0。满 N 次未退出 +1 之后，下一信号周五触发。"""
    return weeks >= n


def first_eligible_friday(t, fridays: list, k: int):
    """K=0 → t 当周可再入。四件套不调用 K>0。"""
    if k <= 0:
        return t
    after = [f for f in fridays if f > t]
    if len(after) < k:
        return None
    return after[k - 1]


def is_spike(snap: dict[str, Any] | None) -> bool:
    if not snap:
        return False
    if snap.get("pending_second_week") or snap.get("in_play_kind") == "box_pending":
        return False
    return bool(snap.get("in_play")) and snap.get("in_play_kind") == "spike_ft"


def sharpe_key(c: Cand, pool: list[Cand]) -> tuple:
    miss = 0 if c.sharpe is not None else 1
    return (miss, -(c.sharpe if c.sharpe is not None else 0.0), c.code)


def run_fixtures() -> None:
    assert not time_stop_trigger(weeks=0, n=8)
    assert not time_stop_trigger(weeks=7, n=8)
    assert time_stop_trigger(weeks=8, n=8)
    fri = [pd.Timestamp("2020-01-03"), pd.Timestamp("2020-01-10")]
    t = fri[0]
    assert first_eligible_friday(t, fri, 0) == t


def _git_has(path: str, ref: str = "HEAD") -> bool:
    try:
        subprocess.run(
            ["git", "cat-file", "-e", f"{ref}:{path}"],
            cwd=ROOT.parents[1],
            check=True,
            capture_output=True,
        )
        return True
    except (subprocess.CalledProcessError, FileNotFoundError):
        return False


def scan_inventory() -> dict[str, Any]:
    skipped: list[str] = []
    repo = ROOT.parents[1]
    for p in SKIP_PATHS:
        for base in (repo, ROOT.parent):
            fp = base / p
            if fp.exists():
                skipped.append(str(p).replace("\\", "/"))
                break

    engine_source = "missing"
    kit_path = str(KIT) if KIT.exists() else ""
    if (repo / ENGINE_A).exists() or _git_has(str(ENGINE_A).replace("\\", "/"), SOURCE_SHA):
        engine_source = "btheta_05f0f8a4"
    elif _git_has(
        str(ENGINE_B).replace("\\", "/"),
        "origin/cursor/spike-s20-extend-rebase-live1430-27f1",
    ):
        engine_source = "extend_rebase_19834fa0"

    nav_anchor = ""
    if (repo / NAV_D).exists():
        nav_anchor = str(NAV_D)
    elif _git_has(
        str(NAV_D).replace("\\", "/"),
        "origin/cursor/spike-s20-extend-rebase-live1430-27f1",
    ):
        nav_anchor = f"git:origin/cursor/spike-s20-extend-rebase-live1430-27f1:{NAV_D}"

    return {
        "engine_source": engine_source,
        "kit_path": kit_path,
        "nav_anchor": nav_anchor,
        "skipped": skipped,
    }


def write_blocked(inventory: dict[str, Any], reason: str) -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    summary = {
        "batch": "TIME-STOP-EXIT",
        "champion_swap": False,
        "crown": "NO",
        "source_sha": SOURCE_SHA,
        "sample": [EVAL_START, END_S],
        "anchor_pass": False,
        "anchor": ANCHOR,
        "face_id": "F0",
        "primary_n": 8,
        "primary_k": 0,
        "inventory": inventory,
        "h1": H1_TEXT,
        "family_verdict": "BLOCKED",
        "positive_ids": [],
        "books": ["F0", "TS-MH8", "TS-MH6", "TS-MH12"],
        "cells": [],
    }
    (OUT / "summary.json").write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
    report = f"""{HEADLINE}

> {H1_TEXT}

## 库存

- `engine_source` = **{inventory['engine_source']}**
- `kit_path` = `{inventory.get('kit_path')}`
- 原因：{reason}
- `skipped`：{json.dumps(inventory.get('skipped') or [], ensure_ascii=False)}

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
    risk_on_by_fri: dict[str, bool],
    variant: str,
    mh_n: int | None,
    mh_k: int = 0,
    max_pos: int = MAX_POS,
) -> tuple[list[dict[str, Any]], dict[str, list[str]], dict[str, Any]]:
    cash = 1.0
    positions: dict[str, Position] = {}
    trades: list[dict[str, Any]] = []
    picks: dict[str, list[str]] = {}
    cool_until: dict[str, pd.Timestamp] = {}
    n_timestop = 0
    n_timestop_same_fri_reenter = 0
    n_cool_block = 0
    n_e0 = 0
    hold_weeks_at_exit: list[float] = []

    def px_on(code: str, d: str) -> float | None:
        return closes_w.get(code, {}).get((alias.get(code) or {}).get(d) or d)

    def snap_at(code: str, d: str) -> dict[str, Any] | None:
        key = (alias.get(code) or {}).get(d) or d
        return snaps.get(code, {}).get(key)

    def equity_now() -> float:
        return cash + sum(p.shares * p.last_px for p in positions.values())

    def build_cands(d: str, skip: set[str]) -> list[Cand]:
        out: list[Cand] = []
        td = pd.Timestamp(d)
        for code in snaps:
            if code in skip:
                continue
            elig = cool_until.get(code)
            if elig is not None and td < elig:
                n_cool_block += 1
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

    last_i = len(calendar) - 1
    for i, d in enumerate(calendar):
        for p in positions.values():
            px = px_on(p.code, d)
            if px is not None:
                p.last_px = px

        last_bar = i == last_i
        risk_on = False if last_bar else bool(risk_on_by_fri.get(d, False))
        ts_exited: set[str] = set()

        exiting: list[tuple[str, str, float, str | None]] = []
        for code, p in list(positions.items()):
            px = px_on(code, d)
            if last_bar:
                exiting.append((code, "eod_eval", px if px is not None else p.last_px, None))
                continue
            if not risk_on:
                exiting.append((code, "breadth_off", px if px is not None else p.last_px, None))
                continue
            if px is None:
                continue

            e0_reason = None
            sn = snap_at(code, d)
            if sn:
                fz = sn.get("falsify_close")
                if fz is not None and px < float(fz):
                    e0_reason = "falsify"
                elif sn.get("always_in") != "Long":
                    e0_reason = "always_in_flip"
                elif (not sn.get("in_play")) and sn.get("phase") not in LIVE_PHASE:
                    e0_reason = "left_structure"

            ts_hit = mh_n is not None and time_stop_trigger(weeks=p.weeks, n=mh_n)
            if ts_hit:
                exiting.append((code, "time_stop", px, e0_reason))
                if e0_reason:
                    n_e0 += 1
            elif e0_reason:
                exiting.append((code, e0_reason, px, None))
                n_e0 += 1
            else:
                p.weeks += 1

        for code, reason, px, e0_also in exiting:
            p = positions.pop(code)
            cash += p.shares * px * (1.0 - COST_SIDE)
            hold_weeks_at_exit.append(float(p.weeks))
            if reason == "time_stop":
                n_timestop += 1
                ts_exited.add(code)
                if mh_k > 0:
                    fe = first_eligible_friday(pd.Timestamp(d), fridays, mh_k)
                    if fe is not None:
                        cool_until[code] = pd.Timestamp(fe)
            elif reason in ("falsify", "always_in_flip", "left_structure"):
                if reason != "time_stop":
                    pass
            trades.append(
                {
                    "variant": variant,
                    "code": code,
                    "entry_date": p.entry_date,
                    "exit_date": d,
                    "exit_reason": reason,
                    "e0_also": e0_also,
                    "weeks_held": p.weeks,
                }
            )

        take: list[Cand] = []
        if not last_bar and risk_on:
            pool = build_cands(d, set(positions))
            slots = max_pos - len(positions)
            if slots > 0 and pool:
                pool_rank = [c for c in pool if c.sharpe is not None]
                take = sorted(pool_rank, key=lambda c: sharpe_key(c, pool_rank))[:slots]
                for c in take:
                    if c.code in ts_exited:
                        n_timestop_same_fri_reenter += 1

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
        "n_cash_weeks": n_cash,
        "n_timestop": n_timestop,
        "n_timestop_same_fri_reenter": n_timestop_same_fri_reenter,
        "n_cool_block": n_cool_block,
        "n_e0": n_e0,
        "avg_hold_weeks": float(np.mean(hold_weeks_at_exit)) if hold_weeks_at_exit else 0.0,
        "n_trades": len(trades),
    }
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


def daily_sharpe(s: pd.Series) -> float:
    if s is None or len(s) < 3:
        return float("nan")
    x = s.dropna()
    if len(x) < 3:
        return float("nan")
    sig = float(x.std(ddof=1))
    if sig <= 0:
        return float("nan")
    return float(x.mean() / sig * np.sqrt(252))


def pct(x: float | None) -> str:
    if x is None or (isinstance(x, float) and (math.isnan(x) or math.isinf(x))):
        return "—"
    return f"{100 * x:.1f}%"


def check_anchor(st: dict[str, float], sharpe: float, n_weeks: int, T: int, n_codes: int, end_s: str) -> bool:
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
    if abs(st["Calmar"] - ANCHOR["Calmar"]) > 0.05:
        return False
    if abs(sharpe - 0.82) > ANCH_TOL["sharpe"]:
        return False
    if abs(st["ret"] - 1.583) < 0.03:
        return False
    if abs(st["ret"] - 0.681) < 0.03:
        return False
    return True


def judge_cell(cell: dict[str, Any], f0: dict[str, Any]) -> None:
    if cell["id"] == "F0":
        cell["delta_ret"] = 0.0
        cell["delta_abs_mdd"] = 0.0
        cell["g1_covers"] = True
        cell["g2_2023_26"] = True
        cell["verdict"] = "ANCHOR"
        return
    dret = cell["ret"] - f0["ret"]
    d_abs = abs(cell["maxDD"]) - abs(f0["maxDD"])
    cell["delta_ret"] = dret
    cell["delta_abs_mdd"] = d_abs
    g1 = dret >= d_abs
    g2 = cell["w2023_26"]["ret"] >= f0["w2023_26"]["ret"] and cell["w2023_26"]["ret"] > 0
    cell["g1_covers"] = g1
    cell["g2_2023_26"] = g2
    if any(math.isnan(x) for x in (cell["ret"], cell["maxDD"], dret, d_abs)):
        cell["verdict"] = "证伪"
    elif cell["id"] == "TS-MH8" and cell.get("n_timestop", 0) == 0:
        cell["verdict"] = "证伪"
    elif g1 and g2:
        cell["verdict"] = "记正"
    else:
        cell["verdict"] = "证伪"


def main() -> None:
    if len(BOOK_SPECS) != 4:
        raise SystemExit("BOOK_SPECS must be exactly 4 rows")
    for spec in BOOK_SPECS:
        if spec["id"] == "F0":
            continue
        if spec.get("K", 0) != 0:
            raise SystemExit("K>0 not allowed in four-pack")
        if spec.get("N") in (10,):
            raise SystemExit("N=10 not allowed")

    run_fixtures()
    print("fixtures OK", flush=True)

    inventory = scan_inventory()
    print("inventory", inventory, flush=True)

    if inventory["engine_source"] == "missing":
        write_blocked(inventory, "引擎针 05f0f8a4 / 延窗 run.py 均不可解析")
        raise SystemExit(2)

    for p in (WEEK, FACE, DAY_DIR, NOON_CSV, SINA_DAILY, SNAP_CACHE, UNI_CSV):
        if not Path(p).exists():
            write_blocked(inventory, f"missing kit path {p}")
            raise SystemExit(2)

    OUT.mkdir(parents=True, exist_ok=True)
    t0 = time.time()

    uni = pd.read_csv(UNI_CSV)
    uni["code"] = uni["code"].astype(str).str.zfill(6)
    uni = uni[uni["aum"] >= 2].copy()
    codes = uni["code"].tolist()
    aum = {r.code: float(r.aum or 0) for r in uni.itertuples()}
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
        risk_on_by_fri[d] = bool(
            bv is not None and not (isinstance(bv, float) and math.isnan(bv)) and float(bv) >= BREADTH_THETA
        )
    risk_on_by_fri[calendar[-1]] = False

    closes_w_close: dict[str, dict[str, float]] = {}
    for c in codes:
        fp = WEEK / f"{c}.json"
        if not fp.exists():
            closes_w_close[c] = {}
            continue
        rec = json.loads(fp.read_text(encoding="utf-8"))
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
            risk_on_by_fri=risk_on_by_fri,
            variant=name,
            mh_n=spec["N"],
            mh_k=spec["K"] or 0,
        )
        if spec["id"] == "F0" and st["n_timestop"] != 0:
            raise SystemExit("F0 leaked time_stop overlay")
        hold_by[name] = hold
        sim_stats[name] = st
        pd.DataFrame(trades).to_csv(OUT / f"trades_{spec['id']}.csv", index=False)
        rows = []
        for d in calendar[:-1]:
            codes_h = hold.get(d) or []
            rows.append(
                {
                    "date": d,
                    "risk_on": int(risk_on_by_fri.get(d, False)),
                    "n_held": len(codes_h),
                    "codes": ",".join(codes_h),
                }
            )
        pd.DataFrame(rows).to_csv(OUT / f"holdings_{spec['id']}.csv", index=False)

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
        sh = daily_sharpe(r)
        r2022 = r[(r.index >= "2020-01-01") & (r.index <= "2022-12-31")]
        r2023 = r[r.index >= "2023-01-01"]
        st2022 = stats_full(r2022) if len(r2022) > 5 else {k: float("nan") for k in st}
        st2023 = stats_full(r2023) if len(r2023) > 5 else {k: float("nan") for k in st}
        sim = sim_stats[name]
        cell = {
            "id": spec["id"],
            "book": name,
            "N": spec["N"],
            "K": spec["K"],
            "ret": st["ret"],
            "maxDD": st["maxDD"],
            "CAGR": st["CAGR"],
            "Calmar": st["Calmar"],
            "Sharpe": sh,
            "avgL": float(L[L > 0].mean()) if (L > 0).any() else 0.0,
            "avg_turnover_1way": avg_to,
            "n_cash_weeks": sim["n_cash_weeks"],
            "n_timestop": sim["n_timestop"],
            "n_timestop_same_fri_reenter": sim["n_timestop_same_fri_reenter"],
            "n_cool_block": sim["n_cool_block"],
            "n_e0": sim["n_e0"],
            "avg_hold_weeks": sim["avg_hold_weeks"],
            "w2020_22": {"ret": st2022["ret"], "maxDD": st2022["maxDD"], "Calmar": st2022["Calmar"]},
            "w2023_26": {"ret": st2023["ret"], "maxDD": st2023["maxDD"], "Calmar": st2023["Calmar"]},
        }
        cells.append(cell)
        print(
            f"  {spec['id']}: ret={pct(st['ret'])} dd={pct(st['maxDD'])} Calmar={st['Calmar']:.2f} "
            f"n_ts={sim['n_timestop']}",
            flush=True,
        )

    f0_cell = next(c for c in cells if c["id"] == "F0")
    T = len(calendar) - 1
    anchor_pass = check_anchor(f0_cell, f0_cell["Sharpe"], len(calendar), T, len(codes), actual_end)
    print(f"anchor_pass={anchor_pass}", flush=True)

    blocked_run = not anchor_pass or inventory["engine_source"] == "missing"
    for c in cells:
        if blocked_run:
            c["delta_ret"] = 0.0
            c["delta_abs_mdd"] = 0.0
            c["g1_covers"] = False
            c["g2_2023_26"] = False
            c["verdict"] = "BLOCKED"
        else:
            judge_cell(c, f0_cell)

    primary = next(c for c in cells if c["id"] == "TS-MH8")
    positive_ids = ["TS-MH8"] if primary["verdict"] == "记正" else []
    if blocked_run:
        family_verdict = "BLOCKED"
    elif positive_ids:
        family_verdict = "H1_REJECT"
    else:
        family_verdict = "H1_HOLD"

    table_rows = []
    for c in cells:
        nk = c["N"]
        kk = c["K"]
        table_rows.append(
            {
                "id": c["id"],
                "book": c["book"],
                "N": "off" if nk is None else nk,
                "K": "off" if kk is None else kk,
                "ret": c["ret"],
                "maxDD": c["maxDD"],
                "CAGR": c["CAGR"],
                "Calmar": c["Calmar"],
                "Sharpe": c["Sharpe"],
                "avgL": c["avgL"],
                "avg_turnover_1way": c["avg_turnover_1way"],
                "n_cash_weeks": c["n_cash_weeks"],
                "n_timestop": c["n_timestop"],
                "n_timestop_same_fri_reenter": c["n_timestop_same_fri_reenter"],
                "n_cool_block": c["n_cool_block"],
                "n_e0": c["n_e0"],
                "avg_hold_weeks": c["avg_hold_weeks"],
                "w2020_22_ret": c["w2020_22"]["ret"],
                "w2020_22_maxDD": c["w2020_22"]["maxDD"],
                "w2020_22_Calmar": c["w2020_22"]["Calmar"],
                "w2023_26_ret": c["w2023_26"]["ret"],
                "w2023_26_maxDD": c["w2023_26"]["maxDD"],
                "w2023_26_Calmar": c["w2023_26"]["Calmar"],
                "delta_ret": c["delta_ret"],
                "delta_abs_mdd": c["delta_abs_mdd"],
                "g1_covers": c["g1_covers"],
                "g2_2023_26": c["g2_2023_26"],
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
    ax.set_title("time-stop-exit: F0 vs TS-MH")
    ax.set_ylabel("nav (log)")
    ax.grid(True, alpha=0.3)
    ax.legend(fontsize=8)
    fig.tight_layout()
    fig.savefig(OUT / "equity_curve.png")
    plt.close(fig)

    summary = {
        "batch": "TIME-STOP-EXIT",
        "champion_swap": False,
        "crown": "NO",
        "source_sha": SOURCE_SHA,
        "sample": [EVAL_START, actual_end],
        "anchor_pass": anchor_pass,
        "anchor": {**ANCHOR, "n_weeks": len(calendar), "T": T},
        "face_id": "F0",
        "primary_n": 8,
        "primary_k": 0,
        "inventory": inventory,
        "h1": H1_TEXT,
        "family_verdict": family_verdict,
        "positive_ids": positive_ids,
        "books": ["F0", "TS-MH8", "TS-MH6", "TS-MH12"],
        "cells": cells,
        "elapsed_sec": round(time.time() - t0, 1),
    }
    (OUT / "summary.json").write_text(json.dumps(summary, ensure_ascii=False, indent=2, default=str), encoding="utf-8")

    def tbl(c: dict[str, Any]) -> str:
        nk = "off" if c["N"] is None else str(c["N"])
        return (
            f"| {c['id']} | {nk} | {pct(c['ret'])} | {pct(c['maxDD'])} | {c['Calmar']:.2f} | "
            f"{c['n_timestop']} | {c['n_timestop_same_fri_reenter']} | {c['avg_turnover_1way']:.4f} | {c['verdict']} |"
        )

    anchor_note = (
        f"F0 ret={pct(f0_cell['ret'])} maxDD={pct(f0_cell['maxDD'])} Calmar={f0_cell['Calmar']:.2f} "
        f"Sharpe={f0_cell['Sharpe']:.2f}（锚 131.6% / −18.8% / 0.70 / Sharpe 0.82）→ "
        f"{'通过' if anchor_pass else '未通过'}。"
    )
    if not anchor_pass:
        r0 = f0_cell["ret"]
        if abs(r0 - 1.583) < 0.05:
            anchor_note += " 落点接近 TV 网格 158.3% 面。"
        elif abs(r0 - 0.681) < 0.05:
            anchor_note += " 落点接近压缩突破 68.1% 面。"

    if family_verdict == "H1_HOLD":
        verdict_line = (
            f"证伪（不换冠）：TS-MH8 未过闸 G1/G2（或 n_timestop=0）。"
            f"Δret {100*primary['delta_ret']:+.1f}pp，Δ|MDD| {100*primary['delta_abs_mdd']:+.1f}pp，"
            f"2023–26 {pct(primary['w2023_26']['ret'])} vs F0 {pct(f0_cell['w2023_26']['ret'])}。"
        )
        if primary["verdict"] == "证伪" and primary["n_timestop"] == 0:
            verdict_line = f"证伪（不换冠）：主簿 n_timestop=0，机制未咬住。{verdict_line}"
    elif family_verdict == "H1_REJECT":
        verdict_line = (
            f"记正（不换冠）：TS-MH8 两闸全过。Δret {100*primary['delta_ret']:+.1f}pp，"
            f"Δ|MDD| {100*primary['delta_abs_mdd']:+.1f}pp，"
            f"2023–26 {pct(primary['w2023_26']['ret'])}，n_timestop={primary['n_timestop']}，"
            f"同周五再入={primary['n_timestop_same_fri_reenter']}。邻档只旁注。"
        )
    else:
        verdict_line = "**BLOCKED（不换冠）**：锚点或库存未过，不解读家族句。"

    report = f"""{HEADLINE}

> {H1_TEXT}

## 库存

- `engine_source` = **{inventory['engine_source']}**
- `kit_path` = `{inventory.get('kit_path')}`
- `nav_anchor` = `{inventory.get('nav_anchor')}`
- `skipped` = {json.dumps(inventory.get('skipped') or [], ensure_ascii=False)}

## 锚点门

{anchor_note}

## 主表

| id | N | ret | maxDD | Calmar | n_timestop | same_fri_re | avg_to_1w | verdict |
|---:|---:|---:|---:|---:|---:|---:|---:|---|
{chr(10).join(tbl(c) for c in cells)}

### Δ / 闸（相对本次 F0）

| id | Δret pp | Δ|MDD| pp | G1 | G2 2023–26 | verdict |
|---|---:|---:|:---:|:---:|---|
"""
    for c in cells:
        if c["id"] == "F0":
            continue
        report += (
            f"| {c['id']} | {100*c['delta_ret']:+.1f} | {100*c['delta_abs_mdd']:+.1f} | "
            f"{str(c['g1_covers']).lower()} | {str(c['g2_2023_26']).lower()} | {c['verdict']} |\n"
        )

    report += f"""
### 时停诊断

| id | n_timestop | same_fri_reenter | n_cool_block | n_e0 | avg_hold_weeks |
|---|---:|---:|---:|---:|---:|
"""
    for c in cells:
        report += (
            f"| {c['id']} | {c['n_timestop']} | {c['n_timestop_same_fri_reenter']} | "
            f"{c['n_cool_block']} | {c['n_e0']} | {c['avg_hold_weeks']:.2f} |\n"
        )

    report += f"""
## 证伪段

{verdict_line}

**family_verdict** = `{family_verdict}`；`positive_ids` = {json.dumps(positive_ids, ensure_ascii=False)}。

## 红线

`champion_swap=false`；`crown=NO`；未改 LIVE_OPS / champion_mast；未新抓数；未混用 158.3%/0.94 或 68.1%/0.31 锚。

source_sha={SOURCE_SHA}；耗时 {summary['elapsed_sec']}s。
"""
    (OUT / "REPORT.md").write_text(report, encoding="utf-8")
    print("done", OUT, flush=True)


if __name__ == "__main__":
    main()
