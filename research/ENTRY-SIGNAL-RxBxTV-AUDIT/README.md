# ENTRY-SIGNAL · R × B × TV 交叉审计（设计稿）

请拍板：维持面层 B45 + spike_ft max5 + E0 + TV25 + SHARPE20，本交叉无论记正与否都不换冠。

设计日 2026-10-26。研究池。本目录是准则、证伪尺子、稀疏网格和执行交接，不含批跑结果。

## 面

| 项 | 冻结值 |
|----|--------|
| 书 | B45 + spike_ft max5 + E0 + TV25 + SHARPE20 填席 |
| 信号 / 成交 | 周五 ≥14:30 / 当日收盘 |
| 成本 / 杠杆 | 0.2% RT；L≤1 |
| 窗 | 2020-01-03 → 2026-10-23 |
| 口述标签 | 约 134% / Calmar 约 0.70 |
| 同引擎锚 | `LIVE1430-B45-S20-max5` = **131.6% / −18.8% / Calmar 0.70**（btheta 延窗） |

口述 134% 与引擎 131.6% 是同一面的两个标签。交叉的分母用**本次** F0。F0 必须先贴上 131.6% / 0.70，贴不上就停。

## 五件

| # | 文件 | 内容 |
|---|------|------|
| 1 | `CRITERION.md` | 相对面的唯一改动、机制、Calmar / \|MDD\| 方向 |
| 2 | `FALSIFY.md` + `ruler.py` | 记正 vs 证伪；Δret 盖 Δ\|MDD\|；2020–22 与 2023–26；禁止强势段跳过 |
| 3 | `GRID.md` + `cells.json` | 8 格（≤9）；已闭合单轴不重开、不插值 |
| 4 | `COMPOSER.md` | 冻结参数与四件套，执行方照此写代码 |
| 5 | 本页首行 | 拍板问句。预承诺不换冠 |

`check_grid.py` 锁网格，`ruler.py` 锁尺子。两者都不读行情。

## 审计顺序

执行方交四件套之后，按这个顺序看，不跳步：

1. diff 只落在 `research/ENTRY-SIGNAL-RxBxTV-AUDIT/`。不出现 `strategy_exec`、`LIVE_OPS`、`champion_mast`、固收+、红利袖。
2. `python3 check_grid.py` 与 `python3 ruler.py` 都退出 0。
3. `table.csv` 的 `id` 集合等于 `cells.json`，不多一格。
4. `summary.json` 的 `anchor_pass` 为 true 之后才读各格 verdict。F0 相对 btheta 锚 \|Δret\|≤0.5pp、\|ΔmaxDD\|≤0.2pp、\|ΔCalmar\|≤0.02。
5. 用 `ruler.verdict` 重算 X1–X7。手写「记正」与函数不一致则整包退回。
6. 四件套齐全：`out/REPORT.md`、`out/summary.json`、`out/table.csv`、`out/equity.csv` + `out/equity_curve.png`。
7. `champion_swap` 为 false。REPORT 首行是本页拍板问句，原样，不改成结论。

## 红线

研究池。不改实盘、不改冠军主钉、不把 HYST-M3 或 K2/K3 叠进这 8 格。
