# REPORT · SPIKE-S20-UNIVERSE-SLICE-AB

**性质**：研究批；**非 LIVE**；不换冠；不写 strategy_exec / LIVE_OPS。

## 问题

同一 **B45+S20** 面层（breadth risk_on 来自 face；spike_ft max5；SHARPE20；Fri≥14:30/收盘；0.2% RT；L≤1；TV25），仅更换**候选池切片**（单簿不混类）：

| 切片 | 分组来源 | 规则 |
|---|---|---|
| **A** | `etf-correlation/data/research_pool_v2.csv` | `l0=中国权益` 且 `family` 以 `宽基` 开头 |
| **B** | 同上 | `l0=中国权益` 且 `family` 以 `行业·` 或 `主题·` 开头 |

窗：2020-01-03 → 2026-10-23；可投池全量 324（AUM≥2亿）。

## 主表（ret / MDD / turnover）

| book | n_pool | ret | maxDD | Calmar | avgTO | cash周% | trades |
|---|---:|---:|---:|---:|---:|---:|---:|
| RES-B45-S20-A-BROAD | 38 | 3.7% | -35.0% | 0.02 | 0.164 | 60.1% | 136 |
| RES-B45-S20-B-SECTOR-THEME | 185 | 162.1% | -20.3% | 0.75 | 0.226 | 44.0% | 246 |
| REF full pool B45 | 324 | 131.6% | -18.8% | 0.70 | — | 43.1% | — |

Δ(B−A) ret +158.4pp；Δ|MDD| -14.7pp；ΔavgTO +0.062。

## 分散化旁注

- **A 宽基**：RES-B45-S20-A-BROAD: 32 distinct ETFs ever held; avg concurrent slots ~1.47; top families by slot-weeks: 宽基·交易所其他(179), 宽基·创业板(144), 宽基·市值阶梯(113)
- **B 行业/主题**：RES-B45-S20-B-SECTOR-THEME: 114 distinct ETFs ever held; avg concurrent slots ~2.51; top families by slot-weeks: 行业·TMT其他(231), 行业·消费(138), 行业·新能源(95)

宽基切片候选更少（38 只），信号周常更「空」→ cash 周占比通常更高；行业/主题池更厚，换手与品种分散度更高，但子行业集中度（半导体、医药等）仍可能抬升同向风险。

## 红线

研究池分组仅用于本对比；**不得**将 A/B 标的混在同一账面。

耗时约 5.3s。
