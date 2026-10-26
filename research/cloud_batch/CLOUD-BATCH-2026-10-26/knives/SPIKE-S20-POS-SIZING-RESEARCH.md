# SPIKE-S20-POS-SIZING-RESEARCH

- 编号 / 日期 / 来源：SPIKE-S20-POS-SIZING-RESEARCH / 2026-10-26 / CLOUD-BATCH 权重轴
- 批次 ID：CLOUD-POS-SIZING
- 性质：同 S20 入场排序，只改持仓权重（研究池）

## 准则原文
相对 B45+S20 **EQ5 等权**，只改权重方案：
1. **EQ5** — 等权 max5（基线）
2. **INV20W** — 20 周周线已实现波动率倒数加权
3. **CAP30** — 等权后单票上限 30%（超出留现金）

填席仍 **SHARPE20**；E0+TV25 不变。窗 ≥2026-10-23。

## 红线
研究池 ≠ 实盘；不写 strategy_exec / LIVE_OPS；不换冠。

## 交付
四件套至 `research/cloud_batch/SPIKE-S20-POS-SIZING-RESEARCH/`。
