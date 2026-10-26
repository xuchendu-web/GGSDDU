# REPORT · COMPRESSION-BREAKOUT-LIVE1430

研究池四件套：FACE vs N∈{4,6,8} 周压缩突破门控（spike 填席新增）。

## 组合主表

| book | N | ret | maxDD | Calmar | hit-rate | win-size | n_entries | Δret | Δ|MDD| | Δhit | Δwin-size |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| FACE-B45-S20-LIVE1430 | — | 68.1% | -25.4% | 0.31 | 56.8% | 1.04 | 475 | +0.0% | +0.0% | +0.0% | +0.00 |
| CB-N4 | 4.0 | 7.9% | -23.5% | 0.05 | 31.6% | 1.01 | 19 | -60.3% | -2.0% | -25.3% | -0.03 |
| CB-N6 | 6.0 | 5.5% | -24.1% | 0.03 | 40.0% | 1.15 | 20 | -62.7% | -1.3% | -16.8% | +0.12 |
| CB-N8 | 8.0 | -17.1% | -21.1% | -0.13 | 35.7% | 0.68 | 14 | -85.2% | -4.3% | -21.1% | -0.36 |

## FACE 参照
- ret 68.1% · maxDD -25.4% · Calmar 0.31
- 入场 hit-rate 56.8% · win-size 1.04 · n=475

## 一句结论（探索记账，不换冠）
**探索记账**：邻档未同时在 hit-rate 与 win-size 上优于 FACE；见主表 Δ 列。

耗时约 19.2s。产物：`run.py` / `criterion.md` / `REPORT.md` / `summary.json` / `table.csv` / `entry_quality_vs_face.csv` / `equity_curve.png`