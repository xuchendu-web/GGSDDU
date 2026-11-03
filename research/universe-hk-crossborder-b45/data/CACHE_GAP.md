# NAV 缓存缺口（zsmcp 权威源，不臆造）

回测门槛见 `run.py`：HK `codes_ok/total >= 85%` 且全池 `>= 70%`，单码 `>= 200` 个交易日（宽表 ffill 后）。`FETCH.md` 另设 `codes_ge_200 >= 220`。

## 本轮审阅（2026-11-03，official DESC page fill）

| 项 | 值 |
|---|---|
| PR#102 | https://github.com/xuchendu-web/GGSDDU/pull/102 引擎/PIT/`SecuCategory=8` 已齐，等 NAV |
| 本 follow-up | 分支 `cursor/universe-hk-nav-official-1000-dafe`（17 只全池码 DESC 次页） |
| 权威源 | `zsmcp.query` → `mf_fundnetvaluere.UnitNVRestored`（当场查询原文落盘，未编造） |
| InnerCode | `inner_cat8.json`（`secumain.SecuCategory=8`），勿用 `MAX(InnerCode)` |
| 字段 | `listings.json` 同时写 `listed_date` + `listed_by_code`；`run.py` 二者皆读 |
| 分页坑 | 升序第一页满 1000 大约只到 2023-12；H1 要 2023–26 必须再拉 DESC/`OFFSET 1000` |
| 本轮已合并 | `nav_long.csv` **151925** 行 / **183** 码（全为 zsmcp 原文；+12064 官方新行，0 冲突替换） |
| HK ≥200 | **42 / 42 = 100%**（门槛 85%） |
| 全池 ≥200 | **168 / 280 = 60.0%**（门槛 70% → 需 ≥196，还差 **28** 码） |
| 就绪 | **否**（`coverage_status.py` → `ready=false`） |

港股切片已齐。全池还差 28 只 ≥200 日码。宽基旁注：`510300`/`510500`/`159915`/`159919`/`159922` 已接到 2026-10-23。

本轮把 17 只已计入覆盖、但 ASC 第一页截在 2023-12 / 2024-03 的全池码补上官方 DESC 1000 日（`{code}_1000.tsv`，未改 `{code}_0.tsv`）：`510310` `159919` `513100` `510880` `510330` `510210` `159922` `159901` `159925` `513030` `512810` `510360` `512290` `159994` `159929` `512900` `510180`。合并后末日均为 `2026-10-23`。`510330` 仍缺 2021-01-01..2022-09-08（未编造）。

未写入 `nav_long.csv` 的全池码清单见 `_need_full.json`（按 `jobs_full_*.json` InnerCode）。**不要把对话里的查询结果手抄进 CSV。**

## 权威 SQL

```sql
SELECT '{secucode}' AS SecuCode, DATE(TradingDay) d, UnitNVRestored c
FROM mf_fundnetvaluere
WHERE InnerCode={inner}   -- 来自 inner_cat8.json
  AND TradingDay BETWEEN '2019-11-01' AND '2026-10-23'
ORDER BY TradingDay DESC
LIMIT 1000;
-- 或升序分页：ORDER BY TradingDay LIMIT 1000 OFFSET {0|1000}
```

空结果才回退 `qt_dailyquote.ClosePrice`（`SecuCategory=8`）。不要用进门/中金/Alpha派，不要抄 sibling close 缓存。

`fund_nav` 最多 500 日、`stock_quote` 最多 120 日，不够本刀窗口。

## 复现

```bash
cd research/universe-hk-crossborder-b45/data
# 1) 按 jobs_hk.json / jobs_full_0..3.json / _need_full.json 调 zsmcp.query，TSV 写入 mcp_pages/
# 2) 合并（不发明行）
python3 merge_nav_pages.py
python3 coverage_status.py
# 3) 回测（覆盖不足会以 exit 2 + incomplete_cache 退出）
cd ..
python3 run.py --cache data/nav_long.csv
```

覆盖仍不足时 `summary.json.verdict` 保持 `incomplete_cache`，勿填造 NAV。
