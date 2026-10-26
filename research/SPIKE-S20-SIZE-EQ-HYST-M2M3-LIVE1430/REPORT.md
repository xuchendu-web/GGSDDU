# REPORT · SPIKE-S20-SIZE-EQ-HYST-M2M3-LIVE1430（等权 + 滞回 · 研究池）

## 准则原文（摘要）

在 PR#44 结论（INV/CAP 未胜等权）之上，**冻结等权**，只测 **HYST-M2/M3** 持仓滞回；Face B45+S20+TV25 不变。INV×HYST-M3 仅归因。Composer lane；不换冠。

## 实现要点

- 引擎：POS-SIZING 等权权重 + E24/HYST-M3 rank-kick 逻辑；CLOUD-BATCH `research_cache` 延窗。
- 四账本：Face EQ / EQ+HYST-M2 / EQ+HYST-M3 / INV×HYST-M3（归因）。
- 只读：`CLOUD-BATCH-2026-10-26/data/cache_1430_snaps.json`（end=2026-10-23）。
- 隔离：strategy_exec / LIVE_OPS / champion **NONE** 写入。

基线 **Face EQ**（fill-only 等权）：ret=158.3% MDD=-15.9% Calmar=0.94；样本 2020-01-03→2026-10-23（n=349 周）。

## 近似与覆盖

- 延窗：week/day/face/14:30 来自 CLOUD-BATCH data/research_cache；breadth risk_on 用 holdings_ro2_extended
- qfq_1430 = price_1430 × (day qfq 收 / sina 收)；sina 作 bfq 代理
- 14:30 分类只读 cache_1430_snaps.json（end=2026-10-23）
- Sharpe 窗截至信号日严格前一交易日（无周五收盘前视）
- 成交/净值：周五收盘填仓 + TV25 + 0.2%RT；L≤1
- 唯一改动：等权持仓 + HYST-M2/M3 滞回踢出（rank>5+M）；SHARPE20 填席与 max5 不变
- INV×HYST-M3 仅归因对照，不晋升
- 不写 strategy_exec / LIVE_OPS / 冠军主钉

| 覆盖 | 值 |
|---|---|
| 可投池（AUM≥2亿） | 324 |
| 日历周 | 349（至 2026-10-23） |
| listed 行 14:30 非空率 | 100.0% |
| 成功映射 qfq_1430 | 45269 |
| Face EQ 候选周 / 排队>席 | 190 / 81 |
| M2 vs Face 持仓差异周 | 141/198 |
| M3 vs Face 持仓差异周 | 141/198 |
| M3 hyst 踢出笔数 | 112 |

## 主表（研究池 · Fri 14:30）

| book | ret | maxDD | CAGR | Calmar | 2020–22 ret/DD/Calmar | 2023–26 ret/DD/Calmar | avgL | avgTO | 空仓周 | hyst踢 |
|---|---:|---:|---:|---:|---|---|---:|---:|---:|---:|
| EQ-S20 **基线** | 158.3% | -15.9% | 15.0% | 0.94 | 29.3%/-14.9%/0.60 | 99.8%/-14.3%/1.39 | 0.83 | 0.154 | 150 | 0 |
| EQ-HYST-M2-S20 | 166.1% | -18.5% | 15.5% | 0.84 | 0.4%/-18.4%/0.01 | 165.0%/-12.8%/2.28 | 0.82 | 0.206 | 150 | 130 |
| EQ-HYST-M3-S20 | 195.3% | -15.3% | 17.3% | 1.13 | 16.2%/-15.3%/0.34 | 154.1%/-12.8%/2.16 | 0.81 | 0.193 | 150 | 112 |
| INV-HYST-M3-S20 *归因* | 174.3% | -15.6% | 16.0% | 1.02 | 10.3%/-15.5%/0.22 | 148.6%/-11.5%/2.35 | 0.84 | 0.208 | 150 | 112 |

## Δ vs Face EQ（探索尺子）

- EQ+HYST-M2：ret=166.1% MDD=-18.5% Calmar=0.84；Δvs Face ret=+7.8pp Δ|MDD|=+2.6pp ΔCalmar=-0.11 盖住=是 Calmar优于=否 2023–26不差=是
- EQ+HYST-M3：ret=195.3% MDD=-15.3% Calmar=1.13；Δvs Face ret=+37.0pp Δ|MDD|=-0.5pp ΔCalmar=+0.18 盖住=是 Calmar优于=是 2023–26不差=是
- INV×HYST-M3（归因）：ret=174.3% MDD=-15.6% Calmar=1.02；Δvs Face ret=+16.0pp Δ|MDD|=-0.2pp ΔCalmar=+0.08 盖住=是 Calmar优于=是 2023–26不差=是

## M3 vs M2（邻居）

- Δret=+29.2pp；ΔCalmar=+0.29

## 分段（Face EQ）

| 段 | Face EQ ret/DD/Calmar |
|---|---|
| 2020–22 | 29.3% / -14.9% / 0.60 |
| 2023–26 | 99.8% / -14.3% / 1.39 |

## 历年

| 年 | Face EQ | M2 | Δpp | M3 | Δpp | INV×M3 | Δpp |
|---|---:|---:|---:|---:|---:|---:|---:|
| 2020 | 27.0% | 14.3% | -12.7 | 19.4% | -7.6 | 17.4% | -9.6 |
| 2021 | 9.7% | -3.1% | -12.9 | 7.4% | -2.4 | 4.7% | -5.0 |
| 2022 | -7.2% | -9.3% | -2.1 | -9.3% | -2.1 | -10.3% | -3.0 |
| 2023 | 4.9% | 16.4% | +11.5 | 17.2% | +12.3 | 17.9% | +13.0 |
| 2024 | 10.6% | 17.7% | +7.1 | 17.7% | +7.0 | 16.3% | +5.6 |
| 2025 | 38.9% | 55.8% | +16.9 | 48.6% | +9.7 | 44.5% | +5.6 |
| 2026 | 23.9% | 24.1% | +0.2 | 24.0% | +0.1 | 25.5% | +1.5 |

## 结论（探索记账，不换冠）

**HYST-M3 探索记正（不换冠）**：Calmar 优于 Face 且 Δret 盖住 Δ|MDD|、后段不踏空。 **HYST-M2 探索偏弱**：盖住回撤但 Calmar 未优于 Face（segment/skip 风险）。 INV×HYST-M3 仅归因：Calmar=1.02，不晋升。

## 产物

- `run.py` / `criterion.md` / `REPORT.md` / `summary.json`
- `table.csv` / `metrics.csv` / `yearly.csv` / `equity.csv` / `nav_*.csv` / `equity_curve.png`
- `holdings_*.csv` / `trades_*.csv` / `entries_*.csv`

耗时约 8.1s。
