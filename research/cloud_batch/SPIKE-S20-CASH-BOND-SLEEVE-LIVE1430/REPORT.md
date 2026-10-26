# REPORT · SPIKE-S20-CASH-BOND-SLEEVE-LIVE1430（现金/债空槽停放邻档）

## 1. 准则原文

```
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
```

## 2. 实现要点

- **B45 FACE 基线**：`LIVE1430-B45-S20-max5` 复用 BTHETA 同窗持仓 + 原版 TV（空仓周 = 纯现金）。
- **邻档唯一改动**：max5 **槽位** 1/5；未满槽名义停放 **511010 / 511260 / cash stub(0)**；权益腿仍 spike+S20+E0+TV25。
- **空周** 149（42.9%）· **部分填席** 21（6.1%）。
- FACE 直接复用 BTHETA 同窗 `nav_LIVE1430-B45-S20-max5.csv`（与 B45 face 一致）。
- **红线**：研究 only；**不启 LIVE 债袖**；**不换冠**；不写 strategy_exec / LIVE_OPS。

## 债券日线

- 来源：`bond_daily/*.csv`（mf-hold 日线 × zsmcp `qt_dailyquote` 2024-02-26 锚定缩放）；上市前用常数日漂移外推（见 `extend_bond_backward`）。
- 续跑：可用 zsmcp 全历史覆盖 `bond_daily/` 后重跑。

## 3. 主表（vs B45 FACE）

| book | ret | maxDD | CAGR | Calmar | 2020–22 | 2023–26 | avgL | 均停放占比 |
|---|---:|---:|---:|---:|---|---|---:|---:|
| LIVE1430-B45-S20-max5 **FACE** | 131.9% | -18.8% | 13.2% | 0.70 | 19.0%/-16.0%/0.37 | 94.8%/-13.8%/1.39 | 0.84 | 0.0% |
| LIVE1430-B45-SLOT-CASH 邻档 | 72.4% | -20.9% | 8.3% | 0.40 | 16.5%/-16.0%/0.33 | 48.0%/-20.9%/0.52 | 0.96 | 93.3% |
| LIVE1430-B45-SLOT-511010 邻档 | 90.7% | -20.8% | 10.0% | 0.48 | 23.2%/-15.7%/0.46 | 54.9%/-20.8%/0.59 | 0.97 | 93.3% |
| LIVE1430-B45-SLOT-511260 邻档 | 93.2% | -20.2% | 10.2% | 0.50 | 23.2%/-15.7%/0.46 | 56.9%/-20.2%/0.62 | 0.97 | 93.3% |

### Δ vs FACE（pp）

| 邻档 | Δret | ΔMDD | ΔabsMDD | ΔCalmar |
|---|---:|---:|---:|---:|
| CASH slot | -59.4 | -2.1 | +2.1 | -0.30 |
| 511010 | -41.2 | -2.0 | +2.0 | -0.22 |
| 511260 | -38.6 | -1.4 | +1.4 | -0.20 |

## 4. 一句证伪或通过

**证伪「空槽债停放优于 FACE」（不换冠、不启 LIVE 债袖）**：债邻档均未做到 Δret 盖住 Δ|MDD|；最优邻档 511260 Calmar 未高于 FACE；后段 2023–26 踏空。

耗时 1.3s。日历终点 **2026-10-16**。
