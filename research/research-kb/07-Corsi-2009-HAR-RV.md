---
title: A Simple Approximate Long-Memory Model of Realized Volatility (HAR-RV)
authors: [Fulvio Corsi]
year: 2009
venue: Journal of Financial Econometrics, 7(2), 174–196
tags: [论文笔记, 已实现波动率, HAR-RV, 波动率预测, 长记忆]
source_article: 用户附件（波动率/趋势文献清单）
date_studied: 2026-10-14
---

# Corsi (2009)：HAR-RV——已实现波动率的简易近似长记忆模型

## 结论

HAR-RV（Heterogeneous Autoregressive model of Realized Volatility）用**日、周、月**三个时间尺度上的已实现波动率作为回归元，预测下一期（通常是下一日）已实现波动率。它并不真正引入分整（fractional integration），却能在模拟与实证中近似复制波动率的长记忆、厚尾与多尺度特征，同时保持 OLS 可估、参数少、易扩展。对演讲/回测：它是比「过去 20 日标准差」更有研究含量的**风险预测基准**，可与滚动标准差、EWMA、GARCH/FIGARCH 比较预测误差，再比较对组合效用的影响。关键边界：**预测准确 ≠ 基于该预测的投资策略一定赚钱**（波动率管理能否兑现还取决于风险–收益权衡，见 Moreira/Cederburg 线）。

## 问题与设定

- **问题**：如何在避免 FIGARCH/ARFIMA 估计与解释困难的前提下，捕捉已实现波动率的持久性与多尺度行为？
- **理论动机**：异质市场假说（不同期限交易者）+ 波动率级联；启发自 HARCH（Müller et al.）。
- **数据**：高频 tick → 日度已实现波动率；实证序列包括 USD/CHF、S&P500 期货、国债期货等（原文样本约 1989/1990 起至 2000s）。

## 方法

### 已实现波动率

由高频收益平方和构造日度 $RV_t$，再聚合成周、月：

$$
RV_t^{(w)} = \frac{1}{5}\sum_{i=0}^{4} RV_{t-i}^{(d)}, \quad
RV_t^{(m)} = \frac{1}{22}\sum_{i=0}^{21} RV_{t-i}^{(d)}
$$

（聚合天数以原文定义为准，常取 5 与 22。）

### HAR-RV 核心方程

由三级波动率级联递推压缩后，得到可估形式（原文 Eq. 6 一类）：

$$
RV_{t+1}^{(d)} = c + \beta^{(d)} RV_t^{(d)} + \beta^{(w)} RV_t^{(w)} + \beta^{(m)} RV_t^{(m)} + \omega_{t+1}
$$

也常对 $\log RV$ 或 $\sqrt{RV}$ 建模以保证正值。估计：标准回归；可加入跳跃、杠杆项等扩展（后续文献 HAR-RV-J 等，非本文必须）。

### 评价

- 模拟：自相关、厚尾、多尺度分布是否像真实 RV。
- 实证：样本内拟合与样本外预测相对 ARFIMA、短记忆 AR 等。

## 主要发现

（依据：**WU 镜像 PDF** / JFEC 2009；机制以原文为准，不编造未核表的 RMSE 小数。）

- HAR-RV 结构简单，却能再现金融收益与 RV 的主要经验特征（持久相关、厚尾等）。
- 相对真长记忆模型：避免分数差分算子的估计与样本损耗问题，且更易解释「短/中/长」交易者成分。
- 日、周、月三个系数通常显著，说明多尺度成分共同驱动条件波动。
- 预测用途：作为条件方差 $\widehat{\sigma}_{t+1}^{2}$ 的输入，可接入波动率管理或目标波动策略——但这是**下游应用**，原文主贡献是计量预测。

## 边界与批评

- 「近似」长记忆：在足够长聚合下仍是短记忆级联；极端长程依赖是否足够是开放问题。
- 微观结构噪声、跳跃会污染 RV；实务需预平均、子采样或跳跃稳健 RV。
- **策略层**：把 HAR 预测误差降下来，不自动提高夏普——还需 $\mu$ 是否补偿 $\sigma$（[[01-Moreira-Muir-2017-Volatility-Managed-Portfolios]]）。
- 实现细节（隔夜收益、日历、交易时段）影响跨市场可比性。

## 可学习框架

1. **预测赛马**：RW / 滚动 20 日 std / EWMA / GARCH / HAR-RV —— 统一损失（MSE、QLIKE）。
2. **效用赛马**：同一波动率管理规则，只换 $\widehat{\sigma}_t$ 来源，比较夏普与 CER。
3. **证伪**：若 HAR 预测显著更准但策略效用不升，说明瓶颈在风险溢价侧而非预报侧。
4. **消融**：只留日项 vs 日+周 vs 全日周月，看预测增益来自哪一尺度。

## 与其它笔记的关系

- 为 [[01-Moreira-Muir-2017-Volatility-Managed-Portfolios]]、[[08-Risk-Parity-Vol-Targeting-Clarke-CFA-Bai]] 提供更精细的 $\sigma$ 输入。
- 不替代趋势方向（[[04-Moskowitz-Ooi-Pedersen-2012-Time-Series-Momentum]]）。
- 源文章提醒：预测研究含量高，但与「策略赚钱」要分开讲。

## 出处

- 期刊：*Journal of Financial Econometrics* 7(2) 2009, 174–196, DOI: [10.1093/jjfinec/nbp001](https://doi.org/10.1093/jjfinec/nbp001)（OUP 页面：`academic.oup.com/jfec/article-abstract/7/2/174/856522`）
- PDF 镜像：`https://statmath.wu.ac.at/~hauser/LVs/FinEtricsQF/References/Corsi2009JFinEtrics_LMmodelRealizedVola.pdf`（**已下载全文研读**）
- 早期工作论文标题曾用 “A Simple Long Memory Model of Realized Volatility”
