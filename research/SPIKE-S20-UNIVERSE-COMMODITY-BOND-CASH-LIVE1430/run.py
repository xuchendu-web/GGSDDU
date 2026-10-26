#!/usr/bin/env python3
"""SPIKE-S20-UNIVERSE-COMMODITY-BOND-CASH-LIVE1430 — research only.

B45+S20 face (spike_ft max5; SHARPE20; E0; Fri≥14:30/close; 0.2% RT; L≤1; TV25).
Separate books (no cross-category ranks):

  1) Commodity sleeve — research_pool `l0=商品`
  2) Bond/cash sleeve — `bond_cash_sleeve_labels.csv` (`l0=固收现金`)
  3) Side: 50/50 barbell on face calendar

Breadth: slice-local B45 only if n_pool≥BREADTH_MIN; else NA → risk_on always on
(absolute+relative spike filters only). Reference: full-pool A-share B45 face.
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
EXTEND_DIR = OUT.parent / "cloud_batch" / "SPIKE-S20-EXTEND-REBASE-LIVE1430"
POOL_CSV = OUT.parent.parent / "etf-correlation" / "data" / "research_pool_v2.csv"
BOND_LABELS = OUT / "bond_cash_sleeve_labels.csv"
BOND_DIR = OUT.parent / "cloud_batch" / "CLOUD-BATCH-2026-10-26" / "data" / "research_cache" / "bond_daily"
KIT = OUT.parent / "cloud_batch" / "CLOUD-BATCH-2026-10-26"
BREADTH_MIN = 20
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
    commodity = set(pool[pool["l0"] == "商品"]["code"])
    bond = pd.read_csv(BOND_LABELS)
    bond["code"] = bond["code"].astype(str).str.zfill(6)
    bond_cash = set(bond["code"])
    pool = pd.concat([pool, bond], ignore_index=True).drop_duplicates("code", keep="first")
    return commodity, bond_cash, pool


def extend_bond_backward(close: pd.Series, start: str, daily_drift: float = 0.00014) -> pd.Series:
    idx = pd.to_datetime(close.index).sort_values()
    s = close.astype(float).sort_index()
    first = s.index[0]
    need = pd.bdate_range(start, first - pd.Timedelta(days=1))
    if len(need) == 0:
        return s
    back: list[tuple[pd.Timestamp, float]] = []
    px = float(s.iloc[0])
    for d in reversed(need):
        px = px / (1.0 + daily_drift)
        back.append((pd.Timestamp(d), px))
    back_s = pd.Series({d: v for d, v in reversed(back)})
    out = pd.concat([back_s, s]).sort_index()
    return out[~out.index.duplicated(keep="last")]


def daily_to_week_raw(code: str, daily: pd.Series) -> dict[str, Any]:
    s = daily.sort_index()
    s = s[s.index <= pd.Timestamp(END_S)]
    bars: list[dict[str, float | str]] = []
    grp = s.resample("W-FRI").agg(["first", "max", "min", "last"]).dropna(how="all")
    for dt, row in grp.iterrows():
        c = float(row["last"])
        if c <= 0:
            continue
        o = float(row["first"]) if pd.notna(row["first"]) else c
        h = float(row["max"]) if pd.notna(row["max"]) else c
        l = float(row["min"]) if pd.notna(row["min"]) else c
        bars.append({"date": dt.strftime("%Y-%m-%d"), "o": o, "h": h, "l": l, "c": c})
    return {"code": code, "bars": bars}


def load_bond_daily(code: str) -> pd.Series:
    fp = BOND_DIR / f"{code}.csv"
    if not fp.exists():
        raise SystemExit(f"missing bond_daily/{code}.csv")
    df = pd.read_csv(fp, parse_dates=["date"])
    s = df.set_index("date")["close"].astype(float).sort_index()
    return extend_bond_backward(s, EVAL_START)


def risk_on_for_slice(
    calendar: list[str], face_risk: dict[str, bool], n_pool: int
) -> tuple[dict[str, bool], str]:
    if n_pool >= BREADTH_MIN:
        return face_risk, "face_B45_breadth"
    m = {d: True for d in calendar}
    m[calendar[-1]] = False
    return m, "NA_thin_slice"


def augment_panel_bond_codes(panel: dict[str, Any], bond_codes: set[str]) -> None:
    """Add bond/cash sleeve tickers (not in equity uni) with classify snaps."""
    calendar = panel["calendar"]
    extra = [c for c in bond_codes if c not in panel["codes"]]
    if not extra:
        return
    by_rows: dict[str, list] = {}
    cache_fp = OUT / "bond_sleeve_snaps.json"
    if cache_fp.exists():
        by_rows = json.loads(cache_fp.read_text(encoding="utf-8")).get("by_code") or {}
    for c in extra:
        if c in by_rows and by_rows[c]:
            continue
        daily_s = load_bond_daily(c)
        panel["daily"][c] = daily_s
        panel["aum"][c] = float(
            pd.read_csv(BOND_LABELS).assign(code=lambda x: x["code"].astype(str).str.zfill(6))
            .set_index("code")
            .loc[c, "aum"]
        )
        raw = daily_to_week_raw(c, daily_s)
        closes = {b["date"]: float(b["c"]) for b in raw.get("bars") or []}
        panel["closes_w_sig"][c] = closes
        ds = sorted(closes)
        if ds:
            panel["alias"][c] = {d: spike.nearest_date(d, ds, 3) for d in calendar}
        noon = {d: closes.get((panel["alias"].get(c) or {}).get(d) or d, closes.get(d)) for d in calendar if closes}
        by_rows[c] = spike.classify_modified({c: raw}, {c: {k: v for k, v in noon.items() if v}})[c]
    cache_fp.write_text(
        json.dumps({"by_code": by_rows, "end": panel["actual_end"]}, ensure_ascii=False),
        encoding="utf-8",
    )
    for c in extra:
        panel["snaps"][c] = spike.snap_index(by_rows.get(c) or [])
        panel["codes"].append(c)


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


def segment_yearly(r: pd.Series) -> pd.DataFrame:
    rows = []
    for y in sorted(set(r.index.year)):
        sy = r[r.index.year == y]
        if len(sy) < 2:
            continue
        qy = (1 + sy).cumprod()
        ret = float(qy.iloc[-1] - 1)
        mdd = float((qy / qy.cummax().clip(lower=1e-12) - 1).min())
        cal = ret / abs(mdd) if mdd < 0 else float("nan")
        rows.append({"year": y, "ret": ret, "mdd": mdd, "calmar": cal})
    return pd.DataFrame(rows)


def barbell_5050(
    r_a: pd.Series, r_b: pd.Series, calendar: list[str]
) -> tuple[pd.Series, str]:
    """Rebalance to 50/50 on each face Friday (calendar); side-note book."""
    idx = r_a.index.union(r_b.index).sort_values()
    ra = r_a.reindex(idx).fillna(0.0)
    rb = r_b.reindex(idx).fillna(0.0)
    reb = {pd.Timestamp(d) for d in calendar}
    val_a, val_b = 0.5, 0.5
    r_out: list[float] = []
    for d in idx:
        prev_nav = val_a + val_b
        val_a *= 1.0 + float(ra.loc[d])
        val_b *= 1.0 + float(rb.loc[d])
        nav = val_a + val_b
        r_out.append(nav / prev_nav - 1.0 if prev_nav > 0 else 0.0)
        if d in reb:
            half = nav / 2.0
            val_a = val_b = half
    note = "50/50 barbell; rebalance on face Fridays (calendar)"
    return pd.Series(r_out, index=idx), note


def run_book(
    name: str,
    panel: dict[str, Any],
    allowed: set[str],
    pool: pd.DataFrame,
    risk_on: dict[str, bool],
    breadth_mode: str,
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
        risk_on,
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
                "risk_on": int(risk_on.get(d, False)),
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
    row["breadth_mode"] = breadth_mode
    row["diversification"] = div["note"]
    row["yearly"] = segment_yearly(r).to_dict(orient="records")
    nav = (1 + r).cumprod()
    nav.to_csv(OUT / f"nav_{name}.csv", header=["nav"])
    return {
        "row": row,
        "returns": r,
        "hold": hold,
        "sim": st,
        "div": div,
        "trades": trades,
        "breadth_mode": breadth_mode,
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


def momentum_verdict(row: dict[str, Any], ref_calmar: float) -> str:
    cal = float(row.get("Calmar") or 0)
    to = float(row.get("avgTO") or 0)
    cash = float(row.get("cash_week_pct") or 0)
    if cal < 0.25 or cal < 0.35 * ref_calmar:
        return "弱/不适配动量（Calmar 相对 face 过低）"
    if to < 0.05 and cash > 0.7:
        return "信号稀薄，动量机械难发挥（高 cash 周 + 低换手）"
    if cal >= ref_calmar * 0.6 and to >= 0.08:
        return "中等：有一定趋势段，但需接受空周与品种集中度"
    return "边际：可研究但不宜替代 A 股 face"


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    t0 = time.time()
    commodity, bond_cash, pool = load_pool_slices()

    uni = pd.read_csv(spike.UNI_CSV)
    uni["code"] = uni["code"].astype(str).str.zfill(6)
    u = set(uni[uni["aum"] >= 2]["code"])
    allowed_comm = commodity & u
    allowed_bond = bond_cash.copy()
    print(
        f"commodity slice: {len(allowed_comm)} codes; bond/cash sleeve: {len(allowed_bond)}",
        flush=True,
    )

    print("load shared panel…", flush=True)
    panel = load_panel()
    augment_panel_bond_codes(panel, allowed_bond)

    book_specs = [
        ("RES-B45-S20-COMMODITY", allowed_comm),
        ("RES-B45-S20-BOND-CASH", allowed_bond),
    ]
    results: list[dict[str, Any]] = []
    series: dict[str, pd.Series] = {}
    for name, allowed in book_specs:
        risk_on, bmode = risk_on_for_slice(panel["calendar"], panel["risk_b45"], len(allowed))
        print(f"simulate {name} breadth={bmode} n={len(allowed)}…", flush=True)
        res = run_book(name, panel, allowed, pool, risk_on, bmode)
        results.append(res)
        series[name] = res["returns"]
        st = res["sim"]
        print(
            f"  ret={spike.pct(res['row']['ret'])} mdd={spike.pct(res['row']['maxDD'])} "
            f"Calmar={res['row']['Calmar']:.2f} avgTO={res['row']['avgTO']:.3f}",
            flush=True,
        )

    r_bar, bar_note = barbell_5050(
        results[0]["returns"], results[1]["returns"], panel["calendar"]
    )
    st_stub = {"cash_week_pct": 0.0, "n_trades": 0, "n_entries": 0}
    bar_row = spike.metrics_row("RES-B45-S20-BARBELL-50-50", r_bar, pd.Series(0.0, index=r_bar.index), st_stub)
    bar_row["avgTO"] = float("nan")
    bar_row["n_pool_codes"] = len(allowed_comm) + len(allowed_bond)
    bar_row["breadth_mode"] = "synthetic"
    bar_row["note"] = bar_note
    (1 + r_bar).cumprod().to_csv(OUT / "nav_RES-B45-S20-BARBELL-50-50.csv", header=["nav"])
    series["RES-B45-S20-BARBELL-50-50"] = r_bar

    table = pd.DataFrame([r["row"] for r in results] + [{"book": bar_row["book"], **bar_row}])
    ref = load_ref_b45()
    ref_calmar = float(ref.get("Calmar") or 0.7)
    if ref:
        table = pd.concat([table, pd.DataFrame([ref])], ignore_index=True)
    table.to_csv(OUT / "metrics.csv", index=False)
    table.to_csv(OUT / "table.csv", index=False)

    yearly_rows = []
    for res in results:
        ydf = segment_yearly(res["returns"])
        ydf["book"] = res["row"]["book"]
        yearly_rows.append(ydf)
    pd.concat(yearly_rows, ignore_index=True).to_csv(OUT / "yearly.csv", index=False)

    eq = pd.DataFrame({k: (1 + series[k]).cumprod() for k in series})
    eq.to_csv(OUT / "equity.csv")

    fig, ax = plt.subplots(figsize=(10, 5), dpi=120)
    for name in series:
        ax.plot(eq.index, eq[name], label=name, lw=1.6)
    if ref.get("ret"):
        ref_nav = 1 + float(ref["ret"])
        ax.axhline(ref_nav, color="gray", ls="--", lw=1, label="REF B45 (end NAV)")
    ax.set_yscale("log")
    ax.set_title("SPIKE-S20 · commodity vs bond/cash sleeves (research)")
    ax.set_ylabel("NAV (log)")
    ax.grid(True, alpha=0.3)
    ax.legend(fontsize=7)
    fig.tight_layout()
    fig.savefig(OUT / "equity_curve.png")
    plt.close(fig)

    c_row, b_row = results[0]["row"], results[1]["row"]
    v_c = momentum_verdict(c_row, ref_calmar)
    v_b = momentum_verdict(b_row, ref_calmar)

    report = f"""# REPORT · SPIKE-S20-UNIVERSE-COMMODITY-BOND-CASH-LIVE1430

**性质**：研究 only；**非 LIVE**；不换冠；不写 strategy_exec / LIVE_OPS / champion。  
PR#46 已证伪「空槽债停放换冠」——本批为 **袖套-as-book** 归因（整簿只在该类标的内排序）。

## 面层（各切片独立，不混类 rank）

spike_ft max5 · SHARPE20 · E0 · Fri≥14:30/收盘 · 0.2% RT · L≤1 · TV25。  
Breadth：池子 ≥{BREADTH_MIN} 才沿用 face B45 `risk_on`；否则 **NA**（切片内恒 risk_on，仅靠 falsify + 相对 Sharpe）。

| 簿 | 池定义 |
|---|---|
| **COMMODITY** | `research_pool_v2` · `l0=商品`（AUM≥2 与 uni 交集） |
| **BOND/CASH** | `bond_cash_sleeve_labels.csv` · `l0=固收现金`（国债+货币类） |
| **REF** | 全池 A 股研究 face · LIVE1430-B45-S20（extend 同窗） |

窗：{EVAL_START} → {panel['actual_end']}。

## 主表

| book | n | breadth | ret | maxDD | Calmar | avgTO | cash周% |
|---|---:|---|---:|---:|---:|---:|---:|
| {c_row['book']} | {c_row['n_pool_codes']} | {results[0]['breadth_mode']} | {spike.pct(c_row['ret'])} | {spike.pct(c_row['maxDD'])} | {c_row['Calmar']:.2f} | {c_row['avgTO']:.3f} | {100*c_row['cash_week_pct']:.1f}% |
| {b_row['book']} | {b_row['n_pool_codes']} | {results[1]['breadth_mode']} | {spike.pct(b_row['ret'])} | {spike.pct(b_row['maxDD'])} | {b_row['Calmar']:.2f} | {b_row['avgTO']:.3f} | {100*b_row['cash_week_pct']:.1f}% |
| {bar_row['book']} | — | synthetic | {spike.pct(bar_row['ret'])} | {spike.pct(bar_row['maxDD'])} | {bar_row['Calmar']:.2f} | — | — |
| REF B45 face | {panel['n_codes']} | face | {spike.pct(ref.get('ret'))} | {spike.pct(ref.get('maxDD'))} | {ref_calmar:.2f} | — | {100*ref.get('cash_week_pct', 0):.1f}% |

## 动量适配性（Calmar / 换手 / 分段）

- **商品袖**：{v_c} — {results[0]['div']['note']}
- **固收现金袖**：{v_b} — {results[1]['div']['note']}
- **50/50 杠铃（侧边）**：{bar_note}；全样本 Calmar {bar_row['Calmar']:.2f}（非独立 spike 簿）。

分段见 `yearly.csv`（2020–22 / 2023–26 可自算）。

## 红线

不得将商品与债/货币标的在同一簿内混合排序；不得据此启用 LIVE 债袖或替换冠军。

耗时约 {round(time.time() - t0, 1)}s。
"""
    (OUT / "REPORT.md").write_text(report, encoding="utf-8")
    (OUT / "README.md").write_text(
        "# SPIKE-S20-UNIVERSE-COMMODITY-BOND-CASH-LIVE1430\n\n"
        "研究批四件套目录。运行：`python3 run.py`（需 cloud_batch 研究缓存）。\n",
        encoding="utf-8",
    )
    summary = {
        "knife": "SPIKE-S20-UNIVERSE-COMMODITY-BOND-CASH-LIVE1430",
        "sample": f"{EVAL_START} → {panel['actual_end']}",
        "n_commodity": len(allowed_comm),
        "n_bond_cash": len(allowed_bond),
        "breadth_min": BREADTH_MIN,
        "momentum_verdict": {"commodity": v_c, "bond_cash": v_b},
        "barbell_note": bar_note,
        "table": table.to_dict(orient="records"),
        "elapsed_sec": round(time.time() - t0, 1),
    }
    (OUT / "summary.json").write_text(
        json.dumps(summary, ensure_ascii=False, indent=2, default=str), encoding="utf-8"
    )
    print("done", OUT, flush=True)


if __name__ == "__main__":
    main()
