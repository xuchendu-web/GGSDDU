# SPIKE-S20-ENTRY-MOM-LB-LIVE1430

- 编号 / 日期 / 来源：SPIKE-S20-ENTRY-MOM-LB-LIVE1430 / 2026-10-26 / CloudAgent 研究批
- 批次 ID：CLOUD-ENTRY-MOM-LB
- 性质：spike_ft **入场动量窗**机械网格（延窗）

## 准则原文
SPIKE-S20 面冻结：**B45 + spike_ft max5 + SHARPE20 填席 + E0 + TV25**；**只改**新入场动量确认 **R{N}d > 0**，N ∈ {**40, 60（基线）, 80**}。窗 ≥2026-10-23；**研究 ETF 池**。

## 改动点（唯一）
个股 spike_ft 候选在填席前须满足 `R{N}d>0`（日频，信号日 strict 前一日截止）；持仓退出仍结构/宽度闸，不因 R 转负强平。

## 假设
~12 周（60 交易日）动量确认与 spike 冲击节奏最合拍：**R60d** 为甜区中心；R40 过灵易踏空后段，R80 过粘易伤参与。

## 证伪
R40 或 R80 稳定优于 R60（Δret 盖住 Δ|MDD| 且 2023–26 不踏空）→ 记「入场窗偏离 60d」；或 R60 相对无 R 门槛 B45+S20 面后段系统性踏空 → 记「动量确认伤参与」。

## 红线
不写 LIVE_OPS / champion_mast / 实盘 / strategy_exec；不与 hyp4 填席改动混跑。

## 主表
三档；产物 `research/cloud_batch/SPIKE-S20-ENTRY-MOM-LB-LIVE1430/`

## 共用冻结
- 成交：Fri ≥14:30 / 当日收盘；0.2%RT；**L≤1**
- 面层：breadth≥45% + spike_ft max5 + E0 + TV25 + SHARPE20（本刀仅改入场 R 窗）
- 研究池 ≠ 实盘池；**不换冠**
- 探索尺子：Δret 须盖住 Δ|MDD|；报 2020–22 / 2023–26

## 交付
四件套（criterion → run.py → REPORT 主表 → 证伪段）；CloudAgent 批跑。
