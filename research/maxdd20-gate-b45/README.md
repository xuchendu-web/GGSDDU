# MAXDD20-GATE-B45

研究池机械批：B45+S20 face 上叠加 **周频 −20% 硬闸**（次周空仓、−18% 恢复）。

| 文件 | 说明 |
|---|---|
| `criterion.md` | 准则原文 |
| `run.py` | 复现脚本（依赖 `research/cloud_batch/` 数据与引擎） |
| `REPORT.md` | 四件套汇总（准则→实现→主表→结论） |
| `table.csv` / `summary.json` | 主表与元数据 |
| `neighbor_triggers.csv` | 触发阈 −22% / −18% 敏感性 |

```bash
python3 research/maxdd20-gate-b45/run.py
```
