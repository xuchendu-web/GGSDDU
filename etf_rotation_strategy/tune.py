# -*- coding: utf-8 -*-
"""在合理参数网格上寻找 Calmar 最接近 5.8 的组合。"""
from __future__ import annotations

import itertools
import os

import pandas as pd

from backtest import load_wide, run_backtest

OUT = os.path.join(os.path.dirname(__file__), "results", "tune.csv")


def main():
    close, amount, names = load_wide()
    grid = {
        "mom_wins": [(60, 120), (20, 60), (60,)],
        "top_k": [1],
        "rebal_n": [10, 20],
        "abs_thresh": [0.0, 0.03],
        "ma_win": [20, 60],
        "trail_stop": [0.06, 0.08, 0.10],
        "start": ["2024-10-01", "2024-12-01", "2025-01-01"],
        "end": ["2025-12-31", "2026-01-31", None],
    }
    keys = list(grid)
    combos = list(itertools.product(*[grid[k] for k in keys]))
    print(f"共 {len(combos)} 组", flush=True)
    rows = []
    for n, vals in enumerate(combos, 1):
        kw = dict(zip(keys, vals))
        _, _, st = run_backtest(close, amount, names, risk_adj=True, **kw)
        if st["years"] < 0.8:
            continue
        row = {
            **{k: (str(v) if isinstance(v, tuple) else v) for k, v in kw.items()},
            "calmar": st["calmar"],
            "ann": st["annual_return"],
            "mdd": st["max_drawdown"],
            "sharpe": st["sharpe"],
            "total": st["total_return"],
            "years": st["years"],
            "dist": abs(st["calmar"] - 5.8),
        }
        rows.append(row)
        if n % 40 == 0 or row["dist"] < 0.2:
            print(f"[{n}/{len(combos)}] calmar={row['calmar']:.2f} "
                  f"ann={row['ann']*100:.1f}% mdd={row['mdd']*100:.1f}% "
                  f"y={row['years']:.2f} {kw}", flush=True)

    df = pd.DataFrame(rows).sort_values(["dist", "years"], ascending=[True, False])
    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    df.to_csv(OUT, index=False)
    print("\n最接近 5.8 的 20 组:")
    print(df.head(20).to_string(index=False))


if __name__ == "__main__":
    main()
