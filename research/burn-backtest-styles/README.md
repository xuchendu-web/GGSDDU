# Multi-style backtest ranking burn

Frozen **toy rule** on a fixed-seed synthetic panel. Nine engine implementations compute the same weekly cross-sectional ranks; `compare_rankings.py` writes pairwise **agreement matrices** (top-K and full rank list).

**Not live / 非实盘** — no broker, no production `strategy_exec`.

## Engines (≥8)

| ID | Script | Style |
|----|--------|--------|
| A `vector` | `style_a_vector.py` | Vectorized wide matrix |
| B `event` | `style_b_event.py` | Event-driven daily loop |
| C `pandas_resample` | `style_c_pandas.py` | Long-format groupby + resample |
| D `weekly_bar` | `style_d_weekly_bar.py` | Weekly bar outer loop |
| E `daily_resample` | `style_e_daily_resample.py` | Daily features → weekly resample |
| F `numba_loop` | `style_f_numba_loop.py` | Numba-ish numpy nested loops |
| G `pandas_rolling` | `style_g_pandas_rolling.py` | Pandas rolling + rank |
| H `polars` | `style_h_polars.py` | Polars (optional: `pip install polars`) |
| I `numexpr` | `style_i_numexpr.py` | numexpr vector comparisons |

Canonical spec: `shared/rule_spec.py` and `HYPOTHESIS.md`.

## Reproduce

```bash
cd research/burn-backtest-styles
pip install -r requirements.txt
# optional: pip install polars
python -m shared.generate_synthetic_panel
python scripts/compare_rankings.py
pytest tests/ -q
```

Outputs: `compare_report.md` (matrices + rank tables), `data/synthetic_panel.csv`.

## Toy rule (summary)

1. Universe: all symbols in `synthetic_panel.csv`.
2. Momentum: 60-day return on close.
3. Breadth gate: mean(`close > MA20`) ≥ 0.45 on rebalance day, else empty book.
4. Top K=3 by momentum; rebalance `W-FRI` last observation.
