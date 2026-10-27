# Composer 交接 · r2-er-secondary

照此实现并跑完 **4 本书**（F0 + 主簿 R290S + 邻档 ER20S + 邻档 COMBOS）。缺参数就停，不要补一套「合理默认」。不要再开网格，不要循环插值，不要跑回测主循环以外的「顺便扫一下」。

不要实现硬闸（R²≥0.50、ER≥0.40、accel>0）。不要把 R² / ER / combo 换成填席键。不要做 R290A（R² 近分用 accel 断）。不要读 510300 当 σ / L / 闸。不要 import `research/er-r2-floor/run.py` 的 `floor_pass`，不要 import `research/accel-gate/run.py`，不要 import `research/clenow-slope-r2-fill/run.py`。

公式以 `DESIGN.md` 为准，id / 窗长 / 锚 / 权重以 `SPEC.json` 为准。两处对不上就停，不要私下调和。

设计 PR 里的 `run.py` 是 stub，执行会直接退出。执行分支**替换**它。替换前不要写 `research/r2-er-secondary/out/`。

## 跑完之后的四件套

写到 `research/r2-er-secondary/out/`：

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

脚本放在 `research/r2-er-secondary/run.py`。夹具不过：退出码非 0，四件套一个都不写。锚不过、实现门不过、或 ATTRIBUTION 未齐：四件套仍要写，`family_verdict=BLOCKED`。

针路径或 `05f0f8a4` 载不出来：退出码非 0，四件套一个都不写。没有针就没有可引用的 F0。

`summary.json` 字段形状：

```json
{
  "batch": "r2-er-secondary",
  "knife_id": "R2-ER-SECONDARY",
  "champion_swap": false,
  "crown": "NO",
  "source_sha": "05f0f8a4f778fde886f3e7b2976646ff4b7d777b",
  "sample": ["2020-01-03", "2026-10-23"],
  "anchor_pass": true,
  "impl_pass": true,
  "attrib_pass": true,
  "anchor": {"ret": 1.316, "maxDD": -0.188, "Calmar": 0.70, "n_weeks": 349, "T": 348, "n_codes": 324},
  "face_id": "F0",
  "primary": "R290S",
  "third_book": "COMBOS",
  "mechanism": "S20 band secondary sort; R290S=R2(N=90); ER20S=ER(N=20); COMBOS=0.5*z(R2)+0.5*z(ER); no hard gate",
  "h1": "filled by the ruler",
  "family_verdict": "H1_HOLD",
  "positive_ids": [],
  "skipped_ids": ["R290A", "RF50", "ER20", "AND50", "AG40", "AG20", "SR90", "SR60", "SR90K2", "ER10-T30", "ER10-T40", "ER10-T50"],
  "side_note": {"AG40S": "235.6%/-14.8%/1.32 mechanism template only; not a cell; not the ruler RHS"},
  "cells": []
}
```

`family_verdict` 只允许 `H1_HOLD`、`H1_REJECT`、`BLOCKED`。上面的 `H1_HOLD` 与空的 `positive_ids` 是形状，不要照抄，以尺子为准。`positive_ids` 只装记正的排序书 id。AG40S 只放在 `side_note`。

`anchor_pass=false` 或 `impl_pass=false` 或 `attrib_pass=false` → `family_verdict=BLOCKED`。锚不过时 `cells[].verdict` 全部 `BLOCKED`。实现门不过时，偏离的那本以及家族句都是 `BLOCKED`（其余本可以仍按尺子写，但家族句不得是 H1_HOLD / H1_REJECT）。ATTRIBUTION 未齐时格子仍可写尺子结果，家族句必须 `BLOCKED`。

每个 cell：

```json
{
  "id": "R290S",
  "book": "LIVE1430-B45-S20-R290S-max5",
  "mode": "r2_sort",
  "r2_n": 90,
  "er_n": 0,
  "ret": 0.0,
  "maxDD": 0.0,
  "CAGR": 0.0,
  "Calmar": 0.0,
  "avgL": 0.0,
  "avg_turnover_1way": 0.0,
  "n_cash_weeks": 0,
  "n_entries": 0,
  "n_rerank": 0,
  "n_miss_r2": 0,
  "n_miss_er": 0,
  "n_empty_slots": 0,
  "n_short_fills": 0,
  "n_fallback_weeks": 0,
  "mean_r2": 0.0,
  "mean_er": 0.0,
  "mean_combo": 0.0,
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

| id | book | mode | r2_n | er_n |
|----|------|------|------|------|
| F0 | `LIVE1430-B45-S20-max5` | `off` | 0 | 0 |
| R290S | `LIVE1430-B45-S20-R290S-max5` | `r2_sort` | 90 | 0 |
| ER20S | `LIVE1430-B45-S20-ER20S-max5` | `er_sort` | 0 | 20 |
| COMBOS | `LIVE1430-B45-S20-COMBOS-max5` | `combo_sort` | 90 | 20 |

F0：`n_rerank` / `n_miss_r2` / `n_miss_er` / `n_short_fills` / `n_fallback_weeks` / `mean_r2` / `mean_er` / `mean_combo` 为 0，`jaccard_vs_f0` 为 1，`inert` 为 false，`delta_*` 为 0，`covers` 与两窗为 true，`verdict` 为 `ANCHOR`。

R290S 的 `n_miss_er` / `mean_er` / `mean_combo` 为 0。ER20S 的 `n_miss_r2` / `mean_r2` / `mean_combo` 为 0。三本排序书的 `n_short_fills` 都为 0，否则 `impl_pass=false`。

`verdict` 只允许 `ANCHOR`、`记正`、`证伪`、`证伪·惰性`、`BLOCKED`。

`table.csv` 列，顺序固定：

`id,book,mode,r2_n,er_n,ret,maxDD,CAGR,Calmar,w2020_22_ret,w2020_22_maxDD,w2020_22_Calmar,w2023_26_ret,w2023_26_maxDD,w2023_26_Calmar,avgL,avg_turnover_1way,n_cash_weeks,n_entries,n_rerank,n_miss_r2,n_miss_er,n_empty_slots,n_short_fills,n_fallback_weeks,mean_r2,mean_er,mean_combo,mean_abs_D,hit_rate,win_size,jaccard_vs_f0,inert,delta_ret,delta_abs_mdd,covers,window_2020_22,window_2023_26,verdict`

四行顺序：`F0,R290S,ER20S,COMBOS`。布尔写 `true` / `false`。JSON 与 CSV 用小数，不用百分数。REPORT 主表用一位百分数、Calmar 两位；Δ 表用 pp（小数 ×100，标 pp）。

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
| 短名单 | `band_k = max(2*slots, slots+2)`。`slots=5` → 10；`slots=1` → 3 |
| 退出 | E0。原因仅 `breadth_off` / `falsify` / `always_in_flip` / `left_structure` / 末日 `eod_eval`。不因键变差增退出原因 |
| 成本 | `COST_SIDE=0.001` 且 `LIVE_COST_RT=0.002` |
| 杠杆 | `LCAP=1`。`L = min(1, 0.25 / max(σ20, σ60))` |
| 换手 | 再平衡双向权重变化的一半，再对再平衡次数平均 → `avg_turnover_1way` |
| 空仓周 | 去掉哨兵后、信号周五持仓为空的周数 |
| 周频 | T=348 |

变体不在这 4 个 id 里：退出码非 0，不写四件套。

## 键与取席

截止与 `sharpe_n_on` 对齐。不要用信号日当天收盘。

```python
def ols_r2(px: np.ndarray) -> float | None:
    """OLS R^2 of ln(P) on trading-day index 0..n-1. Flat → None."""
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
    er = num / denom
    if not np.isfinite(er):
        return None
    return float(er)


def sort_tuple(value, s20_index: int, code: str):
    miss = 0 if value is not None else 1
    mag = -(value if value is not None else 0.0)
    return (miss, mag, s20_index, code)


def combo_on_band(r2s, ers):
    """Return list of combo or None per name. None return = fallback to S20 order.

    z sample = names with both legs finite. ddof=0. Weights 0.5/0.5.
    """
    idx = [i for i, (r, e) in enumerate(zip(r2s, ers)) if r is not None and e is not None]
    if len(idx) < 2:
        return None
    def _z(vals):
        n = len(vals)
        mu = sum(vals) / n
        var = sum((v - mu) ** 2 for v in vals) / n
        if not (var > 0):
            return [0.0] * n
        sd = var ** 0.5
        return [(v - mu) / sd for v in vals]
    zr = _z([r2s[i] for i in idx])
    ze = _z([ers[i] for i in idx])
    if all(z == 0.0 for z in zr) and all(z == 0.0 for z in ze):
        return None
    out = [None] * len(r2s)
    for k, i in enumerate(idx):
        out[i] = 0.5 * zr[k] + 0.5 * ze[k]
    return out


def pick(band, slots, mode):
    """band is sharpe-sorted. Always return (take, how). Never drop for a low or missing key."""
    if slots <= 0 or not band:
        return [], "fallback"
    band = list(band)
    n_take = min(slots, len(band))
    if mode == "off":
        return band[:n_take], "sorted"
    if mode == "r2_sort":
        if all(c.r2 is None for c in band):
            return band[:n_take], "fallback"
        order = sorted(range(len(band)), key=lambda i: sort_tuple(band[i].r2, i, band[i].code))
        return [band[i] for i in order[:n_take]], "sorted"
    if mode == "er_sort":
        if all(c.er is None for c in band):
            return band[:n_take], "fallback"
        order = sorted(range(len(band)), key=lambda i: sort_tuple(band[i].er, i, band[i].code))
        return [band[i] for i in order[:n_take]], "sorted"
    if mode == "combo_sort":
        scores = combo_on_band([c.r2 for c in band], [c.er for c in band])
        if scores is None or all(s is None for s in scores):
            return band[:n_take], "fallback"
        order = sorted(range(len(band)), key=lambda i: sort_tuple(scores[i], i, band[i].code))
        return [band[i] for i in order[:n_take]], "sorted"
    raise ValueError(mode)
```

调用形状：

```
slots = max_pos - len(positions)
band_k = max(2 * slots, slots + 2)
band = cands[:band_k]          # cands already sharpe-sorted, positions already skipped
take, how = pick(band, slots, mode)
# len(take) == min(slots, len(band))。短了就 n_short_fills += 1，且 impl_pass=false
```

`n_rerank`：当周纯 S20 头部 `slots` 个代码的集合为 A，实际 take 为 B，加 `|B \ A|`。回退周贡献 0。F0 为 0。

`n_miss_r2` / `n_miss_er`：过了 spike、有信号价、在 `C_t`（不含已持仓）里、对应函数返回 None 的（周五, 代码）次数。按全书 `C_t` 计，不按「刚好在带内」计。该书不计算的键写 0。

`n_fallback_weeks`：`how == "fallback"` 的 `risk_on` 且 `slots>0` 的周数。

`n_short_fills`：断言失败的周数。生产路径在计数之后仍应取满；计数大于 0 则 `impl_pass=false`。不要用「删掉低 R² 再让后面的 S20 补上」把这个计数伪装成 0——带外的名字不能补带内被删掉的席。夹具锁的是「差键留在带尾并可以入选」。

`mean_*`：只对实际新开/换入、且该键有限的名字取均值。空样本写 0。

`jaccard_vs_f0`：入场集合 `{(date, code)}` 的 `|A∩B|/|A∪B|`。F0 为 1。任一方入场为空则写 0（F0 除外）。

`inert`：`id ≠ F0` 且每周 `(周五, frozenset(持仓代码))` 与 F0 相同。`n_empty_slots` 相等**不是**惰性。

`hit_rate` / `win_size`：新开那只券，从该信号周五收盘到下一信号周五收盘的简单收益。盈利为该收益 > 0。没有下一根信号周五的开仓不进样本。

## 夹具（先跑，不过就不写四件套）

只锁公式和取席，不锁策略净值。合成序列即可。

| 名 | 输入 | 应落在 |
|----|------|--------|
| 直线 R² | `P=exp(0.01·i)`，i=0…89 | `ols_r2` 返回 1.0（原始值允许 1+1e-12 内，函数 clip 到 1） |
| 全平 R² | 90 根常数 10 | `None`（不是 0） |
| 非正价 | 窗内有 ≤0 | `None` |
| 根数不足 | N=90 只有 89 根 | `None` |
| 隔了超过 5 日 | 末根距信号 >5 日 | `None` |
| 单边 ER | N=4，收盘 10,11,12,13,14 | ER=1 |
| 折返 ER | N=4，收盘 10,12,11,13,12 | ER=1/3（绝对误差 <1e-12） |
| 全平 ER | 21 根常数 | `None` |
| R290S 换人 | slots=1，S20 序 A>B>C，R² 为 0.2 / 0.4 / 0.9 | `band_k=3`，take=C，`n_rerank` 计 1 |
| 缺失置底仍入选 | slots=1，带里只有 A，A 的 R² 为 None | take=A，不空席，`n_short_fills` 不增加 |
| 差键不丢 | slots=2，带 A,B,C 的 R² 为 0.9 / 0.01 / None | take 的前两名是 A,B。C 可以排第三，B 必须留下。take 个数=2 |
| 全缺失回退 | 带内 R² 全 None | take = S20 原序的前 slots，`how=fallback` |
| 带外进不来 | slots=1，S20 序 A>B>C>D，R² 为 D 最高 | `band_k=3`，D 不在带内，take ≠ D |
| 只重排 top slots 会被夹具拒绝 | slots=1 且实现把 band_k 写成 1 | 与「R290S 换人」矛盾，夹具失败 |
| COMBOS 选中间 | slots=1，S20 序 A>B>C。R²=0.95/0.20/0.70，ER=0.10/0.90/0.70。ddof=0 | combo ≈ A −0.151883989，B −0.177862767，C +0.329746756（绝对误差 <1e-9）。take=C。R290S 在同输入上 take=A，ER20S take=B |
| 缺腿不进 z | 上表再加 D：R²=None，ER=0.99，S20 最差 | D 的 combo 为 None，A/B/C 的 combo 与上一行相同（D 不拉动 z）。slots=1 仍 take=C |
| 单腿无离散 | 两人 R² 相同且有限，ER 不同，两腿都有限 | 该腿 z=0，排序与 ER 同向 |
| 不足两人 | 带内只有 1 人两腿都有限 | 整段回退 S20 |
| 已持仓不因键平 | 持有 A，A 的 R² 从 0.9 掉到 0.1，E0 未触发 | A 仍在仓。不出现新的退出原因 |
| 无阈值 | R²=0.01 且它是带内唯一有限值，另有一人缺失 | 有限值排第一。不得因为 0.01<0.50 丢掉 |

COMBOS 那一行的对照数（总体标准差）：

- R² μ=0.6166…，sd=0.31180478223116176，z=[1.0690449676496978, −1.3363062095621216, 0.2672612419124245]
- ER μ=0.5666…，sd=0.33993463423951903，z=[−1.372812945967288, 0.9805806756909201, 0.3922322702763679]

不要把 0.50 / 0.40 写进 `pick`。不要做 accel。夹具里出现 `accel` 或 `theta` 参数即失败。

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

1. **(a) 机制**：只在 S20 短名单内做了 R² / ER / combo 次级排序。列出未动的 B45 / spike_ft / max5 / E0 / TV25 / SHARPE20 宇宙 / Fri≥14:30 / 0.2%RT / AUM≥2。写明无硬闸、无替换 S20、无 θ、第三本是 COMBOS。
2. **(b) 席位**：三本相对 F0 的 Jaccard。
3. **(c) 分段**：两窗 Δret 与是否踏空。
4. **(d) 换手与空仓周**相对 F0，并报 `n_empty_slots`。
5. **(e) 名字·年份和大赢/大亏段**：
   - 每个非 F0 书、每个有 diff 的年，ADD 前 5 与 DROP 前 5（代码 + `n_events`）。
   - 每本一条 BIGWIN、一条 BIGLOSS：起止日、年份、`delta_cum_ex`、`uniq_book` 与 `uniq_f0`。
   - 周超额：`ex_t = r_book,t − r_F0,t`，`r` 为该书 NAV 比 − 1。`cum_ex` 是 `ex` 的累加，不是再复合。BIGWIN = `cum_ex[j]−cum_ex[i]` 最大的 `i<j`；BIGLOSS = 最负的一段。并列取更早的 `i`，再取更短的 `j−i`。
   - 真惰性：写「与 F0 席位逐周相同，无名字可列」。CSV 仍要有 BIGWIN/BIGLOSS 行，`uniq_*` 空、`delta_cum_ex=0`。

结尾写「ATTRIBUTION 不进 verdict。」

`attrib_pass` 为 true 当且仅当：REPORT 有 `## ATTRIBUTION`；(a)–(e) 都在；两个支持 CSV 可读；R290S / ER20S / COMBOS 在分段 CSV 里各有 BIGWIN 与 BIGLOSS，且每行有 `start` / `end`；(e) 对每本要么点了一个 6 位代码，要么写了惰性句。

## 锚点或实现对不上

锚不过：四件套仍写完；`anchor_pass=false`；`family_verdict=BLOCKED`；REPORT 写明 F0 实际 ret / maxDD / Calmar，以及它更接近 131.6/0.70、158.3/0.94、134.0/0.70、135.0/0.74，还是 131.9/0.70。停止。不去调成本、不去换宽度。

`n_short_fills > 0`：同样写完四件套，`impl_pass=false`，家族 BLOCKED。不要把少填的席解释成机制结论。

针或 `CLOUD-BATCH-2026-10-26` 缺失：不写 `out/`，退出码非 0，stderr 写明缺的路径 / SHA。

## 实现时不要做的事

- 不要跑第 5 本书，不要跑 R290A，不要跑 accel tie-break，不要跑 R² 或 ER 的阈值。
- 不要把 `band_k` 改成 `slots`，也不要改成 `|C_t|`。
- 不要重开 RF50 / ER20 / AND50 / ER10-T* / AG40 / AG20 / SR90 / SR60 / SR90K2。
- 不要把 AG40S 的 235.6% 放进 Δ 表或当成记正标准。旁注可以引用。
- 不要重开 RET8/12、MOM121、Z121、R4W、residual-mom、corr-dedup、SORTINO20、SHARPE12/40、SOFT、skip-month、MA200。
- 不要用 0.9× 或 −2pp。
- 不要改 `strategy_exec`、`LIVE_OPS`、`champion_mast`、实盘、固收+、红利袖。
- 不要在看到结果之后改 `DESIGN.md` 的键、第三本、尺子和锚。
- 不要把 data cache 提交进 PR。
- 不要在 ATTRIBUTION 齐之前写 `H1_HOLD` / `H1_REJECT`。

## 拍板问句（REPORT 首行，原样）

请拍板：在面层 B45 + spike_ft max5 + E0 + TV25、LIVE≥14:30 面上，**填席宇宙仍是 SHARPE20 短名单**，只在短名单内按路径质量次级排序取席。主口径冻结为 **OLS R²(N=90) 降序（R290S）**。邻档只留 **ER(N=20) 降序（ER20S）** 与短名单内 **0.5·z(R²)+0.5·z(ER)（COMBOS）**。不设硬闸、不替 S20、不扫 θ。已持仓不因排序键变差而平。无论记正与否都不换冠。
