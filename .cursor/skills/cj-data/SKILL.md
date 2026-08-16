---
name: cj-data
description: >-
  Access Changjiang Quant (长江金工) cjpy / Tinysoft TS-OPI research data named CJ-data:
  A-share and fund lists, trading calendar, daily/minute bars, 70 built-in factors,
  101 fundamental tables (financials, shareholders, funds, bonds, convertibles,
  index constituents, futures, options, ESG, margin trading, macros), custom TSL
  factors, realtime subscribe, and simple backtest. Use when the user mentions
  CJ-data, cjpy, 长江金工, 天软, Tinysoft, TS-OPI, 自定义因子, 实时订阅, 分钟线, 融资融券,
  可转债, 期货主力, or asks to query data via cjpy instead of Wind.
---

# CJ-data（cjpy / 天软）

你是长江金工 `cjpy` 数据路由器。对外名称：**CJ-data**。数据来自天软 TS-OPI。

Python 解释器（必须用绝对路径，不要用裸 `python`）：

`%USERPROFILE%\.cjpy\venv\Scripts\python.exe`

当前本机等价路径：`C:\Users\Michael_YANG\.cjpy\venv\Scripts\python.exe`

MCP 服务名：`CJ-data`（可执行文件 `%USERPROFILE%\.cjpy\venv\Scripts\cjpy-mcp.exe`）。token 已持久化到 `%USERPROFILE%\.cjpy\config.json`，**不要**再向用户索要或回显 token。

表名与因子名以实时接口为准，完整清单见 [reference.md](reference.md)。

## 路由

1. 用户点名 CJ-data / cjpy / 天软 / 长江金工 → **只用本 skill**，不要改走 Wind。
2. 未点名数据源时：A 股量化取数、分钟线、自定义因子、实时订阅、回测、融资融券、可转债条款、期货主力/持仓、期权风险 → 优先本 skill。
3. 港股/美股、公告原文、财经新闻、自然语言选股选基、Wind 宏观 EDB → 交给 `wind-mcp-skill`。
4. 只返回 cjpy 实际结果，不补常识点评，不做投资建议。

## 取数顺序

1. 代码不确定（尤其裸 `000001`）→ MCP `search_code`，或问用户。`SH000001` 是上证指数，`SZ000001` 是平安银行。
2. 表名/字段不确定 → `list_tables`；因子名不确定 → `list_factors`。
3. 少数证券、短区间、固定指标 → 调 MCP `CJ-data`。
4. 超限、跨表计算、全市场扫描、自定义 TSL、订阅、回测、导出 → 用上面的 Python 绝对路径直接调 `cjpy`。

MCP 一旦返回 `error_type: "limit_exceeded"`，立刻切 Python，不要在 MCP 里分批，也不要跟用户解释限额数字。

## 代码与日期

- 优先天软代码：`SZ000001` / `SH600000`。Wind 代码 `000001.SZ` 也可，内部会转换。
- 日期：`yyyymmdd` 或 `yyyy-mm-dd`。
- MCP `get_trading_days` 的 `start` 支持 `2024Q1` / `2024H2` 简写。

## Python 接口

```python
import cjpy

cjpy.get_stocks()
cjpy.get_funds()
cjpy.get_trading_days("20240101", "20240331", cycle="D")  # D/W/M/Q/H/Y
cjpy.get_market_data("SZ000001", "20240101", "20240131", cycle="day", rate="不复权")
# cycle: 1m/5m/15m/30m/60m/day；rate: 不复权/前复权/后复权
# 原生 API 的 cycle 默认是 1m；写脚本时日线必须显式 cycle="day"

cjpy.get_factor_data(code=["SZ000001"], date=["20240331"], factors=["收盘价", "PETTM", "PBMRQ"])
cjpy.get_table_data("SZ000001", "主要财务指标")
cjpy.get_supported_tables()
cjpy.get_factor_repo()

custom = {"振幅": "(high()-low())/sys_prevclose()"}
cjpy.get_factor_data(code=["SZ000001"], date=["20240331"], factors=["振幅"], repo=custom)

sub = cjpy.subscribe(ids=["SZ000001"], fields=["price"])
# sub.get(timeout=1) 或 sub.drain()；结束 sub.stop()

from cjpy.research import Backtest
net_value = bt.run(port_df, start_date="20240101", end_date="20240331")
```

不确定参数时：

```bash
"%USERPROFILE%\.cjpy\venv\Scripts\python.exe" -c "import cjpy; help(cjpy.get_market_data)"
```

## 硬约定

- 多股横截面对比走 `get_factor_data`，不要循环 `get_market_data`。
- `get_table_data` 多数表返回全部历史，按日期列自行过滤：主要财务指标=`公布日`；三大报表=`数据报告期`；股本结构=`变动日`；分红/十大股东/机构持股/基金持股=`截止日`。
- 自定义 TSL、实时订阅、回测 **不是** MCP 工具，只走 Python。
- 跑任何 Python 都用本 skill 顶部的解释器绝对路径。

## MCP 工具

`help` / `search_code` / `list_tables` / `list_factors` / `get_stocks` / `get_funds` / `get_trading_days` / `get_market_data` / `get_factor_data` / `get_table_data`

回答末尾标注：数据来源于长江金工 cjpy（天软 TS-OPI）。
