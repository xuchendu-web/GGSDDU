# Criterion · VOL-TARGET-10-15-B45

- **刀**：在 **B45+S20 face** 上设组合年化波动目标 **σ*=10%** 与 **15%**（缩放仓位 `L=min(1, σ*/σ̂)`，缩放后仍 clip `L≤1`）；对照 **无额外 VT 的 face（UNSCALED, L=1）** 与同批 **VT12**；半凯利叙事仅引用仓库既有产物 `research/cloud_batch/SPIKE-S20-VOL-TARGET-FKELLY/`（勿混口径横比）。
- **面层冻结**：breadth≥45% + spike_ft max5 + E0 + TV25（面层主钉不在本刀替换）+ SHARPE20；Fri≥14:30→收盘；**0.2% RT**；**研究池 only**。
- **σ̂**：未杠杆组合日收益 `max(20d, 60d)` 年化（与面层 TV 同构）。
- **基线**：`RESEARCH-S20-UNSCALED` = 同一周频持仓、不套 VT。
- **样本**：延窗 ≥2026-10-23（`research/cloud_batch/CLOUD-BATCH-2026-10-26/data/research_cache`）；数据源为 CLOUD-BATCH 缓存，**不用**进门/中金/Alpha派行情。
- **假设 H1**：VT10/VT15 相对 face 与 VT12 **无稳定** Calmar/Sortino 优势（Δret 盖不住代价或后段踏空）；若证伪则记正优档，**仍不换冠**。
- **探索尺子**：全样本 + 2020–22 / 2023–26 分段；报 Calmar、**Sortino**、已实现 vol；Δret 须盖住 Δ|MDD| 才称“盖住代价”。
- **红线**：不写 `strategy_exec` / `LIVE_OPS`；不换冠；**No LIVE**。
- **批次**：`CLOUD-VOL-TARGET-10-15-B45`。
