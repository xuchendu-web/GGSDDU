# strategy-weekly（研究池）

仅用于 **研究池** 周报实验；不包含 LIVE、champion 或 `strategy_exec`。

## COMPRESSION-BREAKOUT-LIVE1430

四件套：FACE（SPIKE-S20 B45）+ 压缩突破邻档 N∈{4,6,8}。

```bash
pip install -r strategy-weekly/requirements-research.txt
python strategy-weekly/COMPRESSION-BREAKOUT-LIVE1430/run.py
```

可选：设置 `RESEARCH_CACHE` 指向既有 TiltFolio `research_cache`（含 `daily/*.parquet`）；未设置时首次运行用 akshare 拉取研究池 ETF 日线并写入 `COMPRESSION-BREAKOUT-LIVE1430/data/research_cache/`。
