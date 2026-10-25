# Burn job #1 — multi-style backtest ranking

## Hypothesis

Three engine implementations of the **same frozen toy rule** on the **same fixed-seed synthetic panel** will produce **identical weekly cross-sectional rankings** (and therefore identical top-K selections):

| Style | Engine |
|-------|--------|
| A | Vectorized weekly on wide matrix |
| B | Event-driven daily loop (rebalance only on `W-FRI` anchors) |
| C | Long-format pandas `groupby` + `resample` |

### Toy rule (not production `strategy_exec`)

1. **Universe:** all symbols in `synthetic_panel.csv`.
2. **Momentum:** `R60d = close / close[t-60] - 1` (~12w stub).
3. **Breadth gate (stub):** `breadth = mean(close > MA20)` on rebalance day; trade only if `breadth >= 0.45`, else empty book.
4. **Selection:** sort by momentum descending; **top K=3**.
5. **Rebalance:** last business day in each pandas `W-FRI` week.

## Fail criteria

| Outcome | Verdict |
|---------|---------|
| All pairwise **full rank list** weekly match rate = 100% | Hypothesis **holds** for this panel + spec |
| Any pairwise top-K or rank list mismatch | Hypothesis **fails** for parity; document deltas in `compare_report.md`; keep scripts as **templates only** |
| Script crash, nondeterministic output on rerun with same CSV | Implementation **broken** (fix before claiming template status) |

## Explicit non-goals

- No live broker, no real ETF panel download required.
- Do **not** modify production `strategy_exec` or claim live-engine equivalence.

## Reproduce

```bash
cd research/burn-backtest-styles
python -m shared.generate_synthetic_panel
python scripts/compare_rankings.py
pytest tests/ -q
```
