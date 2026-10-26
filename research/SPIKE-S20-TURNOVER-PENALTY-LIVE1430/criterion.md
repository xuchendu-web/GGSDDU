# SPIKE-S20-TURNOVER-PENALTY-LIVE1430

- 编号 / 日期 / 来源：SPIKE-S20-TURNOVER-PENALTY-LIVE1430 / 2026-10-26 / Michael 语音·烧 Cursor（悟空）
- 批次 ID：CLOUD-TURNOVER-PENALTY
- 性质：**填席排序换手惩罚**（研究池；非 LIVE / 非实盘）

## 准则原文
冻结面层 **B45 + spike_ft max5 + E0 + TV25 + SHARPE20**；Fri≥14:30/收盘；**0.2%RT**；**L≤1**。  
**唯一改动**：填席排序时对高近期换手标的扣分（**非**额外费率）：  
`score = sharpe20 − λ × to_norm`，再按 score 取 top-max5。  
`to_norm`：当周 spike 候选池（有 sharpe20 者）内对 `trailing_4w_turnover` 做 min-max 归一化至 [0,1]（池内无跨度则 0）。  
λ ∈ **{0, 0.15, 0.25}**；**λ=0** 为同窗对照（plain face）。

## 换手分（可复现）
`trailing_4w_turnover(code, Fri_d)` = 信号周 `d` 之前 **4 个日历周五**（不含 `d`）上，各周五 14:30 切片  
`turnover_rate_fri = (vol_1430 × price_1430) / (aum_亿元 × 1e8)` 的算术均值；缺 `vol_1430`/价/AUM 的周五跳过；全无则 **0**。

## 邻档
- **对照 / baseline**：λ=0（plain S20 填席）
- **网格**：λ=0.15、λ=0.25（仅排序惩罚权重）

## 假设
λ>0 能在 **不显著牺牲 Calmar** 下压低组合换手/改善回撤覆盖（Δret 盖住 Δ|MDD|）；后段 2023–26 不踏空。

## 证伪
任一档 **λ>0** 相对 λ=0：**Calmar 更差** 且 **Δret 盖不住 Δ|MDD|**（全样本或 2020–22 / 2023–26 分段）；或后段 ret 明显踏空（< λ=0 ×0.9）。

## 红线
不重做成本敏感性（PR#40）；不改 breadth/TV/滞回/债腿；不写 strategy_exec / LIVE_OPS / 实盘池；不换冠。

## 主表
三账（λ 网格）；产物 `research/SPIKE-S20-TURNOVER-PENALTY-LIVE1430/`

## 交付
四件套 + λ 相对对照表（Δret / Δ|MDD| / ΔCalmar / 分段 / skip）。

