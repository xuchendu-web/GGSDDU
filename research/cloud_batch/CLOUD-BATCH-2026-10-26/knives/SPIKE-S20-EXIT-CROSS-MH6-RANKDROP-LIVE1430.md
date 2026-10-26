# SPIKE-S20-EXIT-CROSS-MH6-RANKDROP-LIVE1430

- 编号 / 日期 / 来源：SPIKE-S20-EXIT-CROSS-MH6-RANKDROP-LIVE1430 / 2026-10-26 / CloudAgent
- 批次 ID：CLOUD-SPIKE-EXIT-CROSS
- 性质：面层 **B45+S20+TV25 max5** 上 MH6 × rank-drop 交叉（研究池）

## 准则原文
冻结 face：breadth≥45% + spike_ft max5 + SHARPE20 填席 + E0 + TV25 + Fri 14:30。
**唯一改动**：MH6（邻域 4/8 周）+ rank-drop（Sharpe 排名 > max5+buffer，主 buffer=2）。

## 证伪
主组合 MH6×RD 相对 face：分段 Calmar 失败且 Δret 未盖住 Δ|MDD|；或强市周 Calmar 折价。

## 红线
不换冠；不改 strategy_exec / LIVE_OPS。

## 交付
四件套 → `research/SPIKE-S20-EXIT-CROSS-MH6-RANKDROP-LIVE1430/`

## 跑批
`python3 research/SPIKE-S20-EXIT-CROSS-MH6-RANKDROP-LIVE1430/run.py`
