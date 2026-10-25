---
title: Time Series Momentum and Volatility Scaling
authors: [Abby Y. Kim, Yiuman Tse, John K. Wald]
year: 2016
venue: Journal of Financial Markets, 30, 103–124
tags: [论文笔记, 时间序列动量, 波动率缩放, 消融, 风险平价]
source_article: 用户附件（波动率/趋势文献清单）
date_studied: 2026-10-14
---

# Kim, Tse & Wald (2016)：时间序列动量与波动率缩放

## 结论

作者认为：Moskowitz–Ooi–Pedersen (2012) 报告的国际期货 TSMOM 大幅 alpha，**很大程度上来自波动率缩放（类风险平价仓位）**，而非「纯」时间序列动量本身。去掉波动率缩放后，TSMOM 与买入持有的累计收益接近，alpha 差异往往不显著；该相似性在多数板块与合并组合上成立。截面动量相对未缩放 TSMOM 仍可显示更高 alpha，与缩放后 TSMOM 则更接近。对演讲：这是最适合做**消融实验**的文献——组合跑赢究竟因为买对方向、识别趋势，还是高波动时承担更少风险？边界：批评的是「把缩放后的漂亮曲线全部记在趋势名下」；并不否定趋势在部分市场/子期仍有预测力，也不否定缩放本身作为风险管理工具的价值。

## 问题与设定

- **问题**：TSMOM 文献中的异常收益，有多少应归因于动量信号，有多少应归因于波动率缩放？
- **对照对象**：Moskowitz et al. (2012) 国际期货设定。
- **比较策略**：波动率缩放 TSMOM；未缩放 TSMOM；买入持有；截面动量；分板块与总组合。

## 方法

1. 复制 TSMOM：有/无 $\sigma$ 缩放两套并行。
2. 绩效：累计收益、因子模型 alpha、板块拆分。
3. 与买入持有、截面动量对比，识别「缩放开关」打开前后差异是否仍显著。
4. 将波动率缩放解释为风险平价式资产配置机制。

（本笔记对方法细节以**期刊摘要与二手可靠页面**为主；未能稳定下载全文 PDF，见「出处」。）

## 主要发现

（依据：Journal of Financial Markets 摘要 / Ideas RePEc；**非全文逐表**。）

- MOP (2012) 结果「largely driven by volatility-scaling returns (risk parity approach)」。
- 无缩放时：TSMOM 与买入持有累计收益相似，alpha **无显著差别**。
- 多数 sector 与合并期货组合上结论成立。
- 截面动量 alpha 高于未缩放 TSMOM；与缩放 TSMOM 相比则类似。

## 边界与批评

- 摘要级证据不足以复述具体 t 统计或图表数字——引用时宜标「基于公开摘要」。
- 回应可能包括：缩放是趋势策略风险控制的合理部分；「归因」取决于反事实基准选买入持有是否公平。
- 与 Moreira–Muir 对话：两边都说明**波动率缩放能改善风险调整表现**，但一个贴在因子上，一个贴在趋势期货组合上。

## 可学习框架

1. **标准消融四象限**

| | 有趋势信号 | 无趋势信号 |
|--|--|--|
| **有 vol 缩放** | 完整 TSMOM | 纯风险缩放/类 vol target |
| **无 vol 缩放** | 纯方向 | 买入持有 |

2. 跑赢时必须能回答落在哪一格。
3. 证伪「趋势故事」：若「有趋势无缩放」≈「买入持有」，则叙事应改为风险管理。

## 与其它笔记的关系

- 直接消融 [[04-Moskowitz-Ooi-Pedersen-2012-Time-Series-Momentum]]；同样适用于解读 [[05-Hurst-Ooi-Pedersen-2017-Century-Trend-Following]]。
- 与 [[01-Moreira-Muir-2017-Volatility-Managed-Portfolios]]、[[08-Risk-Parity-Vol-Targeting-Clarke-CFA-Bai]] 共同强调：缩放本身是一等公民，不是装饰。

## 出处

- 期刊：*Journal of Financial Markets* 30 (2016) 103–124, DOI: [10.1016/j.finmar.2016.05.003](https://doi.org/10.1016/j.finmar.2016.05.003)
- Ideas/RePEc 摘要：`https://ideas.repec.org/a/eee/finmar/v30y2016icp103-124.html`（**已核对摘要全文**）
- ScienceDirect 入口：`https://www.sciencedirect.com/science/article/abs/pii/S1386418116301379`
- SEC 学术列表页仅有题录，无正文。
- **全文 PDF**：本次检索未获得稳定公开 PDF → 笔记不编造表格内具体数值。
