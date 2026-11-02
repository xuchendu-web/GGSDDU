# NAV 缓存缺口（zsmcp 权威源，不臆造）

回测门槛见 `run.py`：HK `codes_ok/total >= 85%` 且全池 `>= 70%`，单码 `>= 200` 个交易日（宽表 ffill 后）。`FETCH.md` 另设 `codes_ge_200 >= 220`。

## 本轮审阅（2026-11-02）

| 项 | 值 |
|---|---|
| PR#102 | https://github.com/xuchendu-web/GGSDDU/pull/102 `incomplete_cache` |
| 起点缓存 | `nav_long.csv` 1018 行 / **3** 码（159202=250 截断, 159303=568, 159557=200 截断） |
| 并集 | 293（HK 42 + 全池 280） |
| InnerCode | `inner_cat8.json`（`secumain.SecuCategory=8`），勿用 `MAX(InnerCode)` |
| 字段 | `listings.json` 同时写 `listed_date` + `listed_by_code`；`run.py` 二者皆读 |
| 分页坑 | `ingest_secu_page.py` 曾在 200 行标 done，已改为仅当本页 `<1000` 才 done |

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

## 复现

```bash
cd research/universe-hk-crossborder-b45/data
# 1) 按 jobs_hk.json / jobs_full_0..3.json 调 zsmcp.query，TSV 写入 mcp_pages/
# 2) 合并（不发明行）
python3 merge_nav_pages.py
# 3) 回测
cd ..
python3 run.py --cache data/nav_long.csv
```

覆盖仍不足时 `summary.json.verdict` 保持 `incomplete_cache`，勿填造 NAV。
