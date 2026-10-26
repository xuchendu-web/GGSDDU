# REBAND 邻域稳健 · 判卷准则（研究-only）

## 面（FACE）
- breadth≥45% MA20（`holdings_ro2_extended` risk_on）+ spike_ft max5 + E0 + TV25 L≤1 + **SHARPE20** 填席
- Fri≥14:30 信号 / 当日收盘成交；**0.2% RT**；样本 `2020-01-03 → ≥2026-10-23`

## 唯一扫参轴
- **参数名**：`reband_tol`（组合权重带宽，绝对权重差，非百分点）
- **E30 记正定义**（`JUDGING_LOG` / PEER E30）：`|Δw| ≤ reband_tol` 时不做等权再平衡；**开关翻转**（breadth risk_on 当周相对上周变化）除外，仍强制调仓
- **FACE**：`reband_tol = 0`（每周持有段内强制等权，等同原 B45+S20 引擎）
- **邻档**：3% / 5% / 10%（旁注 7%）

## 四件套
`criterion.md` · `run_reband_neighbors.py` · `REPORT.md` · `table.csv` + `summary.json` + `nav_*.csv`

## 探索尺子（相对 FACE）
- **记正**：某邻档 **Calmar 明确高于 FACE**，且 **2023–26 分段收益不弱于 FACE**（≥ FACE − 0.5pp 绝对收益）
- **证伪**：邻档 Calmar 低于 FACE，或后段明显塌（2023–26 收益 < FACE − 2pp）
- **旁注**：介于两者之间，或仅全样本盖住但后段未稳
- **不换冠**；不碰 LIVE_OPS / strategy_exec / 实盘

## 引擎来源
- 持仓仿真：`research/cloud_batch/SPIKE-S20-EXTEND-REBASE-LIVE1430/run.py` → 固定 `LIVE1430-B45-S20` 持仓轨
- TV 执行：`run_live_tv_reband(reband_tol)`，参数即 E30 **|Δw|** 带宽（绝对权重）
- 原 PEER 产物 `spike_mom_rank/SPIKE-S20-REBAND5-LIVE1430/` **源码未入库**；旋钮定义以 `research/research-kb/JUDGING_LOG.md` 为准
- 数据包：`research/cloud_batch/CLOUD-BATCH-2026-10-26/data/`（延窗 ≥2026-10-23）
