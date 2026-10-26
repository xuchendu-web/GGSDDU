#!/usr/bin/env python3
"""Causal walk-forward backtest of the board's in_play long signals.

Reuses scripts/build_scan.py classify() unchanged.
"""

from __future__ import annotations

import csv
import json
import math
import sys
import time
from collections import Counter, defaultdict
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass, field
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from typing import Any

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(Path(__file__).resolve().parent))

from build_scan import (  # noqa: E402
    Bar,
    classify,
    http_get_retry,
    load_universe,
    market,
)

BT_RAW = ROOT / "data" / "raw_bt"
SIG_CACHE = ROOT / "data" / "bt_signals.json"
OUT = ROOT / "backtest"
SCAN_JSON = ROOT / "data" / "scan.json"

START_S = "2023-01-01"
END_S = "2026-09-04"
EVAL_START = "2024-07-01"
EVAL_END = "2026-09-04"
COST = 0.001  # 0.1% each side
MIN_BARS = 5
WORKERS = 8
ENTER_KINDS = frozenset({"tight_long", "spike_ft"})
LIVE_PHASE = frozenset({"紧通道", "冲击"})
MAX_POS_VARIANTS = (5, 10, 10**9)
MAX_POS_LABEL = {5: "5", 10: "10", 10**9: "unlimited"}


# ---------------------------------------------------------------------------
# Download
# ---------------------------------------------------------------------------

def parse_tencent(payload: dict[str, Any], code: str) -> list[Bar]:
    data = payload.get("data") or {}
    key = f"{market(code)}{code}"
    node = data.get(key) or (next(iter(data.values())) if data else None)
    if not isinstance(node, dict):
        return []
    rows = node.get("qfqweek") or node.get("week") or []
    bars: list[Bar] = []
    for row in rows:
        if not row:
            continue
        d = str(row[0])[:10]
        if d < START_S or d > END_S:
            continue
        o, cl, h, l = float(row[1]), float(row[2]), float(row[3]), float(row[4])
        if min(o, cl, h, l) <= 0:
            continue
        bars.append(Bar(d, o, h, l, cl))
    bars.sort(key=lambda b: b.date)
    return bars


def parse_yahoo(payload: dict[str, Any]) -> list[Bar]:
    result = ((payload.get("chart") or {}).get("result") or [None])[0]
    if not result:
        return []
    ts = result.get("timestamp") or []
    q0 = ((result.get("indicators") or {}).get("quote") or [{}])[0]
    opens, highs, lows, closes = q0.get("open"), q0.get("high"), q0.get("low"), q0.get("close")
    bars: list[Bar] = []
    for i, t in enumerate(ts):
        if opens[i] is None or highs[i] is None or lows[i] is None or closes[i] is None:
            continue
        dt = datetime.fromtimestamp(int(t), tz=timezone.utc)
        wd = dt.weekday()
        if wd == 6:
            end = dt.date() + timedelta(days=5)
        elif wd <= 4:
            end = dt.date() + timedelta(days=(4 - wd))
        else:
            end = dt.date() - timedelta(days=wd - 4)
        if end < date.fromisoformat(START_S) or end > date.fromisoformat(END_S):
            continue
        o, h, l, c = float(opens[i]), float(highs[i]), float(lows[i]), float(closes[i])
        if min(o, h, l, c) <= 0:
            continue
        bars.append(Bar(end.isoformat(), o, h, l, c))
    uniq: dict[str, Bar] = {b.date: b for b in bars}
    return [uniq[k] for k in sorted(uniq)]


def fetch_one(code: str) -> dict[str, Any]:
    cache = BT_RAW / f"{code}.json"
    if cache.exists():
        try:
            rec = json.loads(cache.read_text(encoding="utf-8"))
            if rec.get("bars"):
                return rec
        except Exception:
            pass
    err = None
    m = market(code)
    url = (
        "https://web.ifzq.gtimg.cn/appstock/app/fqkline/get"
        f"?param={m}{code},week,{START_S},{END_S},220,qfq"
    )
    try:
        payload = json.loads(http_get_retry(url))
        bars = parse_tencent(payload, code)
        if bars:
            rec = {
                "code": code,
                "source": "tencent_qfq_week",
                "bars": [{"date": b.date, "o": b.o, "h": b.h, "l": b.l, "c": b.c} for b in bars],
            }
            cache.write_text(json.dumps(rec, ensure_ascii=False), encoding="utf-8")
            return rec
        err = "tencent_empty"
    except Exception as e:
        err = f"tencent:{type(e).__name__}"
    suffix = ".SS" if code[0] in "56" else ".SZ"
    p1 = int(datetime(2023, 1, 1, tzinfo=timezone.utc).timestamp())
    p2 = int(datetime(2026, 9, 4, 16, tzinfo=timezone.utc).timestamp())
    yurl = (
        "https://query1.finance.yahoo.com/v8/finance/chart/"
        f"{code}{suffix}?interval=1wk&period1={p1}&period2={p2}&events=history"
    )
    try:
        payload = json.loads(http_get_retry(yurl))
        bars = parse_yahoo(payload)
        if bars:
            rec = {
                "code": code,
                "source": "yahoo_weekly",
                "bars": [{"date": b.date, "o": b.o, "h": b.h, "l": b.l, "c": b.c} for b in bars],
            }
            cache.write_text(json.dumps(rec, ensure_ascii=False), encoding="utf-8")
            return rec
        err = (err or "") + "|yahoo_empty"
    except Exception as e:
        err = (err or "") + f"|yahoo:{type(e).__name__}"
    rec = {"code": code, "source": None, "bars": [], "error": err or "download_failed"}
    cache.write_text(json.dumps(rec, ensure_ascii=False), encoding="utf-8")
    return rec


def download_all(codes: list[str]) -> dict[str, dict[str, Any]]:
    BT_RAW.mkdir(parents=True, exist_ok=True)
    out: dict[str, dict[str, Any]] = {}
    with ThreadPoolExecutor(max_workers=WORKERS) as ex:
        futs = {ex.submit(fetch_one, c): c for c in codes}
        done = 0
        for fut in as_completed(futs):
            rec = fut.result()
            out[rec["code"]] = rec
            done += 1
            if done % 50 == 0:
                print(f"  download {done}/{len(codes)}", flush=True)
    return out


# ---------------------------------------------------------------------------
# Causal classify walk
# ---------------------------------------------------------------------------

KEEP = (
    "always_in",
    "phase",
    "in_play",
    "in_play_kind",
    "pending_second_week",
    "falsify_close",
    "last_close",
    "last_bar_date",
)


def walk_classify(code: str, rec: dict[str, Any]) -> list[dict[str, Any]]:
    raw = rec.get("bars") or []
    bars = [Bar(b["date"], b["o"], b["h"], b["l"], b["c"]) for b in raw]
    bars = [b for b in bars if b.date <= END_S]
    snaps: list[dict[str, Any]] = []
    for i in range(len(bars)):
        if bars[i].date < "2024-05-01":
            continue  # keep a few weeks before eval for pending state
        if i + 1 < MIN_BARS:
            continue
        try:
            cl = classify(bars[: i + 1])
        except Exception:
            continue
        snap = {k: cl.get(k) for k in KEEP}
        snap["code"] = code
        snap["n_bars"] = i + 1
        snap["thin_history"] = (i + 1) < 30
        snaps.append(snap)
    return snaps


def build_signals(
    universe: list[dict[str, Any]], raws: dict[str, dict[str, Any]]
) -> dict[str, list[dict[str, Any]]]:
    if SIG_CACHE.exists():
        try:
            cached = json.loads(SIG_CACHE.read_text(encoding="utf-8"))
            if cached.get("end") == END_S and len(cached.get("by_code") or {}) == len(universe):
                print("using signal cache", SIG_CACHE, flush=True)
                return cached["by_code"]
        except Exception:
            pass
    by_code: dict[str, list[dict[str, Any]]] = {}
    codes = [u["code"] for u in universe]
    done = 0
    t0 = time.time()
    with ThreadPoolExecutor(max_workers=6) as ex:
        futs = {ex.submit(walk_classify, c, raws.get(c) or {}): c for c in codes}
        for fut in as_completed(futs):
            c = futs[fut]
            by_code[c] = fut.result()
            done += 1
            if done % 40 == 0:
                print(f"  classify {done}/{len(codes)} {time.time()-t0:.1f}s", flush=True)
    SIG_CACHE.write_text(
        json.dumps({"end": END_S, "by_code": by_code}, ensure_ascii=False),
        encoding="utf-8",
    )
    print(f"wrote {SIG_CACHE}", flush=True)
    return by_code


# ---------------------------------------------------------------------------
# Calendar / alignment
# ---------------------------------------------------------------------------

def close_map(rec: dict[str, Any]) -> dict[str, float]:
    return {b["date"]: float(b["c"]) for b in rec.get("bars") or [] if b["date"] <= END_S}


def snap_index(snaps: list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    return {s["last_bar_date"]: s for s in snaps}


def nearest_date(target: str, dates: list[str], window: int = 3) -> str | None:
    """Exact match or a bar within ±window calendar days (holiday / QDII)."""
    if target in dates:
        return target
    td = date.fromisoformat(target)
    best = None
    best_d = 99
    for d in dates:
        delta = abs((date.fromisoformat(d) - td).days)
        if delta <= window and delta < best_d:
            best, best_d = d, delta
    return best


# ---------------------------------------------------------------------------
# Portfolio
# ---------------------------------------------------------------------------

@dataclass
class Position:
    code: str
    kind: str
    entry_date: str
    entry_px: float
    entry_falsify: float | None
    shares: float
    last_px: float
    weeks: int = 0


def net_ret(entry_px: float, exit_px: float) -> float:
    return (exit_px * (1.0 - COST)) / (entry_px * (1.0 + COST)) - 1.0


def simulate(
    calendar: list[str],
    snaps_by_code: dict[str, dict[str, dict[str, Any]]],
    closes_by_code: dict[str, dict[str, float]],
    aum: dict[str, float],
    max_pos: int,
    falsify_mode: str,
    date_alias: dict[str, dict[str, str]],
    enter_kinds: frozenset[str] | None = None,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    """Return (trades, equity_rows)."""
    kinds = enter_kinds if enter_kinds is not None else ENTER_KINDS
    cash = 1.0
    positions: dict[str, Position] = {}
    trades: list[dict[str, Any]] = []
    equity_rows: list[dict[str, Any]] = []
    pending_prev: set[str] = set()  # codes that were box_pending last week

    def equity_now() -> float:
        return cash + sum(p.shares * p.last_px for p in positions.values())

    def px_on(code: str, d: str) -> float | None:
        alias = date_alias.get(code, {}).get(d)
        key = alias or d
        return closes_by_code.get(code, {}).get(key)

    def snap_on(code: str, d: str) -> dict[str, Any] | None:
        alias = date_alias.get(code, {}).get(d)
        key = alias or d
        return snaps_by_code.get(code, {}).get(key)

    for i, d in enumerate(calendar):
        # 1) mark to market
        for p in positions.values():
            px = px_on(p.code, d)
            if px is not None:
                p.last_px = px

        # 2) exits at this close
        exiting: list[tuple[str, str, float]] = []
        for code, p in positions.items():
            snap = snap_on(code, d)
            px = px_on(code, d)
            if px is None:
                continue
            reason = None
            if snap:
                fz = p.entry_falsify if falsify_mode == "frozen" else snap.get("falsify_close")
                if fz is not None and px < float(fz):
                    reason = "falsify"
                elif snap.get("always_in") != "Long":
                    reason = "always_in_flip"
                elif (not snap.get("in_play")) and snap.get("phase") not in LIVE_PHASE:
                    reason = "left_structure"
            if reason:
                exiting.append((code, reason, px))
            else:
                p.weeks += 1

        for code, reason, px in exiting:
            p = positions.pop(code)
            cash += p.shares * px * (1.0 - COST)
            trades.append(
                {
                    "code": code,
                    "kind": p.kind,
                    "entry_date": p.entry_date,
                    "entry_px": round(p.entry_px, 6),
                    "exit_date": d,
                    "exit_px": round(px, 6),
                    "exit_reason": reason,
                    "weeks_held": p.weeks + 1,
                    "ret_net": round(net_ret(p.entry_px, px), 6),
                    "max_positions": MAX_POS_LABEL[max_pos],
                    "falsify_mode": falsify_mode,
                }
            )

        # 3) entries at this close
        pending_now: set[str] = set()
        cands: list[tuple[int, float, str, str, float, float | None]] = []
        for code, smap in snaps_by_code.items():
            if code in positions:
                continue
            snap = snap_on(code, d)
            if not snap:
                continue
            kind = snap.get("in_play_kind")
            if kind == "box_pending" or snap.get("pending_second_week"):
                pending_now.add(code)
                continue
            if not snap.get("in_play") or kind not in kinds:
                continue
            px = px_on(code, d)
            if px is None or px <= 0:
                continue
            # pending last week confirming this week is already a tight_long/spike_ft buy
            rank = 0 if kind == "tight_long" else 1
            cands.append((rank, -(aum.get(code) or 0.0), code, kind, px, snap.get("falsify_close")))

        slots = max_pos - len(positions)
        cands.sort()
        # last bar is evaluation end — do not open a name we would instantly liquidate
        if i == len(calendar) - 1:
            take = []
        else:
            take = cands[: max(0, slots)]

        if take:
            eq = equity_now()
            n_after = len(positions) + len(take)
            target = eq / n_after if n_after else 0.0
            for p in positions.values():
                if p.last_px > 0:
                    p.shares = target / p.last_px
            for _rk, _aum, code, kind, px, fz in take:
                shares = (target * (1.0 - COST)) / px
                positions[code] = Position(
                    code=code,
                    kind=kind,
                    entry_date=d,
                    entry_px=px,
                    entry_falsify=float(fz) if fz is not None else None,
                    shares=shares,
                    last_px=px,
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

        pending_prev = pending_now
        eq = equity_now()
        equity_rows.append({"date": d, "equity": eq, "n_open": len(positions)})

    # liquidate remainder at last eval close
    last_d = calendar[-1] if calendar else EVAL_END
    for code, p in list(positions.items()):
        px = p.last_px
        cash += p.shares * px * (1.0 - COST)
        trades.append(
            {
                "code": code,
                "kind": p.kind,
                "entry_date": p.entry_date,
                "entry_px": round(p.entry_px, 6),
                "exit_date": last_d,
                "exit_px": round(px, 6),
                "exit_reason": "eod_eval",
                "weeks_held": p.weeks,
                "ret_net": round(net_ret(p.entry_px, px), 6),
                "max_positions": MAX_POS_LABEL[max_pos],
                "falsify_mode": falsify_mode,
            }
        )
        positions.pop(code)
    if equity_rows:
        equity_rows[-1]["equity"] = cash
        equity_rows[-1]["n_open"] = 0
    return trades, equity_rows


# ---------------------------------------------------------------------------
# Metrics / plots
# ---------------------------------------------------------------------------

def max_drawdown(eq: list[float]) -> float:
    peak = -1e9
    dd = 0.0
    for x in eq:
        peak = max(peak, x)
        if peak > 0:
            dd = min(dd, x / peak - 1.0)
    return dd


def weekly_rets(eq: list[float]) -> list[float]:
    out = []
    for i in range(1, len(eq)):
        if eq[i - 1] > 0:
            out.append(eq[i] / eq[i - 1] - 1.0)
    return out


def sharpe_weekly(rets: list[float]) -> float | None:
    if len(rets) < 8:
        return None
    mu = sum(rets) / len(rets)
    var = sum((r - mu) ** 2 for r in rets) / (len(rets) - 1)
    sd = math.sqrt(var)
    if sd == 0:
        return None
    return (mu / sd) * math.sqrt(52.0)


def cagr(eq0: float, eq1: float, n_weeks: int) -> float | None:
    if eq0 <= 0 or n_weeks <= 0:
        return None
    years = n_weeks / 52.0
    if years <= 0:
        return None
    return (eq1 / eq0) ** (1.0 / years) - 1.0


def summarize(trades: list[dict[str, Any]], eq_rows: list[dict[str, Any]]) -> dict[str, Any]:
    closed = [t for t in trades if t["exit_reason"] != "eod_eval"]
    all_t = trades
    use = all_t  # include eod marks so open P&L is in expectancy
    n = len(use)
    wins = sum(1 for t in use if t["ret_net"] > 0)
    rets = [t["ret_net"] for t in use]
    weeks = [t["weeks_held"] for t in use]
    by_kind: dict[str, dict[str, Any]] = {}
    for kind in ("tight_long", "spike_ft"):
        kt = [t for t in use if t["kind"] == kind]
        by_kind[kind] = {
            "n": len(kt),
            "win_rate": (sum(1 for t in kt if t["ret_net"] > 0) / len(kt)) if kt else None,
            "avg_ret": (sum(t["ret_net"] for t in kt) / len(kt)) if kt else None,
        }
    reasons = Counter(t["exit_reason"] for t in use)
    eq = [r["equity"] for r in eq_rows]
    wr = weekly_rets(eq)
    return {
        "n_trades": n,
        "n_closed": len(closed),
        "n_eod_open": sum(1 for t in use if t["exit_reason"] == "eod_eval"),
        "win_rate": (wins / n) if n else None,
        "avg_ret": (sum(rets) / n) if n else None,
        "expectancy": (sum(rets) / n) if n else None,
        "median_weeks": (sorted(weeks)[len(weeks) // 2] if weeks else None),
        "total_return": (eq[-1] / eq[0] - 1.0) if len(eq) >= 2 else (eq[-1] - 1.0 if eq else None),
        "CAGR": cagr(eq[0], eq[-1], max(0, len(eq) - 1)) if eq else None,
        "max_dd": max_drawdown(eq) if eq else None,
        "sharpe_weekly": sharpe_weekly(wr),
        "exit_reasons": dict(reasons),
        "by_kind": by_kind,
        "final_equity": eq[-1] if eq else None,
    }


def plot_equity(
    series: dict[str, list[tuple[str, float]]],
    path: Path,
    title: str = "In-play long · weekly equity (recompute falsify)",
) -> None:
    fig, ax = plt.subplots(figsize=(10.5, 5.2))
    fig.patch.set_facecolor("#F8F7F3")
    ax.set_facecolor("#F8F7F3")
    colors = {
        "max5": "#9C3B2C",
        "max10": "#1F6B4A",
        "unlimited": "#1A1917",
        "510300": "#8A6A2F",
        "universe_ew": "#4A463F",
    }
    styles = {
        "max5": "-",
        "max10": "-",
        "unlimited": "-",
        "510300": "--",
        "universe_ew": ":",
    }
    for name, pts in series.items():
        if not pts:
            continue
        xs = [date.fromisoformat(d) for d, _ in pts]
        ys = [v for _, v in pts]
        ax.plot(xs, ys, styles.get(name, "-"), color=colors.get(name, "#1A1917"), lw=1.4, label=name)
    ax.axhline(1.0, color="#C8C2B6", lw=0.8)
    ax.set_title(title)
    ax.set_ylabel("equity (start = 1)")
    ax.legend(frameon=False, fontsize=9)
    ax.grid(True, color="#C8C2B6", lw=0.4)
    for spine in ax.spines.values():
        spine.set_color("#C8C2B6")
    fig.tight_layout()
    fig.savefig(path, dpi=140)
    plt.close(fig)


def plot_winrate(summary: dict[str, Any], path: Path) -> None:
    labels = []
    tight = []
    spike = []
    for key in ("5", "10", "unlimited"):
        block = ((summary.get("recompute") or {}).get(key) or {})
        bk = block.get("by_kind") or {}
        labels.append(f"max {key}")
        tight.append((bk.get("tight_long") or {}).get("win_rate") or 0.0)
        spike.append((bk.get("spike_ft") or {}).get("win_rate") or 0.0)
    x = list(range(len(labels)))
    w = 0.36
    fig, ax = plt.subplots(figsize=(8.2, 4.4))
    fig.patch.set_facecolor("#F8F7F3")
    ax.set_facecolor("#F8F7F3")
    ax.bar([i - w / 2 for i in x], [v * 100 for v in tight], w, color="#1F6B4A", label="tight_long")
    ax.bar([i + w / 2 for i in x], [v * 100 for v in spike], w, color="#9C3B2C", label="spike_ft")
    ax.set_xticks(x)
    ax.set_xticklabels(labels)
    ax.set_ylabel("win rate %")
    ax.set_title("Win rate by in_play_kind (recompute falsify)")
    ax.legend(frameon=False)
    ax.grid(True, axis="y", color="#C8C2B6", lw=0.4)
    for spine in ax.spines.values():
        spine.set_color("#C8C2B6")
    fig.tight_layout()
    fig.savefig(path, dpi=140)
    plt.close(fig)


# ---------------------------------------------------------------------------
# Sanity / README
# ---------------------------------------------------------------------------

def board_inplay_codes() -> tuple[set[str], set[str]]:
    if not SCAN_JSON.exists():
        return set(), set()
    data = json.loads(SCAN_JSON.read_text(encoding="utf-8"))
    enter, pending = set(), set()
    for r in data.get("rows") or []:
        if r.get("in_play") and r.get("in_play_kind") in ENTER_KINDS:
            enter.add(r["code"])
        if r.get("in_play_kind") == "box_pending" or r.get("pending_second_week"):
            pending.add(r["code"])
    return enter, pending


def write_readme(
    summary: dict[str, Any],
    sanity: dict[str, Any],
    n_univ: int,
    n_ok: int,
    n_thin: int,
    n_fail: int,
) -> None:
    rec = summary["recompute"]
    frz = summary["frozen"]

    def pct(x):
        return "—" if x is None else f"{100 * x:.1f}%"

    lines = []
    lines.append("# 「在结构里」多头周线回测 / In-play long weekly backtest")
    lines.append("")
    lines.append(
        f"Evaluation `{EVAL_START}` → `{EVAL_END}`. Universe {n_univ} champion ETFs "
        f"(Yang 20260830). Weekly Tencent qfq; Yahoo fallback. "
        f"Downloaded {n_ok}, failed {n_fail}, thin_history (<30 weeks at some point) {n_thin}."
    )
    lines.append("")
    lines.append("Signal = board `classify()` unchanged, causal: bars through week t only. ")
    lines.append("Enter Friday close when `in_play` and `in_play_kind` ∈ {tight_long, spike_ft}. ")
    lines.append("Do not enter `box_pending` / `short_mtr`. Long-only. Equal weight among open names. ")
    lines.append("Round-trip 0.2%. Cash = 0. Primary exit uses **recomputed** `falsify_close` each week.")
    lines.append("")
    lines.append("## Headline (primary = recompute falsify)")
    lines.append("")
    lines.append("| max_pos | n_trades | win_rate | total_return | max_dd | CAGR | Sharpe_w |")
    lines.append("|---|---:|---:|---:|---:|---:|---:|")
    for key in ("5", "10", "unlimited"):
        s = rec[key]
        lines.append(
            f"| {key} | {s['n_trades']} | {pct(s['win_rate'])} | {pct(s['total_return'])} | "
            f"{pct(s['max_dd'])} | {pct(s['CAGR'])} | "
            f"{'—' if s['sharpe_weekly'] is None else format(s['sharpe_weekly'], '.2f')} |"
        )
    lines.append("")
    lines.append("Benchmarks (same window): "
                 f"510300 buy&hold {pct(summary['benchmark']['bh_510300'])}, "
                 f"universe equal-weight weekly {pct(summary['benchmark']['universe_ew'])}.")
    lines.append("")
    lines.append("## Does 「在结构里」 long work?")
    s5, su = rec["5"], rec["unlimited"]
    vs = summary["benchmark"]["bh_510300"]
    def beat(a, b):
        if a is None or b is None:
            return "n/a"
        return "ahead of" if a > b else "behind"
    lines.append(
        f"Unlimited book {pct(su['total_return'])} total, max DD {pct(su['max_dd'])}, "
        f"{beat(su['total_return'], vs)} 510300 ({pct(vs)}). "
        f"Capped-5 {pct(s5['total_return'])}, win rate {pct(s5['win_rate'])}. "
        f"tight_long win rate {pct((s5['by_kind']['tight_long'] or {}).get('win_rate'))}; "
        f"spike_ft {pct((s5['by_kind']['spike_ft'] or {}).get('win_rate'))}."
    )
    lines.append("")
    lines.append("## Which exit matters? (recompute, unlimited)")
    lines.append("")
    er = su.get("exit_reasons") or {}
    lines.append(
        f"falsify {er.get('falsify', 0)}, always_in_flip {er.get('always_in_flip', 0)}, "
        f"left_structure {er.get('left_structure', 0)}, eod_eval {er.get('eod_eval', 0)}."
    )
    f5 = frz["unlimited"]
    lines.append(
        f"Frozen falsify (unlimited) total {pct(f5['total_return'])} vs recompute {pct(su['total_return'])} "
        f"— primary is the live-board rule (falsify moves with the channel)."
    )
    lines.append("")
    lines.append("## Frozen falsify (appendix)")
    lines.append("")
    lines.append("| max_pos | n_trades | win_rate | total_return | max_dd |")
    lines.append("|---|---:|---:|---:|---:|")
    for key in ("5", "10", "unlimited"):
        s = frz[key]
        lines.append(
            f"| {key} | {s['n_trades']} | {pct(s['win_rate'])} | {pct(s['total_return'])} | {pct(s['max_dd'])} |"
        )
    lines.append("")
    lines.append("## Sanity")
    lines.append("")
    lines.append(
        f"Signal-weeks (name×week with tight_long/spike_ft in eval): {sanity['n_signal_weeks']}. "
        f"Unique names that ever signaled: {sanity['n_signal_names']}. "
        f"Walk-forward 2026-08-28 enter-set overlap with board in-play longs: "
        f"{sanity['overlap_n']}/{sanity['board_n']} "
        f"(walk {sanity['walk_n']}, missing {sanity['missing']}, extra {sanity['extra']})."
    )
    lines.append("")
    lines.append("## Caveats")
    lines.append("")
    lines.append(
        "- **Pivots:** `swing_indices` needs 2 bars on the right. At week t the last two bars cannot be confirmed swings — same as the live board, not future-bar leak."
    )
    lines.append(
        "- **2025-01-01 swing-high cutoff** is inside `classify()` (2025–2026 high). Before 2025 it falls back to the full available series. Not a new Always In definition."
    )
    lines.append(
        "- **History length:** this walk uses 2023-01+ bars; the published board used 2024-01+. Recent 16–22 bar channel/climax logic is unchanged; older swings can theoretically change the last impulse pair used for magnet/falsify."
    )
    lines.append(
        "- **QDII / holidays:** weekly stamps can be off by a few days; we align ±3 calendar days to the 510300 Friday grid."
    )
    lines.append(
        "- **qfq / rolls:** front-adjusted closes. Corporate actions are in the series; we do not model creation/redemption friction beyond 0.2%."
    )
    lines.append(
        "- **Turnover:** the unchanged classifier is on ~19% of name-weeks and usually dies in 1–3 weeks (median hold 2–3). Unlimited books thousands of round-trips; costs matter. This is the board rule, not a slower filter."
    )
    lines.append(
        "- **Small n per name:** many ETFs fire once or twice. Kind-level stats are more informative than single-ticker records."
    )
    lines.append(
        "- **Cap ranking** when signals exceed max_positions: tight_long first, then spike_ft, then larger AUM, then code. No look-ahead in the rank."
    )
    lines.append(
        "- Structure-signal backtest only. 只报结构，不荐股。"
    )
    lines.append("")
    OUT.joinpath("README.md").write_text("\n".join(lines) + "\n", encoding="utf-8")


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main() -> None:
    t0 = time.time()
    OUT.mkdir(parents=True, exist_ok=True)
    universe = load_universe()
    codes = [u["code"] for u in universe]
    aum = {u["code"]: (u["aum"] or 0.0) for u in universe}
    print(f"universe {len(codes)}", flush=True)

    raws = download_all(codes)
    n_ok = sum(1 for r in raws.values() if r.get("bars"))
    n_fail = sum(1 for r in raws.values() if not r.get("bars"))
    n_thin = sum(1 for r in raws.values() if 0 < len(r.get("bars") or []) < 30)
    print(f"downloaded ok={n_ok} fail={n_fail} thin_now={n_thin}", flush=True)

    by_code = build_signals(universe, raws)
    print(f"classified {len(by_code)} names in {time.time()-t0:.1f}s", flush=True)

    closes = {c: close_map(raws.get(c) or {}) for c in codes}
    snaps = {c: snap_index(by_code.get(c) or []) for c in codes}

    cal_src = closes.get("510300") or {}
    calendar = sorted(d for d in cal_src if EVAL_START <= d <= EVAL_END)
    if not calendar:
        raise SystemExit("no 510300 calendar in eval window")
    print(f"calendar {calendar[0]} → {calendar[-1]} n={len(calendar)}", flush=True)

    # date aliases per code for ±3d alignment
    date_alias: dict[str, dict[str, str]] = {}
    for c in codes:
        ds = list(closes.get(c, {}))
        if not ds:
            continue
        alias = {}
        for d in calendar:
            hit = nearest_date(d, ds, 3)
            if hit:
                alias[d] = hit
        date_alias[c] = alias

    # signal-week counts (eval)
    n_sig_weeks = 0
    sig_names: set[str] = set()
    for c, smap in snaps.items():
        for d, s in smap.items():
            if not (EVAL_START <= d <= EVAL_END):
                continue
            if s.get("in_play") and s.get("in_play_kind") in ENTER_KINDS:
                n_sig_weeks += 1
                sig_names.add(c)

    # overlap vs board as-of 2026-08-28
    board_enter, _board_pend = board_inplay_codes()
    walk_enter = set()
    for c, smap in snaps.items():
        s = smap.get("2026-08-28")
        if not s:
            alias = date_alias.get(c, {}).get("2026-08-28")
            s = smap.get(alias) if alias else None
        if s and s.get("in_play") and s.get("in_play_kind") in ENTER_KINDS:
            walk_enter.add(c)
    overlap = board_enter & walk_enter
    sanity = {
        "n_signal_weeks": n_sig_weeks,
        "n_signal_names": len(sig_names),
        "board_n": len(board_enter),
        "walk_n": len(walk_enter),
        "overlap_n": len(overlap),
        "missing": sorted(board_enter - walk_enter),
        "extra": sorted(walk_enter - board_enter),
    }
    print("SANITY signal-weeks", n_sig_weeks, "names", len(sig_names), flush=True)
    print(
        f"SANITY 2026-08-28 overlap {len(overlap)}/{len(board_enter)} "
        f"walk={len(walk_enter)} missing={sanity['missing'][:12]} extra={sanity['extra'][:12]}",
        flush=True,
    )

    # benchmarks
    p0 = cal_src[calendar[0]]
    bh = [(d, cal_src[d] / p0) for d in calendar if d in cal_src]
    ew = []
    prev_px: dict[str, float] = {}
    eq_ew = 1.0
    for i, d in enumerate(calendar):
        rets = []
        now_px = {}
        for c in codes:
            px = closes[c].get(date_alias.get(c, {}).get(d, d))
            if px is None:
                continue
            now_px[c] = px
            if i > 0 and c in prev_px and prev_px[c] > 0:
                rets.append(px / prev_px[c] - 1.0)
        if i > 0 and rets:
            eq_ew *= 1.0 + (sum(rets) / len(rets))
        ew.append((d, eq_ew))
        prev_px = now_px
    bh_ret = bh[-1][1] - 1.0 if bh else None
    ew_ret = ew[-1][1] - 1.0 if ew else None
    print(f"BH 510300 {bh_ret}  EW {ew_ret}", flush=True)

    all_trades: list[dict[str, Any]] = []
    equity_out: list[dict[str, Any]] = []
    summary: dict[str, Any] = {
        "eval_start": EVAL_START,
        "eval_end": EVAL_END,
        "asof_board": "2026-08-28",
        "cost_roundtrip": 0.002,
        "n_universe": len(codes),
        "n_downloaded": n_ok,
        "n_failed": n_fail,
        "n_thin": n_thin,
        "n_weeks": len(calendar),
        "benchmark": {"bh_510300": bh_ret, "universe_ew": ew_ret},
        "sanity": sanity,
        "recompute": {},
        "frozen": {},
    }
    eq_plot: dict[str, list[tuple[str, float]]] = {
        "510300": bh,
        "universe_ew": ew,
    }

    for mode in ("recompute", "frozen"):
        for mp in MAX_POS_VARIANTS:
            label = MAX_POS_LABEL[mp]
            print(f"simulate {mode} max={label}", flush=True)
            trades, eq_rows = simulate(
                calendar, snaps, closes, aum, mp, mode, date_alias
            )
            for t in trades:
                all_trades.append(t)
            bh_map = dict(bh)
            ew_map = dict(ew)
            for r in eq_rows:
                equity_out.append(
                    {
                        "date": r["date"],
                        "equity": round(r["equity"], 8),
                        "n_open": r["n_open"],
                        "benchmark_510300": round(bh_map.get(r["date"], float("nan")), 8),
                        "universe_ew": round(ew_map.get(r["date"], float("nan")), 8),
                        "max_positions": label,
                        "falsify_mode": mode,
                    }
                )
            summary[mode][label] = summarize(trades, eq_rows)
            if mode == "recompute":
                key = {"5": "max5", "10": "max10", "unlimited": "unlimited"}[label]
                eq_plot[key] = [(r["date"], r["equity"]) for r in eq_rows]
            # first/last trades print
            if mode == "recompute" and label == "unlimited":
                show = trades
                print("FIRST 10 trades (unlimited/recompute):", flush=True)
                for t in show[:10]:
                    print(
                        f"  {t['entry_date']} {t['code']} {t['kind']} → {t['exit_date']} "
                        f"{t['exit_reason']} {t['ret_net']:+.2%} {t['weeks_held']}w",
                        flush=True,
                    )
                print("LAST 10 trades:", flush=True)
                for t in show[-10:]:
                    print(
                        f"  {t['entry_date']} {t['code']} {t['kind']} → {t['exit_date']} "
                        f"{t['exit_reason']} {t['ret_net']:+.2%} {t['weeks_held']}w",
                        flush=True,
                    )

    # write files
    with (OUT / "trades.csv").open("w", encoding="utf-8", newline="") as f:
        cols = [
            "max_positions",
            "falsify_mode",
            "code",
            "kind",
            "entry_date",
            "entry_px",
            "exit_date",
            "exit_px",
            "exit_reason",
            "weeks_held",
            "ret_net",
        ]
        w = csv.DictWriter(f, fieldnames=cols, extrasaction="ignore")
        w.writeheader()
        for t in all_trades:
            w.writerow(t)

    with (OUT / "equity.csv").open("w", encoding="utf-8", newline="") as f:
        cols = [
            "date",
            "equity",
            "n_open",
            "benchmark_510300",
            "universe_ew",
            "max_positions",
            "falsify_mode",
        ]
        w = csv.DictWriter(f, fieldnames=cols)
        w.writeheader()
        for r in equity_out:
            w.writerow(r)

    (OUT / "summary.json").write_text(
        json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    plot_equity(eq_plot, OUT / "equity.png")
    plot_winrate(summary, OUT / "winrate_by_kind.png")
    write_readme(summary, sanity, len(codes), n_ok, n_thin, n_fail)

    print("\n=== HEADLINE recompute ===", flush=True)
    for key in ("5", "10", "unlimited"):
        s = summary["recompute"][key]
        wr = "—" if s["win_rate"] is None else f"{100*s['win_rate']:.1f}%"
        tr = "—" if s["total_return"] is None else f"{100*s['total_return']:.1f}%"
        dd = "—" if s["max_dd"] is None else f"{100*s['max_dd']:.1f}%"
        print(f"  max={key:9}  win={wr:7}  ret={tr:8}  dd={dd:8}  n={s['n_trades']}", flush=True)
    print(f"wrote {OUT} in {time.time()-t0:.1f}s", flush=True)


if __name__ == "__main__":
    main()
