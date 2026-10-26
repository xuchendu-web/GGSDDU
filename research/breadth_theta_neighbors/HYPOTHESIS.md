# H1：breadth θ 邻档（B40 / B45 / B50）

## 冻结面层（本批不改）

| 维度 | 设定 |
|------|------|
| 池 / 填席 | `spike_ft` **max5** + **SHARPE20（S20）** |
| 出场 | E0 |
| 总暴露 | **TV25**（σ\*=0.25） |
| 信号 / 成交 | LIVE1430（Fri ≥14:30 → 当日收盘） |
| 成本 / 杠杆 | 0.2% RT；**L≤1** |
| 样本窗 | **2020-01-03 → 2026-10-23**（`SPIKE-S20-BTHETA-GRID-LIVE1430` 延窗） |
| 研究池 | ≠ 实盘池 |

**唯一变动**：宽基 MA20 宽度门槛 **θ**（`risk_on = (b ≥ θ)`）。基线 **B45（θ=0.45）**；邻档 **B40 / B50**。

## H1（开跑前写死）

在冻结 **spike+S20+TV25 max5** 下，**B45 为中心**的 θ 邻档应呈现 **可解释的单调平台**（θ↑ → 全样本 ret/Calmar 不乱跳），且 **B40 不应机械升格 B45**；**B50 相对 B45** 用同一尺子检验 E01 延续（收益增量是否盖住回撤恶化、2023–26 是否踏空）。

## 机械规则

相对同窗 **B45+S20+TV25-max5**：

1. **升格候选**：邻档同时满足 **Δret ≥ Δ|MDD|**（比例差，与 `run_btheta_neighbor_scan.py` 一致）且 **2023–26 累计收益 ≥ 基线**。
2. **邻域稳定**：在 **B40→B45→B50** 上，全样本 **ret** 与 **Calmar** 均单调非降；Calmar 峰值落在 **θ=0.50**；历年 **Δ(B50−B45)** 符号翻转仅作旁注（不单独否决）。

## 跳过（本批不跑）

- 实盘池、`strategy_exec` / **LIVE_OPS** / **冠军主钉**
- θ 插值（0.48 / 0.52）或换 TV / max seat 网格
- NOBREADTH / RET12 等同构重派

## 数据

- 引擎真值：`data/btheta_neighbor_engine.csv`（摘自 `SPIKE-S20-BTHETA-GRID-LIVE1430/metrics.csv`）
- 历年：`data/yearly_b40_b50.csv`
- 主表 / 判定：`main_table.md`、`scan_result.json`（`python run_btheta_neighbor_scan.py`）
