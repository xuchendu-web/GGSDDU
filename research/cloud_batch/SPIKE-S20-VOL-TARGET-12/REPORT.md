# REPORT · SPIKE-S20-VOL-TARGET-12（12% 年化波动目标 · vs unscaled）

## 准则原文（摘要）

在冻结的 **B45+S20 face weekly**（EQ5 / SHARPE20 / max5 / E0）上，只改杠杆叠加：**UNSCALED (L=1)** vs **VT12 (σ*=12%)**；TV25 为面层参照。研究池；窗 ≥2026-10-23。CLOUD-VOL-TARGET-12，不换冠，**No LIVE**。

## 实现要点

- 引擎：fork POS-SIZING / MAXSEAT `run.py` + CLOUD-BATCH `research_cache` 延窗路径。
- 一周频持仓，三叠加：UNSCALED / VT12 / TV25。
- 只读：`CLOUD-BATCH-2026-10-26/data/cache_1430_snaps.json`（end=2026-10-23）。
- 隔离：strategy_exec / LIVE_OPS **NONE** 写入。

基线 **UNSCALED**（B45+S20 EQ5，L=1）：ret=159.7% MDD=-25.7% vol=21.7% Calmar=0.59；样本 2020-01-03→2026-10-23（n=349 周）。

## 近似与覆盖

- 延窗：week/day/face/14:30 来自 CLOUD-BATCH data/research_cache；breadth risk_on 用 holdings_ro2_extended
- qfq_1430 = price_1430 × (day qfq 收 / sina 收)；sina 作 bfq 代理
- 14:30 分类只读 cache_1430_snaps.json（end=2026-10-23）
- Sharpe 窗截至信号日严格前一交易日（无周五收盘前视）
- 成交/净值：周五收盘填仓 + 0.2%RT；L≤1
- 周频持仓冻结为 B45+S20 EQ5 max5（三账本共享）
- 唯一改动：杠杆叠加 UNSCALED(L=1) / VT12(σ*=12%) / TV25(σ*=25% 面层参照)
- σ̂ = max(近20日, 近60日) 未杠杆组合日收益年化波动（与面层 TV 同构）
- 不写 strategy_exec / LIVE_OPS / 冠军主钉

| 覆盖 | 值 |
|---|---|
| 可投池（AUM≥2亿） | 324 |
| 日历周 | 349（至 2026-10-23） |
| listed 行 14:30 非空率 | 100.0% |
| 成功映射 qfq_1430 | 45269 |
| 候选周 / 排队>席 | 190 / 81 |
| 三账本持仓差异周 | 0（共享 FACE） |

## 主表（研究池 · Fri 14:30 · vs unscaled）

| book | ret | maxDD | vol | CAGR | Calmar | 2020–22 ret/DD/Calmar | 2023–26 ret/DD/Calmar | avgL | L<1占比 | avgTO | 空仓周 |
|---|---:|---:|---:|---:|---:|---|---|---:|---:|---:|---:|
| UNSCALED **基线** | 159.7% | -25.7% | 21.7% | 15.1% | 0.59 | 33.3%/-25.7%/0.39 | 94.8%/-20.7%/0.93 | 1.00 | 0.0% | 0.180 | 150 |
| VT12 | 71.1% | -12.0% | 9.6% | 8.2% | 0.69 | 12.3%/-12.0%/0.33 | 52.4%/-7.0%/1.67 | 0.44 | 99.0% | 0.085 | 150 |
| TV25 **面层** | 158.3% | -15.9% | 17.6% | 15.0% | 0.94 | 29.3%/-14.9%/0.60 | 99.8%/-14.3%/1.39 | 0.83 | 69.8% | 0.154 | 150 |

## Δ vs UNSCALED（探索尺子）

- VT12：ret=71.1% MDD=-12.0% vol=9.6% Calmar=0.69；Δvs UNSCALED ret=-88.5pp Δ|MDD|=-13.7pp Δvol=-12.2pp 盖住=否 2023–26不差=否
- TV25：ret=158.3% MDD=-15.9% vol=17.6% Calmar=0.94；Δvs UNSCALED ret=-1.4pp Δ|MDD|=-9.9pp Δvol=-4.2pp 盖住=是 2023–26不差=是

## 分段（UNSCALED 基线）

| 段 | UNSCALED ret/DD/vol/Calmar | VT12 ret/DD/vol/Calmar |
|---|---|---|
| 2020–22 | 33.3% / -25.7% / 22.0% / 0.39 | 12.3% / -12.0% / 9.6% / 0.33 |
| 2023–26 | 94.8% / -20.7% / 21.5% / 0.93 | 52.4% / -7.0% / 9.5% / 1.67 |

## 历年

| 年 | UNSCALED | VT12 | Δpp(vt-un) | TV25 | Δpp(tv-un) |
|---|---:|---:|---:|---:|---:|
| 2020 | 31.6% | 10.8% | -20.8 | 27.0% | -4.6 |
| 2021 | 10.1% | 5.0% | -5.2 | 9.7% | -0.4 |
| 2022 | -8.0% | -3.5% | +4.5 | -7.2% | +0.8 |
| 2023 | 1.9% | 3.8% | +1.8 | 4.9% | +3.0 |
| 2024 | 10.2% | 7.0% | -3.3 | 10.6% | +0.4 |
| 2025 | 38.1% | 22.7% | -15.4 | 38.9% | +0.8 |
| 2026 | 25.5% | 11.9% | -13.6 | 23.9% | -1.6 |

## 结论（探索记账，不换冠）

**探索记账（不换冠）**：VT12 把已实现波动压近 12%、Calmar 或改善，但 Δret 未盖住 Δ|MDD|；研究记账，不换冠。

TV25 面层参照：ret=158.3% MDD=-15.9% vol=17.6% Calmar=0.94（应对齐已知 158.3% / −15.9% / 0.94）。

## 产物

- `run.py` / `criterion.md` / `REPORT.md` / `summary.json`
- `table.csv` / `metrics.csv` / `yearly.csv` / `equity.csv` / `nav_*.csv` / `equity_curve.png` / `scale_log.csv`
- `holdings_RESEARCH-S20-FACE.csv` / `trades_RESEARCH-S20-FACE.csv` / `entries_RESEARCH-S20-FACE.csv`

耗时约 5.1s。
