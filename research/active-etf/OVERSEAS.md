# 海外主动 ETF：结构、披露与费用

研究截止：2026-10-26。只比较产品结构和费用，不构成投资建议，也不预测收益。

美国主动 ETF 的主流是**全透明**：每个交易日开市前公开真实持仓，靠申赎篮子把二级市场价格拉回净值附近。半透明结构存在，但是豁免令下的另一条路，规模不是主叙事。境内 2026 年试点对齐的是全透明，外加比美国更硬的分散约束。ARKK 可以用来说明“全透明主动股票 ETF 长什么样”，不能用来想象境内首批产品的持仓。

## 1. 被动 ETF 与主动 ETF 共用外壳

两边都在交易所上市，一级市场按创设单位申赎，二级市场按市价买卖。SEC 在 2019 年把这套已经运行多年的豁免收成 Rule 6c-11：指数 ETF 和主动 ETF 只要满足同一组运营条件，就不再因为“跟不跟指数”而适用两套规则。规则文本写明，两类产品在注册、创设单位、上市和盘中交易上的运作方式相同，差别在投资目标。[SEC 新闻稿 2019-190](https://www.sec.gov/newsroom/press-releases/2019-190) [Federal Register：Exchange-Traded Funds](https://www.federalregister.gov/documents/2019/10/24/2019-21250/exchange-traded-funds)

6c-11 对网站披露的要求，是后面和境内 PCF 对照的基准：

- 每个营业日、主上市交易所开市前，按统一格式披露全部持仓。
- 披露当日净值、市价、折溢价，以及折溢价的历史幅度和频率。
- 披露过去 30 个日历日的买卖价差中位数。
- 允许定制篮子，但必须有成文政策、指定复核岗位，并留存记录。
- 杠杆、反向 ETF 不能靠这条规则。单位投资信托（UIT）、多份额类别中的 ETF 份额、非透明 ETF 也不能靠它。[SEC 新闻稿 2019-190](https://www.sec.gov/newsroom/press-releases/2019-190)

被动产品的投资目标是跟踪指数。SPY 的说明书写的是：扣除费用前，对应标普 500 的价格和收益率表现。它的法律形式是 UIT，费用表用的是受托人费、指数授权费和营销费，合计估计年费率 0.0945%，不是开放式基金的“管理费”一行。[SPY 说明书](https://fundcompli.rightprospectus.com/documents/SSgA/PRO_SPDRSP500ETF.pdf) 州街页面在 2026-10-23 给出的总费率仍是 0.0945%，净资产约 8079 亿美元；2026-10-26 的基金信息页确认成立日为 1993-01-22。[SPY 基金页](https://www.ssga.com/us/en/intermediary/etfs/state-street-spdr-sp-500-etf-trust-spy)

QQQ 2025-12-19 / 2025-12-22 说明书列示的管理费和基金总运营费率都是 0.18%。[Invesco QQQ 说明书](https://fundcompli.rightprospectus.com/documents/Invesco/P-QQQ-PRO-1.pdf) 本环境没有打开该说明书封面，因此不判断它当前是 UIT 还是开放式基金。

债券被动的参照是 AGG 与 BND，总费率都是 0.03%。AGG 的 2026-06-29 概要说明书写明目标是跟踪美国投资级债券市场指数，管理费 0.03%。[AGG 概要说明书](https://www.ishares.com/us/literature/summary-prospectus/sp-ishares-core-us-aggregate-bond-etf-2-28.pdf) BND 2026-09-30 事实清单：跟踪 Bloomberg U.S. Aggregate Float Adjusted Index，费率 0.03%，ETF 净资产 1614.42 亿美元，抽样复制，债券只数 11434，有效久期 5.7 年。[BND 事实清单](https://fund-docs.vanguard.com/F0928.pdf)

## 2. 全透明主动：ARKK

ARKK 是主动管理的股票 ETF，投资目标是资本长期增长。正常情况下至少把 65% 的资产投在与“颠覆式创新”主题相关的境内外股票。2025-11-30 概要说明书：管理费 0.75%，12b-1 为零，其他费用为零，总运营费率 0.75%。顾问协议下，ARK 承担基金的常规其他费用；收购基金份额费用、税、交易佣金、借款利息和非常费用除外。最近一个会计年度换手率 43%。说明书给出的 SEC 费用例子（假设年收益 5%、费率不变）是 1 万美元持有 1 年约 77 美元。这个数字高于 10000×0.75%=75 美元，因为例子按增长后的资产计费。[ARKK 概要说明书，2025-11-30](https://assets.ark-funds.com/media-12243148-2a3e-4996-9763-260f93905eb9/43f4ba54-a65f-44d9-b18c-c911a1d6e3e4/ARK%20Innovation%20ETF%20Summary%20Prospectus.pdf)

持仓公开在官网上，以 CSV 和 PDF 提供，事实清单明确写着当前持仓要下载这两份文件，印刷表格会过时。[ARK 文件列表](https://www.ark-funds.com/api/fund/document-table/1004) [ARKK 事实清单](https://assets.ark-funds.com/media-12243148-2a3e-4996-9763-260f93905eb9/ef66386b-e5c5-4deb-ad61-aae02f5aee3a/ARKK%20Fact%20Sheet.pdf)

截至该事实清单标注的 2026-03-31：

| 项目 | 数值 |
| --- | --- |
| 成立日 | 2014-10-31 |
| 费率 | 0.75% |
| 规模 | 59.8 亿美元 |
| 持仓只数 | 35–55 |
| 相对标普 500 的 active share | 91% |
| 前十大合计 | 52.4% |

前十大（2026-03-31）：特斯拉 10.8%，CRISPR Therapeutics 6.0%，Tempus AI 5.1%，Shopify 5.0%，Circle 4.7%，Coinbase 4.6%，Robinhood 4.4%，Roku 4.1%，AMD 4.1%，Palantir 3.7%。[ARKK 事实清单](https://assets.ark-funds.com/media-12243148-2a3e-4996-9763-260f93905eb9/ef66386b-e5c5-4deb-ad61-aae02f5aee3a/ARKK%20Fact%20Sheet.pdf)

第三方行情页在 2026-10-22 前后给出另一套持仓和约 59.6 亿美元规模，前十大合计约 49.95%，名称与 3 月 31 日不同。[Robinhood ARKK 页](https://robinhood.com/us/en/stocks/ARKK/) 页面如果要举 ARKK 的例子，只用 2026-03-31 这张官方表，并写明“持仓会变”。不要把两个日期的权重拼在一起，也不要采用未经 ARK 当日 CSV 核对的私募或未上市名称。

和境内规则比，这张 3 月 31 日的快照**没有**越过“前十大不超过净值 60%”和“不少于 30 只”这两条数量线。由此不能推出 ARKK 可以在沪深上市。境内指引还要求换手有序、风格相对基准稳定、股票流动性落在交易所上市股票前 80%，以及管理人资质；ARKK 的投资范围包含境外证券。本环境没有做流动性检验。[上交所指引转载文本](http://www.glfund.com/upload/resources/file/2026/09/03/KM4DE3DKQY30OPPCEQ5XMR3YLA.pdf)

CFRA 在 2026-10-26 列出的美国主动 ETF 规模前 20 名，第一名是 JEPI（约 456 亿美元），其后是 JPST、JEPQ、DYNF、CGDV、JAAA。ARKK 不在这张前 20 里。[CFRA Active ETFs](https://www.cfraresearch.com/solutions/etf-data-and-analytics/us-listed-etfs/active-etfs/) 全透明主动 ETF 里真正做大规模的，是期权增强、超短债、因子轮动和 CLO，不是高集中度的主题股票。

## 3. 半透明：另一套豁免，不是 6c-11

半透明主动 ETF 不每日向全市场公开真实持仓，因此不能依赖 6c-11。ActiveShares 的 SEC 命令写明：基金不在每个营业日开市前公布将用于当日净值计算的证券及数量；改为全天每秒发布经核验的指示性价值（VIIV）。创设赎回通过授权参与商代表（APR）和保密账户，以实物、按比例完成，避免把持仓暴露给市场。该命令同时写明，这些基金**不**依赖 Rule 6c-11，而依赖 ActiveShares 豁免令或实质相同的命令。[SEC 命令 34-88301a](https://www.sec.gov/files/rules/exorders/2020/34-88301a.pdf)

ActiveShares 的发行人说明：公开持仓至少按季度，和共同基金的最低频率相同；管理人可以自愿提高频率。结构目的是降低抢跑和白嫖策略的风险。发行人把这种安排称为 semi-transparent，而不是完全不披露。[ActiveShares FAQ](http://activeshares.com/wp-content/uploads/2021/10/ActiveShares-FAQs.pdf)

行业材料里，已获批路径大致是五条。资产规模以这些旧材料为准会过时，这里只取披露机制：

| 路径 | 盘中向市场公开什么 | 真实持仓何时公开 |
| --- | --- | --- |
| Precidian ActiveShares | 不公开当日持仓；每秒 VIIV；申赎由 APR 在保密账户完成 | 至少每季 |
| Fidelity | 每日跟踪篮子，并披露与真实组合的重合度 | 每月 |
| Blue Tractor Shielded Alpha | 每日公布证券名称，权重被掩盖 | 每季 |
| T. Rowe Price / Natixis（含与 NYSE 相关的代理组合） | 每日代理组合 | 每季 |

[Russell Investments ETF primer](https://russellinvestments.com/content/dam/ri/files/us/en/individual-investor/insights/ETF-primer.pdf) [Citi：Choosing Your Path to the Semi-Transparent ETF Age](https://www.citibank.com/mss/sa/flippingbook/2020/Choosing_Your_Path_to_the_Semi-Transparent_ETF_Age/2/)

境内没有采用上表任何一条。上交所指引第九条要求基于**真实投资组合**制作申购赎回清单，每个交易日开市前在指定渠道披露；第十条的 IOPV 基于这份清单或本所认可的方式计算。[上交所指引转载文本](http://www.glfund.com/upload/resources/file/2026/09/03/KM4DE3DKQY30OPPCEQ5XMR3YLA.pdf) 证券日报在指引发布当日转述业内人士：全球主动 ETF 里全透明是主流，规模占比约 98%，沪深也将采用全透明。[证券日报，2026-06-17](https://finance.sina.com.cn/jjxw/2026-06-17/doc-inictnum6987393.shtml) 98% 是报道中的转述，本环境没有独立复算，页面正文不要写成自行统计的结果。

## 4. 主动债券 ETF：全透明下做成了规模

债券主动 ETF 大多走全透明。持仓透明度对信用和利率交易的伤害，通常小于对集中股票交易的伤害，所以债券管理人更早接受每日披露。下面的费率来自各自说明书或发行人页面，规模取同一张 CFRA 2026-10-26 榜或发行人注明日期的数字，不把不同日期的规模相减。

| 代码 | 角色 | 总费率 | 规模口径 | 投资目标里和被动基准的差别 |
| --- | --- | --- | --- | --- |
| AGG | 被动投资级综合债 | 0.03% | 说明书未在本次摘录规模 | 跟踪美国投资级债券指数 |
| BND | 被动投资级综合债 | 0.03% | 1614.42 亿美元，2026-09-30，ETF 份额 | 跟踪 Bloomberg 综合债浮动调整指数，久期 5.7 年 |
| JPST | 主动超短债 | 0.18% | CFRA：430.6 亿美元，2026-10-26 | 争取当期收入，并维持本金低波动。监管比较基准仍是 Bloomberg 美国综合债指数，和组合本身的超短久期不是一回事 |
| JAAA | 主动 AAA CLO | 0.20% | 325.2 亿美元，2026-10-23 | 监管比较基准写的是 Bloomberg 美国综合债指数；资产是 AAA CLO。2026-09-30 的 30 日 SEC 收益率为 4.52% |
| MINT | 主动增强短久期 | 0.36% | CFRA：189.2 亿美元，2026-10-26 | 在资本保全和每日流动性约束下争取最大当期收入。0.36% 里有 0.01% 利息支出 |
| FBND | 主动综合债 | 0.36% | CFRA：283.7 亿美元，2026-10-26 | 争取高当期收入 |
| BINC | 主动多行业债 | 净 0.40% / 毛 0.52% | 事实清单 164.5 亿美元，2026-09-30；CFRA 同日榜 168.0 亿美元 | 全球高收益、新兴市场和证券化资产。管理费 0.50%，费减免到 2027-06-30。2026-09-30 有效久期 2.58 年，持仓 4174 只 |

来源：[AGG 概要说明书](https://www.ishares.com/us/literature/summary-prospectus/sp-ishares-core-us-aggregate-bond-etf-2-28.pdf)、[BND 事实清单](https://fund-docs.vanguard.com/F0928.pdf)、[JPST 概要说明书，2026-07-01](https://www.sec.gov/Archives/edgar/data/1485894/000119312526277832/d227782d497k.htm)、[JPST 事实清单](https://am.jpmorgan.com/content/dam/jpm-am-aem/americas/us/en/literature/fact-sheet/etfs/FS-JPST.PDF)、[JAAA 产品页](https://www.janushenderson.com/en-us/investor/product/jaaa-aaa-clo-etf/)、[MINT 概要说明书](https://www.sec.gov/Archives/edgar/data/1450011/000119312526095851/d108394d497k.htm)、[FBND 概要说明书，2025-12-30](https://www.sec.gov/Archives/edgar/data/1562565/000156256525000256/filing10396.htm)、[BINC 事实清单，2026-09-30](https://www.blackrock.com/us/individual/literature/fact-sheet/binc-ishares-flexible-income-active-etf-fund-fact-sheet-en-us.pdf)、[BINC 费率说明](https://www.blackrock.com/us/financial-professionals/investments/products/active-fixed-income/binc)、[CFRA Active ETFs](https://www.cfraresearch.com/solutions/etf-data-and-analytics/us-listed-etfs/active-etfs/)。

JAAA 的比较基准是综合债指数，组合却是 AAA CLO。BINC 的久期 2.58 年，BND 是 5.7 年。把 JAAA 或 BINC 的收益率直接减 BND，得到的是资产类别差异，不是“主动管理多赚了多少”。页面上的费用对照必须标资产，不能只标代码。

## 5. 费用对照：同样的 1 万美元，只比说明书费率

下表是费率乘以 1 万个货币单位的一年名义支出，美元产品和人民币产品各用各的货币，不做汇率换算。不含券商佣金、买卖价差、折溢价和换手交易成本。ARKK 另给说明书里的 77 美元例子。

| 产品 | 费率 | 1 万货币单位的一年名义支出 | 这笔费用买到的暴露 |
| --- | ---: | ---: | --- |
| BND / AGG | 0.03% | 3 美元 | 美国投资级综合债 |
| SPY | 0.0945% | 9.45 美元 | 标普 500 |
| QQQ | 0.18% | 18 美元 | 纳斯达克 100 |
| JPST | 0.18% | 18 美元 | 主动超短债 |
| JAAA | 0.20% | 20 美元 | 主动 AAA CLO |
| 华泰柏瑞沪深 300ETF（510300） | 管理费 0.15% + 托管费 0.05% | 20 美元 | 沪深 300。见境内文件 |
| MINT / FBND | 0.36% | 36 美元 | 主动短债 / 主动综合债 |
| BINC 净费率 | 0.40% | 40 美元 | 主动多行业债；毛费率 0.52% 对应 52 美元 |
| ARKK | 0.75% | 75 美元；说明书例子为 77 美元 | 全球颠覆式创新股票 |
| 境内首批主动 ETF | 管理费 1.00%；已点名样本托管费 0.15% | 仅管理费 100 美元；加 0.15% 托管费为 115 美元 | 境内股票主动组合，见 `CHINA-22.md` |
| 境内场外主动股票 / 偏股混合的注册上限 | 管理费不超过 1.2%，托管费不超过 0.2% | 若顶格，120 + 20 = 140 美元 | 上限，不是每只产品的实际费率 |

510300 的费率来自 2024-11-20 公告，自 2024-11-22 起管理费由 0.50% 降至 0.15%，托管费由 0.10% 降至 0.05%。[上交所基金公告 PDF](https://www.sse.com.cn/disclosure/fund/announcement/c/new/2024-11-20/510300_20241120_FOBE.pdf) 场外主动权益的上限来自 2023 年 7 月费率改革：新注册主动股票型和偏股混合型的管理费、托管费分别不超过 1.2%、0.2%。[上证报转述的监管通知](https://news.cnstock.com/news,bwkx-202307-5095630.htm) [人民网对三阶段改革的转述，2026-01-01](http://finance.people.com.cn/n1/2026/0101/c1004-40637249.html)

读这张表时用同一风险预算：

- 境内主动 ETF 的管理费比 510300 高 85 个基点。已点名样本的托管费 0.15% 比 510300 的 0.05% 高 10 个基点，两项合计高 95 个基点。这是它相对这只宽基工具的起点成本，还没算佣金、价差和换手。托管费未点名的产品不进入这 95 个基点。
- 相对场外主动权益的 1.2% / 0.2% 上限，1.00% 的管理费低 20 个基点，已点名的 0.15% 托管费也低于 0.2% 上限。媒体因此说它低于大部分场外主动权益基金。这句话成立的范围是费率，不是收益。[中国基金报转载](https://finance.sina.com.cn/jjxw/2026-10-23/doc-iniweiyr4889627.shtml)
- 美国主动债相对 BND/AGG 的费率差是 15–37 个基点（JPST、JAAA、MINT、FBND、BINC 净费率）。差额小于境内股票主动 ETF 对 510300 的差额，但组合久期、信用和证券化暴露不同，不能横比收益率。
- ARKK 的 0.75% 低于境内主动 ETF 的 1.00% 管理费。两者投资范围、集中度和基准都不同，费率接近不等于产品可替代。

2025-05-07 证监会《推动公募基金高质量发展行动方案》要求新设主动权益基金推行与业绩比较基准挂钩的浮动管理费。[证监会行动方案](https://www.csrc.gov.cn/csrc/c100028/c7555824/content.shtml) 首批境内主动 ETF 的已披露文本被媒体统一写成固定管理费 1.00%。本环境没有逐只核对基金合同里有没有浮动条款，页面按固定 1.00% 展示，并在脚注保留这条未决问题。

## 6. 页面只需要带走的五句话

1. 被动和主动可以共用 ETF 外壳；6c-11 要求全透明主动 ETF 和指数 ETF 一样，在开市前公布真实持仓。
2. 半透明是豁免令路径。境内指引要求真实组合 PCF，不走 ActiveShares、代理篮子或掩盖权重。
3. ARKK 是全透明主题股票 ETF 的公开案例。2026-03-31 的前十大合计 52.4%，只数 35–55。它说明透明和集中可以同时存在，不说明境内首批会做成同样的主题仓。
4. 美国主动 ETF 的规模前列在 2026-10-26 是期权增强、超短债、CLO 和多行业债。主动债的费率差是几十个基点，而且基准经常和真实暴露不一致。
5. 费用比较要写明日期、费率和资产。1 万美元名义支出只用于比较说明书费率。

欧洲 UCITS 主动 ETF 本次没有单独取数。页面不要出现没有出处的欧洲或日本规模。

## Sources

- [SEC 新闻稿 2019-190](https://www.sec.gov/newsroom/press-releases/2019-190)（2019-09）
- [Federal Register：Exchange-Traded Funds](https://www.federalregister.gov/documents/2019/10/24/2019-21250/exchange-traded-funds)（2019-10-24）
- [SEC 命令 34-88301a](https://www.sec.gov/files/rules/exorders/2020/34-88301a.pdf)
- [ActiveShares FAQ](http://activeshares.com/wp-content/uploads/2021/10/ActiveShares-FAQs.pdf)
- [Russell Investments ETF primer](https://russellinvestments.com/content/dam/ri/files/us/en/individual-investor/insights/ETF-primer.pdf)
- [Citi：Choosing Your Path to the Semi-Transparent ETF Age](https://www.citibank.com/mss/sa/flippingbook/2020/Choosing_Your_Path_to_the_Semi-Transparent_ETF_Age/2/)
- [ARKK 概要说明书，2025-11-30](https://assets.ark-funds.com/media-12243148-2a3e-4996-9763-260f93905eb9/43f4ba54-a65f-44d9-b18c-c911a1d6e3e4/ARK%20Innovation%20ETF%20Summary%20Prospectus.pdf)
- [ARKK 事实清单](https://assets.ark-funds.com/media-12243148-2a3e-4996-9763-260f93905eb9/ef66386b-e5c5-4deb-ad61-aae02f5aee3a/ARKK%20Fact%20Sheet.pdf)（业绩截至 2026-03-31）
- [ARK 文件列表](https://www.ark-funds.com/api/fund/document-table/1004)
- [Robinhood ARKK 页](https://robinhood.com/us/en/stocks/ARKK/)（约 2026-10-22，仅作“持仓会变”的旁证）
- [SPY 说明书](https://fundcompli.rightprospectus.com/documents/SSgA/PRO_SPDRSP500ETF.pdf)
- [SPY 基金页](https://www.ssga.com/us/en/intermediary/etfs/state-street-spdr-sp-500-etf-trust-spy)（2026-10-23 / 2026-10-26）
- [Invesco QQQ 说明书](https://fundcompli.rightprospectus.com/documents/Invesco/P-QQQ-PRO-1.pdf)（2025-12-19）
- [AGG 概要说明书](https://www.ishares.com/us/literature/summary-prospectus/sp-ishares-core-us-aggregate-bond-etf-2-28.pdf)（2026-06-29）
- [BND 事实清单](https://fund-docs.vanguard.com/F0928.pdf)（2026-09-30）
- [JPST 概要说明书](https://www.sec.gov/Archives/edgar/data/1485894/000119312526277832/d227782d497k.htm)（2026-07-01）
- [JAAA 产品页](https://www.janushenderson.com/en-us/investor/product/jaaa-aaa-clo-etf/)
- [MINT 概要说明书](https://www.sec.gov/Archives/edgar/data/1450011/000119312526095851/d108394d497k.htm)（2025-10-31，2026-03-06 补充）
- [FBND 概要说明书](https://www.sec.gov/Archives/edgar/data/1562565/000156256525000256/filing10396.htm)（2025-12-30）
- [BINC 事实清单](https://www.blackrock.com/us/individual/literature/fact-sheet/binc-ishares-flexible-income-active-etf-fund-fact-sheet-en-us.pdf)（2026-09-30）
- [BINC 费率说明](https://www.blackrock.com/us/financial-professionals/investments/products/active-fixed-income/binc)
- [CFRA Active ETFs](https://www.cfraresearch.com/solutions/etf-data-and-analytics/us-listed-etfs/active-etfs/)（2026-10-26）
- [证券日报对全透明占比的转述](https://finance.sina.com.cn/jjxw/2026-06-17/doc-inictnum6987393.shtml)（2026-06-17）
- [上交所主动 ETF 指引转载文本](http://www.glfund.com/upload/resources/file/2026/09/03/KM4DE3DKQY30OPPCEQ5XMR3YLA.pdf)
- [510300 降费公告](https://www.sse.com.cn/disclosure/fund/announcement/c/new/2024-11-20/510300_20241120_FOBE.pdf)（2024-11-20）
- [上证报：费率改革通知](https://news.cnstock.com/news,bwkx-202307-5095630.htm)（2023-07）
- [人民网：费率改革三阶段](http://finance.people.com.cn/n1/2026/0101/c1004-40637249.html)（2026-01-01）
- [证监会：推动公募基金高质量发展行动方案](https://www.csrc.gov.cn/csrc/c100028/c7555824/content.shtml)（2025-05-07）
