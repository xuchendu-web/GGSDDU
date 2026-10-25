# CHANGELOG · ETF 分析站视觉打磨

## 2026-10-25 — 设计升级（仅视觉 / 交互，不改数据管道逻辑）

### 意图（Before → After）

| 维度 | 之前 | 之后 |
|------|------|------|
| 整体气质 | 扁平灰底、默认系统样式 | 现代金融研究站：slate 画布、白卡片、轻阴影层次 |
|  typography | 单一 16px、数字与中文混排 | 层级标题 + `tabular-nums` 对齐 KPI/表格/信号 |
| 色彩 | `#2563eb` 点缀、浅黄警示条 | CSS 变量体系：ink / muted / accent 蓝、绿跌红涨保留 |
| 卡片 | 1px 边框 hover 变蓝 | 微抬升 + 阴影过渡；信号卡左侧 accent 条 |
| 图表 | 静态 SVG，无交互 | 悬停十字线 + 浮层 tooltip（策略/基准/回撤）；线宽与网格细化 |
| 导航 | 纯文字链接 | sticky 半透明顶栏、`aria-current`、focus/hover 态 |
| 空态 / 移动 | 较少 | 统一 `.empty`；表格局部横滑；小屏减动效 |

### 变更文件

- `static/style.css` — **重写**设计令牌与组件样式（主交付）
- `static/site.js` — **新增** SVG 图表 tooltip / crosshair
- `templates/base.html` — **新增** 站点壳、导航、页脚、引入 `site.js`
- `templates/index.html` — 语义化区块、空态、`nav_home`
- `templates/market.html` — 空态、`section-intro`
- `templates/_card.html` — **新增** 统一策略/组合卡片 markup
- `templates/strategy.html` — **新增** KPI / 分年表 / rules 容器 class
- `templates/compare.html` — **新增** 9 策略对比表样式钩子
- `templates/projects.html` — **新增**
- `templates/portfolios.html` — **新增**
- `templates/portfolio.html` — **新增**
- `templates/article.html` — **新增**
- `templates/about.html` — **新增** 口径/术语页
- `build.py` — `chart()` **仅输出层**：`chart-panel` + `data-series` JSON（供 tooltip；不改变 metrics/数据源）
- `preview/render_preview.py` — **新增** 无数据路径的本地视觉预览
- 自 uploads 还原：`build.py`、`sources.py`、`DEPLOY.md`、部分模板与样例 markdown

### 未改动（按 Michael 要求）

- `sources.py` 数据路径与策略清单
- 构建页清单、对比表入选逻辑、weekly 过滤规则
- 无生产部署、无 cron / build.sh 数据刷新钩子

### 本地预览

```bash
cd research/etf-site
python3 preview/render_preview.py
python3 -m http.server 8765 --directory preview/dist
# 打开 http://127.0.0.1:8765/index.html ，在净值图上游走测试 tooltip
```
