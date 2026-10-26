# REPORT · SPIKE-S20-NOBREADTH-LIVE1430（去 breadth）

## 1. 准则原文

```
# SPIKE-S20-NOBREADTH-LIVE1430

- 编号 / 日期 / 来源：SPIKE-S20-NOBREADTH-LIVE1430 / 2026-10-26 / Michael 语音指定（悟空转达·再改口）
- 批次 ID：HYP-SPIKE-S20-NOB
- 性质：探索正式单刀；**不含 breadth 开关**
- 取代：假设#3 BCONF2（已作废停派）；非 TEMA580-SPIKE-NOTBREADTH（彼刀是换 TEMA 开关，已证伪）；非 ETF-TOP3-RET52-NOBREADTH（无结构 TopK，已证伪）

## 准则原文
相对研究基线 **B45+S20-LIVE1430**，**只去掉 breadth≥45% MA20 风险开关**：

- **每周一律 risk_on**（无宽度门；不因 b 空仓）。
- 开仓周选品与仓位不变：**spike_ft max5**（excl box_pending）→ **SHARPE20** 填席取 max5 → **E0** 出场 → **TV25**（σ*=0.25）定总暴露，等权腿内。
- 口径：Fri ≥14:30 信号 / 当日收盘；0.2%RT；**L≤1**；研究池（≠实盘池）。

即组合面 = **Spike max5 × Top Sharp 20（SHARPE20）**，无 breadth；**保留 E0 / TV25**（出场与总仓，与「无 breadth」不冲突，本刀不改这两腿）。

## 改动点（唯一）
`risk_on = (b ≥ 0.45)` → **`risk_on ≡ True`（去 breadth）**。  
不改 spike / 填席窗 / E0 / TV / 成交时点；不叠 HYST / 空仓债 / B50。

## 为什么应该有效（逻辑闸）
高相关政策宇宙里 breadth 常与行业同步，弱宽度周会把仍在冲击的 spike 一并关掉（5/15 后长空仓即为例）。去掉宽度门，让 spike×S20 自己决定有没有票：有 spike 且 S20 够格就持，没有就自然轻仓/空——回答「面层要不要宽度门」这一腿，而不是换另一套开关（TEMA 已证伪）或改成裸动量 TopK（RET52 Top3 已证伪）。

## 预期（探索尺子）
相对同窗 B45+S20：空仓周应下降；Δret 须盖住可能加深的 Δ|MDD|；2023–26 强势段参与不差 → 探索记正。  
若回撤明显加深且收益盖不住，或仅靠多挨打换一点收益 → 证伪「可去 breadth」。

## 主表必须含
| book | 说明 |
|---|---|
| **B45+S20** | 基线（同引擎同窗；延窗后数字以本跑为准） |
| **NOB+S20-max5** | 本刀主（无 breadth + spike max5 + S20 + E0 + TV25） |

## 邻档 / 旁注（稳健，非插值升格）
- 席位：无 breadth 下 spike/**S20 max3**、**max7**（只动席位数）
- 可选旁注一行：已证伪 TEMA580-SPIKE-NOTBREADTH / TOP3-RET52-NOB 结论（勿重跑）
- 分段：2020–22 / 2023–26；报 cash 周占比 vs 基线

## 数据（开跑前必做）
研究 panel / 日周 / face / 14:30 接到**最新完整周**（目标 ≥**2026-10-23**）。暂停前约止 10-16、主回测多止 09-24，须延窗后再出主表。

## 红线
不换冠；不写 `strategy_exec` / LIVE_OPS / 实盘池 / 冠军主钉 / 固收+ / 红利袖；510300 不作开关；勿重派 BCONF2 / BATCH 同构 / 511260。

## 交付
四件套 → `/workspace/strategy-weekly/spike_mom_rank/SPIKE-S20-NOBREADTH-LIVE1430/`  
准则：`/workspace/strategy-weekly/knives/SPIKE-S20-NOBREADTH-LIVE1430.md`

## 成功/证伪（探索）
- vs 同窗 B45+S20：Δret 盖住 Δ|MDD| 且后段不踏空 → **探索记正**（不换冠）
- 未盖住 / 后段塌 / 回撤失控 → **证伪「去 breadth」**
```

## 2. 实现要点

- **唯一改动**：`risk_on=(b≥0.45)` → **`risk_on≡True`**（NOB 书）；B45 书仍用 face 宽度门作同窗对照。
- **冻结**：spike_ft max5（excl box_pending）+ SHARPE20 填席 + E0 + TV25（σ*=0.25）+ Fri≥14:30/收盘 + 0.2%RT + L≤1；研究池。
- **邻档**：仅动席位 max3 / max7。
- **延窗**：研究缓存接到 **2026-10-23**（目标 ≥2026-10-23）；14:30 新周 pytdx；日线缺口 sina 收益链拼接。
- **不换冠**；不写 strategy_exec / LIVE_OPS / 实盘池。

## 近似与覆盖

- 延窗研究缓存：week/day 合并 recon week_2026-10-23 / day_2026-10-23；缺日线用 sina 收益链拼接（研究目录）
- 14:30 新周（09-30/10-09/10-16/10-23）pytdx idx209 拉入 research_cache；旧周复用 fri_1430_through_20260925
- B45 breadth/risk_on：≤2026-10-09 沿用 face holdings_ro2；其后用研究周线 MA20 宽度假算（aum≥2）
- NOB：risk_on≡True（去 breadth）；选品/E0/TV25/成本同引擎
- qfq_1430 = price_1430 × (day/tema qfq 收 / sina 收)；Sharpe 窗截至信号日前一交易日
- 成交/净值：信号周末交易日收盘填仓 + TV25 + 0.2%RT；L≤1

| 覆盖 | 值 |
|---|---|
| 可投池（AUM≥2亿） | 324 |
| 日历周 | 349（2020-01-03→2026-10-23） |
| listed 行 14:30 非空率 | 100.0% |
| 成功映射 qfq_1430 | 73435 |
| B45 risk_on 周占比 | 58.3% |
| NOB risk_on 周占比 | 100.0% |

## 3. 主表（LIVE1430 · Fri 14:30 信号）

| book | ret | maxDD | CAGR | Calmar | 2020–22 ret/DD/C | 2023–26 ret/DD/C | avgL | cash周% |
|---|---:|---:|---:|---:|---|---|---:|---:|
| LIVE1430-B45-S20 | 134.0% | -18.9% | 13.3% | 0.70 | 18.8%/-16.1%/0.37 | 97.0%/-15.1%/1.29 | 0.84 | 43.1% |
| LIVE1430-NOB-S20-max5 | 96.6% | -33.9% | 10.4% | 0.31 | 24.4%/-33.9%/0.22 | 58.0%/-20.8%/0.61 | 0.85 | 4.9% |
| LIVE1430-NOB-S20-max3 | 121.9% | -30.0% | 12.4% | 0.41 | 28.6%/-30.0%/0.29 | 72.5%/-18.9%/0.82 | 0.82 | 4.9% |
| LIVE1430-NOB-S20-max7 | 70.6% | -35.9% | 8.2% | 0.23 | 9.2%/-35.9%/0.08 | 56.2%/-18.6%/0.67 | 0.86 | 4.6% |

### Δ · NOB-max5 vs B45

| | |
|---|---|
| Δ总收益 | -37.4pp |
| ΔMDD（代数；正=更浅） | -15.0pp |
| Δ\|MDD\|（正=更深） | +15.0pp |
| ΔCAGR | -2.86pp |
| ΔCalmar | -0.40 |
| Δcash周占比 | -38.2pp（B45 43.1% → NOB 4.9%） |

### 分段

| 段 | B45 ret/DD/Calmar | NOB5 ret/DD/Calmar |
|---|---|---|
| 2020–22 | 18.8% / -16.1% / 0.37 | 24.4% / -33.9% / 0.22 |
| 2023–26 | 97.0% / -15.1% / 1.29 | 58.0% / -20.8% / 0.61 |

### 邻档

- NOB-max3：ret=121.9% MDD=-30.0% Calmar=0.41 cash=4.9%
- NOB-max7：ret=70.6% MDD=-35.9% Calmar=0.23 cash=4.6%

### 历年

| 年 | B45 | NOB5 | Δpp | NOB3 | NOB7 | B45 MDD | NOB5 MDD |
|---|---:|---:|---:|---:|---:|---:|---:|
| 2020 | 25.3% | 36.1% | +10.8 | 40.7% | 31.1% | -15.0% | -14.2% |
| 2021 | 3.1% | 7.6% | +4.5 | 6.2% | 0.7% | -11.9% | -17.0% |
| 2022 | -8.0% | -15.1% | -7.0 | -13.9% | -17.3% | -10.1% | -26.8% |
| 2023 | 4.2% | 2.2% | -2.0 | 5.8% | 3.6% | -8.7% | -11.6% |
| 2024 | 13.1% | 6.4% | -6.7 | 8.3% | 8.3% | -7.9% | -16.0% |
| 2025 | 41.9% | 46.0% | +4.1 | 49.1% | 42.2% | -8.7% | -9.1% |
| 2026 | 17.8% | -0.4% | -18.3 | 1.0% | -2.2% | -15.1% | -18.7% |

### 旁注

旁注（勿重跑）：TEMA580-SPIKE-NOTBREADTH / ETF-TOP3-RET52-NOBREADTH 均已证伪（彼为换 TEMA 开关或裸动量 TopK；本刀是同结构去 face breadth）。

## 4. 一句证伪或通过

**证伪「可去 breadth」（不换冠）**：Δret=-37.4pp 未盖住 Δ|MDD|=+15.0pp；2023–26 踏空/塌（NOB 58.0% vs B45 97.0%）。全样本 ΔCalmar=-0.40；cash周 Δ-38.2pp。

## 产物

- `run.py` / `extend_research_data.py` / `criterion.md` / `REPORT.md` / `equity_curve.png`
- `table.csv` / `metrics.csv` / `yearly.csv` / `equity.csv` / `nav_*.csv` / `summary.json`
- `holdings_*.csv` / `trades_*.csv` / `entries_*.csv`
- `research_cache/`（week/day/sina/face/14:30 延窗；不碰 strategy_exec）
- `cache_1430_snaps.json`（本刀目录，不覆盖旧 LIVE1430 缓存）

耗时约 52.5s。延窗实际终点 **2026-10-23**。
