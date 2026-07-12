# news_search 工具原型

借鉴 [cn-web-search](https://github.com/joansongjr/cn-web-search) 的多引擎聚合思路，工程化为对话层可注册的资讯检索工具。设计说明见 `docs/对话层-资讯检索工具设计.md`。

## 运行

```bash
pip install requests beautifulsoup4
python3 search_provider.py "沪深300 调样 2026"
```

## 输出结构

```json
{
  "snapshot_id": "NS-xxxxxxxx",
  "query": "...",
  "engine_trace": {"sogou": {"status": "ok", "hits": 9}, "...": "..."},
  "results": [
    {"title": "...", "url": "...", "engine": "sogou",
     "tier": 3, "corroboration": 2, "engines": ["sogou", "so360"]}
  ],
  "usage_rule": "T1 可作事实引用；T3/T4 仅作线索…"
}
```

- `tier`：来源可信度分层（1 官方 / 2 权威财经 / 3 聚合搜索 / 4 社区）
- `corroboration`：跨引擎交叉佐证数（同一事实被几个独立引擎命中）
- `snapshot_id`：检索快照编号，供证据包引用
