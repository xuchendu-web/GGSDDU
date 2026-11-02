# 新浪 / AKShare 分钟旁路（研究轨）

与腾讯分钟旁路对称的实盘实时对照工具。只做研究互校，**不当回测权威，不写 LIVE，不改 `strategy_exec`**。

审阅口径（2026-11-02，Michael / 经悟空）：新浪分钟与 AKShare `stock_zh_a_minute` 是实盘实时旁路；回测日线不当权威；无 AUM；东财 `*_em` 勿当主力（#21 未入库）。`money.finance` `scale=1` 可能 `null`。

## 两轨边界

| 轨 | 用途 | 本目录 |
|---|---|---|
| **研究 / 回测轨** | 日/周面板、B45 面、四件套 NAV | 不在这里。回测收盘**不能**当实时分钟权威 |
| **实盘实时旁路轨** | 盘中 1m/5m 互校、休市自判 | **本工具**：新浪 `getKLineData` + AKShare `stock_zh_a_minute` + 腾讯 `mkline` |

两轨数字不要横比后直接写进策略。旁路只回答「现在这两家实时分钟是否对齐」。

## 入口

| 源 | URL / 函数 | 1m | 5m | 角色 |
|---|---|---|---|---|
| **sina.cn** | `quotes.sina.cn` `CN_MarketDataService.getKLineData` `scale=1/5` | 可用 | 可用 | **主力旁路** |
| **AKShare** | `stock_zh_a_minute(symbol, period="1"|"5")` | 同源 sina.cn；若实现走 money.finance 则 1m 可能空 | 可用 | 旁路，未安装则 `akshare_compat` 回退 sina.cn |
| **money.finance** | `CN_MarketData.getKLineData` `scale=1` | **常为 null** | 可用 | 仅探测，不当主力 |
| **腾讯** | `ifzq.gtimg.cn` `kline/mkline` `m1`/`m5` | 可用 | 可用 | **互校**，成交量单位不同，只比收盘价 |
| 东财 `*_em` | `fund_etf_hist_min_em` 等 | — | — | **禁止当主力** |

成交量：新浪多为股，腾讯 ETF 常见为手。互校**只比 close**。

## 红黄判据

| flag | 条件 |
|---|---|
| **GREEN** | 两边有重叠分钟；`|新浪close − 腾讯close| / 腾讯close ≤ 0.3%`；OHLC 合法 |
| **YELLOW** | 重叠分钟上相对偏差 **> 0.3%**；或休市自判后腾讯缺数（不升红）。低价 ETF（如 0.33）一跳 0.001 即约 0.30%，`max%` 可能刚过线而最后一根仍对齐 |
| **RED** | 新浪失败/空表；**开盘时段**腾讯失败；无重叠分钟；OHLC 非法；开盘时段最后一根时间差 > 3 分钟 |

休市自判：时钟（周末 / 2026 节假日**提示表**）+ **多数标的最大行情日**。行情日优先。时钟像交易日但全样本最新 K 线早于今日 → `inferred_closed`，缺今日分钟**不标红**。

## 复现命令

仓库根目录。本机若按用户习惯，把 `python3` 换成 `D:\python\python.exe`。

```bash
# 单测（无网）
PYTHONPATH=research/sina-minute-bypass python3 -m unittest discover -s research/sina-minute-bypass/tests -q

# 动量池 20+ ETF，1m+5m，写 CSV+摘要
PYTHONPATH=research/sina-minute-bypass python3 research/sina-minute-bypass/scripts/pull_minutes.py \
  --scales 1,5 --datalen 240 --out research/sina-minute-bypass/out

# 只跑两只、跳过可选源
PYTHONPATH=research/sina-minute-bypass python3 research/sina-minute-bypass/scripts/pull_minutes.py \
  --codes 510300,159915 --scales 1 --skip-akshare --limit 2

# 腾讯旁路已落 CSV 时互校（列同构：code,scale,ts,open,high,low,close,volume,amount,source）
PYTHONPATH=research/sina-minute-bypass python3 research/sina-minute-bypass/scripts/pull_minutes.py \
  --tencent-csv path/to/tencent_bars.csv
```

产物：

- `out/bars/sina_cn.csv` / `tencent.csv` / `akshare.csv`
- `out/compare.csv`
- `out/summary.md` + `out/summary.json`

进程退出码：有 RED 为 `2`，无 RED 为 `0`（YELLOW 仍 0）。

可选：`pip install akshare` 后脚本走真 `stock_zh_a_minute`。未装则标记 `akshare_compat`，不装东财、不调 `*_em`。

## 样本

`universe.json` 28 只：宽基（300/50/500/创业板/科创50/1000/A500）、半导体/券商/医药/通信/有色/AI/酒/消费/银行/军工、黄金、QDII、现金袖 511010/511260。覆盖动量池常用面，**不是** LIVE 交易名单，**不含 AUM**。

QDII（如 159941）A 股开盘时最后一根可能仍停在上一美股交易日；两边对齐则 GREEN，不当作 A 股停牌。

## 2026-11-02 盘中试跑

上海 09:49，`session=open`，自判交易日 2026-11-02。28 只 × 1m/5m = 56 条对照：**GREEN 54 / YELLOW 2 / RED 0**。

- `money.finance`：510300/510050 的 1m 为 `null`，5m 有数。与审阅一致。
- 仅 512170 医疗 ETF 的 1m/5m `max%` 刚过 0.3%（0.302% / 0.305%），最后一根 0.331 vs 0.331。低价一跳噪声。
- 摘要与对照表见 `out/summary.md`、`out/compare.csv`。分钟明细 CSV 不入库（`out/bars/`）。

## 禁区

- 进门 / comein、中金 / cicc、Alpha派 / alphapai：本工具不调用。
- `strategy_exec/`、LIVE、实盘下单、换冠：不碰。
- 东财 `*_em` 不当主力；#21 未入库的东财分钟不在本目录复活。
- 回测 NAV / 研究面板收盘价不当实时权威。
- 不把旁路偏差写成持仓或 AUM 结论。

## 与腾讯旁路对称

| 项 | 约定 |
|---|---|
| 目录 | `research/sina-minute-bypass/` ↔ `research/tencent-minute-bypass/` |
| CSV 列 | `code,name,scale,ts,trade_date,open,high,low,close,volume,amount,source` |
| 黄线 | 收盘价相对偏差 0.3% |
| 日历 | 休市自判，不把东财日历当权威 |

本工具自带腾讯 `mkline` 客户端做互校；若腾讯旁路脚本先落了 CSV，用 `--tencent-csv` 对齐，避免重复打接口。
