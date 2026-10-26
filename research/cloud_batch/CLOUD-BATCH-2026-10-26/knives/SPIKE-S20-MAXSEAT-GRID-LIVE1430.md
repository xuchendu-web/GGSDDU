# SPIKE-S20-MAXSEAT-GRID-LIVE1430

- 编号 / 日期 / 来源：SPIKE-S20-MAXSEAT-GRID-LIVE1430 / 2026-10-26 / Michael 语音·烧 Cursor（悟空）
- 批次 ID：CLOUD-MAXSEAT-GRID
- 性质：spike 席位 **maxN 机械网格**（延窗）

## 准则原文
相对 B45+S20 max5，**只改席位数** maxN ∈ {**3, 4, 5, 6, 7**}；填席仍 SHARPE20；E0+TV25 不变。窗 ≥2026-10-23。

## 改动点（唯一）
spike_ft 取前 maxN。

## 假设
延窗后 **max5** 仍是网格甜区；max3（未升格）与 max7（E07 证伪）相对 max5 仍盖不住或踏空。

## 证伪
max4/max6 稳定优于 max5 且盖住回撤并后段不踏空 → 记下「席位甜区外移」（仍不换冠）；若 max3/max7 翻盘亦记。若全档逊于旧窗叙事且与 E07/MAX3 矛盾，标延窗敏感。

## 红线
非 RET/宏观同构；不与 hyp4 填席改动混跑。

## 主表
五档；产物 `.../SPIKE-S20-MAXSEAT-GRID-LIVE1430/`

## 共用冻结
- 成交：Fri ≥14:30 / 当日收盘；0.2%RT；**L≤1**
- 面层默认：breadth≥45% + spike_ft max5 + E0 + TV25 + SHARPE20（各刀「唯一改动」另写）
- 研究池 ≠ 实盘池；**不换冠**；不碰 strategy_exec / LIVE_OPS / 冠军主钉 / 固收+ / 红利袖
- 探索尺子：Δret 须盖住 Δ|MDD|；报 2020–22 / 2023–26；强势段不踏空
- **执行强制**：机械回测/扫参/延窗 **必须用 Cursor CloudAgent**（Cursor 自家模型跑批）；本机 Grok executor 仅可做准则核对与收件，勿替代云端批跑（烧 Cursor 池至约 11/1 周重置）
- **并行**：勿打断/取消 `SPIKE-MOM121-W7525-LIVE1430`（hyp4 既定路径继续）


## 交付
四件套；CloudAgent 扫参。
