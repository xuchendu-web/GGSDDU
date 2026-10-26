# REPORT · SPIKE-S20-POS-SIZING-RESEARCH（权重轴 · 研究池）

## 准则原文（摘要）

相对 B45+S20（EQ5 等权）**只改持仓权重**：等权 max5 / 20 周反波动 / 单票 30% 上限；**入场排序仍 SHARPE20**；E0+TV25 不变。研究池；窗 ≥2026-10-23。CLOUD-POS-SIZING，不换冠。

## 实现要点

- 引擎：fork MAXSEAT `run.py` + CLOUD-BATCH `research_cache` 延窗路径。
- 三账本：EQ5 / INV20W / CAP30；EQ5 为 B45+S20 基线。
- 只读：`CLOUD-BATCH-2026-10-26/data/cache_1430_snaps.json`（end=2026-10-23）。
- 隔离：strategy_exec / LIVE_OPS **NONE** 写入。

基线 **EQ5**（=B45+S20 等权）：ret=158.3% MDD=-15.9% Calmar=0.94；样本 2020-01-03→2026-10-23（n=349 周）。

## 近似与覆盖

- 延窗：week/day/face/14:30 来自 CLOUD-BATCH data/research_cache；breadth risk_on 用 holdings_ro2_extended
- qfq_1430 = price_1430 × (day qfq 收 / sina 收)；sina 作 bfq 代理
- 14:30 分类只读 cache_1430_snaps.json（end=2026-10-23）
- Sharpe 窗截至信号日严格前一交易日（无周五收盘前视）
- 成交/净值：周五收盘填仓 + TV25 + 0.2%RT；L≤1
- 唯一改动：持仓权重 EQ5 / INV20W / CAP30；SHARPE20 填席与 max5 不变
- 不写 strategy_exec / LIVE_OPS / 冠军主钉

| 覆盖 | 值 |
|---|---|
| 可投池（AUM≥2亿） | 324 |
| 日历周 | 349（至 2026-10-23） |
| listed 行 14:30 非空率 | 100.0% |
| 成功映射 qfq_1430 | 45269 |
| EQ5 候选周 / 排队>席 | 190 / 81 |
| INV20W vs EQ5 持仓差异周 | 0/198 |
| CAP30 vs EQ5 持仓差异周 | 0/198 |

## 主表（研究池 · Fri 14:30 · 三档）

| book | ret | maxDD | CAGR | Calmar | 2020–22 ret/DD/Calmar | 2023–26 ret/DD/Calmar | avgL | avgTO | 空仓周 |
|---|---:|---:|---:|---:|---|---|---:|---:|---:|
| EQ5 **基线** | 158.3% | -15.9% | 15.0% | 0.94 | 29.3%/-14.9%/0.60 | 99.8%/-14.3%/1.39 | 0.83 | 0.154 | 150 |
| INV20W | 111.6% | -15.5% | 11.6% | 0.75 | 19.5%/-15.4%/0.40 | 77.0%/-13.8%/1.17 | 0.86 | 0.168 | 150 |
| CAP30 | 146.0% | -16.6% | 14.1% | 0.85 | 25.5%/-14.9%/0.53 | 96.1%/-13.9%/1.40 | 0.83 | 0.142 | 150 |

## Δ vs EQ5（探索尺子）

- INV20W：ret=111.6% MDD=-15.5% Calmar=0.75；Δvs EQ5 ret=-46.7pp Δ|MDD|=-0.4pp 盖住=否 2023–26不差=否
- CAP30：ret=146.0% MDD=-16.6% Calmar=0.85；Δvs EQ5 ret=-12.2pp Δ|MDD|=+0.8pp 盖住=否 2023–26不差=是

## 分段（EQ5 基线）

| 段 | EQ5 ret/DD/Calmar |
|---|---|
| 2020–22 | 29.3% / -14.9% / 0.60 |
| 2023–26 | 99.8% / -14.3% / 1.39 |

## 历年

| 年 | EQ5 | INV20W | Δpp(inv-eq) | CAP30 | Δpp(cap-eq) |
|---|---:|---:|---:|---:|---:|
| 2020 | 27.0% | 22.0% | -5.0 | 21.8% | -5.2 |
| 2021 | 9.7% | 5.9% | -3.8 | 11.0% | +1.3 |
| 2022 | -7.2% | -7.5% | -0.3 | -7.2% | +0.0 |
| 2023 | 4.9% | 5.6% | +0.7 | 2.7% | -2.2 |
| 2024 | 10.6% | 8.1% | -2.5 | 10.2% | -0.4 |
| 2025 | 38.9% | 28.5% | -10.4 | 39.8% | +0.9 |
| 2026 | 23.9% | 20.7% | -3.3 | 23.9% | +0.0 |

## 结论（探索记账，不换冠）

**探索证伪/记账（不换冠）**：INV20W 与 CAP30 均未稳定优于 B45+S20 等权；与 2026-10-14 INVVOL 叙事一致，不换冠。

## 产物

- `run.py` / `criterion.md` / `REPORT.md` / `summary.json`
- `table.csv` / `metrics.csv` / `yearly.csv` / `equity.csv` / `nav_*.csv` / `equity_curve.png`
- `holdings_*.csv` / `trades_*.csv` / `entries_*.csv`

耗时约 6.8s。
