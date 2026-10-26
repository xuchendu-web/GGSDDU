# Composer 交接 · entry-kaufman-er

照此实现并跑完 4 本书。缺参数就停，不要补一套「合理默认」。不要再开网格，不要循环插值，不要跑回测主循环以外的「顺便扫一下」。

本 PR 的设计分支只交 `DESIGN.md` 与本文件。执行方另开分支写 `run.py` 和四件套。

## 跑完之后的四件套

写到 `research/entry-kaufman-er/out/`，不多也不少：

| 文件 | 内容 |
|------|------|
| `REPORT.md` | 首行贴 DESIGN 的拍板问句。接着原样贴 DESIGN 的 H1 代码块。然后锚点门、主表、Δ 表、入场质量旁注、证伪段、红线 |
| `summary.json` | 下面的字段 |
| `table.csv` | 4 行，列顺序固定 |
| `equity.csv` + `equity_curve.png` | 4 条净值。图用对数轴，F0 黑线、线宽 2.2；三本 ER 灰色细线 |

支持文件可以有 `holdings_*.csv`、`entries_*.csv`，不替代四件套。脚本放在 `research/entry-kaufman-er/run.py`。夹具不过：退出码非 0，四件套一个都不写。锚不过：四件套仍要写，但 `family_verdict` 必须是 `BLOCKED`。

`summary.json`：

```json
{
  "batch": "entry-kaufman-er",
  "champion_swap": false,
  "crown": "NO",
  "source_sha": "05f0f8a4f778fde886f3e7b2976646ff4b7d777b",
  "sample": ["2020-01-03", "2026-10-23"],
  "anchor_pass": true,
  "anchor": {"ret": 1.316, "maxDD": -0.188, "Calmar": 0.70, "n_weeks": 349, "T": 348, "n_codes": 324},
  "face_id": "F0",
  "er_n": 10,
  "h1": "ER10-T30/T40/T50 all 证伪",
  "family_verdict": "H1_HOLD",
  "positive_ids": [],
  "cells": []
}
```

`family_verdict` 只允许 `H1_HOLD`、`H1_REJECT`、`BLOCKED`。`anchor_pass=false` 时必须是 `BLOCKED`，`cells[].verdict` 全部 `BLOCKED`。上面的 JSON 是字段形状；`H1_HOLD` 与空的 `positive_ids` 不要照抄，以尺子为准。`positive_ids` 只装记正的 ER 邻档 id。

每个 cell：

```json
{
  "id": "ER10-T30",
  "book": "LIVE1430-ER10-T30-B45-TV25",
  "N": 10,
  "theta": 0.30,
  "ret": 0.0,
  "maxDD": 0.0,
  "CAGR": 0.0,
  "Calmar": 0.0,
  "avgL": 0.0,
  "avg_turnover_1way": 0.0,
  "n_cash_weeks": 0,
  "n_entries": 0,
  "n_er_blocked": 0,
  "hit_rate": 0.0,
  "win_size": 0.0,
  "w2020_22": {"ret": 0.0, "maxDD": 0.0, "Calmar": 0.0},
  "w2023_26": {"ret": 0.0, "maxDD": 0.0, "Calmar": 0.0},
  "delta_ret": 0.0,
  "delta_abs_mdd": 0.0,
  "covers": false,
  "window_2020_22": false,
  "window_2023_26": false,
  "verdict": "证伪"
}
```

F0 的 `N` / `theta` 写 `null`，`n_er_blocked` 为 0，`delta_*` 为 0，`covers` 为 true，两窗为 true，`verdict` 为 `ANCHOR`。

`table.csv` 列：

`id,book,N,theta,ret,maxDD,CAGR,Calmar,w2020_22_ret,w2020_22_maxDD,w2020_22_Calmar,w2023_26_ret,w2023_26_maxDD,w2023_26_Calmar,avgL,avg_turnover_1way,n_cash_weeks,n_entries,n_er_blocked,hit_rate,win_size,delta_ret,delta_abs_mdd,covers,window_2020_22,window_2023_26,verdict`

CSV 里 F0 的 N / theta 写 `off`。布尔写 `true` / `false`。

`equity.csv` 列：`date,book,nav`。`nav` 是日净收益的 `cumprod`，起点 1。`book` 用上表书名。

## 引擎从哪 fork

只读针：

`05f0f8a4f778fde886f3e7b2976646ff4b7d777b`
`research/cloud_batch/SPIKE-S20-BTHETA-GRID-LIVE1430/run.py`

数据与 `LIVE_PHASE` 同提交：

`research/cloud_batch/CLOUD-BATCH-2026-10-26/`

`LIVE_PHASE = {"紧通道", "冲击"}`，从该提交的 `scripts/backtest.py` 导入。

工作区若没有这些路径：用 `git show` / 只读 worktree 拷到临时目录。不要 `git checkout` 到 btheta 分支上改原文件。不要用 `strategy-weekly/_kit/face_engine.py`——那是压缩突破的 68.1% FACE，不是本刀的面。

`summary.json` 的 `source_sha` 写实际载入的提交；载入的不是 `05f0f8a4` 就停。

本机解释器 `D:\python\python.exe`。云端用 `python3`。

4 本书在同一次进程里跑完：只改 ER 的 θ（F0 关闭）。持仓、成本、E0、SHARPE20、周五 14:30 成交、TV 的 σ20/σ60 保持与针一致。TV 用**这本书自己**的过去日收益。

## 冻结参数

| 名 | 值 |
|----|----|
| `EVAL_START` / `END_S` | `2020-01-03` / `2026-10-23` |
| 宇宙 | `universe_replace_only_436.csv`，`aum >= 2`，代码 zfill 6 |
| 信号价 | `fri_1430_through_20261023.csv`；`qfq_1430 = price_1430 × (日 qfq / sina)` |
| 分类 | 只读 `cache_1430_snaps.json`。不重新 classify |
| 宽度 | `holdings_ro2_extended.csv` 列 `b`。`risk_on = b is not None and b >= 0.45`。不用该文件里现成的 `risk_on` 列 |
| 日历末日 | `risk_on` 强制 false |
| spike | `in_play` 且 `in_play_kind==spike_ft`；`box_pending` / `pending_second_week` 排除 |
| 填席 | `sharpe_key`，`sharpe_n=20`，`require_sharpe=True`，`max_pos=5`。Sharpe 窗截至信号日前一交易日 |
| 退出 | E0。原因仅 `breadth_off` / `falsify` / `always_in_flip` / `left_structure` / 末日 `eod_eval` |
| 成本 | `COST_SIDE=0.001` 且 `LIVE_COST_RT=0.002`，两处都留 |
| 杠杆 | `LCAP=1`。`L = min(1, 0.25 / max(σ20, σ60))`，σ 来自该书自身过去非零日收益 × √252，样本短于 2 根时 L=1 |
| 换手 | 再平衡双向权重变化的一半，再对再平衡次数平均，写入 `avg_turnover_1way` |
| 空仓周 | 信号周五（去掉日历哨兵最后一根）持仓为空的周数 |
| 周频 | T=348 个持有周 |

变体不在这 4 个 id 里：退出码非 0，不写四件套。

## ER 实现

截止与 `sharpe_n_on` 对齐，不要用信号日当天收盘（14:30 决策会前瞻）：

```python
def kaufman_er(closes: pd.Series, d: str, n: int) -> float | None:
    ts = pd.Timestamp(d)
    sub = closes.loc[: ts - pd.Timedelta(days=1)]
    if len(sub) < n + 1:
        return None
    if (ts - sub.index[-1]).days > 5:
        return None
    window = sub.iloc[-(n + 1) :]
    diffs = window.diff().abs().iloc[1:]
    if len(diffs) != n:
        return None
    denom = float(diffs.sum())
    if denom <= 0 or not np.isfinite(denom):
        return None
    num = abs(float(window.iloc[-1]) - float(window.iloc[0]))
    if not np.isfinite(num):
        return None
    return num / denom
```

闸：`er is not None and er >= theta`。挂在 `build_cands` 出口，对象已经不包含 `positions`。F0 不调用此函数。

`n_er_blocked`：过了 `is_spike`、有信号价、有 SHARPE20，但 ER 为 None 或 `< θ` 的次数。按（周五, 代码）计，不要按「本会进 top5 才计」——那样会在事后挑选分母。

`hit_rate` / `win_size`：仅新开/换入的那只券，从该信号周五收盘到下一信号周五收盘的简单收益。盈利为该收益 > 0。没有下一根信号周五的开仓不进样本。不要用组合周收益冒充个券入场质量。

不要实现 KAMA 的 Fast SC / Slow SC / SC²。不要改用周 OHLC。不要用自身历史分位替代 θ。

## 夹具（先跑）

| 名 | 输入 | 应落在 |
|----|------|--------|
| 单边 | N=10，收盘 10…20 | ER ∈ [0.999999, 1.000001] |
| 折返 | N=10，10,11,10,11,10,11,10,11,10,11,10 | ER ∈ [−1e-12, 1e-12] |
| 全平 | N=10，十一个 10 | 返回 `None` |

任一夹具出界：退出码非 0，不写四件套。

## 尺子

与 DESIGN 相同。不要在跑批脚本里另写 0.9× 或 −2pp。

```
记正 = (Δret ≥ Δ|MDD|) 且 (2020-22 ret ≥ F0) 且 (2023-26 ret ≥ F0)
F0.verdict = ANCHOR
family_verdict = H1_HOLD   若三本都是证伪
family_verdict = H1_REJECT 若至少一本记正
```

hit-rate / win-size 只进表，不进 `verdict`。

## 锚点不过时的写法

F0 先与 DESIGN 的锚比较。不过：

- 四件套仍写完，4 本数字照实
- `anchor_pass=false`，`family_verdict=BLOCKED`
- REPORT 写明 F0 实际 ret / maxDD / Calmar，以及它更接近 131.6/0.70、158.3/0.94，还是压缩突破的 68.1/0.31
- 停止。不去调成本、不去换宽度、不去贴另一条引擎

## 实现时不要做的事

- 不要跑第 5 本书，不要跑 N=8/20，不要跑 θ=0.75，不要跑周频 ER。
- 不要把 TV 网格的 158.3% 当成 F0 目标，也不要把压缩突破的 68.1% 当成 F0。
- 不要用 `strategy-weekly/_kit/face_engine.py` 或 `_kit/compression.py`。
- 不要打开 R 闸，不要叠 PT / COOL / HYST / K2 / 压缩突破。
- 不要重开 R×B×TV 八格（PR#61 已 H1_REJECT：X1、X5 记正）。
- 不要重开 PT15×COOL6（PR#59，且用了 158.3% 那条引擎）。
- 不要用 `0.9 ×` 或 `−2pp`。
- 不要改 `strategy_exec`、`LIVE_OPS`、`champion_mast`、固收+、红利袖。
- 不要在看到结果之后改 `DESIGN.md` 的 N、θ、尺子和锚。
- 不要把 data cache 提交进 PR。

## 拍板问句（REPORT 首行，原样）

请拍板：维持面层 B45 + spike_ft max5 + E0 + TV25 + SHARPE20，ER(N)≥θ 只挡新开/换入，无论记正与否都不换冠。
