# REPORT · UNIVERSE-HK-CROSSBORDER-B45

研究池刀：港股+跨境权益 ETF 宇宙切片 vs 全池 FACE（B45+S20 LIVE1430）。不换冠、不碰 LIVE_OPS。

## 状态

**`incomplete_cache`。引擎、准则、PIT listing、`SecuCategory=8` InnerCode 已齐；HK 切片 NAV 已过门槛，全池覆盖未过 70%，未出 H1 数字。**

| 覆盖 | 当前 | 门槛 |
|---|---:|---:|
| HK ≥200 日 | 42 / 42（100%） | 85% |
| 全池 ≥200 日 | 168 / 280（60.0%） | 70% |
| `nav_long.csv` | 151925 行 / 183 码 | — |

缺口与复现见 `data/CACHE_GAP.md`。`python3 data/coverage_status.py` 可复核。未臆造 NAV，未跑 `--allow-partial` 充数。

## 面层（冻结）

B45 + spike_ft max5 + E0 + TV25 + SHARPE20；周五信号→收盘成交（云批次用日收盘近似 Fri≥14:30）；0.2%RT；L≤1。

## 宇宙与 breadth

- **切片**：`data/universe_hk.json`（42 只，聚源标签+名称规则，见 `universe.sql`）。
- **全池 face**：`data/universe_full.json`（280 只流动性筛 equity ETF）。
- **breadth 母池（写死）**：全池 MA20 宽度 ≥45%；**旁注**：切片内 MA20 宽度未作主口径。

## 假设 H1

港股跨境切片相对全池 face **不能**同时改善 Calmar 且 2023–26 不踏空。

证伪/记账结论在 `summary.json` 的 `h1.h1_verdict`（需完整缓存后生成）。本轮不给 H1。

## 复现

```bash
cd research/universe-hk-crossborder-b45
# 先按 data/FETCH.md / data/CACHE_GAP.md 补全 nav_long.csv
python3 data/coverage_status.py
python3 run.py --cache data/nav_long.csv
```

数据源：**zsmcp** `mf_fundnetvaluere.UnitNVRestored`（未用进门/中金/Alpha派）。
