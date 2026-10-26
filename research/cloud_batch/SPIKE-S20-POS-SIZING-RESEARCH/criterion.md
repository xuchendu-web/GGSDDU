# Criterion · SPIKE-S20-POS-SIZING-RESEARCH

- **唯一改动**：持仓权重 **EQ5 / INV20W / CAP30**；填席仍 **SHARPE20**；**max5** 不变。
- **冻结**：B45 + spike_ft + E0 + TV25；Fri≥14:30 / 收盘；0.2%RT；L≤1；**研究池**。
- **基线**：RESEARCH-S20-EQ5 = B45+S20 等权。
- **INV20W**：20 周周线已实现波动率倒数加权（全投资）。
- **CAP30**：等权后单票上限 30%，超出部分留现金。
- **样本**：延窗 ≥2026-10-23（CLOUD-BATCH research_cache）。
- **探索尺子**：Δret 须盖住 Δ|MDD|；报 2020–22 / 2023–26；强势段不踏空。
- **红线**：不写 strategy_exec / LIVE_OPS；不换冠。
- **批次**：CLOUD-POS-SIZING。
