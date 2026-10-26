# Composer 交接 · residual-mom-fill

照此实现并跑完 4 本书。缺参数就停，不要补一套「合理默认」。不要再开网格，不要循环插值，不要跑回测主循环以外的「顺便扫一下」。不要实现 β×510300。

本 PR 的设计分支只交 `DESIGN.md` 与本文件。执行方另开分支写 `run.py` 和四件套。本文件被执行前，设计 PR 里不应出现 NAV。

## 跑完之后的四件套

写到 `research/residual-mom-fill/out/`，不多也不少：

| 文件 | 内容 |
|------|------|
| `REPORT.md` | 四段，顺序见 DESIGN「报告四件套」。首行贴 DESIGN 的拍板问句。接着原样贴 DESIGN 的 H1 代码块。然后锚点门、主表、Δ 表、填席质量旁注、证伪段、红线 |
| `summary.json` | 下面的字段 |
| `table.csv` | 4 行，列顺序固定 |
| `equity.csv` + `equity_curve.png` | 4 条净值。图用对数轴，F0 黑线、线宽 2.2；三本残差灰色细线 |

支持文件可以有 `holdings_*.csv`、`entries_*.csv`，不替代四件套。脚本放在 `research/residual-mom-fill/run.py`。夹具不过：退出码非 0，四件套一个都不写。锚不过：四件套仍要写，但 `family_verdict` 必须是 `BLOCKED`。

`summary.json`：

```json
{
  "batch": "residual-mom-fill",
  "champion_swap": false,
  "crown": "NO",
  "source_sha": "05f0f8a4f778fde886f3e7b2976646ff4b7d777b",
  "sample": ["2020-01-03", "2026-10-23"],
  "anchor_pass": true,
  "anchor": {"ret": 1.316, "maxDD": -0.188, "Calmar": 0.70, "n_weeks": 349, "T": 348, "n_codes": 324},
  "face_id": "F0",
  "primary": "RES12-EW",
  "residual": "R12w - EW(D_t)",
  "h1": "RES12-EW/RES8-EW/RES12-MED all 证伪",
  "family_verdict": "H1_HOLD",
  "positive_ids": [],
  "skipped_fills": ["RET8", "RET12", "MOM121", "SOFT", "Z121", "R4W"],
  "cells": []
}
```

`family_verdict` 只允许 `H1_HOLD`、`H1_REJECT`、`BLOCKED`。`anchor_pass=false` 时必须是 `BLOCKED`，`cells[].verdict` 全部 `BLOCKED`。上面的 JSON 是字段形状；`H1_HOLD` 与空的 `positive_ids` 不要照抄，以尺子为准。`positive_ids` 只装记正的残差邻档 id。

每个 cell：

```json
{
  "id": "RES12-EW",
  "book": "LIVE1430-B45-RES12EW-max5",
  "lookback": "R12w",
  "center": "EW",
  "ret": 0.0,
  "maxDD": 0.0,
  "CAGR": 0.0,
  "Calmar": 0.0,
  "avgL": 0.0,
  "avg_turnover_1way": 0.0,
  "n_cash_weeks": 0,
  "n_entries": 0,
  "n_miss_residual": 0,
  "mean_abs_D": 0.0,
  "n_undef_weeks": 0,
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

F0 的 `lookback` / `center` 写 `S20` / `off`，`n_miss_residual` / `n_undef_weeks` 为 0，`delta_*` 为 0，`covers` 为 true，两窗为 true，`verdict` 为 `ANCHOR`。

`table.csv` 列：

`id,book,lookback,center,ret,maxDD,CAGR,Calmar,w2020_22_ret,w2020_22_maxDD,w2020_22_Calmar,w2023_26_ret,w2023_26_maxDD,w2023_26_Calmar,avgL,avg_turnover_1way,n_cash_weeks,n_entries,n_miss_residual,mean_abs_D,n_undef_weeks,hit_rate,win_size,delta_ret,delta_abs_mdd,covers,window_2020_22,window_2023_26,verdict`

CSV 里 F0 的 lookback / center 写 `S20` / `off`。布尔写 `true` / `false`。

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

4 本书在同一次进程里跑完：只改填席键（F0 仍 SHARPE20）。持仓、成本、E0、周五 14:30 成交、TV 的 σ20/σ60 保持与针一致。TV 用**这本书自己**的过去日收益。

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
| F0 填席 | `sharpe_key`，`sharpe_n=20`，`require_sharpe=True`，`max_pos=5`。Sharpe 窗截至信号日前一交易日 |
| 残差填席 | `residual_key`，`require_residual=True`，`max_pos=5`。回看截至信号日前一交易日 |
| 退出 | E0。原因仅 `breadth_off` / `falsify` / `always_in_flip` / `left_structure` / 末日 `eod_eval` |
| 成本 | `COST_SIDE=0.001` 且 `LIVE_COST_RT=0.002`，两处都留 |
| 杠杆 | `LCAP=1`。`L = min(1, 0.25 / max(σ20, σ60))`，σ 来自该书自身过去非零日收益 × √252，样本短于 2 根时 L=1 |
| 换手 | 再平衡双向权重变化的一半，再对再平衡次数平均，写入 `avg_turnover_1way` |
| 空仓周 | 信号周五（去掉日历哨兵最后一根）持仓为空的周数 |
| 周频 | T=348 个持有周 |

变体不在这 4 个 id 里：退出码非 0，不写四件套。

## 残差实现

截止与 `sharpe_n_on` 对齐，不要用信号日当天收盘（14:30 决策会前瞻）：

```python
def lookback_ret(closes: pd.Series, d: str, cal_days: int, min_bars: int) -> float | None:
    ts = pd.Timestamp(d)
    sub = closes.loc[: ts - pd.Timedelta(days=1)]
    if len(sub) < 2:
        return None
    if (ts - sub.index[-1]).days > 5:
        return None
    p1 = float(sub.iloc[-1])
    t0 = sub.index[-1] - pd.Timedelta(days=cal_days)
    past = sub.loc[:t0]
    if len(past) == 0:
        return None
    if (sub.index[-1] - past.index[-1]).days > 5:
        return None
    p0 = float(past.iloc[-1])
    n_bars = int(sub.loc[past.index[-1]:].shape[0])
    if n_bars < min_bars or p0 <= 0 or not np.isfinite(p0) or not np.isfinite(p1):
        return None
    return p1 / p0 - 1.0


def residual_key(c, pool):
    miss = 0 if c.residual is not None else 1
    return (miss, -(c.residual if c.residual is not None else 0.0), c.code)
```

| 书 | `cal_days` | `min_bars` | 中心 |
|----|------------|------------|------|
| RES12-EW | 84 | 40 | `mean` |
| RES8-EW | 56 | 28 | `mean` |
| RES12-MED | 84 | 40 | `median` |

每个信号周五：

1. 先对**全部**当周 spike_ft（含已持仓）算 `R_*`，构成 `D_t`。
2. `|D_t| < 2`：残差全体 `None`，`n_undef_weeks += 1`，本周不新开。
3. 否则 `center = mean(D_t)` 或 `median(D_t)`，`resid = R − center`。
4. `build_cands` 仍 `skip=set(positions)`。`require_residual=True` 后按 `residual_key` 取 `slots`。

`n_miss_residual`：过了 `is_spike`、有信号价，但 `lookback_ret` 为 None 的（周五, 代码）次数。按名字计，不要按「本会进 top5 才计」。F0 不调用残差函数。

`mean_abs_D`：`risk_on` 且 `|D_t| ≥ 1` 的周，对 `|D_t|` 取均值。没有这类周则写 0。

`hit_rate` / `win_size`：仅新开/换入的那只券，从该信号周五收盘到下一信号周五收盘的简单收益。盈利为该收益 > 0。没有下一根信号周五的开仓不进样本。不要用组合周收益冒充个券入场质量。

不要实现 β、不要读 510300、不要 z-score、不要减 R1w、不要 0.75/0.25 合成、不要跳月。不要把残差缺失回退成 SHARPE20。

## 夹具（先跑）

| 名 | 输入 | 应落在 |
|----|------|--------|
| 三名去均值 | R = 0.12, 0.00, −0.06 | EW 残差 = 0.10, −0.02, −0.08 |
| 三名中位数 | 同上 | MED 残差 = 0.12, 0.00, −0.06 |
| 单名 | D 只有一只 | 残差 `None`（`|D|<2`） |
| 回看缺档 | 前一交易日距信号 >5 日 | `lookback_ret` 返回 `None` |

算术用 `pytest` 或脚本内 assert 均可。任一夹具出界：退出码非 0，不写四件套。

## 尺子

与 DESIGN 相同。不要在跑批脚本里另写 0.9× 或 −2pp。

```
记正 = (Δret ≥ Δ|MDD|) 且 (2020-22 ret ≥ F0) 且 (2023-26 ret ≥ F0)
F0.verdict = ANCHOR
family_verdict = H1_HOLD   若三本残差都是证伪
family_verdict = H1_REJECT 若至少一本记正
```

hit-rate / win-size / `mean_abs_D` 只进表，不进 `verdict`。

## 锚点不过时的写法

F0 先与 DESIGN 的锚比较。不过：

- 四件套仍写完，4 本数字照实
- `anchor_pass=false`，`family_verdict=BLOCKED`
- REPORT 写明 F0 实际 ret / maxDD / Calmar，以及它更接近 131.6/0.70、158.3/0.94，还是 nob_ref 134.0/0.70
- 停止。不去调成本、不去换宽度、不去贴另一条引擎

## 实现时不要做的事

- 不要跑第 5 本书，不要跑 β×510300，不要跑 z 分，不要跑 12−1，不要跑原始 R4W/R8W/R12W。
- 不要重开 RET8/RET12 窗插值（KB：后段踏空，不扫窗）。
- 不要重开 MOM121 W7525 / W67 / W85（假设#4 已证伪）。
- 不要重开 Z121、SOFT4535、NOBREADTH。
- 不要把 TV 网格的 158.3% 当成 F0 目标，也不要把 nob_ref 134.0% 或 KB 135.0% 当成 F0。
- 不要用 `strategy-weekly/_kit/face_engine.py`。
- 不要打开 R 闸，不要叠 PT / COOL / HYST / 软门 / 换手惩罚。
- 不要用 `0.9 ×` 或 `−2pp`。
- 不要改 `strategy_exec`、`LIVE_OPS`、`champion_mast`、实盘、固收+、红利袖。
- 不要在看到结果之后改 `DESIGN.md` 的残差定义、邻档、尺子和锚。
- 不要把 data cache 提交进 PR。
- 不要发明 MOM121 / RET8 / Z121 的「延窗换算」数字。引用只用 KB / PR 已写原文。

## 拍板问句（REPORT 首行，原样）

请拍板：在面层 B45 + spike_ft max5 + E0 + TV25 上，只改填席键：SHARPE20 → 残差截面动量（R12w − 当周合格池等权均值）。无论记正与否都不换冠。
