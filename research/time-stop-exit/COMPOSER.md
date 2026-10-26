# Composer 交接 · time-stop-exit

一次做完：按 `DESIGN.md` 实现主簿与两本邻档，重放 F0 对照，写出本文件第 6 节四件套。做完用 `DESIGN.md` 第 6 节两闸写判词。不要改规则，不要加邻档，不要换冠，不要在本交接里发明数字。

本 PR 的设计分支只交 `DESIGN.md` 与本文件。执行方另开分支写 `run.py` 和四件套。**本文件被执行之前禁止发明净值。**

工作分支自包含。输入只读。缺缓存就 `BLOCKED`，不要补抓一套新宇宙，也不要改 `strategy_exec/` 来「借」脚本。

## 1. 角色与边界

- 只新增 `research/time-stop-exit/` 下的运行脚本和 `out/` 产物。
- 可读 `strategy-weekly/` 与已有 `research/cloud_batch/`。不可写这两处，不可写 `strategy_exec/`、`LIVE_OPS`、`champion_mast`、实盘池、固收+、红利袖。
- 本设计分支不要 `git checkout` 到别的分支。别的分支上的文件用 `git show <branch>:<path>` 拷到临时只读目录，或在单独 worktree 里读。
- 解释器：云端用 `python3`。本机 Windows 仓里若要跑，用 `D:\python\python.exe`。不要为了本卡去装新的数据客户端。

## 2. 库存先行（先于 fork，先于跑批）

时停不需要相关矩阵、不需要 ATR。缺的是 FACE 针和延窗 kit。按顺序找，写进 `summary.json.inventory`。找不到就停，不要新抓。

| 序 | 找什么 | 首选 | 分支回退（只读 `git show` / worktree） | 找不到 |
|----|--------|------|----------------------------------------|--------|
| A | 引擎针 `05f0f8a4` 的 `simulate` / `run_live_tv` / `stats_full` | `research/cloud_batch/SPIKE-S20-BTHETA-GRID-LIVE1430/run.py` | `git show 05f0f8a4f778fde886f3e7b2976646ff4b7d777b:research/cloud_batch/SPIKE-S20-BTHETA-GRID-LIVE1430/run.py` | `BLOCKED` |
| B | 延窗样本接到 2026-10-23 | `research/cloud_batch/SPIKE-S20-EXTEND-REBASE-LIVE1430/run.py` | `origin/cursor/spike-s20-extend-rebase-live1430-27f1` 同路径 | 退回 A，但终点仍须 ≥2026-10-23；对不齐锚则 `BLOCKED` |
| C | 数据 kit | `research/cloud_batch/CLOUD-BATCH-2026-10-26/` | `origin/cursor/s20-tv-grid-live1430-26c5` 同目录 | `BLOCKED` |
| D | FACE 净值锚 | `SPIKE-S20-EXTEND-REBASE-LIVE1430/nav_LIVE1430-B45-S20.csv` | 同上延窗分支 | 没有净值锚仍可重放，但 `anchor_pass` 必须按 DESIGN 第 1 节数字核 |

明确 **SKIP**（找到也不用）：

| 路径 | 为何 SKIP |
|------|-----------|
| `research/exit-atr-chandelier/` | 吊灯已证伪。不要复用其 `chandelier_trigger`，不要叠 |
| `research/cloud_batch/SPIKE-MAXHOLD-SWEEP-LIVE1430/` 的 **metrics / REPORT 数字** | TV 网格 158.3% 面。可只读其 `weeks >= N` 计数实现，**禁止**把 143.3 / 160.1 / 137.5 抄进本刀主表或当预期 |
| `research/SPIKE-S20-EXIT-CROSS-MH6-RANKDROP-LIVE1430/` | MH×RD 已证伪。不要打开 rank-drop |
| `research/SPIKE-S20-EXIT-CROSS-PT15-COOL6-LIVE1430/` 与 PR#59 副本 | PT×COOL 已证伪 |
| `research/cloud_batch/SPIKE-PROFIT-TAKE-SWEEP-LIVE1430/` | PT 族已证伪，含邻档 20% |
| `strategy-weekly/_kit/face_engine.py` | 压缩突破 68.1% FACE，不是本刀的面 |

`inventory.skipped` 必须列出上面实际碰到的路径。没碰到就写空数组，不要假装读过。

`inventory.engine_source` 只允许 `btheta_05f0f8a4`、`extend_rebase_19834fa0`、`missing`。

## 3. 行情从哪来（禁止来门 / 中金 / Alpha 派）

价格、日历、14:30、宽度**只许**走下面这条链，找到即停。禁止调用 `comein-mcp-all`、`cicc-research`、Alpha 派 / `alphapai-research` / 任何 `apify-*` 行情 Actor。卖方研报 MCP 不是行情源。

| 优先级 | 源 | 用途 |
|---|---|---|
| 1 | 已有 CLOUD-BATCH `research_cache` | 日 OHLC、周线、`fri_1430_through_20261023.csv`、`holdings_ro2_extended.csv`、`listing.json`、`universe_replace_only_436.csv`、`cache_1430_snaps.json` |
| 2 | 本机 CJ-data / cjpy（`D:\python\python.exe`，token 在 `~/.cjpy/config.json`，不要回显） | 仅当缓存缺某只日 OHLC 时补洞；天软代码 `SZ`/`SH` |
| 3 | zsmcp `stock_quote` | 仅 cjpy 也没有的日行情洞 |
| 4 | `/pyas-data-discovery` | 仅 2、3 都没有的字段 |
| 5 | pytdx | **仅**补 14:30 分钟（kit 已有 `idx209` 路径）。K 线不复权，不能替代缓存的 qfq |

三条都找不到（池、日 OHLC、FACE 重放输入）则整单 `BLOCKED`，`REPORT.md` 只写缺什么。不要用 yfinance 去「先跑通再横比 FACE」。

| 用途 | 首选路径 | 回退 |
|------|----------|------|
| 研究池 | kit `universe_replace_only_436.csv`，`aum >= 2`，代码 zfill 6 | 同 kit 分支 |
| 14:30 | `fri_1430_through_20261023.csv`；`qfq_1430 = price_1430 × (日 qfq / sina)` | 同上 |
| 宽度 | `holdings_ro2_extended.csv` 列 `b`。`risk_on = b is not None and b >= 0.45`。不用该文件里现成的 `risk_on` 列 | 同上 |
| 分类缓存 | 只读 `cache_1430_snaps.json`。不重新 classify | 同上 |
| FACE 指标锚 | 延窗 `metrics.csv` 里 `LIVE1430-B45-S20` 行 | `origin/cursor/spike-s20-extend-rebase-live1430-27f1` |

`LIVE_PHASE = {"紧通道", "冲击"}`，从该提交的 `scripts/backtest.py` 导入。

`summary.json` 的 `source_sha` 写实际载入的提交。载入的针既不是延窗复核、也不是 `05f0f8a4`，就停。

## 4. 要写的脚本

只新增：

- `research/time-stop-exit/run.py`

脚本做四件事：

1. 先跑第 7 节夹具。不过：退出码非 0，四件套一个都不写。
2. 重放 F0（E0，无时停）。对不齐锚则四件套仍写，`family_verdict = BLOCKED`，时停簿可以不算。
3. 在 `simulate` 退出环里按 `DESIGN.md` 第 4.4 节插入时停，跑 `TS-MH8`、`TS-MH6`、`TS-MH12`（三本都是 K=0）。N、K、`weeks` 起点不要在脚本里另选默认值。
4. 写第 6 节产物，并在 `REPORT.md` 末段给出一句判词。

时停判定（主簿；邻档只换 N）：

```python
def time_stop_trigger(*, weeks: int, n: int) -> bool:
    """入场当周 weeks=0。满 N 次未退出 +1 之后，下一信号周五触发。"""
    return weeks >= n


def first_eligible_friday(t, fridays: list, k: int):
    """K=0 → t 当周可再入。四件套不调用 K>0。"""
    if k <= 0:
        return t
    after = [f for f in fridays if f > t]
    if len(after) < k:
        return None
    return after[k - 1]
```

闸点（对着 FACE `simulate` 的退出环，顺序写死）：

1. 末日 → `eod_eval`
2. `not risk_on` → `breadth_off`
3. `time_stop_trigger(weeks=p.weeks, n=N)` → `time_stop`（本族）
4. 否则 E0 原文（`falsify` / `always_in_flip` / `left_structure`）
5. 都没有：`p.weeks += 1`

入场：`weeks=0`。`build_cands(d, set(positions))` 必须在时停 `pop` **之后**调用，这样被清的名字同一周五可以重挣席（K=0）。不要把刚时停的代码塞进 `skip`。

F0 不调用 `time_stop_trigger`。F0 行的 `n_timestop` 必须为 0。否则实现把 overlay 漏进了对照，退出码非 0。

变体不在 F0 + 3 本时停里：退出码非 0，不写四件套。不要跑 N=10、不要跑 K=2，除非另开旁注文件且不进 `table.csv` 的 4 行。

## 5. 冻结参数

| 名 | 值 |
|----|----|
| `EVAL_START` / `END_S` | `2020-01-03` / `2026-10-23` |
| 宇宙 | `universe_replace_only_436.csv`，`aum >= 2`，代码 zfill 6 |
| 信号价 | `fri_1430_through_20261023.csv`；`qfq_1430 = price_1430 × (日 qfq / sina)` |
| 分类 | 只读 `cache_1430_snaps.json`。不重新 classify |
| 宽度 | `holdings_ro2_extended.csv` 列 `b`。`risk_on = b is not None and b >= 0.45` |
| 日历末日 | `risk_on` 强制 false |
| spike | `in_play` 且 `in_play_kind==spike_ft`；`box_pending` / `pending_second_week` 排除 |
| 填席 | `sharpe_key`，`sharpe_n=20`，`require_sharpe=True`，`max_pos=5`。Sharpe 窗截至信号日前一交易日 |
| 退出 | E0 + 本族时停。原因仅 `breadth_off` / `time_stop` / `falsify` / `always_in_flip` / `left_structure` / 末日 `eod_eval` |
| 成本 | `COST_SIDE=0.001` 且 `LIVE_COST_RT=0.002`，两处都留 |
| 杠杆 | `LCAP=1`。`L = min(1, 0.25 / max(σ20, σ60))`，σ 来自该书自身过去非零日收益 × √252，样本短于 2 根时 L=1 |
| 换手 | 再平衡双向权重变化的一半，再对再平衡次数平均，写入 `avg_turnover_1way` |
| 周频 | T=348 个持有周 |

4 本书在同一次进程里跑完：只改 N（F0 关闭）。持仓存活、成本、E0、SHARPE20、周五 14:30 成交、TV 的 σ20/σ60 保持与针一致。TV 用**这本书自己**的过去日收益。

## 6. 产物（四件套）

全部写到 `research/time-stop-exit/out/`。不多也不少：

| 文件 | 内容 |
|------|------|
| `REPORT.md` | 首行贴 DESIGN 的拍板问句。接着原样贴 DESIGN 的 H1。然后锚点门、主表、Δ/闸表、时停诊断、一句判词、红线 |
| `summary.json` | 下面的字段 |
| `table.csv` | 4 行，列顺序固定 |
| `equity.csv` + `equity_curve.png` | 4 条净值。图用对数轴：F0 黑线、线宽 2.2；主簿实线；邻档灰细线 |

支持文件可以有 `holdings_*.csv`、`trades_*.csv`，不替代四件套。缓存不要提交。夹具不过：退出码非 0，四件套一个都不写。锚不过或库存失败：四件套仍要写（库存失败可只写 REPORT + summary），但 `family_verdict` 必须是 `BLOCKED`。

`summary.json` 形状（数字是形状，不要照抄成实测）：

```json
{
  "batch": "TIME-STOP-EXIT",
  "champion_swap": false,
  "crown": "NO",
  "source_sha": "05f0f8a4f778fde886f3e7b2976646ff4b7d777b",
  "sample": ["2020-01-03", "2026-10-23"],
  "anchor_pass": true,
  "anchor": {"ret": 1.316, "maxDD": -0.188, "Calmar": 0.70, "n_weeks": 349, "T": 348, "n_codes": 324},
  "face_id": "F0",
  "primary_n": 8,
  "primary_k": 0,
  "inventory": {
    "engine_source": "btheta_05f0f8a4",
    "kit_path": "",
    "skipped": []
  },
  "h1": "TS-MH8 vs F0: G1 Δret>=Δ|MDD| and G2 2023-26 not missed",
  "family_verdict": "H1_HOLD",
  "positive_ids": [],
  "books": ["F0", "TS-MH8", "TS-MH6", "TS-MH12"],
  "cells": []
}
```

`family_verdict` 只允许 `H1_HOLD`、`H1_REJECT`、`BLOCKED`。`anchor_pass=false` 或 `engine_source=missing` 时必须是 `BLOCKED`，`cells[].verdict` 全部 `BLOCKED`。上面的 `H1_HOLD` 与空的 `positive_ids` 不要照抄，以两闸为准。`positive_ids` 只装 **主档** 记正时的 `["TS-MH8"]`。邻档记正不进这个数组。

每个 cell：

```json
{
  "id": "TS-MH8",
  "book": "LIVE1430-TSMH-N8-K0-B45-TV25",
  "N": 8,
  "K": 0,
  "ret": 0.0,
  "maxDD": 0.0,
  "CAGR": 0.0,
  "Calmar": 0.0,
  "Sharpe": 0.0,
  "avgL": 0.0,
  "avg_turnover_1way": 0.0,
  "n_cash_weeks": 0,
  "n_timestop": 0,
  "n_timestop_same_fri_reenter": 0,
  "n_cool_block": 0,
  "n_e0": 0,
  "avg_hold_weeks": 0.0,
  "w2020_22": {"ret": 0.0, "maxDD": 0.0, "Calmar": 0.0},
  "w2023_26": {"ret": 0.0, "maxDD": 0.0, "Calmar": 0.0},
  "delta_ret": 0.0,
  "delta_abs_mdd": 0.0,
  "g1_covers": false,
  "g2_2023_26": false,
  "verdict": "证伪"
}
```

F0 的 `N` / `K` 写 `null`，`n_timestop` / `n_timestop_same_fri_reenter` / `n_cool_block` 为 0，`delta_*` 为 0，两闸为 true，`verdict` 为 `ANCHOR`。

`table.csv` 列：

`id,book,N,K,ret,maxDD,CAGR,Calmar,Sharpe,avgL,avg_turnover_1way,n_cash_weeks,n_timestop,n_timestop_same_fri_reenter,n_cool_block,n_e0,avg_hold_weeks,w2020_22_ret,w2020_22_maxDD,w2020_22_Calmar,w2023_26_ret,w2023_26_maxDD,w2023_26_Calmar,delta_ret,delta_abs_mdd,g1_covers,g2_2023_26,verdict`

CSV 里 F0 的 `N`/`K` 写 `off`。布尔写 `true` / `false`。

`equity.csv` 列：`date,book,nav`。`nav` 从 1 起，`cumprod(1+r)`。`book` 用上表书名。

日收益 `r` 为扣成本之后的策略收益。`stats_full` 原样调用，不要重写 CAGR。

| 列 | 定义 |
|----|------|
| ret | `(1+r).cumprod()` 的末端减 1 |
| maxDD | 该净值相对历史峰值的最小跌幅 |
| CAGR | `(1+ret) ** (365.25 / 日历天数) − 1` |
| Calmar | `CAGR / |maxDD|`，maxDD ≥ 0 时留空 |
| Sharpe | `mean(r) / std(r, ddof=1) × √252`，rf = 0 |
| avg_turnover_1way | 每个再平衡日 `Σ\|Δ(L·w)\| / 2` 的均值（一手） |
| 2020–22、2023–26 | 对子样本重复 ret、maxDD、Calmar |

## 7. 夹具（先跑）

| 名 | 输入 | 应落在 |
|----|------|--------|
| 入场周 | `weeks=0`，N=8 | `time_stop_trigger` 为 False |
| 差一周 | `weeks=7`，N=8 | False |
| 到期 | `weeks=8`，N=8 | True |
| K=0 再入 | `first_eligible_friday(t, fridays, 0) == t` | 当周可进 `take` |

任一夹具出界：退出码非 0，不写四件套。

## 8. 尺子与判词

与 DESIGN 第 6 节相同。不要在跑批脚本里另写 0.9×、−2pp，或「Calmar ≥ FACE」。

```
记正 = G1 (Δret ≥ Δ|MDD|) 且 G2 (2023-26 ret ≥ F0 且为正)
F0.verdict = ANCHOR
family_verdict = H1_HOLD    若主档 TS-MH8 证伪
family_verdict = H1_REJECT  若主档记正
邻档 verdict 照算，但不得写入 positive_ids，不得改 family_verdict
主簿 n_timestop == 0 → 证伪（没咬住），不是 BLOCKED
```

时停诊断列只进表，不进 `verdict`（`n_timestop==0` 这条除外，它本身就是证伪）。

判词句子用设计卡里的两句模板，数字换成当次实测。句末加「不换冠」。

锚不过时：

- 能跑的书数字照实
- `anchor_pass=false` → `family_verdict=BLOCKED`
- REPORT 写明 F0 实际 ret / maxDD / Calmar（若有），以及它更接近 131.6/0.70、158.3/0.94，还是压缩突破的 68.1/0.31
- 停止。不去调成本、不去换宽度、不去贴另一条引擎、不去新抓行情

FACE 重放的接受标准见 `DESIGN.md` 第 1 节：ret 131.6% ± 2.0pp，|MDD| 18.8% ± 1.0pp，日频 Sharpe 0.82 ± 0.03（用已发布净值时）。**落到 158.3% / −15.9% / 0.94 就是 TV 网格引擎，停。**

## 9. 实现时不要做的事

- 不要跑第 5 本书，不要跑 N∈{4,7,9,10,16}，不要跑 K∈{1,2,3,4} 笛卡尔。
- 不要重开 ATR 吊灯（PR#79）。不要叠 `chandelier_trigger`。
- 不要重开 PROFTAKE-20 / PT10/15/25（PR#35）。
- 不要重开 PT15×COOL6（PR#52 / #59）。
- 不要重开组合亏损冷静（PR#37）。不要把 K 做成「上周组合 ≤ −6% → 整本现金」。
- 不要重开 MH6×rank-drop（PR#53）。
- 不要把 PR#41 的 158.3% / 160.1% / 137.5% 抄进主表或当预期 Δ。
- 不要把 TV 网格的 158.3% 当成 F0 目标，也不要把压缩突破的 68.1% 当成 F0。
- 不要用 `strategy-weekly/_kit/face_engine.py`。
- 不要替换 E0，不要叠 HYST、B50、TV33、MaxDD 闸、波动目标、ER、相关去重、残差填席。
- 不要用 `0.9 ×` 或 `−2pp`。
- 不要改 `strategy_exec`、`LIVE_OPS`、`champion_mast`、固收+、红利袖。
- 不要在看到结果之后改 `DESIGN.md` 的 N、K、两闸或主簿名字。
- 不要把 data cache 提交进 PR。
- 不要为了本卡去装新的数据客户端，不要下达新抓数。
- 不要用来门、中金、Alpha 派补行情。

## 10. 拍板问句（REPORT 首行，原样）

请拍板：维持面层 B45 + spike_ft max5 + E0 + TV25 + SHARPE20，只叠一层单票时停：连续持有 ≥ N 周的名字在当周周五再平衡被强制清出，必须重新挣席。主档 N=8、冷静 K=0。无论记正与否都不换冠。
