# 公募经营驾驶舱 · 风格原型

从内部「经营驾驶舱」截图拆出的视觉语言 + 可点击 HTML 原型。产品/经理均已匿名，数据为示意。

## 打开

```bash
cd apps/fund-cockpit
python3 -m http.server 8080
```

- 驾驶舱：http://127.0.0.1:8080/
- 设计规范：http://127.0.0.1:8080/design.html
- 路演 PPT：`docs/公募经营驾驶舱-风格拆解.pptx`

## 这套风格是什么

白底 Bento 卡片 + 金融蓝锚点。浅冷色画布、左侧 3px 蓝竖条标题、KPI 用大号等宽数字。红涨绿跌（A 股口径）。过滤下沉到卡片，页头只留数据截至日期。

信息架构四层，不要混排：

1. 经营管理（只数/规模/生命周期/申赎/营收）
2. 公司全景（同业雷达、规模结构、排行、管理费、渠道）
3. 基金投资（部门切片 + 产品表 + 静态风控）
4. 权益研究（考评、组合 vs 基准、行业收益）

Token 在 `apps/fund-cockpit/assets/tokens.css`。

## 建议技术栈

React / Vue 3 + CSS Grid + ECharts 5。每个卡片做成 `title / filters / renderer / queryKey`。先做 1920 工作台。
