# 实现缺口（TV 邻档机械扫）

## 已有

- `data/table_bead_baseline.csv`：自 uploads 复制的同窗主表（含 **LIVE1430-B45-S20** = TV25 基线）。
- `data/summary_reference.json`：NOB 批 `summary_e47d.json`（引擎口径、样本窗、近似说明；**非 TV 扫结果**）。
- `run_tv_neighbor_scan.py`：读基线 → 合并邻档结果 CSV（若存在）或输出 **placeholder** → 写 `main_table.md` + `scan_result.json`。
- `HYPOTHESIS.md`：H1 + 证伪规则。

## 缺失（真扫必补）

| 缺口 | 说明 |
|------|------|
| SPIKE 研究引擎 | uploads 指向 `/workspace/strategy-weekly/...`；**本 GGSDDU 仓无 strategy 代码**。 |
| 14:30 / qfq / face | `fri_1430_through_20261023.csv`、week-day panel、B45 breadth 链未挂载。 |
| TV 暴露模块 | 需在引擎内仅改 σ\*∈{0.20,0.22,0.25,0.28,0.30}，冻结 E0 + S20 + max5。 |
| 邻档净值 / 持仓 | 无 `nav_tv20.csv` 等；放入 `data/tv_neighbor_engine.csv` 后重跑脚本即得 **real** 主表。 |
| 换手 | 基线 uploads 无周换手列；NOB summary 有 `n_trades=268`（B45-S20），邻档需引擎输出 `turnover` 或等价。 |

## 接引擎后操作

```bash
python3 research/spike_tv_neighbors/run_tv_neighbor_scan.py \
  --engine-csv research/spike_tv_neighbors/data/tv_neighbor_engine.csv
```

`tv_neighbor_engine.csv` 列：`book,sigma,ret,maxDD,CAGR,Calmar,2020-22_ret,2020-22_DD,2020-22_Calmar,2023-26_ret,2023-26_DD,2023-26_Calmar,avgL,cash_week_pct,turnover,data_source`

## 红线（已遵守）

- 未改生产 / 实盘配置；未提交密钥。
- 本批 uploads 为 MOM121 准则 + NOB 对照表，**非 TV 邻档回测输出**。
