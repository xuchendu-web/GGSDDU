# RESEARCH-SKIP-MONTH-CSMOM-WEEKLY

研究池周频 **跳月截面动量（CSMOM）** vs 无跳月 / B45 face。`data/` 链至 `../dual_momentum_weekly/data`（周线 + B45 净值）。

```bash
cd research/RESEARCH-SKIP-MONTH-CSMOM-WEEKLY
pip install -r requirements.txt
python3 scripts/run_backtest.py
python3 -m pytest -q
```

四件套：`HYPOTHESIS.md` · `REPORT.md` · `results/*` · `skip_month_csmom/` + `tests/`。
