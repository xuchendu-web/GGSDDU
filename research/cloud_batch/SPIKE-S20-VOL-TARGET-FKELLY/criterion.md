# Criterion · SPIKE-S20-VOL-TARGET-FKELLY

- **唯一改动**：冻结 **B45+S20 face weekly**（EQ5 max5 + SHARPE20 + E0）上叠加：**UNSCALED**、**VT12 (σ*=12%)**、**VTFK50/25**（σ*=min(15%, f×SR×σ̂)）。
- **FK**：f∈{0.5,0.25}；SR=trailing ann Sharpe（60d 优先）；σ̂=max(20d,60d) 未杠杆日收益年化。
- **冻结**：B45 + spike_ft + E0 + SHARPE20 + max5；Fri≥14:30 / 收盘；0.2%RT；L≤1；**研究池**。
- **对照**：PR#47 固定 VT12 + ungated FACE（L=1）。
- **指标**：Sortino / Sharpe / Calmar / maxDD / turnover（+ ret/vol 分段）。
- **红线**：不写 strategy_exec / LIVE_OPS；不换冠；**No LIVE**。
- **批次**：CLOUD-VOL-TARGET-FKELLY。
