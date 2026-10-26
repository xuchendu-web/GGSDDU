# SPIKE-S20-VOL-TARGET-12

- 编号 / 日期 / 来源：SPIKE-S20-VOL-TARGET-12 / 2026-10-26 / CLOUD-BATCH 波动目标轴
- 批次 ID：CLOUD-VOL-TARGET-12
- 性质：同 B45+S20 face weekly 持仓，只改杠杆叠加（研究池；**No LIVE**）

## 准则原文
相对 B45+S20 **face weekly EQ5**，只改年化波动目标：
1. **UNSCALED** — L=1（无 TV 叠加）
2. **VT12** — σ*=12% ann，L=min(1, 0.12 / max(σ20,σ60))
3. **TV25** — σ*=25% ann，面层参照（不作为本刀基线）

填席仍 **SHARPE20**；E0 + max5 不变。σ̂ 与面层 TV 同构（未杠杆组合日收益 20d/60d）。窗 ≥2026-10-23。

## 红线
研究池 ≠ 实盘；不写 strategy_exec / LIVE_OPS；不换冠。

## 交付
四件套至 `research/cloud_batch/SPIKE-S20-VOL-TARGET-12/`。
