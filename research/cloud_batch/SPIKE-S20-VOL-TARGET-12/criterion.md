# Criterion · SPIKE-S20-VOL-TARGET-12

- **唯一改动**：在冻结的 **B45+S20 face weekly**（EQ5 max5 + SHARPE20 + E0）上叠加杠杆：**UNSCALED (L=1)** vs **VT12 (σ*=12% ann)**；**TV25 (σ*=25%)** 仅作面层参照。
- **冻结**：B45 + spike_ft + E0 + SHARPE20 + max5；Fri≥14:30 / 收盘；0.2%RT；L≤1；**研究池**。
- **σ̂**：未杠杆组合日收益 `max(20d, 60d)` 年化，与面层 TV 同构；L=min(1, σ*/σ̂)。
- **基线**：RESEARCH-S20-UNSCALED = 同一周频持仓、不套 TV。
- **样本**：延窗 ≥2026-10-23（CLOUD-BATCH research_cache）。
- **探索尺子**：Δret 须盖住 Δ|MDD|；报 2020–22 / 2023–26；强势段不踏空；报已实现 vol。
- **红线**：不写 strategy_exec / LIVE_OPS；不换冠；**No LIVE**。
- **批次**：CLOUD-VOL-TARGET-12。
