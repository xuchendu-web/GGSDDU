# NAV 缓存缺口（zsmcp 权威源，不臆造）

回测门槛见 `run.py`：HK `codes_ok/total >= 85%` 且全池 `>= 70%`，单码 `>= 200` 个交易日（宽表 ffill 后）。`FETCH.md` 另设 `codes_ge_200 >= 220`。

## 本轮审阅（2026-11-02，agent bc-076f7e3d）

| 项 | 值 |
|---|---|
| PR#102 | https://github.com/xuchendu-web/GGSDDU/pull/102 仍为 `incomplete_cache` |
| 权威源 | `zsmcp.query` → `mf_fundnetvaluere.UnitNVRestored`（已当场跑通，数字未编造） |
| InnerCode | `inner_cat8.json`（`secumain.SecuCategory=8`），勿用 `MAX(InnerCode)` |
| 字段 | `listings.json` 同时写 `listed_date` + `listed_by_code`；`run.py` 二者皆读 |
| 分页坑 | `ingest_secu_page.py` 仅当本页 `<1000` 才 `done`（满 1000 必须 `OFFSET 1000`） |
| 本轮已合并 | `nav_long.csv` **9008** 行 / **16** 码（全为 zsmcp 原文） |
| HK ≥200 | **4 / 42 = 9.5%**（门槛 85% → 需 ≥36） |
| 全池 ≥200 | **13 / 280 = 4.6%**（门槛 70% → 需 ≥196） |
| 就绪 | **否**（`coverage_status.py` → `ready=false`） |

已落盘且 ≥200 日的 HK 码：`159202` `159303` `159519` `159557`。

其余 38 只 HK 码本轮**未写入** `nav_long.csv`（其中 `159920`/`510900`/`513050`/`513170`/`159688`/`520500`/`520570`/`520590`/`520920` 已用同一 SQL 当场查到完整/次页复权净值，但 1000 行 MCP 页未能在本工作区稳定落盘）。**不要把对话里的查询结果手抄进 CSV。**

## 权威 SQL

```sql
SELECT '{secucode}' AS SecuCode, DATE(TradingDay) d, UnitNVRestored c
FROM mf_fundnetvaluere
WHERE InnerCode={inner}   -- 来自 inner_cat8.json
  AND TradingDay BETWEEN '2019-11-01' AND '2026-10-23'
ORDER BY TradingDay
LIMIT 1000 OFFSET {0|1000};
```

空结果才回退 `qt_dailyquote.ClosePrice`（`SecuCategory=8`）。不要用进门/中金/Alpha派，不要抄 sibling close 缓存。

`fund_nav` 最多 500 日、`stock_quote` 最多 120 日，不够本刀窗口。

老牌 ETF（上市早于约 2022-10）第一页 1000 行大约只到 2023-12；**必须再拉 `OFFSET 1000`**，否则 2023–26 段会被 ffill 冻结、H1 失真。已验证：`159920` InnerCode `18667` 的 OFFSET 1000 从 `2023-12-11` 接到 `2026-10-23`。

## 复现

```bash
cd research/universe-hk-crossborder-b45/data
# 1) 按 jobs_hk.json / jobs_full_0..3.json 调 zsmcp.query，TSV 写入 mcp_pages/
# 2) 合并（不发明行）
python3 merge_nav_pages.py
python3 coverage_status.py
# 3) 回测（覆盖不足会以 exit 2 + incomplete_cache 退出）
cd ..
python3 run.py --cache data/nav_long.csv
```

覆盖仍不足时 `summary.json.verdict` 保持 `incomplete_cache`，勿填造 NAV。
