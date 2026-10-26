# COMPRESSION-BREAKOUT-LIVE1430

- 编号 / 日期 / 来源：COMPRESSION-BREAKOUT-LIVE1430 / 2026-10-26 / Cloud Agent（研究池）
- 批次 ID：CLOUD-COMPRESSION-BREAKOUT
- 性质：**CSMOM/spike 填席压缩突破门控**（研究池；非 LIVE / 非 champion / 非 strategy_exec）

## 准则原文

冻结面层 **SPIKE-S20 B45**（breadth≥45%，spike max5，**TV25**，**SHARPE20**）；**Fri≥14:30** 信号 / 周五收盘成交；**0.2%RT**；**L≤1**。

**唯一改动**：对 **spike / CSMOM 风险席** 的新开仓（填席新增标的），要求同时满足 **N 周区间压缩** 且 **向上突破**（Kaufman 式窄幅后突破）：

1. **压缩（N 周）**：信号周之前已完成的 N 个交易周，每周区间 `rng_w = (H-L)/C`；令 `cum_rng = sum(rng_w)`。压缩当且仅当 `cum_rng` ≤ 该标的过去 52 周（滚动）`cum_rng` 的 **40 分位**（同 N 窗宽）。
2. **突破**：信号日 `px_1430`（无 14:30 时用周五收盘前复权代理）≥ 前 N 个已完成周 **最高价** `max(H_{t-N..t-1})`。
3. **填席**：按 FACE 的 sharpe20 排序取 top-max5；候选若未过门控则 **跳过该席**（不替换为下一名），已持仓非新增不重算门控。

## 邻档（四件套）

| book | N（压缩窗，周） |
|------|----------------|
| **FACE** | 无门控（对照） |
| CB-N4 | 4 |
| CB-N6 | 6 |
| CB-N8 | 8 |

## 主表维度

- 组合账：ret / maxDD / CAGR / Calmar / 分段（2020–22、2023–26）/ avgL / avgTO
- **入场质量**（相对 FACE 的新增开仓子样本）：**hit-rate**（1 周后收益>0 占比）、**win-size**（盈利开仓平均收益 / |亏损开仓平均收益|）、开仓次数

## 红线

不写 strategy_exec / LIVE_OPS / champion；不触实盘池；研究池数据仅读 `RESEARCH_CACHE` 或本目录 `data/` 构建缓存。

## 证伪（探索尺子，相对 FACE）

若某邻档 **Calmar 更差** 且 **Δret 盖不住 Δ|MDD|**，或后段 2023–26 ret < FACE×0.9，且 **hit-rate 与 win-size 未同时改善**，记探索未通过。
