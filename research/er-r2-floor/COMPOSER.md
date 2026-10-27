# Composer 交接 · er-r2-floor

照此实现并跑完 **4 本书**（F0 + 主簿 RF50 + ER 邻档 ER20 + 合取邻档 AND50）。缺参数就停，不要补一套「合理默认」。不要再开网格，不要循环插值，不要跑回测主循环以外的「顺便扫一下」。不要实现 Clenow 填席，不要实现加速度 / AG40S，不要实现 ER10-T30/T40/T50，不要读 510300 当 σ / L / 闸。

本 PR 的设计分支只交 `DESIGN.md` 与本文件。执行方另开分支写 `run.py` 和四件套。本文件被执行前，设计 PR 里不应出现 NAV，不应出现 `research/er-r2-floor/out/`。

## 跑完之后的四件套

写到 `research/er-r2-floor/out/`，不多也不少：

| 文件 | 内容 |
|------|------|
| `REPORT.md` | 五段，顺序见 DESIGN「报告四件套」。必须有名为 **ATTRIBUTION** 的独立段，且 (a)–(e) 齐。首行贴 DESIGN 的拍板问句。接着原样贴 DESIGN 的 H1 代码块。然后锚点门、ATTRIBUTION 门、主表、Δ 表、闸质量旁注、ATTRIBUTION、证伪段、红线 |
| `summary.json` | 下面的字段 |
| `table.csv` | **4 行**，列顺序固定 |
| `equity.csv` + `equity_curve.png` | 4 条净值。图用对数轴，F0 黑线、线宽 2.2；三本地板灰色细线 |

ATTRIBUTION 支持文件（**必须有**，不替代四件套）：

| 文件 | 内容 |
|------|------|
| `out/entries_diff_by_year.csv` | 相对 F0 的入场 ADD/DROP，按年、按书 |
| `out/segment_attribution.csv` | 每本非 F0 至少一行 `BIGWIN`、一行 `BIGLOSS`，外加可选 `WEEKWIN`/`WEEKLOSS` |

还可有 `holdings_*.csv`、`entries_*.csv`。脚本放在 `research/er-r2-floor/run.py`。夹具不过：退出码非 0，四件套一个都不写。锚不过或 ATTRIBUTION 未齐：四件套仍要写，但 `family_verdict` 必须是 `BLOCKED`。

针路径或 `05f0f8a4` 锚提交载不出来：退出码非 0，四件套一个都不写，视为 `BLOCKED`（针缺失，不是锚偏差）。REPORT 都不要写——没有针就没有可引用的 F0。

`summary.json`：

```json
{
  "batch": "er-r2-floor",
  "knife_id": "ER-R2-FLOOR",
  "champion_swap": false,
  "crown": "NO",
  "source_sha": "05f0f8a4f778fde886f3e7b2976646ff4b7d777b",
  "sample": ["2020-01-03", "2026-10-23"],
  "anchor_pass": true,
  "attrib_pass": true,
  "anchor": {"ret": 1.316, "maxDD": -0.188, "Calmar": 0.70, "n_weeks": 349, "T": 348, "n_codes": 324},
  "face_id": "F0",
  "primary": "RF50",
  "floor": "R2(N=90)>=0.50 hard veto on new entries; fill=SHARPE20",
  "h1": "RF50/ER20/AND50 all 证伪",
  "family_verdict": "H1_HOLD",
  "positive_ids": [],
  "skipped_fills": ["RET8", "RET12", "MOM121", "Z121", "R4W", "SORTINO20", "residual-mom", "corr-dedup", "Clenow-SR90", "Clenow-SR60", "Clenow-SR90K2", "AG40", "AG20", "Kaufman-ER10"],
  "cells": []
}
```

`family_verdict` 只允许 `H1_HOLD`、`H1_REJECT`、`BLOCKED`。`anchor_pass=false` 或 `attrib_pass=false` 时必须是 `BLOCKED`，`cells[].verdict` 全部 `BLOCKED`（锚不过时）；ATTRIBUTION 未齐时格子仍可写尺子结果，但家族句必须 `BLOCKED`、不得写 H1_HOLD / H1_REJECT。上面的 JSON 是字段形状；`H1_HOLD` 与空的 `positive_ids` 不要照抄，以尺子为准。`positive_ids` 只装记正的地板邻档 id（含主簿）。

`skipped_fills` 必须含上列十四个名字。AG40S / SHARPE12 / SHARPE40 / RET52 / SOFT / skip-month / MA200 写进 REPORT 跳过段，不要塞进这个数组冒充这十四个。AG40S **不是**闭合填席，也**不是**本刀 F0——只许旁注。

每个 cell：

```json
{
  "id": "RF50",
  "book": "LIVE1430-B45-S20-RF50-max5",
  "mode": "r2",
  "r2_n": 90,
  "r2_theta": 0.50,
  "er_n": 0,
  "er_theta": 0.0,
  "ret": 0.0,
  "maxDD": 0.0,
  "CAGR": 0.0,
  "Calmar": 0.0,
  "avgL": 0.0,
  "avg_turnover_1way": 0.0,
  "n_cash_weeks": 0,
  "n_entries": 0,
  "n_r2_blocked": 0,
  "n_er_blocked": 0,
  "n_floor_blocked": 0,
  "n_miss_r2": 0,
  "n_miss_er": 0,
  "n_empty_slots": 0,
  "mean_r2": 0.0,
  "mean_er": 0.0,
  "mean_abs_D": 0.0,
  "hit_rate": 0.0,
  "win_size": 0.0,
  "jaccard_vs_f0": 0.0,
  "inert": false,
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

F0 的 `mode` 写 `off`，`r2_n` / `er_n` 写 `0`，`r2_theta` / `er_theta` 写 `0`，`n_r2_blocked` / `n_er_blocked` / `n_floor_blocked` / `n_miss_r2` / `n_miss_er` / `mean_r2` / `mean_er` 为 0，`jaccard_vs_f0` 为 1，`inert` 为 false，`delta_*` 为 0，`covers` 为 true，两窗为 true，`verdict` 为 `ANCHOR`。

RF50 的 `mode` 写 `r2`，`r2_n=90`，`r2_theta=0.50`，`er_n=0`，`er_theta=0`，`n_er_blocked=0`，`n_miss_er=0`，`mean_er=0`。

ER20 的 `mode` 写 `er`，`er_n=20`，`er_theta=0.40`，`r2_n=0`，`r2_theta=0`，`n_r2_blocked=0`，`n_miss_r2=0`，`mean_r2=0`。

AND50 的 `mode` 写 `and`，`r2_n=90`，`r2_theta=0.50`，`er_n=20`，`er_theta=0.40`。

四本书名锁死（不要改前缀、不要把 AG40S 写进来）：

| id | book | mode |
|----|------|------|
| F0 | `LIVE1430-B45-S20-max5` | `off` |
| RF50 | `LIVE1430-B45-S20-RF50-max5` | `r2` |
| ER20 | `LIVE1430-B45-S20-ER20-max5` | `er` |
| AND50 | `LIVE1430-B45-S20-AND50-max5` | `and` |

`table.csv` 列：

`id,book,mode,r2_n,r2_theta,er_n,er_theta,ret,maxDD,CAGR,Calmar,w2020_22_ret,w2020_22_maxDD,w2020_22_Calmar,w2023_26_ret,w2023_26_maxDD,w2023_26_Calmar,avgL,avg_turnover_1way,n_cash_weeks,n_entries,n_r2_blocked,n_er_blocked,n_floor_blocked,n_miss_r2,n_miss_er,n_empty_slots,mean_r2,mean_er,mean_abs_D,hit_rate,win_size,jaccard_vs_f0,inert,delta_ret,delta_abs_mdd,covers,window_2020_22,window_2023_26,verdict`

CSV 里 F0 的 mode / r2_n / er_n 写 `off` / `0` / `0`。布尔写 `true` / `false`。四行顺序：`F0,RF50,ER20,AND50`。

`equity.csv` 列：`date,book,nav`。`nav` 是日净收益的 `cumprod`，起点 1。`book` 用上表书名。

`entries_diff_by_year.csv` 列：

`year,id,side,code,n_events,first_date,last_date`

`side` 只允许 `ADD`（该书入场有、F0 无）或 `DROP`（F0 有、该书无）。`year` 为入场周五的日历年。同一 `(year,id,side,code)` 一行。没有 diff 的年可以不写行。

`segment_attribution.csv` 列：

`id,kind,start,end,years,delta_cum_ex,n_weeks,uniq_book,uniq_f0,n_shared`

`kind` 至少含每本非 F0 的 `BIGWIN` 与 `BIGLOSS`。`uniq_book` / `uniq_f0` 为分号分隔的 6 位代码（按该段持有周数取前 8；没有则空字符串）。`years` 写 `2021` 或 `2023-2024` 这种闭区间。`delta_cum_ex` 为该段 `cum_ex[end]−cum_ex[start]`（周超额简单收益累加）。

## 引擎从哪 fork

只读针：

`05f0f8a4f778fde886f3e7b2976646ff4b7d777b`
`research/cloud_batch/SPIKE-S20-BTHETA-GRID-LIVE1430/run.py`

S20 填席点（**不换键**；闸挂在出口）：

| 符号 | 约行 | 地板书改成 |
|------|------|------------|
| `sharpe_n_on` | 160–178 | **不动** |
| `sharpe_key` | 82–84 | **不动** |
| `build_cands` | 261–284 | 出口算该书的 r2 / er；丢掉地板失败的名字 |
| `simulate` 填席 | 339–349 | 仍 `require_sharpe=True` 后取 `slots` |

数据与 `LIVE_PHASE` 同提交：

`research/cloud_batch/CLOUD-BATCH-2026-10-26/`

`LIVE_PHASE = {"紧通道", "冲击"}`，从该提交的 `scripts/backtest.py` 导入。

工作区若没有这些路径：用 `git show` / 只读 worktree 拷到临时目录。不要 `git checkout` 到 btheta 分支上改原文件。不要用 `strategy-weekly/_kit/face_engine.py`——那是压缩突破的 68.1% FACE，不是本刀的面。不要 import `research/clenow-slope-r2-fill/run.py` 或 `research/accel-gate/run.py` 或 `research/residual-mom-fill/run.py` 或 `research/skip-month-csmom/` 或 `research/entry-kaufman-er/`。R² / ER 函数在本目录 `run.py` 里重写；公式与夹具对齐即可，不要为了「复用」把 Clenow score 或 accel 也拉进来。

`summary.json` 的 `source_sha` 写实际载入的提交；载入的不是 `05f0f8a4` 就停（针缺失 → 不写四件套）。

本机解释器 `D:\python\python.exe`。云端用 `python3`。

4 本书在同一次进程里跑完：只改地板闸（F0 关闭）。持仓、成本、E0、SHARPE20、周五 14:30 成交、TV 的 σ20/σ60 保持与针一致。TV 用**这本书自己**的过去日收益。禁止用 510300 或任何单一指数当 σ / L / 闸。

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
| 填席 | **四本都是** `sharpe_key`，`sharpe_n=20`，`require_sharpe=True`，`max_pos=5`。Sharpe 窗截至信号日前一交易日 |
| 地板 | 硬闸书过了地板才进 `C_t` 排序后的补席；回看截至信号日前一交易日 |
| 退出 | E0。原因仅 `breadth_off` / `falsify` / `always_in_flip` / `left_structure` / 末日 `eod_eval`。不因 R² / ER 跌破下限增退出原因 |
| 成本 | `COST_SIDE=0.001` 且 `LIVE_COST_RT=0.002`，两处都留 |
| 杠杆 | `LCAP=1`。`L = min(1, 0.25 / max(σ20, σ60))`，σ 来自该书自身过去非零日收益 × √252，样本短于 2 根时 L=1 |
| 换手 | 再平衡双向权重变化的一半，再对再平衡次数平均，写入 `avg_turnover_1way` |
| 空仓周 | 信号周五（去掉日历哨兵最后一根）持仓为空的周数 |
| 周频 | T=348 个持有周 |

变体不在这 4 个 id 里：退出码非 0，不写四件套。

## 地板实现

截止与 `sharpe_n_on` 对齐，不要用信号日当天收盘（14:30 决策会前瞻）：

```python
def ols_r2(px: np.ndarray) -> float | None:
    """OLS R² of ln(P) on trading-day index 0..n-1. Flat prices → None."""
    n = int(px.size)
    if n < 2:
        return None
    if np.any(~np.isfinite(px)) or np.any(px <= 0):
        return None
    y = np.log(px.astype(float))
    t = np.arange(n, dtype=float)
    t0 = t - t.mean()
    y0 = y - y.mean()
    sxx = float(np.dot(t0, t0))
    syy = float(np.dot(y0, y0))
    sxy = float(np.dot(t0, y0))
    if sxx <= 0 or syy <= 0 or not np.isfinite(sxx + syy + sxy):
        return None
    r2 = (sxy * sxy) / (sxx * syy)
    if not np.isfinite(r2):
        return None
    if r2 < -1e-12 or r2 > 1.0 + 1e-12:
        return None
    return float(min(1.0, max(0.0, r2)))


def r2_on(closes: pd.Series, d: str, n: int = 90) -> float | None:
    """R² of last n daily qfq closes ending the bar before signal Friday."""
    ts = pd.Timestamp(d)
    sub = closes.loc[: ts - pd.Timedelta(days=1)]
    if len(sub) < n:
        return None
    if (ts - sub.index[-1]).days > 5:
        return None
    window = sub.iloc[-n:]
    if len(window) < n:
        return None
    return ols_r2(window.to_numpy(dtype=float))


def kaufman_er(closes: pd.Series, d: str, n: int = 20) -> float | None:
    """Kaufman ER over n steps (needs n+1 closes). None if not gateable."""
    ts = pd.Timestamp(d)
    sub = closes.loc[: ts - pd.Timedelta(days=1)]
    if len(sub) < n + 1:
        return None
    if (ts - sub.index[-1]).days > 5:
        return None
    window = sub.iloc[-(n + 1):]
    diffs = window.diff().abs().iloc[1:]
    if len(diffs) != n:
        return None
    denom = float(diffs.sum())
    if denom <= 0 or not np.isfinite(denom):
        return None
    num = abs(float(window.iloc[-1]) - float(window.iloc[0]))
    if not np.isfinite(num):
        return None
    er = num / denom
    if not np.isfinite(er):
        return None
    return float(er)


def floor_pass(mode: str, r2, er) -> bool:
    if mode == "r2":
        return r2 is not None and r2 >= 0.50
    if mode == "er":
        return er is not None and er >= 0.40
    if mode == "and":
        return (r2 is not None and r2 >= 0.50) and (er is not None and er >= 0.40)
    raise ValueError(mode)
```

硬闸：`floor_pass(mode, r2, er)` 为真才留在 `C_t` 排序后的补席。挂在 `build_cands` 出口，对象已经不包含 `positions`。F0 不调用这些函数。

RF50 **不要**调用 `kaufman_er`。ER20 **不要**调用 `r2_on`。AND50 两个都调。不要为了「顺便披露」在 RF50 上算 ER——那会把两本的缺失计数缠在一起。

`n_r2_blocked`：过了 `is_spike`、有信号价、有有限 S20，但 `r2_on` 为 None 或 `< 0.50` 的（周五, 代码）次数。按 `C_t` 全计，不要按「本会进 top5 才计」。F0 / ER20 写 0。

`n_er_blocked`：同上，对 `kaufman_er` 与 0.40。F0 / RF50 写 0。

`n_floor_blocked`：该书实际丢掉的（周五, 代码）次数。RF50 = `n_r2_blocked`；ER20 = `n_er_blocked`；AND50 = r2 失败或 er 失败的并集（同一名字同一周五只计 1）。F0 写 0。

`n_miss_r2`：过了 `is_spike`、有信号价，但 `r2_on` 返回 None 的（周五, 代码）次数。F0 / ER20 写 0。

`n_miss_er`：过了 `is_spike`、有信号价，但 `kaufman_er` 返回 None 的次数。F0 / RF50 写 0。

`n_empty_slots`：每个 `risk_on` 信号周五，`max(0, slots − 实际新开数)` 求和（去掉哨兵）。

`mean_r2`：仅实际填入的新开/换入名字。没有入场或 r2 缺失则该名字不进均值；均值样本为空写 0。F0 / ER20 写 0。

`mean_er`：同上，ER。F0 / RF50 写 0。

`mean_abs_D`：`risk_on` 且 `|D_t| ≥ 1` 的周，对 `|D_t|` 取均值。没有这类周则写 0。

`jaccard_vs_f0`：该书与 F0 的入场集合（`{(date, code)}`）Jaccard。F0 为 1。任一方入场为空则写 0（F0 除外）。

`inert`：`id ≠ F0` 且（持仓周集合与 F0 相同，或 `n_floor_blocked=0` 且 `n_empty_slots` 与 F0 相同）。

`hit_rate` / `win_size`：仅新开/换入的那只券，从该信号周五收盘到下一信号周五收盘的简单收益。盈利为该收益 > 0。没有下一根信号周五的开仓不进样本。不要用组合周收益冒充个券入场质量。

不要实现 `slope_ann × R²`、不要 raw `β×R²`、不要 `(1+β)^252`、不要加速度、不要 z-score、不要减截面均值、不要 0.75/0.25 合成、不要 `if beta <= 0: None`、不要 signed ER、不要 KAMA SC、不要 ATR 仓位、不要指数 MA 闸、不要短名单按 R² / ER 重排。不要把地板缺失回退成 SHARPE20 硬填满（硬闸书必须空席）或回退成 Clenow。

## 夹具（先跑）

算术用 `pytest` 或脚本内 assert 均可。任一夹具出界：退出码非 0，不写四件套。这些只锁公式，不是策略数字。

构造序列时，信号与最后一根间隔 ≤5 日。R² 夹具 N=90；ER 夹具 N=20（21 根收盘）。

| 名 | 输入 | 应落在 |
|----|------|--------|
| 完美直线 R² | `P_i = exp(0.001 · i)`，`i=0…89` | `R² = 1`（绝对误差 `< 1e-12`）；RF50 **过**；AND50 的 R² 腿 **过** |
| 完美下跌直线 | `P_i = exp(−0.001 · i)`，`i=0…89` | `R² = 1`（`< 1e-12`）；RF50 **过**（地板不管方向，禁止因 β<0 挡） |
| 价格全平 R² | 90 根常数 10.0 | `R² = None`；RF50 **不过** |
| R² 缺档 | 前一交易日距信号 >5 日 | `None`；RF50 不过 |
| R² 根数不足 | 只有 89 根 | `None` |
| R² 非正价格 | 窗内有 ≤0 | `None` |
| 不乘斜率 | 两列形状相同（同一组残差）、一组 β 大约另一组两倍 | 两列 `R²` 必须相同（绝对误差 `< 1e-12`）。实现不得返回 `slope_ann×R²` |
| 曲折低 R² | `P_i = exp(0.001·i + 0.08·(−1)^i)`，`i=0…89` | `R² < 0.50`；RF50 **不过**。夹具只锁「低于 0.50」，不锁精确值 |
| ER 单边 | N=20，收盘 `10,11,…,30`（21 根） | `ER ∈ [0.999999, 1.000001]`；ER20 **过** |
| ER 折返 | N=20，`10,11` 交替共 21 根，起止同为 10 | `ER ∈ [−1e-12, 1e-12]`；ER20 **不过** |
| ER 全平 | 21 根常数 10 | `ER = None`；ER20 **不过** |
| ER 必须是 N=20 | 21 根收盘：`10,20` 交替共 10 根，再接 `21,22,…,31` | `ER(10)=1`（`< 1e-12`）；`ER(20) ∈ (0.20, 0.22)`。N=10 会过 0.40，N=20 **不过**。实现必须走出 N=20 |
| AND 合取 | R²=1 且 ER=0 | AND50 **不过**（ER 腿失败） |
| AND 合取 2 | R²=None 且 ER=1 | AND50 **不过**（缺 R²） |
| AND 合取 3 | R²=1 且 ER=1 | AND50 **过** |

夹具可用合成 `pd.Series`，不必读日线缓存。「曲折低 R²」若因随机实现偶发 ≥0.50：加大交替振幅到 0.12 再断言 `< 0.50`，不要改 θ。

套叠窗 / Clenow score / accel 对照不要做成可切换的生产分支。

## 尺子

与 DESIGN 相同。不要在跑批脚本里另写 0.9× 或 −2pp。

```
记正 = (Δret ≥ Δ|MDD|) 且 (2020-22 ret ≥ F0) 且 (2023-26 ret ≥ F0) 且 (非惰性)
F0.verdict = ANCHOR
family_verdict = H1_HOLD    若三本地板都是证伪（含惰性）且 anchor_pass 且 attrib_pass
family_verdict = H1_REJECT  若至少一本记正且 anchor_pass 且 attrib_pass
family_verdict = BLOCKED    若 anchor_pass=false 或 attrib_pass=false
```

hit-rate / win-size / `mean_r2` / `mean_er` / `n_floor_blocked` / Jaccard 只进表与 ATTRIBUTION，不进 `verdict`（惰性除外——惰性直接证伪）。

不要拿 AG40S 的 235.6% / −14.8% / 1.32 当尺子右侧，也不要拿 SR90 72.8% 或 ER10-T40 69.6% 横比。

## ATTRIBUTION（REPORT 独立段，不翻转旗标；#2 起硬闸）

必须有 `## ATTRIBUTION` 标题。必须按 (a)–(e) 五块写，缺一块则 `attrib_pass=false`：

1. **(a) 机制**：只加了 R²/ER 下限硬闸；列出未动的 B45 / spike_ft / max5 / E0 / TV25 / **SHARPE20 填席** / Fri≥14:30 / 0.2%RT / AUM≥2。
2. **(b) 席位**：RF50 / ER20 / AND50 相对 F0 的 Jaccard（引用 `jaccard_vs_f0`）。
3. **(c) 分段**：两窗 Δret 与是否踏空（引用 Δ 表）。
4. **(d) 换手与空仓周**相对 F0，并报 `n_empty_slots`。
5. **(e) 名字·年份和大赢/大亏段**（#1 欠的，本刀必须有，否则不得判卷）：
   - 引用 `entries_diff_by_year.csv`：每个非 F0 书、每个有 diff 的年，列出 ADD 前 5 与 DROP 前 5（代码 + `n_events`）。无 diff 的年跳过。
   - 引用 `segment_attribution.csv`：每个非 F0 书必须能指认一条 BIGWIN、一条 BIGLOSS——起止日、所跨年份、`delta_cum_ex`、`uniq_book` 与 `uniq_f0` 代码。
   - 周超额：信号周五到下一信号周五，`ex_t = r_book,t − r_F0,t`，`r` 为该书 NAV 比 − 1（不是个券）。`cum_ex` 为 `ex` 的累加（不是再复合）。BIGWIN = `cum_ex[j]−cum_ex[i]` 最大的 `i<j` 段；BIGLOSS = 该差最小（最负）的段。并列取更早的 `i`，再取更短的 `j−i`。
   - 真惰性：写「与 F0 席位逐周相同，无名字可列」，CSV 仍要有 BIGWIN/BIGLOSS 行，`uniq_*` 空、`delta_cum_ex=0`。

结尾：「ATTRIBUTION 不进 verdict。」

`attrib_pass` 为 true 当且仅当：

- REPORT 有 `## ATTRIBUTION`；
- (a)–(e) 五块都在；
- 两个支持 CSV 存在且可读；
- RF50 / ER20 / AND50 在 `segment_attribution.csv` 里各有 `BIGWIN` 与 `BIGLOSS` 行，且每行有 `start` / `end`；
- (e) 对每本非 F0 书要么点名了至少一个 6 位代码（ADD/DROP 或 uniq_*），要么显式写了惰性句。

不要在这段发明 Brinson / 因子分解，不要用 ATTRIBUTION 把证伪改成记正。#1 REPORT 那种只报 Jaccard + 窗 Δ、不报名字的写法，本刀算 `attrib_pass=false`。

## 锚点不过时的写法

F0 先与 DESIGN 的锚比较。不过：

- 四件套仍写完，4 本数字照实
- `anchor_pass=false`，`family_verdict=BLOCKED`
- REPORT 写明 F0 实际 ret / maxDD / Calmar，以及它更接近 131.6/0.70、158.3/0.94、nob_ref 134.0/0.70、KB 135.0/0.74，还是 PR#67 的 131.9/0.70
- 停止。不去调成本、不去换宽度、不去贴另一条引擎

针或 `CLOUD-BATCH-2026-10-26` 缺失：

- 不写 `out/` 四件套
- 退出码非 0
- stderr 写明缺的路径 / SHA
- 不要换 `face_engine.py` 凑合

## 实现时不要做的事

- 不要跑第 5 本书，不要跑 ER10，不要跑 ER N∈{8,10,90}，不要跑 θ∈{0.30,0.35,0.50,0.75}。
- 不要跑 R² 阈值 0.30/0.45/0.55/0.75，不要跑 R² N∈{20,60,70,80,100}。
- 不要跑 `β>0` 另闸，不要把 R² 乘进 S20 / Clenow score。
- 不要把闸叠到 Clenow SR90/SR60/SR90K2 填席上，不要 import `research/clenow-slope-r2-fill/run.py`。
- 不要实现加速度、不要 import `research/accel-gate/run.py`，不要把 AG40S 写成第 4 本或新 F0。
- 不要实现次级排序 / 软闸 / 半权。
- 不要 import `research/entry-kaufman-er/run.py` 来「顺便」重跑 ER10。
- 不要重开 RET8/RET12 窗插值（KB：后段踏空，不扫窗）。
- 不要重开 MOM121 W7525 / W67 / W85（假设#4 已证伪）。
- 不要重开 Z121、R4W 原始近月、SOFT4535、NOBREADTH、SHARPE12/SHARPE40、SORTINO20 填席。
- 不要重开 residual-mom（R12w 去均值）或 corr-dedup（S20 后再 ρ\*）或 skip-month CSMOM。
- 不要读 510300 当闸 / σ / L。TV 仍用该书自身日收益。
- 不要把 TV 网格的 158.3% 当成 F0 目标，也不要把 nob_ref 134.0%、KB 135.0% 或 PR#67 的 131.9% 当成 F0。
- 不要用 `strategy-weekly/_kit/face_engine.py`。
- 不要打开 R 闸，不要叠 PT / COOL / HYST / 软门 / 换手惩罚 / ATR 仓位 / 指数 MA200。
- 不要用 `0.9 ×` 或 `−2pp`。
- 不要改 `strategy_exec`、`LIVE_OPS`、`champion_mast`、实盘、固收+、红利袖。
- 不要在看到结果之后改 `DESIGN.md` 的地板定义、邻档、尺子和锚。
- 不要把 data cache 提交进 PR。
- 不要发明 MOM121 / RET8 / Z121 / residual-mom / corr-dedup / SORTINO20 / Clenow-SR\* / AG40 / ER10 的「延窗换算」数字。引用只用 KB / PR / 已发表 `out/` 原文。
- 不要在 ATTRIBUTION 齐之前写 `H1_HOLD` / `H1_REJECT`。
- 不要把 AG40S 的 235.6% 写进主表或 Δ 表。

## 拍板问句（REPORT 首行，原样）

请拍板：在面层 B45 + spike_ft max5 + E0 + TV25、LIVE≥14:30 面上，填席键仍是 SHARPE20，只对新开/换入加一道路径曲折下限。主口径冻结为 N=90 根交易日 OLS 对数价格 R² ≥ 0.50。邻档只留 ER(N=20)≥0.40 与两者同时过闸。已持仓不因 R² / ER 跌破下限而平。无论记正与否都不换冠。
