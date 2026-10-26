# REPORT · SPIKE-S20-UNIVERSE-COMMODITY-BOND-CASH-LIVE1430

**性质**：研究 only；**非 LIVE**；不换冠；不写 strategy_exec / LIVE_OPS / champion。  
PR#46 已证伪「空槽债停放换冠」——本批为 **袖套-as-book** 归因（整簿只在该类标的内排序）。

## 面层（各切片独立，不混类 rank）

spike_ft max5 · SHARPE20 · E0 · Fri≥14:30/收盘 · 0.2% RT · L≤1 · TV25。  
Breadth：池子 ≥20 才沿用 face B45 `risk_on`；否则 **NA**（切片内恒 risk_on，仅靠 falsify + 相对 Sharpe）。

| 簿 | 池定义 |
|---|---|
| **COMMODITY** | `research_pool_v2` · `l0=商品`（AUM≥2 与 uni 交集） |
| **BOND/CASH** | `bond_cash_sleeve_labels.csv` · `l0=固收现金`（国债+货币类） |
| **REF** | 全池 A 股研究 face · LIVE1430-B45-S20（extend 同窗） |

窗：2020-01-03 → 2026-10-23。

## 主表

| book | n | breadth | ret | maxDD | Calmar | avgTO | cash周% |
|---|---:|---|---:|---:|---:|---:|---:|
| RES-B45-S20-COMMODITY | 5 | NA_thin_slice | 46.1% | -25.1% | 0.23 | 0.072 | 58.0% |
| RES-B45-S20-BOND-CASH | 2 | NA_thin_slice | 0.1% | -2.3% | 0.01 | 0.039 | 78.7% |
| RES-B45-S20-BARBELL-50-50 | — | synthetic | 22.2% | -13.2% | 0.23 | — | — |
| REF B45 face | 324 | face | 131.6% | -18.8% | 0.70 | — | 43.1% |

## 动量适配性（Calmar / 换手 / 分段）

- **商品袖**：弱/不适配动量（Calmar 相对 face 过低） — RES-B45-S20-COMMODITY: 5 distinct ETFs ever held; avg concurrent slots ~0.69; top families by slot-weeks: 黄金现货(92), 期货·农产品(56), 期货·有色(53)
- **固收现金袖**：弱/不适配动量（Calmar 相对 face 过低） — RES-B45-S20-BOND-CASH: 2 distinct ETFs ever held; avg concurrent slots ~0.32; top families by slot-weeks: 国债·5年(67), 国债·10年(43)
- **50/50 杠铃（侧边）**：50/50 barbell; rebalance on face Fridays (calendar)；全样本 Calmar 0.23（非独立 spike 簿）。

分段见 `yearly.csv`（2020–22 / 2023–26 可自算）。

## 红线

不得将商品与债/货币标的在同一簿内混合排序；不得据此启用 LIVE 债袖或替换冠军。

耗时约 5.0s。
