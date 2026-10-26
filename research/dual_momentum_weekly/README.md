# 周频双动量 · 研究 ETF 池 vs B45 face

研究刀。**CODE+BACKTEST**。不开 LIVE。

## 复跑

```bash
python3 -m pip install -r research/dual_momentum_weekly/requirements.txt
# 从 CLOUD-BATCH research_cache/week 建面板（只需做一次）
python3 research/dual_momentum_weekly/scripts/build_panel.py \
  --week-dir /path/to/research_cache/week \
  --universe /path/to/universe_replace_only_436.csv \
  --b45-nav /path/to/nav_LIVE1430-B45-S20.csv
python3 -m pytest research/dual_momentum_weekly/tests -q
python3 research/dual_momentum_weekly/scripts/run_backtest.py
```

产物在 `results/`：`fourpack.png`、`metrics.csv`、`nav.csv`、`yearly.csv`、`holdings.csv`、`summary.json`、`REPORT.md`。

## 主簿

- 名称：`ABS-L52s1-N5`
- 绝对门：52 周跳 1 周收益 > 0
- 相对：门内取前 5 等权
- 邻档：L26 / L78、N3 / N8、无绝对门 XS 消融、池等权

## 红线

不导入 `strategy_exec` / `LIVE_OPS`。对照 B45 face 只读其研究净值。
