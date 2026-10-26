## 0. 假设与证伪（开跑前写死）
- **假设**：单独 MH6（PR#41）未系统性优于 face；rank-drop 与 MH6 **交叉**才可能改善 Calmar（ret 补偿更深 MDD）。
- **证伪（主组合 LIVE1430-MH6-RD）**：相对 face，任一分段（全样本 / 2020–22 / 2023–26）Calmar 更差 **且** Δret（pp）< Δ|MDD|（pp）；或强市周（risk_on 且 HS300 20w>8%）Calmar < face×0.95。
- **红线**：研究池 only；不改 strategy_exec/LIVE_OPS/冠军；PR#41 结论不变。

## 1. 准则
- **面层冻结**：breadth≥45% + spike_ft max5 + SHARPE20 填席 + E0 + TV25 L≤1 + 0.2%RT + Fri 14:30 / 收盘成交。
- **唯一改动**：MH6（邻域 MH4/MH8）× rank-drop（邻域 buffer 1/3）；rank-drop：当日 spike_ft 且 SHARPE20 可算集合内按 Sharpe 降序排名；持仓若不在可填席集合或排名 > max5+buffer（主 buffer=2，即 rank>7 强平）；邻域 RD-only：buffer∈{1,3}。
- **宇宙**：`research_pool_v2` ∩ AUM≥2（n=324）；kit `/workspace/research/cloud_batch/CLOUD-BATCH-2026-10-26`。

## 2. 主表
| book | MH周 | RD | buffer | ret | maxDD | Calmar | 2020–22 | 2023–26 | #MH | #RD |
|---|---|---|---|---:|---:|---:|---|---|---:|---:|
| LIVE1430-B45-S20 | — | N | — | 158.3% | -15.9% | 0.96 | 29.3%/-14.9%/0.60 | 99.8%/-14.3%/1.43 | 0 | 0 |
| LIVE1430-MH6 | 6 | N | — | 160.1% | -17.8% | 0.86 | 23.2%/-15.9%/0.45 | 111.2%/-13.2%/1.69 | 38 | 0 |
| LIVE1430-RD | — | Y | 2 | 223.4% | -18.2% | 1.05 | 17.4%/-18.2%/0.30 | 175.4%/-10.3%/3.03 | 0 | 446 |
| LIVE1430-MH6-RD | 6 | Y | 2 | 223.4% | -18.2% | 1.05 | 17.4%/-18.2%/0.30 | 175.4%/-10.3%/3.03 | 0 | 446 |
| LIVE1430-MH4 | 4 | N | — | 143.3% | -16.9% | 0.83 | 25.4%/-16.9%/0.46 | 94.0%/-15.6%/1.25 | 82 | 0 |
| LIVE1430-MH8 | 8 | N | — | 137.5% | -16.0% | 0.86 | 18.7%/-14.9%/0.40 | 100.0%/-14.3%/1.43 | 20 | 0 |
| LIVE1430-RD-B1 | — | Y | 1 | 203.9% | -18.2% | 0.99 | 14.1%/-18.2%/0.25 | 166.3%/-10.3%/2.91 | 0 | 473 |
| LIVE1430-RD-B3 | — | Y | 3 | 228.9% | -18.1% | 1.07 | 16.7%/-18.1%/0.29 | 181.8%/-10.3%/3.10 | 0 | 428 |

### 2×2（MH6 × rank-drop，buffer=2)
|  | rank-drop **off** | rank-drop **on** |
|---|---|---|
| **MH6 off** | Cal 0.96 / ret 158.3% | Cal 1.05 / ret 223.4% |
| **MH6 on** | Cal 0.86 / ret 160.1% | **Cal 1.05 / ret 223.4%** |

### 主组合 vs face
| 指标 | face | LIVE1430-MH6-RD | Δ |
|---|---:|---:|---|
| ret | 158.3% | 223.4% | +65.1pp |
| maxDD | -15.9% | -18.2% | -2.3pp |
| Calmar | 0.96 | 1.05 | +0.09 |

分段 Calmar 过关：full=True · 2020–22=False · 2023–26=True · strong_regime=False

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
**主组合 MH6×rank-drop 证伪**：全样本/分段 Calmar 未过「≥face 或 Δret 盖住 Δ|MDD|」；强市周 Calmar 相对 face 折价>5%。

**结构注记**：本样本下 RD 开启时 MH6 未触发（#MH=0），`LIVE1430-MH6-RD` 与 `LIVE1430-RD` 路径一致；交叉增量需更长样本或更紧 MH 才可分离。

产物：`/workspace/research/SPIKE-S20-EXIT-CROSS-MH6-RANKDROP-LIVE1430/`（REPORT.md · summary.json · table.csv · equity.csv）。
耗时 21.4s。
