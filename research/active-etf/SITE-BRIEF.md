# SITE-BRIEF：`/active/index.html`

给后续在本地实现的 Composer。本文件是页面规格。当前分支只放研究，不实现模板，不构建，不部署。

研究依据：`OVERSEAS.md`、`CHINA-22.md`、`RESEARCH.md`。三份文件的事实截止 2026-10-26。实现时不得改写已核对的数字；空字段保持为空。

## 0. 禁止事项

- 不连接、不部署、不 SSH 到 `etf-abc.cn` 或其主机，不打开隧道，不改 nginx、防火墙、安全组或已有远程控制进程。
- 不在本任务里启动对外端口。本地预览只用站点仓库已有的 `preview/render_preview.py` 或静态文件服务，绑定本机即可。
- 不新增买卖、开户、认购跳转。外部链接只指向交易所规则、基金公司资料概要和本目录已经引用的公开报道，并加 `rel="noreferrer"`。
- 不制作净值、收益率、回撤、规模、IOPV 或折溢价。数据里没有这些字段，图表组件也不要留一个空的业绩图。
- 不把产品称为指数基金，不写“22 只已获批”，不写“盘中实时持仓”，不写“稳健所以回撤更小”，不给 18 只排名。
- 不改 `:root` 设计令牌，不改策略回测、`sources.py` 和已有页面的数据条件。

## 1. 代码放在哪

站点源码不在 `main`。2026-10-25 的视觉和构建在分支 `cursor/etf-site-visual-polish-a63b` 的 `research/etf-site/`。实现时从那条站点线拉出新分支，把本目录四份 Markdown 作为只读依据拷入或引用，避免在只有 README 的 `main` 上重做一套站。

建议改动面：

| 文件 | 动作 |
| --- | --- |
| `research/etf-site/data/active-etf.json` | 新建。内容等于下方 JSON |
| `research/etf-site/templates/active.html` | 新建。extends `base.html` |
| `research/etf-site/templates/base.html` | 主导航在「市场」和「口径」之间加「主动」，指向 `active/index.html`。当前页加 `aria-current="page"` |
| `research/etf-site/static/active.js` | 新建。只做筛选、搜索和行展开 |
| `research/etf-site/static/style.css` | 只追加 `.page-active` 作用域。不改已有选择器的默认值 |
| `research/etf-site/build.py` | 增加一页输出 `active/index.html`。没有净值数据依赖 |
| `research/etf-site/templates/about.html` | 可选：加三行术语，PCF、IOPV、认购代码。不改其他口径段落 |

输出 URL：`/active/index.html`。标题：`主动 ETF · ETF 分析`。

## 2. 页面结构

沿用现有壳：顶部风险条、sticky 顶栏、页脚备案位。风险条已有“回测与模拟跟踪仅供研究，不构成投资建议”。本页在英雄区下再加一条本页状态，避免读者把募集产品当成已跟踪策略。

宽度：这一页的 `main` 使用页内类，把最大宽度放到 1120px。其他页面仍是 960px。表格区域允许横向滚动，第一列在滚动时保持可读即可，不要求冻结列。

自上而下：

1. 英雄区
2. 状态条
3. 四个数字
4. 结构对照（四列）
5. 费率刻度
6. 筛选和 18 行表
7. 机制三张卡
8. 风险清单
9. 来源

### 2.1 英雄区

眉题：`2026-10-26 · 募集期`

标题：`首批 18 只主动 ETF 已获批，仍在募集，没有净值`

导语：

> 这是不跟踪指数的股票型 ETF。每个交易日开市前披露真实组合的申购赎回清单，持仓不少于 30 只，前十大合计不超过净值的 60%。管理费 1.00%。公开批文是 18 只，单只募集上限 20 亿元。

不要用“境内版 ARKK”做标题。

### 2.2 状态条

三条并列，样式用现有 `.warn` 的颜色变量，单独一块，不替换全站顶栏：

- 状态：认购期。2026-10-23 起募，易方达资料概要写明暂未上市。
- 数据：聚源基金列表尚未收录这些产品。本页不显示净值和规模。
- 名单：证监会转载稿与上交所英文稿均为 18 只。没有第二批名单。

### 2.3 四个数字

| 数字 | 标注 |
| --- | --- |
| 18 | 2026-10-19 同意注册 |
| 20 亿元 | 单只募集上限，合计上限 360 亿元 |
| 1.00% | 管理费。批次报道；国泰档案与平安发售报道已点名 |
| 0 | 本页可展示的历史净值个数 |

数字用 `tabular-nums`。

### 2.4 结构对照

四列卡片，桌面四列，窄屏一列。每列一个短句加一个费率，不放走势。

| 列 | 标题 | 正文 | 费率行 |
| --- | --- | --- | --- |
| 1 | 境内宽基 ETF | 跟踪指数。华泰柏瑞沪深 300ETF 自 2024-11-22 起管理费 0.15%、托管费 0.05%。 | 运作费 0.20% |
| 2 | 境内首批主动 ETF | 不跟踪指数。开市前披露真实组合 PCF。至少 30 只，前十大不超过 60%。 | 管理费 1.00% |
| 3 | 全透明主动股票 | ARKK 总费率 0.75%。官网每日提供持仓文件。2026-03-31 前十大合计 52.4%，只数 35–55。 | 0.75% |
| 4 | 半透明主动 | 不每日公开真实持仓，不能使用美国 Rule 6c-11。境内指引要求真实组合 PCF，试点不走这条路。 | 不单列产品 |

第 4 列展开后才显示五条路径的名称：ActiveShares、Fidelity 跟踪篮子、Blue Tractor、T. Rowe Price、Natixis / NYSE。每条一行，不解释申赎账户怎么开。

### 2.5 费率刻度

纯 CSS 横条，长度按费率比例，最大刻度 1.40%（场外上限 1.2%+0.2%）。不要引入图表库。

条目标签必须含资产，防止读者把利率差当成主动能力：

- BND / AGG · 美国投资级综合债 · 0.03%
- SPY · 标普 500 · 0.0945%
- QQQ · 纳斯达克 100 · 0.18%
- JPST · 主动超短债 · 0.18%
- JAAA · AAA CLO · 0.20%
- 510300 · 沪深 300 · 0.20%（0.15%+0.05%）
- MINT / FBND · 主动短债或综合债 · 0.36%
- BINC · 主动多行业债 · 净 0.40%（毛 0.52%，减免至 2027-06-30）
- ARKK · 全球创新股票 · 0.75%
- 境内主动 ETF · 境内股票 · 管理费 1.00%，已点名样本托管费另计 0.15%
- 场外主动股票注册上限 · 1.20% + 托管费上限 0.20%

图下固定一句：`横条只比较说明书或公告里的费率，不比较收益。JAAA、BINC 的久期和信用与 BND 不同。`

### 2.6 筛选与表格

筛选是两组按钮加一个搜索框，组间取交集：

- 交易所：全部、上交所、深交所
- 风格：全部、均衡、价值、红利、质量、大盘成长
- 方法：全部、基本面、纯量化、量化+基本面
- 搜索：管理人、产品名、代码、基金经理。空字段不参与匹配

默认显示 18 行，顺序与 `CHINA-22.md` 表相同。结果计数写成“显示 18 / 18”。筛完为零时使用现有 `.empty`：`没有同时满足这些条件的产品。`

表格列：

管理人、产品、交易所、风格、方法、业绩比较基准、交易代码、认购代码、基金经理、托管费、募集截止

管理费不单列，表题下写一行：`管理费按已披露报道均为 1.00%，单只募集上限 20 亿元。16 只尚未逐份打开费率表。`

空值渲染为 `待公告`，颜色用 `--ink-faint`。不要渲染成 0 或“—”。

行可展开。展开区只放该行 JSON 里的 `note` 和 `sources`。没有备注的行不显示展开按钮。

平安的展开备注写红利主题股票的合同约束，并写明“只适用于平安”。国泰的展开备注写托管人中国银行、最高认购费率 0.80%。易方达的展开备注写认购费分档、托管人招商银行、固有资金 2 亿元于募集首日认购、股票资产不低于 80%。

### 2.7 机制三张卡

1. **两个代码。** 募集期用认购代码，上市后用交易代码。已核对的例子：易方达 581053 / 581050，华夏 581033 / 581030，汇添富 581013 / 581010，华安 581023 / 581020，平安 581073 / 581070。国泰公开材料只有 158907。未公布的代码保持待公告。
2. **PCF 不是盘中持仓。** 清单在开市前发布，对应前一交易日日终的真实组合。IOPV 在交易时间发布。半透明结构使用的保密账户和代理篮子不属于这次试点。
3. **怎么参与。** 证券账户。新民晚报报道募集期 1000 份起、面值 1 元；上市后 100 份为 1 手。当时没有场外联接基金。超过上限时末日比例确认。二级市场买卖还有佣金和折溢价。

### 2.8 风险清单

用有序列表，六条，保持这个顺序：

1. 股票型基金。已打开的文本和批次报道都指向股票仓位不低于 80%。风格词里的“均衡”“红利”不是保本。
2. 没有可比较的历史净值。基金经理在其他产品上的业绩不在本页展示。
3. 上市初期成交可能稀少，成交价可以偏离 IOPV。
4. 每日披露使持仓可被跟单。这是指引选择全透明之后的代价，不是产品故障。
5. 认购资金锁定到成立。热门产品可能比例配售。认购按面值，不是股票打新。
6. 各家业绩比较基准不同。比较两只“均衡”之前先看基准是中证 800、中证 A500 还是中证 A100。

### 2.9 来源

页脚前用 `<details>`，摘要为“数字出处”。里面按 `OVERSEAS.md` 和 `CHINA-22.md` 的 Sources 列出链接，每条带日期。不要把研究 Markdown 原样贴进 HTML。

## 3. 视觉

使用 `research/etf-site/static/style.css` 已有变量：`--ink`、`--ink-muted`、`--canvas`、`--surface`、`--accent`、`--warn-bg`、`--radius-md`、`--shadow-sm`。

组件直接复用：`.hero`、`.grid`、`.note`、`.empty`、`.tabular`、顶栏和页脚。新增样式全部挂在 `.page-active` 下。

费率横条的填充色用 `--accent`。510300 与境内主动 ETF 这两条可以加 2px 描边 `--border-strong`，方便在一长串美国产品里看见境内参照。不使用红涨绿跌，因为本页没有涨跌。

筛选按钮：未选中是白底灰字，选中是 `--accent-soft` 底、`--accent` 字，并设置 `aria-pressed`。焦点环保留。

窄于 720px：四列对照改成一列；表格包在 `overflow-x: auto` 里；筛选按钮允许换行。`prefers-reduced-motion: reduce` 时去掉行展开的高度动画。

## 4. 数据文件

路径：`research/etf-site/data/active-etf.json`。

实现时把下面 JSON 原样写入。`null` 在页面上变成“待公告”。不要补全代码，不要把 `management_fee_confidence` 从 `batch` 改成 `prospectus`。

```json
{
  "as_of": "2026-10-26",
  "approved_count": 18,
  "approval_date": "2026-10-19",
  "subscription_start": "2026-10-23",
  "cap_cny_per_fund": 2000000000,
  "cap_cny_batch": 36000000000,
  "management_fee": 0.01,
  "management_fee_confidence": "batch",
  "nav_available": false,
  "products": [
    {"id": "efunds-quality-balance", "exchange": "SSE", "manager": "易方达", "name": "品质均衡", "style": "balanced", "style_label": "均衡", "method": "fundamental", "method_label": "基本面", "benchmark": "中证800", "trade_code": "581050", "subscribe_code": "581053", "managers": ["杨思亮", "倪春尧"], "custody_fee": 0.0015, "custody_fee_note": "同花顺以易方达、富国为例", "subscribe_end": "2026-10-29", "note": "资料概要：托管人招商银行；股票资产不低于80%；认购费100万份以下0.80%，100万至500万份0.50%，500万份及以上1000元/笔；暂未上市。中国基金报：固有资金2亿元于2026-10-23认购。", "sources": ["efunds-kiid", "xinmin", "10jqka", "chnfund-launch"]},
    {"id": "chinaamc-quality", "exchange": "SSE", "manager": "华夏", "name": "质量甄选", "style": "quality", "style_label": "质量", "method": "fundamental", "method_label": "基本面", "benchmark": null, "trade_code": "581030", "subscribe_code": "581033", "managers": [], "custody_fee": null, "subscribe_end": "2026-10-29", "note": null, "sources": ["xinmin", "cls"]},
    {"id": "maxwealth-prosperity", "exchange": "SSE", "manager": "永赢", "name": "景气均衡", "style": "balanced", "style_label": "均衡", "method": "fundamental", "method_label": "基本面", "benchmark": "中证A100", "trade_code": null, "subscribe_code": null, "managers": ["许拓", "蔡路平"], "custody_fee": null, "subscribe_end": null, "subscribe_end_label": "11月初", "note": "风格筛选项用均衡。基准来自同花顺，经理来自证券时报。", "sources": ["10jqka", "stcn"]},
    {"id": "jpm-large-growth", "exchange": "SSE", "manager": "摩根", "name": "大盘成长", "style": "large_growth", "style_label": "大盘成长", "method": "fundamental", "method_label": "基本面", "benchmark": null, "trade_code": null, "subscribe_code": null, "managers": [], "custody_fee": null, "subscribe_end": null, "subscribe_end_label": "11月初", "note": null, "sources": ["cls"]},
    {"id": "huatai-value", "exchange": "SSE", "manager": "华泰柏瑞", "name": "价值精选", "style": "value", "style_label": "价值", "method": "fundamental", "method_label": "基本面", "benchmark": "中证800价值", "trade_code": null, "subscribe_code": null, "managers": ["杨景涵", "尤家妤"], "custody_fee": null, "subscribe_end": "2026-10-29", "note": "基准是证券时报对4只价值产品的分组表述。", "sources": ["stcn", "chnfund"]},
    {"id": "htff-balance", "exchange": "SSE", "manager": "汇添富", "name": "均衡策略智选", "style": "balanced", "style_label": "均衡", "method": "quant_fundamental", "method_label": "量化+基本面", "benchmark": null, "trade_code": "581010", "subscribe_code": "581013", "managers": [], "custody_fee": null, "subscribe_end": "2026-10-30", "note": null, "sources": ["xinmin", "cls", "chnfund"]},
    {"id": "huaan-balance", "exchange": "SSE", "manager": "华安", "name": "均衡慧选", "style": "balanced", "style_label": "均衡", "method": "fundamental", "method_label": "基本面", "benchmark": null, "trade_code": "581020", "subscribe_code": "581023", "managers": ["苏圻涵", "王超"], "custody_fee": null, "subscribe_end": "2026-10-29", "note": null, "sources": ["xinmin", "stcn", "chnfund"]},
    {"id": "cmf-value", "exchange": "SSE", "manager": "招商", "name": "价值智选", "style": "value", "style_label": "价值", "method": "quant_fundamental", "method_label": "量化+基本面", "benchmark": "中证800价值", "trade_code": null, "subscribe_code": null, "managers": [], "custody_fee": null, "subscribe_end": "2026-10-29", "note": "基准是证券时报对价值组的分组表述。", "sources": ["stcn", "cls", "chnfund"]},
    {"id": "pingan-dividend", "exchange": "SSE", "manager": "平安", "name": "红利景气", "style": "dividend", "style_label": "红利", "method": "fundamental", "method_label": "基本面", "benchmark": "中证红利", "trade_code": "581070", "subscribe_code": "581073", "managers": ["刘榕俊", "钱晶"], "custody_fee": 0.0015, "subscribe_end": "2026-11-09", "note": "界面新闻引述：管理费1.00%，托管费0.15%，募集期2026-10-23至2026-11-09。红利主题股票不低于非现金基金资产的80%。该比例定义只适用于本产品。", "sources": ["jiemian", "stcn"]},
    {"id": "southern-balance", "exchange": "SZSE", "manager": "南方", "name": "均衡配置", "style": "balanced", "style_label": "均衡", "method": "fundamental", "method_label": "基本面", "benchmark": "中证800", "trade_code": null, "subscribe_code": null, "managers": [], "custody_fee": null, "subscribe_end": "2026-10-29", "note": "基准来自同花顺对易方达、南方、建信的分组。易方达另有资料概要核对。", "sources": ["10jqka", "chnfund"]},
    {"id": "fullgoal-value-quant", "exchange": "SZSE", "manager": "富国", "name": "价值优选量化选股", "style": "value", "style_label": "价值", "method": "quant", "method_label": "纯量化", "benchmark": "中证800价值", "trade_code": null, "subscribe_code": null, "managers": [], "custody_fee": 0.0015, "custody_fee_note": "同花顺举例", "subscribe_end": "2026-10-30", "note": null, "sources": ["10jqka", "cls", "chnfund"]},
    {"id": "dacheng-dividend", "exchange": "SZSE", "manager": "大成", "name": "红利智选", "style": "dividend", "style_label": "红利", "method": "quant_fundamental", "method_label": "量化+基本面", "benchmark": "中证红利", "trade_code": null, "subscribe_code": null, "managers": [], "custody_fee": null, "subscribe_end": null, "subscribe_end_label": "11月初", "note": "基准是证券时报对3只红利产品的分组表述。", "sources": ["stcn", "cls"]},
    {"id": "penghua-value", "exchange": "SZSE", "manager": "鹏华", "name": "价值臻选", "style": "value", "style_label": "价值", "method": "fundamental", "method_label": "基本面", "benchmark": "中证800价值", "trade_code": null, "subscribe_code": null, "managers": [], "custody_fee": null, "subscribe_end": null, "subscribe_end_label": "11月初", "note": null, "sources": ["stcn", "cls"]},
    {"id": "icbccs-dividend", "exchange": "SZSE", "manager": "工银瑞信", "name": "红利", "style": "dividend", "style_label": "红利", "method": "fundamental", "method_label": "基本面", "benchmark": "中证红利", "trade_code": null, "subscribe_code": null, "managers": [], "custody_fee": null, "subscribe_end": null, "subscribe_end_label": "11月初", "note": null, "sources": ["stcn", "cls"]},
    {"id": "huabao-balance", "exchange": "SZSE", "manager": "华宝", "name": "均衡精选", "style": "balanced", "style_label": "均衡", "method": "fundamental", "method_label": "基本面", "benchmark": "中证A500", "trade_code": null, "subscribe_code": null, "managers": ["丁靖斐", "蒋俊阳"], "custody_fee": null, "subscribe_end": null, "subscribe_end_label": "11月初", "note": "基准来自同花顺对国泰、华宝的分组。国泰另有档案核对。", "sources": ["10jqka", "stcn"]},
    {"id": "gtfund-balance", "exchange": "SZSE", "manager": "国泰", "name": "鑫汇均衡收益", "style": "balanced", "style_label": "均衡", "method": "fundamental", "method_label": "基本面", "benchmark": "中证A500", "trade_code": "158907", "subscribe_code": null, "managers": ["程洲", "朱碧莹"], "custody_fee": 0.0015, "subscribe_end": "2026-11-05", "note": "天天基金档案：管理费1.00%，托管费0.15%，托管人中国银行，最高认购费率0.80%，无跟踪标的。每经网：募集期2026-10-23至2026-11-05。未见到单独认购代码。", "sources": ["eastmoney", "nbd", "stcn"]},
    {"id": "tianhong-quant", "exchange": "SZSE", "manager": "天弘", "name": "均衡量化选股", "style": "balanced", "style_label": "均衡", "method": "quant", "method_label": "纯量化", "benchmark": null, "trade_code": null, "subscribe_code": null, "managers": [], "custody_fee": null, "subscribe_end": null, "subscribe_end_label": "11月初", "note": null, "sources": ["cls"]},
    {"id": "ccb-balance", "exchange": "SZSE", "manager": "建信", "name": "均衡优选", "style": "balanced", "style_label": "均衡", "method": "fundamental", "method_label": "基本面", "benchmark": "中证800", "trade_code": null, "subscribe_code": null, "managers": [], "custody_fee": null, "subscribe_end": null, "subscribe_end_label": "11月初", "note": "基准来自同花顺对易方达、南方、建信的分组。", "sources": ["10jqka", "cls"]}
  ]
}
```

字段约定：

- `subscribe_end` 为 `null` 时，表格用 `subscribe_end_label`。
- `managers` 为空数组时显示待公告。
- `custody_fee` 是小数。0.0015 显示为 0.15%。
- 构建脚本校验：`products.length === 18`；风格计数均衡 9、价值 4、红利 3、质量 1、大盘成长 1；方法计数基本面 13、纯量化 2、量化+基本面 3；上交所 9、深交所 9。校验失败则构建失败。

## 5. 交互验收

本地打开 `active/index.html` 后逐条核对：

1. 首屏标题含“18 只”和“没有净值”，不含“22 只”，不含“ARKK”作为产品别名。
2. 默认表格 18 行。筛选“深交所 + 红利”得到大成、工银瑞信两行（平安在上交所，不应出现）。再加“纯量化”后为空态。
3. 筛选“均衡 + 量化+基本面”只剩汇添富。筛选“价值 + 纯量化”只剩富国。
4. 搜索 `581053` 只命中易方达。搜索 `158907` 只命中国泰。搜索一个不存在的尾号，例如按规律臆造的号码，结果为空。
5. 国泰行没有认购代码，单元格是“待公告”。华夏行没有基金经理。
6. 页面源代码和可见文本里没有净值、涨跌幅、`%` 形式的收益率。费率百分号除外。
7. 键盘可以切换筛选按钮，焦点可见。表格在 390px 宽下不把页面撑出横向滚动条以外的溢出；溢出只发生在表格容器内。
8. 导航「主动」在本页带 `aria-current`。从首页、策略、对比、口径点回，顶栏状态正确。
9. 构建校验：把 JSON 临时删成 17 行时构建失败；恢复后通过。这个临时修改不要提交。

## 6. 做完即停

这一页的完成定义是：静态页表达 18 只产品的结构、费率和信息缺口。成立、上市、PCF 文件和净值是下一次数据任务，不在这次实现里预埋假数据或隐藏图表。

## Sources

页面文案的事实来源即 `OVERSEAS.md` 与 `CHINA-22.md` 的 Sources。视觉约束来自站点分支 `cursor/etf-site-visual-polish-a63b` 的 `research/etf-site/static/style.css` 与 `templates/base.html`，该分支不在本次提交中。
