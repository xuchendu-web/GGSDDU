# 事件驱动型个股复盘 — 数据参考

## 归因模型公式

```
个股涨跌幅 = α + β × 大盘涨跌幅 + γ × 行业涨跌幅

大盘贡献 = β × 沪深300涨跌幅（窗口期）
行业贡献 = 申万一级行业指数涨跌幅（窗口期）
个股Alpha = 实际涨跌幅 - 大盘贡献 - 行业贡献

其中：
  β = Cov(个股60日收益率, 沪深300 60日收益率) / Var(沪深300 60日收益率)
  γ 默认视为 1（行业同向联动）
```

## cjpy 数据调用

### 个股行情
```python
get_market_data(
    code="SZ300750",
    start="基准开始日",
    end="窗口结束日",
    cycle="day",
    rate="前复权"
)
```

### 大盘指数
```python
get_market_data(
    code="SH000300",  # 沪深300
    start="基准开始日",
    end="窗口结束日",
    cycle="day"
)
```

### 行业分类 + 行业指数
```python
get_factor_data(
    code=["SZ300750"],
    date=["事件日"],
    factors=["一级行业", "二级行业"]
)
```

### 事件数据
```python
# 公告
get_table_data(code="SZ300750", table_name="股票公告")

# 龙虎榜
get_table_data(code="SZ300750", table_name="交易公开信息")

# 增减持
get_table_data(code="SZ300750", table_name="股东增减持")

# 业绩
get_table_data(code="SZ300750", table_name="业绩预告")
```

## JSON 数据格式

```json
{
  "code": "SZ300750",
  "name": "宁德时代",
  "event": "2026年中报发布",
  "event_date": "20260723",
  "pre_window": 3,
  "post_window": 5,
  "beta": 1.15,
  "sector_return": 1.8,
  "baseline_volume": 50000000,
  "stock_prices": [
    {"date": "20260718", "close": 370.0, "volume": 45000000},
    {"date": "20260721", "close": 372.3, "volume": 52000000},
    {"date": "20260722", "close": 372.3, "volume": 48000000},
    {"date": "20260723", "close": 386.0, "volume": 85000000}
  ],
  "market_prices": [
    {"date": "20260718", "close": 4600.0},
    {"date": "20260721", "close": 4739.2},
    {"date": "20260722", "close": 4717.2},
    {"date": "20260723", "close": 4728.0}
  ],
  "events": [
    {"title": "宁德时代发布2026年中报，Q2净利润超预期", "time": "2026-07-23", "source": "公司公告"}
  ],
  "announcements": [
    {"date": "20260723", "title": "2026年半年度报告"}
  ]
}
```

## 成交量异动判断

| 量比 | 标记 | 含义 |
|------|------|------|
| >2.0x | 大幅放量 | 事件冲击强烈，资金激烈博弈 |
| 1.5~2.0x | 放量 | 事件引起明显关注 |
| 0.5~1.5x | 正常 | 事件未引发显著量能变化 |
| <0.5x | 缩量 | 市场对事件反应冷淡 |

## WebSearch 关键词模板

- `"{股票名} 新闻 {事件日期}"`
- `"{股票名} 公告 {关键词} {事件日期}"`
- `"{股票名} 龙虎榜 {事件日期}"`
