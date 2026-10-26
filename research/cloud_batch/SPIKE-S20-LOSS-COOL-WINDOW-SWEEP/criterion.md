# Criterion · SPIKE-S20-LOSS-COOL-WINDOW-SWEEP

# SPIKE-S20-LOSS-COOL-WINDOW-SWEEP

- 编号 / 日期 / 来源：SPIKE-S20-LOSS-COOL-WINDOW-SWEEP / 2026-10-26 / CloudAgent 研究队列
- 批次 ID：CLOUD-LOSS-COOL
- 性质：**风控 overlay 扫参**（机械批；非换冠）

## 准则原文

在 **B45+S20 face 基线**（breadth≥45% + spike_ft max5 + SHARPE20 + E0 + TV25）上，唯一叠加：

> 若**上一完整交易周**组合周收益 ≤ **−4% / −6% / −10%**（三档并列扫），则**本周信号日强制空仓/冷静**（不新开、持仓清零至现金），直至下一周五再按基线规则恢复（仍受当周触发约束）。

触发用收益：**基线 B45+S20 同窗周收益**（overlay 不反身；与 RET 窗扫区分）。

## 改动点（唯一）

loss-cool 阈值三档；规则引擎、池、face、14:30 分类均冻结。

## 假设

急跌周后冷静一周能在不显著牺牲 2023–26 参与的前提下，**Δret 盖住 Δ|MDD|**（探索尺子）。

## 证伪

三档**无一**同时满足：相对基线 Δret ≥ Δ|MDD|、2023–26 ret 不低于基线 90%、Calmar 不劣于基线 → **loss-cool 方向证伪**（记入 summary `falsify: true`）。

若仅 −10% 有效而 −4% 踏空 → 记下**阈值过敏**旁注，仍不换冠。

## 主表

同窗一行一账：基线 + LC4 / LC6 / LC10。

## 共用冻结

- 成交：Fri ≥14:30 / 当日收盘；0.2%RT；**L≤1**
- 面层：**B45 face**（`holdings_ro2_extended` risk_on）+ spike_ft max5 + E0 + TV25 + SHARPE20
- **研究 ETF 池**（replace_only + AUM≥2）；**不写 strategy_exec / LIVE_OPS**；不换冠
- 样本：CLOUD-BATCH research_cache 延窗 ≥2026-10-23
- **执行**：Cursor CloudAgent 机械批跑

## 交付

四件套 + `table.csv` / `equity_curve.png` / `holdings_*.csv`。
