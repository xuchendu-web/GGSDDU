# COMPOSER 简报 · RP-SLEEVE-IV60

一次做完：按 `DESIGN.md` 实现主簿与四本邻档，重放 FACE 对照，写出第 6 节的产物。做完用第 4 节的四闸写判词。不要改规则，不要加邻档，不要换冠。

工作分支自包含。输入只读。缺缓存就 `BLOCKED`，不要补抓一套新宇宙，也不要改 `strategy_exec/` 来「借」脚本。

## 1. 角色与边界

- 只新增本目录下的运行脚本和 `RP-SLEEVE-IV60-LIVE1430/` 产物。
- 可读 `strategy-weekly/` 与已有 `research/cloud_batch/`。不可写这两处，不可写 `strategy_exec/`、`LIVE_OPS`、冠军目录、实盘池、固收+、红利袖。
- 本设计分支不要 `git checkout` 到别的分支。别的分支上的文件用 `git show <branch>:<path>` 拷到临时只读目录，或在单独 worktree 里读。
- 解释器：云端用 `python3`。本机 Windows 仓里若要跑，用 `D:\python\python.exe`。不要为了本卡去装新的数据客户端。

## 2. 输入（按顺序找，找到即停）

池与 FACE 锚：

| 用途 | 首选路径 | 分支回退（只读拷出） |
|---|---|---|
| 研究池 | `/workspace/strategy-weekly/etf_replace_only_436/universe_replace_only_436.csv` | `origin/cursor/s20-tv-grid-live1430-26c5:research/cloud_batch/CLOUD-BATCH-2026-10-26/data/universe_replace_only_436.csv` |
| FACE 净值锚 | `.../SPIKE-S20-EXTEND-REBASE-LIVE1430/nav_LIVE1430-B45-S20.csv` | `origin/cursor/spike-s20-extend-rebase-live1430-27f1:research/cloud_batch/SPIKE-S20-EXTEND-REBASE-LIVE1430/nav_LIVE1430-B45-S20.csv` |
| FACE 持仓 | 同目录 `holdings_LIVE1430-B45-S20.csv` | 同上分支 |
| FACE 指标锚 | 同目录 `metrics.csv` 里 `LIVE1430-B45-S20` 行 | 同上分支 |
| 日历 / breadth | `research_cache/holdings_ro2_extended.csv`（列 `date,b,risk_on`） | `origin/cursor/s20-tv-grid-live1430-26c5:research/cloud_batch/CLOUD-BATCH-2026-10-26/data/research_cache/holdings_ro2_extended.csv` |
| 日价格 | kit `data/research_cache/day/` 与 `sina_daily/`，辅以 `strategy-weekly` 里既有 day/tema 缓存 | 同一 cloud-batch 分支 |
| 上市日 | kit `data/research_cache/listing.json` | 同一分支；缺失则用第一根价格日，并在报告里写明 |

价格只做研究缓存里已有的后复权或既有 qfq 拼接。FACE 重放若走引擎，14:30 用 `fri_1430_through_20261023.csv`。主簿 `RP-*` 不读 14:30。

三条都找不到（池、价格、FACE 净值）则整单 `BLOCKED`，`REPORT.md` 只写缺什么。

## 3. 复用的脚本（只读，把需要的函数抄进新脚本或原样 import）

不要改这些文件。

| 文件 | 用什么 |
|---|---|
| `research/cloud_batch/CLOUD-BATCH-2026-10-26/scripts/backtest.py` | `Position`、`KEEP`、`LIVE_PHASE`、`MIN_BARS`、`snap_index`、`nearest_date`。仅 FACE 重放需要。只用 kit 里这份，不去 `strategy_exec/` 找同名模块 |
| 同 kit `scripts/build_scan.py` | `Bar`、`classify`。仅 FACE 重放需要。**不要**用 `classify_l0_family` 定袖 |
| `research/cloud_batch/SPIKE-S20-EXTEND-REBASE-LIVE1430/run.py` | `is_spike`、`sharpe_n_on`、`classify_modified`、`simulate`、`run_live_tv`、`stats_full`。这是窗到 2026-10-23 的那份 |
| 若延窗 `run.py` 不在工作区 | `CLOUD-BATCH-2026-10-26/engine/run_s20_live1430.py` 的同名函数，但样本终点必须接到 ≥2026-10-23 的研究缓存，否则 FACE 对不齐锚，直接 `BLOCKED` |

FACE 重放的接受标准见 `DESIGN.md` 第 1 节：ret 131.6% ± 2.0pp，|MDD| 18.8% ± 1.0pp，日频 Sharpe 0.82 ± 0.03（用已发布净值时），引擎一手换手落在 0.10–0.40。TV 网格报告里的 158.3% 不是这条锚。

成本与杠杆常量与引擎一致：`LIVE_COST_RT = 0.002`，`SIGMA_STAR = 0.25`，`LCAP = 1.0`。`run_live_tv` 里 `cost = to × 0.002 / 2`，`to = Σ|Δ(L·w)|`。

## 4. 要写的脚本

只新增：

- `research/risk-parity-sleeve/run_rp_sleeve.py`

脚本做四件事：

1. 读池，按 `DESIGN.md` 第 2.1 节写 `sleeve_map.csv`。断言可投 324、划分 `EQ 59 / SEC 260 / CMD 5`、商品代码集合等于 {518880, 518600, 159980, 159985, 159981}。失败则退出码非 0，并写 `BLOCKED`。
2. 重放或读入 FACE 日收益，算出与主簿相同定义的 Sharpe 与换手。
3. 跑 `RP-IV60`、`RP-IV20`、`RP-IV60-CAP40`、`RP-ERC60`、`RP-IV60-EQONLY`。权重公式、60/20 周回看、代表选取、ERC 岭与 500 步迭代、fallback，都按 `DESIGN.md` 第 2–3 节，不在脚本里另选默认值。
4. 写第 6 节产物，并在 `REPORT.md` 末段给出一句判词。

袖子映射用下面这个函数，与设计卡同一逻辑：

```python
EQ_FAMILIES = {
    "港股·宽基",
    "海外·美股核心",
    "海外·美股成长",
    "海外·日本",
    "海外·欧洲",
    "海外·其他",
}

def sleeve_of(l0: str, family: str) -> str:
    if l0 == "商品":
        return "CMD"
    if family.startswith("宽基") or family in EQ_FAMILIES:
        return "EQ"
    if l0 in {"中国权益", "港股中资离岸", "海外权益"}:
        return "SEC"
    raise ValueError(f"unmapped {l0} {family}")
```

## 5. 指标（主表每一行都要有）

日收益 `r` 为扣成本之后的策略收益。

| 列 | 定义 |
|---|---|
| ret | `(1+r).cumprod()` 的末端减 1 |
| maxDD | 该净值相对历史峰值的最小跌幅 |
| CAGR | `(1+ret) ** (365.25 / 日历天数) − 1` |
| Calmar | `CAGR / |maxDD|`，maxDD ≥ 0 时留空 |
| Sharpe | `mean(r) / std(r, ddof=1) × √252`，rf = 0。过闸用这一列 |
| avgTO | 每个再平衡日 `Σ\|Δ(L·w)\| / 2` 的均值（一手） |
| annTO | `avgTO × 52` |
| 2020–22、2023–26 | 对子样本重复 ret、maxDD、Calmar |
| avgL | `L > 0` 的日子上 L 的均值 |
| cash_week_pct | 现金权重 ≥ 0.999 的信号周五占比 |
| max_sleeve_avg_w | 三袖里，信号周五权重时间序列均值的最大者 |
| erc_fallback_weeks | 仅 `RP-ERC60`；其余簿为 0 |

分段边界：2020-01-01…2022-12-31，以及 ≥2023-01-01。与延窗 `metrics_row` 相同。

## 6. 产物

全部写到 `research/risk-parity-sleeve/RP-SLEEVE-IV60-LIVE1430/`。

| 文件 | 内容 |
|---|---|
| `REPORT.md` | 四件套：准则原文、实现要点、主表、一句判词 |
| `metrics.csv` | 一行一簿，列见第 5 节。簿顺序：FACE 重放、`RP-IV60`、`RP-IV20`、`RP-IV60-CAP40`、`RP-ERC60`、`RP-IV60-EQONLY` |
| `table.csv` | 与主表同内容的可读副本 |
| `nav_<book>.csv` | 日净值，列 `date,nav` |
| `weights_<book>.csv` | 每个信号周五：`date,w_EQ,w_SEC,w_CMD,L,w_cash`。前三列是乘 L 之前的袖子权重；`w_cash = 1 − L × (w_EQ + w_SEC + w_CMD)` |
| `holdings_<book>.csv` | 每个信号周五的名字与乘 L 之后的权重 |
| `sleeve_map.csv` | `code,name,l0,family,aum,sleeve`，仅可投 324 行 |
| `yearly.csv` | `book,year,ret,mdd,vol,sharpe,calmar` |
| `summary.json` | 锚偏差、四闸布尔、判词、各袖首个可投周五、`sleeve_missing_week_pct`、`erc_fallback_weeks`、覆盖（可投只数、日历周数、价格缺失只数） |
| `equity_curve.png` | 三条线：FACE、`RP-IV60`、`RP-ERC60` |

`summary.json` 的判词字段只允许 `记正`、`证伪`、`BLOCKED`。

覆盖段写进 `REPORT.md` 第 2 节，至少包括：可投 324、三袖只数、日历 2020-01-03 → 2026-10-23、商品代码核对、FACE 相对锚的 ret / maxDD / Sharpe 偏差、价格缺失只数。

## 7. 判词怎么落

按 `DESIGN.md` 第 4 节，只评主簿 `RP-IV60`：

- 四闸都过，且不触发「单袖平均权重 > 70% 而 CAP40 未过 G1 与 G3」：`记正`。
- 任一闸失败：`证伪`，点名闸号。
- 主簿四闸都过但单袖平均权重 > 70%，且 `RP-IV60-CAP40` 未同时过 G1 与 G3：`证伪`，句子里写「结果来自单袖低波」。
- 锚对不齐、商品名单不对、缓存缺失、FACE 换手不在 0.10–0.40：`BLOCKED`。

邻档四闸的过或不过写在主表下的旁注里。旁注不改变判词，不挑最好的回看替换主簿。

判词句子用设计卡里的两句模板，数字换成当次实测。句末加「不换冠」。

## 8. 做完即停

- 不要把产物拷进 `strategy-weekly/spike_mom_rank/`。
- 不要开第二张刀，不要扫 cap 30/50，不要扫 40 周波动。
- 不要改冠军、实盘说明、固收+、红利袖。
- 报告里的每个数字都要能在 `metrics.csv` 或 `summary.json` 里找到。对不齐就改报告，不要改锚。
