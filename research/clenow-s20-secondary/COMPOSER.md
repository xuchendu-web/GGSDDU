# Composer 交接 · clenow-s20-secondary

照此实现并跑完 **4 本书**（F0 + 主簿 CS90S + 邻档 CS60S + 邻档 CS90R）。缺参数就停，不要补一套「合理默认」。不要再开网格，不要循环插值，不要跑回测主循环以外的「顺便扫一下」。

四本锁定为 `F0/CS90S/CS60S/CS90R`。不要实现 CS90K2（哪怕 #1 有 `slope_ann × (R²)^2`）。不要做 CS90×accel 近分断同分。不要做 CS90S-top。不要把 Clenow 换成填席键。不要设 `β>0`、R² 或 ER 硬闸。不要读 510300 当 σ / L / 闸。

不要 import `research/clenow-slope-r2-fill/run.py`、`research/accel-gate/run.py`、`research/er-r2-floor/run.py`、`research/r2-er-secondary/run.py`。#1 那份会在 score 缺失时丢席，和本刀相反。

公式以 `DESIGN.md` 为准，id / 窗长 / 锚以 `SPEC.json` 为准，取席语义以 `band.py` 为准。三处对不上就停，不要私下调和。

设计 PR 里的 `run.py` 是 stub，执行会直接退出。执行分支**替换**它。替换前不要写 `research/clenow-s20-secondary/out/`。`band.py` 与 `test_band.py` 留下。夹具不过：退出码非 0，四件套一个都不写。

```
python3 research/clenow-s20-secondary/test_band.py
```

## 跑完之后的四件套

写到 `research/clenow-s20-secondary/out/`：

| 文件 | 内容 |
|------|------|
| `REPORT.md` | 五段，顺序见 DESIGN「报告四件套」。必须有名为 **ATTRIBUTION** 的独立段，且 (a)–(e) 齐。首行贴 DESIGN 的拍板问句。接着原样贴 DESIGN 的 H1 代码块 |
| `summary.json` | 下面的字段 |
| `table.csv` | **4 行**，列顺序固定 |
| `equity.csv` + `equity_curve.png` | 4 条净值。对数轴。F0 黑线、线宽 2.2；三本排序书灰色细线 |

ATTRIBUTION 支持文件（必须有，不替代四件套）：

| 文件 | 内容 |
|------|------|
| `out/entries_diff_by_year.csv` | 相对 F0 的入场 ADD/DROP，按年、按书 |
| `out/segment_attribution.csv` | 每本非 F0 至少一行 `BIGWIN`、一行 `BIGLOSS` |

针路径或 `05f0f8a4` 载不出来：退出码非 0，四件套一个都不写。没有针就没有可引用的 F0。

锚不过、实现门不过、或 ATTRIBUTION 未齐：四件套仍要写，`family_verdict=BLOCKED`。

`summary.json` 字段形状：

```json
{
  "batch": "clenow-s20-secondary",
  "knife_id": "CLENOW-S20-SECONDARY",
  "champion_swap": false,
  "crown": "NO",
  "source_sha": "05f0f8a4f778fde886f3e7b2976646ff4b7d777b",
  "sample": ["2020-01-03", "2026-10-23"],
  "anchor_pass": true,
  "impl_pass": true,
  "attrib_pass": true,
  "anchor": {"ret": 1.316, "maxDD": -0.188, "Calmar": 0.70, "n_weeks": 349, "T": 348, "n_codes": 324},
  "face_id": "F0",
  "primary": "CS90S",
  "third_book": "CS90R",
  "books_locked": "F0/CS90S/CS60S/CS90R",
  "mechanism": "S20 band secondary sort; CS90S=Clenow(N=90); CS60S=Clenow(N=60); CS90R=slope_ann(N=90) without R^2; no hard gate",
  "h1": "filled by the ruler",
  "family_verdict": "H1_HOLD",
  "positive_ids": [],
  "skipped_ids": ["CS90K2", "CS90xACCEL", "CS90S-top", "SR90", "SR60", "SR90K2", "R290S", "ER20S", "COMBOS", "AG40", "AG20", "AG40S"],
  "side_note": {"AG40S": "235.6%/-14.8%/1.32 mechanism template only; not a cell; not the ruler RHS"},
  "cells": []
}
```

`family_verdict` 只允许 `H1_HOLD`、`H1_REJECT`、`BLOCKED`。上面的 `H1_HOLD` 与空的 `positive_ids` 是形状，不要照抄，以尺子为准。`positive_ids` 只装记正的排序书 id。AG40S 只放在 `side_note`。

`anchor_pass=false` 或 `impl_pass=false` 或 `attrib_pass=false` → `family_verdict=BLOCKED`。锚不过时 `cells[].verdict` 全部 `BLOCKED`。实现门不过时，偏离的那本以及家族句都是 `BLOCKED`（其余本可以仍按尺子写，但家族句不得是 H1_HOLD / H1_REJECT）。ATTRIBUTION 未齐时格子仍可写尺子结果，家族句必须 `BLOCKED`。

每个 cell：

```json
{
  "id": "CS90S",
  "book": "LIVE1430-B45-S20-CS90S-max5",
  "mode": "clenow_sort",
  "n": 90,
  "ret": 0.0,
  "maxDD": 0.0,
  "CAGR": 0.0,
  "Calmar": 0.0,
  "avgL": 0.0,
  "avg_turnover_1way": 0.0,
  "n_cash_weeks": 0,
  "n_entries": 0,
  "n_rerank": 0,
  "n_miss_clenow": 0,
  "n_empty_slots": 0,
  "n_short_fills": 0,
  "n_fallback_weeks": 0,
  "mean_score": 0.0,
  "mean_slope_ann": 0.0,
  "mean_r2": 0.0,
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

| id | book | mode | n | 排序键 |
|----|------|------|---|--------|
| F0 | `LIVE1430-B45-S20-max5` | `off` | 0 | 无 |
| CS90S | `LIVE1430-B45-S20-CS90S-max5` | `clenow_sort` | 90 | `(exp(β·252)−1)×R²` |
| CS60S | `LIVE1430-B45-S20-CS60S-max5` | `clenow_sort` | 60 | 同公式 |
| CS90R | `LIVE1430-B45-S20-CS90R-max5` | `slope_ann_sort` | 90 | `exp(β·252)−1` |

F0：`n_rerank` / `n_miss_clenow` / `n_short_fills` / `n_fallback_weeks` / `mean_score` / `mean_slope_ann` / `mean_r2` 为 0，`jaccard_vs_f0` 为 1，`inert` 为 false，`delta_*` 为 0，`covers` 与两窗为 true，`verdict` 为 `ANCHOR`。

三本排序书的 `n_short_fills` 都为 0，否则 `impl_pass=false`。CS90S 与 CS90R 的 `n_miss_clenow` 必须相等，否则 `impl_pass=false`。

`verdict` 只允许 `ANCHOR`、`记正`、`证伪`、`证伪·惰性`、`BLOCKED`。

`table.csv` 列，顺序固定：

`id,book,mode,n,ret,maxDD,CAGR,Calmar,w2020_22_ret,w2020_22_maxDD,w2020_22_Calmar,w2023_26_ret,w2023_26_maxDD,w2023_26_Calmar,avgL,avg_turnover_1way,n_cash_weeks,n_entries,n_rerank,n_miss_clenow,n_empty_slots,n_short_fills,n_fallback_weeks,mean_score,mean_slope_ann,mean_r2,mean_abs_D,hit_rate,win_size,jaccard_vs_f0,inert,delta_ret,delta_abs_mdd,covers,window_2020_22,window_2023_26,verdict`

四行顺序：`F0,CS90S,CS60S,CS90R`。布尔写 `true` / `false`。JSON 与 CSV 用小数，不用百分数。REPORT 主表用一位百分数、Calmar 两位；Δ 表用 pp（小数 ×100，标 pp）。

`equity.csv` 列：`date,book,nav`。`nav` 是日净收益的 `cumprod`，起点 1。`book` 用上表书名。

`entries_diff_by_year.csv` 列：

`year,id,side,code,n_events,first_date,last_date`

`side` 只允许 `ADD`（该书入场有、F0 无）或 `DROP`（F0 有、该书无）。`year` 为入场周五的日历年。同一 `(year,id,side,code)` 一行。

`segment_attribution.csv` 列：

`id,kind,start,end,years,delta_cum_ex,n_weeks,uniq_book,uniq_f0,n_shared`

`kind` 至少含每本非 F0 的 `BIGWIN` 与 `BIGLOSS`。`uniq_book` / `uniq_f0` 为分号分隔的 6 位代码，按该段持有周数取前 8；没有则空字符串。`years` 写 `2021` 或 `2023-2024`。`delta_cum_ex` 为该段 `cum_ex[end] − cum_ex[start]`。

## 引擎从哪 fork

只读针：

`05f0f8a4f778fde886f3e7b2976646ff4b7d777b`
`research/cloud_batch/SPIKE-S20-BTHETA-GRID-LIVE1430/run.py`

数据与 `LIVE_PHASE` 同提交：`research/cloud_batch/CLOUD-BATCH-2026-10-26/`。`LIVE_PHASE = {"紧通道", "冲击"}`，从该提交的 `scripts/backtest.py` 导入。

工作区若没有这些路径：`git show` 或只读 worktree 拷到临时目录。不要 checkout 到针分支上改原文件。不要用 `strategy-weekly/_kit/face_engine.py`。

`summary.json` 的 `source_sha` 写实际载入的提交。载入的不是 `05f0f8a4` 就停。

本机解释器 `D:\python\python.exe`。云端用 `python3`。

4 本书在同一次进程里跑完。持仓、成本、E0、SHARPE20、周五 14:30 成交、TV 的 σ20/σ60 与针一致。TV 用这本书自己的过去日收益。

## 冻结参数

| 名 | 值 |
|----|----|
| `EVAL_START` / `END_S` | `2020-01-03` / `2026-10-23` |
| 宇宙 | `universe_replace_only_436.csv`，`aum >= 2`，代码 zfill 6 |
| 信号价 | `fri_1430_through_20261023.csv`；`qfq_1430 = price_1430 × (日 qfq / sina)` |
| 分类 | 只读 `cache_1430_snaps.json`。不重新 classify |
| 宽度 | `holdings_ro2_extended.csv` 列 `b`。`risk_on = b is not None and b >= 0.45`。不用文件里现成的 `risk_on` 列 |
| 日历末日 | `risk_on` 强制 false |
| spike | `in_play` 且 `in_play_kind==spike_ft`；`box_pending` / `pending_second_week` 排除 |
| 填席宇宙 | 四本都是 `sharpe_key`，`sharpe_n=20`，`require_sharpe=True`，`max_pos=5`。先取短名单，再按本书的键重排 |
| 短名单 | `band_k = max(2*slots, slots+2)`。`slots=5` → 10；`slots=1` → 3。`slots≤0` 不新开 |
| 退出 | E0。原因仅 `breadth_off` / `falsify` / `always_in_flip` / `left_structure` / 末日 `eod_eval`。不因键变差增退出原因 |
| 成本 | `COST_SIDE=0.001` 且 `LIVE_COST_RT=0.002` |
| 杠杆 | `LCAP=1`。`L = min(1, 0.25 / max(σ20, σ60))` |
| 换手 | 再平衡双向权重变化的一半，再对再平衡次数平均 → `avg_turnover_1way` |
| 空仓周 | 去掉哨兵后、信号周五持仓为空的周数 |
| 周频 | T=348 |

变体不在这 4 个 id 里：退出码非 0，不写四件套。

## 键与取席

截止与 `sharpe_n_on` 对齐。不要用信号日当天收盘。回归实现调用 `band.py` 的 `ols_clenow`。下面的序列切片只是把 pandas 收盘序列收成 `ols_clenow` 的输入，语义要和 `band.clenow_on` 一致：信号日当天排除，末根距信号超过 5 个日历日则缺失，`t_i` 是这 n 根的顺序下标。

```python
def clenow_on_series(closes: pd.Series, d: str, n: int) -> dict | None:
    ts = pd.Timestamp(d)
    sub = closes.loc[: ts - pd.Timedelta(days=1)]
    if len(sub) < n:
        return None
    if (ts - pd.Timestamp(sub.index[-1])).days > 5:
        return None
    window = sub.iloc[-n:]
    if len(window) < n:
        return None
    return ols_clenow(window.to_numpy(dtype=float))  # from band.py


def pick(band, slots, mode):
    """band is sharpe-sorted. Delegate to band.pick. Never drop for a low or missing key."""
    return band_pick(band, slots, mode)
```

`Cand.score` 是 `slope_ann * r2`。`Cand.slope_ann` 是 `exp(beta*252)-1`。`mode=clenow_sort` 只读 `score`。`mode=slope_ann_sort` 只读 `slope_ann`。不要加 `k` 参数。

调用形状：

```
slots = max_pos - len(positions)
band = take_band(cands, slots)   # cands already sharpe-sorted, positions already skipped
take, how = pick(band, slots, mode)
# slots>0 且带非空时 len(take) == min(slots, len(band))
# 短了就 n_short_fills += 1，且 impl_pass=false
```

`n_rerank`：当周纯 S20 头部 `slots` 个代码的集合为 A，实际 take 为 B，加 `|B \ A|`。回退周贡献 0。F0 为 0。

`n_miss_clenow`：过了 spike、有信号价、在 `C_t`（不含已持仓）里、`clenow_on` 返回 None 的（周五, 代码）次数。按全书 `C_t` 计。F0 写 0。CS90S 与 CS90R 用同一个 N=90，计数必须相同。

`n_fallback_weeks`：`how == "fallback"` 的 `risk_on` 且 `slots>0` 的周数。`how == "empty"` 不计入。

`n_short_fills`：`slots>0`、带非空、且取席个数短于 `min(slots, |band|)` 的周数。生产路径在计数之后仍应取满；计数大于 0 则 `impl_pass=false`。不要用「删掉低分再让带外的 S20 补上」把这个计数伪装成 0。夹具锁的是「差键留在带尾并可以入选」。

`mean_score`：实际新开/换入上，该书排序键的均值。CS90R 的排序键是 `slope_ann`，所以它的 `mean_score` 等于 `mean_slope_ann`。空样本写 0。

`mean_slope_ann` / `mean_r2`：同上，只对有限值取均值。CS90R 的 R² 要算、要披露、不参与排序。

`jaccard_vs_f0`：入场集合 `{(date, code)}` 的 `|A∩B|/|A∪B|`。F0 为 1。任一方入场为空则写 0（F0 除外）。

`inert`：`id ≠ F0` 且每周 `(周五, frozenset(持仓代码))` 与 F0 相同。`n_empty_slots` 相等不是惰性。

`hit_rate` / `win_size`：新开那只券，从该信号周五收盘到下一信号周五收盘的简单收益。盈利为该收益 > 0。没有下一根信号周五的开仓不进样本。`mean_abs_D`：`risk_on` 且 `|D_t| ≥ 1` 的周，对 `|D_t|` 取均值。`D_t` 的成员资格看 SHARPE20，不看 Clenow。

## 夹具（先跑，不过就不写四件套）

`test_band.py` 已经锁住下面这些。执行分支改了 `band.py` 之后必须仍能通过。只锁公式和取席，不锁策略净值。

| 名 | 输入 | 应落在 |
|----|------|--------|
| 同带换序 | slots=1，S20 序 A>B>C>D。score 先为 0.2/0.4/0.9/5，再为 0.9/0.4/0.2/5 | 带永远是 A,B,C。第一次 take=C，第二次 take=A。D 两次都在带外 |
| slots=2 换序 | score 0.10/0.50/0.30 与 0.90/0.10/0.20，带相同 | take 从 B,C 变成 A,C |
| 带外进不来 | slots=1，D 的 score 最高 | `band_k=3`，take≠D |
| 缺失置底仍入选 | slots=1，带里只有 A，score 为 None | take=A，`how=fallback`，不空席 |
| 低分不丢 | slots=2，score 0.90 / 0.01 / None | take=A,B。0.01 留下 |
| 负分仍可入选 | score −0.50 / 0.10 / None，slots=2 | take=B,A。负分排在正分之后、缺失之前 |
| 同分回 S20 | A 与 B 的 score 相同，S20 序是 B 在前 | take 先取 B |
| 全缺失回退 | 带内 score 全 None，slots=2 | take=S20 前两名，`how=fallback` |
| F0 不看分 | mode=off，A 的 score 低于 B | take=A |
| 直线 | `P=exp(0.001·i)`，i=0…89 | R² clip 到 1，`slope_ann = score = exp(0.252)−1`。与 `(1.001)^252−1` 的差大于 1e-4 |
| 信号日收盘 | 同一条直线再加信号日价格 1e9 | 分数不变 |
| 全平 / 非正 / 89 根 / 末根距信号 7 日 | 见测试 | `None`，不是 0 |
| CS90R 换席 | 平滑 β=0.0008 对上隔日 ±0.05 的 β=0.0015，N=90 | score 选平滑，slope_ann 选噪声。同一条带 |
| CS60 换席 | 前 30 根日对数 −0.002、后 60 根 +0.002，对照全程 0.0008 | N=60 选前陡的那只，N=90 选平稳的那只 |
| 无 k / θ / accel | `pick` 的参数 | 没有这三项。年化常数是 252 |

不要把 0.50、0.40 或 `β>0` 写进 `pick`。不要做 accel。夹具里出现阈值参数即失败。

## 尺子

与 DESIGN 相同。

```
记正 = (Δret ≥ Δ|MDD|) 且 (2020-22 ret ≥ F0) 且 (2023-26 ret ≥ F0) 且 (非惰性)
F0.verdict = ANCHOR
惰性 → 证伪·惰性（算进「全部证伪」）
family_verdict = H1_HOLD    三本都是证伪或证伪·惰性，且 anchor_pass 且 impl_pass 且 attrib_pass
family_verdict = H1_REJECT  至少一本记正，且三门都过
family_verdict = BLOCKED    任一门不过
```

hit-rate / win-size / Jaccard / `n_rerank` 只进表和 ATTRIBUTION，不进 `verdict`。惰性除外。

## ATTRIBUTION

必须有 `## ATTRIBUTION`。缺一块则 `attrib_pass=false`。

1. **(a) 机制**：只在 S20 短名单内做了 Clenow 次级排序。列出未动的 B45 / spike_ft / max5 / E0 / TV25 / SHARPE20 宇宙 / Fri≥14:30 / 0.2%RT / AUM≥2。写明无替席、无硬闸、无 θ/N/k，第三本是 CS90R，四本是 `F0/CS90S/CS60S/CS90R`。
2. **(b) 席位**：三本相对 F0 的 Jaccard。
3. **(c) 分段**：两窗 Δret 与是否踏空。
4. **(d) 换手与空仓周**相对 F0，并报 `n_empty_slots`。
5. **(e) 名字·年份和大赢/大亏段**：
   - 每个非 F0 书、每个有 diff 的年，ADD 前 5 与 DROP 前 5（代码 + `n_events`）。
   - 每本一条 BIGWIN、一条 BIGLOSS：起止日、年份、`delta_cum_ex`、`uniq_book` 与 `uniq_f0`。
   - 周超额：`ex_t = r_book,t − r_F0,t`，`r` 为该书 NAV 比 − 1。`cum_ex` 是 `ex` 的累加，不是再复合。BIGWIN = `cum_ex[j]−cum_ex[i]` 最大的 `i<j`；BIGLOSS = 最负的一段。并列取更早的 `i`，再取更短的 `j−i`。
   - 真惰性：写「与 F0 席位逐周相同，无名字可列」。CSV 仍要有 BIGWIN/BIGLOSS 行，`uniq_*` 空、`delta_cum_ex=0`。

结尾写「ATTRIBUTION 不进 verdict。」

`attrib_pass` 为 true 当且仅当：REPORT 有 `## ATTRIBUTION`；(a)–(e) 都在；两个支持 CSV 可读；CS90S / CS60S / CS90R 在分段 CSV 里各有 BIGWIN 与 BIGLOSS，且每行有 `start` / `end`；(e) 对每本要么点了一个 6 位代码，要么写了惰性句。

## 锚点或实现对不上

锚不过：四件套仍写完；`anchor_pass=false`；`family_verdict=BLOCKED`；REPORT 写明 F0 实际 ret / maxDD / Calmar，以及它更接近 131.6/0.70、158.3/0.94、134.0/0.70、135.0/0.74，还是 131.9/0.70。停止。不去调成本、不去换宽度。

`n_short_fills > 0`：同样写完四件套，`impl_pass=false`，家族 BLOCKED。不要把少填的席解释成机制结论。

针或 `CLOUD-BATCH-2026-10-26` 缺失：不写 `out/`，退出码非 0，stderr 写明缺的路径 / SHA。

## 实现时不要做的事

- 不要跑第 5 本书，不要跑 CS90K2，不要跑 accel tie-break，不要跑 R² 或斜率的阈值。
- 不要把 `band_k` 改成 `slots`，也不要改成 `|C_t|`。
- 不要重开 SR90 / SR60 / SR90K2 / R290S / ER20S / COMBOS / RF50 / ER20 / AND50 / AG40 / AG20。
- 不要把 AG40S 的 235.6% 放进 Δ 表或当成记正标准。旁注可以引用。
- 不要重开 RET8/12、MOM121、Z121、R4W、residual-mom、corr-dedup、SORTINO20、SHARPE12/40、SOFT、skip-month、MA200。
- 不要用 0.9× 或 −2pp。
- 不要改 `strategy_exec`、`LIVE_OPS`、`champion_mast`、实盘、固收+、红利袖。
- 不要在看到结果之后改 `DESIGN.md` 的键、第三本、尺子和锚。
- 不要把 data cache 提交进 PR。
- 不要在 ATTRIBUTION 齐之前写 `H1_HOLD` / `H1_REJECT`。

## 拍板问句（REPORT 首行，原样）

请拍板：在面层 B45 + spike_ft max5 + E0 + TV25、LIVE≥14:30 面上，**填席宇宙仍是 SHARPE20 短名单**，只在短名单内按 Clenow score 次级排序取席。主口径冻结为 **N=90、`score = (e^{β·252} − 1) × R²` 降序（CS90S）**。邻档只留 **同公式 N=60（CS60S）** 与 **只按年化斜率 `(e^{β·252} − 1)`、不乘 R²（CS90R）**。四本锁定为 `F0/CS90S/CS60S/CS90R`。不替 S20，不设硬闸，不扫 θ/N/k。已持仓不因排序键变差而平。无论记正与否都不换冠。
