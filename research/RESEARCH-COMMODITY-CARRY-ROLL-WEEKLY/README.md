# RESEARCH-COMMODITY-CARRY-ROLL-WEEKLY

**状态：SKIP**（无展期/基差/期限结构数据，无法诚实构造 carry/roll 信号）

## 原定假设

在 `research_pool_v2` 商品袖（`l0=商品`）内，**周频**按展期收益（carry）横截面排序：做多高 carry、低配或空仓低 carry；与 **FACE SPIKE-S20 B45**（全池 LIVE1430 面层）及商品袖内 **plain CSMOM** 对照（PR#56 已提示商品袖动量适配偏弱）。

约束：Fri≥14:30、0.2% RT、L≤1；指标 ret / maxDD / Calmar / Sharpe / turnover；研究 only。

## 本批产物

| 文件 | 说明 |
|---|---|
| `SKIP.md` | 跳过原因、所需数据规格、若补齐后的回测骨架 |
| `inventory_evidence.json` | 2026-10-26 云环境可复现盘点结果 |
| `scripts/inventory_data.py` | 重新生成 `inventory_evidence.json` |

未生成四件套（`metrics.csv` / `nav.csv` / `fourpack.png` / `REPORT.md` 主结论表），因缺少 carry 输入序列。
