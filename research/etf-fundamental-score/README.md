# ETF Fundamental Score (research)

Transparent multi-factor **screening** score for a research ETF universe.  
**Not** a live trading system and **not** validated alpha — use for reproducible pool filtering only.  
`research_pool_only` is hard-guarded in config loading (no LIVE升格).

## Layout

```
research/etf-fundamental-score/
├── config.yaml              # weights, overlays, missing policies (v2.0)
├── docs/SCORING.md          # definitions, formulas, failure modes
├── fixtures/universe_sample.csv
├── etf_fundamental_score/
│   ├── score.py             # ScoreEngine, composite, ranking
│   ├── batch.py             # multi-CSV batch scorer
│   ├── sector_overlay.py    # per-category weights & params
│   ├── cli.py
│   ├── factors/             # one module per factor
│   └── adapters/            # FixtureCsvAdapter + ETFDataAdapter ABC
└── tests/
```

## Quick start

```bash
cd research/etf-fundamental-score
python -m pip install -e ".[dev]"
etf-score
etf-score batch -m fixtures/batch_manifest.csv -o batch_scores/
pytest -q
```

Default paths: input `fixtures/universe_sample.csv`, config `config.yaml`, output `./scores.csv`.

## Factors (v0.2)

| Key | Input fields | Idea |
|-----|--------------|------|
| aum | `aum_usd` | Larger / more liquid |
| fee | `expense_ratio` | Cheaper |
| tracking_error | `tracking_error_bps` | Tighter benchmark tracking |
| concentration | `top10_holdings_weight` | Less single-name risk |
| valuation | `holdings_median_pe` | Cheaper stub |
| flow | `net_flow_30d_usd` / AUM | Recent inflows |
| premium | `premium_bps` | Lower premium vs fair value |
| liquidity | `avg_daily_volume_usd` / AUM | Higher ADV/AUM |
| dividend_yield | `dividend_yield` | Higher income yield |

**Sector overlays** adjust weights and factor bands per `category` (see `config.yaml` and [docs/SCORING.md](docs/SCORING.md)).

**Missing data:** `reweight` | `zero` | `neutral`, plus `min_factor_coverage` and `required_factors`.

## Extending data

Implement `etf_fundamental_score.adapters.base.ETFDataAdapter` and pass rows into `ScoreEngine.score_universe()`. Keep the same field names or map in `enrich()`.

Paid APIs (zsmcp, cjpy, etc.) are **not** required for this package; connect them in your adapter when available.

## Hypothesis (burn job #3)

A documented factor → weight pipeline can screen a frozen research ETF list reproducibly.  
**Failure criterion:** unclear factor defs or undocumented weights → treat run as incomplete.

## License / use

Internal research tooling. Do not present composite ranks as investment advice or live performance.
