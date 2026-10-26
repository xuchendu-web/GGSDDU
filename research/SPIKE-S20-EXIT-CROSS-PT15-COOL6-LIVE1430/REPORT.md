# REPORT · SPIKE-S20-EXIT-CROSS-PT15-COOL6-LIVE1430

## 1. 准则

```
# SPIKE-S20-EXIT-CROSS-PT15-COOL6-LIVE1430

- 面层冻结：breadth≥45% + spike_ft max5 + E0 + TV25 + SHARPE20；Fri≥14:30/收盘；0.2%RT；L≤1；研究池
- 唯一改动：同时启用 profit-take +15% 与 loss-cool −6%（上周组合收益≤−6% → 本周空仓）
- 证伪：交叉相对 face 无法在 Calmar 上胜出且 Δret 盖住 Δ|MDD|；或 2023–26 踏空；或邻档不稳
- 先验：PR#35 止盈单腿 falsify；PR#37 冷静单腿 falsify；本刀测交叉协同
```

## 2. 实现要点

- **交叉**：simulate 内 profit-take；冷静为 signal 周持仓 overlay（触发周收益=同路径无冷静 NAV 的周收益）。
- **主细胞**：PT15 × COOL−6；归因复跑 PT-only / COOL-only；2×2 显式记账。
- **冻结 face**；研究池；不写 strategy_exec / LIVE_OPS / champion。

## 3. 主表

| book | PT | COOL | ret | maxDD | Calmar | 2020–22 / 2023–26 ret | pt_exits | cool_w |
|---|---|---|---:|---:|---:|---|---:|---:|
| LIVE1430-FACE | off | off | 158.3% | -15.9% | 0.94 | 29.3%/99.8% | 0 | 0 |
| LIVE1430-PT15-only | PT15 | off | 141.2% | -16.1% | 0.86 | 23.8%/94.9% | 39 | 0 |
| LIVE1430-COOL6-only | off | COOL6 | 150.4% | -15.9% | 0.91 | 25.3%/99.8% | 0 | 1 |
| LIVE1430-CROSS-PT15-COOL6 | PT15 | COOL6 | 133.4% | -16.1% | 0.82 | 19.8%/94.9% | 39 | 1 |

### CROSS vs FACE

| 指标 | face | CROSS | Δ |
|---|---:|---:|---:|
| Calmar | 0.94 | 0.82 | -0.12 |
| ret | 158.3% | 133.4% | -24.9pp |
| |MDD| | 15.9% | 16.1% | +0.3pp |
| Δret 盖住 Δ|MDD| | — | — | 否 |
| 2023–26 ≥90% face | — | 94.9% | 是 |

## 4. 2×2（PT15 on/off × COOL−6 on/off）

| 2×2 cell | book | Δret vs face | Δ|MDD| | Calmar beat |
|---|---|---:|---:|---|
| grid_PT0_COOL0 | LIVE1430-FACE | +0.0pp | +0.0pp | 否 |
| grid_PT1_COOL0 | LIVE1430-PT15-only | -17.1pp | +0.3pp | 否 |
| grid_PT0_COOL1 | LIVE1430-COOL6-only | -7.9pp | +0.0pp | 否 |
| grid_PT1_COOL1 | LIVE1430-CROSS-PT15-COOL6 | -24.9pp | +0.3pp | 否 |

## 5. 邻档旁注

### PT 邻档（无冷静）
| label | ret | maxDD | Calmar | pt_exits |
|---|---:|---:|---:|---:|
| PT10 | 131.9% | -15.9% | 0.83 | 68 |
| PT20 | 134.6% | -16.1% | 0.83 | 27 |
### COOL 邻档（无止盈）
| label | ret | maxDD | Calmar | cool_weeks |
|---|---:|---:|---:|---:|
| COOL4 | 139.9% | -20.9% | 0.66 | 6 |
| COOL8 | 150.4% | -15.9% | 0.91 | 1 |

## 6. 一句结论

**交叉退出证伪（不换冠）**：face Calmar=0.94； CROSS PT15×COOL6 Calmar=0.82 Δret=-24.9pp Δ|MDD|=+0.3pp 后段OK；邻档不稳。 单腿 PT15 / COOL6 此前已 falsify，交叉无新增升格。

产物：`summary.json` · `table.csv` · `equity_curve.png` · `run.py`（耗时 9.9s）
