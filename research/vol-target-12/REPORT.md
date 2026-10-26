# REPORT · VOL-TARGET-12-B45

## 锚（FACE · TV25，无 VT12 叠加）

| | ret | maxDD | Calmar |
|---|---:|---:|---:|
| inventory | 131.6% | -18.8% | 0.70 |
| 本跑 FACE | 131.6% | -18.8% | 0.70 |

锚复现：**OK**

## 主表

| book | ret | maxDD | Calmar | vol | 2023–26 ret | avgL |
|---|---:|---:|---:|---:|---:|---:|
| FACE | 131.6% | -18.8% | 0.70 | 17.5% | 94.8% | 0.84 |
| VT12 | 85.4% | -18.2% | 0.52 | 14.7% | 72.7% | 0.68 |

Δret=-46.3pp；Δ|MDD|=-0.6pp；盖住=False；2023–26 不差=False。

交叉引用：VT10/VT15 见 **PR#73** `research/vol-target-10-15-b45`（日频 σ̂ 网格，本刀仅 12% + 周频 σ̂）。

## 波动口径

- **VT12 主口径**：邻居 σ̂ 中位数（仅记账）：12w≈18.1%，40w≈19.6%；主口径 20w。
- **FACE**：日频 max(σ20,σ60)×√252，σ*=25%。

## 近似

- 延窗研究缓存：week/day 合并 recon week_2026-10-23 / day_2026-10-23；缺日线用 sina 收益链拼接（研究目录）
- 14:30 新周（09-30/10-09/10-16/10-23）pytdx idx209 拉入 research_cache；旧周复用 fri_1430_through_20260925
- B45/B50 breadth/risk_on：face holdings_ro2_extended 列 b / risk_on（B50: b≥0.50）
- HYST-M3：滞回 M=3；TV33：σ*=0.33 同 B45 持仓；CASH-511010：空仓周 TV25 持 511010
- qfq_1430 = price_1430 × (day/tema qfq 收 / sina 收)；Sharpe 窗截至信号日前一交易日
- 成交/净值：信号周末交易日收盘填仓 + TV25 + 0.2%RT；L≤1
- VT12：σ̂_w=std(近20个 Fri–Fri 未杠杆周收益)×√52；每周五调 L=min(1,0.12/σ̂_w)
- FACE 锚：TV25 daily max(σ20,σ60) 与 SPIKE-S20-EXTEND-REBASE LIVE1430-B45-S20 一致
- 邻居 VT10/VT15 见 PR#73 research/vol-target-10-15-b45（不重跑网格）

## 归因

见 `ATTRIBUTION.md`、`attribution_yearly.csv`、`attribution_by_name_year.csv`。

## 结论

**证伪（不换冠）**：VT12 相对 FACE 未同时满足 Calmar/ret/|MDD| 探索尺子或 2023–26 踏空；Δret=-46.3pp Δ|MDD|=-0.6pp covers=False rear_ok=False。

耗时约 6.0s。
