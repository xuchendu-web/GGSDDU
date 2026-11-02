# NAV 缓存构建（zsmcp）

回测读取 `data/nav_long.csv`（列：`SecuCode,d,c`）。在 Cloud Agent 中需通过 **zsmcp `query`** 拉取后写入。

## 推荐：按 SecuCode 分页

```bash
cd research/universe-hk-crossborder-b45/data
python3 secu_fetch_runner.py next --group hk --limit 20   # 打印 JSON jobs
# 对每个 job.sql 调用 zsmcp query，将 TSV 正文：
python3 secu_fetch_runner.py store '<job_json>' < raw.tsv
python3 secu_fetch_status.py
```

目标：`codes_ge_200 >= 220`（见 `secu_fetch_lib.CODES_TARGET`）。

## 备选：文件队列

```bash
python3 build_nav_cache.py fetch-nav   # 阻塞等待 mcp_queue 响应
# 另一终端/Agent 循环：agent_mcp_dispatch.py → zsmcp → complete_mcp.py
```

数据源：`mf_fundnetvaluere.UnitNVRestored`（`InnerCode` 必须来自 `secumain.SecuCategory=8`，见 `inner_cat8.json`）。勿用 `MAX(InnerCode)`。空结果才回退 `qt_dailyquote.ClosePrice`。

分页：zsmcp `query` 上限 1000 行；本页满 1000 必须再拉 `OFFSET 1000`。`ingest_secu_page.py` 仅当本页 `<1000` 才标 done（不要在 200 行截断）。

合并：`python3 merge_nav_pages.py`（`mcp_pages/*.tsv` → `nav_long.csv`，按 `(SecuCode,d)` 去重，不发明行）。覆盖复核：`python3 coverage_status.py`。缺口清单见 `CACHE_GAP.md`。
