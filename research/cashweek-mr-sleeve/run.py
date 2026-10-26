#!/usr/bin/env python3
"""CASHWEEK-MR-SLEEVE: mild mean-reversion bond sleeve on B45 breadth-forced cash weeks.

Books vs B45 FACE (frozen spike_ft max5 + S20 + E0 + TV25 + B45 hard gate):
  LIVE1430-B45-S20-max5              — FACE
  LIVE1430-B45-CASHWEEK-MR           — 4w min-return MR sleeve (511010/511260)
  LIVE1430-B45-CASHWEEK-511010       — neighbor: always 511010 on forced-cash weeks
  LIVE1430-B45-CASHWEEK-511260       — neighbor: always 511260 on forced-cash weeks

Research only — no crown / LIVE edits.
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

from bond_inventory import SLEEVE_CODES, ensure_bond_daily, inventory_report

OUT = Path(__file__).resolve().parent
KIT = OUT.parent / "cloud_batch" / "CLOUD-BATCH-2026-10-26"
BTHETA = OUT.parent / "cloud_batch" / "SPIKE-S20-BTHETA-GRID-LIVE1430"
BOND_DIR = KIT / "data" / "research_cache" / "bond_daily"
KNIFE_MD = KIT / "knives" / "CASHWEEK-MR-SLEEVE.md"

EVAL_START = "2020-01-03"
END_S = "2026-10-23"
LIVE_COST_RT = 0.002
LOOKBACK_WEEKS = 4
TRADING_DAYS_4W = 20
BREADTH_THETA = 0.45

BASELINE = "LIVE1430-B45-S20-max5"
BOOKS = [
    (BASELINE, "face", None),
    ("LIVE1430-B45-CASHWEEK-MR", "mr", None),
    ("LIVE1430-B45-CASHWEEK-511010", "fixed", "511010"),
    ("LIVE1430-B45-CASHWEEK-511260", "fixed", "511260"),
]


def write_summary(path: Path, payload: dict) -> None:
    def _default(o: object):
        if isinstance(o, float) and (math.isnan(o) or math.isinf(o)):
            return None
        raise TypeError(type(o))

    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2, default=_default), encoding="utf-8")


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


def load_bond_closes(codes: tuple[str, ...], days: pd.DatetimeIndex) -> dict[str, pd.Series]:
    out: dict[str, pd.Series] = {}
    for code in codes:
        fp = BOND_DIR / f"{code}.csv"
        if not fp.exists():
            raise FileNotFoundError(fp)
        df = pd.read_csv(fp, parse_dates=["date"])
        s = df.set_index("date")["close"].astype(float).sort_index()
        s = s.reindex(days).ffill()
        out[code] = s
    return out


def ret_4w_on(close: pd.Series, d: pd.Timestamp) -> float | None:
    sub = close.loc[:d]
    if len(sub) < TRADING_DAYS_4W + 1:
        return None
    c0 = float(sub.iloc[-1])
    c1 = float(sub.iloc[-(TRADING_DAYS_4W + 1)])
    if c1 <= 0:
        return None
    return c0 / c1 - 1.0


def pick_mr_sleeve(bond_px: dict[str, pd.Series], d: pd.Timestamp) -> list[str]:
    rets: dict[str, float] = {}
    for code in SLEEVE_CODES:
        r = ret_4w_on(bond_px[code], d)
        if r is not None and np.isfinite(r):
            rets[code] = r
    if not rets:
        return []
    min_r = min(rets.values())
    if min_r >= 0:
        return []
    winners = [c for c, r in rets.items() if abs(r - min_r) < 1e-12]
    return winners


def load_calendar_risk() -> tuple[list[str], dict[str, bool]]:
    hp = BTHETA / f"holdings_{BASELINE}.csv"
    if not hp.exists():
        raise SystemExit(f"missing {hp}")
    hdf = pd.read_csv(hp)
    hdf["date"] = hdf["date"].astype(str).str[:10]
    calendar = sorted(hdf["date"].unique().tolist())
    risk: dict[str, bool] = {}
    for _, row in hdf.iterrows():
        d = str(row["date"])[:10]
        ro = row.get("risk_on")
        risk[d] = bool(int(ro)) if ro is not None and not (isinstance(ro, float) and math.isnan(ro)) else False
    return calendar, risk


def build_sleeve_schedule(
    calendar: list[str],
    risk: dict[str, bool],
    bond_px: dict[str, pd.Series],
    mode: str,
    fixed_code: str | None,
) -> tuple[dict[str, list[str]], dict]:
    """Friday -> list of sleeve codes (empty = cash). Only used when risk_off."""
    sched: dict[str, list[str]] = {}
    forced = 0
    active = 0
    hits = 0
    active_weeks = 0
    blocked_data = 0

    for i, d in enumerate(calendar[:-1]):
        if risk.get(d, False):
            sched[d] = []
            continue
        forced += 1
        ts = pd.Timestamp(d)
        if mode == "face":
            sched[d] = []
            continue
        if mode == "fixed":
            picks = [fixed_code] if fixed_code else []
        else:
            picks = pick_mr_sleeve(bond_px, ts)
            if not picks and any(ret_4w_on(bond_px[c], ts) is None for c in SLEEVE_CODES):
                blocked_data += 1
        sched[d] = picks
        if picks:
            active += 1
            active_weeks += 1
            nxt = calendar[i + 1]
            seg_days = bond_px[picks[0]].index[(bond_px[picks[0]].index > ts) & (bond_px[picks[0]].index <= pd.Timestamp(nxt))]
            if len(seg_days) >= 2:
                w = 1.0 / len(picks)
                r_w = 0.0
                for c in picks:
                    seg = bond_px[c].loc[seg_days]
                    r_w += w * (float(seg.iloc[-1] / seg.iloc[0]) - 1.0)
                if r_w > 0:
                    hits += 1

    meta = {
        "forced_cash_weeks": forced,
        "sleeve_active_weeks": active,
        "sleeve_hit_rate": hits / max(1, active_weeks),
        "sleeve_blocked_weeks": blocked_data,
    }
    return sched, meta


def apply_sleeve_overlay(
    r_face: pd.Series,
    calendar: list[str],
    risk: dict[str, bool],
    sched: dict[str, list[str]],
    bond_px: dict[str, pd.Series],
) -> pd.Series:
    r = r_face.copy()
    prev_w: dict[str, float] = {}
    days = r.index

    for i, d in enumerate(calendar[:-1]):
        if risk.get(d, False):
            prev_w = {}
            continue
        picks = sched.get(d, [])
        ts = pd.Timestamp(d)
        nxt = pd.Timestamp(calendar[i + 1])
        seg = days[(days > ts) & (days <= nxt)]
        if len(seg) == 0:
            continue
        new_w = {c: 1.0 / len(picks) for c in picks} if picks else {}
        to = sum(abs(new_w.get(k, 0) - prev_w.get(k, 0)) for k in set(new_w) | set(prev_w))
        cost = to * LIVE_COST_RT / 2.0
        prev_w = new_w

        if not picks:
            r.loc[seg] = 0.0
            if cost and seg[0] in r.index:
                r.loc[seg[0]] -= cost
            continue

        daily_sleeve = pd.Series(0.0, index=seg)
        for c, w in new_w.items():
            px = bond_px[c].reindex(seg).ffill()
            dr = px.pct_change().fillna(0.0)
            daily_sleeve += w * dr
        r.loc[seg] = daily_sleeve.values
        if cost and seg[0] in r.index:
            r.loc[seg[0]] -= cost

    return r


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    t0 = time.time()

    inv = inventory_report()
    bond_status = ensure_bond_daily(allow_fetch=False)
    if not bond_status["ok"]:
        summary = {
            "title": "CASHWEEK-MR-SLEEVE",
            "status": "BLOCKED",
            "blocked": bond_status["blocked"],
            "inventory": inv,
            "bond_actions": bond_status.get("actions"),
            "verdict": "BLOCKED：现金袖债史不足或缺失，未做 drift 回填。见 inventory / blocked。",
        }
        write_summary(OUT / "summary.json", summary)
        (OUT / "REPORT.md").write_text(
            "# REPORT · CASHWEEK-MR-SLEEVE\n\n## 状态：BLOCKED\n\n"
            + json.dumps(summary, ensure_ascii=False, indent=2)
            + "\n",
            encoding="utf-8",
        )
        print("BLOCKED", bond_status["blocked"], flush=True)
        sys.exit(2)

    nav_fp = BTHETA / f"nav_{BASELINE}.csv"
    if not nav_fp.exists():
        raise SystemExit(f"missing {nav_fp}")
    bn = pd.read_csv(nav_fp, index_col=0, parse_dates=True).iloc[:, 0].sort_index()
    days = bn.index[(bn.index >= EVAL_START) & (bn.index <= END_S)]
    r_face = bn.pct_change().fillna(0.0)

    calendar, risk = load_calendar_risk()
    bond_px = load_bond_closes(SLEEVE_CODES, days)

    table_rows = []
    series: dict[str, pd.Series] = {}
    sleeve_meta: dict[str, dict] = {}

    for name, mode, fixed in BOOKS:
        if mode == "face":
            r = r_face.reindex(days).fillna(0.0)
            meta = {
                "forced_cash_weeks": sum(1 for d in calendar[:-1] if not risk.get(d, False)),
                "sleeve_active_weeks": 0,
                "sleeve_hit_rate": float("nan"),
            }
        else:
            sched, meta = build_sleeve_schedule(calendar, risk, bond_px, mode, fixed)
            r = apply_sleeve_overlay(r_face, calendar, risk, sched, bond_px)
            if mode == "mr":
                pd.DataFrame(
                    [{"date": d, "picks": ",".join(sched.get(d, []))} for d in calendar[:-1] if not risk.get(d, False)]
                ).to_csv(OUT / "sleeve_picks.csv", index=False)

        series[name] = r
        sleeve_meta[name] = meta
        st = stats_full(r)
        r2022 = r[(r.index >= "2020-01-01") & (r.index <= "2022-12-31")]
        r2023 = r[r.index >= "2023-01-01"]
        st2022 = stats_full(r2022) if len(r2022) > 5 else {k: float("nan") for k in st}
        st2023 = stats_full(r2023) if len(r2023) > 5 else {k: float("nan") for k in st}
        table_rows.append(
            {
                "book": name,
                **st,
                "2020-22_ret": st2022["ret"],
                "2020-22_DD": st2022["maxDD"],
                "2020-22_Calmar": st2022["Calmar"],
                "2023-26_ret": st2023["ret"],
                "2023-26_DD": st2023["maxDD"],
                "2023-26_Calmar": st2023["Calmar"],
                **meta,
            }
        )
        (1 + r).cumprod().to_csv(OUT / f"nav_{name}.csv", header=["nav"])
        print(f"{name}: ret={pct(st['ret'])} dd={pct(st['maxDD'])} Calmar={st['Calmar']:.2f}", flush=True)

    df = pd.DataFrame(table_rows)
    df.to_csv(OUT / "table.csv", index=False)
    df.to_csv(OUT / "metrics.csv", index=False)

    face = df[df.book == BASELINE].iloc[0]
    mr = df[df.book == "LIVE1430-B45-CASHWEEK-MR"].iloc[0]

    def delta(row: pd.Series) -> dict[str, float]:
        return {
            "dret_pp": (row["ret"] - face["ret"]) * 100,
            "dMDD_pp": (row["maxDD"] - face["maxDD"]) * 100,
            "d_absMDD_pp": (abs(row["maxDD"]) - abs(face["maxDD"])) * 100,
            "dCalmar": row["Calmar"] - face["Calmar"],
        }

    d_mr = delta(mr)

    def covers(d: dict[str, float]) -> bool:
        return float(mr["Calmar"]) >= float(face["Calmar"]) or d["dret_pp"] >= d["d_absMDD_pp"] - 1e-9

    falsify: list[str] = []
    if not covers(d_mr):
        falsify.append("主袖未达 Calmar≥FACE 且 Δret 未盖住 Δ|MDD|")
    if float(mr["2023-26_ret"]) < float(face["2023-26_ret"]) - 0.01:
        falsify.append("2023–26 收益弱于 FACE ≥1pp")
    if float(mr["2023-26_Calmar"]) < float(face["2023-26_Calmar"]) - 0.05:
        falsify.append("2023–26 Calmar 系统性偏弱")

    if falsify:
        verdict = "**证伪（研究记负；不换冠）**：" + "；".join(falsify) + "。"
    else:
        verdict = (
            f"**探索记正（不换冠）**：主袖 Calmar {float(mr['Calmar']):.2f} vs FACE {float(face['Calmar']):.2f}；"
            f"Δret={d_mr['dret_pp']:+.2f}pp Δ|MDD|={d_mr['d_absMDD_pp']:+.2f}pp；"
            f"强制现金周={int(mr['forced_cash_weeks'])} 袖激活={int(mr['sleeve_active_weeks'])} "
            f"命中率={100*float(mr['sleeve_hit_rate']):.1f}%。"
        )

    summary = {
        "title": "CASHWEEK-MR-SLEEVE",
        "status": "OK",
        "unique_change": "breadth-forced cash weeks only: 4w min-return MR on 511010/511260",
        "baseline_face": BASELINE,
        "inventory": inv,
        "bond_materialize": bond_status,
        "sleeve_set": list(SLEEVE_CODES),
        "forced_cash_weeks": int(mr["forced_cash_weeks"]),
        "sleeve_active_weeks": int(mr["sleeve_active_weeks"]),
        "sleeve_hit_rate": float(mr["sleeve_hit_rate"]),
        "table": table_rows,
        "delta_vs_face_mr": d_mr,
        "falsify": bool(falsify),
        "verdict": verdict,
        "elapsed_sec": round(time.time() - t0, 1),
    }
    write_summary(OUT / "summary.json", summary)

    eq = pd.DataFrame({k: (1 + series[k]).cumprod() for k, _, _ in BOOKS})
    eq.to_csv(OUT / "equity.csv")
    eq.to_csv(OUT / "nav_all.csv")

    fig, ax = plt.subplots(figsize=(11, 5.5), dpi=120)
    for name, lw, ls in [
        (BASELINE, 2.0, "-"),
        ("LIVE1430-B45-CASHWEEK-MR", 1.6, "-"),
        ("LIVE1430-B45-CASHWEEK-511010", 1.2, "--"),
        ("LIVE1430-B45-CASHWEEK-511260", 1.2, ":"),
    ]:
        if name in eq.columns:
            ax.plot(eq.index, eq[name], label=name, lw=lw, ls=ls)
    ax.set_yscale("log")
    ax.set_title("CASHWEEK-MR-SLEEVE vs B45 FACE")
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

    criterion_src = (OUT / "criterion.md").read_text(encoding="utf-8")
    (OUT / "criterion.md").write_text(criterion_src, encoding="utf-8")

    def row_md(row: pd.Series, tag: str = "") -> str:
        hr = row.get("sleeve_hit_rate")
        hr_s = f"{100*hr:.1f}%" if hr is not None and np.isfinite(hr) else "—"
        return (
            f"| {row['book']} {tag} | {pct(row['ret'])} | {pct(row['maxDD'])} | {pct(row['CAGR'])} | "
            f"{row['Calmar']:.2f} | {pct(row['2020-22_ret'])}/{pct(row['2020-22_DD'])}/{row['2020-22_Calmar']:.2f} | "
            f"{pct(row['2023-26_ret'])}/{pct(row['2023-26_DD'])}/{row['2023-26_Calmar']:.2f} | "
            f"{int(row.get('forced_cash_weeks', 0))} | {int(row.get('sleeve_active_weeks', 0))} | {hr_s} |"
        )

    report = f"""# REPORT · CASHWEEK-MR-SLEEVE（广度强制现金周 · 轻度 MR 债袖）

## 1. 准则

见 `criterion.md`。

## 2. 数据盘点

- **现金袖集合**：{", ".join(SLEEVE_CODES)}（`bond_daily/`）；货币 ETF 缓存：{inv.get("money_market_in_cache") or "无"}
- **物化**：{bond_status.get("actions")}
- **红线**：非永久 CASH-511010 idle；仅 `risk_on=0` 周；无 drift 回填。

## 3. 主表

| book | ret | maxDD | CAGR | Calmar | 2020–22 | 2023–26 | 强制现金周 | 袖激活周 | 命中率 |
|---|---:|---:|---:|---:|---|---:|---:|---:|---:|
{row_md(face, "**FACE**")}
{row_md(mr, "**主袖**")}
{row_md(df[df.book=="LIVE1430-B45-CASHWEEK-511010"].iloc[0], "邻档")}
{row_md(df[df.book=="LIVE1430-B45-CASHWEEK-511260"].iloc[0], "邻档")}

### Δ vs FACE（主袖 MR）

| Δret pp | ΔMDD pp | Δ|MDD| pp | ΔCalmar |
|---:|---:|---:|---:|
| {d_mr['dret_pp']:+.2f} | {d_mr['dMDD_pp']:+.2f} | {d_mr['d_absMDD_pp']:+.2f} | {d_mr['dCalmar']:+.2f} |

## 4. 结论

{verdict}

耗时 {summary['elapsed_sec']}s。
"""
    (OUT / "REPORT.md").write_text(report, encoding="utf-8")

    if KNIFE_MD.parent.exists():
        KNIFE_MD.write_text(
            "# CASHWEEK-MR-SLEEVE\n\n"
            + (OUT / "criterion.md").read_text(encoding="utf-8").split("\n", 1)[-1],
            encoding="utf-8",
        )

    print(verdict, flush=True)
    print("done", OUT, flush=True)


if __name__ == "__main__":
    main()
