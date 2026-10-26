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
