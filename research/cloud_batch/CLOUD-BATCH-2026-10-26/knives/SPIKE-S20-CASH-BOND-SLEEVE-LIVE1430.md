# SPIKE-S20-CASH-BOND-SLEEVE-LIVE1430

- 编号 / 日期 / 来源：SPIKE-S20-CASH-BOND-SLEEVE-LIVE1430 / 2026-10-26 / Cloud research
- 批次 ID：CLOUD-CASH-BOND-SLEEVE
- 性质：B45+S20 **空槽停放邻档**（研究 only）

## 准则原文
相对 **B45+S20-LIVE1430 FACE**（同窗 spike_ft max5 + S20 + E0 + TV25；空仓周=现金），**只改未满 max5 槽位的停放工具**：

| book | 空槽停放 |
|---|---|
| **B45 FACE** | 基线（无槽位模型；与 BTHETA/B45 同窗） |
| **B45-SLOT-CASH** | 纯 cash stub（0 收益） |
| **B45-SLOT-511010** | 国泰上证 5 年期国债 ETF |
| **B45-SLOT-511260** | 上证 10 年期国债 ETF |

槽位：每席 1/5 NAV；已占席权益腿冻结；TV25 仍只缩放权益腿。

## 改动点（唯一）
FACE → 槽位模型 + 邻档停放标的；**不**改 breadth θ、不叠 HYST/B50、不启 LIVE 固收+。

## 假设
空槽改持短债可抬全样本 Calmar，且 Δret 盖住略深的 Δ|MDD|；511010 vs 511260 差异可辨。

## 证伪
相对 FACE：债邻档 Δret 未盖住 Δ|MDD|；或 Calmar 不优于 FACE；或 2023–26 踏空 → 证伪「空槽债停放」；**不换冠、不写 LIVE 债袖**。

## 主表
四本书 + Δ vs FACE；产物 `research/cloud_batch/SPIKE-S20-CASH-BOND-SLEEVE-LIVE1430/`

## 共用冻结
- Fri ≥14:30 / 收盘；0.2%RT；L≤1；研究池
- **不换冠**；不碰 strategy_exec / LIVE_OPS / 冠军主钉 / 固收+ / 红利袖
- 探索尺子：Δret 须盖住 Δ|MDD|；报 2020–22 / 2023–26

## 交付
四件套（REPORT / summary.json / table.csv / equity_curve.png + nav）。
