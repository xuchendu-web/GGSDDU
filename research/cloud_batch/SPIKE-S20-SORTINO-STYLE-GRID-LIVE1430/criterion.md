# Criterion · SPIKE-S20-SORTINO-STYLE-GRID-LIVE1430

# SPIKE-S20-SORTINO-STYLE-GRID-LIVE1430

- 编号 / 日期 / 来源：SPIKE-S20-SORTINO-STYLE-GRID-LIVE1430 / 2026-10-26 / Michael 语音·烧 Cursor（悟空）
- 批次 ID：CLOUD-SORTINO-STYLE-GRID
- 性质：**研究面层 risk-adjust 补表**（复用既有 nav/trades，不重跑引擎）

## 准则原文
在 **研究池 face（B45+S20）** 与关键邻档 **TV22/28/33**、**B40/B50**（若产物已存在）上，对同窗 LIVE1430 日净值补算 **Sortino（下行波动、rf=0）**，与既有 **Sharpe / Calmar** 同表对照；**不重跑** SPIKE 填席引擎。

## 改动点（唯一）
无引擎改动；仅 **post-hoc 指标**（日收益序列 → Sharpe / Sortino / Calmar + 2020–22 / 2023–26 段）。

## 假设
邻档相对 face 的 **Sortino 排序**与 Calmar 主叙事一致；TV 抬高杠杆时 Sortino 不系统性劣于 Sharpe 排序。

## 证伪
face 在 Sortino 上被弱邻档全面压制且与 Calmar 叙事矛盾 → 旁注「下行风险尺不稳健」（不换冠）。

## 邻档说明
- face：`LIVE1430-B45-S20-max5`（B45+S20 研究面层）
- breadth 邻档：B40、B50（BTHETA 网格产物）
- TV 邻档：TV22、TV28、TV33（TV 网格产物）
- 不插值、不升格；勿碰 LIVE / champion / strategy_exec

## 主表
`style_grid_dump.csv`：各行一书，列含 ret / maxDD / CAGR / **Sharpe / Sortino / Calmar** + 分段；产物 `.../SPIKE-S20-SORTINO-STYLE-GRID-LIVE1430/`

## 共用冻结
- 成交口径：**Fri ≥14:30 / 当日收盘**；**0.2%RT**；**L≤1**（体现在源 nav 中）
- 研究池 ≠ 实盘池；**不换冠**；不碰 strategy_exec / LIVE_OPS / 冠军主钉
- Sortino：日收益、rf=0、下行偏差 = sqrt(mean(min(r,0)²))，年化 ×√252

## 交付
四件套：`run.py` / `criterion.md` / `REPORT.md` / `equity_curve.png`

