# SKIP · 商品 ETF 展期收益（Carry/Roll）周频研究

**判定：SKIP** — 在仓库与本云 Agent 可访问的本地路径中，**不存在**可用于构造横截面 carry/roll 信号的展期、基差或期货期限结构序列；仅有 ETF 复权/1430 价量。在此条件下运行「高 carry 做多 / 低 carry 低配」会退化为价格动量或其它不可审计代理，违反研究红线（不编造数字）。

盘点机器可读证据：`inventory_evidence.json`（由 `scripts/inventory_data.py` 生成）。

---

## 1. 盘点摘要（2026-10-26 UTC）

| 检查项 | 结果 |
|---|---|
| `/cj-data`、`/pyas-data-discovery`、`/mnt/cj-data`、`/data` | **均不存在**（本云环境未挂载 CJ-data / 通联） |
| `main` 分支研究树 | 无 `research/cloud_batch`、无期货曲线缓存 |
| `git grep`（roll_yield / carry_signal / term_structure / basis / 展期 / 基差 / 期限结构）于 `origin/main` 与 PR#56 分支 | **0** 个数据文件命中（仅 pandas `.rolling` 等无关匹配） |
| CLOUD-BATCH 日 K 缓存（PR#56 分支） | 字段仅 `date,o,h,l,c`；**无** near/far、basis、roll_yield |
| 商品袖标的（`research_pool_v2` · `l0=商品` · AUM≥2） | 5 只：518880/518600（现货金）、159980/159985/159981（单品种期货 ETF） |

---

## 2. 为何现有价量不足以代替 Carry

Carry/roll 信号需要 **同一标的** 在信号日的 **期限结构信息**（或基金披露的展期收益），例如：

- 近月/次近月（或前主力/次主力）结算价或隐含年化展期收益；
- 或 ETF 跟踪误差分解中的 **roll yield** 官方序列。

现有数据只能提供各 ETF **自身** 的交易日 OHLC / 周五 14:30 价，无法区分：

- 159980（有色期货指数）与 159985（豆粕）之间的 **相对展期**；
- 黄金现货 ETF 与期货类 ETF 的 **可比 carry**（现货金应使用租赁利率/远期曲线，与期货 roll 不同口径）。

用 12M 收益或 SPIKE 分数代替 carry 会重复 PR#56 已做的动量簿，**不能**回答「展期收益因子是否在商品袖有效」。

---

## 3. 若补齐数据，建议规格（供下一批 CLOUD 任务）

### 3.1 最小可行数据集

| 层级 | 内容 | 频率 | 用途 |
|---|---|---|---|
| A | 商品袖 5 ETF 的 **周频信号日**（周五 ≥14:30 或收盘，与 LIVE1430 一致）对齐表 | 周 | 与 B45/CSMOM 同窗 |
| B | 期货类 3 只（159980/159985/159981）对应 **指数/主力合约链**：近月、次近月价格或年化 roll | 日 → 周取 signal 日 | 横截面 carry 排序 |
| C | 黄金 2 只（518880/518600）：SGE 现货 + 可交易远期/租赁 proxy，或统一标为 **carry NA** 并从排序池剔除 | 日 | 避免现货与期货混排 |
| D | （可选）zsmcp / cjpy 拉取的 **主力连续与次主力** 字段，带交易所与合约乘数元数据 | 日 | 审计与复现 |

建议落盘路径（与现有 kit 一致）：

```text
research/cloud_batch/<BATCH_ID>/data/research_cache/carry_weekly/
  carry_panel.parquet   # columns: week_end, code, carry_ann, source, asof_contract
  carry_meta.json       # 口径说明、缺失规则
```

### 3.2 策略与对照（原计划，未执行）

- **CARRY-WEEKLY**：商品袖内按 `carry_ann` 降序；Top 1–2 等权做多（L≤1），Bottom 置零或 0.5× 低配；周调仓；0.2% RT。
- **对照 1**：`LIVE1430-B45-S20` **商品簿**（PR#56 · `RES-B45-S20-COMMODITY` 同池同窗）。
- **对照 2**：商品袖 **plain CSMOM**（如 12M 或 52W 横截面 z-score，与 dual-mom / skip-month 研究口径一致）。

指标：ret、maxDD、Calmar、Sharpe、avg turnover；四件套图（NAV、回撤、相对 B45 商品簿超额、分年柱）。

### 3.3 与 PR#56 的衔接

PR#56 结论：商品袖 SPIKE-S20 **Calmar 0.23** vs 全池 face **0.70**，动量适配偏弱。本研究旨在检验 **carry 是否优于动量**；在缺数据前不得给出优劣结论。

---

## 4. 红线（仍适用）

- 研究 only；不写 `strategy_exec` / LIVE / champion。
- 不虚构 carry 序列、不用未文档化的 web 抓取冒充聚源/天软口径。
- L≤1；Fri≥14:30；0.2% RT。

---

## 5. 复现盘点

```bash
python3 research/RESEARCH-COMMODITY-CARRY-ROLL-WEEKLY/scripts/inventory_data.py
cat research/RESEARCH-COMMODITY-CARRY-ROLL-WEEKLY/inventory_evidence.json
```
