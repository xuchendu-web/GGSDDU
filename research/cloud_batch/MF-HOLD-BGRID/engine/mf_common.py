#!/usr/bin/env python3
"""MF-HOLD-BGRID shared helpers (research ledger; paths under cloud_batch)."""
from __future__ import annotations

import math
import os
import sys

os.environ.setdefault("ETF_V", "1016")
ENGINE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, ENGINE)
sys.path.insert(0, "/workspace/etf-momentum/engine")

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

import mom_engine as e

plt.rcParams["font.sans-serif"] = ["Noto Sans CJK SC", "WenQuanYi Zen Hei", "SimHei", "DejaVu Sans"]
plt.rcParams["axes.unicode_minus"] = False

START, END = e.START, e.END
CPS = e.CPS
MF = "511880"
OUT_ROOT = "/workspace/research/cloud_batch/MF-HOLD-BGRID"
SYNC_ROOT = "/workspace/etf-multifreq"
OBS = "/workspace/obsidian-notes/ETF多频专题"

_D = None


def data():
    global _D
    if _D is not None:
        return _D
    d = e.data()
    P = d["P"].copy()
    G, W, SIG = d["G"], d["W"].copy(), d["SIG"].copy()
    if not isinstance(G, pd.DatetimeIndex):
        G = pd.DatetimeIndex(G)
    pool = pd.read_csv("/workspace/etf-correlation/data/research_pool_v2.csv", dtype={"code": str})
    pool["code"] = pool.code.str.zfill(6)
    codes = set(d["codes"])
    aw = sorted(
        set(pool[(pool.l0 == "中国权益") & (pool.family.astype(str).str.startswith("宽基"))].code) & codes
    )
    ind = sorted(
        set(pool[(pool.l0 == "中国权益") & (~pool.family.astype(str).str.startswith("宽基"))].code) & codes
    )
    _D = dict(
        P=P,
        W=W,
        SIG=SIG,
        G=G,
        aw=aw,
        ind=ind,
        Open=pd.DataFrame(),
        codes=list(codes),
        gi={g: i for i, g in enumerate(G)},
        reb=[g for g in G if g >= pd.Timestamp(START) and g <= pd.Timestamp(END)][:-1],
    )
    return _D


def stats(s):
    return e.stats(s)


def yearly(s):
    return e.yearly(s)


def mdd(s, a, b):
    q = (1 + s[(s.index >= a) & (s.index <= b)]).cumprod()
    if len(q) < 2:
        return np.nan
    return (q / q.cummax() - 1).min()


def fmt_pct(x):
    if x is None or (isinstance(x, float) and (math.isnan(x) or math.isinf(x))):
        return "—"
    return f"{100 * x:.1f}%"


def fmt_cal(x):
    if x is None or (isinstance(x, float) and (math.isnan(x) or math.isinf(x))):
        return "—"
    return f"{x:.2f}"


def run_weekly(wmap, record=None):
    return e.run_weights(lambda i, dd: wmap.get(dd, {}), record=record)


def champ():
    raise KeyError("champion bench omitted — no LIVE stack in cloud_batch ledger")


def row(k, r, to, ex, extra=None):
    s = stats(r)
    a = stats(r[r.index <= "2022-12-31"])
    b = stats(r[r.index >= "2023-01-01"])
    out = dict(
        book=k,
        ret=s["ret"],
        maxDD=s["maxDD"],
        CAGR=s["CAGR"],
        Calmar=s["Calmar"],
        ret20_22=a["ret"],
        dd20_22=a["maxDD"],
        cal20_22=a["Calmar"],
        ret23_26=b["ret"],
        dd23_26=b["maxDD"],
        cal23_26=b["Calmar"],
        dd_down2109_2409=mdd(r, "2021-09-01", "2024-09-30"),
        turnover=to,
        avg_expo=ex,
    )
    if extra:
        out.update(extra)
    return out


def deliver(ID, books, main, title, report_md, attr_md=None):
    for out in (OUT_ROOT, f"{SYNC_ROOT}/{ID}"):
        os.makedirs(out, exist_ok=True)
        rows = []
        for k, v in books.items():
            r, to, ex = v[0], v[1], v[2]
            extra = v[3] if len(v) > 3 else None
            rows.append(row(k, r, to, ex, extra))
        M = pd.DataFrame(rows)
        M.to_csv(f"{out}/metrics.csv", index=False)
        Y = pd.concat([yearly(v[0]).assign(book=k) for k, v in books.items()])
        Y.to_csv(f"{out}/yearly.csv", index=False)
        nav = pd.DataFrame({k: (1 + v[0]).cumprod() for k, v in books.items()})
        nav.to_csv(f"{out}/nav.csv")
        fig, ax = plt.subplots(figsize=(11, 5.5), dpi=120)
        for k in nav:
            ax.plot(nav.index, nav[k], label=k, lw=2.2 if k == main else 1.1)
        ax.set_yscale("log")
        ax.grid(alpha=0.3)
        ax.legend(fontsize=7)
        ax.set_title(title)
        fig.tight_layout()
        fig.savefig(f"{out}/nav.png")
        plt.close(fig)
        open(f"{out}/REPORT.md", "w", encoding="utf-8").write(report_md)
        if attr_md:
            open(f"{out}/ATTRIBUTION.md", "w", encoding="utf-8").write(attr_md)
    return M


def metrics_table(M, main):
    lines = [
        "| book | ret | maxDD | CAGR | Calmar | 2020–22 ret/DD/Cal | 2023–26 ret/DD/Cal | 下跌段DD | 换手(单边/年) | 均仓 |",
        "|---|---:|---:|---:|---:|---|---|---:|---:|---:|",
    ]
    order = [main] + [b for b in M.book if b != main]
    for b in order:
        r = M[M.book == b].iloc[0]
        lines.append(
            f"| {r.book} | {fmt_pct(r.ret)} | {fmt_pct(r.maxDD)} | {fmt_pct(r.CAGR)} | {fmt_cal(r.Calmar)} | "
            f"{fmt_pct(r.ret20_22)}/{fmt_pct(r.dd20_22)}/{fmt_cal(r.cal20_22)} | "
            f"{fmt_pct(r.ret23_26)}/{fmt_pct(r.dd23_26)}/{fmt_cal(r.cal23_26)} | "
            f"{fmt_pct(r.dd_down2109_2409)} | "
            f"{'—' if pd.isna(r.turnover) else f'{r.turnover:.1f}x'} | "
            f"{'—' if pd.isna(r.avg_expo) else f'{r.avg_expo:.2f}'} |"
        )
    return "\n".join(lines)
