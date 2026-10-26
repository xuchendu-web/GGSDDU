# Composer 交接 · ma200-abs-gate

照此实现并跑完 4 本四件套 + 1 本 CSI500 旁注。缺参数就停，不要补一套「合理默认」。不要再开网格，不要循环插值，不要跑回测主循环以外的「顺便扫一下」。不要重开 Dual-TF（PR#63）和通道 overlay（PR#66）。

本 PR 的设计分支只交 `DESIGN.md` 与本文件。执行方另开分支写 `run.py` 和四件套。本设计分支 **禁止** 跑回测主循环、禁止发明净值。

## 跑完之后的四件套

写到 `research/ma200-abs-gate/out/`，不多也不少：

| 文件 | 内容 |
|------|------|
| `REPORT.md` | 首行贴 DESIGN 的拍板问句。接着原样贴 DESIGN 的 H1 代码块。然后锚点门、主表、Δ 表、闸质量旁注、证伪段、红线 |
| `summary.json` | 下面的字段 |
| `table.csv` | 5 行（4 本四件套 + CSI500 旁注），列顺序固定 |
| `equity.csv` + `equity_curve.png` | 净值。图用对数轴：F0 黑线、线宽 2.2；三本 HS300 灰色细线；CSI500 若画则灰虚线 |

支持文件可以有 `holdings_*.csv`、`gate_weeks.csv`（每周 `date,b,risk_on_B45,abs_on,risk_on,proxy_c,sma`），不替代四件套。脚本放在 `research/ma200-abs-gate/run.py`。夹具不过：退出码非 0，四件套一个都不写。锚不过：四件套仍要写，但 `family_verdict` 必须是 `BLOCKED`。代理文件缺失：`BLOCKED`，不要改用日线收盘冒充周 SMA，不要去外网补抓一套新指数。

`summary.json`：

```json
{
  "batch": "ma200-abs-gate",
  "champion_swap": false,
  "crown": "NO",
  "source_sha": "05f0f8a4f778fde886f3e7b2976646ff4b7d777b",
  "sample": ["2020-01-03", "2026-10-23"],
  "anchor_pass": true,
  "anchor": {"ret": 1.316, "maxDD": -0.188, "Calmar": 0.70, "n_weeks": 349, "T": 348, "n_codes": 324, "n_cash_weeks": 150},
  "face_id": "F0",
  "proxy_econ_hs300": "CSI300",
  "proxy_used_hs300": "510300",
  "proxy_econ_csi500": "CSI500",
  "proxy_used_csi500": "510500",
  "h1": "MA30/MA40/MA50-HS300 all 证伪",
  "family_verdict": "H1_HOLD",
  "positive_ids": [],
  "cells": []
}
```

`family_verdict` 只允许 `H1_HOLD`、`H1_REJECT`、`BLOCKED`。`anchor_pass=false` 时必须是 `BLOCKED`，`cells[].verdict` 全部 `BLOCKED`。上面的 JSON 是字段形状；`H1_HOLD` 与空的 `positive_ids` 不要照抄，以尺子为准。`positive_ids` 只装记正的 **HS300** 邻档 id（不含 F0、不含 CSI500）。`proxy_used_*` 写成实际载入的六位代码。

每个 cell：

```json
{
  "id": "MA40-HS300",
  "book": "LIVE1430-MA40-HS300-B45-TV25",
  "N": 40,
  "proxy": "510300",
  "ret": 0.0,
  "maxDD": 0.0,
  "CAGR": 0.0,
  "Calmar": 0.0,
  "avgL": 0.0,
  "avg_turnover_1way": 0.0,
  "n_cash_weeks": 0,
  "n_ma_off": 0,
  "n_breadth_off": 0,
  "n_ma_off_breadth_on": 0,
  "n_both_off": 0,
  "n_entries": 0,
  "hit_rate": 0.0,
  "win_size": 0.0,
  "w2020_22": {"ret": 0.0, "maxDD": 0.0, "Calmar": 0.0},
  "w2023_26": {"ret": 0.0, "maxDD": 0.0, "Calmar": 0.0},
  "delta_ret": 0.0,
  "delta_abs_mdd": 0.0,
  "covers": false,
  "window_2020_22": false,
  "window_2023_26": false,
  "inert": false,
  "verdict": "证伪"
}
```

F0 的 `N` / `proxy` 写 `null`，`n_ma_off` 与 `n_ma_off_breadth_on` 为 0，`delta_*` 为 0，`covers` 为 true，两窗为 true，`inert` 为 false，`verdict` 为 `ANCHOR`。

CSI500 行 `verdict` 只允许 `旁注-记正` / `旁注-证伪` / `BLOCKED`，**不得**写入 `positive_ids`，**不得**改变 `family_verdict`。

`table.csv` 列：

`id,book,N,proxy,ret,maxDD,CAGR,Calmar,w2020_22_ret,w2020_22_maxDD,w2020_22_Calmar,w2023_26_ret,w2023_26_maxDD,w2023_26_Calmar,avgL,avg_turnover_1way,n_cash_weeks,n_ma_off,n_breadth_off,n_ma_off_breadth_on,n_both_off,n_entries,hit_rate,win_size,delta_ret,delta_abs_mdd,covers,window_2020_22,window_2023_26,inert,verdict`

CSV 里 F0 的 N / proxy 写 `off`。布尔写 `true` / `false`。行顺序：F0、MA40-HS300、MA30-HS300、MA50-HS300、MA40-CSI500。

`equity.csv` 列：`date,book,nav`。`nav` 是日净收益的 `cumprod`，起点 1。`book` 用上表书名。

## 引擎从哪 fork

只读针：

`05f0f8a4f778fde886f3e7b2976646ff4b7d777b`
`research/cloud_batch/SPIKE-S20-BTHETA-GRID-LIVE1430/run.py`

数据与 `LIVE_PHASE` 同提交：

`research/cloud_batch/CLOUD-BATCH-2026-10-26/`

`LIVE_PHASE = {"紧通道", "冲击"}`，从该提交的 `scripts/backtest.py` 导入。

工作区若没有这些路径：用 `git show` / 只读 worktree 拷到临时目录。不要 `git checkout` 到 btheta 分支上改原文件。不要用 `strategy-weekly/_kit/face_engine.py`——那是压缩突破的 68.1% FACE。不要用 TV 网格 `SPIKE-S20-TV-GRID-LIVE1430/run.py`——那是 158.3% / 0.94，PR#66 已经跑错过。

`summary.json` 的 `source_sha` 写实际载入的提交；载入的不是 `05f0f8a4` 就停。

本机解释器 `D:\python\python.exe`。云端用 `python3`。

5 本书在同一次进程里跑完：只改 `abs_on` 的 N 与代理（F0 关闭）。持仓填席、成本、E0、SHARPE20、周五 14:30 成交、TV 的 σ20/σ60 保持与针一致。TV 用**这本书自己**的过去日收益。

## 冻结参数

| 名 | 值 |
|----|----|
| `EVAL_START` / `END_S` | `2020-01-03` / `2026-10-23` |
| 宇宙 | `universe_replace_only_436.csv`，`aum >= 2`，代码 zfill 6 |
| 信号价 | `fri_1430_through_20261023.csv`；`qfq_1430 = price_1430 × (日 qfq / sina)` |
| 分类 | 只读 `cache_1430_snaps.json`。不重新 classify |
| 宽度 | `holdings_ro2_extended.csv` 列 `b`。`risk_on_B45 = b is not None and b >= 0.45`。不用该文件里现成的 `risk_on` 列 |
| 日历末日 | `risk_on` 强制 false |
| spike | `in_play` 且 `in_play_kind==spike_ft`；`box_pending` / `pending_second_week` 排除 |
| 填席 | `sharpe_key`，`sharpe_n=20`，`require_sharpe=True`，`max_pos=5`。Sharpe 窗截至信号日前一交易日 |
| 退出 | E0。原因 `breadth_off` / `abs_trend_off` / `falsify` / `always_in_flip` / `left_structure` / 末日 `eod_eval` |
| 成本 | `COST_SIDE=0.001` 且 `LIVE_COST_RT=0.002`，两处都留 |
| 杠杆 | `LCAP=1`。`L = min(1, 0.25 / max(σ20, σ60))`，σ 来自该书自身过去非零日收益 × √252，样本短于 2 根时 L=1 |
| 换手 | 再平衡双向权重变化的一半，再对再平衡次数平均，写入 `avg_turnover_1way` |
| 空仓周 | 信号周五（去掉日历哨兵最后一根）持仓为空的周数 |
| 周频 | T=348 个持有周 |
| 现金桩 | 闸关收益 0。禁止 511010 / 511260 / 511880 |

变体不在这 5 个 id 里：退出码非 0，不写四件套。

## 代理周线

CSI300 加载顺序（找到即停，写入 `proxy_used_hs300`）：

1. `research_cache/week/000300.json`（或 kit 内同结构指数周线）
2. `research_cache/week/510300.json`，周收用与 FACE 相同的 qfq 链；该周五若 `fri_1430` 有 510300，用 14:30 代理当周 `C_t`

CSI500 同理：`000905` → `510500`。

同一跑里三本 HS300 必须共用 `proxy_used_hs300`。混用 000300 与 510300 → 退出码非 0。代理周线在 `EVAL_START` 之前不够 N 根：允许（闸失败），但评估窗内不得用未来周补历史。评估窗内主代理缺失超过 2 个信号周五 → `BLOCKED`。

不要把 510300 的日线 200SMA 当成 40 周 SMA。不要用新浪实时接口在跑批时另拉一套。

## SMA 实现

```python
def abs_on(weekly_closes: pd.Series, d: str, n: int) -> bool:
    """weekly_closes: DatetimeIndex, 已按信号周五对齐的代理周收（含 14:30 代理）。"""
    ts = pd.Timestamp(d)
    sub = weekly_closes.loc[:ts]
    if len(sub) < n:
        return False
    if (ts - sub.index[-1]).days > 5:
        return False
    window = sub.iloc[-n:]
    c = float(window.iloc[-1])
    sma = float(window.mean())
    if not (np.isfinite(c) and np.isfinite(sma)):
        return False
    return c > sma
```

合成：`risk_on = risk_on_B45 and abs_on(...)`。F0 不调用此函数，等价 `abs_on=True`。

不要实现「SMA 较 4 周前抬升」。不要给 `>` 加缓冲。不要改用指数加权。

`n_ma_off_breadth_on`：信号周五（去哨兵）上 `risk_on_B45 and not abs_on` 的周数。按周计，不要按名字计。

`inert`：`n_ma_off_breadth_on == 0`，或该书每周持仓代码集合与 F0 相同。惰性 ⇒ `verdict=证伪`（F0 除外）。

`hit_rate` / `win_size`：仅新开/换入的那只券，从该信号周五收盘到下一信号周五收盘的简单收益。盈利为该收益 > 0。没有下一根信号周五的开仓不进样本。不要用组合周收益冒充个券入场质量。

## 夹具（先跑）

| 名 | 输入 | 应落在 |
|----|------|--------|
| 单边向上 | N=4，周收 10,11,12,13 | `abs_on is True` |
| 单边向下 | N=4，13,12,11,10 | `abs_on is False` |
| 贴线 | N=4，四个 10 | `abs_on is False` |
| 不够长 | N=4，长度 3 | `abs_on is False` |

任一夹具出界：退出码非 0，不写四件套。生产 N 仍是 30/40/50；夹具只锁 `>` 与长度。

## 尺子

与 DESIGN 相同。不要在跑批脚本里另写 0.9× 或 −2pp。

```
记正 = (Δret ≥ Δ|MDD|) 且 (2020-22 ret ≥ F0) 且 (2023-26 ret ≥ F0) 且 (非惰性)
F0.verdict = ANCHOR
family_verdict = H1_HOLD   若三本 HS300 都是证伪
family_verdict = H1_REJECT 若至少一本 HS300 记正
CSI500 不进 family_verdict
```

hit-rate / win-size / `n_ma_off*` 只进表，不进 `verdict`（惰性除外）。

## 锚点不过时的写法

F0 先与 DESIGN 的锚比较。不过：

- 四件套仍写完，5 本数字照实
- `anchor_pass=false`，`family_verdict=BLOCKED`
- REPORT 写明 F0 实际 ret / maxDD / Calmar，以及它更接近 131.6/0.70、158.3/0.94、Dual-MOM 对照行 131.9、NOB 跑的 134.0，还是压缩突破的 68.1/0.31
- 停止。不去调成本、不去换宽度、不去贴另一条引擎、不去把 510300 通道 overlay 的 FACE 当锚

## 实现时不要做的事

- 不要跑第 6 本书，不要跑 N=20/26/52/100，不要跑日线 200SMA，不要跑 10 月月线。
- 不要把 TV 网格的 158.3% 当成 F0 目标，也不要把压缩突破的 68.1%、Dual-MOM 的 131.9%、NOB 的 134.0% 当成 F0。
- 不要用 `strategy-weekly/_kit/face_engine.py` 或 TV 网格 `run.py`。
- 不要实现 MA 斜率 / 「较 4 周前抬升」——那是 PR#66，不重开。
- 不要重跑 Dual-TF（PR#63）或 Dual-MOM 引擎来「对照」。
- 不要去掉 B45（NOBREADTH 已证伪），不要跑 SOFT4535。
- 不要打开 R 闸，不要叠 PT / COOL / HYST / ER / 压缩突破 / MaxDD 闸。
- 不要把闸关停进 511010 / 511260。
- 不要做 N×代理笛卡尔（禁止 MA30/50 × CSI500）。
- 不要用 `0.9 ×` 或 `−2pp`。
- 不要改 `strategy_exec`、`LIVE_OPS`、`champion_mast`、固收+、红利袖。
- 不要在看到结果之后改 `DESIGN.md` 的 N、代理、尺子和锚。
- 不要把 data cache 提交进 PR。
- 不要在本设计分支跑主循环或手填净值。

## 拍板问句（REPORT 首行，原样）

请拍板：维持面层 B45 + spike_ft max5 + E0 + TV25 + SHARPE20，只在组合 `risk_on` 上 **AND** 一道沪深300（或 kit 内 510300）周收 > 40 周 SMA 的绝对趋势闸；闸关则 100% 现金桩。无论记正与否都不换冠。
