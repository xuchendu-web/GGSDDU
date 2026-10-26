# REBALANCE-BIWEEKLY-B45

- 编号 / 日期 / 来源：REBALANCE-BIWEEKLY-B45 / 2026-10-26 / Michael 语音·机械批测（Composer）
- 批次 ID：CLOUD-REBAL-FREQ
- 性质：**再平衡频率**邻档（研究池 only；不换冠）

## 准则原文
相对 **每周再平衡** 的 B45+S20 face，**只改组合权重调仓频率**；信号仍按 **周五≥14:30** 口径逐周计算（结构踢出 / breadth 门强制退出仍按周执行）。中间周 **沿持**（不加仓、不等权再平衡）。

邻档：
1. **FACE** — 每信号周调仓（周频，对照）
2. **2W** — 每 **2** 个信号周调一次
3. **3W** — 每 **3** 个信号周调一次
4. **GATE+2W** — 门（risk_on）翻转周 **强制调**；其余按双周

## 改动点（唯一）
再平衡 / 加仓 / 等权再分配的节奏；**不改** B45、spike_ft、E0、TV25、S20 选股与踢出规则。

## 假设
**H1**：降频再平衡 **不能** 同时降低换手并保持 Δret 盖住 Δ|MDD| 且 2023–26 不踏空。

## 证伪
任一档相对 FACE：换手未显著下降，或 Δret 盖住 Δ|MDD| 且后段不踏空 → H1 被推翻（只记账，不升格）。

## 红线
不碰 strategy_exec / LIVE_OPS / 冠军；不发明数字；面层冻结 **B45+spike max5+E0+TV25+S20**；0.2%RT；**L≤1**。

## 主表
四档；产物 `research/rebalance-biweekly-b45/`

## 共用冻结
- 成交：Fri ≥14:30 / 当日收盘；0.2%RT；**L≤1**
- 面层：breadth≥45% + spike_ft max5 + E0 + TV25 + SHARPE20
- 研究池 ≠ 实盘池；**不换冠**
- 探索尺子：Δret 须盖住 Δ|MDD|；报 2020–22 / 2023–26；强势段不踏空
- **执行**：Cursor CloudAgent 机械回测；kit `CLOUD-BATCH-2026-10-26`

## 交付
四件套；CloudAgent 批跑。
