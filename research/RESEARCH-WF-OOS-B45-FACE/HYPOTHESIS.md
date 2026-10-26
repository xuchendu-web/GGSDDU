# HYPOTHESIS · RESEARCH-WF-OOS-B45-FACE

## 冻结面层（B45 face book）

| 维度 | 设定 |
|------|------|
| Breadth | **B45**（face `risk_on`，宽基 breadth≥45%） |
| 池 / 填席 | `spike_ft` **max5** + **SHARPE20** |
| 出场 | **E0** |
| 总暴露 | **TV25**（σ\*=0.25）为全样本对照；WF 内仅轻调 TV |
| 信号 / 成交 | Fri≥14:30 → 当周收盘（LIVE1430 研究口径） |
| 成本 / 杠杆 | **0.2% RT**；**L≤1** |
| 池 | 研究池（AUM≥2亿），非实盘 / 非 champion |

## Walk-forward 协议（kovainvest 式）

- **Train / Test / Step**：104 周 / 26 周 / 26 周，滚动前进。
- **轻调轴（本刀唯一）**：**TV σ\*** ∈ {22, 25, 28, 33}（映射 0.22–0.33）；不在 WF 内动 breadth / 填席 / 出场。
- **Train 内选型**：各 TV 在 train 窗拼接日收益上取 **Calmar 最大**；胜出 σ\* 用于紧随其后的 **26 周 OOS**，无 test 窥视。
- **评判**：以 **OOS 拼接净值** 的 Calmar / Sharpe / maxDD / 周胜率 为准；全样本冻结 TV25 仅作过拟合对照。

## 过拟合红旗（机械）

1. OOS Calmar < **50%** × 全样本 face Calmar；或
2. 全样本 Calmar > 0.3 且 OOS Calmar < 0.15。

**本跑结论**：overfit_flag = **False** — 未触发红旗。
