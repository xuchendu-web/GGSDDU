# COMPOSER 简报 · EXIT-ATR-CHANDELIER

一次做完：按 `DESIGN.md` 实现主簿与三本邻档，重放 FACE 对照，写出本文件第 6 节产物。做完用 `DESIGN.md` 第 6 节两闸写判词。不要改规则，不要加邻档，不要换冠，不要在本交接里发明数字。

工作分支自包含。输入只读。缺缓存就 `BLOCKED`，不要补抓一套新宇宙，也不要改 `strategy_exec/` 来「借」脚本。本设计 PR **不写** `run.py`、**不跑** 主循环；本文件给下一张执行卡用。

## 1. 角色与边界

- 只新增 `research/exit-atr-chandelier/` 下的运行脚本和 `out/` 产物。
- 可读 `strategy-weekly/` 与已有 `research/cloud_batch/`。不可写这两处，不可写 `strategy_exec/`、`LIVE_OPS`、`champion_mast`、实盘池、固收+、红利袖。
- 本设计分支不要 `git checkout` 到别的分支。别的分支上的文件用 `git show <branch>:<path>` 拷到临时只读目录，或在单独 worktree 里读。
- 解释器：云端用 `python3`。本机 Windows 仓里若要跑，用 `D:\python\python.exe`。不要为了本卡去装新的数据客户端。

## 2. 行情从哪来（禁止来门 / 中金 / Alpha 派）

价格、日历、14:30、宽度**只许**走下面这条链，找到即停。禁止调用 `comein-mcp-all`、`cicc-research`、Alpha 派 / `alphapai-research` / 任何 `apify-*` 行情 Actor。卖方研报 MCP 不是行情源。

| 优先级 | 源 | 用途 |
|---|---|---|
| 1 | 已有 CLOUD-BATCH `research_cache` | 日 OHLC、周线、`fri_1430_through_20261023.csv`、`holdings_ro2_extended.csv`、`listing.json`、`universe_replace_only_436.csv` |
| 2 | 本机 CJ-data / cjpy（`D:\python\python.exe`，token 在 `~/.cjpy/config.json`，不要回显） | 仅当缓存缺某只日 OHLC 时补洞；天软代码 `SZ`/`SH` |
| 3 | zsmcp `stock_quote` | 仅 cjpy 也没有的日行情洞；科创板走它自己的表，不要猜 |
| 4 | `/pyas-data-discovery` | 仅 2、3 都没有的字段 |
| 5 | pytdx | **仅**补 14:30 分钟（kit 已有 `idx209` 路径）。K 线不复权，不能替代 cjpy / 缓存的 qfq OHLC |

三条都找不到（池、日 OHLC、FACE 净值）则整单 `BLOCKED`，`REPORT.md` 只写缺什么。不要用 yfinance 去「先跑通再横比 FACE」——那会得到另一条绝对水平。

池与 FACE 锚的路径：

| 用途 | 首选路径 | 分支回退（只读拷出） |
|---|---|---|
| 研究池 | `research/cloud_batch/CLOUD-BATCH-2026-10-26/data/universe_replace_only_436.csv` | `origin/cursor/s20-tv-grid-live1430-26c5:research/cloud_batch/CLOUD-BATCH-2026-10-26/data/universe_replace_only_436.csv` |
| 日 OHLC | 同 kit `data/research_cache/day/<code>.json`（字段 `o/h/l/c`） | 同一分支 |
| 14:30 | `data/research_cache/fri_1430_through_20261023.csv` | 同一分支 |
| 宽度 | `data/research_cache/holdings_ro2_extended.csv`（列 `date,b,risk_on`） | 同一分支 |
| FACE 净值锚 | `SPIKE-S20-EXTEND-REBASE-LIVE1430/nav_LIVE1430-B45-S20.csv` | `origin/cursor/spike-s20-extend-rebase-live1430-27f1:research/cloud_batch/SPIKE-S20-EXTEND-REBASE-LIVE1430/nav_LIVE1430-B45-S20.csv` |
| FACE 持仓 | 同目录 `holdings_LIVE1430-B45-S20.csv` | 同上分支 |
| FACE 指标锚 | 同目录 `metrics.csv` 里 `LIVE1430-B45-S20` 行 | 同上分支 |
| 上市日 | kit `data/research_cache/listing.json` | 同一分支；缺失则用第一根价格日，并在报告里写明 |

`qfq_1430` 必须与 day json 的 qfq 收盘同一条链。禁止 sina 未复权高低 + qfq 收盘混算 ATR。

## 3. 复用的脚本（只读）

不要改这些文件。

| 文件 | 用什么 |
|---|---|
| `research/cloud_batch/SPIKE-S20-EXTEND-REBASE-LIVE1430/run.py` | `is_spike`、`sharpe_n_on`、`simulate`、`run_live_tv`、`stats_full`。窗到 2026-10-23 |
| 若延窗 `run.py` 不在工作区 | `05f0f8a4` 的 `SPIKE-S20-BTHETA-GRID-LIVE1430/run.py` 同名函数；样本终点仍须接到 ≥2026-10-23，对不齐锚则 `BLOCKED` |
| kit `scripts/backtest.py` / `build_scan.py` | 仅 FACE 重放需要的 `Bar`、`classify`、`LIVE_PHASE`。只用 kit 里这份 |

FACE 重放的接受标准见 `DESIGN.md` 第 1 节：ret 131.6% ± 2.0pp，|MDD| 18.8% ± 1.0pp，日频 Sharpe 0.82 ± 0.03（用已发布净值时）。**落到 158.3% / −15.9% / 0.94 就是 TV 网格引擎，停。**

成本与杠杆常量与引擎一致：`LIVE_COST_RT = 0.002`，`COST_SIDE = 0.001`，`SIGMA_STAR = 0.25`，`LCAP = 1.0`。

`summary.json` 的 `source_sha` 写实际载入的提交。载入的针既不是延窗复核、也不是 `05f0f8a4`，就停。

## 4. 要写的脚本

只新增：

- `research/exit-atr-chandelier/run.py`

脚本做四件事：

1. 重放 FACE（E0，无吊灯）。对不齐锚则四件套仍写，`family_verdict = BLOCKED`，吊灯簿可以不算。
2. 在 `simulate` 退出环里按 `DESIGN.md` 第 4.4 节插入吊灯，跑 `CH-ATR14×3`、`CH-ATR14×2.5`、`CH-ATR14×3.5`、`CH-ATR22×3`。N、k、Wilder 平滑、HH 定义不要在脚本里另选默认值。
3. 核对 `atr_skip_name_week_pct`。持仓名字-周跳过 > 5%：`BLOCKED`。
4. 写第 6 节产物，并在 `REPORT.md` 末段给出一句判词。

吊灯判定（主簿；邻档只换 N 或 k）：

```python
def wilder_atr(high, low, close, n: int) -> float | None:
    # TR_t = max(H-L, |H-C_prev|, |L-C_prev|)
    # 种子 = 前 n 根 TR 均值；其后 (atr*(n-1) + tr) / n
    # 不足 n 根已完成日或缺 OHLC → None
    ...

def chandelier_trigger(*, hh_done, px_1430, atr, k) -> bool:
    if atr is None or atr <= 0 or px_1430 is None:
        return False
    hh = max(hh_done, px_1430)
    return px_1430 < (hh - k * atr)
```

`hh_done` = 入场日（含）到信号周五上一交易日（含）的日高最大值。入场当周不对新开仓做吊灯。吊灯触发价 = `simulate` 的 `px_on`（FACE 路径上周五已被 `qfq_1430` 覆盖）；日收益与成本仍走 `run_live_tv`，不要另造成交价。函数参数名 `px_1430` 就是这格 `px_on`。

变体不在 FACE + 4 本吊灯里：退出码非 0，不写四件套。

## 5. 指标（主表每一行都要有）

日收益 `r` 为扣成本之后的策略收益。`stats_full` 原样调用，不要重写 CAGR。

| 列 | 定义 |
|---|---|
| ret | `(1+r).cumprod()` 的末端减 1 |
| maxDD | 该净值相对历史峰值的最小跌幅 |
| CAGR | `(1+ret) ** (365.25 / 日历天数) − 1` |
| Calmar | `CAGR / |maxDD|`，maxDD ≥ 0 时留空 |
| Sharpe | `mean(r) / std(r, ddof=1) × √252`，rf = 0 |
| avgTO | 每个再平衡日 `Σ\|Δ(L·w)\| / 2` 的均值（一手） |
| 2020–22、2023–26 | 对子样本重复 ret、maxDD、Calmar |
| avgL | `L > 0` 的日子上 L 的均值 |
| n_chandelier | `exit_reason == chandelier` 的次数 |
| n_e0 | `falsify` + `always_in_flip` + `left_structure` |
| atr_skip_name_week_pct | 持仓名字-周里 ATR 未就绪的比例 |

FACE 行的 `n_chandelier` 必须为 0。否则实现把 overlay 漏进了对照，退出码非 0。

## 6. 产物（四件套）

全部写到 `research/exit-atr-chandelier/out/`。

| 文件 | 内容 |
|---|---|
| `REPORT.md` | 四件套：准则原文、实现要点、主表、一句判词。首行贴 DESIGN 的拍板问句 |
| `summary.json` | 下面的字段 |
| `table.csv` | 一行一簿，列顺序固定 |
| `equity.csv` + `equity_curve.png` | 日净值。图用对数轴：FACE 黑线、线宽 2.2；主簿实线；邻档灰细线 |

支持文件可以有 `holdings_*.csv`、`trades_*.csv`、`chandelier_log.csv`，不替代四件套。缓存不要提交。

`table.csv` 列：

`id,book,N,k,ret,maxDD,CAGR,Calmar,Sharpe,avgTO,avgL,w2020_22_ret,w2020_22_maxDD,w2020_22_Calmar,w2023_26_ret,w2023_26_maxDD,w2023_26_Calmar,n_chandelier,n_e0,atr_skip_name_week_pct,delta_ret,delta_abs_mdd,covers,window_2023_26,verdict`

FACE 的 `N`/`k` 写 `off`，`delta_*` 为 0，`covers` 为 true，`window_2023_26` 为 true，`verdict` 为 `ANCHOR`。布尔写 `true` / `false`。

`equity.csv` 列：`date,book,nav`。`nav` 从 1 起，`cumprod(1+r)`。

`summary.json` 形状（数字是形状，不要照抄成实测）：

```json
{
  "batch": "EXIT-ATR-CHANDELIER",
  "champion_swap": false,
  "crown": "NO",
  "source_sha": "05f0f8a4f778fde886f3e7b2976646ff4b7d777b",
  "sample": ["2020-01-03", "2026-10-23"],
  "anchor_pass": true,
  "anchor": {"ret": 1.316, "maxDD": -0.188, "Calmar": 0.70, "n_weeks": 349, "T": 348, "n_codes": 324},
  "h1": "CH-ATR14x3 vs FACE: G1 Δret>=Δ|MDD| and G2 2023-26 not missed",
  "family_verdict": "证伪",
  "positive_ids": [],
  "books": ["FACE", "CH-ATR14x3", "CH-ATR14x2.5", "CH-ATR14x3.5", "CH-ATR22x3"]
}
```

`family_verdict` 只允许 `记正`、`证伪`、`BLOCKED`。`anchor_pass=false` 时必须是 `BLOCKED`，`positive_ids` 为空。`记正` 时 `positive_ids` 只能有 `CH-ATR14x3`；邻档不准写进去。上面的 `证伪` 是占位，以两闸为准，不要因为占位就改 DESIGN。

## 7. 判词怎么落

按 `DESIGN.md` 第 6 节，只评主簿 `CH-ATR14×3`：

- 两闸都过：`记正`。
- 任一闸失败：`证伪`，点名闸号。
- 锚对不齐、缓存缺失、ATR 跳过 > 5%、FACE 落到 158.3% 引擎：`BLOCKED`。

邻档两闸的过或不过写在主表下的旁注里。旁注不改变判词，不挑最好的 k 替换主簿。阈值过敏按 DESIGN 第 5 节写旁注。

判词句子用设计卡里的两句模板，数字换成当次实测。句末加「不换冠」。

## 8. 实现时不要做的事

- 不要跑第 6 本书，不要跑 k=2.7 / 3.2、N=18、周 ATR、滚动窗 HH、ATR%、组合净值吊灯。
- 不要重开 PT / COOL / MH / rank-drop，不要和它们交叉。
- 不要替换 E0，不要叠 HYST、B50、TV33、MaxDD 闸、波动目标。
- 不要把 TV 网格的 158.3% 当成锚，不要和 131.6% 拼表。
- 不要用来门、中金、Alpha 派补行情；不要用 yfinance 产物和 FACE 横比。
- 不要改 `strategy_exec`、`LIVE_OPS`、`champion_mast`、固收+、红利袖。
- 不要在看到结果之后改 `DESIGN.md` 的 N、k、两闸或主簿名字。
- 不要把产物拷进 `strategy-weekly/spike_mom_rank/`。

## 9. 拍板问句（REPORT 首行，原样）

请拍板：维持面层 B45 + spike_ft max5 + E0 + TV25 + SHARPE20，吊灯主簿无论记正或证伪都不换冠。
