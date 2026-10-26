---
title: On the Performance of Volatility-Managed Portfolios
authors: [Scott Cederburg, Michael S. O’Doherty, Feifei Wang, Xuemin (Sterling) Yan]
year: 2020
venue: Journal of Financial Economics, 138(1), 95–117
tags: [论文笔记, 波动率管理, 样本外, 可实施性, 反方证据]
source_article: 用户附件（波动率/趋势文献清单）
date_studied: 2026-10-14
---

# Cederburg et al. (2020)：波动率管理组合的真实表现

## 结论

在 **103 个股票策略**的宽样本上：波动率管理组合**并不系统性地**在直接比较中战胜未管理版本；尽管 spanning 回归里常出现与 Moreira–Muir 一致的正 alpha，但回归暗示的「scaled + unscaled 最优混合」**不可实时实施**，合理的样本外组合版本在确定性等价收益（CER）与夏普上**往往差于**简单持有原策略。失败主因是 spanning 关系的**结构不稳定**。对演讲/回测：这是必须保留的反方页——把讨论从「历史夏普涨了多少」推进到「实时投资者能否拿到」。边界：改善集中出现在**动量相关**策略（与 Barroso–Santa-Clara、Daniel–Moskowitz 一致），不能因为动量特例宣称「波动率管理普遍有效」。

## 问题与设定

- **问题**：对真实投资者，波动率管理是否系统有利？正 alpha 能否转化为实时可执行超额？
- **样本**：103 个股票交易策略（远宽于 Moreira–Muir 的因子子集），含市场、动量、盈利、投资、无形资产等多个类别。
- **对比**：直接夏普对比；spanning 回归；多种 OOS「组合策略」（用训练样本估计 scaled/unscaled 权重）。

## 方法

1. **波动率缩放**：类 Moreira–Muir，用滞后已实现方差缩放策略收益。
2. **直接比较**：scaled vs unscaled 的夏普差异及统计显著性。
3. **Spanning**：确认正 alpha 是否广泛存在。
4. **可实施组合**：滚动/扩展窗口估计两策略最优权重，评估 OOS 夏普与 CER；多规格稳健性（窗口、约束、是否加入更多资产等）。
5. **诊断**：检验 spanning 参数是否稳定——不稳定则解释为何 in-sample alpha 无法 OOS 兑现。

## 主要发现

（依据：**Lehigh 作者页 PDF** / JFE 2020；数字来自原文。）

- Moreira–Muir 九个股权因子中，仅约 **5/9** 在直接夏普上利于波动率管理。
- 宽样本 103 策略：波动率管理胜出 **53** 例，原策略胜出 **50** 例——接近抛硬币。
- 仅约 **8** 个策略出现统计显著的夏普改善，且**集中在动量相关**策略。
- Spanning 正 alpha 仍常见，但暗示的组合权重需**事后最优**；OOS 组合在多数情形下 CER/夏普低于原策略（文中基线设计下，实时组合相对原组合在 **72/103** 例降低 CER）。
- 根因：**spanning 回归结构不稳定**，而非单纯「波动率不可预测」。

## 边界与批评

- 本文主要覆盖**股票策略**，未声称否定所有资产类别上的波动率目标（对照 Harvey 等跨资产结果，见 [[08-Risk-Parity-Vol-Targeting-Clarke-CFA-Bai]]）。
- 「不系统优于」≠「从不优于」：动量等子类仍可能受益。
- DeMiguel et al. (2024) 不否认本文对单因子/单策略的批评，而是改换评价对象为条件多因子（[[02-DeMiguel-2024-Multifactor-Volatility-Managed]]）。
- 若演讲只展示 Moreira 累计收益图而不展示本页，属于选择偏差。

## 可学习框架

1. **强制 OOS 协议**：训练窗估权重 → 测试窗交易；禁止全样本最优混合。
2. **三重报告**：直接夏普差、spanning $\alpha$、OOS CER ——三者缺一不可。
3. **结构稳定性检验**：滚动回归 $\alpha,\beta$ 是否漂移。
4. **证伪条件**：若宽样本上显著夏普改善比例接近 50% 且不集中于预登记子类，则「普遍有利」假说失败。
5. **回测清单**（源文章回测启示）：实时信息、滚动估计、样本外、明确交易成本。

## 与其它笔记的关系

- 直接反诘 [[01-Moreira-Muir-2017-Volatility-Managed-Portfolios]]。
- 与 [[02-DeMiguel-2024-Multifactor-Volatility-Managed]] 构成「批评 → 修正」链条。
- 评价纪律同样适用于趋势回测（[[04-Moskowitz-Ooi-Pedersen-2012-Time-Series-Momentum]]、[[06-Kim-Tse-Wald-2016-TSMOM-Volatility-Scaling]]）。

## 出处

- 期刊：*Journal of Financial Economics* 138(1), 2020, DOI: [10.1016/j.jfineco.2020.04.015](https://doi.org/10.1016/j.jfineco.2020.04.015)
- 作者 PDF：`https://www.lehigh.edu/~xuy219/research/COWY.pdf`（**已下载全文研读**）
- SSRN：abstract_id=3357038
- 依据声明：53/50、8、72/103 等来自原文引言/正文；细表见 PDF。
