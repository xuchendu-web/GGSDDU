#!/usr/bin/env python3
"""Refresh Face EQ / SENS / AG40S sidenote NAV + drawdown charts. Research pool only."""
from __future__ import annotations

from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib import font_manager
import pandas as pd

OUT = Path(__file__).resolve().parent / "out"
FONT = "/usr/share/fonts/truetype/wqy/wqy-microhei.ttc"
if Path(FONT).exists():
    font_manager.fontManager.addfont(FONT)
    plt.rcParams["font.sans-serif"] = ["WenQuanYi Micro Hei"]
plt.rcParams["axes.unicode_minus"] = False


def _dd(nav: pd.Series) -> pd.Series:
    return nav / nav.cummax().clip(lower=1e-12) - 1.0


def main() -> None:
    eq = pd.read_csv(OUT / "equity.csv", index_col=0, parse_dates=True)
    ag = pd.read_csv(OUT / "ag40s_equity.csv", index_col=0, parse_dates=True)
    idx = eq.index.union(ag.index).sort_values()
    eq = eq.reindex(idx).ffill()
    ag = ag.reindex(idx).ffill()

    series = {
        "Face EQ T−1（LIVE 映射）": (eq["FACE-EQ-T1"], "#333333", 2.2, "-"),
        "SENS·Face EQ（Sharpe 对齐 14:30）": (eq["FACE-EQ-SENS1430"], "#1f77b4", 2.4, "-"),
        "AG40S-max5（机制旁注）": (ag["AG40S-max5"], "#2ca02c", 1.4, "--"),
        "LOOKAHEAD 收盘（诊断，非锚）": (eq["FACE-EQ-LOOKAHEAD-CLOSE"], "#c44e52", 1.1, ":"),
    }

    fig, axes = plt.subplots(2, 1, figsize=(11.2, 7.4), dpi=140, sharex=True, gridspec_kw={"height_ratios": [3, 1.4]})
    ax, axd = axes
    for label, (s, color, lw, ls) in series.items():
        ax.plot(s.index, s, label=label, color=color, lw=lw, ls=ls)
        axd.plot(s.index, _dd(s), color=color, lw=lw * 0.85, ls=ls)
    ax.set_yscale("log")
    ax.set_ylabel("净值（对数）")
    ax.set_title("研究池 · Face EQ 信息集对齐（2020-01-03→2026-10-23）\n不换冠 · 不改 LIVE / strategy_exec / mast")
    ax.grid(True, alpha=0.28)
    ax.legend(fontsize=8, loc="upper left")
    axd.set_ylabel("回撤")
    axd.yaxis.set_major_formatter(plt.FuncFormatter(lambda x, _p: f"{100 * x:.0f}%"))
    axd.grid(True, alpha=0.28)
    axd.set_xlabel("日期")
    fig.tight_layout()
    fig.savefig(OUT / "equity_nav_dd.png")
    fig.savefig(OUT / "equity_curve.png")
    plt.close(fig)

    # Face EQ only (T-1 vs SENS) — cleaner two-book chart
    fig, axes = plt.subplots(2, 1, figsize=(11.2, 6.6), dpi=140, sharex=True, gridspec_kw={"height_ratios": [3, 1.4]})
    ax, axd = axes
    for label, key, color in (
        ("Face EQ T−1（Sharpe 严格日前）", "FACE-EQ-T1", "#333333"),
        ("SENS·Face EQ（末点 = 信号日 qfq_1430）", "FACE-EQ-SENS1430", "#1f77b4"),
    ):
        s = eq[key]
        ax.plot(s.index, s, label=label, color=color, lw=2.2)
        axd.plot(s.index, _dd(s), color=color, lw=1.8)
    ax.set_yscale("log")
    ax.set_ylabel("净值（对数）")
    ax.set_title("Face EQ：LIVE T−1 vs 信息集对齐到信号日 14:30")
    ax.grid(True, alpha=0.28)
    ax.legend(fontsize=9, loc="upper left")
    axd.set_ylabel("回撤")
    axd.yaxis.set_major_formatter(plt.FuncFormatter(lambda x, _p: f"{100 * x:.0f}%"))
    axd.grid(True, alpha=0.28)
    fig.tight_layout()
    fig.savefig(OUT / "face_eq_t1_vs_sens.png")
    plt.close(fig)
    print("wrote", OUT / "equity_nav_dd.png", OUT / "face_eq_t1_vs_sens.png")


if __name__ == "__main__":
    main()
