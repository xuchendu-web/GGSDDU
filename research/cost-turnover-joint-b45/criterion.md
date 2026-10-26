# COST-TURNOVER-JOINT-B45

- 编号 / 日期 / 来源：COST-TURNOVER-JOINT-B45 / 2026-10-26 / Michael 语音·烧 Cursor（悟空）
- 批次 ID：CLOUD-COST-TURNOVER-JOINT
- 性质：**成本×换手惩罚联合敏感**（研究池；非 LIVE / 非实盘）

## 准则原文
冻结面层 **B45 + spike_ft max5 + E0 + TV25 + SHARPE20**；Fri≥14:30/收盘；**L≤1**。  
**联合改动**（非单维重复）：
1. 往返成本 **RT** ∈ **{0.10%, 0.15%, 0.20%, 0.30%}**（`run_live_tv` 换手扣费按 RT 缩放；持仓路径与 RT 无关）。
2. 填席排序换手惩罚 **λ** ∈ **{0, 0.15}**：`score = sharpe20 − λ × to_norm`（**非**额外费率）；`to_norm` 同 SPIKE-S20-TURNOVER-PENALTY。

**对照**：标准面 **RT=0.20%、λ=0**（plain B45+S20 face，与实盘记账口径一致）。

## 换手分（复用）
`trailing_4w_turnover` + 池内 min-max `to_norm`；定义同 turnover-penalty 刀。

## 邻档 / 单维旁注
- 成本单维：SPIKE-S20-COST-SENS-B45（S20 vs AUM @ 0.1/0.2/0.3% 单边）
- λ 单维：SPIKE-S20-TURNOVER-PENALTY（λ∈{0,0.15,0.25} @ 0.2%RT）
- **本刀**：8 格联合主表（4 RT × 2 λ），外加相对对照 RT20-λ0 的 Δ 与 RT 维翻转记账

## 假设 H1
联合后无「低成本 + 轻惩罚」稳定占优档可记**正升格**；仅记账是否相对 **RT20-λ0** 在 Calmar/净收益上形成可重复优势。

## 证伪 / 观察
- 在 **RT≈0.15%** 附近 Calmar 或全样本 ret 相对 RT20-λ0 的排序是否翻转（λ=0 vs λ=0.15 交叉）。
- 任一格相对对照同时 **Calmar 更优且 Δret 盖住 Δ|MDD|** → 记「候选升格」；否则 H1 成立。

## 红线
不改 breadth/TV/滞回/债腿；不叠 AUM 填席对照；不写 strategy_exec / LIVE_OPS / 实盘池；不换冠。

## 主表
八账（4 RT × 2 λ）；产物 `research/cost-turnover-joint-b45/`

## 交付
四件套 + **联合主表**（含 RT 透视 Calmar/ret）+ 相对 RT20-λ0 对照。

