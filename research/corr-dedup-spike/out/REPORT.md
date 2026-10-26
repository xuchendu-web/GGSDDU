请拍板：维持面层 B45 + spike_ft max5 + E0 + TV25 + SHARPE20，只在填席时对已入选名字做 60 周收益相关去重（主档 ρ*=0.85），无论记正与否都不换冠。

```
唯一改动：在面层 B45 + spike_ft max5 + E0 + TV25 + SHARPE20 上，
SHARPE20 排序之后，对本周新开/换入做贪心 60 周收益 Pearson 去重。
  主档 ρ* = 0.85。邻档 0.75 / 0.90。共 4 本。
  已持仓不因彼此相关超过 ρ* 而平。出场维持 E0。
  B、TV、席位上限、成本不离开面。

H1：DEDUP-R85 在严格尺子下相对本次 F0 证伪。
  主档记正 → H1 证伪（家族记一笔，不换冠）。
  主档证伪 → H1 成立。
  邻档即使记正也不升格、不改 H1。
```

## 库存

- `corr_source` = **computed_from_cache**
- `price_cache_path` = `C:\Users\Michael_YANG\Documents\GitHub\GGSDDU\research\cloud_batch\CLOUD-BATCH-2026-10-26\data\research_cache\day;C:\Users\Michael_YANG\Documents\GitHub\GGSDDU\research\cloud_batch\CLOUD-BATCH-2026-10-26\data\research_cache\sina_daily`
- `pool_label_path` = `C:\Users\Michael_YANG\Documents\GitHub\GGSDDU\research\cloud_batch\CLOUD-BATCH-2026-10-26\data\universe_replace_only_436.csv`
- `skipped` = []

## 锚点门

F0 ret=131.6% maxDD=-18.8% Calmar=0.70 （锚 131.6% / −18.8% / 0.70）→ 通过。

## 主表

| id | ρ* | ret | maxDD | Calmar | 2020–22 / 2023–26 ret | n_dedup_skip | avg_max_ρ | avg_max_family | verdict |
|---|---:|---:|---:|---:|---|---:|---:|---:|---|
| F0 | off | 131.6% | -18.8% | 0.70 | 18.9%/94.8% | 0 | 0.885 | 2.17 | ANCHOR |
| DEDUP-R85 | 0.85 | 124.8% | -18.4% | 0.69 | 32.8%/69.2% | 164 | 0.726 | 1.66 | 证伪 |
| DEDUP-R75 | 0.75 | 136.4% | -17.5% | 0.77 | 30.5%/81.1% | 288 | 0.677 | 1.69 | 证伪 |
| DEDUP-R90 | 0.9 | 129.3% | -17.6% | 0.74 | 31.4%/74.5% | 77 | 0.768 | 1.79 | 证伪 |

### Δ / 闸（相对本次 F0）

| id | Δret pp | Δ|MDD| pp | G1 | G2 2023–26 | G3 2020–22 | verdict |
|---|---:|---:|:---:|:---:|:---:|---|
| DEDUP-R85 | -6.8 | -0.4 | false | false | true | 证伪 |
| DEDUP-R75 | +4.7 | -1.3 | true | false | true | 证伪 |
| DEDUP-R90 | -2.3 | -1.2 | false | false | true | 证伪 |

### 扎堆旁注

- F0 `avg_max_pair_corr`=0.885，`avg_max_family`=2.17，`n_incumbent_over_rho`（主档口径）见各格。
- 邻档记正 **不** 写入 `positive_ids`，不翻转 `family_verdict`。

## 证伪段

**H1 成立（不换冠）**：主档 DEDUP-R85 证伪，spike 池内 60 周相关去重无记正。

## 红线

`champion_swap=false`；`crown=NO`；未改 LIVE_OPS / champion_mast；未新抓数；未混用 158.3%/0.94 或 68.1%/0.31 锚。

source_sha=05f0f8a4f778fde886f3e7b2976646ff4b7d777b；family_verdict=H1_HOLD；耗时 43.1s。
