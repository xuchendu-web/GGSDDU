#!/usr/bin/env python3
"""SPIKE-S20-CASH-BOND-SLEEVE-LIVE1430: max5 slot parking when unfilled.

Books (B45 face frozen; spike_ft max5 + S20 + E0 + TV25 + 0.2%RT + L≤1):
  LIVE1430-B45-S20-max5           — FACE baseline (legacy TV; empty week = cash)
  LIVE1430-B45-SLOT-CASH          — neighbor: empty slots → cash stub (0)
  LIVE1430-B45-SLOT-511010        — neighbor: empty slots → 511010
  LIVE1430-B45-SLOT-511260        — neighbor: empty slots → 511260

Unique change vs B45+S20 face: slot 1/5 parking on unfilled max5 seats only.
Exploration — no crown; no LIVE bond sleeve enable.
"""
from __future__ import annotations

import json
import math
import sys
import time
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

KIT = Path(__file__).resolve().parent.parent / "CLOUD-BATCH-2026-10-26"
BTHETA = Path(__file__).resolve().parent.parent / "SPIKE-S20-BTHETA-GRID-LIVE1430"
sys.path.insert(0, str(KIT / "scripts"))

from backtest import nearest_date  # noqa: E402

OUT = Path(__file__).resolve().parent
BOND_DIR = KIT / "data" / "research_cache" / "bond_daily"
KNIFE_MD = KIT / "knives" / "SPIKE-S20-CASH-BOND-SLEEVE-LIVE1430.md"

EVAL_START = "2020-01-03"
END_S = "2026-10-23"
SIGMA_STAR = 0.25
LCAP = 1.0
LIVE_COST_RT = 0.002
MAX_POS = 5
BASELINE = "LIVE1430-B45-S20-max5"

BOOKS = [
    (BASELINE, "face", None),
    ("LIVE1430-B45-SLOT-CASH", "slot", None),
    ("LIVE1430-B45-SLOT-511010", "slot", "511010"),
    ("LIVE1430-B45-SLOT-511260", "slot", "511260"),
]


def pct(x: float | None) -> str:
    if x is None or (isinstance(x, float) and (math.isnan(x) or math.isinf(x))):
        return "—"
    return f"{100 * x:.1f}%"


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


def yearly_table(r: pd.Series) -> pd.DataFrame:
    rows = []
    for y in sorted(set(r.index.year)):
        sy = r[r.index.year == y]
        if len(sy) < 2:
            continue
        qy = (1 + sy).cumprod()
        ret = float(qy.iloc[-1] - 1)
        mdd = float((qy / qy.cummax().clip(lower=1e-12) - 1).min())
        calmar = ret / abs(mdd) if mdd < 0 else float("nan")
        rows.append({"year": y, "ret": ret, "mdd": mdd, "calmar": calmar})
    return pd.DataFrame(rows)


def extend_bond_backward(close: pd.Series, start: str, daily_drift: float = 0.00014) -> pd.Series:
    """Back-fill before first quote with constant daily drift (documented approx)."""
    idx = pd.to_datetime(close.index).sort_values()
    s = close.astype(float).sort_index()
    first = s.index[0]
    need = pd.bdate_range(start, first - pd.Timedelta(days=1))
    if len(need) == 0:
        return s
    back = []
    px = float(s.iloc[0])
    for d in reversed(need):
        px = px / (1.0 + daily_drift)
        back.append((d, px))
    back_s = pd.Series({d: v for d, v in reversed(back)})
    out = pd.concat([back_s, s]).sort_index()
    out = out[~out.index.duplicated(keep="last")]
    return out


def load_bond_close(code: str, days: pd.DatetimeIndex) -> pd.Series:
    fp = BOND_DIR / f"{code}.csv"
    if not fp.exists():
        raise SystemExit(f"missing bond daily {fp}; run materialize / stitch bond_daily first")
    df = pd.read_csv(fp, parse_dates=["date"])
    s = df.set_index("date")["close"].astype(float).sort_index()
    s = extend_bond_backward(s, EVAL_START)
    s = s.reindex(days).ffill().bfill()
    return s


def run_live_tv_face(
    hold: dict[pd.Timestamp, list[str]], days: pd.DatetimeIndex, px: pd.DataFrame, R: pd.DataFrame
) -> tuple[pd.Series, pd.Series]:
    """Original B45 face TV (from btheta grid)."""
    reb = sorted(hold)
    rp = pd.Series(0.0, index=days)
    Ls = pd.Series(0.0, index=days)
    prev: dict[str, float] = {}
    cst = pd.Series(0.0, index=days)
    R2 = R.reindex(days)

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
        prev = wt
        if d in cst.index:
            cst.loc[d] = to * LIVE_COST_RT / 2
        if w and len(seg):
            rp.loc[seg] = (R2.loc[seg, list(w)].fillna(0) @ pd.Series(w)).values
            Ls.loc[seg] = L
    r = rp * Ls - cst
    return r, Ls


def run_live_tv_slots(
    hold: dict[pd.Timestamp, list[str]],
    n_held_map: dict[pd.Timestamp, int],
    days: pd.DatetimeIndex,
    px: pd.DataFrame,
    R: pd.DataFrame,
    bond_code: str | None,
    max_pos: int = MAX_POS,
) -> tuple[pd.Series, pd.Series, pd.Series]:
    """max_pos slot model: each filled seat = 1/max_pos of NAV; empty slots park in bond_code or cash."""
    reb = sorted(hold)
    rp = pd.Series(0.0, index=days)
    Ls = pd.Series(0.0, index=days)
    park_frac = pd.Series(0.0, index=days)
    prev_eq: dict[str, float] = {}
    prev_park = 0.0
    cst = pd.Series(0.0, index=days)
    R2 = R.reindex(days)
    bond_r = None
    if bond_code:
        bc = load_bond_close(bond_code, days)
        bond_r = bc.pct_change().fillna(0.0)

    for i, d in enumerate(reb):
        cs = [c for c in hold[d] if c in px.columns]
        n = int(n_held_map.get(d, len(cs)))
        n = max(0, min(max_pos, n))
        cs = cs[:n]
        nxt = reb[i + 1] if i + 1 < len(reb) else days[-1] + pd.Timedelta(days=1)
        seg = days[(days > d) & (days <= nxt)]
        park_w = max(0.0, (max_pos - n) / max_pos)
        eq_w = 1.0 - park_w

        if n == 0:
            w = {}
            L = 0.0
        else:
            w = {c: eq_w / n for c in cs}
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
        new_park = park_w
        to = sum(abs(wt.get(k, 0) - prev_eq.get(k, 0)) for k in set(wt) | set(prev_eq))
        to += abs(new_park - prev_park)
        prev_eq = wt
        prev_park = new_park
        if d in cst.index:
            cst.loc[d] = to * LIVE_COST_RT / 2

        if len(seg):
            eq_part = np.zeros(len(seg))
            if w:
                eq_part = (R2.loc[seg, list(w)].fillna(0) @ pd.Series(w)).values * L
            park_part = np.zeros(len(seg))
            if park_w > 0 and bond_r is not None:
                park_part = bond_r.loc[seg].values * park_w
            rp.loc[seg] = eq_part + park_part
            Ls.loc[seg] = L if n else 0.0
            park_frac.loc[seg] = park_w

    r = rp - cst
    return r, Ls, park_frac


def load_b45_holdings() -> tuple[dict[pd.Timestamp, list[str]], dict[pd.Timestamp, int], list[str]]:
    hp = BTHETA / f"holdings_{BASELINE}.csv"
    if not hp.exists():
        raise SystemExit(f"missing {hp}; run SPIKE-S20-BTHETA-GRID-LIVE1430 first")
    hdf = pd.read_csv(hp)
    hdf["date"] = hdf["date"].astype(str).str[:10]
    calendar = sorted(hdf["date"].unique().tolist())
    hold: dict[pd.Timestamp, list[str]] = {}
    n_held: dict[pd.Timestamp, int] = {}
    for _, row in hdf.iterrows():
        d = str(row["date"])[:10]
        raw = row.get("codes")
        if raw is None or (isinstance(raw, float) and math.isnan(raw)):
            codes = []
        else:
            codes = [c.strip() for c in str(raw).split(",") if c.strip() and c.strip().lower() != "nan"]
        nh = row.get("n_held")
        if nh is not None and not (isinstance(nh, float) and math.isnan(nh)):
            n = int(nh)
        else:
            n = len(codes)
        n = max(0, min(MAX_POS, n))
        hold[pd.Timestamp(d)] = codes[:n] if n else []
        n_held[pd.Timestamp(d)] = n
    return hold, n_held, calendar


def slot_stats(n_held_map: dict[pd.Timestamp, int], calendar: list[str]) -> dict[str, float]:
    n_weeks = max(0, len(calendar) - 1)
    empty = partial = full = 0
    for d in calendar[:-1]:
        n = int(n_held_map.get(pd.Timestamp(d), 0))
        if n == 0:
            empty += 1
        elif n < MAX_POS:
            partial += 1
        else:
            full += 1
    return {
        "empty_weeks": empty,
        "partial_fill_weeks": partial,
        "full_weeks": full,
        "empty_week_pct": empty / max(1, n_weeks),
        "partial_week_pct": partial / max(1, n_weeks),
    }


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    t0 = time.time()
    hold, n_held_map, calendar = load_b45_holdings()
    actual_end = calendar[-1]
    print(f"B45 holdings {calendar[0]} → {actual_end} weeks={len(calendar)}", flush=True)

    btheta_nav_fp = BTHETA / f"nav_{BASELINE}.csv"
    if not btheta_nav_fp.exists():
        raise SystemExit(f"missing {btheta_nav_fp}")
    bn = pd.read_csv(btheta_nav_fp, index_col=0, parse_dates=True).iloc[:, 0].sort_index()
    days = bn.index[(bn.index >= EVAL_START) & (bn.index <= END_S)]
    r_face_kit = bn.pct_change().fillna(0.0)

    all_codes: set[str] = set()
    for cs in hold.values():
        all_codes |= set(cs)

    DAY_DIR = KIT / "data" / "research_cache" / "day"
    TEMA_PX = Path("/workspace/tema_etf_scan_2018/prices_daily")
    px_map: dict[str, pd.Series] = {}
    for c in sorted(all_codes):
        s = None
        fday = DAY_DIR / f"{c}.json"
        if fday.exists():
            j = json.loads(fday.read_text(encoding="utf-8"))
            bars = j.get("bars") if isinstance(j, dict) else j
            if bars:
                idx = pd.to_datetime([b["date"] for b in bars])
                s = pd.Series([float(b["c"]) for b in bars], index=idx).sort_index()
        ftema = TEMA_PX / f"{c}.csv"
        if TEMA_PX.exists() and ftema.exists():
            df = pd.read_csv(ftema, parse_dates=["Date"])
            t = df.set_index("Date")["Close"].astype(float).sort_index()
            s = t if s is None else t.combine_first(s).sort_index()
        if s is not None:
            px_map[c] = s.reindex(days).ffill()

    px = pd.DataFrame(px_map).reindex(days)
    R = px.pct_change()
    print(f"live days {days[0].date()} → {days[-1].date()} n={len(days)}", flush=True)

    st_slots = slot_stats(n_held_map, calendar)
    print(f"slot weeks empty={st_slots['empty_weeks']} partial={st_slots['partial_fill_weeks']}", flush=True)

    table_rows = []
    series: dict[str, pd.Series] = {}
    for name, mode, bond in BOOKS:
        if mode == "face":
            r = r_face_kit.reindex(days).fillna(0.0)
            L = pd.Series(0.8413486853673591, index=days)
            avg_park = 0.0
        else:
            r, L, pf = run_live_tv_slots(hold, n_held_map, days, px, R, bond, MAX_POS)
            avg_park = float(pf[pf > 0].mean()) if (pf > 0).any() else 0.0
        series[name] = r
        st = stats_full(r)
        r2022 = r[(r.index >= "2020-01-01") & (r.index <= "2022-12-31")]
        r2023 = r[r.index >= "2023-01-01"]
        st2022 = stats_full(r2022) if len(r2022) > 5 else {k: float("nan") for k in st}
        st2023 = stats_full(r2023) if len(r2023) > 5 else {k: float("nan") for k in st}
        row = {
            "book": name,
            **st,
            "2020-22_ret": st2022["ret"],
            "2020-22_DD": st2022["maxDD"],
            "2020-22_Calmar": st2022["Calmar"],
            "2023-26_ret": st2023["ret"],
            "2023-26_DD": st2023["maxDD"],
            "2023-26_Calmar": st2023["Calmar"],
            "avgL": float(L[L > 0].mean()) if (L > 0).any() else 0.0,
            "avg_park_frac": avg_park,
            **{f"slot_{k}": v for k, v in st_slots.items()},
        }
        table_rows.append(row)
        (1 + r).cumprod().to_csv(OUT / f"nav_{name}.csv", header=["nav"])
        print(
            f"{name}: ret={pct(st['ret'])} dd={pct(st['maxDD'])} Calmar={st['Calmar']:.2f} park={avg_park:.2f}",
            flush=True,
        )

    df = pd.DataFrame(table_rows)
    df.to_csv(OUT / "table.csv", index=False)
    df.to_csv(OUT / "metrics.csv", index=False)

    face = df[df.book == BASELINE].iloc[0]
    b010 = df[df.book == "LIVE1430-B45-SLOT-511010"].iloc[0]
    b260 = df[df.book == "LIVE1430-B45-SLOT-511260"].iloc[0]
    bcash = df[df.book == "LIVE1430-B45-SLOT-CASH"].iloc[0]

    def delta(row: pd.Series) -> dict[str, float]:
        return {
            "dret_pp": (row["ret"] - face["ret"]) * 100,
            "dMDD_pp": (row["maxDD"] - face["maxDD"]) * 100,
            "d_absMDD_pp": (abs(row["maxDD"]) - abs(face["maxDD"])) * 100,
            "dCalmar": row["Calmar"] - face["Calmar"],
        }

    d010 = delta(b010)
    d260 = delta(b260)
    dcash = delta(bcash)

    # verify face ~ btheta published
    align_note = "FACE 直接复用 BTHETA 同窗 `nav_LIVE1430-B45-S20-max5.csv`（与 B45 face 一致）。"

    def covers(d: dict[str, float]) -> bool:
        return d["dret_pp"] >= d["d_absMDD_pp"] - 1e-9

    best_neighbor = max(
        [("511010", b010, d010), ("511260", b260, d260), ("CASH", bcash, dcash)],
        key=lambda x: x[1]["Calmar"],
    )
    falsify: list[str] = []
    if not covers(d010) and not covers(d260):
        falsify.append("债邻档均未做到 Δret 盖住 Δ|MDD|")
    if float(best_neighbor[1]["Calmar"]) <= float(face["Calmar"]) + 0.01:
        falsify.append(f"最优邻档 {best_neighbor[0]} Calmar 未高于 FACE")
    if float(best_neighbor[1]["2023-26_ret"]) < float(face["2023-26_ret"]) - 0.02:
        falsify.append("后段 2023–26 踏空")

    if falsify:
        verdict = "**证伪「空槽债停放优于 FACE」（不换冠、不启 LIVE 债袖）**：" + "；".join(falsify) + "。"
    else:
        verdict = (
            f"**探索记正（邻档有信号；不换冠）**：最优邻档 **{best_neighbor[0]}** "
            f"Calmar {float(best_neighbor[1]['Calmar']):.2f} vs FACE {float(face['Calmar']):.2f}；"
            f"Δret={best_neighbor[2]['dret_pp']:+.1f}pp Δ|MDD|={best_neighbor[2]['d_absMDD_pp']:+.1f}pp。"
        )

    criterion_src = KNIFE_MD.read_text(encoding="utf-8") if KNIFE_MD.exists() else ""

    summary = {
        "title": "SPIKE-S20-CASH-BOND-SLEEVE-LIVE1430",
        "unique_change": "max5 slot parking on unfilled seats (511010 / 511260 / cash stub)",
        "baseline_face": BASELINE,
        "sample": f"{EVAL_START} → {actual_end}",
        "slot_week_stats": st_slots,
        "table": table_rows,
        "delta_vs_face": {"511010": d010, "511260": d260, "CASH": dcash},
        "best_neighbor": best_neighbor[0],
        "falsify": bool(falsify),
        "verdict": verdict,
        "bond_data_note": "bond_daily: mf-hold qfq scaled to zsmcp anchor 2024-02-26; pre-list drift backfill",
        "elapsed_sec": round(time.time() - t0, 1),
    }
    (OUT / "summary.json").write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")

    eq = pd.DataFrame({k: (1 + series[k]).cumprod() for k, _, _ in BOOKS})
    eq.to_csv(OUT / "equity.csv")
    eq.to_csv(OUT / "nav_all.csv")

    fig, ax = plt.subplots(figsize=(11, 5.5), dpi=120)
    styles = [
        (BASELINE, 2.0, "-"),
        ("LIVE1430-B45-SLOT-511010", 1.5, "-"),
        ("LIVE1430-B45-SLOT-511260", 1.5, "--"),
        ("LIVE1430-B45-SLOT-CASH", 1.2, ":"),
    ]
    for name, lw, ls in styles:
        if name in eq.columns:
            ax.plot(eq.index, eq[name], label=name, lw=lw, ls=ls)
    ax.set_yscale("log")
    ax.set_title("SPIKE-S20-CASH-BOND-SLEEVE-LIVE1430（B45 FACE vs 空槽停放邻档）")
    ax.grid(True, alpha=0.3)
    ax.legend(fontsize=7)
    fig.tight_layout()
    fig.savefig(OUT / "equity_curve.png")
    plt.close(fig)

    y = yearly_table(series[BASELINE])
    for name, _, _ in BOOKS[1:]:
        yi = yearly_table(series[name]).rename(columns=lambda c, n=name: f"{n}_{c}" if c != "year" else c)
        y = y.merge(yi, on="year", how="outer")
    y.to_csv(OUT / "yearly.csv", index=False)

    (OUT / "criterion.md").write_text(
        "# Criterion · SPIKE-S20-CASH-BOND-SLEEVE-LIVE1430\n\n" + criterion_src,
        encoding="utf-8",
    )

    def row_md(row: pd.Series, tag: str = "") -> str:
        return (
            f"| {row['book']} {tag} | {pct(row['ret'])} | {pct(row['maxDD'])} | {pct(row['CAGR'])} | "
            f"{row['Calmar']:.2f} | {pct(row['2020-22_ret'])}/{pct(row['2020-22_DD'])}/{row['2020-22_Calmar']:.2f} | "
            f"{pct(row['2023-26_ret'])}/{pct(row['2023-26_DD'])}/{row['2023-26_Calmar']:.2f} | "
            f"{row['avgL']:.2f} | {100*row['avg_park_frac']:.1f}% |"
        )

    report = f"""# REPORT · SPIKE-S20-CASH-BOND-SLEEVE-LIVE1430（现金/债空槽停放邻档）

## 1. 准则原文

```
{criterion_src.strip()}
```

## 2. 实现要点

- **B45 FACE 基线**：`{BASELINE}` 复用 BTHETA 同窗持仓 + 原版 TV（空仓周 = 纯现金）。
- **邻档唯一改动**：max5 **槽位** 1/5；未满槽名义停放 **511010 / 511260 / cash stub(0)**；权益腿仍 spike+S20+E0+TV25。
- **空周** {st_slots['empty_weeks']}（{100*st_slots['empty_week_pct']:.1f}%）· **部分填席** {st_slots['partial_fill_weeks']}（{100*st_slots['partial_week_pct']:.1f}%）。
- {align_note}
- **红线**：研究 only；**不启 LIVE 债袖**；**不换冠**；不写 strategy_exec / LIVE_OPS。

## 债券日线

- 来源：`bond_daily/*.csv`（mf-hold 日线 × zsmcp `qt_dailyquote` 2024-02-26 锚定缩放）；上市前用常数日漂移外推（见 `extend_bond_backward`）。
- 续跑：可用 zsmcp 全历史覆盖 `bond_daily/` 后重跑。

## 3. 主表（vs B45 FACE）

| book | ret | maxDD | CAGR | Calmar | 2020–22 | 2023–26 | avgL | 均停放占比 |
|---|---:|---:|---:|---:|---|---|---:|---:|
{row_md(face, '**FACE**')}
{row_md(bcash, '邻档')}
{row_md(b010, '邻档')}
{row_md(b260, '邻档')}

### Δ vs FACE（pp）

| 邻档 | Δret | ΔMDD | ΔabsMDD | ΔCalmar |
|---|---:|---:|---:|---:|
| CASH slot | {dcash['dret_pp']:+.1f} | {dcash['dMDD_pp']:+.1f} | {dcash['d_absMDD_pp']:+.1f} | {dcash['dCalmar']:+.2f} |
| 511010 | {d010['dret_pp']:+.1f} | {d010['dMDD_pp']:+.1f} | {d010['d_absMDD_pp']:+.1f} | {d010['dCalmar']:+.2f} |
| 511260 | {d260['dret_pp']:+.1f} | {d260['dMDD_pp']:+.1f} | {d260['d_absMDD_pp']:+.1f} | {d260['dCalmar']:+.2f} |

## 4. 一句证伪或通过

{verdict}

耗时 {summary['elapsed_sec']}s。日历终点 **{actual_end}**。
"""
    (OUT / "REPORT.md").write_text(report, encoding="utf-8")
    print(verdict, flush=True)
    print("done", OUT, flush=True)


if __name__ == "__main__":
    main()
