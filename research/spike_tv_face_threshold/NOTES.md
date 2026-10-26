# NOTES — spike face TV 阈值邻档 vs 已知 TV25/TV33 记注

## 本包定位

- **研究 only**：机械对照 **TV22 / TV28 / TV33** vs **TV25**，面层 **B45 + spike_ft max5 + S20**。
- **不换冠**：与 `tv22_summary.json` → `isolation`、CLOUD 刀 `SPIKE-S20-*` 红线一致。
- 引擎真值只读：`../spike_tv_neighbors/data/tv_neighbor_engine_full.csv`（全指标）+ `tv_neighbor_engine.csv`（含 TV33 行）。

## 与 `spike_tv_neighbors`（TV20/22/28/30 环）差异

| 项 | `spike_tv_neighbors` | 本包 `spike_tv_face_threshold` |
|----|----------------------|--------------------------------|
| H1 邻档 | σ\*∈{0.20, 0.22, 0.28, 0.30} | σ\*∈{**0.22, 0.28, 0.33**} |
| TV33 | H1 **集外旁注** | **纳入 H1**（对齐 E09 / TV-GRID 上档） |
| TV20/TV30 | H1 内（TV30 缺引擎行） | **本包不扫** |
| 机械结论（同窗） | H1 证伪：**仅 TV28** | H1 证伪：**TV28 + TV33**（TV22 仍不盖回撤） |

同窗数字一致；差异来自 **邻档集合定义**，不是重跑引擎。

## 已知 TV25 / TV33 记注（文档对照）

### TV25（基线）

- `LIVE1430-B45-S20`：σ\*=0.25，`tv22_summary` 与 SPIKE-SHARPE20-max5 **对齐**（\|Δret\|=0）。
- 面层默认锚：`breadth≥45% + spike_ft max5 + E0 + TV25 + S20`（各 CLOUD 刀「唯一改动」除外）。

### TV22（E08，降档）

- `tv22_summary.json` → `verdict`：**探索证伪方向（不换冠）**；Δret≈**−7.5pp**，Δ\|MDD\|≈**−1.2pp**（回撤变浅但收益掉更多，`delta_ret_covers_delta_abs_mdd`: false）。
- `strong_2023_26_ok`: true（后段未踏空，但 **不满足升格尺子**）。
- 本包 H1：**仍证伪降 σ\*** 叙事成立。

### TV33（E09，升档记正）

- `SPIKE-S20-EXTEND-REBASE-LIVE1430` 主表清单 **#3 TV33（E09 记正腿）**；假设：延窗后仍盖住相对 0.25 的回撤加深。
- `SPIKE-S20-TV-GRID-LIVE1430`：σ\*=0.33 为网格上档；**本窗未延至 ≥2026-10-23**。
- 同窗引擎（2026-09-24）：相对 TV25，TV33 **Δret≈+3.9pp**、**Δ\|MDD\|≈+1.2pp**，**盖回撤=Y**，**2023–26≥基线=Y** → 机械上与 E09「记正」一致；**不触发换冠**。

### TV28（上档邻点，非 E09 主叙事）

- 同窗：**Δret≈+1.0pp**、**Δ\|MDD\|≈+1.0pp**，盖回撤=Y → 邻域 **不平坦**（`spike_tv_neighbors` 已记）。
- Calmar 仍低于 TV25（0.705 vs 0.739）→ **记账不升格**。

## 实现 / 数据缺口（继承邻档包）

| 缺口 | 说明 |
|------|------|
| 延窗 2026-10-23 | EXTEND-REBASE / TV-GRID 要求；本包仍用 E08 引擎窗。 |
| `cash_week_pct` | 引擎 CSV 未出；换手用 `avg_turnover_1way`。 |
| breadth 14:30 | `tv22_summary` → breadth 沿用 face 收盘 MA20，非 14:30 重算。 |

## 用法

```bash
cd research/spike_tv_face_threshold
pip install -r requirements.txt
python run_tv_threshold_neighbors.py
```
