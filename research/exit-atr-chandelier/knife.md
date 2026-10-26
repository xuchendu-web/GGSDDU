# EXIT-ATR-CHANDELIER

- 编号 / 日期 / 来源：EXIT-ATR-CHANDELIER / 2026-10-26 / 研究设计卡
- 批次 ID：EXIT-ATR-CH
- 性质：面层 **B45+S20+TV25 max5** 上叠加入场后 ATR 吊灯（研究池；本刀不跑批）

## 准则原文

冻结 face：breadth≥45% + spike_ft max5 + SHARPE20 填席 + E0 + TV25 + Fri≥14:30 / 收盘 + 0.2%RT + L≤1。

**唯一改动**：单票 `stop = HH_since_entry − k × ATR(N)`，与 E0 共用周五 `px_on`（FACE 路径上为 qfq_1430）。主簿 N=14、k=3。E0 保留，不替换。

与旧刀布尔差：E0 / PT / MH / COOL 都是一次性对照（当周结构、入场价、持有周数、上周组合收益）。本族路径追踪，HH 只上不下，距离跟自身波动走。

## H1

主簿相对 in-run FACE：Δret ≥ Δ|MDD|，且 2023–26 不踏空（后段收益 ≥ FACE 后段且为正）。

## 邻档

`CH-ATR14×2.5`、`CH-ATR14×3.5`、`CH-ATR22×3`。只旁注，不升格，不插值。

## 证伪

主簿未过 H1 两闸；或锚对不齐 / ATR 覆盖不足 → `BLOCKED`。邻档不能救主簿。

## 跳过

PT / COOL / MH / RD 及其交叉；滚动窗吊灯；周 ATR；组合净值吊灯；替换 E0；固收+ / 红利袖 / LIVE_OPS / 换冠。行情不走来门 / 中金 / Alpha 派。

## 红线

研究池 only；不换冠；`champion_swap = false`。FACE 锚是延窗 131.6% / −18.8% / 0.70，不是 TV 网格 158.3% / 0.94。

## 交付

四件套 → `research/exit-atr-chandelier/out/`（由执行卡按 `COMPOSER.md` 写；本 PR 只有准则）。
