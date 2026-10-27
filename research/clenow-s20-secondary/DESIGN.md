# 次级排序 · Clenow score（CLENOW-S20-SECONDARY）· RESEARCH only（设计稿）

请拍板：在面层 B45 + spike_ft max5 + E0 + TV25、LIVE≥14:30 面上，**填席宇宙仍是 SHARPE20 短名单**，只在短名单内按 Clenow score 次级排序取席。主口径冻结为 **N=90、`score = (e^{β·252} − 1) × R²` 降序（CS90S）**。邻档只留 **同公式 N=60（CS60S）** 与 **只按年化斜率 `(e^{β·252} − 1)`、不乘 R²（CS90R）**。四本锁定为 `F0/CS90S/CS60S/CS90R`。不替 S20，不设硬闸，不扫 θ/N/k。已持仓不因排序键变差而平。无论记正与否都不换冠。

**假设（一句）**：在 SHARPE20 短名单内按 Clenow 年化斜率×R² 次级排序、不砍席，相对 F0 能盖住回撤，且 2020–22 与 2023–26 两窗都不踏空。

设计日 2026-10-27。刀 ID：`CLENOW-S20-SECONDARY`（斜率族 knife #5，一次一把）。本目录是准则、书、H1、证伪尺子和执行交接，不含批跑结果。研究池。`champion_swap = false`。本 PR 不跑回测主循环、不写 NAV、不写 `out/`。`run.py` 是拒绝执行的 stub。取席公式的可执行规格在 `band.py`，夹具在 `test_band.py`。

这是 **AG40S / #4 那条「先 S20 短名单、再按另一键重排」的机制，键换成 #1 已经定义过的 Clenow score**。#1 用这条分数替换 S20，三本后段踏空。#4 用无方向的 R² / ER 在同一条带里重排，全样本有两本盖住，2023–26 三本都踏空。本刀只问：同一条 Clenow score 放进 S20 带内当次级键，后段还踏不踏空。不换冠。

## 面

| 项 | 冻结值 |
|----|--------|
| 书 | B45：`risk_on = (b ≥ 0.45)`；`spike_ft` max5；E0；TV25（σ\* = 0.25） |
| 填席宇宙 | SHARPE20。近 20 个日收益均值/标准差 × √252，窗止于信号日前一交易日。先排 S20，再在短名单内重排 |
| 被测机制 | 短名单次级排序（本卡）。席位仍 max5、腿内等权。无硬闸 |
| 信号 / 成交 | 周五 ≥14:30 / 当日收盘 |
| 成本 / 杠杆 | 0.2% RT；`L = min(1, σ* / max(σ20, σ60))`，故 L≤1 |
| 窗 | 2020-01-03 → 2026-10-23 |
| 锚 | `LIVE1430-B45-S20-max5` = **131.6% / −18.8% / Calmar 0.70** |
| 锚提交 | `05f0f8a4f778fde886f3e7b2976646ff4b7d777b`（`SPIKE-S20-BTHETA-GRID-LIVE1430`） |
| 延窗锚出处 | PR#28 `SPIKE-S20-EXTEND-REBASE-LIVE1430` 主表 `LIVE1430-B45-S20` 行：ret 131.6%、maxDD −18.8%、CAGR 13.1%、Calmar 0.70；2020–22 为 18.9% / −16.0% / 0.37；2023–26 为 94.8% / −13.8% / 1.39；avgL 0.84；空仓周 43.1%。PR#104 / #106 / #108 / #110 同针重跑 F0，贴上同一组 131.6% / −18.8% / 0.70。本刀不重跑延窗 |
| 日历 | 349 个信号周；有前向持有的周 **T = 348**（去掉最后一根哨兵） |
| 宇宙 | AUM≥2 亿，324 只 |

同一名字在另一条引擎上是 158.3% / −15.9% / Calmar 0.94（TV 网格 `f2b681df7b015050eea38a270b55c57e0817451b`）。那是跑错引擎的识别标记。F0 必须先贴上 131.6% / 0.70，贴不上就停。

nob_ref 134.0% / −18.9% / 0.70、KB 对照 135.0% / −18.3% / 0.74、PR#67 旁注 131.9% / −18.8% / 0.70 都不是本刀 F0。

Calmar 沿用 btheta `stats_full`：日净收益 `cumprod`，`ret = q[-1] − 1`，`maxDD` 为相对运行峰值的最小回撤，`CAGR = (1+ret)^(365.25/n) − 1`，`n` 为收益序列首尾时间戳的日历天数，`Calmar = CAGR / |maxDD|`（`maxDD < 0` 才有定义）。

出场锁 E0。`NO-E0` 已判不重开。

## 已闭合的路径结论（本卡不改）

硬否决和替填席容易在 2023–26 踏空。次级排序不能从 accel 泛化到无方向的路径质量键。**只有 AG40S（S20 带内按 accel 重排）记过正**，而且只是旁注，不升格成面、不进本刀四件套、不作尺子右侧。

| 书 | 宇宙 | 键 | 机制 | 已发表（相对同针 F0） | 本刀 |
|----|------|----|------|----------------------|------|
| F0 | S20 取席 | SHARPE20 | 面 | 131.6% / −18.8% / 0.70 | 锚，重跑只为贴针 |
| AG40S | S20 短名单 `band_k` | accel(40+40) | 次级排序 | **235.6% / −14.8% / 1.32**；2020–22 44.6%；2023–26 132.1%；Jaccard 0.389；PR#106 记正旁注 | **带形模板**。不进四件套，不作 F0，不作尺子右侧，不升格 |
| AG40 / AG20 | S20 后丢掉 `accel≤0` | accel | 硬闸 | 125.0% / −17.8% / 0.71（后段踏空）；144.3% / −18.1% / 0.78（前段踏空） | 不重开 |
| SR90 | 用 Clenow **替换** S20 | N=90，`slope_ann × R²` | 换键 | 72.8% / −21.5% / 0.39；2023–26 33.5%；PR#104，H1_HOLD | 同一条代数，**本刀只排序、不替席** |
| SR60 | 用 Clenow **替换** S20 | N=60，`slope_ann × R²` | 换键 | 122.0% / −19.4% / 0.64；2023–26 59.1%；H1_HOLD | 同一条代数、同一窗，**本刀只排序、不替席** |
| SR90K2 | 用 Clenow **替换** S20 | N=90，`slope_ann × R²²` | 换键 | 73.9% / −21.7% / 0.39；2023–26 29.8%；H1_HOLD | 有这条变体。**不进本刀**，见下节 |
| RF50 / ER20 / AND50 | S20 后硬下限 | R² / ER | 硬闸 | 102.9 / 90.5 / 56.2，PR#108，H1_HOLD | 不重开 |
| R290S / ER20S / COMBOS | S20 短名单 | R² / ER / 等权 z | 次级排序 | R290S 132.1% / −15.6% / 0.84（Jaccard 0.399）；ER20S 127.1% / −18.4% / 0.70（0.741）；COMBOS 131.0% / −15.1% / 0.87（0.487）。R290S 与 COMBOS 全样本盖住，三本 2023–26 为 77.5% / 71.9% / 72.0%，对照 F0 94.8%，都踏空。PR#110，H1_HOLD | 不重开。说明次级排序不能泛化到无方向路径键 |
| **CS90S** | S20 短名单 | Clenow(N=90) | 次级排序 | 未测 | **主簿** |
| **CS60S** | S20 短名单 | Clenow(N=60) | 次级排序 | 未测 | 邻档 |
| **CS90R** | S20 短名单 | 年化斜率，不乘 R² | 次级排序 | 未测 | 第三本 |

#1 原文（PR#103 设计 / PR#104 执行）：`family_verdict=H1_HOLD`。缺失 score 的名字不进池，空席空着，禁止回退 S20。那是替席规则。本刀的缺失名字留在带尾，可以占席。两条不能混。

#4 原文（PR#109 设计 / PR#110 执行）：`family_verdict=H1_HOLD`。R² 高、β<0 的平滑下跌在 #4 里排在带首。本刀的 score 带符号：`slope_ann < 0` 时 score 为负，排在任何正 score 之后。方向仍先由 `spike_ft` + SHARPE20 决定能不能进带。

尺子右侧只有**本次运行的 F0**。AG40S 的 235.6% 只说明「短名单重排这条路在 accel 上记过正」，不是本刀要超过的横杆。

## 第三本：冻结 CS90R

#1 有 k 加权变体。SR90K2 的公式是 `slope_ann × (R²)^2`，k=2，当时做的是**替席**。刀单允许「有这条变体就把同公式挪成次级键」。本卡不挪。四本写死为 `F0/CS90S/CS60S/CS90R`。

| 候选 | 形状 | 本卡 |
|------|------|------|
| CS90K2 | 带内 `slope_ann × (R²)^2`，与 #1 SR90K2 同公式，只改成次级排序 | **不跑** |
| CS90×accel | CS90S 同分或近分时用 accel(40+40) 断 | **不跑** |
| CS90S-top | 只在带内 S20 最前的 `slots` 名上再排一次，键仍是 CS90S | **不跑**。与主簿同键且带外进不来时，集合贴近 F0，问不出增量 |
| **CS90R** | 同一条 S20 带内只按 `slope_ann = e^{β·252} − 1` 降序，不乘 R² | **冻结** |

不选另外三本的理由（设计选择，写在跑批之前）：

1. k=2 仍是 `slope_ann × (R²)^k` 的幂次。本族禁止 θ / N / k 插值。#1 已经把 k=2 当替席跑完，后段 29.8%，H1_HOLD。再把幂次搬进次级键，问的不是「R² 到底要不要乘」。
2. CS90×accel 的「近分」要一个 ε。ε 没有在刀单里点名。冻 ε 就是新的 θ。只断精确同分时，连续的 score 几乎不触发，第三本与 CS90S 惰性。accel 硬闸是 #2 已证伪的主簿。#4 用同样的理由否掉了 R290A。
3. CS90S-top 把 `band_k` 收成 `slots`。短名单消失，重排的集合就是 F0 会买的那一组。夹具要求 `slots=1` 时带长为 3，带外最高分进不来，带内第三名可以因为 score 坐上唯一的席。`band_k = slots` 过不了这支夹具。
4. CS90R 问的是还没问过的事：#1 乘 R² 是为了罚跳空和噪声。在 S20 带内，只按年化斜率排（CS90R）和乘上 R² 再排（CS90S）如果同向，R² 权重是多余的；如果分叉，才知道权重有没有用。无新 θ，无硬闸，带形与 AG40S 相同。

CS90R 不把 R² 乘进键。实现写成独立的 `slope_ann_sort`，键就是 `slope_ann`。不要做成可调的 k，也不要写成 `slope_ann × 0`。

accel、ER、无方向 R² 地板都不进本刀任何一本书。不 import `research/clenow-slope-r2-fill/run.py`（那份会替席、会丢缺失），不 import `research/accel-gate/run.py`，不 import `research/er-r2-floor/run.py`，不 import `research/r2-er-secondary/run.py`。回归代数以本目录 `band.py` 的 `ols_clenow` 为准。

## 精确规则

### 池

每个信号周五 `t`，先看 `risk_on = (b ≥ 0.45)`。`risk_on` 为假：与 FACE 相同，E0 / `breadth_off` 出清，本周不填席。

`D_t` = 当周同时满足：`in_play` 且 `in_play_kind == spike_ft`；不是 `box_pending` / `pending_second_week`；有有限 SHARPE20；在 AUM≥2 亿研究池内。Clenow 缺失**不**把名字剔出 `D_t`。

`C_t` = `D_t` 减去当前持仓（与 btheta `build_cands(..., skip=set(positions))` 相同）。重排只发生在 `C_t` 上。

S20 坐在针 `05f0f8a4` 的 `research/cloud_batch/SPIKE-S20-BTHETA-GRID-LIVE1430/run.py`：

| 符号 | 行附近 | 本刀 |
|------|--------|------|
| `sharpe_n_on` | 160–178 | 不动。四本都仍用它产生 S20 序 |
| `sharpe_key` | 82–84 | 短名单的第一序，不动 |
| `build_cands` | 261–284 | 出口在短名单内重排；`skip=已持仓` 不动 |
| `simulate` 填席 | 339–349 | 仍 `require_sharpe=True`，`slots = max_pos − 已持仓` |

不把 `sharpe_n_on` 换成 `clenow_score_on`。breadth / spike / max5 / E0 / TV / 时钟 / 成本 / 宇宙不动。

### 短名单（与 AG40S、#4 同一条带，换键）

```
slots = max_pos − 已持仓
若 slots ≤ 0：本周不新开（与 F0 相同）
band_k = max(2 · slots, slots + 2)
band = C_t 按 sharpe_key 的前 band_k 名（必须 S20 有限）
take = 按本书的键重排后的前 slots
```

`slots=5` → `band_k=10`；`slots=4` → `band_k=8`；`slots=1` → `band_k=3`。`slots≤0` 时不使用这条公式。

这条带两头都收死：

- 只重排当前会进席的 `slots` 名：集合与 F0 相同，整本惰性。禁止。这就是被否掉的 CS90S-top。
- 在全部 `C_t` 上按 Clenow 重排：低 S20 的名字可以凭一条陡的斜率跳进席。那是 #1 替席的软版本。禁止。

带外的名字本周不能新开。带内的名字即使键为负、很小或缺失，也只是排到带尾，**不从带里删掉**。过不了「陡」的席位仍由带尾的 S20 名字坐下，不空着。

### 回看：Clenow

价格与 `sharpe_n_on` 同一条日 qfq 收盘。截止：**信号周五的前一交易日**。信号日当天收盘不进回归。`(signal − last_bar).days > 5` → 缺失。`t_i` 是这 n 根的顺序下标，不是日历日。年化只用 252。与 #1 SR90 / SR60 同一条代数；本刀**不**调用 #1 的 `require_clenow` 丢席。

```
ols_clenow(px[0…n−1]):
    根数 < n，或任一收盘 ≤0 或非有限 → None
    y_i = ln(P_i)                         # 最老→最新
    t_i = i                               # 交易日下标，不是日历日
    β = Sxy / Sxx
    R² = Sxy² / (Sxx·Syy)
    Sxx≤0 或 Syy≤0 或非有限 → None        # 全平 → 缺失，不是 0
    β 或 R² 非有限，或 R² 落在 [0,1] 外超过 1e-12 → None
    否则 R² clip 到 [0,1]
    slope_ann = exp(β · 252) − 1         # 不是 (1+β)^252，不是 (1+β)^252−1，不是 raw β
    非有限 → None
    score = slope_ann × R²               # k=1。没有 k 参数
    返回 β、R²、slope_ann、score

clenow_on(closes, d, n):
    sub = closes[: d − 1 日]
    (d − sub 末根).days > 5 → None
    最后 n 根，不足 n → None
    返回 ols_clenow
```

| 书 | 窗 | 排序用 | 不算进键 |
|----|----|--------|----------|
| F0 | — | 无 | 不计算 Clenow |
| CS90S | N=90 | `score` | 不单独用 slope_ann 排序 |
| CS60S | N=60 | `score` | 同上 |
| CS90R | N=90 | `slope_ann` | R² 只披露，不乘进键 |

负的 `slope_ann` 得到负的 score，排在正 score 之后，仍然可以占带尾的席。不做 `β>0` 硬闸，不取绝对值。

### 排序键

先记下带内的 S20 下标 `s20_index`（0 = 带内 S20 最好），再排。元组升序：

```
(0 if 键有限 else 1,  −键 if 有限 else 0,  s20_index,  code)
```

精确同分先回到原来的 S20 序，再按代码升序。不用 accel 断同分。不把 score 四舍五入成分桶。

单键书：带内该键**全部**缺失 → 回退这条带的 S20 原序，取前 `slots`，`how=fallback`。有一部分缺失：有限的在前（含负数），缺失的在后，仍然取满 `min(slots, |band|)`。

CS90S 与 CS60S 的键是 `score`。CS90R 的键是 `slope_ann`。两本书用同一条 N=90 回归，所以 `n_miss_clenow` 必须相同；不同就是实现偏离。

### 持仓与出场

已持仓不因 score、slope_ann 或 R² 变差而平，也不因排到带尾而平。换仓只发生在席位空出来之后：空席从当周短名单的重排结果里补。与 F0、AG40S 相同。

出场只走 E0：`breadth_off` / `falsify` / `always_in_flip` / `left_structure` / 末日 `eod_eval`。不新增「键跌破」或「斜率变负」退出原因。

腿内等权，总暴露仍 TV25。TV 的 σ20/σ60 来自**该书自己**的过去日收益。

入口不变量：给定同一 `positions` 与同一 `C_t`，`slots>0` 且带非空时 `len(take) = min(slots, |band|)`。少填一次就记 `n_short_fills`。正确实现里这个计数是 0。全样本 `n_empty_slots` 仍可能和 F0 不同，因为入选的名字不同，之后的 E0 出场路径会分叉。那是结果，不是入口丢席。

`slots≤0` 或带为空：`how=empty`，不计入 `n_fallback_weeks`，也不计入 `n_short_fills`。

### F0

排序键关闭。`rank_fn = sharpe_key`，`sharpe_n=20`，`require_sharpe=True`。不计算 Clenow。`n_rerank = 0`，`n_miss_clenow = 0`，`n_short_fills = 0`，`n_fallback_weeks = 0`，`mean_score = 0`，`mean_slope_ann = 0`，`mean_r2 = 0`。

## 四本（含 F0，不再加）

| id | book | 填席宇宙 | 次级键 | 角色 |
|----|------|----------|--------|------|
| F0 | `LIVE1430-B45-S20-max5` | SHARPE20 | 关 | 面 / 锚 |
| CS90S | `LIVE1430-B45-S20-CS90S-max5` | SHARPE20 短名单 | Clenow score，N=90，降序，缺失置底 | **主簿** |
| CS60S | `LIVE1430-B45-S20-CS60S-max5` | SHARPE20 短名单 | 同公式，N=60，降序，缺失置底 | 邻档 |
| CS90R | `LIVE1430-B45-S20-CS90R-max5` | SHARPE20 短名单 | `e^{β·252}−1`，N=90，不乘 R²，缺失置底 | 邻档（第三本） |

四件套是 4 个文件（`REPORT.md` / `summary.json` / `table.csv` / `equity.csv`+图），主表 **4 行**。机制书 3 本，加 F0。邻档记正也不升格、不改主口径、不换冠、不进 LIVE。

不跑（做了也不进四件套）：

- CS90K2，以及任何 `k≠1` 的 `slope_ann × (R²)^k`。
- CS90×accel，以及任何「score 近分 / 四舍五入分桶 + accel tie-break」。
- CS90S-top，以及 `band_k = slots` 或 `band_k = |C_t|`。
- 用 Clenow **替换** S20，或在全部 `C_t` 上按 Clenow 重排。SR90 / SR60 / SR90K2 不重开。
- raw `β × R²`、`(1+β)^252`、`(1+β)^252 − 1`、250/260 日年化、百分数 `×100` 当另一本。
- N∈{10,20,40,70,80,100,120,125,250} 的窗插值。125/250 双窗平均。
- `β>0` 硬闸、R² 地板、ER 地板、accel 硬闸、斜率×S20 加权。
- R290S / ER20S / COMBOS / R290A / RF50 / ER20 / AND50 / AG40 / AG20。
- MOM121 / W67 / W85 / W7525，Z121，R4W，RET8/12/52，SORTINO20，SHARPE12/40。
- residual-mom、corr-dedup、skip-month、SOFT4535、NOBREADTH、B50、TV33、HYST、PT/COOL、换手惩罚、席位 max3/4/6/7。
- 510300 当 σ / L / 闸，指数 MA200，通道 overlay，ATR 仓位。

## H1

```
唯一改动：在面层 B45 + spike_ft max5 + E0 + TV25 + SHARPE20 上，
对每周信号日的 S20 短名单按 Clenow 次级排序后取席。
  主簿 CS90S：排序键 (e^{β·252}−1)×R²，N=90，降序，缺失置底。
  邻档：CS60S（同公式，N=60）、CS90R（只按 e^{β·252}−1，N=90，不乘 R²）。
  四本锁定为 F0/CS90S/CS60S/CS90R。
  填席宇宙仍是 SHARPE20 短名单。不替 S20，不设硬闸，不扫 θ/N/k。
  已持仓不因排序键变差而平。出场维持 E0。
  B、TV、席位、成本、时钟不离开面。

H1：CS90S / CS60S / CS90R 在严格尺子下相对本次 F0 全部证伪。
  任一记正 → H1 证伪（家族记一笔，不换冠、不升格）。
  全部证伪 → H1 成立。
  与 F0 逐周持仓集合相同 → 该本记「证伪·惰性」，不能记正。
  n_short_fills > 0 → 该本 BLOCKED（入口丢席，实现偏离），家族 BLOCKED。
```

事前倾向只作旁注，不写进尺子：#1 的替席和 #4 的路径质量次级排序都在 2023–26 踏空；AG40S 只说明 accel 这一个键在带内记过正。本刀默认按证伪记账。倾向写错，也不构成改窗、把第三本改回 k=2、加硬闸、或把 AG40S 写成面的理由。

## 证伪尺子

比较对象只有本次运行的 **F0**。不与 158.3% / 0.94 比，不与 nob_ref 134.0% 比，不与 KB 135.0% 比，不与 PR#67 的 131.9% 比，不与 #1 的 SR90 72.8% / SR60 122.0% / SR90K2 73.9% 比，不与 #2 的 AG40S 235.6% 比，不与 #3 的 RF50 / ER20 / AND50 比，不与 #4 的 R290S 132.1% / ER20S 127.1% / COMBOS 131.0% 比。这些数字只许出现在对照段和跳过段。

记收益为小数（131.6% = 1.316），回撤为负数。

```
Δret     = ret − ret_F0
Δ|MDD|   = |maxDD| − |maxDD_F0|
盖住     = Δret ≥ Δ|MDD|
窗过     = 该窗累计收益 ≥ F0 同窗累计收益
惰性     = (id ≠ F0) 且持仓周集合 {(周五, frozenset(codes))} 与 F0 相同
记正     = 盖住 且 2020–22 窗过 且 2023–26 窗过 且 非惰性
证伪     = 其余，含任一字段缺失或 NaN
证伪·惰性 = 惰性
```

相等算盖住，相等算窗过。Calmar 只展示，不进尺子。没有 0.9×，没有 −2pp。

| 窗 | 切片 |
|----|------|
| 2020–22 | `2020-01-01` ≤ date ≤ `2022-12-31` |
| 2023–26 | date ≥ `2023-01-01`，直到 2026-10-23 |

两窗都报 ret / maxDD / Calmar。判定只用窗内 ret。2023–26 必须 ≥ F0 同窗。这是硬条件。

### 只披露、不翻转旗标

- `n_entries`：新开+换入次数
- `n_rerank`：实际填入、但不在当周纯 S20 头部 `slots` 里的（周五, 代码）次数。F0 为 0
- `n_miss_clenow`：过了 spike、有信号价、在 `C_t` 中，但该书的 `clenow_on` 为 None 的次数。按 `C_t` 全计，不按「刚好在带内」计。F0 为 0。CS90S 与 CS90R 必须相等
- `n_empty_slots`：各周 `max(0, slots − 实际新开数)` 之和。可以与 F0 不同
- `n_short_fills`：`slots>0`、带非空、且 `len(take) < min(slots, |band|)` 的周数。四本都应为 0。大于 0 是实现偏离，不是机制证伪
- `n_fallback_weeks`：带内排序键全部缺失、从而整段带回退 S20 的周数。`how=empty` 不计入。F0 为 0
- `mean_score`：实际新开名字上排序键的均值。CS90S / CS60S 是 score；CS90R 是 slope_ann。F0 写 0。缺失不进均值；样本空写 0
- `mean_slope_ann` / `mean_r2`：实际新开且该项有限的均值。F0 写 0。CS90R 仍披露 `mean_r2`，但排序不看它
- `mean_abs_D`、`hit_rate`、`win_size`、`jaccard_vs_f0`：定义同 #4。hit-rate 与 win-size 同时更好只写旁注，不能把证伪改成记正

惰性只看持仓集合，不看 `n_rerank=0` 的旁路。排序书 `n_empty_slots` 接近 F0 是常态（入口不砍席），**不能**据此记惰性。

### 锚点门（先于家族句）

F0 相对已发表 `LIVE1430-B45-S20-max5`（SHA `05f0f8a4f778fde886f3e7b2976646ff4b7d777b`）：

| 量 | 锚 | 允许偏差 |
|----|----|----------|
| ret | 1.316 | 0.005 |
| maxDD | −0.188 | 0.002 |
| Calmar | 0.70 | 0.02 |
| 日历周 | 349 | 0 |
| 持有周 T | 348 | 0 |
| 终点 | 2026-10-23 | 必须相同 |
| AUM≥2 亿只数 | 324 | 0 |

超出：`anchor_pass=false`，`family_verdict=BLOCKED`，各格 `BLOCKED`，仍输出四件套。不把 F0 改去贴 158.3% / 0.94，也不去贴 134.0% / 135.0% / 131.9%。

针或数据目录缺失：不写四件套，退出码非 0。

### 实现门（先于家族句）

`impl_pass=false` 当任一成立：某本 `n_short_fills > 0`；id / `mode` / `n` 与 `SPEC.json` 不一致；CS90S 与 CS90R 的 `n_miss_clenow` 不等；任一本书使用了数值阈值或 k≠1 的幂；出现第 5 个 id；出现「键变差」退出原因。此时 `family_verdict=BLOCKED`。格子可以写尺子算出来的数，但 verdict 写 `BLOCKED`，不得记正，也不得把丢席记成「硬闸证伪」。

### ATTRIBUTION 门（先于家族句）

五段必须同时有。缺一项：`attrib_pass=false`，`family_verdict=BLOCKED`，REPORT 写「ATTRIBUTION 未齐，不得判卷」。不翻转旗标，不发明 Brinson。

| 段 | 最低交付 |
|----|----------|
| (a) 机制 | 一句：只在 S20 短名单内做了 Clenow 次级排序。列出未动的 B45 / spike_ft / max5 / E0 / TV25 / SHARPE20 宇宙 / Fri≥14:30 / 0.2%RT / AUM≥2。写明没有替席、没有硬闸、没有 θ/N/k，第三本是 CS90R |
| (b) 席位重叠 | CS90S / CS60S / CS90R 各自 vs F0 的 Jaccard，按（周五, 代码） |
| (c) 窗 Δ | 2020–22 / 2023–26 的 Δret 与是否踏空 |
| (d) 换手 / 空仓周 | 相对 F0，并报 `n_empty_slots` |
| (e) 名字·年份和大赢/大亏段 | 每年 ADD/DROP 前 5 代码；每本一条 BIGWIN、一条 BIGLOSS（起止日、年份、Δcum_ex、book 独有 / F0 独有代码）。真惰性写「与 F0 席位逐周相同，无名字可列」 |

支持 CSV：`out/entries_diff_by_year.csv`、`out/segment_attribution.csv`。它们不替代四件套。字段与切段算法见 `COMPOSER.md`。

### 家族一句

| 条件 | REPORT 证伪段 |
|------|----------------|
| `anchor_pass` 为 false | 锚点未过。家族结论 BLOCKED。不换冠。 |
| `impl_pass` 为 false | 入口丢席或书规格偏离。家族结论 BLOCKED。不换冠。 |
| `attrib_pass` 为 false | ATTRIBUTION 未齐，不得判卷。家族结论 BLOCKED。不换冠。 |
| 三本排序书全是证伪（含惰性） | H1 成立：S20 短名单上的 Clenow 次级排序无记正。不换冠。 |
| 至少一本记正 | H1 证伪：点名格子。不换冠，不升格，不进 LIVE。 |

`family_verdict` 只允许 `H1_HOLD`、`H1_REJECT`、`BLOCKED`。

## 跳过（已闭合，禁止重开，禁止当格子）

数字只引用已发表主表。本卡不重跑、不把它们改写成预测。

| 已闭合 | 仓库怎么写 | 与本刀 |
|--------|------------|--------|
| AG40S | PR#105/#106：235.6% / −14.8% / C1.32，两窗都过，Jaccard 0.389，记正旁注 | 带形模板。不是格子，不是 F0，不是尺子右侧 |
| AG40 / AG20 | 硬闸证伪。家族句 H1_REJECT 只因 AG40S | 本刀不算 accel |
| SR90 / SR60 / SR90K2 | PR#103/#104：72.8 / 122.0 / 73.9，后段 33.5% / 59.1% / 29.8%，H1_HOLD | 同一条代数的替席。本刀不换 S20，也不把 k=2 挪进带内 |
| RF50 / ER20 / AND50 | PR#107/#108：102.9 / 90.5 / 56.2，H1_HOLD | 硬闸。本刀不设阈值 |
| R290S / ER20S / COMBOS | PR#109/#110：132.1 / 127.1 / 131.0，2023–26 全踏空，H1_HOLD | 无方向路径键的次级排序。本刀换的是带符号的 Clenow |
| ER10-T30/T40/T50 | PR#80/#83：98.7 / 69.6 / 88.5，H1_HOLD | N=10 阈值扫描 |
| RET8 / RET12 / RET52、MOM121、Z121、R4W | 见 #1 DESIGN 跳过表。后段踏空或对照引擎不同 | 不重开 |
| residual-mom、corr-dedup | PR#90 / #91，H1_HOLD，同针 F0 131.6% | 不去均值，不做 ρ\* |
| SORTINO20、SHARPE12/40、SOFT、skip-month、MA200 | 已判或不是本刀的问 | 不重开 |

## 红线

不写 `strategy_exec` / `LIVE_OPS` / `champion_mast` / 实盘 / 固收+ / 红利袖。不把 HYST、止盈、冷静、R 闸、软门、宇宙切片、现金债、Clenow 替席、k=2、加速度硬闸、AG40S 升格、ER/R² 地板、R²/ER 次级排序、510300 叠进这 4 本。不在看到结果之后改排序键、第三本、尺子和锚。研究池 ≠ 实盘池。不换冠。`champion_swap=false`。不合并。

## 报告四件套

执行方 `REPORT.md` 五段，顺序固定。首行贴本卡拍板问句，接着原样贴 H1 代码块。

1. **准则原文**：精确规则 + H1 + 尺子的可执行摘要。
2. **实现要点**：短名单次级排序、`band_k`、第三本是 CS90R、与锚的偏差、`n_rerank` / `n_miss_clenow` / `n_short_fills`。
3. **主表**：F0 + 三本。列见 `COMPOSER.md`。
4. **ATTRIBUTION**：独立 `## ATTRIBUTION`，(a)–(e) 齐。一句：ATTRIBUTION 不进 `verdict`。
5. **一句判词**：`记正` / `证伪` / `证伪·惰性` / `BLOCKED`，点名未过的闸；句末「不换冠」。

本设计 PR 交 `DESIGN.md`、`SPEC.json`、`COMPOSER.md`、`band.py`、`test_band.py` 和 stub `run.py`。四件套由执行方另开分支生成。

## 设计期夹具

`test_band.py` 锁取席，不锁净值。最低一条：同一条 S20 带、同一个 `slots`，CS90S 的取席顺序随 score 改变；带外更高的 score 进不来。另外锁住：缺失置底仍可入选、低分和负分不删名、全缺失回退 S20、直线价格走出 `e^{β·252}−1` 而不是 `(1+β)^252`、CS90R 在 R² 很低的陡斜率上可以和 CS90S 换席、CS60 的窗可以和 CS90 换席、`run.py` 直接退出且不写 `out/`。夹具不过，执行方不得写四件套。
