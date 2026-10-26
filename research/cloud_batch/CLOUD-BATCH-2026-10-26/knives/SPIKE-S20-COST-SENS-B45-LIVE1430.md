# SPIKE-S20-COST-SENS-B45-LIVE1430

- 编号 / 日期 / 来源：SPIKE-S20-COST-SENS-B45-LIVE1430 / 2026-10-26 / Michael 语音·烧 Cursor（悟空）
- 批次 ID：CLOUD-COST-SENS-B45
- 性质：**往返成本敏感性**（研究池；非 LIVE / 非实盘）

## 准则原文
在 **B45 面层**（breadth≥45% + spike_ft max5 + E0 + TV25）上，冻结 **SPIKE-S20**（Sharpe20 填席）规则；**唯一改动**为单边交易成本假设 ∈ **{0.1%, 0.2%, 0.3%}**（往返 RT = **2×** 单边）。窗 ≥2026-10-23。

对照 **填席排序基线**：同面层下 **AUM-max5** 填席（非 Sharpe20），同窗同成本网格。

## 假设
默认 **0.1% 单边（0.2%RT）** 下 S20 排序相对 AUM 基线仍有 **探索尺子** 优势（Δret 盖住 Δ|MDD|）；成本抬升后优势单调收窄，但需报告 **相对排序是否翻转**（Calmar / 全样本 ret）。

## 证伪
三档成本下 S20 均不优于 AUM（Calmar 与 ret 双输）；或在 **0.2% 单边** 即已翻转 → 记「成本脆弱」。

## 红线
不扫第四档；不改 breadth/TV/滞回/债腿；不叠 B50/STACK；不写 strategy_exec / LIVE_OPS / 实盘池；不换冠。

## 主表
六账（S20×3 + AUM×3）；产物 `research/cloud_batch/SPIKE-S20-COST-SENS-B45-LIVE1430/`

## 共用冻结
- 成交：Fri ≥14:30 / 当日收盘；**L≤1**
- 面层：B45 + spike_ft max5 + E0 + TV25 + SHARPE20（S20 腿）；AUM 腿仅改填席键
- 研究池 ≠ 实盘池
- 探索尺子：Δret 盖住 Δ|MDD|；报 2020–22 / 2023–26

## 交付
四件套 + **排序翻转表**（S20 vs AUM @ 各成本档）。
