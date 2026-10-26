## 0. 假设与证伪（开跑前写死）
- **假设**：无 max-hold 的 B45+S20+TV25 max5 基准在后段更优；强加持有上限 4/6/8 周主要降换手、略损收益，Calmar 不系统性优于基准。
- **证伪**：∃MH∈{4,6,8} 全样本 ret 与 2023–26 ret 均盖住基准 **且** Calmar ≥ 基准。
- **红线**：研究池 only；不改 strategy_exec/LIVE/冠军；不合层。

## 1. 准则
- **面层冻结**：breadth≥45%（face risk_on）+ spike_ft max5 + SHARPE20 填席 + E0 + TV25 L≤1 + 0.2%RT + Fri 14:30 信号 / 收盘成交。
- **唯一改动**：单票连续持有满 **W** 周强制清仓（W∈{4,6,8}）；基准 **无上限**。
- **宇宙**：`research_pool_v2` ∩ AUM≥2（n=324）；数据 kit `/workspace/research/cloud_batch/CLOUD-BATCH-2026-10-26`。

## 2. 主表
| book | max_hold周 | ret | maxDD | Calmar | 2020–22 | 2023–26 | avgL |
|---|---:|---:|---:|---:|---|---|---:|
| LIVE1430-B45-S20 | — | 158.3% | -15.9% | 0.96 | 29.3%/-14.9%/0.60 | 99.8%/-14.3%/1.43 | 0.83 |
| LIVE1430-MH4 | 4 | 143.3% | -16.9% | 0.83 | 25.4%/-16.9%/0.46 | 94.0%/-15.6%/1.25 | 0.82 |
| LIVE1430-MH6 | 6 | 160.1% | -17.8% | 0.86 | 23.2%/-15.9%/0.45 | 111.2%/-13.2%/1.69 | 0.82 |
| LIVE1430-MH8 | 8 | 137.5% | -16.0% | 0.86 | 18.7%/-14.9%/0.40 | 100.0%/-14.3%/1.43 | 0.83 |

### 网格 vs 基准
| book | cap | ret | maxDD | Calmar | 2023–26 | #max_hold退出 | Δ vs 基准 |
|---|---:|---:|---:|---:|---:|---:|---|
| LIVE1430-MH4 | cap=4 | 143.3% | -16.9% | 0.83 | 94.0% | 82 | Δret -15.0pp ΔMDD -1.1pp ΔCal -0.12 |
| LIVE1430-MH6 | cap=6 | 160.1% | -17.8% | 0.86 | 111.2% | 38 | Δret +1.9pp ΔMDD -1.9pp ΔCal -0.10 |
| LIVE1430-MH8 | cap=8 | 137.5% | -16.0% | 0.86 | 100.0% | 20 | Δret -20.8pp ΔMDD -0.1pp ΔCal -0.09 |

## 3. 覆盖
- breadth/risk_on 沿用 face holdings_ro2_from2016（收盘 MA20 宽度），未用 14:30 价重算 breadth
- qfq_1430 = price_1430 × (day2017/tema qfq 收 / sina daily 收)；sina 作 bfq 代理（缺 sina/qfq 无法映射则当日不可选）
- 冲击分类：周线收盘替换为 qfq_1430 后因果 classify（14:30 信号，非 11:30、非周五收盘探索）
- Sharpe 窗截至信号日严格前一交易日（避免周五收盘前视）
- 成交/净值：周五（信号周末交易日）收盘填仓 + TV25 + 0.2%RT（ops 目标盘后成交；收盘填仓对齐 LIVE 主表约定）
- 14:30 价来自 pytdx get_history_minute_time_data idx209；非收盘伪装

| 项 | 值 |
|---|---|
| 研究池代码数 | 324 |
| 日历周 | 345 |
| 14:30 映射成功 | 44573 |

## 4. 结论
**未证伪（探索记账）**：无 MH 档同时盖住基准全样本+后段且 Calmar≥基准。

产物：`/workspace/research/cloud_batch/SPIKE-MAXHOLD-SWEEP-LIVE1430/`（四件套 metrics/nav/REPORT/ATTRIBUTION）；镜像 `/workspace/etf-multifreq/SPIKE-MAXHOLD-SWEEP-LIVE1430/`。
耗时 8.3s。
