# ETF 站点视觉打磨变更说明

> 范围：`research/etf-site-visual/` — **仅视觉与交互**，未改动信息架构、区块顺序或删节。  
> 主题：**精炼浅色（Refined Light）**，现代投研风；刻意避免酒红/宣纸类「HENG」审美。

## 设计系统

| 类别 | 变更 |
|------|------|
| **色彩 Token** | `:root` 定义背景层级（`--color-bg` / `--color-bg-elevated`）、文本四级、accent 蓝、红涨绿跌、警示条、图表专用色（策略/基准/回撤）。 |
| **字体** | Inter + 系统中文字体栈；标题字重 600–700、`letter-spacing: -0.02em`；数值 `tabular-nums`。 |
| **间距** | 4px 基准刻度 `--space-1` … `--space-12`，统一 main/header/card 内边距。 |
| **圆角与阴影** | `--radius-sm/md/lg`；卡片 `--shadow-sm`，hover `--shadow-md`；表格与 chart 容器 `--shadow-xs`。 |
| **动效** | 150–220ms cubic-bezier；卡片 hover 微抬升；`prefers-reduced-motion` 降级。 |

## 组件与页面

| 区域 | 具体变化 |
|------|----------|
| **顶栏** | 半透明白 + `backdrop-filter` 毛玻璃；导航项 pill hover / focus-visible 环。 |
| **免责声明条** | 保留文案；加底边线与 warn token，字号略收。 |
| **最新信号卡 `.signal`** | 保留双卡结构；加 gap、hover 阴影；开/关色 token 化。 |
| **策略卡片 `.grid/.card`** |  elevation + 边框透明化；hover 边框变 accent、`-2px` 位移；标签 `.tag` 胶囊化。 |
| **KPI `.kpi`** | 四列网格保留；单元格阴影与 tabular 数字。 |
| **口径页 `about`** | 内容列表未改；外包 `article` 白卡片与列表行距。 |
| **三轨对照 `compare`** | 两表 + footnote 结构保留；`.scroll` 横向滚动；表头 sticky；行 hover 淡蓝底；冠军 badge。 |
| **九策略表** | 见 `projects/champion-industry-etf.html` / `templates/project.html`；移动端正列 sticky（≤600px）。 |
| **折叠 `details.dev/rep`** | 卡片式边框；自定义 ▸ 箭头旋转；summary hover accent。 |
| **页脚** | 顶部分割线 + 浅底，链接 muted → accent。 |

## 图表（CSS + `static/charts.js`）

| 项 | 说明 |
|----|------|
| **容器 `.chart-wrap`** | 白底、圆角、内边距；`focus-within` 高亮。 |
| **系列色** | 策略实线 `#2563eb` 2px；基准虚线 `#94a3b8`；回撤渐变填充 + 描边。 |
| **网格** | `.g` 使用低对比 `--color-chart-grid`。 |
| **Tooltip** | 深色浮层，日期 + 多系列行；`data-chart-dates` / `data-chart-values` 驱动。 |
| **十字准线** | SVG 竖线 `.chart-crosshair`，hover 时显示；触摸 `touchmove` 支持。 |
| **图例** | `.legend` flex 换行；色条圆角加粗。 |

## 文件清单

```
research/etf-site-visual/
├── DESIGN-CHANGELOG.md          # 本文件
├── index.html                   # 首页预览（信号 + 网格 + 折叠 + 模拟组合 + 市场链）
├── about.html                   # 口径与免责声明
├── static/
│   ├── style.css                # 设计系统 + 全站组件
│   └── charts.js                # 图表 tooltip / 准线
├── templates/                   # 与上传 Jinja 结构对齐，类名已升级
│   ├── base.html
│   ├── index.html
│   ├── about.html
│   ├── compare.html
│   ├── project.html             # 信号 + KPI + 双图 + 九策略表
│   └── _card.html
└── projects/
    ├── index.html
    ├── compare.html
    └── champion-industry-etf.html
```

## 接入生产构建

1. 将 `static/style.css`、`static/charts.js` 复制或 symlink 至站点 `static/`。
2. 在 `base.html` 增加 Inter 字体 link（已写入模板）。
3. 策略详情页在 `</body>` 前或 `head` 加载 `charts.js`；图表外层使用 `.chart-wrap` 并可选挂载 JSON 属性。
4. 无需改 Python 路由；Jinja 块与变量名与上传模板一致，仅 CSS 类与 DOM 包裹层增强。

## 未做（按需求刻意排除）

- 无后端/部署变更  
- 无区块删除或信息架构重组  
- 未做独立暗色主题（当前单一浅色体系，token 便于日后扩展 `[data-theme=dark]`）
