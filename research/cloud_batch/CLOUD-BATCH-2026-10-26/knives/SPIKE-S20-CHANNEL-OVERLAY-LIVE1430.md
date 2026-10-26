# SPIKE-S20-CHANNEL-OVERLAY-LIVE1430

- 编号 / 日期 / 来源：SPIKE-S20-CHANNEL-OVERLAY-LIVE1430 / 2026-10-26 / Michael 语音·烧 Cursor（悟空）
- 批次 ID：CLOUD-CH-OVERLAY
- 性质：**宏观通道 long/flat（Ariston_Macro 风）× B45 广度门** 面层叠加（延窗）

## 准则原文
在 **SPIKE-S20 B45 face** 上叠加 **510300 周线通道/均线结构**：`risk_on = face_B45 ∧ macro_long`；macro 仅当 **价在上升均线/通道结构上方** 为 on，否则面层空仓（cash）。邻档 **周 MA20 / MA50 / MA100**（上升：MA 较 4 周前抬升）。Fri≥14:30 / 收盘；**0.2%RT**；**L≤1**；TV25+E0+max5+SHARPE20 冻结。

## 改动点（唯一）
相对 B45+S20，**只改 risk_on 合成**（加宏观 long/flat 过滤）；选品/填席/TV 不变。

## 假设
宏观 long/flat 能在不显著踏空 2023–26 的前提下 **压低 |MDD|**，且 Δret 盖住 Δ|MDD|（相对 FACE 基线）。

## 证伪
三邻档均未盖住回撤加深，或 2023–26 相对 FACE 明显踏空 → 证伪「宏观通道可作正式叠加」。

## 红线
不换冠；不碰 strategy_exec / LIVE_OPS / 冠军主钉；研究池 only。

## 主表
四账：B45 基线 + CH-MA20/50/100；产物 `.../SPIKE-S20-CHANNEL-OVERLAY-LIVE1430/`

## 交付
四件套；CloudAgent 批跑。
