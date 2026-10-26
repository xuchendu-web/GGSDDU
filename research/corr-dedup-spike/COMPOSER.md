# Composer 交接 · corr-dedup-spike

照此实现并跑完 4 本书。缺参数就停，不要补一套「合理默认」。不要再开网格，不要循环插值，不要跑回测主循环以外的「顺便扫一下」。

本 PR 的设计分支只交 `DESIGN.md` 与本文件。执行方另开分支写 `run.py` 和四件套。**本文件被执行之前禁止发明净值。**

## 0. 库存先行（先于 fork，先于跑批）

按顺序找。每一步写进 `summary.json.inventory`。找不到就停，不要新抓。

### 0.1 60 周相关输入

| 序 | 找什么 | 首选 | 分支回退（只读 `git show` / worktree） | 找到之后 |
|----|--------|------|----------------------------------------|----------|
| A | 预计算 60 周滚动收益 Pearson 矩阵（代码×代码×周五，窗=60 周，截止信号日前一周五） | 工作区 `etf-correlation/**`、`research/**/corr*60w*` | 全部分支扫描；2026-10-26 设计卡已扫过 **无此文件** | `inventory.corr_source = "precomputed"`，核对其窗长与截止规则。对不上 60 周或用的是价格水平 / 60 日 → **不要用**，落到 B |
| B | 日 qfq / sina 日线，足以在 FACE 周五上算周收益 | `research/cloud_batch/CLOUD-BATCH-2026-10-26/data/research_cache/day/` 与 `sina_daily/` | `origin/cursor/s20-tv-grid-live1430-26c5` 同路径；或 `origin/cursor/spike-s20-extend-rebase-live1430-27f1` | `inventory.corr_source = "computed_from_cache"`。用 DESIGN 公式现场算。这是复用缓存，**不是**新抓 |
| C | A、B 都没有 | — | — | `family_verdict=BLOCKED`，`inventory.corr_source = "missing"`。REPORT 只写缺什么。退出码非 0。**禁止** yfinance / AKShare / cjpy / 新浪 / 进门补抓 |

### 0.2 明确 SKIP 的相关产物（找到也不用）

| 路径 | 为何 SKIP |
|------|-----------|
| `research/research-kb/CORR-R3.md` 及同卡 `corr_lib.py` / `engine/corr_r3.py` | 60 **日**持仓 ρ̄，选品不变，引擎 XS/RA，不是 B45 FACE |
| `etf-correlation/data/research_pool_v2.csv` 当「相关矩阵」 | 只有 `family` / `l0` 标签。可用作 `avg_max_family` 诊断，**不可**替代 ρ |
| `charts/chart_corr_heatmap.png`（`cursor/fof-ppt-6f3b`） | 图，无矩阵定义 |

`inventory.skipped` 必须列出上面实际碰到的路径。没碰到就写空数组，不要假装读过。

### 0.3 FACE 针与池（与 Kaufman / btheta 同一套）

| 用途 | 首选 | 回退 |
|------|------|------|
| 引擎针 | `05f0f8a4f778fde886f3e7b2976646ff4b7d777b` 的 `research/cloud_batch/SPIKE-S20-BTHETA-GRID-LIVE1430/run.py` | `git show` 该提交；不要 `git checkout` 到 btheta 上改原文件 |
| 数据 kit | `research/cloud_batch/CLOUD-BATCH-2026-10-26/` | `origin/cursor/s20-tv-grid-live1430-26c5` 同目录 |
| 研究池 | kit `universe_replace_only_436.csv`，`aum >= 2`，代码 zfill 6 | 同上 |
| 宽度 | `holdings_ro2_extended.csv` 列 `b`。`risk_on = b is not None and b >= 0.45`。不用该文件里现成的 `risk_on` 列 | 同上 |
| 14:30 | `fri_1430_through_20261023.csv`；`qfq_1430 = price_1430 × (日 qfq / sina)` | 同上 |
| 分类缓存 | 只读 `cache_1430_snaps.json`。不重新 classify | 同上 |
| family 诊断 | `etf-correlation/data/research_pool_v2.csv`（`origin/cursor/universe-slice-ab-spike-b45-10d0`） | 没有则用研究池 CSV 的 `family`；再没有则 `avg_max_family` 写 null，**不** BLOCKED |

`LIVE_PHASE = {"紧通道", "冲击"}`，从该提交的 `scripts/backtest.py` 导入。

工作区若没有这些路径：用 `git show` / 只读 worktree 拷到临时目录。不要用 `strategy-weekly/_kit/face_engine.py`——那是压缩突破的 68.1% FACE，不是本刀的面。

`summary.json` 的 `source_sha` 写实际载入的提交；载入的不是 `05f0f8a4` 就停。

本机解释器 `D:\python\python.exe`。云端用 `python3`。

## 跑完之后的四件套

写到 `research/corr-dedup-spike/out/`，不多也不少：

| 文件 | 内容 |
|------|------|
| `REPORT.md` | 首行贴 DESIGN 的拍板问句。接着原样贴 DESIGN 的 H1 代码块。然后库存段、锚点门、主表、Δ/闸表、扎堆旁注、证伪段、红线 |
| `summary.json` | 下面的字段 |
| `table.csv` | 4 行，列顺序固定 |
| `equity.csv` + `equity_curve.png` | 4 条净值。图用对数轴，F0 黑线、线宽 2.2；三本去重灰色细线 |

支持文件可以有 `holdings_*.csv`、`skips_*.csv`，不替代四件套。脚本放在 `research/corr-dedup-spike/run.py`。夹具不过：退出码非 0，四件套一个都不写。锚不过或库存失败：四件套仍要写（库存失败可只写 REPORT + summary），但 `family_verdict` 必须是 `BLOCKED`。

`summary.json`：

```json
{
  "batch": "corr-dedup-spike",
  "champion_swap": false,
  "crown": "NO",
  "source_sha": "05f0f8a4f778fde886f3e7b2976646ff4b7d777b",
  "sample": ["2020-01-03", "2026-10-23"],
  "anchor_pass": true,
  "anchor": {"ret": 1.316, "maxDD": -0.188, "Calmar": 0.70, "n_weeks": 349, "T": 348, "n_codes": 324},
  "face_id": "F0",
  "lookback_weeks": 60,
  "min_overlap": 40,
  "primary_rho": 0.85,
  "inventory": {
    "corr_source": "computed_from_cache",
    "corr_matrix_path": null,
    "price_cache_path": "",
    "pool_label_path": "",
    "skipped": []
  },
  "h1": "DEDUP-R85 证伪",
  "family_verdict": "H1_HOLD",
  "positive_ids": [],
  "cells": []
}
```

`family_verdict` 只允许 `H1_HOLD`、`H1_REJECT`、`BLOCKED`。`anchor_pass=false` 或 `corr_source=missing` 时必须是 `BLOCKED`，`cells[].verdict` 全部 `BLOCKED`。上面的 JSON 是字段形状；`H1_HOLD` 与空的 `positive_ids` 不要照抄，以尺子为准。`positive_ids` 只装 **主档** 记正时的 `["DEDUP-R85"]`。邻档记正不进这个数组。

`inventory.corr_source` 只允许 `precomputed`、`computed_from_cache`、`missing`。

每个 cell：

```json
{
  "id": "DEDUP-R85",
  "book": "LIVE1430-DEDUP-R85-B45-TV25",
  "rho_star": 0.85,
  "ret": 0.0,
  "maxDD": 0.0,
  "CAGR": 0.0,
  "Calmar": 0.0,
  "avgL": 0.0,
  "avg_turnover_1way": 0.0,
  "n_cash_weeks": 0,
  "avg_selected": 0.0,
  "n_dedup_skip": 0,
  "n_corr_na": 0,
  "avg_max_pair_corr": 0.0,
  "avg_max_family": 0.0,
  "n_incumbent_over_rho": 0,
  "w2020_22": {"ret": 0.0, "maxDD": 0.0, "Calmar": 0.0},
  "w2023_26": {"ret": 0.0, "maxDD": 0.0, "Calmar": 0.0},
  "delta_ret": 0.0,
  "delta_abs_mdd": 0.0,
  "g1_covers": false,
  "g2_2023_26": false,
  "g3_2020_22": false,
  "verdict": "证伪"
}
```

F0 的 `rho_star` 写 `null`，`n_dedup_skip` / `n_corr_na` / `n_incumbent_over_rho` 为 0，`delta_*` 为 0，三闸为 true，`verdict` 为 `ANCHOR`。

`table.csv` 列：

`id,book,rho_star,ret,maxDD,CAGR,Calmar,w2020_22_ret,w2020_22_maxDD,w2020_22_Calmar,w2023_26_ret,w2023_26_maxDD,w2023_26_Calmar,avgL,avg_turnover_1way,n_cash_weeks,avg_selected,n_dedup_skip,n_corr_na,avg_max_pair_corr,avg_max_family,n_incumbent_over_rho,delta_ret,delta_abs_mdd,g1_covers,g2_2023_26,g3_2020_22,verdict`

CSV 里 F0 的 `rho_star` 写 `off`。布尔写 `true` / `false`。

`equity.csv` 列：`date,book,nav`。`nav` 是日净收益的 `cumprod`，起点 1。`book` 用上表书名。

## 引擎从哪 fork

只读针 `05f0f8a4f778fde886f3e7b2976646ff4b7d777b`。4 本书在同一次进程里跑完：只改 ρ*（F0 关闭）。持仓存活、成本、E0、SHARPE20、周五 14:30 成交、TV 的 σ20/σ60 保持与针一致。TV 用**这本书自己**的过去日收益。

## 冻结参数

| 名 | 值 |
|----|----|
| `EVAL_START` / `END_S` | `2020-01-03` / `2026-10-23` |
| 宇宙 | `universe_replace_only_436.csv`，`aum >= 2`，代码 zfill 6 |
| 信号价 | `fri_1430_through_20261023.csv`；`qfq_1430 = price_1430 × (日 qfq / sina)` |
| 分类 | 只读 `cache_1430_snaps.json`。不重新 classify |
| 宽度 | `holdings_ro2_extended.csv` 列 `b`。`risk_on = b is not None and b >= 0.45` |
| 日历末日 | `risk_on` 强制 false |
| spike | `in_play` 且 `in_play_kind==spike_ft`；`box_pending` / `pending_second_week` 排除 |
| 填席排序 | `sharpe_key`，`sharpe_n=20`，`require_sharpe=True`，`max_pos=5`。Sharpe 窗截至信号日前一交易日 |
| 去重 | 见下一节。挂在 `build_cands` / `take[:slots]` **之前**：先排序，再贪心，再取满 5 或取尽 |
| 退出 | E0。原因仅 `breadth_off` / `falsify` / `always_in_flip` / `left_structure` / 末日 `eod_eval`。**不加**相关出场 |
| 成本 | `COST_SIDE=0.001` 且 `LIVE_COST_RT=0.002`，两处都留 |
| 杠杆 | `LCAP=1`。`L = min(1, 0.25 / max(σ20, σ60))`，σ 来自该书自身过去非零日收益 × √252，样本短于 2 根时 L=1 |
| 换手 | 再平衡双向权重变化的一半，再对再平衡次数平均，写入 `avg_turnover_1way` |
| 空仓周 | 信号周五（去掉日历哨兵最后一根）持仓为空的周数 |
| 周频 | T=348 个持有周 |

变体不在这 4 个 id 里：退出码非 0，不写四件套。

## 相关与贪心实现

截止与 `sharpe_n_on` 对齐：相关窗不含信号日当天。

```python
def weekly_returns(closes: pd.Series, fridays: list[pd.Timestamp]) -> pd.Series:
    """closes: DatetimeIndex 日 qfq。fridays: FACE 日历周五（升序）。"""
    px = []
    for fri in fridays:
        sub = closes.loc[:fri]
        px.append(float(sub.iloc[-1]) if len(sub) else float("nan"))
    p = pd.Series(px, index=pd.DatetimeIndex(fridays), dtype=float)
    return p.pct_change()


def pearson_60w(r_i: pd.Series, r_j: pd.Series, t: pd.Timestamp,
                lookback: int = 60, min_overlap: int = 40) -> float | None:
    """t 为信号周五。窗 = t 之前已完成的 lookback 根周收益。"""
    prev = r_i.index[r_i.index < t]
    if len(prev) < 1:
        return None
    end = prev[-1]
    win_idx = r_i.index[r_i.index <= end][-lookback:]
    if len(win_idx) < lookback:
        return None
    a = r_i.reindex(win_idx)
    b = r_j.reindex(win_idx)
    pair = pd.concat([a, b], axis=1).dropna()
    if len(pair) < min_overlap:
        return None
    rho = float(pair.iloc[:, 0].corr(pair.iloc[:, 1], method="pearson"))
    if not np.isfinite(rho):
        return None
    return rho


def greedy_fill(incumbents: list[str], ranked: list[str], rho_of,
                rho_star: float, max_pos: int = 5) -> tuple[list[str], int, int]:
    """ranked 已按 SHARPE20 降序，且不含 incumbents。
    rho_of(i, j) -> float | None。"""
    selected = list(incumbents)
    n_skip = 0
    n_na = 0
    for c in ranked:
        if len(selected) >= max_pos:
            break
        blocked = False
        for s in selected:
            rho = rho_of(c, s)
            if rho is None:
                n_na += 1
                continue
            if rho > rho_star:
                blocked = True
                break
        if blocked:
            n_skip += 1
            continue
        selected.append(c)
    return selected, n_skip, n_na
```

闸点：

- `incumbents` = 当周存活且仍 `is_spike` 的已持仓。它们互相超阈 **不踢**，只计入 `n_incumbent_over_rho`（该周任意一对 `ρ > ρ*` 则计 1 周）。
- `ranked` = `build_cands` 出口里已过 `is_spike`、有 SHARPE20、不在 `incumbents` 的名字。
- F0 不调用 `pearson_60w` / `greedy_fill`，直接 `take[:slots]`。
- 不要用 `|rho|`。不要用 `family` 相等当作 `rho > ρ*`。
- 不要在 `|S|<5` 时从非 spike 池或已跳过名单里回填。

`n_dedup_skip`：按（周五, 代码）计，对象是「过了 spike + 有信号价 + 有 SHARPE20 + 不在 incumbents + 被 ρ* 挡住」。不要事后只计「若无去重会进 top5 的」。

`avg_max_pair_corr`：当周入选集合两两有限 Pearson 的 max，再对有定义的周平均。不要把 NA 当 0。

## 夹具（先跑）

| 名 | 输入 | 应落在 |
|----|------|--------|
| 同列 | 两列相同的 60 根有限周收益 | Pearson ∈ [0.999999, 1.000001]；`greedy_fill` 在 ρ*=0.85 下跳过第二名 |
| 正交 | 60 根，样本 Pearson 为 0 | Pearson ∈ [−1e-12, 1e-12]；三档 ρ* 都留下第二名 |
| 重叠不足 | 共同有限周 = 39 | `pearson_60w` 返回 `None`；`greedy_fill` 留下第二名，`n_na ≥ 1` |

任一夹具出界：退出码非 0，不写四件套。

## 尺子

与 DESIGN 相同。不要在跑批脚本里另写 0.9× 或 −2pp。

```
记正 = G1 (Δret ≥ Δ|MDD|) 且 G2 (2023-26 ret ≥ F0) 且 G3 (2020-22 ret ≥ F0)
F0.verdict = ANCHOR
family_verdict = H1_HOLD    若主档 DEDUP-R85 证伪
family_verdict = H1_REJECT  若主档记正
邻档 verdict 照算，但不得写入 positive_ids，不得改 family_verdict
```

扎堆诊断列只进表，不进 `verdict`。

## 锚点 / 库存不过时的写法

F0 先与 DESIGN 的锚比较。相关库存按第 0 节。不过：

- 能跑的书数字照实；库存失败则可以没有净值，但 `summary.json` 与 REPORT 必须说明缺哪一类缓存
- `anchor_pass=false` 和/或 `corr_source=missing` → `family_verdict=BLOCKED`
- REPORT 写明 F0 实际 ret / maxDD / Calmar（若有），以及它更接近 131.6/0.70、158.3/0.94，还是压缩突破的 68.1/0.31
- 停止。不去调成本、不去换宽度、不去贴另一条引擎、不去把 60 日 ρ̄ 拿来顶替、不去新抓行情

## 实现时不要做的事

- 不要跑第 5 本书，不要跑 ρ*∈{0.70,0.80,0.95}，不要跑 20/40/120 周回看，不要跑 Spearman。
- 不要把 TV 网格的 158.3% 当成 F0 目标，也不要把压缩突破的 68.1% 当成 F0。
- 不要用 `strategy-weekly/_kit/face_engine.py`。
- 不要重开 RP-IV60（PR#82 已证伪）。不要重开主题×宽基分账（PR#75 / PR#36）。不要重开 CORR-R3。
- 不要把去重做成袖子逆波动、family 硬顶、或持仓平均相关降总仓。
- 不要每周全量重建 5 席来「顺便」踢掉高相关老仓——那是另一刀出场。
- 不要打开 R 闸，不要叠 PT / COOL / HYST / ER / 压缩突破。
- 不要用 `0.9 ×` 或 `−2pp`。
- 不要改 `strategy_exec`、`LIVE_OPS`、`champion_mast`、固收+、红利袖。
- 不要在看到结果之后改 `DESIGN.md` 的 ρ*、60 周、40 周重叠、尺子和锚。
- 不要把 data cache 提交进 PR。
- 不要为了本卡去装新的数据客户端，不要下达新抓数。

## 拍板问句（REPORT 首行，原样）

请拍板：维持面层 B45 + spike_ft max5 + E0 + TV25 + SHARPE20，只在填席时对已入选名字做 60 周收益相关去重（主档 ρ*=0.85），无论记正与否都不换冠。
