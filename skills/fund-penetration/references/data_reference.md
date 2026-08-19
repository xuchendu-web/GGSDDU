# 基金穿透与 Brinson 归因 — 数据参考

## Brinson 公式

```
超额 = 配置效应 + 选股效应 + 交互效应

按行业 i：
  配置效应(i) = (w_p_i - w_b_i) × R_b_i
  选股效应(i) = w_b_i × (R_p_i - R_b_i)
  交互效应(i) = (w_p_i - w_b_i) × (R_p_i - R_b_i)
```

## cjpy 数据通路

### 基金持仓
```
get_table_data(code="OF501046", table_name="基金持股明细")
→ 字段: 代码, 名称, 占净值比例(%), 板块名称
```

### 行业映射
```
get_factor_data(code=["持仓股票们"], date=["最新日期"], factors=["一级行业"])
→ 映射每只股票到申万一级行业
```

### 收益率
```
get_factor_data(code=["持仓+基准股票们"], date=["近120个交易日"], factors=["日收益率"])
→ 用于计算行业收益率
```

### 基准构建
沪深300成分股 → 同方法聚合成行业权重和行业收益

## JSON 格式

```json
{
  "fund_names": ["方正富邦核心优势A","财通多策略福鑫"],
  "period": "最近6个月",
  "benchmark_name": "沪深300",
  "portfolio_return": 0.35,
  "benchmark_return": 0.12,
  "portfolio": {
    "电子": {"weight": 0.42, "return": 0.52},
    "电力设备": {"weight": 0.25, "return": 0.38}
  },
  "benchmark": {
    "电子": {"weight": 0.18, "return": 0.35},
    "电力设备": {"weight": 0.15, "return": 0.30}
  },
  "stock_contributions": [
    {"name":"寒武纪","sector":"电子","weight":9.5,"contrib":8.2},
    {"name":"中际旭创","sector":"通信","weight":8.0,"contrib":5.5}
  ]
}
```

## 归因结论模板

| 超额方向 | 配置效应 | 选股效应 | 解读 |
|---------|---------|---------|------|
| 正超额 | 正 | 正 | 行业配置+选股双优 |
| 正超额 | 正 | 负 | 靠超配强势行业，选股能力一般 |
| 正超额 | 负 | 正 | 行业配置一般，但选股出色 |
| 负超额 | 负 | 负 | 行业配置+选股双差 |
