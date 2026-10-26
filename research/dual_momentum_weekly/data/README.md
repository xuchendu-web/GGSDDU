# 研究数据（只读）

- `universe.csv`：replace-only 436，评分用静态 AUM；回测筛 AUM≥2 亿。
- `weekly_panel.parquet`：由 `research_cache/week/*.json` 周五对齐建成（324 列）。
- `nav_LIVE1430-B45-S20.csv`：B45 face 延窗净值，只读对照。

重建：`scripts/build_panel.py`。不要写入 LIVE 目录。
