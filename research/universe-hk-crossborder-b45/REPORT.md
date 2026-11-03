# REPORT · UNIVERSE-HK-CROSSBORDER-B45

研究池刀：港股+跨境权益 ETF 宇宙切片 vs 全池 FACE（B45+S20 LIVE1430）。不换冠、不碰 LIVE_OPS。

## 面层（冻结）

B45 + spike_ft max5 + E0 + TV25 + SHARPE20；周五信号→收盘成交（本云批次用日收盘近似 Fri≥14:30）；0.2%RT；L≤1。

## 宇宙与 breadth

- **切片**：`data/universe_hk.json`（港股/跨境权益 ETF，聚源标签+名称规则，见 `universe.sql`）。
- **全池 face 对照**：`data/universe_full.json`（~280 流动性筛 equity ETF）。
- **breadth 母池（写死）**：全池 `full_ok` 的 MA20 宽度 ≥45% 才 risk-on；**旁注**：切片内 MA20 宽度未作主口径。

## 覆盖

- HK ≥200 日：42/42（门槛 85%）
- 全池 ≥200 日：199/280（门槛 70%）
- 权威源：zsmcp `mf_fundnetvaluere.UnitNVRestored`（`SecuCategory=8` InnerCode）。未臆造 NAV，未碰 LIVE / 冠军主钉。

## 主表

| book | ret | maxDD | Calmar | 2023–26 ret | 2023–26 Calmar | avgL | 空仓周占比 |
|---|---:|---:|---:|---:|---:|---:|---:|
| FACE-FULL | 18.4% | -15.6% | 0.16 | 10.8% | 0.18 | 0.49 | 50.9% |
| SLICE-HK-XB | 23.7% | -17.5% | 0.18 | 8.4% | 0.12 | 0.41 | 50.9% |

## H1

假设：切片相对全池 face **不能**同时改善 Calmar 且 2023–26 不踏空。
**NOT_FALSIFIED**（ΔCalmar=0.021；切片后段踏空=True）。

## 宽基旁注

- WIDE-510300: ret 2.0%, Calmar 0.03
- WIDE-510500: ret 12.0%, Calmar 0.22
- WIDE-159915: ret 15.4%, Calmar 0.32
- WIDE-159919: ret 2.2%, Calmar 0.03
- WIDE-159922: ret 13.1%, Calmar 0.27

## 数据与复现

数据源：**zsmcp** `mf_fundnetvaluere.UnitNVRestored`（未用进门/中金/Alpha派，未抄 sibling close）。`python3 run.py --cache data/nav_long.csv`。
剩余未达 200 日的全池码见 `data/_need_full.json` / `data/CACHE_GAP.md`（可选补齐，不影响本轮门槛）。

耗时约 18.18s。产物：`run.py` / `criterion.md` / `REPORT.md` / `summary.json` / `output/table.csv` / `output/equity_curve.png`。