# Composer 交接 · clenow-slope-r2-fill

照此实现并跑完 **4 本书**（F0 + 主簿 SR90 + 窗邻档 SR60 + 权邻档 SR90K2）。缺参数就停，不要补一套「合理默认」。不要再开网格，不要循环插值，不要跑回测主循环以外的「顺便扫一下」。不要实现 raw `β×R²` 主簿，不要实现 `(1+β)^252`，不要实现加速度闸或 ER/R² 地板，不要读 510300。

本 PR 的设计分支只交 `DESIGN.md` 与本文件。执行方另开分支写 `run.py` 和四件套。本文件被执行前，设计 PR 里不应出现 NAV。

## 跑完之后的四件套

写到 `research/clenow-slope-r2-fill/out/`，不多也不少：

| 文件 | 内容 |
|------|------|
| `REPORT.md` | 五段，顺序见 DESIGN「报告四件套」。必须有名为 **ATTRIBUTION** 的独立段。首行贴 DESIGN 的拍板问句。接着原样贴 DESIGN 的 H1 代码块。然后锚点门、主表、Δ 表、填席质量旁注、ATTRIBUTION、证伪段、红线 |
| `summary.json` | 下面的字段 |
| `table.csv` | **4 行**，列顺序固定 |
| `equity.csv` + `equity_curve.png` | 4 条净值。图用对数轴，F0 黑线、线宽 2.2；三本斜率灰色细线 |

支持文件可以有 `holdings_*.csv`、`entries_*.csv`，不替代四件套。脚本放在 `research/clenow-slope-r2-fill/run.py`。夹具不过：退出码非 0，四件套一个都不写。锚不过：四件套仍要写，但 `family_verdict` 必须是 `BLOCKED`。

针路径或 `05f0f8a4` 锚提交载不出来：退出码非 0，四件套一个都不写，视为 `BLOCKED`（针缺失，不是锚偏差）。REPORT 都不要写——没有针就没有可引用的 F0。

`summary.json`：

```json
{
  "batch": "clenow-slope-r2-fill",
  "knife_id": "CLENOW-SLOPE-R2-FILL",
  "champion_swap": false,
  "crown": "NO",
  "source_sha": "05f0f8a4f778fde886f3e7b2976646ff4b7d777b",
  "sample": ["2020-01-03", "2026-10-23"],
  "anchor_pass": true,
  "anchor": {"ret": 1.316, "maxDD": -0.188, "Calmar": 0.70, "n_weeks": 349, "T": 348, "n_codes": 324},
  "face_id": "F0",
  "primary": "SR90",
  "clenow": "score=(exp(beta*252)-1)*(R2**k); N=90 k=1 primary",
  "h1": "SR90/SR60/SR90K2 all 证伪",
  "family_verdict": "H1_HOLD",
  "positive_ids": [],
  "skipped_fills": ["RET8", "RET12", "MOM121", "Z121", "R4W", "SORTINO20", "residual-mom", "corr-dedup"],
  "cells": []
}
```

`family_verdict` 只允许 `H1_HOLD`、`H1_REJECT`、`BLOCKED`。`anchor_pass=false` 时必须是 `BLOCKED`，`cells[].verdict` 全部 `BLOCKED`。上面的 JSON 是字段形状；`H1_HOLD` 与空的 `positive_ids` 不要照抄，以尺子为准。`positive_ids` 只装记正的斜率邻档 id（含主簿）。

`skipped_fills` 必须含上列八个名字。SHARPE12 / SHARPE40 / RET52 / SOFT / skip-month 写进 REPORT 跳过段，不要塞进这个数组冒充这八个。

每个 cell：

```json
{
  "id": "SR90",
  "book": "LIVE1430-B45-SR90-max5",
  "n": 90,
  "k": 1,
  "ret": 0.0,
  "maxDD": 0.0,
  "CAGR": 0.0,
  "Calmar": 0.0,
  "avgL": 0.0,
  "avg_turnover_1way": 0.0,
  "n_cash_weeks": 0,
  "n_entries": 0,
  "n_miss_clenow": 0,
  "mean_r2": 0.0,
  "mean_score": 0.0,
  "mean_abs_D": 0.0,
  "hit_rate": 0.0,
  "win_size": 0.0,
  "jaccard_vs_f0": 0.0,
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

F0 的 `n` / `k` 写 `20` / `0`（表示 S20，k 关闭），`n_miss_clenow` / `mean_r2` / `mean_score` 为 0，`jaccard_vs_f0` 为 1，`delta_*` 为 0，`covers` 为 true，两窗为 true，`verdict` 为 `ANCHOR`。

`table.csv` 列：

`id,book,n,k,ret,maxDD,CAGR,Calmar,w2020_22_ret,w2020_22_maxDD,w2020_22_Calmar,w2023_26_ret,w2023_26_maxDD,w2023_26_Calmar,avgL,avg_turnover_1way,n_cash_weeks,n_entries,n_miss_clenow,mean_r2,mean_score,mean_abs_D,hit_rate,win_size,jaccard_vs_f0,delta_ret,delta_abs_mdd,covers,window_2020_22,window_2023_26,verdict`

CSV 里 F0 的 n / k 写 `20` / `0`。布尔写 `true` / `false`。四行顺序：`F0,SR90,SR60,SR90K2`。

`equity.csv` 列：`date,book,nav`。`nav` 是日净收益的 `cumprod`，起点 1。`book` 用上表书名。

## 引擎从哪 fork

只读针：

`05f0f8a4f778fde886f3e7b2976646ff4b7d777b`
`research/cloud_batch/SPIKE-S20-BTHETA-GRID-LIVE1430/run.py`

S20 填席点（只换这里）：

| 符号 | 约行 | 斜率书改成 |
|------|------|------------|
| `sharpe_n_on` | 160–178 | 另写 `clenow_score_on`；F0 仍调 `sharpe_n_on` |
| `sharpe_key` | 82–84 | 另写 `clenow_key` |
| `Cand.sharpe` | 68 | 斜率书加 `score: float \| None`（可复用字段，但 F0 不要往里塞 Clenow） |
| `build_cands` | 261–284 | 斜率书对 spike 池算 score；`skip=set(positions)` 不动 |
| `simulate` 填席 | 339–349 | `require_clenow=True` 后按 `clenow_key` 取 `slots` |

数据与 `LIVE_PHASE` 同提交：

`research/cloud_batch/CLOUD-BATCH-2026-10-26/`

`LIVE_PHASE = {"紧通道", "冲击"}`，从该提交的 `scripts/backtest.py` 导入。

工作区若没有这些路径：用 `git show` / 只读 worktree 拷到临时目录。不要 `git checkout` 到 btheta 分支上改原文件。不要用 `strategy-weekly/_kit/face_engine.py`——那是压缩突破的 68.1% FACE，不是本刀的面。不要 import `research/residual-mom-fill/run.py` 或 `research/skip-month-csmom/` 或 `research/RESEARCH-SKIP-MONTH-CSMOM-WEEKLY/`。

`summary.json` 的 `source_sha` 写实际载入的提交；载入的不是 `05f0f8a4` 就停（针缺失 → 不写四件套）。

本机解释器 `D:\python\python.exe`。云端用 `python3`。

4 本书在同一次进程里跑完：只改填席键（F0 仍 SHARPE20）。持仓、成本、E0、周五 14:30 成交、TV 的 σ20/σ60 保持与针一致。TV 用**这本书自己**的过去日收益。禁止用 510300 或任何单一指数当 σ / L / 闸。

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
| 斜率填席 | `clenow_key`，`require_clenow=True`，`max_pos=5`。回看截至信号日前一交易日 |
| 退出 | E0。原因仅 `breadth_off` / `falsify` / `always_in_flip` / `left_structure` / 末日 `eod_eval` |
| 成本 | `COST_SIDE=0.001` 且 `LIVE_COST_RT=0.002`，两处都留 |
| 杠杆 | `LCAP=1`。`L = min(1, 0.25 / max(σ20, σ60))`，σ 来自该书自身过去非零日收益 × √252，样本短于 2 根时 L=1 |
| 换手 | 再平衡双向权重变化的一半，再对再平衡次数平均，写入 `avg_turnover_1way` |
| 空仓周 | 信号周五（去掉日历哨兵最后一根）持仓为空的周数 |
| 周频 | T=348 个持有周 |

变体不在这 4 个 id 里：退出码非 0，不写四件套。

## 斜率实现

截止与 `sharpe_n_on` 对齐，不要用信号日当天收盘（14:30 决策会前瞻）：

```python
def clenow_score_on(
    closes: pd.Series, d: str, n: int, k: int
) -> tuple[float | None, float | None]:
    """Return (score, r2). Both None if not rankable."""
    ts = pd.Timestamp(d)
    sub = closes.loc[: ts - pd.Timedelta(days=1)]
    if len(sub) < n:
        return None, None
    if (ts - sub.index[-1]).days > 5:
        return None, None
    window = sub.iloc[-n:]
    if len(window) < n:
        return None, None
    px = window.to_numpy(dtype=float)
    if np.any(~np.isfinite(px)) or np.any(px <= 0):
        return None, None
    y = np.log(px)
    t = np.arange(n, dtype=float)  # 0..n-1 trading-day index
    t0 = t - t.mean()
    y0 = y - y.mean()
    sxx = float(np.dot(t0, t0))
    syy = float(np.dot(y0, y0))
    sxy = float(np.dot(t0, y0))
    if sxx <= 0 or syy <= 0 or not np.isfinite(sxx + syy + sxy):
        return None, None
    beta = sxy / sxx
    r2 = (sxy * sxy) / (sxx * syy)
    if (not np.isfinite(beta)) or (not np.isfinite(r2)):
        return None, None
    if r2 < -1e-12 or r2 > 1.0 + 1e-12:
        return None, None
    r2 = float(min(1.0, max(0.0, r2)))
    slope_ann = float(np.exp(beta * 252.0) - 1.0)
    if not np.isfinite(slope_ann):
        return None, None
    score = float(slope_ann * (r2 ** k))
    if not np.isfinite(score):
        return None, None
    return score, r2


def clenow_key(c, pool):
    miss = 0 if c.score is not None else 1
    return (miss, -(c.score if c.score is not None else 0.0), c.code)
```

年化恒等（夹具锁）：`exp(beta * 252) - 1 == exp(beta) ** 252 - 1`。实现只写其中一套。

禁止实现：

```python
# 不要
score = beta * r2
score = ((1 + beta) ** 252) * r2
slope_ann = (np.exp(beta) ** 250) - 1
slope_ann = (np.exp(beta) ** 260) - 1
score = (np.exp(beta * 252) - 1) * r2 * 100   # 展示 ×100 会换单位；本卡小数
```

| 书 | `n` | `k` | book |
|----|-----|-----|------|
| SR90 | 90 | 1 | `LIVE1430-B45-SR90-max5` |
| SR60 | 60 | 1 | `LIVE1430-B45-SR60-max5` |
| SR90K2 | 90 | 2 | `LIVE1430-B45-SR90K2-max5` |

每个信号周五：

1. 先对**全部**当周 spike_ft（含已持仓）算该书的 `(score, r2)`，构成 `D_t`。
2. `build_cands` 仍 `skip=set(positions)`。`require_clenow=True` 后按 `clenow_key` 取 `slots`。
3. 不要要求 `|D_t| ≥ 2`（没有去均值）。`C_t` 为空则本周不新开。
4. 不要因 score<0 拒填；负分可以进排序。

`n_miss_clenow`：过了 `is_spike`、有信号价，但 `clenow_score_on` 返回 None 的（周五, 代码）次数。按名字计，不要按「本会进 top5 才计」。F0 不调用斜率函数。

`mean_r2` / `mean_score`：仅实际填入的新开/换入名字。没有入场则写 0。F0 写 0。

`mean_abs_D`：`risk_on` 且 `|D_t| ≥ 1` 的周，对 `|D_t|` 取均值。没有这类周则写 0。

`jaccard_vs_f0`：该书与 F0 的入场集合（`{(date, code)}`）Jaccard。F0 为 1。任一方入场为空则写 0（F0 除外）。

`hit_rate` / `win_size`：仅新开/换入的那只券，从该信号周五收盘到下一信号周五收盘的简单收益。盈利为该收益 > 0。没有下一根信号周五的开仓不进样本。不要用组合周收益冒充个券入场质量。

不要实现 β×510300、不要 z-score、不要减截面均值、不要 0.75/0.25 合成、不要加速度、不要 `if r2 < thresh: None`、不要 `if slope_ann <= 0: None`、不要 ATR 仓位、不要指数 MA 闸。不要把 score 缺失回退成 SHARPE20 或 RET12。

## 夹具（先跑）

算术用 `pytest` 或脚本内 assert 均可。任一夹具出界：退出码非 0，不写四件套。这些只锁公式，不是策略数字。

| 名 | 输入 | 应落在 |
|----|------|--------|
| 完美指数 | `P_i = exp(0.001 · i)`，`i=0…89`，信号与最后一根间隔 ≤5 日 | `β = 0.001`（绝对误差 `< 1e-12`）；`R² = 1`（`< 1e-12`）；`score = exp(0.001·252)−1`（`< 1e-12`）；`k=2` 时 score 相同（因为 R²=1） |
| 年化恒等 | 同上的 β | `exp(β·252)−1` 与 `exp(β)**252 − 1` 绝对误差 `< 1e-12` |
| 价格全平 | 90 根常数 10.0 | `(score, r2) = (None, None)`（Syy=0） |
| 缺档 | 前一交易日距信号 >5 日 | `(None, None)` |
| 根数不足 | 只有 89 根 | `(None, None)` |
| 非正价格 | 窗内有 ≤0 | `(None, None)` |
| 拒绝 Teddy 分叉 | `β=0.001`，`R²=1` | Teddy 误写 `(1+β)**252` ≈ **1.2864**；本卡 `exp(β·252)−1` ≈ **0.2866**。实现必须走出后者；两值绝对差 `> 0.9`（不要把 Teddy 再减 1 当成「已经对齐」——那是另一条近亲误写，也不跑） |
| k=1 vs k=2 换序 | A：`slope_ann=0.40`，`R²=0.50`；B：`slope_ann=0.22`，`R²=0.90` | k=1：A=0.20 > B=0.198；k=2：A=0.10 < B=0.1782。SR90 与 SR90K2 不得共用同一排序键 |

夹具可用合成 `pd.Series`，不必读日线缓存。

## 尺子

与 DESIGN 相同。不要在跑批脚本里另写 0.9× 或 −2pp。

```
记正 = (Δret ≥ Δ|MDD|) 且 (2020-22 ret ≥ F0) 且 (2023-26 ret ≥ F0)
F0.verdict = ANCHOR
family_verdict = H1_HOLD   若三本斜率都是证伪
family_verdict = H1_REJECT 若至少一本记正
```

hit-rate / win-size / `mean_r2` / `mean_score` / `mean_abs_D` / Jaccard 只进表与 ATTRIBUTION，不进 `verdict`。

## ATTRIBUTION（REPORT 独立段，不翻转旗标）

必须有 `## ATTRIBUTION` 标题。最少四句：

1. 机制：只换填席键；列出未动的 B45 / spike_ft / max5 / E0 / TV25 / Fri≥14:30 / 0.2%RT / AUM≥2。
2. 席位：SR90 / SR60 / SR90K2 相对 F0 的 Jaccard（引用 `jaccard_vs_f0`）。
3. 分段：两窗 Δret 与是否踏空（引用 Δ 表）。
4. 换手与空仓周相对 F0。结尾：「ATTRIBUTION 不进 verdict。」

不要在这段发明 Brinson / 因子分解，不要用 ATTRIBUTION 把证伪改成记正。

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

- 不要跑第 5 本书，不要跑 raw `β×R²`，不要跑 `(1+β)^252`，不要跑 250/260 年化，不要跑 N=120/125/250。
- 不要跑 vol-scaled、S20 互补、k=0.5/k=3、加速度、ER、R² 地板、斜率>0 硬闸。
- 不要重开 RET8/RET12 窗插值（KB：后段踏空，不扫窗）。
- 不要重开 MOM121 W7525 / W67 / W85（假设#4 已证伪）。
- 不要重开 Z121、R4W 原始近月、SOFT4535、NOBREADTH、SHARPE12/SHARPE40、SORTINO20 填席。
- 不要重开 residual-mom（R12w 去均值）或 corr-dedup（S20 后再 ρ\*）或 skip-month CSMOM。
- 不要读 510300，不要用任何单一指数当闸 / σ / L。
- 不要把 TV 网格的 158.3% 当成 F0 目标，也不要把 nob_ref 134.0%、KB 135.0% 或 PR#67 的 131.9% 当成 F0。
- 不要用 `strategy-weekly/_kit/face_engine.py`。
- 不要打开 R 闸，不要叠 PT / COOL / HYST / 软门 / 换手惩罚 / ATR 仓位 / 指数 MA200。
- 不要用 `0.9 ×` 或 `−2pp`。
- 不要改 `strategy_exec`、`LIVE_OPS`、`champion_mast`、实盘、固收+、红利袖。
- 不要在看到结果之后改 `DESIGN.md` 的分数定义、邻档、尺子和锚。
- 不要把 data cache 提交进 PR。
- 不要发明 MOM121 / RET8 / Z121 / residual-mom / corr-dedup / SORTINO20 填席的「延窗换算」数字。引用只用 KB / PR / 已发表 `out/` 原文。

## 拍板问句（REPORT 首行，原样）

请拍板：在面层 B45 + spike_ft max5 + E0 + TV25、LIVE≥14:30 面上，只改填席键：SHARPE20 → Clenow 对数价格回归年化斜率 × R²。主口径冻结为 N=90 根交易日、score = (e^{β·252} − 1) × R²（小数单位，不含 ×100）。取 top max5 腿内等权。无论记正与否都不换冠。
