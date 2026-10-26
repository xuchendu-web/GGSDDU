# REPORT · B45-MAXDD-GATE-SPIKE-S20

## 1. 准则原文

```
# B45-MAXDD-GATE-SPIKE-S20

- 编号 / 日期 / 来源：B45-MAXDD-GATE-SPIKE-S20 / 2026-10-26 / 研究池机械批
- 批次 ID：CLOUD-B45-MAXDD-GATE
- 性质：**路径 MaxDD 硬闸 + 邻档 20%**（面层规则冻结）

## 准则原文

在 **B45 面层 SPIKE-S20**（breadth≥45% + spike_ft max5 + E0 + TV25 + SHARPE20 填席）上，叠加**路径回撤硬闸/去杠杆**，使全样本 **maxDD≤15%**；并跑 **20% 邻档**对照。

- 成交：Fri ≥14:30 / 当日收盘；**0.2%RT**；**L≤1**
- 对照：**无闸 FACE**（同窗 B45+S20）
- 评分维度：Calmar / turnover / ret / Sharpe vs 无闸

## 改动点（唯一）

日频路径闸：在距 **−θ** 的最后 **5pp** 区间线性去杠杆（满曝→0）；触及 **−θ** 当日硬底曝光=0。仅缩放 TV25 后日收益链，不改 spike 信号与填席。

## 假设

15% 闸在明显牺牲 ret 的同时把 |MDD| 压到 ≤15%，Calmar 相对无闸仍可比；20% 邻档 ret 更高、|MDD| 介于两档之间。

## 证伪

15% 闸 realized maxDD 仍 **>15.5%**；或 Calmar/Sharpe 全面劣于无闸且 ret 损失 **>10pp** 而无换手改善。

## 主表

无闸 FACE + DD15 + DD20；产物 `strategy-weekly/spike_mom_rank/B45-MAXDD-GATE-SPIKE-S20/`

## 共用冻结

- 研究池 ≠ 实盘池；**不换冠**
- 不碰 strategy_exec / LIVE_OPS / 冠军主钉 / 固收+ / 红利袖
- 窗与 EXTEND-REBASE 对齐（≥2026-10-23）

## 交付

四件套 REPORT（准则原文→实现要点→主表→一句证伪或记正）。
```

## 2. 实现要点

- **面层冻结**：B45 breadth + spike_ft max5 + SHARPE20 + E0 + TV25；Fri≥14:30/收盘；0.2%RT；L≤1。
- **唯一叠加**：日频路径闸——距 −θ 最后 5pp 线性去杠杆，触及 −θ 硬底曝光=0；θ=15% 主档、20% 邻档。
- **引擎**：复用 `SPIKE-S20-EXTEND-REBASE-LIVE1430` simulate + `run_live_tv`；数据 `CLOUD-BATCH-2026-10-26`。
- **红线**：研究池；不换冠；未写 strategy_exec / LIVE_OPS。

| 覆盖 | 值 |
|---|---|
| 样本终点 | 2026-10-23 |
| 日历周 | 349 |
| 可投池 | 324 |

## 3. 主表（vs 无闸 FACE）

| book | ret | maxDD | CAGR | Calmar | Sharpe | avgTO | 2020–22 ret/DD | 2023–26 ret/DD | avgL | cash周% |
|---|---:|---:|---:|---:|---:|---:|---|---|---:|---:|
| FACE-B45-S20-UNGATED | 131.6% | -18.8% | 13.1% | 0.70 | 0.82 | 0.243 | 18.9%/-16.0% | 94.8%/-13.8% | 0.84 | 43.1% |
| FACE-B45-S20-DD15 | 4.7% | -15.0% | 0.7% | 0.05 | 0.12 | 0.313 | 4.8%/-14.9% | -0.1%/-0.3% | 0.30 | 43.1% |
| FACE-B45-S20-DD20 | 13.6% | -19.9% | 1.9% | 0.10 | 0.21 | 0.279 | 18.9%/-16.0% | -4.4%/-11.8% | 0.54 | 43.1% |

### Δ vs 无闸 FACE

| 闸 | Δret | Δ|MDD| | ΔCalmar | ΔSharpe | ΔavgTO | gate_ok |
|---|---:|---:|---:|---:|---:|---|
| DD15 | -126.9pp | -3.8pp | -0.65 | -0.70 | +0.071 | True |
| DD20 | -118.0pp | +1.1pp | -0.60 | -0.61 | +0.036 | True |

## 4. 一句证伪或通过

**证伪**：DD15 虽控回撤（MDD=-15.0%），但 ret 损失 -126.9pp、Calmar Δ-0.65、Sharpe Δ-0.70，全面劣于无闸 FACE。

耗时约 5.8s。
