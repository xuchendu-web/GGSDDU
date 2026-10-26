# UNIV-THEME-BROAD-SPLIT-B45

- 编号 / 日期：UNIV-THEME-BROAD-SPLIT-B45 / 2026-10-26 / 机械批测 Composer
- 性质：**分账轮动** — 行业主题宇宙 vs 宽基宇宙分开跑 B45+S20，再合成净值；对照全池混排 face

## 准则原文
- 子宇宙：**宽基** = `family` 以「宽基」开头；**主题侧** = 其余（行业/风格/主题等，AUM≥2亿研究池）。
- 各腿规则冻结：spike_ft **max5** + E0 + **TV25** + **SHARPE20**；breadth≥45%（**共用母池 face** `risk_on`）。
- 合成：50/50 固定权、等风险（60日逆波周调）、邻档 **60/40**、**70/30**（主题:宽基）。
- 对照：**FACE** = 全池混排同一规则（face 基线）。
- 成交：Fri≥14:30 / 收盘；**0.2%RT**；**L≤1**；窗 ≥2026-10-23。

## 假设 H1
分账合成**不能**稳定胜过混排 face（Δret 盖 Δ|MDD| 且 2023–26 不踏空）。

## 证伪
任一分账/合成档相对 FACE 同时满足探索尺子且 Calmar 更高 → H1 不成立（只记账，不换冠）。

## 红线
研究池 only；不换冠；不碰 strategy_exec / LIVE_OPS / 实盘。

## 交付
四件套：`research/univ-theme-broad-split-b45/`（run.py / criterion.md / REPORT.md / summary.json）
