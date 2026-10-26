请拍板：维持面层 B45 + spike_ft max5 + E0 + TV25 + SHARPE20，只叠一层单票时停：连续持有 ≥ N 周的名字在当周周五再平衡被强制清出，必须重新挣席。主档 N=8、冷静 K=0。无论记正与否都不换冠。

> 主簿 `TS-MH8` 相对 **当次重放的 F0**，全样本满足 Δret ≥ Δ|MDD|，且 2023–26 累计收益不低于 F0 的 2023–26（强势段不踏空，且自身为正）。

## 库存

- `engine_source` = **btheta_05f0f8a4**
- `kit_path` = `C:\Users\Michael_YANG\Documents\GitHub\GGSDDU\research\cloud_batch\CLOUD-BATCH-2026-10-26`
- `nav_anchor` = `git:origin/cursor/spike-s20-extend-rebase-live1430-27f1:research\cloud_batch\SPIKE-S20-EXTEND-REBASE-LIVE1430\nav_LIVE1430-B45-S20.csv`
- `skipped` = ["research/exit-atr-chandelier"]

## 锚点门

F0 ret=131.6% maxDD=-18.8% Calmar=0.70 Sharpe=0.82（锚 131.6% / −18.8% / 0.70 / Sharpe 0.82）→ 通过。

## 主表

| id | N | ret | maxDD | Calmar | n_timestop | same_fri_re | avg_to_1w | verdict |
|---:|---:|---:|---:|---:|---:|---:|---:|---|
| F0 | off | 131.6% | -18.8% | 0.70 | 0 | 0 | 0.1559 | ANCHOR |
| TS-MH8 | 8 | 113.4% | -19.0% | 0.62 | 20 | 0 | 0.1664 | 证伪 |
| TS-MH6 | 6 | 126.0% | -19.5% | 0.65 | 35 | 0 | 0.1650 | 证伪 |
| TS-MH12 | 12 | 125.1% | -18.8% | 0.67 | 5 | 0 | 0.1582 | 证伪 |

### Δ / 闸（相对本次 F0）

| id | Δret pp | Δ|MDD| pp | G1 | G2 2023–26 | verdict |
|---|---:|---:|:---:|:---:|---|
| TS-MH8 | -18.3 | +0.2 | false | true | 证伪 |
| TS-MH6 | -5.6 | +0.7 | false | false | 证伪 |
| TS-MH12 | -6.5 | -0.0 | false | true | 证伪 |

### 时停诊断

| id | n_timestop | same_fri_reenter | n_cool_block | n_e0 | avg_hold_weeks |
|---|---:|---:|---:|---:|---:|
| F0 | 0 | 0 | 0 | 175 | 2.51 |
| TS-MH8 | 20 | 0 | 0 | 179 | 2.31 |
| TS-MH6 | 35 | 0 | 0 | 165 | 2.20 |
| TS-MH12 | 5 | 0 | 0 | 176 | 2.42 |

## 证伪段

证伪（不换冠）：TS-MH8 未过闸 G1/G2（或 n_timestop=0）。Δret -18.3pp，Δ|MDD| +0.2pp，2023–26 96.7% vs F0 94.8%。

**family_verdict** = `H1_HOLD`；`positive_ids` = []。

## 红线

`champion_swap=false`；`crown=NO`；未改 LIVE_OPS / champion_mast；未新抓数；未混用 158.3%/0.94 或 68.1%/0.31 锚。

source_sha=05f0f8a4f778fde886f3e7b2976646ff4b7d777b；耗时 23.8s。
