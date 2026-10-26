# REPORT · RESEARCH-TSMOM-12M-LONGFLAT-WEEKLY

## 结论
**FALSIFIED**（主刀 TSMOM-12M-max5 vs B45+S20 研究面）

## 主表（scorecard vs B45 face）
| book | ret | maxDD | Calmar | Sharpe | Sortino | 2020–22 ret | 2023–26 ret | turnover |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| B45+S20 face（参照） | 134.0% | -18.9% | 0.70 | — | — | 18.8% | 97.0% | — |
| **TSMOM-12M-max5** | 90.1% | -44.1% | 0.23 | 0.47 | 0.65 | 90.7% | -0.3% | 8.3x |
| TSMOM-12M-allpos | 24.0% | -38.0% | 0.08 | — | — | — | — | — |

## 探索尺子
- Δret vs face: -43.9%；Δ|MDD|: 25.3%
- 尺子盖住（Δret ≥ Δ|MDD|）: **False**
- 2023–26 踏空（< face×0.85）: **True**

## 邻档 & 旁注
见 `scorecard.csv`（6M/9M max5）；波动率缩放 12% ann 见 `vol_scale_side_table.csv`。

## 实现
- 信号：日频收盘价 2020-01-03 → 2026-10-16 回看 6/9/12 月总收益 >0 则 risk-on，否则现金。
- 调仓：研究周历（510300 week grid）；0.2% RT；L≤1。
- 主刀权重：正动量按 12m 收益取前 5 等权；对照 all-positive 等权全持。

产物目录：`research/RESEARCH-TSMOM-12M-LONGFLAT-WEEKLY/`
