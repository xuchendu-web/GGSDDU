# 双 TF 绝对趋势 + 相对 ROC · 研究 ETF 袖 vs B45 face

TiltFolio 式双周期动量（长 TF 绝对门、短 TF 相对排序）。**CODE+BACKTEST**。不开 LIVE。

## 复跑

```bash
python3 -m pip install -r research/dual_tf_abs_rel_weekly/requirements.txt
python3 -m pytest research/dual_tf_abs_rel_weekly/tests -q
python3 research/dual_tf_abs_rel_weekly/scripts/run_backtest.py
```

面板与 B45 净值只读 `research/dual_momentum_weekly/data/`（与 DUAL-MOM-WEEKLY 同窗）。

## 主簿

- `DT-A52s1-R26s1-N5`：A52s1 绝对门 + R26s1 相对前 5
- 邻档：`DT-A52s1-R52s1-N5`（退化为 PR#48 同 TF）、`R13`、`A26`、`N3/N8`、`XS-R26s1-N5`

## 红线

不导入 `strategy_exec` / `LIVE_OPS`。
