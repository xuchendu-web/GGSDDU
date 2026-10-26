# ATTRIBUTION

## 数据

| 来源 | 用途 |
|------|------|
| `etf-correlation/data/research_pool_v2.csv` | 海外权益宇宙筛选（`l0=海外权益`, AUM≥2亿） |
| `research/cloud_batch/CLOUD-BATCH-2026-10-26/data/research_cache/day/*.json` | QDII ETF 日收盘 |
| `research/dual_momentum_weekly/data/weekly_panel.parquet` | 周五调仓日历栅格 |
| `research/overseas-volscaled-tsmom/vs_tsmom_lib.py` | 价格加载、`OX` 集合校验 |

未使用 A 股 champion 净值、未使用 breadth45 门控。

## 引擎复用

- 回测骨架：`research/dual_momentum_weekly` / `dual_tf_abs_rel_weekly`（周频换手成本、L≤1 现金残差）
- 海外 kit 路径：`vs_tsmom_lib.load_daily_close`

## 产出

- `scripts/build_panel.py` → `data/weekly_panel.parquet`
- `scripts/run_backtest.py` → `results/*`
- 生成时间：回测运行于 Cloud Agent 环境（见 `results/summary.json`）

## 显式跳过

- PR#84 VS-TSMOM 多袖（已证伪）
- PR#63 Dual-TF A 股 face（本卡仅 QDII 独立书）
