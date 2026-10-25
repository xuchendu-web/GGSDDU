---
title: Time Series Momentum
authors: [Tobias J. Moskowitz, Yao Hua Ooi, Lasse Heje Pedersen]
year: 2012
venue: Journal of Financial Economics, 104(2), 228–250
tags: [论文笔记, 时间序列动量, 趋势跟随, 期货, 跨资产]
source_article: 用户附件（波动率/趋势文献清单）
date_studied: 2026-10-14
---

# Moskowitz, Ooi & Pedersen (2012)：时间序列动量（TSMOM）

## 结论

在 **58** 个高流动性股指、国债、外汇与商品期货/远期合约、逾 25 年样本上，**每个工具自身**过去约 **12 个月**超额收益对未来收益有显著正预测力；该「趋势」效应大约持续一年，更长周期部分反转。这与截面动量（相对同伴强弱）不同，更直接对应单资产行为金融模型的预测。分散化的 TSMOM 组合能产生显著异常收益、对标准资产定价因子暴露低，并在极端市场表现较好；投机者从趋势中获利、对冲者支付。对实操：趋势提供**方向**，波动率缩放决定**承担多少风险**——二者应分开检验（见 [[06-Kim-Tse-Wald-2016-TSMOM-Volatility-Scaling]]）。边界：原策略本身含波动率缩放；若只用股指+黄金，无法充分验证原文强调的跨资产普遍性。

## 问题与设定

- **问题**：单资产自身滞后收益是否预测未来收益？该可预测性在哪些资产、何种期限成立？与截面动量关系如何？
- **资产**：58 个期货与远期——股指、货币、商品、主权债。
- **样本**：约 1985 年起逾 25 年（以原文数据表为准）。
- **区分**：Time-series momentum（绝对趋势）vs Cross-sectional momentum（相对动量）。

## 方法

### 信号与仓位（典型构造）

对每个工具 $s$，看回溯窗口（常取 12 个月）超额收益符号决定多空，并用**事前波动率**缩放仓位，使各市场风险贡献可比，例如：

$$
r_{t,t+1}^{\text{TSMOM},s} \propto \operatorname{sign}\big(r_{t-12,t}^{s}\big)\,\frac{\sigma_{\text{target}}}{\widehat{\sigma}_t^{s}}\, r_{t,t+1}^{s}
$$

（精确常数与组合层目标波动以原文公式为准；AQR/原文强调 ex ante volatility scaling。）

### 分析模块

1. **预测回归**：滞后 1–12 月收益预测未来收益；更长滞后观察反转。
2. **稳健性**：子样本、不同 look-back / holding period。
3. **分解**（Lo–MacKinlay / Lewellen 框架）：把 TSMOM 与截面动量利润拆成自协方差、序列截面相关、均值差异——发现**正自协方差**是主导力量。
4. **组合表现**：跨资产等权/风险加权组合相对标准因子的 alpha；极端市场表现。
5. **持仓结构**：投机者 vs 对冲者（CFTC 类持仓）与趋势收益的关系。

## 主要发现

（依据：**Pedersen 站点 PDF** / JFE 2012；并对照 AQR 研究页摘要。）

- 过去 12 个月超额收益是未来收益的正预测变量；效应约持续一年后**部分反转**（与「先反应不足、后反应过度」叙事一致）。
- **58/58** 合约上 12 月 TSMOM 利润为正（不只是平均为正）。
- 主导机制：证券收益的**正自协方差**；截面交叉滞后与均值差异贡献小。
- 分散化 TSMOM：高异常收益、低因子暴露；极端市况下表现突出。
- 投机者从 TSMOM 获利，对冲者承担对手方。

## 边界与批评

- **波动率缩放纠缠**：原文仓位含风险缩放；Kim et al. (2016) 主张去掉缩放后，TSMOM 与买入持有差距大幅缩小（[[06-Kim-Tse-Wald-2016-TSMOM-Volatility-Scaling]]）。
- **样本与成本**：期货滚动、冲击成本、容量；管理期货业日后拥挤可能改变可获得收益（见 [[05-Hurst-Ooi-Pedersen-2017-Century-Trend-Following]] 对近几十年的讨论）。
- **资产覆盖**：验证「普遍性」需要债与商品，不能只留权益与黄金。
- **非保证未来**：长样本平均收益 ≠ 未来承诺。

## 可学习框架

1. **信号分离实验**：仅 sign(过去收益) vs 仅波动率缩放 vs 两者兼有（Kim 消融）。
2. **期限结构**：1/3/12 月 look-back 等权组合（Hurst 等沿用）。
3. **分解报表**：自协方差 vs 截面项，避免把所有利润叫「动量」。
4. **证伪**：若多资产上滞后 12 月符号无预测力，或利润全部来自缩放项，则「纯趋势溢价」需降级。

## 与其它笔记的关系

- 方向信号奠基；百年扩展见 [[05-Hurst-Ooi-Pedersen-2017-Century-Trend-Following]]。
- 必须与 [[06-Kim-Tse-Wald-2016-TSMOM-Volatility-Scaling]] 对照阅读。
- 波动率缩放部分与 [[01-Moreira-Muir-2017-Volatility-Managed-Portfolios]] 同属「高波减仓」家族，但此处缩放服务趋势组合风险控制。

## 出处

- 期刊：*Journal of Financial Economics* 104(2012) 228–250, DOI: [10.1016/j.jfineco.2011.11.003](https://doi.org/10.1016/j.jfineco.2011.11.003)
- PDF：`https://w4.stern.nyu.edu/facdir/lpederse/papers/TimeSeriesMomentum.pdf`（**已下载全文研读**）
- AQR 页：[Time Series Momentum](https://www.aqr.com/Insights/Research/Journal-Article/Time-Series-Momentum)
- SSRN：abstract_id=2089463
