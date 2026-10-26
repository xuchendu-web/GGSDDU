# REPORT · SPIKE-S20-VOL-TARGET-FKELLY（fractional Kelly σ* vs VT12）

## 准则原文（摘要）

在冻结的 **B45+S20 face weekly**（EQ5 / SHARPE20 / max5 / E0）上，只改杠杆叠加：**UNSCALED**、**VT12 (12%)**、**VTFK50/25**（σ*=min(15%, f×SR×σ̂)）。研究池；窗 ≥2026-10-23。CLOUD-VOL-TARGET-FKELLY，不换冠，**No LIVE**。

## 实现要点

- 引擎：fork `SPIKE-S20-VOL-TARGET-12` + CLOUD-BATCH `research_cache`。
- 一周频持仓，四叠加；持仓完全一致。
- 只读：`cache_1430_snaps.json`（end=2026-10-23）。
- 隔离：strategy_exec / LIVE_OPS **NONE** 写入。

基线 **UNSCALED**（B45+S20 EQ5，L=1）：ret=159.7% MDD=-25.7% vol=21.7% Calmar=0.59；样本 2020-01-03→2026-10-23（n=349 周）。

## 近似与覆盖

- 延窗：week/day/face/14:30 来自 CLOUD-BATCH data/research_cache；breadth risk_on 用 holdings_ro2_extended
- qfq_1430 = price_1430 × (day qfq 收 / sina 收)；sina 作 bfq 代理
- 14:30 分类只读 cache_1430_snaps.json（end=2026-10-23）
- Sharpe 窗截至信号日严格前一交易日（无周五收盘前视）
- 成交/净值：周五收盘填仓 + 0.2%RT；L≤1
- 周频持仓冻结为 B45+S20 EQ5 max5（三账本共享）
- 唯一改动：杠杆叠加 UNSCALED / VT12(12%) / VTFK50 / VTFK25（σ*=min(15%,f×SR×σ̂)）
- σ̂ = max(近20日, 近60日) 未杠杆组合日收益年化波动；SR 同窗 trailing Sharpe
- 不写 strategy_exec / LIVE_OPS / 冠军主钉

| 覆盖 | 值 |
|---|---|
| 可投池（AUM≥2亿） | 324 |
| 日历周 | 349（至 2026-10-23） |
| listed 行 14:30 非空率 | 100.0% |
| 成功映射 qfq_1430 | 45269 |
| 候选周 / 排队>席 | 190 / 81 |
| 四账本持仓差异周 | 0（共享 FACE） |

## 主表（Sortino / Sharpe / Calmar / maxDD / turnover）

| book | ret | maxDD | vol | Sharpe | Sortino | Calmar | 2020–22 ret/DD/Calmar | 2023–26 ret/DD/Calmar | avgL | L<1占比 | avgTO | 空仓周 |
|---|---:|---:|---:|---:|---:|---:|---|---|---:|---:|---:|---:|
| UNSCALED **基线** | 159.7% | -25.7% | 21.7% | 0.78 | 0.05 | 0.59 | 33.3%/-25.7%/0.39 | 94.8%/-20.7%/0.93 | 1.00 | 0.0% | 0.180 | 150 |
| VT12 | 71.1% | -12.0% | 9.6% | 0.91 | 0.06 | 0.69 | 12.3%/-12.0%/0.33 | 52.4%/-7.0%/1.67 | 0.44 | 99.0% | 0.085 | 150 |
| VTFK50 | 50.7% | -9.8% | 8.8% | 0.75 | 0.05 | 0.63 | 7.3%/-6.4%/0.37 | 40.4%/-9.8%/0.95 | 0.41 | 98.6% | 0.066 | 150 |
| VTFK25 | 28.6% | -10.4% | 7.6% | 0.55 | 0.03 | 0.36 | 1.7%/-6.9%/0.08 | 26.5%/-7.1%/0.89 | 0.33 | 99.3% | 0.053 | 150 |

## Δ vs UNSCALED（探索尺子）

- VT12：ret=71.1% MDD=-12.0% vol=9.6% Sharpe=0.91 Sortino=0.06 Calmar=0.69 TO=0.085；Δvs UNSCALED ret=-88.5pp Δ|MDD|=-13.7pp 盖住=否 2023–26不差=否
- VTFK50：ret=50.7% MDD=-9.8% vol=8.8% Sharpe=0.75 Sortino=0.05 Calmar=0.63 TO=0.066；Δvs UNSCALED ret=-109.0pp Δ|MDD|=-15.9pp 盖住=否 2023–26不差=否
- VTFK25：ret=28.6% MDD=-10.4% vol=7.6% Sharpe=0.55 Sortino=0.03 Calmar=0.36 TO=0.053；Δvs UNSCALED ret=-131.1pp Δ|MDD|=-15.3pp 盖住=否 2023–26不差=否

## 分段（UNSCALED 基线 vs VT12 vs FK50）

| 段 | UNSCALED | VT12 | VTFK50 |
|---|---|---|---|
| 2020–22 | 33.3% / -25.7% / 0.39 | 12.3% / -12.0% / 0.33 | 7.3% / -6.4% / 0.37 |
| 2023–26 | 94.8% / -20.7% / 0.93 | 52.4% / -7.0% / 1.67 | 40.4% / -9.8% / 0.95 |

VT12 对照（PR#47）：Calmar 0.69；FK25 Calmar 0.36。

## 历年

| 年 | UNSCALED | VT12 | FK50 | FK25 |
|---|---:|---:|---:|---:|
| 2020 | 31.6% | 10.8% | 8.1% | 4.7% |
| 2021 | 10.1% | 5.0% | -0.9% | -2.9% |
| 2022 | -8.0% | -3.5% | 0.1% | 0.1% |
| 2023 | 1.9% | 3.8% | -0.5% | -2.0% |
| 2024 | 10.2% | 7.0% | 3.2% | 1.3% |
| 2025 | 38.1% | 22.7% | 23.5% | 16.4% |
| 2026 | 25.5% | 11.9% | 10.7% | 9.4% |

## 结论（探索记账，不换冠）

**探索记账（不换冠）**：固定 VT12 仍优于 FK 网格；σ*=min(15%,f×SR×σ̂) 不作面层替换。

## 产物

- `run.py` / `criterion.md` / `REPORT.md` / `summary.json`
- `table.csv` / `metrics.csv` / `yearly.csv` / `equity.csv` / `nav_*.csv` / `equity_curve.png` / `scale_log.csv`
- `holdings_RESEARCH-S20-FACE.csv` / `trades_RESEARCH-S20-FACE.csv` / `entries_RESEARCH-S20-FACE.csv`

耗时约 5.3s。
