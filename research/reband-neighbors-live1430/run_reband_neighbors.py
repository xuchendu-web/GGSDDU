#!/usr/bin/env python3
"""REBAND neighbor grid on B45+S20 LIVE1430 (extended window).

Holding path frozen (B45+S20); only TV execution-layer reband_tol varies (E30).
"""
from __future__ import annotations

import importlib.util
import json
import math
import sys
import time
from collections import defaultdict
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parent
OUT = ROOT
EXTEND_RUN = (
    Path(__file__).resolve().parents[1]
    / "cloud_batch/SPIKE-S20-EXTEND-REBASE-LIVE1430/run.py"
)

GRID: list[tuple[str, float]] = [
    ("LIVE1430-FACE-B45-S20", 0.0),
    ("LIVE1430-REBAND3", 0.03),
    ("LIVE1430-REBAND5", 0.05),
    ("LIVE1430-REBAND10", 0.10),
]
GRID_ANNEX: list[tuple[str, float]] = [("LIVE1430-REBAND7", 0.07)]


def load_extend_module():
    spec = importlib.util.spec_from_file_location("extend_live1430", EXTEND_RUN)
    if spec is None or spec.loader is None:
        raise SystemExit(f"cannot load {EXTEND_RUN}")
    mod = importlib.util.module_from_spec(spec)
    sys.modules["extend_live1430"] = mod
    spec.loader.exec_module(mod)
    return mod


def drift_weights(
    w0: dict[str, float], seg: pd.DatetimeIndex, R: pd.DataFrame
) -> dict[str, float]:
    w = {k: float(v) for k, v in w0.items()}
    for day in seg:
        if day not in R.index:
            continue
        for c in list(w.keys()):
            r = float(R.loc[day, c]) if c in R.columns and pd.notna(R.loc[day, c]) else 0.0
            w[c] *= 1.0 + r
        s = sum(w.values())
        if s > 0:
            w = {c: v / s for c, v in w.items()}
    return w


def run_live_tv_reband(
    er,
    hold: dict[pd.Timestamp, list[str]],
    days: pd.DatetimeIndex,
    px: pd.DataFrame,
    R: pd.DataFrame,
    reband_tol: float,
    sigma_star: float | None = None,
    cash_fill: str | None = None,
) -> tuple[pd.Series, pd.Series, dict[str, Any]]:
    sigma_star = sigma_star if sigma_star is not None else er.SIGMA_STAR
    reb = sorted(hold)
    rp = pd.Series(0.0, index=days)
    Ls = pd.Series(0.0, index=days)
    prev_wt: dict[str, float] = {}
    prev_w: dict[str, float] = {}
    prev_L = 0.0
    cst = pd.Series(0.0, index=days)
    R2 = R.reindex(days)
    n_skip_reband = 0

    for i, d in enumerate(reb):
        cs = [c for c in hold[d] if c in px.columns]
        nxt = reb[i + 1] if i + 1 < len(reb) else days[-1] + pd.Timedelta(days=1)
        seg = days[(days > d) & (days <= nxt)]
        prev_day = reb[i - 1] if i > 0 else None
        drift_seg = (
            days[(days > prev_day) & (days <= d)]
            if prev_day is not None
            else days[days <= d]
        )

        w_exec: dict[str, float] = {}
        if not cs:
            if cash_fill and cash_fill in px.columns:
                cs = [cash_fill]
                w_exec = {cash_fill: 1.0}
                L = 1.0
            else:
                L = 0.0
        else:
            w_tgt = {c: 1.0 / len(cs) for c in cs}
            past = rp[rp.index <= d]
            past = past[past != 0]
            if len(past) < 2:
                L = 1.0
            else:
                s20 = past.iloc[-20:].std() * np.sqrt(252)
                s60 = past.iloc[-60:].std() * np.sqrt(252)
                sh = np.nanmax([s20, s60])
                L = float(min(er.LCAP, sigma_star / sh)) if sh and sh > 0 else 1.0

            membership = set(cs) != set(prev_w.keys())
            switch_flip = (prev_L == 0 and L > 0 and len(prev_w) == 0 and len(cs) > 0) or (
                len(prev_w) > 0 and len(cs) == 0
            ) or (prev_L > 0 and L == 0 and len(cs) > 0)

            if membership or switch_flip or reband_tol <= 0 or not prev_w:
                w_exec = w_tgt
            else:
                w_drift = drift_weights(prev_w, drift_seg, R2)
                w_drift = {c: w_drift.get(c, 0.0) for c in cs}
                s = sum(w_drift.values())
                if s > 0:
                    w_drift = {c: v / s for c, v in w_drift.items()}
                else:
                    w_drift = w_tgt
                max_d = max(abs(w_tgt[c] - w_drift.get(c, 0.0)) for c in cs)
                if max_d <= reband_tol:
                    w_exec = w_drift
                    n_skip_reband += 1
                else:
                    w_exec = w_tgt

        wt = {c: L * v for c, v in w_exec.items()} if w_exec else {}
        to = sum(abs(wt.get(k, 0) - prev_wt.get(k, 0)) for k in set(wt) | set(prev_wt))
        prev_wt = wt
        prev_w = w_exec
        prev_L = L
        if d in cst.index:
            cst.loc[d] = to * er.LIVE_COST_RT / 2
        if w_exec and len(seg):
            rp.loc[seg] = (R2.loc[seg, list(w_exec)].fillna(0) @ pd.Series(w_exec)).values
            Ls.loc[seg] = L

    r = rp * Ls - cst
    meta = {"reband_tol": reband_tol, "n_skip_reband_weeks": n_skip_reband}
    return r, Ls, meta


def load_bundle(er) -> dict[str, Any]:
    from backtest import snap_index

    for p in (er.WEEK, er.FACE, er.DAY_DIR, er.NOON_CSV, er.SINA_DAILY):
        if not Path(p).exists():
            raise SystemExit(f"missing {p}")

    uni = pd.read_csv(er.UNI_CSV)
    uni["code"] = uni["code"].astype(str).str.zfill(6)
    uni = uni[uni["aum"] >= 2].copy()
    codes = uni["code"].tolist()
    aum = {r.code: float(r.aum or 0) for r in uni.itertuples()}
    code_set = set(codes)

    noon = pd.read_csv(er.NOON_CSV)
    noon["code"] = noon["etf_code"].astype(str).str.split(".").str[0]
    noon["trade_date"] = noon["trade_date"].astype(str).str[:10]
    noon["friday_week_date"] = noon["friday_week_date"].astype(str).str[:10]
    noon = noon[noon["code"].isin(code_set)].copy()
    if "price_1430" in noon.columns and "price_1130" not in noon.columns:
        noon["price_1130"] = noon["price_1430"]

    face = pd.read_csv(er.FACE)
    face["date"] = face["date"].astype(str).str[:10]
    face = face[(face["date"] >= er.EVAL_START) & (face["date"] <= er.END_S)].copy()
    calendar = sorted(face["date"].unique().tolist())
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
        fp = er.WEEK / f"{c}.json"
        if not fp.exists():
            raws_w[c] = {"bars": []}
            closes_w_close[c] = {}
            continue
        rec = json.loads(fp.read_text(encoding="utf-8"))
        raws_w[c] = rec
        closes_w_close[c] = {
            b["date"]: float(b["c"])
            for b in (rec.get("bars") or [])
            if b.get("date") and b["date"] <= er.END_S and float(b["c"]) > 0
        }

    alias: dict[str, dict[str, str]] = {}
    for c in codes:
        ds = sorted(closes_w_close.get(c, {}))
        if not ds:
            continue
        alias[c] = {d: hit for d in calendar if (hit := er.nearest_date(d, ds, 3))}

    sina = er.load_sina_closes(codes)
    daily = er.load_daily_closes(codes, sina)

    noon_w: dict[str, dict[str, float]] = defaultdict(dict)
    blocked_empty: dict[str, set[str]] = defaultdict(set)
    for r in noon.itertuples():
        td = r.trade_date
        if td < er.EVAL_START or td > er.END_S:
            continue
        if r.status == "empty" or (
            r.status == "ok"
            and (r.price_1130 is None or (isinstance(r.price_1130, float) and math.isnan(r.price_1130)))
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

    cached = json.loads(er.SNAP_CACHE.read_text(encoding="utf-8"))
    by_rows = cached.get("by_code") or {}
    snaps = {c: snap_index(by_rows.get(c) or []) for c in codes}

    return {
        "calendar": calendar,
        "actual_end": actual_end,
        "risk_b45": risk_b45,
        "snaps": snaps,
        "closes_w_sig": closes_w_sig,
        "alias": alias,
        "aum": aum,
        "daily": daily,
        "codes": codes,
    }


def pct(x: float | None) -> str:
    if x is None or (isinstance(x, float) and (math.isnan(x) or math.isinf(x))):
        return "—"
    return f"{100 * x:.1f}%"


def judge_verdict(face: dict[str, Any], row: dict[str, Any]) -> str:
    if row["book"] == face["book"]:
        return "FACE"
    cal_better = float(row["Calmar"]) > float(face["Calmar"]) + 0.01
    r23 = float(row["2023-26_ret"])
    f23 = float(face["2023-26_ret"])
    if cal_better and r23 >= f23 - 0.005:
        return "记正"
    if float(row["Calmar"]) < float(face["Calmar"]) - 0.02 or r23 < f23 - 0.02:
        return "证伪"
    return "旁注"


def build_report(df: pd.DataFrame, face: pd.Series, summary: dict[str, Any]) -> str:
    lines = [
        "# REBAND 邻域稳健 · LIVE1430 四件套",
        "",
        f"- 样本：{summary['sample']}",
        "- 持仓路径：单一 `LIVE1430-B45-S20` simulate（与 EXTEND-REBASE 同窗）",
        "- 唯一改动：`run_live_tv_reband(reband_tol)` — |Δw|≤tol 不调（成员/开关翻转强制）",
        f"- 总判卷：**{summary['verdict_pack']}**（不换冠）",
        "",
        "## 主表（FACE + 邻档 3/5/10）",
        "",
        "| book | reband_tol | ret | maxDD | Calmar | 2023–26 ret | 2023–26 Calmar | skip周 | 判卷 |",
        "|---|---:|---:|---:|---:|---:|---:|---:|---|",
    ]
    for _, r in df.iterrows():
        lines.append(
            f"| {r['book']} | {100*r['reband_tol']:.0f}% | {pct(r['ret'])} | {pct(r['maxDD'])} | "
            f"{r['Calmar']:.2f} | {pct(r['2023-26_ret'])} | {r['2023-26_Calmar']:.2f} | "
            f"{int(r.get('n_skip_reband_weeks', 0))} | {r['verdict']} |"
        )
    if summary.get("annex_rows"):
        lines += ["", "## 旁注 REBAND7", ""]
        for ar in summary["annex_rows"]:
            lines.append(
                f"- {ar['book']}: Calmar {ar['Calmar']:.2f}; 2023–26 {pct(ar['2023-26_ret'])} · **{ar['verdict']}**"
            )
    lines += ["", "## 相对 FACE（Δ）", ""]
    for _, r in df.iterrows():
        if r["book"] == face["book"]:
            continue
        dret = 100 * (float(r["ret"]) - float(face["ret"]))
        dcal = float(r["Calmar"]) - float(face["Calmar"])
        lines.append(f"- **{r['book']}**: Δret {dret:+.1f}pp; ΔCalmar {dcal:+.2f}")
    lines += [
        "",
        "## 引擎溯源",
        "",
        "- PEER E30 原产物：`spike_mom_rank/SPIKE-S20-REBAND5-LIVE1430/`（源码未入库）",
        "- 旋钮口径：`research/research-kb/JUDGING_LOG.md`（|Δw|≤5% 不调；邻档 10%）",
        f"- FACE 对齐 EXTEND B45：{summary.get('face_align_extend_b45', '—')}",
    ]
    return "\n".join(lines) + "\n"


def main() -> None:
    t0 = time.time()
    er = load_extend_module()
    bundle = load_bundle(er)

    print("simulate LIVE1430-B45-S20 holdings (shared)…", flush=True)
    trades, hold, sim_st = er.simulate(
        bundle["calendar"],
        bundle["snaps"],
        bundle["closes_w_sig"],
        bundle["alias"],
        bundle["aum"],
        bundle["daily"],
        bundle["risk_b45"],
        er.sharpe_key,
        "LIVE1430-B45-S20",
        True,
        20,
        er.MAX_POS,
    )
    pd.DataFrame(trades).to_csv(OUT / "trades_FACE_holdings.csv", index=False)

    all_codes: set[str] = set()
    for cs in hold.values():
        all_codes |= set(cs)
    px_map = {}
    for c in sorted(all_codes):
        if c in bundle["daily"]:
            px_map[c] = bundle["daily"][c]
        else:
            fday = er.DAY_DIR / f"{c}.json"
            if fday.exists():
                j = json.loads(fday.read_text(encoding="utf-8"))
                bars = j.get("bars") if isinstance(j, dict) else j
                if bars:
                    idx = pd.to_datetime([b["date"] for b in bars])
                    px_map[c] = pd.Series(
                        [float(b["c"]) for b in bars], index=idx, dtype=float
                    ).sort_index()
    px = pd.DataFrame(px_map).sort_index()
    px = px.loc[(px.index >= er.EVAL_START) & (px.index <= er.END_S)]
    R = px.pct_change()
    days = px.dropna(how="all").index
    days = days[(days >= er.EVAL_START) & (days <= er.END_S)]
    hd = {pd.Timestamp(d): cs for d, cs in hold.items()}

    all_books = GRID + GRID_ANNEX
    table_rows = []
    series: dict[str, pd.Series] = {}
    tv_meta: dict[str, Any] = {}

    for name, tol in all_books:
        print(f"TV layer {name} reband_tol={tol:.2%} …", flush=True)
        if tol <= 0:
            r, L = er.run_live_tv(hd, days, px, R, sigma_star=er.SIGMA_STAR, cash_fill=None)
            meta = {"reband_tol": tol, "n_skip_reband_weeks": 0}
        else:
            r, L, meta = run_live_tv_reband(er, hd, days, px, R, tol)
        tv_meta[name] = meta
        series[name] = r
        row = er.metrics_row(name, r, L, sim_st)
        row["reband_tol"] = tol
        row["n_skip_reband_weeks"] = meta.get("n_skip_reband_weeks", 0)
        table_rows.append(row)
        (1 + r).cumprod().to_csv(OUT / f"nav_{name}.csv", header=["nav"])

    df = pd.DataFrame(table_rows)
    face_row = df[df["book"] == "LIVE1430-FACE-B45-S20"].iloc[0]
    face_dict = face_row.to_dict()
    df["verdict"] = [judge_verdict(face_dict, r.to_dict()) for _, r in df.iterrows()]

    pack = df[df["book"].isin([b for b, _ in GRID])]
    pos_neighbors = pack[(pack["verdict"] == "记正") & (pack["book"] != face_row["book"])]
    if len(pos_neighbors):
        verdict_pack = "记正（邻域有明确优于 FACE）"
    elif (pack["verdict"] == "证伪").any():
        verdict_pack = "证伪（邻域未稳优于 FACE）"
    else:
        verdict_pack = "旁注（边际/不插值）"

    extend_ref = (
        Path(__file__).resolve().parents[1]
        / "cloud_batch/SPIKE-S20-EXTEND-REBASE-LIVE1430/table.csv"
    )
    align_note = ""
    if extend_ref.exists():
        ref = pd.read_csv(extend_ref)
        b45 = ref[ref.book == "LIVE1430-B45-S20"]
        if not b45.empty:
            dr = abs(float(face_row["ret"]) - float(b45.iloc[0]["ret"]))
            align_note = f"Δret={100*dr:.2f}pp (FACE tol=0 vs EXTEND B45)"

    annex_rows = [
        {
            "book": r["book"],
            "Calmar": float(r["Calmar"]),
            "2023-26_ret": float(r["2023-26_ret"]),
            "verdict": r["verdict"],
        }
        for _, r in df[df["book"].str.contains("REBAND7")].iterrows()
    ]

    summary = {
        "title": "REBAND-neighbors-LIVE1430",
        "sample": f"{er.EVAL_START} → {bundle['actual_end']}",
        "parameter": "reband_tol on TV execution weights (E30 JUDGING_LOG)",
        "grid_four_pack": [{"book": b, "reband_tol": t} for b, t in GRID],
        "annex": [{"book": b, "reband_tol": t} for b, t in GRID_ANNEX],
        "verdict_pack": verdict_pack,
        "face_align_extend_b45": align_note,
        "sim_stats_b45_hold": sim_st,
        "tv_meta": tv_meta,
        "elapsed_s": round(time.time() - t0, 1),
    }

    pack.to_csv(OUT / "table.csv", index=False)
    df.to_csv(OUT / "metrics.csv", index=False)
    summary["books"] = df.to_dict(orient="records")
    (OUT / "summary.json").write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
    report = build_report(pack, face_row, {**summary, "annex_rows": annex_rows})
    (OUT / "REPORT.md").write_text(report, encoding="utf-8")
    print(report, flush=True)
    print(f"done {summary['elapsed_s']}s {verdict_pack} {align_note}", flush=True)


if __name__ == "__main__":
    main()
