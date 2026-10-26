# Composer 交接 · ENTRY-SIGNAL-RxBxTV

照此实现并跑完 8 本书。缺参数就停，不要补一套「合理默认」。

## 跑完之后的四件套

写到 `research/ENTRY-SIGNAL-RxBxTV-AUDIT/out/`：

| 文件 | 内容 |
|------|------|
| `REPORT.md` | 首行贴 README 的拍板问句。接着原样贴 `CRITERION.md` 的 TEMPLATE。然后锚点门、主表、Δ 表、证伪段、红线 |
| `summary.json` | 下面的字段，不多解释性散文 |
| `table.csv` | 8 行，列顺序固定 |
| `equity.csv` + `equity_curve.png` | 8 条净值。图用对数轴，F0 黑线、线宽 2.2 |

支持文件可以有 `holdings_*.csv`，不替代四件套。

`summary.json`：

```json
{
  "batch": "ENTRY-SIGNAL-RxBxTV",
  "champion_swap": false,
  "crown": "NO",
  "source_sha": "<git rev-parse of the btheta pin actually loaded>",
  "sample": ["2020-01-03", "2026-10-23"],
  "anchor_pass": true,
  "anchor": {"ret": 1.316, "maxDD": -0.188, "Calmar": 0.70, "n_weeks": 349, "n_codes": 324},
  "face_id": "F0",
  "h1": "X1-X7 all 证伪",
  "family_verdict": "H1_HOLD",
  "positive_ids": [],
  "cells": []
}
```

`family_verdict` 只允许 `H1_HOLD`、`H1_REJECT`、`BLOCKED`。`anchor_pass=false` 时必须是 `BLOCKED`，`cells[].verdict` 全部 `BLOCKED`。上面的 JSON 是字段形状；`H1_HOLD` 与空的 `positive_ids` 不要照抄，以 `ruler.verdict` 为准。

每个 cell：

```json
{
  "id": "X1",
  "book": "LIVE1430-X-R80-B50-TV25",
  "R": 80,
  "B": 0.5,
  "TV": 0.25,
  "ret": 0.0,
  "maxDD": 0.0,
  "CAGR": 0.0,
  "Calmar": 0.0,
  "avgL": 0.0,
  "avg_turnover_1way": 0.0,
  "n_cash_weeks": 0,
  "n_entries": 0,
  "n_spike_blocked_by_mom": 0,
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

F0 的 `delta_*` 为 0，`covers` 为 true，两窗为 true，`verdict` 为 `ANCHOR`。R 关写 `null`。

`table.csv` 列：

`id,book,R,B,TV,ret,maxDD,CAGR,Calmar,w2020_22_ret,w2020_22_maxDD,w2020_22_Calmar,w2023_26_ret,w2023_26_maxDD,w2023_26_Calmar,avgL,avg_turnover_1way,n_cash_weeks,n_entries,n_spike_blocked_by_mom,delta_ret,delta_abs_mdd,covers,window_2020_22,window_2023_26,verdict`

CSV 里 R 关写 `off`。布尔写 `true` / `false`。

`equity.csv` 列：`date,book,nav`。`nav` 是日净收益的 `cumprod`，起点 1。`book` 用上表书名。

判定调用 `ruler.verdict`。不要在跑批脚本里重写不等式。

## 引擎从哪 fork

只读针：

`05f0f8a4f778fde886f3e7b2976646ff4b7d777b`
`research/cloud_batch/SPIKE-S20-BTHETA-GRID-LIVE1430/run.py`

数据与 `LIVE_PHASE` 同提交：

`research/cloud_batch/CLOUD-BATCH-2026-10-26/`

`LIVE_PHASE = {"紧通道", "冲击"}`，从该提交的 `scripts/backtest.py` 导入。

新脚本放在本目录，例如 `run.py`。不改 btheta 分支上的原文件，不把 data cache 再提交一遍。`summary.json` 记下实际载入的 `source_sha`。

本机解释器 `D:\python\python.exe`。云端批跑用 `python3`，脚本路径相同。

## 冻结参数

| 名 | 值 |
|----|----|
| `EVAL_START` / `END_S` | `2020-01-03` / `2026-10-23` |
| 宇宙 | `universe_replace_only_436.csv`，`aum >= 2`，代码 zfill 6 |
| 信号价 | `fri_1430_through_20261023.csv`；`qfq_1430 = price_1430 × (日 qfq / sina)` |
| 分类 | 只读 `cache_1430_snaps.json`。不重新 classify |
| 宽度 | `holdings_ro2_extended.csv` 列 `b`。`risk_on = b is not None and b >= θ`。不用该文件里现成的 `risk_on` 列（那列是 θ=0.45） |
| 日历末日 | `risk_on` 强制 false（与 btheta 一致） |
| spike | `in_play` 且 `in_play_kind==spike_ft`；`box_pending` / `pending_second_week` 排除 |
| 填席 | `sharpe_key`，`sharpe_n=20`，`require_sharpe=True`，`max_pos=5`。Sharpe 窗截至信号日前一交易日 |
| R 关 | `build_cands` 不调用 `ret_nd_on`，`n_spike_blocked_by_mom=0` |
| R 40 / 80 | 仅新进：`ret_nd_on` 要 n+1 根，最后一根在信号日之前，与信号日相距 ≤5 个日历日；收益 `≤0` 或缺失则挡掉。不平旧仓 |
| 退出 | E0。原因仅 `breadth_off` / `falsify` / `always_in_flip` / `left_structure` / 末日 `eod_eval`。无 rank 滞回，无 K 周 top-seat 等待 |
| 成本 | `COST_SIDE=0.001`（份额）且 `LIVE_COST_RT=0.002`（换手×RT/2）。两处都留 |
| 杠杆 | `LCAP=1`。`L = min(1, σ* / max(σ20, σ60))`，σ 来自该书自身过去非零日收益 × √252，样本短于 2 根时 L=1。每本书各算各的 |
| 换手 | 再平衡双向权重变化的一半，再对再平衡次数平均，写入 `avg_turnover_1way` |
| 空仓周 | 信号周五（去掉日历哨兵最后一根）持仓为空的周数 |

变体表从 `cells.json` 读。脚本若发现书名不在这 8 个之内，退出码非 0，不写四件套。

## 锚点不过时的写法

F0 先与 `FALSIFY.md` 的锚比较。不过：

- 四件套仍写完，数字照实
- `anchor_pass=false`，`family_verdict=BLOCKED`
- REPORT 写明 F0 实际 ret / maxDD / Calmar，以及它更接近 131.6/0.70 还是 158.3/0.94
- 停止。不去调成本、不去换宽度定义、不去贴另一条引擎

## 实现时不要做的事

- 不要跑 R60、B40、B55、TV20/22/28/30，也不要在 8 格之间再插一档。
- 不要把 TV 网格的 158.3% 当成 F0 目标。
- 不要用 `0.9 ×` 或 `−2pp`。
- 不要把 HYST-M3、盈利止盈、亏损冷却、宇宙切片、现金债腿写进同一 `run.py`。
- 不要改 `strategy_exec`、`LIVE_OPS`、`champion_mast`、固收+、红利袖。
- 不要在看到结果之后改 `CRITERION.md` 的 TEMPLATE。

## 拍板问句（REPORT 首行，原样）

请拍板：维持面层 B45 + spike_ft max5 + E0 + TV25 + SHARPE20，本交叉无论记正与否都不换冠。
