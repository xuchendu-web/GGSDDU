# REPORT · SPIKE-S20-SORTINO-STYLE-GRID-LIVE1430（Sortino 邻域对照）

## 1. 准则原文

```
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
```

## 2. 实现要点

- **不重跑引擎**：直接读取 BTHETA / TV-GRID 已冻结 **nav**（含 Fri≥14:30 face、0.2%RT、L≤1）。
- **Sharpe / Sortino**：日收益；年化 √252；Sortino 下行偏差 sqrt(mean(min(r,0)²))，**rf=0**。
- **Calmar**：CAGR/|maxDD|（与 BTHETA 主表同口径）。
- **红线**：仅 `research/cloud_batch/...`；不换冠；不写 strategy_exec / LIVE。

## 3. 主表 · style grid（Sharpe / Sortino / Calmar）

| axis | label | book | ret | maxDD | CAGR | Sharpe | Sortino | Calmar | 2020–22 S/Sor/Cal | 2023–26 S/Sor/Cal |
|---|---|---|---:|---:|---:|---:|---:|---:|---|---|
| face | B45+S20 **face** | LIVE1430-B45-S20-max5 | 131.9% | -18.8% | 13.2% | 0.82 | 1.24 | 0.70 | 0.43/0.60/0.38 | 1.14/1.86/1.39 |
| breadth | B40 | LIVE1430-B40-S20-max5 | 67.9% | -29.2% | 7.9% | 0.53 | 0.75 | 0.27 | 0.16/0.22/0.05 | 0.83/1.25/0.98 |
| breadth | B50 | LIVE1430-B50-S20-max5 | 149.4% | -15.5% | 14.4% | 0.91 | 1.40 | 0.93 | 0.42/0.58/0.36 | 1.31/2.22/1.59 |
| tv | TV22 | LIVE1430-TV22-S20 | 148.1% | -14.9% | 14.3% | 0.94 | 1.44 | 0.96 | 0.56/0.78/0.53 | 1.25/2.09/1.54 |
| tv | TV28 | LIVE1430-TV28-S20 | 162.9% | -16.9% | 15.3% | 0.89 | 1.34 | 0.90 | 0.59/0.84/0.59 | 1.13/1.83/1.30 |
| tv | TV33 | LIVE1430-TV33-S20 | 168.1% | -19.1% | 15.6% | 0.86 | 1.29 | 0.82 | 0.61/0.86/0.55 | 1.07/1.71/1.15 |

**Calmar 最高**：LIVE1430-TV22-S20（0.96）。
**Sortino 最高**：LIVE1430-TV22-S20（1.44）。
**Face（B45+S20）**：Sharpe 0.82 · Sortino 1.24 · Calmar 0.70。

### 相对 face 旁注

- B50 同时在 Calmar/Sortino 上高于 face（ΔCalmar=+0.23 ΔSortino=+0.16）
- TV22 同时在 Calmar/Sortino 上高于 face（ΔCalmar=+0.26 ΔSortino=+0.20）
- TV28 同时在 Calmar/Sortino 上高于 face（ΔCalmar=+0.20 ΔSortino=+0.10）

## 4. 产物

- `style_grid_dump.csv` / `metrics.csv` / `summary.json`
- `run.py` / `criterion.md` / `REPORT.md` / `equity_curve.png`
