# -*- coding: utf-8 -*-
"""2022-2026、每次 1 只 ETF,搜索 Calmar 接近 5.8 的参数。"""
from __future__ import annotations

import itertools
import os

import pandas as pd

from backtest import load_wide, run_backtest

OUT = os.path.join(os.path.dirname(__file__), "results", "tune_2022_2026.csv")
START, END = "2022-01-01", None


def main():
    close, amount, names = load_wide()
    grid = {
        "pick_mode": ["all", "class"],
        "mom_wins": [(20, 60), (60,), (10, 20, 60)],
        "rebal_n": [5, 10],
        "abs_thresh": [0.0, 0.08],
        "ma_win": [20, 60],
        "trail_stop": [0.05, 0.08],
        "risk_adj": [True],
    }
    keys = list(grid)
    combos = list(itertools.product(*[grid[k] for k in keys]))
    print(f"共 {len(combos)} 组  {START} -> {close.index.max().date()}", flush=True)
    rows = []
    for n, vals in enumerate(combos, 1):
        kw = dict(zip(keys, vals), top_k=1, start=START, end=END)
        _, hold, st = run_backtest(close, amount, names, **kw)
        max_n = max((len(hs) for hs in hold.values()), default=0)
        row = {
            **{k: (str(v) if isinstance(v, tuple) else v) for k, v in kw.items()
               if k not in ("start", "end", "top_k")},
            "calmar": st["calmar"],
            "ann": st["annual_return"],
            "mdd": st["max_drawdown"],
            "sharpe": st["sharpe"],
            "total": st["total_return"],
            "years": st["years"],
            "max_hold": max_n,
            "dist": abs(st["calmar"] - 5.8),
        }
        rows.append(row)
        if n % 50 == 0 or row["calmar"] > 1.5 or row["dist"] < 0.5:
            print(f"[{n}/{len(combos)}] calmar={row['calmar']:.2f} "
                  f"ann={row['ann']*100:.1f}% mdd={row['mdd']*100:.1f}% {kw}",
                  flush=True)

    df = pd.DataFrame(rows).sort_values(["calmar"], ascending=False)
    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    df.to_csv(OUT, index=False)
    print("\nCalmar 最高 15 组:")
    print(df.head(15).to_string(index=False))
    print("\n最接近 5.8 的 8 组:")
    print(df.sort_values("dist").head(8).to_string(index=False))


if __name__ == "__main__":
    main()
