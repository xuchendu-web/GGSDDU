# REPORT · SPIKE-S20-TURNOVER-PENALTY-LIVE1430（填席换手惩罚）

## 1. 准则原文

```
# SPIKE-S20-TURNOVER-PENALTY-LIVE1430

- 编号 / 日期 / 来源：SPIKE-S20-TURNOVER-PENALTY-LIVE1430 / 2026-10-26 / Michael 语音·烧 Cursor（悟空）
- 批次 ID：CLOUD-TURNOVER-PENALTY
- 性质：**填席排序换手惩罚**（研究池；非 LIVE / 非实盘）

## 准则原文
冻结面层 **B45 + spike_ft max5 + E0 + TV25 + SHARPE20**；Fri≥14:30/收盘；**0.2%RT**；**L≤1**。  
**唯一改动**：填席排序时对高近期换手标的扣分（**非**额外费率）：  
`score = sharpe20 − λ × to_norm`，再按 score 取 top-max5。  
`to_norm`：当周 spike 候选池（有 sharpe20 者）内对 `trailing_4w_turnover` 做 min-max 归一化至 [0,1]（池内无跨度则 0）。  
λ ∈ **{0, 0.15, 0.25}**；**λ=0** 为同窗对照（plain face）。

## 换手分（可复现）
`trailing_4w_turnover(code, Fri_d)` = 信号周 `d` 之前 **4 个日历周五**（不含 `d`）上，各周五 14:30 切片  
`turnover_rate_fri = (vol_1430 × price_1430) / (aum_亿元 × 1e8)` 的算术均值；缺 `vol_1430`/价/AUM 的周五跳过；全无则 **0**。

## 邻档
- **对照 / baseline**：λ=0（plain S20 填席）
- **网格**：λ=0.15、λ=0.25（仅排序惩罚权重）

## 假设
λ>0 能在 **不显著牺牲 Calmar** 下压低组合换手/改善回撤覆盖（Δret 盖住 Δ|MDD|）；后段 2023–26 不踏空。

## 证伪
任一档 **λ>0** 相对 λ=0：**Calmar 更差** 且 **Δret 盖不住 Δ|MDD|**（全样本或 2020–22 / 2023–26 分段）；或后段 ret 明显踏空（< λ=0 ×0.9）。

## 红线
不重做成本敏感性（PR#40）；不改 breadth/TV/滞回/债腿；不写 strategy_exec / LIVE_OPS / 实盘池；不换冠。

## 主表
三账（λ 网格）；产物 `research/SPIKE-S20-TURNOVER-PENALTY-LIVE1430/`

## 交付
四件套 + λ 相对对照表（Δret / Δ|MDD| / ΔCalmar / 分段 / skip）。
```

## 2. 实现要点

- **唯一改动**：填席 `score = sharpe20 − λ × to_norm`；λ ∈ {0, 0.15, 0.25}（**非**额外费率）。
- **trailing_4w_turnover**：信号周五 `d` 之前 4 个日历周五，`turnover_rate = vol_1430×price_1430/(aum_亿×1e8)` 的均值（缺则跳过；全无=0）。
- **to_norm**：当周 spike 池（有 sharpe20）内对 `trailing_4w_turnover` min-max 至 [0,1]。
- **邻档**：λ=0 plain face（对照）；λ=0.15 / 0.25 为网格邻档。
- **冻结**：B45 + spike_ft max5 + E0 + **TV25** + SHARPE20；Fri≥14:30 / 收盘；**0.2%RT**；**L≤1**。
- **延窗**：CLOUD-BATCH `research_cache`，日历至 **2026-10-23**（≥2026-10-23）。
- **隔离**：不写 strategy_exec / LIVE_OPS / 实盘池。

## 近似与覆盖

- 延窗：research_cache week/day/face/14:30；≤2026-10-09 沿用 face；其后研究周线 MA20 宽度
- qfq_1430 = price_1430 × (day qfq 收 / sina daily 收)；sina 作 bfq 代理
- 冲击分类：周线收盘替换为 qfq_1430 后因果 classify（Fri≥14:30 信号）
- Sharpe 窗截至信号日严格前一交易日
- 成交：周五收盘填仓 + TV25 + 0.2%RT；L≤1
- 填席：score=sharpe20−λ×to_norm；to_norm=池内min-max(trailing_4w_turnover)
- trailing_4w_turnover=mean_Fri(vol_1430×px_1430)/(aum_亿×1e8) 信号日前4周五
- 冻结 B45+spike_ft max5+S20+E0+TV25；**唯一改动 λ∈{0,0.15,0.25}**
- 只读 kit `data/cache_1430_snaps.json`；不写 strategy_exec / LIVE_OPS

| 覆盖 | 值 |
|---|---|
| 可投池（AUM≥2亿） | 324 |
| 日历周 | 349（2020-01-03→2026-10-23） |
| listed 行 14:30 非空率 | 100.0% |
| 成功映射 qfq_1430 | 45269 |
| 持仓差异周 λ=0.15 | 11/198 |
| 持仓差异周 λ=0.25 | 32/198 |

## 3. 主表（三账 · LIVE1430）

| book | λ | ret | maxDD | CAGR | Calmar | 2020–22 ret/DD/C | 2023–26 ret/DD/C | avgL | avgTO | 空仓周 |
|---:|---:|---:|---:|---:|---:|---|---|---:|---:|---:|
| LIVE1430-B45-S20-LAM00 **plain** | 0.00 | 158.3% | -15.9% | 15.0% | 0.94 | 29.3%/-14.9%/0.60 | 99.8%/-14.3%/1.39 | 0.83 | 0.154 | 150 |
| LIVE1430-B45-S20-LAM15 | 0.15 | 162.8% | -15.1% | 15.3% | 1.01 | 31.5%/-14.9%/0.64 | 99.8%/-14.3%/1.39 | 0.83 | 0.153 | 150 |
| LIVE1430-B45-S20-LAM25 | 0.25 | 161.8% | -15.1% | 15.2% | 1.01 | 31.0%/-14.9%/0.63 | 99.9%/-13.6%/1.47 | 0.82 | 0.155 | 150 |

### Δ vs plain（λ=0）

| λ | Δret vs λ=0 | Δ|MDD| | ΔCalmar | 盖住? | Calmar胜? | 2023–26 | 2020–22段 | 2023–26段 |
|---:|---:|---:|---:|---|---|---|---|---|
| 0.15 | +4.5pp | -0.8pp | +0.07 | 是 | 是 | 是 | 是 | 是 |
| 0.25 | +3.5pp | -0.8pp | +0.06 | 是 | 是 | 是 | 是 | 是 |

### 分段 · λ=0 对照

| 段 | ret | maxDD | Calmar |
|---|---:|---:|---:|
| 2020–22 | 29.3% | -14.9% | 0.60 |
| 2023–26 | 99.8% | -14.3% | 1.39 |

## 4. 一句结论（探索记账，不换冠）

**未证伪（记账）**：λ>0 相对 λ=0 Calmar 更优且探索尺子成立；组合 avgTO：λ=0 0.154 → 0.15 0.153 → 0.25 0.155。不换冠。

## 产物

- `run.py` / `criterion.md` / `REPORT.md` / `summary.json`
- `table.csv` / `metrics.csv` / `yearly.csv` / `equity.csv` / `nav_*.csv` / `equity_curve.png`

耗时约 8.2s。
