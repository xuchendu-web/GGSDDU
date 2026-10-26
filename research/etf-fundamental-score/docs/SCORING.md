# ETF Fundamental Composite Scoring (Research)

**Purpose:** Transparent, reproducible **screening** of a research ETF universe.  
**Non-goals:** Live alpha claims, production trading signals, or “实盘升格”. Outputs are ranks for human review.

`research_pool_only: true` is enforced in `load_config()` — this package cannot be switched into a LIVE / production trading mode.

## Pipeline

```mermaid
flowchart LR
  A[Universe CSV / Adapter] --> B[Normalize rows]
  B --> C[Sector overlay weights + params]
  C --> D[Factor modules 0-100]
  D --> E[Weighted composite + missing policy]
  E --> F[scores.csv + rank / rank_within_category]
```

1. Load universe via `FixtureCsvAdapter` (or future `ETFDataAdapter` implementations).
2. Optional **sector overlay** adjusts factor weights and bands per `category` (see below).
3. Each factor maps raw fields → **score ∈ [0, 100]** (higher = more attractive on that dimension).
4. Composite applies **missing-factor policy** (`reweight`, `zero`, or `neutral`) and optional `min_factor_coverage` / `required_factors`.
5. Cross-sectional **global rank**; optional **within-category rank** when `ranking.within_category: true`.

## Weights (default `config.yaml` v2.0)

| Factor | Weight | Rationale (research stub) |
|--------|--------|---------------------------|
| `aum` | 0.15 | Scale / liquidity; log-AUM band + optional percentile |
| `fee` | 0.15 | Fee drag; lower ER preferred |
| `tracking_error` | 0.15 | Benchmark fidelity; lower TE preferred |
| `concentration` | 0.12 | Diversification; lower top-10 weight preferred |
| `valuation` | 0.12 | Cheapness stub; lower median P/E preferred |
| `flow` | 0.08 | Short-term demand; higher flow/AUM preferred |
| `premium` | 0.08 | Execution cost; lower premium vs fair value preferred |
| `liquidity` | 0.07 | ADV/AUM; higher on-screen liquidity preferred |
| `dividend_yield` | 0.08 | Income sleeve; higher trailing yield preferred |

Weights **must sum to 1.0**. Change only with documented rationale in git / research notes.

## Sector overlays

Configured under `sector_overlays`:

- **`category_field`**: CSV column (default `category`).
- **`weight_multipliers`**: per-category multipliers on base weights, then **renormalized** to sum to 1.
- **`factor_params`**: per-category overrides merged into factor bands (e.g. wider TE for `qdii_us`, down-weight valuation for `commodity`).

Use overlays to avoid comparing QDII premium/TE bands to onshore broad equity without adjustment.

## Missing-data policies

| Policy | Behavior |
|--------|----------|
| `reweight` (default) | Missing factors omitted from denominator; flag `reweighted_missing` |
| `zero` | Missing factors contribute score 0 with full weight |
| `neutral` | Missing factors contribute `neutral_missing_score` (default 50) with full weight |

Additional guards:

- **`min_factor_coverage`**: fraction of base weight that must have non-null scores; else composite 0 and `insufficient_factor_coverage`.
- **`required_factors`**: list of factor keys; if any missing → composite 0 and `failed_required_factors`.

## Factor definitions & formulas

### 1. AUM (`aum_usd`)

- **Score:** log band + optional 50/50 blend with cross-sectional AUM percentile.
- **Params:** `min_log_aum`, `max_log_aum`.

### 2. Fee (`expense_ratio`)

- Linear map; lower ER is better.

### 3. Tracking error (`tracking_error_bps`)

- Linear map in bps; lower TE is better.

### 4. Concentration (`top10_holdings_weight`)

- Lower top-10 weight is better; HHI fallback unchanged.

### 5. Valuation (`holdings_median_pe`)

- Lower P/E is better; PE ≤ 0 → missing.

### 6. Flow (`net_flow_30d_usd`, `aum_usd`)

- Flow/AUM ratio; higher is better.

### 7. Premium (`premium_bps`)

- **Raw:** Premium vs IOPV / fair value in **basis points** (fixture field).
- **Score:** Lower premium is better between `best_premium_bps` and `worst_premium_bps`.

### 8. Liquidity (`avg_daily_volume_usd`, `aum_usd`)

- **Raw:** `adv_to_aum = avg_daily_volume_usd / aum_usd` (or precomputed `adv_to_aum`).
- **Score:** Higher ratio is better.

### 9. Dividend yield (`dividend_yield`)

- **Raw:** Trailing dividend yield as decimal (0.03 = 3%).
- **Score:** Higher yield is better between `worst_yield` and `best_yield`.

## Composite

```
composite = Σ wᵢ sᵢ / Σ wᵢ   (reweight mode, for factors with non-null sᵢ)
```

## Batch scoring

```bash
etf-score batch -m fixtures/batch_manifest.csv -o batch_scores/
etf-score batch -i fixtures/a.csv -i fixtures/b.csv -o batch_scores/
etf-score batch --input-dir fixtures/universes/ -o batch_scores/
```

Writes `{stem}_scores.csv` per input plus optional `all_scores.csv` with `universe_source`.

## CLI (single universe)

```bash
cd research/etf-fundamental-score
pip install -e ".[dev]"
etf-score -i fixtures/universe_sample.csv -c config.yaml -o scores.csv
# or explicitly:
etf-score score -i fixtures/universe_sample.csv -o scores.csv
```

## Required / optional CSV columns

| Column | Required | Used by |
|--------|----------|---------|
| `symbol` | Yes | ID |
| `category` | For overlays / within-category rank | sector_overlays |
| `expense_ratio` | For fee | fee |
| `aum_usd` | For aum, flow, liquidity | aum, flow, liquidity |
| `tracking_error_bps` | For TE | tracking_error |
| `top10_holdings_weight` | For concentration | concentration |
| `holdings_median_pe` | For valuation | valuation |
| `net_flow_30d_usd` | For flow | flow |
| `premium_bps` | For premium | premium |
| `avg_daily_volume_usd` | For liquidity | liquidity |
| `dividend_yield` | For dividend_yield | dividend_yield |

## Failure modes & mitigations

| Failure | Symptom | Mitigation |
|---------|---------|------------|
| Undocumented weight change | Non-reproducible ranks | Weights only in `config.yaml`; `version` field |
| Missing factor fields | `flags` contains `missing_factor:*` | Fix data; pick missing policy |
| Cross-category compare | Apples-to-oranges ranks | Filter `category` or use `rank_within_category` |
| QDII vs onshore TE | Mis-ranking | Use `sector_overlays` TE bands |
| Attempt LIVE mode | `load_config` error | By design — research pool only |

## Verification checklist

- [ ] Weights sum to 1.0  
- [ ] Each factor has unit tests on synthetic rows  
- [ ] `scores.csv` includes rank + factor columns  
- [ ] Row with intentional missing TE flags `missing_factor:tracking_error`  
- [ ] Batch manifest produces `all_scores.csv`  
- [ ] No language implying guaranteed outperformance  
