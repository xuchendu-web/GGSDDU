---
name: fund-penetration
description: 基金组合穿透分析 — 输入基金列表，穿透至个股与申万一级行业层面，基于 Brinson 模型归因最近半年收益来源（配置效应/选股效应/交互效应），输出 HTML 可视化报告。触发词：基金穿透、Brinson归因、收益归因、组合归因、穿透分析、fund penetration。
metadata:
  type: user
  tags: [基金分析, 穿透, Brinson, 归因分析, 行业配置, FOF]
---

# 基金组合穿透与 Brinson 归因分析

> 基金组合 → 穿透到个股/行业 → 半年收益 Brinson 拆解 → HTML 报告

---

## 一、总览

本 skill 对给定的基金组合做两层穿透，并用量化模型回答「这半年的收益是怎么来的」：

| 步骤 | 内容 |
|------|------|
| **穿透** | 基金持仓 → 个股 → 申万一级行业，输出组合行业权重 vs 基准行业权重 |
| **归因** | Brinson 模型拆解超额收益：配置效应 + 选股效应 + 交互效应 |
| **展示** | HTML：行业配置对比图 + Brinson 归因棒棒糖图 + 个股贡献排名 |

---

## 二、Brinson 归因模型

### 2.1 核心公式

```
超额收益 R_excess = R_portfolio - R_benchmark

按行业 i 分解：
  配置效应(Allocation) = Σ (w_p_i - w_b_i) × R_b_i
  选股效应(Selection)   = Σ w_b_i × (R_p_i - R_b_i)
  交互效应(Interaction) = Σ (w_p_i - w_b_i) × (R_p_i - R_b_i)

其中：
  w_p_i = 组合在行业 i 的权重
  w_b_i = 基准在行业 i 的权重
  R_p_i = 组合在行业 i 的收益率
  R_b_i = 基准行业 i 的收益率
```

### 2.2 基准选择

默认基准：**沪深300 行业配置**���用沪深300成分股按申万行业聚合权重）

### 2.3 归因周期

最近 **6 个月**（约 120 个交易日），从基金最新报告期截止日开始计算。

### 2.4 因子归因（v2）

四大因子：规模(Small-Cap)/价值(Low PB)/动量(12-1M)/质量(ROE)。主动暴露 × 因子收益 = 因子贡献。

### 2.5 买卖时机评估（v2）

前10大持仓：入场时间、入场后收益、期间收益 → ✅精准/⚡及时/⚠️偏晚/❌追高

---

## 三、工作流程

```
┌────────────────────────────────────────────────────────────┐
│  Step 1: 获取基金持仓                                        │
│  对每只基金调用 get_table_data(code, "基金持股明细")           │
│  取最新报告期，提取：股票代码/名称/占净值比例(%)                 │
│  组合权重 = 所有基金等权合并，持仓叠加取总权重                   │
└──────────────────────────┬─────────────────────────────────┘
                           │
┌──────────────────────────▼─────────────────────────────────┐
│  Step 2: 股票→行业映射                                       │
│  用 cjpy get_factor_data 获取每只持仓股票的「一级行业」         │
│  聚合：Σ同行业股票权重 → 组合行业配置                          │
│  基准：沪深300成分股按同方式聚合 → 基准行业配置                 │
└──────────────────────────┬─────────────────────────────────┘
                           │
┌──────────────────────────▼─────────────────────────────────┐
│  Step 3: 计算行业收益率                                      │
│  过去6个月，每日：                                              │
│    组合行业收益率 = Σ(行业i内股票j的日收益率 × j在i内权重)       │
│    基准行业收益率 = 同方法用沪深300成分股计算                    │
│  累计收益率 = Π(1+日收益) - 1                                │
└──────────────────────────┬─────────────────────────────────┘
                           │
┌──────────────────────────▼─────────────────────────────────┐
│  Step 4: Brinson 归因计算                                    │
│  按 2.1 公式逐行业计算配置/选股/交互三效应                      │
│  汇总：总超额 = 总配置效应 + 总选股效应 + 总交互效应              │
└──────────────────────────┬─────────────────────────────────┘
                           │
┌──────────────────────────▼─────────────────────────────────┐
│  Step 5: 生成 HTML 报告                                      │
│  ├─ 组合 vs 基准 行业配置对比图（双柱状图）                     │
│  ├─ Brinson 归因图（各行业配置+选股+交互 棒棒糖图）             │
│  ├─ 行业收益贡献排名                                          │
│  └─ 穿透个股 TOP 贡献/拖累                                    │
└────────────────────────────────────────────────────────────┘
```

---

## 四、输出报告结构

### HTML 布局

```
┌──────────────────────────────────────────┐
│  标题：基金组合穿透与归因分析               │
│  副标题：组合名称 · 归因周期 · 基准        │
├──────────────────────────────────────────┤
│  摘要卡片：                               │
│  组合收益 | 基准收益 | 超额收益 |          │
│  配置效应 | 选股效应 | 交互效应            │
├──────────────────────────────────────────┤
│  📊 行业配置对比（组合 vs 基准 双柱状图）    │
├──────────────────────────────────────────┤
│  📈 Brinson 归因（棒棒糖图）               │
├──────────────────────────────────────────┤
│  📋 行业归因明细表                         │
├──────────────────────────────────────────┤
│  🎯 个股收益贡献 TOP10 / BOTTOM10          │
└──────────────────────────────────────────┘
```

---

## 五、使用示例

### 示例 1：单基金穿透

> 用户：「穿透分析 OF501046 财通多策略福鑫」

执行：提取持仓 → 行业映射 → Brinson 归因 → HTML

### 示例 2：FOF 组合穿透

> 用户：「分析我的 FOF 组合 OF018815 + OF501046 + OF005844 的穿透和归因」

执行：三只基金等权合并 → 穿透 → 归因

---

## 六、数据获取关键经验

### 6.1 批量计算收益率：用 get_factor_data 而非 get_market_data

`get_market_data` **只能传单个代码**，传 list 会报错 `'list' object has no attribute 'split'`。批量获取收益的正确姿势：

```python
# ❌ 错误：get_market_data(code_list, start, end) — code_list 不支持
# ✅ 正确：用 get_factor_data 分两次取起止日收盘价，算收益率

trading_days = cjpy.get_trading_days("20260101", "20260630", cycle="D")
start_date = str(trading_days[0])
end_date = str(trading_days[-1])

# 分批取起止日收盘价（100只/批）
stock_prices = {}
for batch in chunk(codes, 100):
    df1 = cjpy.get_factor_data(code=batch, date=[start_date], factors=["收盘价"])
    df2 = cjpy.get_factor_data(code=batch, date=[end_date], factors=["收盘价"])
    for code in batch:
        p1 = df1[df1['代码']==code]['收盘价'].values
        p2 = df2[df2['代码']==code]['收盘价'].values
        if len(p1) and len(p2) and p1[0] > 0:
            stock_prices[code] = (float(p2[0]) / float(p1[0]) - 1) * 100
```

**注意**：`get_factor_data` 中的 "收盘价" 是**后复权**，但计算两日比值时后复权系数前后一致，不影响收益率结果。不要用 "不复权收盘价"（可能返回 None）。

### 6.2 沪深300成分股获取

```python
# get_table_data("SH000300", "指数成份变动")
# 筛选 成份标志==1 得到当前300只成分股
df_hs300 = cjpy.get_table_data("SH000300", "指数成份变动")
hs300_codes = df_hs300[df_hs300['成份标志'] == 1]['证券代码'].unique().tolist()
# 再通过 get_factor_data 获取市值+行业，按市值加权聚合行业权重
```

### 6.3 行业名称对齐

`get_factor_data` 返回的行业值带 "申万" 前缀（如 "申万电子"），需要 strip 掉才能与基准对齐：

```python
industry = row['一级行业'].replace('申万', '')
```

### 6.4 基金代码格式转换

Wind/Excel 格式 `.OF` → cjpy `OF` 前缀格式：
```python
cjpy_code = 'OF' + code.replace('.OF', '')
```

---

## 七、HTML 报告生成规范（关键）

### 7.1 ⚠️ 严禁 f-string 直接嵌入 JavaScript

Python f-string 的 `{{` `}}` 转义与 JavaScript 对象字面量 `{` `}` **冲突**，会导致 Chart.js 语法错误图表无法渲染。

**错误方式**（图表不会显示）：
```python
html = f'''
<script>
new Chart(ctx, {{           # f-string 把 {{ 转成 { ，但可能出现转义不一致
  type: 'bar',
  data: {{                 # ← 实际输出可能是 {{ 或 { ，取决于转义层级
    labels: {json.dumps(labels)},
  }}
}});
</script>'''
```

**正确方式**：用 `%` 格式化或 `str.replace`，JS 代码原样写入：
```python
template = '''<script>
new Chart(ctx, {
  type: "bar",                    # JS 对象直接用 { }
  data: {
    labels: %(ind_labels_json)s,  # Python 变量用 %(key)s 占位
    datasets: [
      { label: "组合权重", data: %(port_data)s, backgroundColor: "#e74c3c" }
    ]
  },
  options: {
    responsive: true,
    maintainAspectRatio: false,
    plugins: {
      legend: { position: "top" },
      tooltip: { callbacks: { label: function(ctx) { return ctx.dataset.label + ": " + ctx.raw.toFixed(2) + "%"; } } }
    },
    scales: {
      y: { title: { display: true, text: "权重(%%)" }, ticks: { callback: function(v) { return v + "%%"; } } }
    }
  }
});
</script>'''

values = {'ind_labels_json': json.dumps(labels, ensure_ascii=False), ...}
html = template % values
```

**规则总结**：
| 组件 | 方式 | 原因 |
|------|------|------|
| JS 代码块 | `%` 格式化模板 | `{ }` 不被 Python 解释 |
| 数据注入 | `%(key)s` 占位 + `json.dumps` | 安全序列化 |
| CSS 中的 `%` | `%%` 转义为 `%` | `%` 格式化要求 |
| 避免 | f-string 嵌入 JS | 转义混乱 |

### 7.2 图表颜色约定

遵循中国股市红涨绿跌：`#e74c3c`（红/涨）、`#27ae60`（绿/跌）、`#3498db`（蓝/基准）、`#f39c12`（橙/交互效应）。

### 7.3 Chart.js 引入方式

CDN 方案（预览环境可直接加载）：
```html
<script src="https://cdn.jsdelivr.net/npm/chart.js@4.4.0/dist/chart.umd.min.js"></script>
```

### 7.4 变量名冲突防护

生成脚本中**不要用 `s` 作为循环变量**，因其通常持有 `data['summary']`。遍历股票列表时用 `st`、`d` 等名称：
```python
# ❌ for i, s in enumerate(stocks):   # s 被覆盖，后续 s['period_start'] KeyError
# ✅ for i, st in enumerate(stocks):
```

---

## 八、注意事项

1. **持仓滞后**：基金持仓按季报披露，最新数据可能滞后 1-2 个月
2. **权重归一**：组合内多基金等权合并，持仓权重归一化
3. **行业映射**：用 cjpy `一级行业` 因子，记得 strip "申万" 前缀
4. **停牌处理**：个股停牌期间收益率记为 0
5. **基准**：默认沪深300，通过 `指数成份变动` 表获取成分股
6. **缺失基金**：太新的基金（成立<1年）可能无持仓数据，跳过即可
7. **收益因子**：用 "收盘价"（后复权），不要用 "不复权收盘价"（常为 None）

---

## 九、依赖

- **cjpy MCP**：`get_table_data`（基金持股明细、指数成份变动）、`get_factor_data`（行业+收盘价+总市值）
- **cjpy Python 库**：批量数据处理、交易日历
- **Python 3.14+**（`C:\Python314\python.exe`）
- **无需额外 pip 包**（Chart.js 走 CDN）

---

## 八、依赖

- **cjpy MCP**：`get_table_data`（基金持股明细）、`get_factor_data`（行业+收益率）
- **cjpy Python 库**：批量数据处理
- **Python 3.14+**（`C:\Python314\python.exe`）
- **无需额外 pip 包**
