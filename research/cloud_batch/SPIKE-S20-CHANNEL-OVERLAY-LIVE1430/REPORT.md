# REPORT · SPIKE-S20-CHANNEL-OVERLAY-LIVE1430（510300 long/flat × B45 · 延窗）

## 1. 准则原文

```
# SPIKE-S20-CHANNEL-OVERLAY-LIVE1430

- 编号 / 日期 / 来源：SPIKE-S20-CHANNEL-OVERLAY-LIVE1430 / 2026-10-26 / Michael 语音·烧 Cursor（悟空）
- 批次 ID：CLOUD-CH-OVERLAY
- 性质：**宏观通道 long/flat（Ariston_Macro 风）× B45 广度门** 面层叠加（延窗）

## 准则原文
在 **SPIKE-S20 B45 face** 上叠加 **510300 周线通道/均线结构**：`risk_on = face_B45 ∧ macro_long`；macro 仅当 **价在上升均线/通道结构上方** 为 on，否则面层空仓（cash）。邻档 **周 MA20 / MA50 / MA100**（上升：MA 较 4 周前抬升）。Fri≥14:30 / 收盘；**0.2%RT**；**L≤1**；TV25+E0+max5+SHARPE20 冻结。

## 改动点（唯一）
相对 B45+S20，**只改 risk_on 合成**（加宏观 long/flat 过滤）；选品/填席/TV 不变。

## 假设
宏观 long/flat 能在不显著踏空 2023–26 的前提下 **压低 |MDD|**，且 Δret 盖住 Δ|MDD|（相对 FACE 基线）。

## 证伪
三邻档均未盖住回撤加深，或 2023–26 相对 FACE 明显踏空 → 证伪「宏观通道可作正式叠加」。

## 红线
不换冠；不碰 strategy_exec / LIVE_OPS / 冠军主钉；研究池 only。

## 主表
四账：B45 基线 + CH-MA20/50/100；产物 `.../SPIKE-S20-CHANNEL-OVERLAY-LIVE1430/`

## 交付
四件套；CloudAgent 批跑。
```

## 2. 实现要点

- **唯一改动**：`risk_on = face_B45 ∧ (510300 周收>Fri14:30价) > 上升周 MA{20,50,100}`（MA 较 4 周前抬升）。
- **冻结**：B45 + spike_ft max5 + E0 + SHARPE20 + **TV25**；Fri≥14:30 / 收盘；**0.2%RT**；**L≤1**。
- **对照**：`LIVE1430-B45-S20` = FACE 基线（无宏观叠加）。
- **延窗**：CLOUD-BATCH `research_cache`，日历至 **2026-10-23**（≥2026-10-23）。
- **隔离**：不写 strategy_exec / LIVE_OPS / 实盘池。

## 近似与覆盖

- 延窗：research_cache week/day/face/14:30；≤2026-10-09 沿用 face；其后研究周线 MA20 宽度
- qfq_1430 = price_1430 × (day qfq 收 / sina daily 收)；sina 作 bfq 代理
- 冲击分类：周线收盘替换为 qfq_1430 后因果 classify（Fri≥14:30 信号）
- Sharpe 窗截至信号日严格前一交易日
- 成交：周五收盘填仓 + 0.2%RT；L=min(1, σ*/max(σ20,σ60))；σ*=0.25 冻结
- 冻结 B45+spike_ft max5+S20+E0+TV25；**唯一改动** risk_on=FACE∧macro(510300 周MA上升结构)
- 只读 kit `data/cache_1430_snaps.json`；不写 strategy_exec / LIVE_OPS

| 覆盖 | 值 |
|---|---|
| 宏观代理 | 510300 |
| macro long 周数 MA20/50/100 | 114/121/89 |
| 可投池（AUM≥2亿） | 324 |
| 日历周 | 349（2020-01-03→2026-10-23） |
| listed 行 14:30 非空率 | 100.0% |
| 持仓 vs FACE 差异周（CHMA20） | 153/198 |

## 3. 主表（四账 · vs FACE）

| book | macro | ret | maxDD | CAGR | Calmar | Sharpe | 2020–22 ret/DD/C | 2023–26 ret/DD/C | avgL | avgTO | 空仓周 |
|---|---|---:|---:|---:|---:|---:|---|---|---:|---:|---:|
| LIVE1430-B45-S20 **FACE** | — | 158.3% | -15.9% | 15.0% | 0.94 | 0.91 | 29.3%/-14.9%/0.60 | 99.8%/-14.3%/1.39 | 0.83 | 0.154 | 150 |
| LIVE1430-B45-CHMA20-S20 | MA20 | 130.4% | -18.2% | 13.1% | 0.72 | 1.02 | 28.9%/-10.5%/0.85 | 78.8%/-18.2%/0.91 | 0.81 | 0.078 | 247 |
| LIVE1430-B45-CHMA50-S20 | MA50 | 73.0% | -16.7% | 8.4% | 0.50 | 0.74 | 0.1%/-16.7%/0.00 | 72.8%/-15.3%/1.01 | 0.83 | 0.071 | 257 |
| LIVE1430-B45-CHMA100-S20 | MA100 | 56.3% | -17.8% | 6.8% | 0.38 | 0.72 | 0.2%/-2.8%/0.03 | 55.9%/-17.8%/0.70 | 0.83 | 0.049 | 283 |

### Δ vs FACE（探索尺子）

| book | Δret vs FACE | Δ|MDD| | 盖住? | 2023–26 不差 |
|---|---:|---:|---|---|
| B45-CHMA20-S20 | -27.8pp | +2.3pp | 否 | 否 |
| B45-CHMA50-S20 | -85.3pp | +0.8pp | 否 | 否 |
| B45-CHMA100-S20 | -102.0pp | +1.9pp | 否 | 否 |

### 分段 · FACE 基线

| 段 | ret | maxDD | Calmar |
|---|---:|---:|---:|
| 2020–22 | 29.3% | -14.9% | 0.60 |
| 2023–26 | 99.8% | -14.3% | 1.39 |

## 4. 一句结论（探索记账，不换冠）

**证伪宏观通道叠加（不换冠）**：三邻档均未浅化 |MDD| 或 2023–26 踏空； CH-MA20 Δret=-27.8pp、Δ|MDD|=+2.3pp。

## 产物

- `run.py` / `criterion.md` / `REPORT.md` / `summary.json`
- `table.csv` / `metrics.csv` / `yearly.csv` / `equity.csv` / `nav_*.csv` / `equity_curve.png` / `macro_510300_signals.csv`

耗时约 6.6s。
