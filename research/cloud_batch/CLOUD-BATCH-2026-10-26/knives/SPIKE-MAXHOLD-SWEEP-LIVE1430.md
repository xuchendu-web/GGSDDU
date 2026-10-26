# SPIKE-MAXHOLD-SWEEP-LIVE1430

- 编号 / 日期 / 来源：SPIKE-MAXHOLD-SWEEP-LIVE1430 / 2026-10-26 / CloudAgent
- 批次 ID：CLOUD-SPIKE-MAXHOLD-SWEEP
- 性质：面层 **B45+S20+TV25 max5** 上，单票连续持有上限扫参（研究池）

## 准则原文
冻结 face：breadth≥45% + spike_ft max5 + SHARPE20 填席 + E0 + TV25 L≤1 + 0.2%RT + Fri 14:30 信号 / 收盘成交。
**唯一改动**：连续持有满 W 周强制清仓，W ∈ {4, 6, 8}；对照无上限基准。

## 宇宙
`etf-correlation/data/research_pool_v2.csv` ∩ AUM≥2（**研究池 only**，非实盘池）。

## 证伪
∃W∈{4,6,8}：全样本 ret 与 2023–26 ret 均盖住基准 **且** Calmar ≥ 基准。

## 红线
不换冠；不改 strategy_exec / LIVE_OPS；不合层。

## 交付
四件套 → `research/cloud_batch/SPIKE-MAXHOLD-SWEEP-LIVE1430/` 与 `etf-multifreq/` 镜像。

## 跑批
`python3 research/cloud_batch/SPIKE-MAXHOLD-SWEEP-LIVE1430/engine/run_maxhold_sweep.py`
