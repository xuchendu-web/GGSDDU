# Composer 交接 · overfit-guards

照此实现。缺参数就停，不要补一套「合理默认」。本刀是研究池上的有限 13 本书，加一次路径拼接。不要再开网格，不要循环插值。

## 跑完之后的四件套

写到这些路径，不多也不少：

| 文件 | 内容 |
|------|------|
| `research/overfit-guards/out/REPORT.md` | 首行贴 DESIGN 的拍板问句。然后锚点门、13 本主表、DSR 输入与结果、6 条路径的 Calmar、21 个 split 的选择记录、证伪段、红线 |
| `research/overfit-guards/out/summary.json` | 下面的字段 |
| `research/overfit-guards/out/table.csv` | 列顺序固定，见下 |
| `research/overfit-guards/out/equity.csv` | 日净值 |
| `research/overfit-guards/out/equity_curve.png` | 对数轴。FACE 黑线、线宽 2.2；其余 12 本灰色细线；6 条选择路径用虚线 |

支持文件可以有 `holdings_*.csv`，不替代四件套。脚本放在 `research/overfit-guards/run.py`。夹具不过，或锚不过而你改了公式，都不要写四件套——锚不过时四件套仍要写，但 `family_verdict` 必须是 `BLOCKED`。夹具不过：退出码非 0，四件套一个都不写。

`summary.json`：

```json
{
  "batch": "overfit-guards",
  "champion_swap": false,
  "crown": "NO",
  "source_sha": "05f0f8a4f778fde886f3e7b2976646ff4b7d777b",
  "sample": ["2020-01-03", "2026-10-23"],
  "anchor_pass": true,
  "anchor": {"ret": 1.316, "maxDD": -0.188, "Calmar": 0.70, "n_weeks": 349, "T": 348, "n_codes": 324},
  "N": 13,
  "N_assumption": "BTHETA 4 + TV 6 + MAXSEAT 5, face counted once",
  "V_sr_week": 0.0,
  "sigma_sr_week": 0.0,
  "sr_star": 0.0,
  "sr_week_face": 0.0,
  "sr_ann_face_display": 0.0,
  "gamma3": 0.0,
  "gamma4": 3.0,
  "DSR": 0.0,
  "PSR0": 0.0,
  "rho_bar": 0.0,
  "N_eff": 0.0,
  "DSR_eff": 0.0,
  "DSR_max": 0.0,
  "dsr_max_id": "FACE",
  "FLAG_DSR": false,
  "cpcv": {"G": 7, "k": 2, "splits": 21, "paths": 6, "purge_weeks": 1, "embargo_weeks": 4},
  "group_sizes": [50, 50, 50, 50, 50, 49, 49],
  "path_calmars": [0.0, 0.0, 0.0, 0.0, 0.0, 0.0],
  "path_calmar_median": 0.0,
  "calmar_face": 0.70,
  "FLAG_CPCV": false,
  "n_splits_face_selected": 0,
  "family_verdict": "HOLD",
  "positive_ids": []
}
```

`family_verdict` 只允许 `HOLD`、`OVERFIT`、`BLOCKED`。`anchor_pass=false` 时必须是 `BLOCKED`，两面旗都为 false，DSR 字段填 null。上面的数字是形状；`HOLD` 不要照抄，以 DESIGN 的尺子为准。`positive_ids` 恒为空：本刀不记正、不升格。

`table.csv` 两种 `kind`，列相同，没有的格子留空：

`kind,id,theta,maxN,sigma,ret,maxDD,CAGR,Calmar,sr_week,sr_ann_display,gamma3,gamma4,in_dsr,in_cpcv,path,train_pick,split,test_calmar_face,test_calmar_selected`

- `kind=trial`：13 行，`id` 用 DESIGN 的表。`in_dsr` 全是 `true`。邻档 7 本 `in_cpcv=true`，另外 6 本为 `false`。
- `kind=path`：6 行，`id` 为 `P0`…`P5`，`path` 为 0…5，`Calmar` 为该路径的 `stats_full`。
- `kind=split`：21 行，`id` 为 `S00`…`S20`（字典序），`train_pick` 为选中的书 id，`test_calmar_face` 与 `test_calmar_selected` 为该测试窗的 Calmar。

布尔写 `true` / `false`。

`equity.csv` 列：`date,book,nav`。`nav` 从 1 起，`cumprod(1+r)`。`book` 取 13 个 trial id，再加 `P0`…`P5`。

## 引擎从哪 fork

只读针：

`05f0f8a4f778fde886f3e7b2976646ff4b7d777b`
`research/cloud_batch/SPIKE-S20-BTHETA-GRID-LIVE1430/run.py`

数据与该提交的 `research/cloud_batch/CLOUD-BATCH-2026-10-26/`。`LIVE_PHASE`、成本、TV、填席都从这份 `run.py` 来。`stats_full` 原样调用，不要重写 CAGR。

新脚本在 `research/overfit-guards/run.py`。不改 btheta 分支上的原文件。数据缓存不要提交进本 PR。`summary.json` 的 `source_sha` 写实际载入的提交；载入的不是 `05f0f8a4` 就停。

本机解释器 `D:\python\python.exe`。云端用 `python3`。

13 本书在同一次进程里跑完：只改 `θ`、`max_pos`、`SIGMA_STAR`。持仓、成本、E0、SHARPE20、周五 14:30 成交保持与针一致。TV 的 σ20/σ60 用**这本书自己**的过去日收益，与 btheta 的 `run_live_tv` 相同。

## 冻结参数

| 名 | 值 |
|----|----|
| `EVAL_START` / `END_S` | `2020-01-03` / `2026-10-23` |
| 宇宙 | `universe_replace_only_436.csv`，`aum >= 2`，代码 zfill 6 |
| 信号价 | `fri_1430_through_20261023.csv` |
| 宽度 | `holdings_ro2_extended.csv` 的列 `b`。`risk_on = b is not None and b >= θ`。不用文件里现成的 `risk_on` 列 |
| 日历末日 | `risk_on` 强制 false |
| spike | `in_play` 且 `in_play_kind==spike_ft` |
| 填席 | `sharpe_n=20`，`require_sharpe=True` |
| 退出 | E0 |
| 成本 | `COST_SIDE=0.001` 且 `LIVE_COST_RT=0.002`，两处都留 |
| 杠杆 | `LCAP=1` |
| 周频 | T=348 个持有周。最后一根没有前向收益的信号周五不进 T |

变体不在这 13 个 id 里：退出码非 0，不写四件套。

## 周收益、矩、DSR

持有周 `i` 的周收益 = 该周内日净收益的 `∏(1+r)−1`。日净收益来自 fork 后的 `r`（已含 TV 与 0.2% RT）。13 本的周索引必须对齐，否则 `BLOCKED`。

```
SR = mean / sample_std(ddof=1)
m2, m3, m4 的除数是 T，不是 T−1
γ4 是 m4/m2^2，正态为 3
V = sample variance of the 13 weekly SRs, ddof=1
SR* = sqrt(V) * z_max(13)
零假设均值 = 0
```

`z_max` 与 DSR 的式子在 `DESIGN.md`。实现用 `scipy.stats.norm`。γ_E = `0.5772156649015329`。

夹具（观测频率，先跑）：

| 名 | 输入 | DSR 应落在 |
|----|------|------------|
| 论文 N=100 | 年化 SR 2.5、年化试验方差 0.5、250 观测/年、T=1250、γ3=−3、γ4=10；SR 与 σ_SR 各除以 √250 | [0.9003, 0.9005] |
| 论文 N=46 | 同上，只改 N | [0.9504, 0.9506] |
| 正态 N=88 | 同上但 γ3=0、γ4=3、N=88 | [0.9504, 0.9506] |

夹具的 `σ_SR = sqrt(0.5/250)`，`SR = 2.5/sqrt(250)`，均值项 0。任一夹具出界：退出码非 0，不写四件套。

判决：`FLAG_DSR = (DSR < 0.95)`。`DSR_max` 把同一 V、同一 N 用到 13 本中 `SR` 最大的那本（它自己的 γ3、γ4）。并列时取 DESIGN 表里更靠前的 id。`DSR_max` 不参与 `FLAG_DSR`。

`N_eff = 1 + (1 − ρ̄) * 12`，ρ̄ 为 13×13 相关矩阵的非对角平均。`DSR_eff` 只披露。

禁止把年化夏普代进 DSR。禁止用日频 T 做判决。禁止把 `pandas` 的超额峰度当作 γ4。

## CPCV

邻档与组切片以 `DESIGN.md` 为准。选择菜单只有 FACE、B40、B50、TV22、TV28、S4、S6。

```
splits = list(itertools.combinations(range(7), 2))  # 21，字典序
```

对每个 split 的每个测试组 `[a, b]`（b 为该组最后一个周下标）：

- 训练补集中删掉周 `a-1`（若存在且仍在训练段）
- 训练补集中删掉周 `b+1` 到 `b+4`（若存在且仍在训练段）

训练 Calmar：这些周里的日收益，保留原时间戳，调用 `stats_full`。非有限 Calmar 排最后。并列：训练 `ret` 更高者优先，再按 FACE、B40、B50、TV22、TV28、S4、S6。

路径 m = 0…5：组 g 使用「含 g 的 split 清单」的第 m 个 split 所选出的书，填入该组的日收益。接成一条带原时间戳的日收益，`stats_full` 得到路径 Calmar。

```
非有限路径 Calmar 排序时当作 −∞
median = 升序第 3 与第 4 个的算术平均
FLAG_CPCV = median 非有限，或 median < 0.5 * Calmar_FACE
```

21 行短窗 Calmar 写入 `kind=split`，不参与旗标。面自己的 6 条路径会与全样本重合；选择路径不重合才说明菜单在换书。`n_splits_face_selected` 照实填写。若它等于 21，路径 Calmar 应与面的全样本 Calmar 一致（绝对差 ≤ 1e-9），否则实现有误，退出码非 0，不把这种情况写成 `HOLD`。

## 锚点不过时的写法

面先与 DESIGN 的锚比较。不过：

- 四件套仍写完，13 本数字照实
- `anchor_pass=false`，`family_verdict=BLOCKED`，两面旗为 false，DSR 相关字段为 null
- REPORT 写明面的实际 ret / maxDD / Calmar，以及它更接近 131.6/0.70 还是 158.3/0.94
- 停止。不去调成本、不去换宽度、不去贴 TV 网格

## 实现时不要做的事

- 不要跑第 14 个参数向量，不要跑 B42、B48、σ\*=0.23、maxN=8。
- 不要把 TV 网格的 158.3% 当成锚。
- 不要用日频夏普做 `FLAG_DSR`。
- 不要用 `N_eff` 或 `DSR_max` 覆盖 `FLAG_DSR`。
- 不要用 21 个短测试窗的 Calmar 覆盖 `FLAG_CPCV`。
- 不要把 MF-HOLD、TSMOM、CSMOM、DUAL-MOM、止盈、冷静、HYST 写进同一个 `run.py`。
- 不要改 `strategy_exec`、`LIVE_OPS`、`champion_mast`、固收+、红利袖。
- 不要在看到结果之后改 `DESIGN.md` 的 N、邻档、0.95 和 0.5。

## 拍板问句（REPORT 首行，原样）

请拍板：维持面层 B45 + spike_ft max5 + TV25 + SHARPE20，DSR / CPCV 无论是否标过拟合都不换冠。
