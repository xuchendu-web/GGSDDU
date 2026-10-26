# REPORT · SPIKE-S20-REB-FOURPACK-LIVE1430（再平衡四件套 · 延窗）

## 1. 准则原文

```
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
```

## 2. 实现要点

- **Face**：breadth≥45% + spike_ft **max5** + **SHARPE20** + E0 + **TV25**（σ*=0.25）；Fri≥14:30 / 收盘；**0.2%RT**；**L≤1**。
- **邻档**：TV22 / TV28 / TV33（σ* 仅缩放 L）；持仓与 B45 FACE 相同。
- **再平衡统计**：每个日历再平衡日 Fri→次 Fri 组合期收益（含空仓周、含成本）；命中率 / 均赢均亏 / payoff / expectancy。
- **延窗**：CLOUD-BATCH `research_cache`，日历至 **2026-10-23**（≥2026-10-23）。
- **隔离**：不写 strategy_exec / LIVE_OPS / champion / 实盘池。

## 近似与覆盖

- 延窗：research_cache week/day/face/14:30；≤2026-10-09 沿用 face；其后研究周线 MA20 宽度
- qfq_1430 = price_1430 × (day qfq 收 / sina daily 收)；sina 作 bfq 代理
- 冲击分类：周线收盘替换为 qfq_1430 后因果 classify（Fri≥14:30 信号）
- Sharpe 窗截至信号日严格前一交易日
- 成交：周五收盘填仓 + 0.2%RT；L=min(1, σ*/max(σ20,σ60))；**唯一改动 σ* 六档网格**
- 冻结 B45+spike_ft max5+S20+E0；持仓相同，TV 只缩放 L（L≤1）
- 只读 kit `data/cache_1430_snaps.json`；不写 strategy_exec / LIVE_OPS

| 覆盖 | 值 |
|---|---|
| 可投池（AUM≥2亿） | 324 |
| 日历周 | 349（2020-01-03→2026-10-23） |
| listed 行 14:30 非空率 | 100.0% |
| 持仓 vs B45 差异周（邻档） | 0/198 |

## 3. 主表（收益 + 再平衡四指标）

| book | σ* | TV | ret | maxDD | Calmar | reb 命中率 | reb expectancy | payoff | avg win | avg loss | reb_n | occ 命中率 | 空仓周 |
|---|---:|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| LIVE1430-B45-S20 **FACE** | 0.25 | TV25 | 158.3% | -15.9% | 0.94 | 30.2% | 0.3% | 1.78 | 2.5% | -1.4% | 348 | 53.0% | 150 |
| LIVE1430-TV22-S20 | 0.22 | TV22 | 148.1% | -14.9% | 0.96 | 30.5% | 0.3% | 1.78 | 2.3% | -1.3% | 348 | 53.5% | 150 |
| LIVE1430-TV28-S20 | 0.28 | TV28 | 162.9% | -16.9% | 0.90 | 30.2% | 0.3% | 1.74 | 2.7% | -1.5% | 348 | 53.0% | 150 |
| LIVE1430-TV33-S20 | 0.33 | TV33 | 168.1% | -19.1% | 0.82 | 30.2% | 0.3% | 1.71 | 2.8% | -1.7% | 348 | 53.0% | 150 |

### 命中率 / expectancy vs Calmar（对照表）

| TV | Calmar | reb 命中率 | reb expectancy | payoff | avg win | avg loss |
|---|---:|---:|---:|---:|---:|---:|
| TV25 | 0.94 | 30.2% | 0.3% | 1.78 | 2.5% | -1.4% |
| TV22 | 0.96 | 30.5% | 0.3% | 1.78 | 2.3% | -1.3% |
| TV28 | 0.90 | 30.2% | 0.3% | 1.74 | 2.7% | -1.5% |
| TV33 | 0.82 | 30.2% | 0.3% | 1.71 | 2.8% | -1.7% |

图：`reb_expectancy_vs_calmar.png`

### Δ vs B45 FACE（探索尺子）

| book | Δret vs B45 | Δ|MDD| | 盖住? | 2023–26 不差 |
|---|---:|---:|---|---|
| TV22-S20 | -10.2pp | -1.0pp | 否 | 是 |
| TV28-S20 | +4.6pp | +1.0pp | 是 | 是 |
| TV33-S20 | +9.8pp | +3.3pp | 是 | 是 |

## 4. 一句结论（研究记账，不换冠）

**再平衡四件套（研究记账，不换冠）**：B45 FACE（TV25）Calmar=0.94、再平衡命中率=30.2%、expectancy=0.3%/期。 Calmar 最高 **TV22-S20**（0.96）； 再平衡 expectancy 最高 **TV33**（0.3%/期）。 TV22/28/33 vs B45：Δret -10.2/+4.6/+9.8pp。

## 产物（四件套）

- `run.py` / `criterion.md` / `REPORT.md` / `summary.json`
- `table.csv` / `metrics.csv` / `reb_hit_expectancy_vs_calmar.csv` / `rebalance_periods.csv`
- `equity_curve.png` / `reb_expectancy_vs_calmar.png` / `nav_*.csv`

耗时约 6.3s。
