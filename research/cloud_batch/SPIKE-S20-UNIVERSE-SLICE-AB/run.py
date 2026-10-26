#!/usr/bin/env python3
"""SPIKE-S20-UNIVERSE-SLICE-AB — research only.

Same B45+S20 face as SPIKE-S20-EXTEND (breadth risk_on from face; spike_ft max5;
SHARPE20; Fri 14:30/close; 0.2% RT; L≤1; TV25). Two **separate** books (no mixing):

  (A) CN broad ETFs only — `etf-correlation/data/research_pool_v2.csv` family 宽基·*
  (B) CN sector/theme only — family 行业·* or 主题·* (l0=中国权益)

Reference row: full research pool B45 from extend batch (not re-simulated here).
"""
from __future__ import annotations

import importlib.util
import json
import math
import sys
import time
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

OUT = Path(__file__).resolve().parent
EXTEND_DIR = OUT.parent / "SPIKE-S20-EXTEND-REBASE-LIVE1430"
POOL_CSV = OUT.parents[2] / "etf-correlation" / "data" / "research_pool_v2.csv"
KIT = OUT.parent / "CLOUD-BATCH-2026-10-26"
sys.path.insert(0, str(KIT / "scripts"))

# Load extend engine (simulate, run_live_tv, loaders, …)
_spec = importlib.util.spec_from_file_location("spike_extend", EXTEND_DIR / "run.py")
if _spec is None or _spec.loader is None:
    raise SystemExit("cannot load spike extend run.py")
spike = importlib.util.module_from_spec(_spec)
sys.modules["spike_extend"] = spike
_spec.loader.exec_module(spike)

# Point kit at checked-in CLOUD-BATCH tree
spike.KIT = KIT
spike.CACHE = KIT / "data" / "research_cache"
spike.WEEK = spike.CACHE / "week"
spike.FACE = spike.CACHE / "holdings_ro2_extended.csv"
spike.DAY_DIR = spike.CACHE / "day"
spike.NOON_CSV = spike.CACHE / "fri_1430_through_20261023.csv"
spike.SINA_DAILY = spike.CACHE / "sina_daily"
spike.UNI_CSV = KIT / "data" / "universe_replace_only_436.csv"
spike.SNAP_CACHE = EXTEND_DIR / "cache_1430_snaps.json"
spike.OUT = OUT

EVAL_START = spike.EVAL_START
END_S = spike.END_S
SIGMA_STAR = spike.SIGMA_STAR
MAX_POS = spike.MAX_POS


def load_pool_slices() -> tuple[set[str], set[str], pd.DataFrame]:
    if not POOL_CSV.exists():
        raise SystemExit(f"missing pool grouping {POOL_CSV}")
    pool = pd.read_csv(POOL_CSV)
    pool["code"] = pool["code"].astype(str).str.zfill(6)
    cn = pool[pool["l0"] == "中国权益"].copy()
    broad = set(cn[cn["family"].str.startswith("宽基", na=False)]["code"])
    sect = set(
        cn[cn["family"].str.startswith(("行业·", "主题·"), na=False)]["code"]
    )
    return broad, sect, pool


def filter_snaps(snaps: dict[str, Any], allowed: set[str]) -> dict[str, Any]:
    return {c: snaps[c] for c in snaps if c in allowed}


def avg_turnover(hold: dict[str, list[str]], calendar: list[str]) -> float:
    to_vals: list[float] = []
    prev: set[str] = set()
    for d in calendar[:-1]:
        cur = set(hold.get(d) or [])
        if prev or cur:
            to_vals.append(len(prev.symmetric_difference(cur)) / (2.0 * MAX_POS))
        prev = cur
    return float(np.mean(to_vals)) if to_vals else 0.0


def diversification_note(
    hold: dict[str, list[str]],
    calendar: list[str],
    pool: pd.DataFrame,
    label: str,
) -> dict[str, Any]:
    fam_map = dict(zip(pool["code"], pool["family"]))
    name_map = dict(zip(pool["code"], pool["name"]))
    all_held: list[str] = []
    fam_counts: Counter[str] = Counter()
    for d in calendar[:-1]:
        for c in hold.get(d) or []:
            all_held.append(c)
            fam_counts[fam_map.get(c, "?")] += 1
    uniq = sorted(set(all_held))
    n_weeks = max(1, len(calendar) - 1)
    avg_names = len(uniq)
    top_fams = fam_counts.most_common(5)
    note = (
        f"{label}: {len(uniq)} distinct ETFs ever held; "
        f"avg concurrent slots ~{np.mean([len(hold.get(d) or []) for d in calendar[:-1]]):.2f}; "
        f"top families by slot-weeks: "
        + ", ".join(f"{f}({n})" for f, n in top_fams[:3])
    )
    return {
        "n_distinct_etfs": len(uniq),
        "top_families": top_fams,
        "held_codes_sample": uniq[:12],
        "note": note,
        "names": {c: name_map.get(c, c) for c in uniq[:8]},
    }


def load_panel() -> dict[str, Any]:
    """Reuse extend data pipeline; return shared panel + full snaps."""
    for p in (
        spike.WEEK,
        spike.FACE,
        spike.DAY_DIR,
        spike.NOON_CSV,
        spike.SINA_DAILY,
    ):
        if not Path(p).exists():
            raise SystemExit(f"missing research cache path {p}")

    uni = pd.read_csv(spike.UNI_CSV)
    uni["code"] = uni["code"].astype(str).str.zfill(6)
    uni = uni[uni["aum"] >= 2].copy()
    codes = uni["code"].tolist()
    aum = {r.code: float(r.aum or 0) for r in uni.itertuples()}
    code_set = set(codes)

    noon = pd.read_csv(spike.NOON_CSV)
    noon["code"] = noon["etf_code"].astype(str).str.split(".").str[0]
    noon["trade_date"] = noon["trade_date"].astype(str).str[:10]
    noon["friday_week_date"] = noon["friday_week_date"].astype(str).str[:10]
    noon = noon[noon["code"].isin(code_set)].copy()
    if "price_1430" in noon.columns and "price_1130" not in noon.columns:
        noon["price_1130"] = noon["price_1430"]

    face = pd.read_csv(spike.FACE)
    face["date"] = face["date"].astype(str).str[:10]
    face = face[(face["date"] >= EVAL_START) & (face["date"] <= END_S)].copy()
    calendar = sorted(face["date"].unique().tolist())
    if not calendar:
        raise SystemExit("empty calendar")
    actual_end = calendar[-1]

    risk_b45: dict[str, bool] = {}
    for _, row in face.iterrows():
        d = str(row["date"])[:10]
        v = row["risk_on"]
        if isinstance(v, (bool, np.bool_)):
            risk_b45[d] = bool(v)
        else:
            risk_b45[d] = str(v).lower() in {"1", "true", "True"}
    for d in calendar:
        risk_b45.setdefault(d, False)
    risk_b45[calendar[-1]] = False

    raws_w: dict[str, dict[str, Any]] = {}
    closes_w_close: dict[str, dict[str, float]] = {}
    for c in codes:
        fp = spike.WEEK / f"{c}.json"
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
        if not ds:
            continue
        alias[c] = {d: hit for d in calendar if (hit := spike.nearest_date(d, ds, 3))}

    sina = spike.load_sina_closes(codes)
    daily = spike.load_daily_closes(codes, sina)

    noon_w: dict[str, dict[str, float]] = defaultdict(dict)
    blocked_empty: dict[str, set[str]] = defaultdict(set)
    for r in noon.itertuples():
        td = r.trade_date
        if td < EVAL_START or td > END_S:
            continue
        if r.status == "empty" or (
            r.status == "ok"
            and (
                r.price_1130 is None
                or (isinstance(r.price_1130, float) and math.isnan(r.price_1130))
            )
        ):
            blocked_empty[td].add(r.code)
            continue
        if r.status != "ok":
            continue
        q = None
        if r.code in daily:
            ser = daily[r.code]
            ts = pd.Timestamp(td)
            if ts in ser.index:
                q = float(ser.loc[ts])
            else:
                sub = ser.loc[:ts]
                if len(sub) and (ts - sub.index[-1]).days <= 3:
                    q = float(sub.iloc[-1])
        b = (sina.get(r.code) or {}).get(td)
        if not b or b <= 0:
            blocked_empty[td].add(r.code)
            continue
        if not q or q <= 0:
            q = float(b)
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

    if not spike.SNAP_CACHE.exists():
        raise SystemExit(f"missing snap cache {spike.SNAP_CACHE}")
    cached = json.loads(spike.SNAP_CACHE.read_text(encoding="utf-8"))
    by_rows = cached.get("by_code") or {}
    snaps = {c: spike.snap_index(by_rows.get(c) or []) for c in codes}

    return {
        "calendar": calendar,
        "actual_end": actual_end,
        "codes": codes,
        "aum": aum,
        "daily": daily,
        "alias": alias,
        "closes_w_sig": closes_w_sig,
        "snaps": snaps,
        "risk_b45": risk_b45,
        "n_codes": len(codes),
    }


def run_book(
    name: str,
    panel: dict[str, Any],
    allowed: set[str],
    pool: pd.DataFrame,
) -> dict[str, Any]:
    snaps = filter_snaps(panel["snaps"], allowed)
    calendar = panel["calendar"]
    trades, hold, st = spike.simulate(
        calendar,
        snaps,
        panel["closes_w_sig"],
        panel["alias"],
        panel["aum"],
        panel["daily"],
        panel["risk_b45"],
        spike.sharpe_key,
        name,
        True,
        20,
        MAX_POS,
    )
    st["avgTO"] = avg_turnover(hold, calendar)
    div = diversification_note(hold, calendar, pool, name)

    rows = []
    for d in calendar[:-1]:
        codes_h = hold.get(d) or []
        rows.append(
            {
                "date": d,
                "risk_on": int(panel["risk_b45"].get(d, False)),
                "n_held": len(codes_h),
                "codes": ",".join(codes_h),
            }
        )
    pd.DataFrame(rows).to_csv(OUT / f"holdings_{name}.csv", index=False)
    pd.DataFrame(trades).to_csv(OUT / f"trades_{name}.csv", index=False)

    all_codes: set[str] = set()
    for cs in hold.values():
        all_codes |= set(cs)
    px_map = {c: panel["daily"][c] for c in all_codes if c in panel["daily"]}
    px = pd.DataFrame(px_map).sort_index()
    px = px.loc[(px.index >= EVAL_START) & (px.index <= END_S)]
    R = px.pct_change()
    if "510300" in px.columns:
        days = px["510300"].dropna().index
    else:
        days = px.dropna(how="all").index
    days = days[(days >= EVAL_START) & (days <= END_S)]

    hd = {pd.Timestamp(d): cs for d, cs in hold.items()}
    r, L = spike.run_live_tv(hd, days, px, R, sigma_star=SIGMA_STAR, cash_fill=None)
    row = spike.metrics_row(name, r, L, st)
    row["avgTO"] = st["avgTO"]
    row["n_pool_codes"] = len(allowed)
    row["diversification"] = div["note"]
    nav = (1 + r).cumprod()
    nav.to_csv(OUT / f"nav_{name}.csv", header=["nav"])
    return {
        "row": row,
        "returns": r,
        "hold": hold,
        "sim": st,
        "div": div,
        "trades": trades,
    }


def load_ref_b45() -> dict[str, Any]:
    ref_path = EXTEND_DIR / "metrics.csv"
    if not ref_path.exists():
        return {}
    df = pd.read_csv(ref_path)
    sub = df[df["book"] == "LIVE1430-B45-S20"]
    if sub.empty:
        return {}
    r = sub.iloc[0].to_dict()
    return {
        "book": "REF-FULL-POOL-B45-S20",
        "ret": r.get("ret"),
        "maxDD": r.get("maxDD"),
        "CAGR": r.get("CAGR"),
        "Calmar": r.get("Calmar"),
        "avgTO": float("nan"),
        "cash_week_pct": r.get("cash_week_pct"),
        "note": "Full research pool (extend batch); not re-run this slice job.",
    }


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    t0 = time.time()
    broad, sect, pool = load_pool_slices()

    uni = pd.read_csv(spike.UNI_CSV)
    uni["code"] = uni["code"].astype(str).str.zfill(6)
    u = set(uni[uni["aum"] >= 2]["code"])
    allowed_a = broad & u
    allowed_b = sect & u
    print(f"pool slice A broad: {len(allowed_a)} codes; B sector/theme: {len(allowed_b)}", flush=True)
    if allowed_a & allowed_b:
        raise SystemExit("A/B overlap — fix pool grouping")

    print("load shared panel…", flush=True)
    panel = load_panel()

    books = [
        ("RES-B45-S20-A-BROAD", allowed_a),
        ("RES-B45-S20-B-SECTOR-THEME", allowed_b),
    ]
    results: list[dict[str, Any]] = []
    series: dict[str, pd.Series] = {}
    for name, allowed in books:
        print(f"simulate {name}…", flush=True)
        res = run_book(name, panel, allowed, pool)
        results.append(res)
        series[name] = res["returns"]
        st = res["sim"]
        print(
            f"  ret={spike.pct(res['row']['ret'])} mdd={spike.pct(res['row']['maxDD'])} "
            f"avgTO={res['row']['avgTO']:.3f} entries={st['n_entries']}",
            flush=True,
        )
        print(f"  {res['div']['note']}", flush=True)

    table = pd.DataFrame([r["row"] for r in results])
    ref = load_ref_b45()
    if ref:
        table = pd.concat([table, pd.DataFrame([ref])], ignore_index=True)
    table.to_csv(OUT / "metrics.csv", index=False)
    table.to_csv(OUT / "table.csv", index=False)

    eq = pd.DataFrame({k: (1 + series[k]).cumprod() for k in series})
    eq.to_csv(OUT / "equity.csv")

    fig, ax = plt.subplots(figsize=(10, 5), dpi=120)
    for name in series:
        ax.plot(eq.index, eq[name], label=name, lw=1.8)
    ax.set_yscale("log")
    ax.set_title("SPIKE-S20 B45 face · universe slice A/B (research)")
    ax.set_ylabel("NAV (log)")
    ax.grid(True, alpha=0.3)
    ax.legend(fontsize=8)
    fig.tight_layout()
    fig.savefig(OUT / "equity_curve.png")
    plt.close(fig)

    a_row = results[0]["row"]
    b_row = results[1]["row"]
    div_a = results[0]["div"]
    div_b = results[1]["div"]

    report = f"""# REPORT · SPIKE-S20-UNIVERSE-SLICE-AB

**性质**：研究批；**非 LIVE**；不换冠；不写 strategy_exec / LIVE_OPS。

## 问题

同一 **B45+S20** 面层（breadth risk_on 来自 face；spike_ft max5；SHARPE20；Fri≥14:30/收盘；0.2% RT；L≤1；TV25），仅更换**候选池切片**（单簿不混类）：

| 切片 | 分组来源 | 规则 |
|---|---|---|
| **A** | `etf-correlation/data/research_pool_v2.csv` | `l0=中国权益` 且 `family` 以 `宽基` 开头 |
| **B** | 同上 | `l0=中国权益` 且 `family` 以 `行业·` 或 `主题·` 开头 |

窗：{EVAL_START} → {panel['actual_end']}；可投池全量 {panel['n_codes']}（AUM≥2亿）。

## 主表（ret / MDD / turnover）

| book | n_pool | ret | maxDD | Calmar | avgTO | cash周% | trades |
|---|---:|---:|---:|---:|---:|---:|---:|
| {a_row['book']} | {a_row['n_pool_codes']} | {spike.pct(a_row['ret'])} | {spike.pct(a_row['maxDD'])} | {a_row['Calmar']:.2f} | {a_row['avgTO']:.3f} | {100*a_row['cash_week_pct']:.1f}% | {results[0]['sim']['n_trades']} |
| {b_row['book']} | {b_row['n_pool_codes']} | {spike.pct(b_row['ret'])} | {spike.pct(b_row['maxDD'])} | {b_row['Calmar']:.2f} | {b_row['avgTO']:.3f} | {100*b_row['cash_week_pct']:.1f}% | {results[1]['sim']['n_trades']} |
| REF full pool B45 | {panel['n_codes']} | {spike.pct(ref.get('ret')) if ref else '—'} | {spike.pct(ref.get('maxDD')) if ref else '—'} | {ref.get('Calmar', float('nan')) if ref else '—'} | — | {100*ref.get('cash_week_pct', 0):.1f}% | — |

Δ(B−A) ret {(b_row['ret']-a_row['ret'])*100:+.1f}pp；Δ|MDD| {(abs(b_row['maxDD'])-abs(a_row['maxDD']))*100:+.1f}pp；ΔavgTO {b_row['avgTO']-a_row['avgTO']:+.3f}。

## 分散化旁注

- **A 宽基**：{div_a['note']}
- **B 行业/主题**：{div_b['note']}

宽基切片候选更少（{len(allowed_a)} 只），信号周常更「空」→ cash 周占比通常更高；行业/主题池更厚，换手与品种分散度更高，但子行业集中度（半导体、医药等）仍可能抬升同向风险。

## 红线

研究池分组仅用于本对比；**不得**将 A/B 标的混在同一账面。

耗时约 {round(time.time()-t0, 1)}s。
"""
    (OUT / "REPORT.md").write_text(report, encoding="utf-8")
    summary = {
        "title": "SPIKE-S20-UNIVERSE-SLICE-AB",
        "sample": f"{EVAL_START} → {panel['actual_end']}",
        "n_pool_a": len(allowed_a),
        "n_pool_b": len(allowed_b),
        "table": table.to_dict(orient="records"),
        "diversification": {"A": div_a, "B": div_b},
        "elapsed_sec": round(time.time() - t0, 1),
    }
    (OUT / "summary.json").write_text(
        json.dumps(summary, ensure_ascii=False, indent=2, default=str), encoding="utf-8"
    )
    print("done", OUT, flush=True)


if __name__ == "__main__":
    main()
