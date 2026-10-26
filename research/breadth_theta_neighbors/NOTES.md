# 实现说明（breadth θ 邻档）

## 已闭合

| 项 | 路径 |
|----|------|
| B40/B45/B50/B55 引擎行 | `data/btheta_neighbor_engine.csv` |
| 历年 Δ(B50−B45) | `data/yearly_b40_b50.csv` |
| turnover 旁证 | `data/summary_reference.json` |
| 机械主表 + 邻域稳定 | `run_btheta_neighbor_scan.py` → `main_table.md` / `scan_result.json` |

引擎来源：`origin/cursor/btheta-grid-live1430-87d9` 批次 `SPIKE-S20-BTHETA-GRID-LIVE1430`（Cloud 已跑四档；本仓只消费 B40/B45/B50 邻档 + B55 旁注）。

## 红线

- **不换冠**；不改生产 / 实盘配置。
- 指标来自引擎 CSV，脚本不插值、不伪造。

## 与 TV 邻档扫的关系

| | TV 邻档 (`spike_tv_neighbors`) | 本批 |
|--|-------------------------------|------|
| 冻结 | B45 + S20 + max5 + TV | spike + S20 + **TV25** + max5 |
| 扫描轴 | σ\* @ TV25 | **θ** @ TV25 |
| 邻档 | TV20/22/28/30 | **B40 / B50**（中心 B45） |
