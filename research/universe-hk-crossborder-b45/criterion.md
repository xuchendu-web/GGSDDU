# UNIVERSE-HK-CROSSBORDER-B45

- 编号 / 日期：UNIVERSE-HK-CROSSBORDER-B45 / 2026-10-26
- 批次：CLOUD-UNIVERSE-HK-XB
- 性质：**研究池宇宙切片**（非 LIVE / 非实盘）

## 准则原文

**宇宙切片**：仅港股 + 跨境权益 ETF（`data/universe_hk.json` 明文列表；定义见 `universe.sql` 聚源标签）。  
**规则**：与 B45+S20 face 同面层。  
**breadth 母池（写死）**：全 A 研究池 `universe_full.json` 内 ETF 的周线 MA20 宽度 ≥45% 才 risk-on；**旁注**：切片内 MA20 宽度（未作主口径）。  
**对照**：同行 **全池 FACE** + **仅宽基旁注**（510300/510500/159915/159919/159922，数据够则出表）。

**面层（冻结）**：spike_ft max5 + E0 + TV25 + SHARPE20；Fri≥14:30→收盘（本批次日收盘近似）；**0.2%RT**；**L≤1**。  
勿与已证伪「外盘三本」旧引擎数字混抄；本刀须自跑。

## 假设 H1

港股跨境切片相对**全池 face** 不能同时改善 Calmar 且 2023–26 不踏空（相对全池 face 后段 ret ≥ 全池×0.9）。

## 证伪

若 **SLICE** 相对 **FACE-FULL**：Calmar 更高 **且** 2023–26 ret 未踏空（≥ 全池×0.9）→ H1 **FALSIFIED**；否则 **NOT_FALSIFIED**（探索记账，不换冠）。

## 红线

不改 strategy_exec / LIVE_OPS / 实盘池；不换冠；不走进门/中金/Alpha派行情。

## 交付四件套

`research/universe-hk-crossborder-b45/`：`run.py` · `criterion.md` · `REPORT.md` · `summary.json`
