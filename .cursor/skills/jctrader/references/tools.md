# jctrader 工具速查

服务：`jctrader-mcp` v1.0.0  
调用：MCP `tools/call`，或 `python3 .cursor/skills/jctrader/scripts/jctrader_client.py call <name> '<json>'`

## 市场总览

### get_market_sentiment

- `metric`: `all` | `buy_ratio` | `median_age` | `dispersion` | `freshness_burst`（默认 `all`）
- 返回：`interpretation`、`overall_buy_ratio`、`median_tracking_age`、`industry_dispersion`

### get_market_breadth

- `index`: `all` | `hs300` | `zz500` | `zz1000` | `zz2000`（默认 `all`）
- 返回：`total`、`inflection_buy`、`inflection_buy_ratio`、`tracking_buy`、`tracking_buy_ratio`、中位年龄
- 注意：`index` 过滤可能不生效

### get_market_resonance_matrix

- `granularity`: `stock` | `industry` | `index`（默认 `stock`）
- `freshness_threshold`: 默认 `5`
- 返回：`down_acceleration`、`bull_loosening`、`trend_acceleration`、`bear_exhaustion`、`total`

## 板块 / 风格

### get_sector_strength

- `dimension`（必填）: `industry_l1` | `industry_l2` | `industry_l3` | `theme` | `concept` | `index`
- `signal_type`: `inflection` | `tracking` | `both`（默认 `both`）
- `sort_by`: `strength` | `freshness` | `buy_ratio`（默认 `strength`）
- `top_n`: 默认 `20`；行业全表用 `40`
- `min_stocks`: 默认 `5`
- 返回每条：`name`、`strength_score`、`buy_ratio`、`fresh_buy_ratio`、`buy_count`、`fresh_buy_count`、`total`

index 名称：`sz50`、`hs300`、`kc50`、`chinext`、`zz500`、`zz1000`、`bz50`、`zz2000`

### get_sector_freshness

- `dimension`: `industry_l1` | `theme` | `concept` | `index`
- `freshness_days`: 默认 `5`
- `top_n`: 默认 `20`

### get_concept_voice_index

- `concepts`: 可选字符串数组
- `short_weight`: 默认 `0.7`；`long_weight`: 默认 `0.3`
- `top_n`: 默认 `20`
- 返回：`name`、`momentum_score`、`buy_ratio`、`buy_count`、`total`

### get_signal_crowding

- `dimension`: `industry_l1` | `theme` | `concept`（默认 `industry_l1`）
- `top_n`: 默认 `20`
- 返回：`crowding_note`（如「较为拥挤」「正常」）

### get_reversal_risk

- `dimension`: `industry_l1` | `theme` | `concept`
- `top_n`: 默认 `10`
- 返回：`quadrant`（黄金区 / 蛰伏区等）

### get_allocation_weights

- `dimensions`: 默认 `["industry_l1","theme"]`
- `exclude_crowded`: 默认 `true`
- `crowding_threshold`: 默认 `2.0`
- `risk_budget`: 默认 `100`

## 个股 / ETF / 商品

### screen_stocks

- `industry` / `concept` / `index`（`sz50` `hs300` `zz500` `zz1000` `zz2000` `chinext` `bz50` `kc50`）
- `inflection_signal` / `tracking_signal`: `buy` | `sell`
- `tracking_fresh_days`: 只保留近 N 日跟踪信号
- `exclude_st` / `exclude_loss`: 默认 `true`
- `top_n`: 默认 `50`

### get_top_rated_stocks

- `universe`: `all` | `hs300` | `zz500` | `zz1000`
- `top_n`: 默认 `20`
- 可能大量同分，慎当排行榜

### get_etf_signals

- `keyword`: 如 `银行`、`沪深300`、`科创`
- `signal_filter`: `all` | `buy` | `sell`

### get_etf_sector_match

- `sector`: 行业/主题名，如 `银行`、`传媒`
- `top_n`: 默认 `10`

### get_commodity_signals

- `category`: `all` | `贵金属` | `能源` | `农产品` | `工业金属` | `黑色系`

### get_commodity_stock_correlation

- `commodity` / `sector`

### get_risk_stocks

- `risk_types`: 默认 `["st","loss_warning"]`
- `stale_days`: 默认 `60`

### get_alpha_decomposition

- `code`（必填），如 `000001.SZ`

### get_signal_quality_rank

- `universe`: `all` | `hs300` | `zz500`
- `top_n`: 默认 `50`

### get_long_short_pairs

- `universe`: `industry` | `index` | `cross_market`
- `target`、`top_long`、`top_short`
- 可能返回空列表

### get_market_neutral_portfolio

- `balance_mode`: `equal_count` | `equal_weight`
- `num_long` / `num_short`: 默认 `10`

### get_portfolio_status

- `codes`: 代码数组（必填）
- `include_distribution`: 默认 `true`

### get_rebalance_suggestion

- `current_allocation`: 对象，如 `{"银行": 20, "传媒": 10}`
- `rebalance_threshold`: 默认 `5.0`
