# RESEARCH-TSMOM-12M-LONGFLAT-WEEKLY

Moskowitz 风格 **时间序列动量**（long if 12m return > 0 else cash），研究 ETF 池，周频调仓。

```bash
pip install -r requirements.txt
python run_tsmom.py
```

依赖：`research/cloud_batch/CLOUD-BATCH-2026-10-26` 周频缓存 + `etf-correlation/data/research_pool_v2.csv`（由 `MF-HOLD-BGRID/engine/panel_build.py` 组 panel）。

**主刀**：`TSMOM-12M-max5`（正动量按 12m 收益取前 5 等权）。  
**旁注**：`TSMOM-12M-allpos`、6M/9M max5、`vol_scale_side_table.csv`（12% ann）。

对照：**B45+S20 研究面**（`data/b45_face_reference.csv`）。  
红线：仅 `research/`；不碰 LIVE/champion。
