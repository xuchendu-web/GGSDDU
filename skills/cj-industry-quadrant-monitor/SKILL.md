---
name: cj-industry-quadrant-monitor
description: 申万行业四象限监控系统 — 从基本面（净利润增速/营收增速变化）与技术面（量价齐升信号）两个维度，对全市场申万行业进行打分排序，生成交互式四象限散点图。默认申万二级行业（--sw-level 2），支持--sw-level切换。气泡大小=PETTM因子算出的连续PE分位数。额外输出「基本面较好+技术面转好」行业表格，并生成 HTML、Excel 和 PDF 报告。触发词：行业四象限、行业监控、行业轮动、行业打分、行业象限图、industry quadrant。
---

# 申万行业四象限监控

当前版本：`3.1.0`

## 概述

基于 cjpy 数据，对申万行业进行**基本面 + 技术面 + 估值分位**三维度分析。默认使用**申万二级行业**（`--sw-level 2`），可通过 `--sw-level` 切换。一次运行产出 **HTML 交互报告 + Excel 底稿（多 sheet 覆盖取数/打分/PE 分位/血统）+ PDF 打印版** 四个文件（同名不同扩展名），并支持财务表 / PETTM 分层缓存（复跑大幅提速）。

| 象限 | 基本面 | 技术面 | 标签 | 含义 |
|------|--------|--------|------|------|
| Q1 右上 | 较强 | 较强 | 🔴 相对较强行业 | 同向偏强 |
| Q2 左上 | 弱 | 强 | 🟡 情绪驱动 | 技术面走强但基本面未跟上 |
| Q3 左下 | 较弱 | 较弱 | 🟢 相对较弱行业 | 双弱 |
| Q4 右下 | 较强 | 较弱 | 🔵 价值洼地 | 基本面较好但价格未反应 |

> **散点图文字标签规则**：仅**一级行业**在图上标注每个行业的名称；**二级 / 三级行业**数量多（~130 / ~340 个），标注会严重重叠、反而看不清，因此只画气泡、不标文字（轴标题与四象限角标始终保留）。明细仍可通过 HTML 悬停提示、Excel 底稿查看。

## 数据计算

### 基本面（X轴）
- **TTM 同比**：净利润 TTM 增速 + 营收 TTM 增速。
  从累计利润表还原滚动四季度：`TTM(D) = C(D) + C(去年Dec31) − C(去年同期同季)`，
  再算 `TTM(D) / TTM(D−1年) − 1`。需 5 个报告期齐全（D / D−1y / D−2y / 去年年报 / 前年年报）。
- Winsorize 1/99% → z-score → 行业中位数 → 加权（0.5 / 0.5）

### 技术面（Y轴）
- 三截面（T-40 → T-20 → T）：价格动量 + 换手率变化
- 同样 Winsorize + z-score + 中位数聚合
- 额外计算「技术面变化」，检测动量改善

### 气泡 = PE 估值分位数（PETTM 因子，第二期起）
- 用现成 `PETTM` 日频因子，按窗口（默认近 2 年）采样（周频约 100 点 / 月频约 26 点 / 日频全量），
  行业中位数 PETTM 在其历史中的分位 —— **连续 0–100，不再卡 5 档**。
- 「当前」PE 用最新交易日，不再滞后 7 个月（年报披露时滞）。
- 不再请求 2.6 万行市值表（v2 的致命失败点）。
- 粒度/窗口可调：`--pe-granularity {daily,weekly,monthly}`（默认 weekly）、`--pe-window-years`（默认 2）。

### 标准化与财务口径
- **标准化方法 = 全市场 z-score（与 v2 一致）**：行业排名对缺样本较敏感，但数值与历史报告连续可比。
  若需最强稳定性可改用排名百分位（需重训历史，未启用）。
- **财务 = TTM 同比**：从累计利润表还原滚动四季度再同比，避免累计同比的时点季节性扭曲。
  负基数（TTM 去年同期为负）样本仍用 `safe_pct_change` 的 ±1000% 截断 + Winsorize 硬压，尚未根治（见 L8 / D13）。

### 技术面改善表格
- 筛选：基本面得分 **>= 0** 且 技术面改善（技术面变化 **>= 0**）—— 与象限门槛口径一致。
- 排序：单一确定规则 `排序分 = 技术面相对变化×0.7 + 基本面得分×0.3`。
- 双口径：表格同时给「改善幅度(相对, z 相减)」与「改善幅度(绝对, 原始价格动量中位差 pp)」。

## 使用

### 第一次触发：先建立受控 Python 环境（Agent 必做）

首次调用时，Agent 必须先在技能根目录执行：

```powershell
.\bootstrap.ps1
```

脚本优先复用**系统默认 Python 或 Agent 自带环境**中已完整可用的 Python 3.11/3.12；缺少报告依赖时会通过清华 PyPI 镜像 `https://pypi.tuna.tsinghua.edu.cn/simple` 安装 `requirements.txt`。本技能**不封装 CJPY**：默认用户或 Agent 已有可用的 CJPY 工具/环境。若改用其他数据源，Agent 必须先确认它能提供本技能所需的股票池、行业分类、利润表、交易日历、收盘价、换手率及 PETTM 等兼容字段，再适配 `datasource.py`，不得混用口径。成功后会把绝对解释器路径保存到技能目录 `.iqm-runtime.json`。如需完全隔离环境，再显式执行 `-Isolated` 创建本技能私有 `.venv`。若尚未配置 CJPY token，应由用户在本机交互终端运行（输入不会回显、Agent 不得索要或记录 token）：

```powershell
.\bootstrap.ps1 -ConfigureToken
```

后续触发时，Agent 必须优先加载技能内的 `.iqm-runtime.ps1`，它会设置 `$env:IQM_PYTHON`；同一信息也保存在 `.iqm-runtime.json` 便于程序读取。随后直接使用 `$env:IQM_PYTHON` 调用，**不要重新扫描、猜测或切换解释器**。若路径已失效，才执行 `bootstrap.ps1 -Reconfigure`；若想改用隔离环境，执行 `bootstrap.ps1 -Isolated -Reconfigure`。环境不完整时应明确报告缺失的 CJPY 或报告依赖，不得以“报告已生成”掩盖问题。

### 后续调用：读取已固定的解释器

读取保存路径并运行；仅在迁移/路径失效时才重新配置：

```bash
. .\.iqm-runtime.ps1
& $env:IQM_PYTHON scripts\industry_monitor.py --check-env
.\bootstrap.ps1 -Reconfigure
```

首次 bootstrap 成功即保存绝对路径；保存路径优先级高于系统 PATH 和 Agent 环境，避免不同模型/Agent 再次扫描时选到不同解释器。

> 不要在后续运行中重新使用 `preflight.py` 选解释器；它只用于 bootstrap 的首次选择和诊断。

依赖清单见 `requirements.txt`（cjpy 走内部渠道分发，不在 PyPI）。

### 第二步：自检环境

```bash
<保存的 Python 路径> scripts/industry_monitor.py --check-env
```

打印各依赖版本，并用一次轻量调用验证 token 与网络连通性。

### 第三步：运行

以下 `<PY>` 代表 preflight 给出的解释器路径。

```bash
# 默认二级行业
<PY> scripts/industry_monitor.py

# 一级 / 三级行业
<PY> scripts/industry_monitor.py --sw-level 2
<PY> scripts/industry_monitor.py --sw-level 3

# 跳过 PE 分位（加速）
<PY> scripts/industry_monitor.py --skip-valuation

# 网络不稳时：调小批次、加大重试
<PY> scripts/industry_monitor.py --batch-size 200 --factor-batch-size 500 --max-retry 8
```

全市场（约 5200 只）实测：仅基本面+技术面约 **1 分钟**；加上 PE（PETTM 周频，默认）约 **6–8 分钟**（日频粒度会到 ~40 分钟，建议用默认周频）。

每次运行会基于 `-o` 同名生成四件套（扩展名不同）：

| 文件 | 内容 |
|------|------|
| `<name>.html` | 红黑灰券商研究风交互报告：象限概览 + 四象限散点图 + 改善行业表 + 底部数据血统（Plotly 内嵌、响应式、离线可用） |
| `<name>.xlsx` | Excel 底稿：四象限汇总 / 行业得分 / 改善行业 / PE 分位明细 / 数据血统 多 sheet |
| `<name>.pdf` | 打印版：标题 + 血统 + 汇总 + 改善表 + 象限散点（reportlab 原生绘制） |
| `<name>.run.log` | 完整运行日志（调试用，含缓存命中/未命中统计） |
| `<name>.manifest.json` | 本次 as-of、版本、提交文件的机器可读清单 |

### 参数

| 参数 | 说明 | 默认 |
|------|------|------|
| `--sw-level` | 行业级别 1/2/3 | 2（二级） |
| `--lookback` / `-l` | 技术回看交易日，范围 1~250 | 20 |
| `--min-stocks` | 行业最少成分股 | 3 |
| `--skip-valuation` | 跳过 PE 分位 | 否 |
| `--pe-granularity` | PE 历史采样粒度 daily/weekly/monthly | weekly（约100点/2年，~6分钟） |
| `--pe-window-years` | PE 分位回溯年数 | 2 |
| `--pe-batch-size` | PETTM 因子每批股票数 | 100 |
| `--fundamental-quarter` | 指定财报期，`YYYYMMDD` 或 `YYYYQn` | 自动选覆盖率最高的报告期 |
| `--batch-size` | 财务表每批股票数 | 300 |
| `--factor-batch-size` | 因子接口每批股票数 | 800 |
| `--max-retry` | 单批最大重试次数（指数退避） | 5 |
| `--min-coverage` | 关键环节最低覆盖率，不达标即失败退出 | 0.95 |
| `--allow-partial` | 覆盖率不达标仍出报告（报告标红） | 否 |
| `--history-start` | 财务表起始日期 `YYYYMMDD` | 7 年前 |
| `-o` / `--output` | 输出路径（自动生成 `.html`/`.xlsx`/`.pdf`/`.run.log` 四件套） | 自动按级别与日期命名 |
| `--no-cache` | 禁用缓存，强制重新取数 | 否（默认开） |
| `-q` / `--quiet` | 只输出警告与错误 | 否 |
| `-v` / `--verbose` | 输出调试细节 | 否 |
| `--cache-dir` | 自定义缓存目录（默认 `%LOCALAPPDATA%\cjpy-skills\cache\`） | 自动 |
| `--check-env` | 只做环境自检后退出 | — |

### 退出码

| 码 | 含义 |
|----|------|
| 0 | 成功 |
| 2 | 依赖缺失 / 环境不可用 |
| 3 | 参数非法 |
| 4 | 数据获取失败或覆盖率不达标 |
| 5 | 计算结果为空 |
| 6 | 输出路径不可写 |

**非 0 退出时不会提交报告**——HTML/XLSX/PDF 会先写到临时目录并逐一 reopen 验证，三者全部成功才原子提交。全市场截面 z-score 对缺样本极其敏感，
实测缺 58% 样本会让 2/29 个行业象限翻转、排名最大跳动 14 位，而报告外观完全正常。
宁可不出，也不出一份看起来没问题的错报告。

### 缓存

复跑/调参/切级别时，最耗时的两部分数据会被缓存，**不再重取**：

- **财务表（合并利润表）**：按 `(代码集, 起始日期)` 缓存。同一季度内、同一股票池复跑直接命中，省掉约 7 年利润表的拉取。
- **PETTM 估值分位**：按 `(代码集, 采样粒度, 窗口年数, 采样日期序列)` 缓存。你问的「PE_TTM 能不能缓存、下次少取点、快点」就在这里——复跑时 PETTM 历史序列不再重取（周频默认约 52 次调用 → 0 次）。

缓存目录：优先 `%LOCALAPPDATA%\cjpy-skills\cache\`（标准做法），不可写时回退到技能目录 `.cache\`。

**正确性保证**：缓存 key 含完整代码集与日期序列，任何一只股票或任一采样日变化都会使 key 失效、自动重取，不会出现「拿到旧数据却以为是新的」。

```bash
# 正常跑（默认开缓存，首跑落盘、复跑命中）
<PY> scripts/industry_monitor.py -o report

# 强制重取（忽略缓存，等价于清空后重跑）
<PY> scripts/industry_monitor.py -o report --no-cache

# 把缓存放到自定义目录（如团队共享盘 / 多机协同）
<PY> scripts/industry_monitor.py -o report --cache-dir /path/to/cache
```

> 实测：首跑（缓存未命中）约 6–8 分钟；复跑（财务表 + PETTM 全命中）PE 取数 0 次、财务取数 0 次，总耗时降到分钟级（仅剩股票池/行业/技术面/PE 当日因子的新鲜取数）。

### 报告数据血统条

数据血统条按当前版式保留在 **HTML 报告最底部**：真实财报期与同比基准期、技术面三个截面交易日、股票池规模、
各环节覆盖率、失败批次数、PE 口径与基准日、耗时。任一环节降级时整条变红。
**看结论前先看这一条。**

## 常见问题

| 现象 | 原因与处理 |
|------|-----------|
| `ModuleNotFoundError: cjpy` | 用错解释器，跑 `preflight.py` 重新确定 |
| 退出码 4，提示覆盖率不达标 | 服务端限流，通常是暂时的。重试，或 `--batch-size 200 --max-retry 8` |
| 退出码 6 | 输出 HTML 正被浏览器/Excel 占用，关闭或换 `-o` |
| 气泡大小全一样 | PE 分位不可用，血统条里会写明原因 |
| 终端中文/emoji 乱码 | 脚本已自动降级处理，不影响报告；如需正常显示执行 `chcp 65001` |
