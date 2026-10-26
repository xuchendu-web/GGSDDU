# REPORT · UNIVERSE-HK-CROSSBORDER-B45

研究池刀：港股+跨境权益 ETF 宇宙切片 vs 全池 FACE（B45+S20 LIVE1430）。不换冠、不碰 LIVE_OPS。

## 状态

**本 PR 引擎与准则已齐；全样本回测待 `data/nav_long.csv` 覆盖 ≥85% HK 且 ≥70% 全池后重跑 `python3 run.py`。**

当前缓存：`secu_fetch_status.py` 见 `data/secu_fetch_progress.json`。构建步骤见 `data/FETCH.md`。

## 面层（冻结）

B45 + spike_ft max5 + E0 + TV25 + SHARPE20；周五信号→收盘成交（云批次用日收盘近似 Fri≥14:30）；0.2%RT；L≤1。

## 宇宙与 breadth

- **切片**：`data/universe_hk.json`（42 只，聚源标签+名称规则，见 `universe.sql`）。
- **全池 face**：`data/universe_full.json`（280 只流动性筛 equity ETF）。
- **breadth 母池（写死）**：全池 MA20 宽度 ≥45%；**旁注**：切片内 MA20 宽度未作主口径。

## 假设 H1

港股跨境切片相对全池 face **不能**同时改善 Calmar 且 2023–26 不踏空。

证伪/记账结论在 `summary.json` 的 `h1.h1_verdict`（需完整缓存后生成）。

## 复现

```bash
cd research/universe-hk-crossborder-b45
# 先按 data/FETCH.md 补全 nav_long.csv
python3 run.py --cache data/nav_long.csv
```

数据源：**zsmcp**（未用进门/中金/Alpha派）。
