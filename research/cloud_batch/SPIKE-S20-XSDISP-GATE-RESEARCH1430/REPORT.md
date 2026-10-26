# REPORT · SPIKE-S20-XSDISP-GATE-RESEARCH1430

## 1. 准则原文

```
# SPIKE-S20-XSDISP-GATE-RESEARCH1430

- 编号 / 日期：SPIKE-S20-XSDISP-GATE-RESEARCH1430 / 2026-10-26
- 性质：**探索**（横截面离散度开仓门；研究池；不换冠；无 LIVE/实盘）

## 准则原文

在冻结基线 **B45+S20**（breadth≥45% + spike_ft max5 + E0 + TV25 + SHARPE20 + Fri≥14:30/收盘 + 0.2%RT + L≤1）上，**唯一改动**为横截面离散度开仓门：

- 每周计算研究池 **1 周横截面收益 σ**（同窗可投 ETF 的周收益截面标准差，ddof=1）
- **仅当** 当周 σ **≥** 其过去 **52 周** 历史分布的 **P40 / P50 / P60** 分位时，允许**新开仓**（结构踢出 / breadth_off 等强制退出不变）
- 历史不足 52 周：门关闭（不开新仓）

## 四账（four-pack）

| book | 门 |
|---|---|
| RESEARCH1430-B45-S20 | 无（对照基线） |
| RESEARCH1430-B45-S20-XSDISP-P40 | σ ≥ P40(52w) |
| RESEARCH1430-B45-S20-XSDISP-P50 | σ ≥ P50(52w) |
| RESEARCH1430-B45-S20-XSDISP-P60 | σ ≥ P60(52w) |

样本：**2020-01-03 → 最新完整周**；主表必报 **2023–26** 分段。

## 假设

高离散度周开仓可过滤「横截面过于拥挤/同质」的弱环境，相对基线 **Δret 盖住 Δ|MDD|**，且 **2023–26 不塌**。

## 证伪

任一门控腿相对同窗 B45：Δret 未盖住 Δ|MDD|，或 2023–26 ret 相对基线踏空 ≥3pp / 翻负。

## 交付

四件套：`REPORT.md` + `summary.json` + `table.csv` + `equity.csv`（及 nav/metrics 旁件）。
```

## 2. 实现要点

- **唯一改动**：在 B45+S20 上叠加横截面 1w-σ 开仓门（P40/P50/P60 × 52w 历史）；强制退出规则不变。
- **冻结**：Fri≥14:30/收盘；0.2%RT；L≤1；spike_ft max5 + SHARPE20 + E0 + TV25；**研究池**。
- **引擎**：`CLOUD-BATCH-2026-10-26` kit；复用 extend 窗 14:30 classify 缓存。
- **红线**：不换冠；不写 strategy_exec / LIVE_OPS / 实盘。

## 近似与覆盖

- 延窗研究缓存：week/day 合并 recon week_2026-10-23 / day_2026-10-23；缺日线用 sina 收益链拼接（研究目录）
- 14:30 新周（09-30/10-09/10-16/10-23）pytdx idx209 拉入 research_cache；旧周复用 fri_1430_through_20260925
- B45/B50 breadth/risk_on：face holdings_ro2_extended 列 b / risk_on（B50: b≥0.50）
- HYST-M3：滞回 M=3；TV33：σ*=0.33 同 B45 持仓；CASH-511010：空仓周 TV25 持 511010
- qfq_1430 = price_1430 × (day/tema qfq 收 / sina 收)；Sharpe 窗截至信号日前一交易日
- 成交/净值：信号周末交易日收盘填仓 + TV25 + 0.2%RT；L≤1

| 覆盖 | 值 |
|---|---|
| 可投池（AUM≥2亿） | 324 |
| 日历周 | 349（2020-01-03→2026-10-23） |
| xs_sigma 有效周 | 348 |
| σ门开启周（P40/P50/P60） | 181/157/128 |
| B45 risk_on 周占比 | 58.3% |

## 3. 主表（four-pack）

| book | ret | maxDD | CAGR | Calmar | 2020–22 ret/DD/C | 2023–26 ret/DD/C | avgL | cash周% |
|---|---:|---:|---:|---:|---|---|---:|---:|
| RESEARCH1430-B45-S20 | 131.6% | -18.8% | 13.1% | 0.70 | 18.9%/-16.0%/0.37 | 94.8%/-13.8%/1.39 | 0.84 | 43.1% |
| RESEARCH1430-B45-S20-XSDISP-P40 | 45.6% | -18.7% | 5.7% | 0.30 | 1.0%/-14.2%/0.02 | 44.2%/-13.6%/0.75 | 0.79 | 61.2% |
| RESEARCH1430-B45-S20-XSDISP-P50 | 52.5% | -18.7% | 6.4% | 0.34 | 1.0%/-14.2%/0.02 | 51.0%/-14.2%/0.81 | 0.77 | 63.8% |
| RESEARCH1430-B45-S20-XSDISP-P60 | 29.0% | -22.0% | 3.8% | 0.17 | -6.9%/-14.2%/-0.17 | 38.6%/-13.3%/0.67 | 0.71 | 66.1% |

### Δ · 门控腿 vs 同窗基线

- RESEARCH1430-B45-S20-XSDISP-P40: Δret vs B45 -86.0pp；Δ|MDD| -0.1pp；未盖住
- RESEARCH1430-B45-S20-XSDISP-P50: Δret vs B45 -79.1pp；Δ|MDD| -0.1pp；未盖住
- RESEARCH1430-B45-S20-XSDISP-P60: Δret vs B45 -102.6pp；Δ|MDD| +3.2pp；未盖住

旁注：extend 同窗 LIVE1430-B45-S20 ret≈131.6%；本跑基线对齐=是。

## 4. 一句证伪或通过

**横截面σ门证伪（不换冠）**：RESEARCH1430-B45-S20-XSDISP-P40, RESEARCH1430-B45-S20-XSDISP-P50, RESEARCH1430-B45-S20-XSDISP-P60 相对同窗 RESEARCH1430-B45-S20 未满足探索尺子（Δret 盖住 Δ|MDD| 且 2023–26 不塌）；基线 ret=131.6% MDD=-18.8%。

耗时约 11.6s。
