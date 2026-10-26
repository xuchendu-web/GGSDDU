# Composer 交接 · walk-forward-oos

照此实现。缺参数就停，不要补一套「合理默认」。本刀是**一条冻结路径 + 四种切开协议**。不要再开网格，不要在训练窗里挑 TV / θ / maxN，不要循环插值。

本 PR 的设计分支只交 `DESIGN.md` 与本文件。执行方另开分支写 `run.py` 和四件套。**本文件被执行之前禁止发明净值。**

## 0. 这不是 PR#54 的重跑

| 刀 | 假设 | 本卡 |
|----|------|------|
| PR#54 `research/RESEARCH-WF-OOS-B45-FACE/` | 训练窗按 Calmar 轻调 TV∈{22,25,28,33} | **SKIP**。不要 `import` 它的 `run_wf_oos.py` 当主循环，不要把它的 `wf_result.json` / 主表数字写进本卡 `out/` |
| 本卡 | 面全冻结；OOS = 冻结路径切片 | 只 fork btheta 针回放 **一次** F0，再按 DESIGN 切折 |

`inventory.skipped` 必须包含 `RESEARCH-WF-OOS-B45-FACE`（若工作区或远程分支看得到该目录）。没碰到就写空数组，不要假装读过。

也不要重跑：CLOUD-BATCH（PR#23/24/27/28）、MOM121、RET 填席、corr-dedup（PR#89/91）、residual-mom（PR#87/90）、DSR/CPCV（PR#71/72）。

## 1. 库存与针（先于切折）

| 用途 | 首选 | 回退 |
|------|------|------|
| 引擎针 | `05f0f8a4f778fde886f3e7b2976646ff4b7d777b` 的 `research/cloud_batch/SPIKE-S20-BTHETA-GRID-LIVE1430/run.py` | `git show` 该提交。不要 `git checkout` 到 btheta 上改原文件 |
| 数据 kit | `research/cloud_batch/CLOUD-BATCH-2026-10-26/` | `origin/cursor/s20-tv-grid-live1430-26c5` 或 `origin/cursor/btheta-grid-live1430-87d9` 同目录 |
| 研究池 | kit `universe_replace_only_436.csv`，`aum >= 2`，代码 zfill 6 | 同上 |
| 宽度 | `holdings_ro2_extended.csv` 列 `b`。`risk_on = b is not None and b >= 0.45`。不用该文件里现成的 `risk_on` 列 | 同上 |
| 14:30 | `fri_1430_through_20261023.csv`；`qfq_1430 = price_1430 × (日 qfq / sina)` | 同上 |
| 分类缓存 | 只读 `cache_1430_snaps.json`。不重新 classify | 同上 |

工作区若没有这些路径：用 `git show` / 只读 worktree 拷到临时目录。不要用 `strategy-weekly/_kit/face_engine.py`——那是压缩突破的 68.1% FACE，不是本刀的面。不要用 PR#54 的 `face_run.py` 当针（对齐风险）。

`summary.json` 的 `source_sha` 写实际载入的提交；载入的不是 `05f0f8a4` 就停。

本机解释器 `D:\python\python.exe`。云端用 `python3`。数据缓存不要提交进执行 PR。

## 冻结参数（一次回放）

| 名 | 值 |
|----|----|
| `EVAL_START` / `END_S` | `2020-01-03` / `2026-10-23` |
| 宇宙 | `universe_replace_only_436.csv`，`aum >= 2`，代码 zfill 6 |
| 信号价 | `fri_1430_through_20261023.csv` |
| 宽度 | `holdings_ro2_extended.csv` 的列 `b`。`risk_on = b is not None and b >= 0.45` |
| 日历末日 | `risk_on` 强制 false |
| spike | `in_play` 且 `in_play_kind==spike_ft`；排除 `box_pending` / `pending_second_week` |
| 填席 | `sharpe_n=20`，`require_sharpe=True`，`max_pos=5` |
| 退出 | E0 |
| 成本 | `COST_SIDE=0.001` 且 `LIVE_COST_RT=0.002`，两处都留 |
| 杠杆 | `LCAP=1`，`SIGMA_STAR=0.25`。TV 的 σ20/σ60 用**这本书自己**的过去日收益，与 btheta `run_live_tv` 相同 |
| 周频 | T=348 个持有周。最后一根没有前向收益的信号周五不进 T |

`stats_full` 原样调用，不要重写 CAGR。日频 Sharpe：`mean(r_d) / std(r_d, ddof=1) * sqrt(252)`，rf=0。

变体不在 `{F0, WF-P10426, WF-N7826, WF-N10413, WF-N13026}`：退出码非 0，不写四件套。

## 切折（只切，不重跑）

F0 日净收益 `r_d`（已含 TV 与 0.2% RT）对齐 btheta 交易日索引。持有周 `i = 0…347` 的日切片 = 信号周五 `cal[i]` 到 `cal[i+1]` 的 `(friday_i, friday_{i+1}]`。

```python
def make_folds(T: int, train_w: int, test_w: int, step_w: int):
    assert step_w == test_w
    folds = []
    start = train_w
    while start + test_w <= T:
        folds.append({
            "train": (start - train_w, start),
            "test": (start, start + test_w),
        })
        start += step_w
    leftover = T - folds[-1]["test"][1]
    return folds, leftover
```

夹具（先于锚、先于闸；任一出界：退出码非 0，不写四件套）：

| 名 | 输入 | 应落在 |
|----|------|--------|
| 主档折数 | T=348, 104/26/26 | 折数=9；test 起点=`[104,130,156,182,208,234,260,286,312]`；leftover=10 |
| 78/26 | T=348, 78/26/26 | 折数=10；首个 test 起点=78；leftover=10 |
| 104/13 | T=348, 104/13/13 | 折数=18；首个 test 起点=104；leftover=10 |
| 130/26 | T=348, 130/26/26 | 折数=8；首个 test 起点=130；leftover=10 |
| 冻结切片 | 任取主档一折 test | 该段 `r_d` 与 F0 全样本同一索引上的值逐点相等（绝对差 ≤ 1e-15） |

禁止：每折重新 `simulate()` 再换 σ\*；test 起点清空持仓；purge/embargo 删日；用周收益近似日 `stats_full`。

OOS 拼接：各折 test 日收益按原时间戳 `concat`，一段 `stats_full`。主档 step=test，结果必须等于 F0 在周 `[104, 338)` 上的后缀 `stats_full`（Calmar 绝对差 ≤ 1e-9），否则实现有误，`BLOCKED`。

IS 前缀：周 `[0, train_w)`。主档即 `[0, 104)`。只披露。

`period_tag`：用该折 test 对应的**交易日**日期，按 DESIGN 的 WEAK / STRONG / MIX。主档折表缺 2022 探针（没有任何折的 test 与 2022 年相交）→ `BLOCKED`。

## 尺子（不要在脚本里另写）

```
锚：|ret-1.316|≤0.005 且 |maxDD+0.188|≤0.002 且 |Calmar-0.70|≤0.02
    且 n_weeks=349 且 T=348 且 end=2026-10-23 且 n_codes=324

G1 = (not isfinite(C_oos)) or (C_oos < 0.50 * C_face)
G2 = (C_face >= 0.30) and ((not isfinite(C_oos)) or (C_oos < 0.15))
G3 = abs(mdd_oos) > 1.50 * abs(mdd_face)
塌 = G1 or G2 or G3

family_verdict =
    BLOCKED      若锚不过 / 夹具不过后仍写了包则夹具应先退出 /
                 折数不对 / 训练窗动了旋钮 / OOS 不是 F0 切片
    COLLAPSE     若锚过且主档塌
    HOLD_CAVEAT  若锚过且主档未塌
```

只允许这三个 `family_verdict`。不要输出 `CONFIRMED`、`PROMOTE`、`HOLD`、`OVERFIT`。`positive_ids = []`。邻档三闸照算写入 cell，**不得**改 `family_verdict`。

Sharpe、周胜率、IS 前缀、单折 Calmar：进表，不进旗。

## 跑完之后的四件套

写到 `research/walk-forward-oos/out/`，不多也不少：

| 文件 | 内容 |
|------|------|
| `REPORT.md` | 首行贴拍板问句。接着原样贴 DESIGN 的 H1 代码块。然后锚点门、强势段注（引用 0.37 / 1.39，并写本次 OOS 日历）、主表、主档折表、三闸、证伪段、红线 |
| `summary.json` | 下面的字段 |
| `table.csv` | 列顺序固定 |
| `equity.csv` + `equity_curve.png` | 见下 |

支持文件可以有 `folds_all.csv`，不替代四件套。脚本放在 `research/walk-forward-oos/run.py`。夹具不过：退出码非 0，四件套一个都不写。锚不过：四件套仍要写 F0 实数，`family_verdict=BLOCKED`，OOS 字段填 null。

`summary.json` 形状（数字是字段，不要照抄 0.0 当结果）：

```json
{
  "batch": "walk-forward-oos",
  "champion_swap": false,
  "crown": "NO",
  "source_sha": "05f0f8a4f778fde886f3e7b2976646ff4b7d777b",
  "sample": ["2020-01-03", "2026-10-23"],
  "anchor_pass": true,
  "anchor": {"ret": 1.316, "maxDD": -0.188, "Calmar": 0.70, "n_weeks": 349, "T": 348, "n_codes": 324},
  "protocol_primary": {"id": "WF-P10426", "train_w": 104, "test_w": 26, "step_w": 26, "n_folds": 9, "leftover_weeks": 10},
  "selection_in_train": false,
  "inventory": {"engine": "btheta-05f0f8a4", "skipped": ["RESEARCH-WF-OOS-B45-FACE"]},
  "face": {"ret": 0.0, "maxDD": 0.0, "Calmar": 0.0, "Sharpe": 0.0, "CAGR": 0.0},
  "g1_threshold": 0.0,
  "g3_threshold": 0.0,
  "FLAG_G1": false,
  "FLAG_G2": false,
  "FLAG_G3": false,
  "family_verdict": "HOLD_CAVEAT",
  "h1": "主档未塌 → H1 证伪（HOLD_CAVEAT）",
  "positive_ids": [],
  "strong_period_note": true,
  "cells": []
}
```

`family_verdict` 只允许 `HOLD_CAVEAT`、`COLLAPSE`、`BLOCKED`。上面的 `HOLD_CAVEAT` 不要照抄，以尺子为准。`g1_threshold = 0.50 * face.Calmar`，`g3_threshold = 1.50 * abs(face.maxDD)`。`strong_period_note` 必须为 true（REPORT 写了分段注才许落盘）。

每个 protocol cell：

```json
{
  "id": "WF-P10426",
  "train_w": 104,
  "test_w": 26,
  "step_w": 26,
  "n_folds": 9,
  "leftover_weeks": 10,
  "oos": {"ret": 0.0, "maxDD": 0.0, "Calmar": 0.0, "Sharpe": 0.0, "CAGR": 0.0, "n_weeks": 234},
  "is_prefix": {"ret": 0.0, "maxDD": 0.0, "Calmar": 0.0, "Sharpe": 0.0},
  "g1_collapse": false,
  "g2_floor": false,
  "g3_dd": false,
  "verdict": "HOLD_CAVEAT"
}
```

F0 cell：`id=F0`，`oos` 与 `is_prefix` 都填全样本（或 `oos` 填全样本、`is_prefix` 为 null），`verdict=ANCHOR`，三闸 false。

主档 9 个 fold 另放 `summary.json.folds_primary`：

```json
{
  "fold": 0,
  "train": [0, 104],
  "test": [104, 130],
  "train_end": "YYYY-MM-DD",
  "test_end": "YYYY-MM-DD",
  "ret": 0.0,
  "maxDD": 0.0,
  "Calmar": 0.0,
  "Sharpe": 0.0,
  "period_tag": "MIX"
}
```

`table.csv` 列：

`kind,id,train_w,test_w,step_w,fold,ret,maxDD,CAGR,Calmar,Sharpe,n_weeks,leftover_weeks,period_tag,g1_collapse,g2_floor,g3_dd,verdict`

- `kind=protocol`：5 行，`fold` 空。F0 的 train/test/step 空。
- `kind=fold`：主档 9 行，`id=WF-P10426`，`fold=0…8`。邻档折若写，`kind=fold` 且 `id` 为该邻档；可省略。

布尔写 `true` / `false`。

`equity.csv` 列：`date,book,nav`。

| book | 区间 | nav |
|------|------|-----|
| `LIVE1430-B45-S20-max5` | 全样本交易日 | F0 `cumprod`，起点 1 |
| `WF-P10426` | 仅主档 OOS 交易日 | 该段 `r_d` 从 1 起 `cumprod` |
| `WF-N7826` / `WF-N10413` / `WF-N13026` | 各协议 OOS 交易日 | 同上 |

`equity_curve.png`：对数轴。F0 黑线、线宽 2.2，画全样本。四条 WF 线只从各自首个 OOS 日画起；**图上**把 WF 线乘以 F0 在该日的 nav，使视觉接上 F0（旁注「图已接水平，表内 OOS 仍从 1」）。主档 WF 用实线、线宽 1.6；三本邻档灰色细虚线。不要把 PR#54 的 TV 选择路径画进来。

## 锚点不过时的写法

- 四件套仍写完，F0 数字照实
- `anchor_pass=false`，`family_verdict=BLOCKED`，三面旗为 false，OOS 字段 null
- REPORT 写明 F0 实际 ret / maxDD / Calmar，以及它更接近 131.6/0.70、158.3/0.94，还是压缩突破的 68.1/0.31
- 停止。不去调成本、不去换宽度、不去贴 TV 网格、不去改 104/26、不去把 leftover 短折补进来凑折数

## 实现时不要做的事

- 不要在训练窗里对 TV / Bθ / maxN / 填席做 Calmar 选型。
- 不要重跑 PR#54，不要把它的 折选型表或 OOS 拼接数写进本卡 REPORT。
- 不要重开 CLOUD-BATCH、MOM121、RET 填席、corr-dedup、residual-mom。
- 不要把 TV 网格的 158.3% 当成 F0，也不要把压缩突破的 68.1% 当成 F0。
- 不要用 `strategy-weekly/_kit/face_engine.py`。
- 不要用日频以外的 CAGR `n` 去算 OOS Calmar。
- 不要用单折 Calmar 或邻档翻转 `family_verdict`。
- 不要因为 OOS Calmar > 0.70 写成确认或换冠。
- 不要叠 PT / COOL / HYST / ER / MA200 / 袖子 / 去重 / 残差填席。
- 不要改 `strategy_exec`、`LIVE_OPS`、`champion_mast`、固收+、红利袖。
- 不要在看到结果之后改 `DESIGN.md` 的 104/26、0.50、0.15、1.50 和锚。
- 不要把 data cache 提交进 PR。
- 不要为了本卡去装新的数据客户端，不要下达新抓数。

## 拍板问句（REPORT 首行，原样）

请拍板：维持面层 B45 + spike_ft max5 + E0 + TV25 + SHARPE20，对**已冻结规则**做 104w/26w 滚动 OOS 过程审计；OOS Calmar 无论塌或不塌都不换冠。
