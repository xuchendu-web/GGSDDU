# Criterion · SPIKE-S20-ENTRY-PERSIST-K-LIVE1430

- **唯一改动**：新进填席前须 **连续 K 周** 处于 S20 **Top5 席位（top-seat）**；K∈{1,2,3}。
- **冻结**：B45 + spike_ft **max5** + E0 + TV25 + SHARPE20；Fri≥14:30 / 收盘；0.2%RT；L≤1。
- **基线**：K=1 = B45+S20（无额外等待）。
- **样本**：延窗 ≥2026-10-23（CLOUD-BATCH research_cache · 冻结研究池）。
- **探索尺子**：邻档 Δret 须盖住 Δ|MDD|；2023–26 累计 ≥ 基线。
- **红线**：不写 strategy_exec / LIVE_OPS / champion_mast / 实盘池。
- **批次**：CLOUD-ENTRY-PERSIST-K；**不升格**。
