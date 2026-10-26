# ATTRIBUTION · turnover-softcap

## 引擎与面

| 项 | 值 |
|----|-----|
| 针 SHA | `05f0f8a4f778fde886f3e7b2976646ff4b7d777b` |
| 面层 | B45 + spike_ft max5 + E0 + TV25 + SHARPE20-fill |
| 成交 | Fri LIVE≥14:30；0.2% RT；L≤1 |
| 样本 | 2020-01-03 → 2026-10-23 |
| FACE 锚 | 131.6% / −18.8% / Calmar 0.70（延窗 inventory） |

## 数据（未提交 kit）

- `research/cloud_batch/CLOUD-BATCH-2026-10-26/data/research_cache/`
- `holdings_ro2_extended.csv`（B45 宽度日历）
- `cache_1430_snaps.json`（spike 分类）
- `fri_1430_through_20261023.csv`

## 本刀唯一改动

路径约束：目标 max5 权重后的 **52 周滚动单边换手软帽**（T*∈{6,8,10}×/年），pro-rata 缩仓。

## 排除

- PR#77 `COST-TURNOVER-JOINT-B45`（RT×λ 填席联合）
- PR#55 turnover-penalty（λ 排序扣分）
- LIVE_OPS / champion_mast / strategy_exec

## 运行

```bash
python research/turnover-softcap/run.py
```

elapsed 6s
