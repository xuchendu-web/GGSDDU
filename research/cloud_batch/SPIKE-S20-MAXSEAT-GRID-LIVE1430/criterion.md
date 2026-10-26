# Criterion · SPIKE-S20-MAXSEAT-GRID-LIVE1430

- **唯一改动**：spike_ft 席位数 **maxN ∈ {3,4,5,6,7}**；填席仍 **SHARPE20**。
- **冻结**：B45 + spike_ft + E0 + TV25；Fri≥14:30 / 收盘；0.2%RT；L≤1。
- **基线**：max5 = B45+S20。
- **样本**：延窗 ≥2026-10-23（CLOUD-BATCH research_cache）。
- **探索尺子**：各档 Δret 须盖住 Δ|MDD|；报 2020–22 / 2023–26；强势段不踏空。
- **红线**：不写 strategy_exec / LIVE_OPS；不与 hyp4 填席改动混跑。
- **批次**：CLOUD-MAXSEAT-GRID。
