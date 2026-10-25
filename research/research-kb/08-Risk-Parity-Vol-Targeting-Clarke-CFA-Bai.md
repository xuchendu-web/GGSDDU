---
title: 风险平价、最大分散化、最小方差与波动率目标（主题笔记）
authors: [Roger Clarke, Harindra de Silva, Steven Thorley; Campbell R. Harvey et al.; Zefeng Bai et al.]
year: 2013–2025
venue: JPM 2013; JPM/Man–CFA Digest 2018–2019; FMPM 2025
tags: [论文笔记, 风险平价, 最大分散化, 最小方差, 波动率目标, 再平衡]
source_article: 用户附件（波动率/趋势文献清单）
date_studied: 2026-10-14
---

# 主题：风险平价 / 最大分散化 / 最小方差 / 波动率目标

> 本篇是**主题簇笔记**：标清各文贡献。切勿把 AQR 入口或 CFA 摘要误当成单一论文正式引用。

## 结论

组合层面要把四件事分开：

1. **等权**：忽略风险差异。
2. **风险平价（等风险贡献）**：让各资产对组合风险的贡献相近。
3. **最小方差**：最小化事前组合波动（落在有效前沿最左端）。
4. **最大分散化**：最大化「加权平均波动 / 组合波动」；若预期收益与风险成正比，它接近切点组合。
5. **波动率目标（volatility targeting）**：让**组合整体**（或单资产暴露）的事前波动靠近常数目标——这是**时间维风险锚定**，不是横截面等风险贡献。

Clarke et al. (2013) 给出解析权重直觉：三者都随系统与特质风险下降而降权，但函数形式不同（最小方差更近逆方差，风险平价/最大分散化更近逆波动），且 long-only 下最大分散化与最小方差往往只用少量股票，风险平价更「全覆盖」。Harvey et al.（CFA Digest 2019 摘要所据研究）：波动率目标能稳住风险、削尾，但**夏普改善并非普遍**——股票与信用更明显，债券/外汇/商品上夏普影响可忽略。Bai et al.：给目标波动策略加**再平衡边界**，用优化选边界，在控制风险阈值下降低交易成本。对实操：先问自己在做「横截面风险预算」还是「时间维波动锚定」，再决定要不要叠趋势或因子信号。

---

## A. Clarke, de Silva & Thorley (2013)

### 文献信息

*Risk Parity, Maximum Diversification, and Minimum Variance: An Analytic Perspective*, *Journal of Portfolio Management* 39(3), Spring 2013, 39–53。

### 结论（本分节）

用**解析、long-only**解比较三种风险型组合，避免只依赖特定样本的数值优化黑箱；并在 1968–2012、约 1000 只美股、单因子风险模型下做回测。核心直觉：权重如何随 beta / 特质波动变化，解释为何有的组合高度集中、有的近似「什么都买一点」。

### 问题与设定

- 比较风险平价、最大分散化、最小方差的权重结构与表现。
- 大维证券选择（非仅 2–10 类资产配置）。
- 单指数模型 + OLS 风险估计；附录讨论多因子推广。

### 方法（要点）

- **最小方差**：最小化事前方差；边际风险贡献相等。
- **风险平价 / 等风险贡献**：各资产**总**风险贡献相等；Lee 的解释：权重正比于相对组合 beta 的倒数。
- **最大分散化**（Choueifaty–Coignard）：最大化 $\sum w_i\sigma_i / \sigma_p$；若 $E[r]\propto\sigma$，则靠近最大夏普组合。
- 解析解显示：三者权重均随系统与特质风险上升而下降；最小方差更接近 **1/方差**，另两者更接近 **1/波动**。

### 主要发现

（依据：**Hillsdale 提供的 JPM PDF**；已下载研读。）

- Long-only 最大分散化与最小方差常用投资域中一小部分（文中举例量级：约 100/1000），风险平价倾向纳入集合中更多资产。
- 提供 1968–2012 大盘美股模拟；含大规模风险平价组合的较早系统模拟之一。
- 解析解用于 2013-01 截面权重分布对照，增强可复现性。

### 边界

- 单因子风险模型简化相关结构；真实多因子协方差会改权重。
- 无预期收益输入 → 不回答「该不该买」的定价问题，只回答风险型目标下的权重形状。
- 回测绩效依赖时代与费用，不宜外推为永恒优势。

---

## B. Harvey et al. — *The Impact of Volatility Targeting*（CFA Digest 2019 摘要所据）

### 文献信息

- 研究原文：Campbell R. Harvey, Edward Hoyle, Russell Korgaonkar, Sandy Rattray, Matthew Sargaison, Otto Van Hemert, *The Impact of Volatility Targeting*, *Journal of Portfolio Management* (Fall 2018 左右；Man Group 亦有阐释页)。
- CFA Institute Digest summary：Karl Strauss, CFA，2019-07-18，*The Impact of Volatility Targeting (Digest summary)*。

### 结论（本分节）

波动率目标（低波加杠杆、高波降暴露）能显著降低 **vol-of-vol** 与左右尾极端，对多数资产改善风险形态；但**夏普提升主要见于股票与信用**，以及含较多风险资产的 60/40、风险平价组合；对债券、货币、商品，夏普影响可忽略。机制上，股/信用的杠杆效应（收益与波动负相关）使波动率缩放看起来像叠了一层短趋势。

### 问题与设定（据 Digest + Man/原文 PDF）

- 美股日度约 1927–2017；国债、信用、50+ 期货/远期等多资产。
- 指数衰减权重估计波动；目标如年化 10%；未缩放序列事后标定到相同实现波动以便比较。
- 报告毛/净夏普、vol-of-vol、mean shortfall / exceedance、换手与成本假设。

### 主要发现（可引用）

（依据：CFA Digest 全文抓取 + Duke/Man 公开 PDF/页面；**已读 Harvey PDF 与 Digest**。）

- 股票例：未缩放夏普约 0.40 量级，缩放后上升（原文 Exhibit；精确小数以表为准）。
- 尾部与 vol-of-vol：跨资产普遍改善。
- 股/信用：夏普改善；债/汇/商品：夏普近似不变。
- 对风险平价与平衡组合：回撤与风险统计改善，夏普取决于风险资产占比。

### 边界

- Digest 是二手摘要，正式引用应落到 Harvey et al. 原文。
- 成本假设（股 1bp、债 0.5bp 等）影响净夏普。
- 「夏普不普遍改善」直接警告：不可把波动率目标当成万能 alpha 机器——与 Moreira 股票因子证据、Cederburg 可实施性警告可并列。

---

## C. Bai, Pachamanova, Steblovskaya & Wallbaum（2025）

### 文献信息

*Target volatility strategies: optimal rebalancing boundary for transaction cost minimization*, *Financial Markets and Portfolio Management* (2025/2026 卷期标注以 Springer 页为准), DOI: [10.1007/s11408-025-00486-5](https://doi.org/10.1007/s11408-025-00486-5)。

### 结论（本分节）

标准目标波动策略频繁调仓会吃掉收益。作者引入**再平衡边界（rebalancing boundary）**：仅当实际权重偏离目标超过边界才交易；用约束优化选边界，重叠块 bootstrap 模拟显示：在维持风险阈值可控的前提下，可提高组合收益并降低交易成本。适合回答：「波动率变了，是否必须马上调仓？」

### 方法要点

- 增强型目标波动：风险资产 / 无风险资产配置 + 边界带。
- 优化目标：交易成本与绩效权衡；市场情景与成本水平敏感性分析。

### 主要发现

（依据：**Springer PDF**；已下载研读摘要与引言，细节模拟表以原文为准。）

- 边界带能降换手、提净结果，同时不失去风险控制能力。
- 适宜边界随市场状态与成本大小而变——实操应情景化标定，而非固定一个魔法数字。

### 边界

- 模拟依赖数据块与成本函数；实盘滑点、涨跌停、基金法规约束未完全覆盖。
- 与横截面风险平价仍是不同问题：本文是**时间维**调仓摩擦。

---

## 可学习框架（主题层）

1. **先贴标签**：横截面风险预算 vs 时间维波动目标 vs 方向趋势 —— 三者可叠加但必须消融。
2. **对照表**

| 方法 | 优化什么 | 典型结果 |
|------|----------|----------|
| 等权 | 无 | 高波资产主导风险 |
| 风险平价 | 等总风险贡献 | 压低高波资产权重 |
| 最小方差 | $\min \sigma_p$ | 更集中、偏防御 |
| 最大分散化 | $\max \sum w\sigma / \sigma_p$ | 依赖「收益∝风险」是否成立 |
| 波动率目标 | $\sigma_p(t)\approx \sigma^\star$ | 稳波动、削尾；夏普视资产而定 |

3. **证伪**：若目标波动未降低 vol-of-vol/回撤，或风险平价未改变风险贡献分布，则实施错误或风险模型失效。

## 与其它笔记的关系

- 波动率目标与 [[01-Moreira-Muir-2017-Volatility-Managed-Portfolios]] 同属「高波减仓」，但 Moreira 评价因子 alpha，Harvey 强调跨资产风险形态与夏普异质性。
- 风险缩放消融见 [[06-Kim-Tse-Wald-2016-TSMOM-Volatility-Scaling]]。
- $\sigma$ 估计可换 [[07-Corsi-2009-HAR-RV]]；Bai 讨论何时交易。
- Cederburg（[[03-Cederburg-2020-Performance-Volatility-Managed]]）提醒：再漂亮的风险规则也要 OOS + 成本。

## 出处

- Clarke et al. PDF：`https://www.hillsdaleinv.com/uploads/Risk_Parity,_Maximum_Diversification,_and_Minimum_Variance-_An_Analytic_Perspective.pdf`（**已下载全文**）；SSRN abstract_id=1977577
- CFA Digest：`https://www.cfainstitute.org/en/research/cfa-digest/2019/07/dig-v49-7-2`（**已抓取**）
- Harvey et al. PDF：`https://people.duke.edu/~charvey/Research/Published_Papers/P135_The_impact_of.pdf`（**已下载**）；Man 阐释：`https://www.man.com/insights/the-impact-of-volatility-targeting`
- Bai et al. Springer PDF：DOI 10.1007/s11408-025-00486-5（**已下载**）
