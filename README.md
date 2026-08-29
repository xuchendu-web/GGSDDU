# ETF 个性化行情看板

对齐 [EarlETF《用 AI 手搓一个 ETF 个性化行情看板，比 Wind 都好用》](https://mp.weixin.qq.com/s/9b3vkaUxLBRvtolcOFGePg)：自定义 N 日涨跌、实时 IOPV 溢价、BIAS、目标价。电脑 / 手机浏览器都能开。

**结论：AKShare 能做，但它不是数据库。** 用 `fund_etf_spot_em` + `fund_etf_hist_em` 取数，落到本地 SQLite（`data/etf_board.db`），看板读库。全市场几千只溢价要日更入库；十来只自选可以盘中直拉。

## 页面模块

| 模块 | 作用 | 数据 |
| --- | --- | --- |
| 顶部状态 | 沪深交易中 / 已收盘 + 时钟 | 上海时区交易时段 |
| 自选表 | 代码、名称、最新价、当日涨跌 | `fund_etf_spot_em` |
| IOPV / 溢价率 | 市价相对实时估值 | `IOPV实时估值`，溢价本地重算 |
| N 日涨跌 + 走势 | 默认 19 日含当日，可改窗口 | 日线 + 实时价覆盖当日 |
| BIAS / 目标价 | 默认 BIAS20，10% / 15% 目标价 | 复权收盘 MA |
| 成交额（亿） | 当日成交 | 快照 `成交额` / 1e8 |
| 侧栏 | 加减自选、改 N / BIAS / 复权、重拉 K 线 | `watchlist.json` |

红涨绿跌，暗底金边，收盘后停自动刷新（默认 15 秒）。

## 口径（上线前用行情软件勾稽）

- **N 日涨跌幅（含当日）** = 最新价 / `REF(收盘, N)` − 1，至少 N+1 根 K 线。默认 N=19。
- **BIAS_N** = 最新价 / MA_N − 1，MA 含当日复权收盘。默认 N=20。
- **目标价** = MA_N × (1 + 阈值)。BIAS 打到 10% / 15% 时的价格，方便提前挂单。
- **溢价率** = (最新价 − IOPV) / IOPV。不直接用接口「基金折价率」符号，另列核对。

原文提醒：大模型最容易把 IOPV 字段和交易日区间各错一天。本仓库把这两处写成单测。

## 启动

```bash
python3 -m pip install -r requirements.txt
python3 -m streamlit run app.py --server.port 8501 --server.address 0.0.0.0
```

打开 http://127.0.0.1:8501 。东财接口不通时自动落「离线演示」，侧栏可关「走 AKShare 实盘接口」。

```bash
python3 -m pytest -q
```

## 结构

```
app.py                 Streamlit 页面
etf_board/indicators.py  涨跌 / BIAS / 溢价
etf_board/akshare_src.py 东财快照 + 日线
etf_board/store.py       SQLite
watchlist.json           自选与口径
data/etf_board.db        本地库（不入库）
```
