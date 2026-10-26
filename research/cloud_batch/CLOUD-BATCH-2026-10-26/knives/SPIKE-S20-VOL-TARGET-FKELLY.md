# SPIKE-S20-VOL-TARGET-FKELLY

- 编号 / 日期 / 来源：SPIKE-S20-VOL-TARGET-FKELLY / 2026-10-26 / CLOUD-BATCH 波动目标轴
- 批次 ID：CLOUD-VOL-TARGET-FKELLY
- 性质：同 B45+S20 face weekly 持仓，只改杠杆叠加（研究池；**No LIVE**）

## 准则原文
相对 B45+S20 **face weekly EQ5**，叠加：
1. **UNSCALED** — L=1（ungated FACE）
2. **VT12** — σ*=12% ann（PR#47 固定对照）
3. **VTFK50** — σ*=min(15%, 0.5×SR×σ̂)
4. **VTFK25** — σ*=min(15%, 0.25×SR×σ̂)

σ̂=max(20d,60d) 未杠杆组合日收益年化；SR=同窗 trailing Sharpe；L=min(1, σ*/σ̂)。填席仍 **SHARPE20**；E0 + max5 不变。

## 红线
研究池 ≠ 实盘；不写 strategy_exec / LIVE_OPS；不换冠。

## 交付
四件套至 `research/cloud_batch/SPIKE-S20-VOL-TARGET-FKELLY/`。
