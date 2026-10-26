# Criterion · RESEARCH-TSMOM-12M-LONGFLAT-WEEKLY

- 编号 / 日期：RESEARCH-TSMOM-12M-LONGFLAT-WEEKLY / 2026-10-26
- 性质：**研究专用** Moskowitz 时间序列动量（long/flat），无 LIVE/champion

## 准则原文
研究 ETF 池上实现 TSMOM：各标的 **12 个月**（主刀）总收益 > 0 则做多，否则空仓（现金）。**周频**再平衡；risk-on 内 **等权**，主刀为 **12m 收益 Top5**；旁注 **全部正动量等权**。邻档回看 **6m / 9m**；旁注表 **波动率缩放至 12% ann**。

## 对照
**B45+S20 研究面**（LIVE1430 同窗指标，非重跑栈）：`data/b45_face_reference.csv`

## 证伪（探索尺子）
相对 B45 face：**Δret 须盖住 Δ|MDD|**；**2023–26 不得明显踏空**（< face×0.85）。不满足 → **FALSIFIED**。

## 冻结
- 成本 **0.2% RT**；**L≤1**
- 周历对齐 `CLOUD-BATCH` research week grid
- 不编辑 `strategy_exec` / `LIVE_OPS` / champion

## 交付（四件套）
`criterion.md`、`HYPOTHESIS.md`、`README.md`、`REPORT.md` + `scorecard.csv` / `summary.json`
