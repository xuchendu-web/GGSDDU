# 实现缺口（TV 邻档机械扫）

## 已闭合

| 项 | 路径 |
|----|------|
| TV20/22/25/28 引擎主表 | `data/tv_neighbor_engine_full.csv`（uploads `tv22_table.csv`） |
| TV33 + 紧凑列 | `data/tv_neighbor_engine.csv` |
| 引擎元数据 / pick_diffs | `data/tv22_summary.json` |
| 机械 H1 判定 | `run_tv_neighbor_scan.py` → `scan_result.json` |

引擎口径（摘自 summary）：持仓与 B45+S20 相同，TV 只缩放 L；σ* 唯一改动；样本 **2020-01-03→2026-09-24**（14:30 面板至 2026-09-25，**未延至 2026-10-23**）。

## 仍缺

| 缺口 | 说明 |
|------|------|
| **TV30（σ*=0.30）** | H1 四邻档之一，当前引擎包无行；需补跑后写入 `tv_neighbor_engine*.csv` 再执行脚本。 |
| 延窗至 2026-10-23 | 与 NOB 批同窗对齐需更新 14:30 面板后重算 TV 邻档。 |
| `cash_week_pct` / `risk_on_week_pct` | 全表未在 TV 引擎 CSV 中输出；主表 turnover 用 `avg_turnover_1way`。 |

## 用法

```bash
pip install -r requirements.txt
python run_tv_neighbor_scan.py
# 或显式：
python run_tv_neighbor_scan.py \
  --engine-csv data/tv_neighbor_engine.csv \
  --engine-full-csv data/tv_neighbor_engine_full.csv
```

## 红线（已遵守）

- 未改生产 / 实盘配置；未提交密钥。
- 指标均来自 uploads 引擎 CSV/JSON，脚本不插值、不伪造。
