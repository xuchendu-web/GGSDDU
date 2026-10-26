# Criterion · SPIKE-S20-SIZE-EQ-HYST-M2M3-LIVE1430

- **唯一改动**：**等权**持仓冻结；**HYST-M2 / HYST-M3** 滞回（rank>5+M 踢；空席只从 Top5 填）。
- **冻结**：B45 + spike_ft max5 + SHARPE20 + E0 + TV25；Fri≥14:30 / 收盘；0.2%RT；L≤1；**研究池**。
- **基线**：LIVE1430-EQ-S20 = Face 等权、无滞回。
- **归因**：LIVE1430-INV-HYST-M3-S20（反波动×M3）**不晋升**。
- **样本**：延窗 ≥2026-10-23（CLOUD-BATCH research_cache）。
- **证伪**：HYST 交叉须 vs Face **Calmar** 更优，且 Δret 盖住 Δ|MDD|；否则 segment skip / 邻居翻转。
- **红线**：不写 strategy_exec / LIVE_OPS / champion；不换冠。
- **批次**：COMPOSER-S20-EQ-HYST。
