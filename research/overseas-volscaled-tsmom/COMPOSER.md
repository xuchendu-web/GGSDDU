# COMPOSER 简报 · VS-TSMOM-SLEEVE

一次做完：先库存，再按 `DESIGN.md` 实现主簿、两本对照、四本邻档，用第 6 节四闸写判词。不要改规则，不要加邻档，不要换冠，不要读 FACE 净值进主表。

工作分支自包含。输入只读。缺缓存就按第 2 节 SKIP / BLOCKED，不要补抓一套新宇宙，也不要改 `strategy_exec/` 来「借」脚本。

本设计分支不要 `git checkout` 到别的分支。别的分支上的文件用 `git show <branch>:<path>` 拷到临时只读目录，或在单独 worktree 里读。

解释器：云端用 `python3`。本机 Windows 仓里若要跑，用 `D:\python\python.exe`。不要为了本卡去装 cjpy / 通联 / 进门客户端。

## 1. 角色与边界

- 只新增本目录下的运行脚本和 `VS-TSMOM-LIVE1430/` 产物。
- 可读 `research/cloud_batch/`、`research/dual_momentum_weekly/`、`research/RESEARCH-TSMOM-12M-LONGFLAT-WEEKLY/`、`etf-correlation/data/` 的只读拷贝。不可写这些目录，不可写 `strategy_exec/`、`LIVE_OPS`、冠军目录、实盘池、固收+、红利袖。
- 不要 import LIVE 引擎来「顺便」重放 B45。本卡对照是 U 与 H，不是 FACE。
- 不要实现 carry / 展期。PR#62 已 SKIP。

## 2. 库存（必须先跑，先写 `inventory.json`）

脚本 `research/overseas-volscaled-tsmom/inventory_data.py` 只做盘点，不写 NAV。退出码：整单 FAIL 为非 0，其余为 0（含袖级 SKIP）。

### 2.1 输入（按顺序找，找到即停）

池与价格：

| 用途 | 首选路径 | 分支回退（只读拷出） |
|---|---|---|
| 研究池 | `etf-correlation/data/research_pool_v2.csv` 或 `strategy-weekly/etf_replace_only_436/universe_replace_only_436.csv` | `origin/cursor/universe-commodity-bond-cash-live1430-1848:etf-correlation/data/research_pool_v2.csv` |
| 日价格（优先） | kit `data/research_cache/day/<code>.json` | 同上分支 `research/cloud_batch/CLOUD-BATCH-2026-10-26/data/research_cache/day/` |
| 日价格（OX 补洞） | — | `origin/cursor/research-tsmom-12m-longflat-weekly-7280:research/cloud_batch/prices_daily/<code>.json` 以及同分支 `.../week/<code>.json` |
| 周网格 | `dual_momentum_weekly/data/weekly_panel.parquet` 的日期索引 | `origin/cursor/dual-mom-weekly-b45-e41b:research/dual_momentum_weekly/data/weekly_panel.parquet` |
| 周网格回退 | kit `research_cache/calendar_extended.json` + week json | `origin/cursor/s20-tv-grid-live1430-26c5` 或 PR#56 同 kit |
| 上市日 | kit `data/research_cache/listing.json` | 同一 cloud-batch 分支；缺失则用该代码第一根可用价格日，并标记 `listing_proxy=first_bar` |
| 利率债 | kit `data/research_cache/day/511010.json`（若存在） | 其次 `.../bond_daily/511010.csv`（PR#56）；再次 PR#60 `prices_daily/511010.json`。511260 同理 |
| 债标签（仅名单） | — | `origin/cursor/universe-commodity-bond-cash-live1430-1848:research/SPIKE-S20-UNIVERSE-COMMODITY-BOND-CASH-LIVE1430/bond_cash_sleeve_labels.csv` |

不要用的路径：

- PR#60 `prices_daily/159941.json`（及黄金等）从 2024-02-26 截断——OX/CMD 已有更长 `day/` 时禁止用它替换。
- PR#46 报告所述 `extend_bond_backward` 漂移债。若文件头/元数据含 `backward` / `drift` / `extend_bond`，RATES = SKIP。
- `/cj-data`、`/pyas-data-discovery`：存在且能查出 511010/511260 从 ≤2019-01-03 起的官方日收盘，才可把 RATES 从 SKIP 改 OK。**不要**为了本卡去登录或新装客户端。不存在就记 `local_data_paths.exists=false`，与 PR#62 同一写法。

### 2.2 库存断言

对池：

- `aum≥2` 且 `l0==海外权益` 的 `code` 集合 == DESIGN 第 3.1 节十六只。
- `l0==商品` 且 `aum≥2` == {518880, 518600, 159980, 159985, 159981}。
- 研究池内不存在 511010 / 511260（预期：不存在；存在则 `BLOCKED`，因为袖定义被破坏）。

对每个 OX/CMD 代码写一行：`code, source_path, source_ref, first_date, last_date, n_bars, fields, listing_proxy`。

RATES 额外写：`honest_from`、`honest_to`、`pre2019_ok`（布尔）、`drift_flag`（布尔）。`pre2019_ok` 当且仅当诚实第一根日期 ≤ 2019-01-03 且最后一根 ≥ 评窗最后周五。最后一根只到 2026-10-16 这类缺口记 `covers_eval_end=false`，全样本 RATES 仍 SKIP。`drift_flag=true` 则强制 SKIP。

本环境已知只读事实（库存脚本须**重新测量**，相符则抄进 json，不相符以测量为准）：

- PR#56 `bond_daily`：511010/511260 各 640 行，2024-02-26 → 2026-10-16，列只有 `date,close`。
- PR#56 `day/` 缺 513850、513290、513730、520870、520580。
- PR#60 `week/` 有上述缺失 OX；`prices_daily` 亦有，但部分序列短。
- PR#62：`/cj-data` 等当时不存在。

### 2.3 SKIP / FAIL 落点

按 `DESIGN.md` 第 4 节。写：

```json
{
  "generated_at_utc": "<ISO>",
  "task": "VS-TSMOM-SLEEVE",
  "ox": {"status": "OK|FAIL", "n": 16, "codes": []},
  "cmd": {"status": "OK|FAIL|SKIP", "n": 5, "codes": []},
  "rates": {"status": "SKIP|OK|FAIL", "reason": "", "pre2019_ok": false, "covers_eval_end": false, "drift_flag": false},
  "n_declared": 2,
  "declared_sleeves": ["OX", "CMD"],
  "triple_sleeve_claim": "SKIP",
  "local_data_paths": [{"path": "/cj-data", "exists": false}],
  "verdict_if_stop": null
}
```

`n_declared` 只数 `status==OK` 的袖。`triple_sleeve_claim` 在 RATES≠OK 时必须是 `"SKIP"`。

OX 或 CMD `FAIL`，或第 4.1 节其它 FAIL：`verdict_if_stop="BLOCKED"`，写 `REPORT.md` 只含缺什么，**不**写主表数字，停。

RATES SKIP 不是停。继续两袖。不要用 2024 起的债子窗替换主簿。

## 3. 要写的脚本

只新增：

- `research/overseas-volscaled-tsmom/inventory_data.py`
- `research/overseas-volscaled-tsmom/run_vs_tsmom.py`

`run_vs_tsmom.py` 做四件事：

1. 读入已写好的 `inventory.json`。`n_declared` 与宣布袖必须与库存一致，否则退出非 0。
2. 按 DESIGN 第 3.3–3.4 节构造周资格集与三簿权重。公式写死，不在脚本里另选 `σ*`、回看或归一。
3. 跑邻档四本。ERC 的 `σ_s` 来自当次 `EW-BH` 袖收益，不是来自主簿。
4. 写第 6 节产物，并在 `REPORT.md` 末段给出一句判词。

`σ* = 0.12`、周回看 52 / 60、`COST_RT = 0.002`、`L_CAP = 1.0`、`EVAL_START = "2020-01-03"`、`EVAL_END = "2026-10-23"`。

袖映射：

```python
OX = {
    "159941", "513500", "159509", "513400", "159687", "513880",
    "513850", "159561", "513800", "513290", "513080", "159329",
    "159529", "513730", "520870", "520580",
}
CMD = {"518880", "518600", "159980", "159985", "159981"}
RATES = {"511010", "511260"}  # 仅当 inventory.rates.status == "OK"
OXHK_EXTRA = {"159920", "510900", "513550", "520560", "159109", "513170", "520770"}

def sleeve_of(code: str, declared: set[str]) -> str | None:
    if code in OX and "OX" in declared:
        return "OX"
    if code in CMD and "CMD" in declared:
        return "CMD"
    if code in RATES and "RATES" in declared:
        return "RATES"
    return None
```

`VS-TSMOM-OXHK` 把 `OXHK_EXTRA` 并进 OX 资格，其它簿不要并。`VS-TSMOM-OXONLY` 的 `declared={"OX"}`。

周收益：相邻研究周五收盘比。缺当日 bar 则取该周五或之前最近一根日收盘；再缺则该名当周不合格。不要用 14:30。

不要调用 `classify` / `is_spike` / `run_live_tv`。本卡不是 FACE 重放。可抄 `dual_momentum_weekly` 里纯面板对齐（日期网格、节前周四映射），不要抄它的 top-N 选品。

## 4. 指标（主表每一行都要有）

日收益 `r` 为扣成本之后的策略收益。若实现是周再平衡、周间权重不变，把周收益按日摊或用周历净值再前向填充到日——**三簿同一套**，并在 REPORT 写明。优先：周五再平衡，周内按当日名字收益用**冻结权重**记日盈亏（与其它研究周频刀一致）。

| 列 | 定义 |
|---|---|
| ret | `(1+r).cumprod()` 的末端减 1 |
| maxDD | 净值相对历史峰值的最小跌幅 |
| CAGR | `(1+ret) ** (365.25 / 日历天数) − 1` |
| Calmar | `CAGR / |maxDD|`，maxDD ≥ 0 时留空 |
| Sharpe | `mean(r) / std(r, ddof=1) × √252`，rf = 0 |
| vol | 周收益 `std(ddof=1) × √52`（G4 用这一列；日收益 std×√252 可旁注，不过闸） |
| avgTO | 每个再平衡日 `Σ\|Δw\| / 2` 的均值（一手） |
| annTO | `avgTO × 52` |
| 2020–22、2023–26 | 对子样本重复 ret、maxDD、Calmar |
| avg_gross_exposure | 信号周五 `Σ w_i` 的均值 |
| cash_week_pct | 现金权重 ≥ 0.999 的信号周五占比 |
| erc_fallback_weeks | 仅 `VS-TSMOM-ERC`；其余为 0 |

分段边界：2020-01-01…2022-12-31，以及 ≥2023-01-01。与延窗研究卡相同。

G1 的 Sharpe 用上表日频 Sharpe。G4 的 vol 用周频年化。不要混用后再比。

分袖表：把 `B_s=1`、只交易该袖资格集，三簿各算一行。分袖表不过闸，只解释主簿。

## 5. 产物

库存：

| 文件 | 内容 |
|---|---|
| `inventory.json` | 第 2.3 节 |
| `inventory_names.csv` | 每只代码的来源与首末日 |

回测（仅库存未 BLOCKED 时）全部写到 `research/overseas-volscaled-tsmom/VS-TSMOM-LIVE1430/`：

| 文件 | 内容 |
|---|---|
| `REPORT.md` | DESIGN 第 8 节四件套 |
| `metrics.csv` | 一行一簿。顺序：`VS-TSMOM-12`、`TSMOM-UNSCALED`、`EW-BH`、`VS-TSMOM-ERC`、`VS-BH-12`、`VS-TSMOM-OXONLY`、`VS-TSMOM-OXHK` |
| `table.csv` | 与主表同内容的可读副本 |
| `sleeve_metrics.csv` | `book,sleeve,ret,maxDD,Calmar,Sharpe,vol` |
| `nav_<book>.csv` | `date,nav` |
| `weights_<book>.csv` | 每个信号周五：`date,w_OX,w_CMD,w_RATES,gross,w_cash`。袖列为乘预算之后的袖内合计；RATES SKIP 时 `w_RATES` 全 0 |
| `holdings_<book>.csv` | 信号周五的名字与权重 |
| `eligibility.csv` | 每周每袖 `n_s`、进入资格的代码数 |
| `yearly.csv` | `book,year,ret,mdd,vol,sharpe,calmar` |
| `summary.json` | `n_declared`、库存旗、四闸布尔、判词、覆盖、`erc_fallback_weeks`。**不要**放 FACE ret/MDD |
| `equity_curve.png` | 三条线：主簿、U、H。不要画 FACE |

`summary.json` 的判词字段只允许 `记正`、`证伪`、`BLOCKED`。另设 `triple_sleeve_claim`: `SKIP` 或 `SCORED`。

覆盖段写进 REPORT 第 2 节：十六只核对、五只核对、RATES 首末日、`n_declared`、评窗 2020-01-03 → 2026-10-23、各袖有资格周占比、价格缺失名单、`price_source`。

附录（可选，不进判词）：若 RATES 诚实 bar 从 2024-02-26 起且未标漂移，可写 `appendix_rates_subwindow.md`，样本从该两只都进入资格的第一周到该序列最后诚实周五。主表不出现这本账。

## 6. 判词怎么落

按 `DESIGN.md` 第 6 节，只评主簿 `VS-TSMOM-12` 对当次 U / H（不要引入 FACE）：

- G1 缩放增量：Sharpe 与 Calmar 都不低于 `TSMOM-UNSCALED`。
- G2 趋势增量：Calmar 不低于 `EW-BH`，或相对 H 的 Δret 盖住 Δ|MDD|。
- G3 后段：2023–26 `ret_P ≥ min(ret_U, ret_H)`。
- G4 缩放绑定：周频年化 `vol_P < vol_U`。
- 四闸都过：`记正`。
- 任一闸失败：`证伪`，点名闸号。
- 库存 FAIL：`BLOCKED`。

邻档四闸的过或不过写在主表下旁注。旁注不改变判词。OXONLY 优于主簿只旁注。

判词用设计卡两句模板，数字换成当次实测。句末加「不换冠」。必须出现「未与 FACE 绝对值横比」。RATES SKIP 时加「三袖普遍性 SKIP」。

报告里的每个数字都要能在 `metrics.csv` 或 `summary.json` 里找到。对不齐就改报告，不要改对照定义，更不要去改 FACE 锚。

## 7. 复用与不要复用

可以只读拷贝：

| 来源 | 用什么 |
|---|---|
| `dual_momentum_weekly/dual_momentum/panel.py` | 周五网格、缺 bar 映射。不要 top-N |
| `RESEARCH-TSMOM-12M-LONGFLAT-WEEKLY/engine/tsmom_backtest.py` | 12M 符号、成本函数的写法。不要 max5，不要它的 B45 scorecard |
| PR#62 `scripts/inventory_data.py` | 本地路径存在性、json 形状 |

不要复用：

- `SPIKE-S20-EXTEND-REBASE-LIVE1430/run.py` 的 `simulate` / `run_live_tv`（FACE 栈）
- `risk-parity-sleeve` 的逆波动归一与 FACE 四闸
- `bond_daily` 的漂移外推函数（若在 PR#46 脚本里）

## 8. 做完即停

- 不要把产物拷进 `strategy-weekly/spike_mom_rank/`。
- 不要开 σ* 网格、不要扫 26/39 周、不要把港股科技并进主簿。
- 不要改冠军、实盘说明、固收+、红利袖。
- 不要为「三袖好看」去回填 2020–2023 的国债 ETF。
- 本 COMPOSER 被执行前，设计 PR 里不应出现 NAV / 四闸实测。设计 PR 只交 `DESIGN.md` 与本文件。
