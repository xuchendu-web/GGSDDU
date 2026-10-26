# BREADTH-SOFT-HALF-B45

- 编号 / 日期 / 来源：BREADTH-SOFT-HALF-B45 / 2026-10-26 / Michael 语音·烧 Cursor（悟空）
- 批次 ID：CLOUD-SOFT-HALF
- 性质：MA20 宽度 **软门**（非 BCONF2）vs 硬门 face 对照

## 准则原文

相对 B45 face（硬门 `b<0.45` 全空），**唯一改动**为宽度软门：

- `b = MA20` 宽度（extended face）
- `b ≥ 0.45` → 满规则仓（face）
- `0.35 ≤ b < 0.45` → 目标仓位 ×**0.5**（仍按 S20 选品）
- `b < 0.35` → 空仓

对照：**B45 硬门 face**（`b<0.45` 全空）；**B50 硬门**记正旁注（勿改实盘）。

邻档：`thr` 对 **(0.40/0.30)** 或半仓系数 **0.33 / 0.66**。

面层其余冻结：spike max5 + E0 + TV25 + S20；Fri≥14:30；0.2%RT；L≤1。

跳过：NOBREADTH、BCONF2、OR/AND mom 门（已证伪同构）。

## 假设

**H1**：软门不能在「Δret 盖 Δ|MDD|」且「强势段不踏空」上战胜硬门 face。

## 证伪 H1

主软门 `SOFT4535-H50` 相对 B45 face 同时满足：总收益/Calmar 占优、Δret 盖住 Δ|MDD|、2023–26 不塌。

## 邻档说明

- 阈值邻档：`SOFT4030-H50`（0.40/0.30 + 半仓 0.5）
- 半仓邻档：`SOFT4535-H33` / `SOFT4535-H66`

## 主表

主软门 + B45 face + B50 旁注 + 邻档；产物 `research/breadth-soft-half-b45/`

## 共用冻结

- 成交：Fri ≥14:30 / 当日收盘；0.2%RT；**L≤1**
- 面层：breadth 门（本刀软/硬）+ spike_ft max5 + E0 + TV25 + SHARPE20
- 研究池 ≠ 实盘池；**不换冠**；不碰 strategy_exec / LIVE_OPS / 冠军主钉
- 探索尺子：Δret 须盖住 Δ|MDD|；报 2020–22 / 2023–26；强势段不踏空

## 交付

四件套；云端一次扫完全书。

