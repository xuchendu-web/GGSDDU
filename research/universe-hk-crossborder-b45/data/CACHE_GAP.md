# NAV 缓存缺口（zsmcp 权威源，不臆造）

回测门槛见 `run.py`：HK `codes_ok/total >= 85%` 且全池 `>= 70%`，单码 `>= 200` 个交易日（宽表 ffill 后）。`FETCH.md` 另设 `codes_ge_200 >= 220`（可选加严，非本刀硬门槛）。

## 本轮（2026-11-03，agent bc-076f7e3d）

| 项 | 值 |
|---|---|
| PR#102 | https://github.com/xuchendu-web/GGSDDU/pull/102 引擎/PIT/`SecuCategory=8` 已齐 |
| 本 follow-up | https://github.com/xuchendu-web/GGSDDU/pull/118 分支 `cursor/universe-hk-nav-ready-4820` |
| 权威源 | `zsmcp.query` → `mf_fundnetvaluere.UnitNVRestored`（当场查询原文落盘，未编造） |
| InnerCode | `inner_cat8.json`（`secumain.SecuCategory=8`），勿用 `MAX(InnerCode)` |
| 分页坑 | 升序第一页满 1000 大约只到 2023-12；H1 要 2023–26 必须再拉 DESC/`OFFSET 1000` |
| 本轮已合并 | `nav_long.csv` **182775** 行 / **213** 码（全为 zsmcp 原文；回测 `nav_codes`=212 因宽表后个别短码不足 200） |
| HK ≥200 | **42 / 42 = 100%**（门槛 85%） |
| 全池 ≥200 | **199 / 280 = 71.07%**（门槛 70% → ≥196） |
| 就绪 | **是**（`coverage_status.py` → `ready=true`；`run.py` 已完整跑通） |
| H1 | **NOT_FALSIFIED**（切片 Calmar 更高但 2023–26 相对全池踏空）。研究记账，不升格、不换冠。 |

港股切片已齐。宽基旁注 `510300`/`510500`/`159915`/`159919`/`159922` 均已接到 2026-10-23。

未达 200 日的全池码（81 只，可选补齐，不影响本轮门槛）见 `_need_full.json`（按 `jobs_full_*.json` InnerCode）。**不要把对话里的查询结果手抄进 CSV。**

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
# 3) 回测
cd ..
python3 run.py --cache data/nav_long.csv
```
