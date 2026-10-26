# SPIKE-S20-REB-FOURPACK-LIVE1430

- 编号 / 日期 / 来源：SPIKE-S20-REB-FOURPACK-LIVE1430 / 2026-10-26 / CloudAgent 研究
- 批次 ID：CLOUD-REB-FOURPACK
- 性质：再平衡期 **命中率 / 均赢均亏 / payoff / expectancy** 与 Calmar 对照（延窗）

## 准则原文

在 **B45 FACE**（breadth≥45% + spike_ft max5 + SHARPE20 + E0 + **TV25**）与 TV **邻档** TV22 / TV28 / TV33 上，按每个日历再平衡日（Fri→次 Fri）统计组合期收益四指标，并与全样本 Calmar 并列；持仓冻结相同，仅 σ* 缩放 L。

## 改动点（唯一）

新增 **per-rebalance** 统计口径（非仅持仓周 occ）；四本合表 `reb_hit_expectancy_vs_calmar.csv`。

## 假设

更高 Calmar 的 TV 档在再平衡 expectancy 上应同向更优；若 Calmar 升而 reb expectancy 降，说明收益来自少数大周而非再平衡「胜率结构」。

## 证伪

四档 reb expectancy 与 Calmar 排序完全背离且无合理解释 → 本表只作描述性记账。

## 红线

不换冠；不碰 strategy_exec / LIVE_OPS / champion；研究池 ≠ 实盘池。

## 主表

四本：B45 FACE + TV22/28/33；产物 `/workspace/strategy-weekly/spike_mom_rank/SPIKE-S20-REB-FOURPACK-LIVE1430/`

## 共用冻结

- 成交：Fri ≥14:30 / 当日收盘；0.2%RT；**L≤1**
- 面层：breadth≥45% + spike_ft max5 + E0 + SHARPE20（TV 为唯一 σ* 差）
- 探索尺子：Δret 须盖住 Δ|MDD|；报 2020–22 / 2023–26
- **执行**：CloudAgent + CLOUD-BATCH `research_cache`（≥2026-10-23）

## 四件套

`REPORT.md` / `criterion.md` / `summary.json` / `table.csv`（+ `reb_hit_expectancy_vs_calmar.csv`）

