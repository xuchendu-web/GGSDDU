# MF-HOLD-BGRID

- 编号 / 日期 / 来源：MF-HOLD-BGRID / 2026-10-26 / Michael 语音·烧 Cursor（悟空）
- 批次 ID：CLOUD-MF-HOLD-BGRID
- 性质：多频轨退出缓冲 **B 邻档网格**（另账、不合层）

## 准则原文
在 `/workspace/etf-multifreq/` 全池 XS52 取5 框架下，**只改退出缓冲 B**，网格 B ∈ {**6, 7, 8, 9**}；对照无缓冲若已有数可引用。不叠冠军强栈。

## 改动点（唯一）
HOLD 缓冲宽度 B。

## 假设
**B=8**（已记正 169.4%/C0.38）在邻域仍最优；B=10 已证伪不重开；B=6/7 换手升但后段不优于 8；B=9 不显著优于 8。

## 证伪
B=6/7/9 相对 B=8 盖住且后段更强 → 甜区外移；或 B=8 延窗/重跑后盖不住无缓冲 → 证伪 B8 记正。

## 红线
多频不合层；不换冠；不改实盘。

## 主表
四档；产物 `/workspace/etf-multifreq/MF-HOLD-BGRID/`

## 共用冻结
- 成交：Fri ≥14:30 / 当日收盘；0.2%RT；**L≤1**
- 面层默认：breadth≥45% + spike_ft max5 + E0 + TV25 + SHARPE20（各刀「唯一改动」另写）
- 研究池 ≠ 实盘池；**不换冠**；不碰 strategy_exec / LIVE_OPS / 冠军主钉 / 固收+ / 红利袖
- 探索尺子：Δret 须盖住 Δ|MDD|；报 2020–22 / 2023–26；强势段不踏空
- **执行强制**：机械回测/扫参/延窗 **必须用 Cursor CloudAgent**（Cursor 自家模型跑批）；本机 Grok executor 仅可做准则核对与收件，勿替代云端批跑（烧 Cursor 池至约 11/1 周重置）
- **并行**：勿打断/取消 `SPIKE-MOM121-W7525-LIVE1430`（hyp4 既定路径继续）


## 交付
四件套；**必须 CloudAgent** 跑网格。
