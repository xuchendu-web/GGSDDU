---
name: jctrader
description: 用 jctrader MCP 分析 A 股盘面、板块强弱、ETF/商品信号与配置建议。用户提到 jctrader、市场盘面、最新信号、板块强度、市场情绪、宽基、共振矩阵、拥挤度或商品信号时必须使用本 skill。
metadata:
  version: 1.0.0
  source: jctrader-mcp
---

# jctrader 市场信号

通过 jctrader MCP（`jctrader-mcp` v1.0.0）读取实时信号。只使用本次工具返回值，不编造买卖信号或盘面数字。

## 何时使用

- 用户问市场、盘面、风格、板块、ETF、商品，或「有什么信号」
- 用户点名 jctrader / 拐点信号 / 跟踪信号 / 共振 / 拥挤度
- 需要从信号给出多空、主线和回避方向

## 云端连接（必须先做）

Cursor Cloud 的 MCP 目录经常**只有** `cursor-cloud`，看不到 jctrader 工具。这不代表服务不可用。

按这个顺序取数：

1. 若当前会话已有 jctrader MCP 工具（如 `get_market_sentiment`），直接调用。
2. 否则立刻用本 skill 自带客户端，不要改去搜网页或编造数据：

```bash
python3 .cursor/skills/jctrader/scripts/jctrader_client.py board
python3 .cursor/skills/jctrader/scripts/jctrader_client.py call get_market_sentiment '{"metric":"all"}'
python3 .cursor/skills/jctrader/scripts/jctrader_client.py list
```

默认地址：`http://8.159.152.196:3000/sse?token=friends-chenji`  
可用环境变量覆盖：`JCTRADER_MCP_URL`、`JCTRADER_TOKEN`。

连不上时如实说明，并停止给出具体买卖占比。

## 盘面分析流程

默认先拉全景，再下钻，不要只看一只股票下结论。

1. **总盘**：`get_market_sentiment`、`get_market_breadth`、`get_market_resonance_matrix`
2. **风格**：`get_sector_strength`（`dimension=index`）看上证50 / 沪深300 / 中证500 / 1000 / 2000 / 科创 / 创业板 / 北证
3. **行业**：`get_sector_strength` + `get_sector_freshness` + `get_reversal_risk` + `get_signal_crowding`（`industry_l1`）
4. **主题/概念**：`get_sector_strength`（theme/concept）、`get_concept_voice_index`
5. **落地**：`get_etf_signals`（按关键词）、`get_etf_sector_match`、`screen_stocks`（`tracking_fresh_days=5`）
6. **跨市场**：`get_commodity_signals`
7. **配置**：`get_allocation_weights`；用户给了持仓再用 `get_portfolio_status` / `get_rebalance_suggestion`

`board` 命令会一次拉第 1–3 步和第 6–7 步的核心接口。

完整参数见 [references/tools.md](references/tools.md)。

## 读数口径

| 字段 | 用法 |
|------|------|
| `interpretation` / `overall_buy_ratio` | 情绪总判。约 50% 为中性，明显低于 45% 偏谨慎 |
| `inflection` | 拐点信号（状态切换） |
| `tracking` | 跟踪信号（趋势是否仍有效） |
| `fresh_buy_ratio` / `days_since_tracking` | 新动能。近 5 日才算新鲜 |
| `strength_score` | 强度综合分，用来排序，不是胜率 |
| 共振四象限 | `down_acceleration` 下行加速；`bull_loosening` 多头松动；`trend_acceleration` 趋势加速；`bear_exhaustion` 空头衰竭 |
| 反转象限 | 黄金区=动能尚可；蛰伏区=买入比例不低但新信号少；拥挤标注「较为拥挤」则不宜追高 |

双信号一致（Buy/Buy 或 Sell/Sell）权重大于单边。新鲜 Buy + 黄金区，优先于「买入占比高但 fresh 很低」的老强势。

## 已知限制（不要误读）

- `get_market_breadth` 的 `index` 过滤可能无效，结果会与 `all` 相同；风格比较改看 `get_sector_strength` 的 index。
- `get_long_short_pairs` 可能返回空列表，改用行业强度头尾对比。
- `get_top_rated_stocks` 可能出现大量同分，且按代码排序；不要当成精选排行榜。
- `screen_stocks` 无行业过滤时，结果常按代码排列，只是新鲜样本，不是质量排名。
- `get_etf_signals` 全量约 1000 条，先用 `keyword` 或自己按名称汇总。
- 信号快照可能数日不更新。若读数与上次完全相同，要写明「快照未更新」。

## 输出要求

用中文，先给总判断，再列信号。建议结构：

1. 一句话总判（中性 / 偏多 / 偏空 / 结构分化）
2. 情绪、宽度、共振数字
3. 宽基强弱阶梯
4. 主线、修复、蛰伏、回避
5. 新鲜个股或 ETF（若用户需要）
6. 商品与操作含义

标注这是 jctrader 信号统计，不是成交额或涨跌幅排名。没有数据就说没有，不要用外部行情顶替。
