# SPIKE-S20-ENTRY-PERSIST-K-LIVE1430

- 编号 / 日期 / 来源：SPIKE-S20-ENTRY-PERSIST-K-LIVE1430 / 2026-10-26 / Cloud research batch
- 批次 ID：CLOUD-ENTRY-PERSIST-K
- 性质：**入口持续性**邻档（top-seat 连续周）

## 准则原文

相对 **B45+spike+E0+TV25+S20 max5** 基线，**只改新进规则**：填席前须连续 **K** 个信号周处于 S20 **Top5 席位（top-seat）**；K ∈ {**1, 2, 3**}（K=1 = 基线）。

## 改动点（唯一）

`entry_persist_k`；出场/E0/滞出/席位数不变。

## 假设（H1）

多等 1–2 周 top-seat 可滤掉单周噪声，但 **不会** 在探索尺子下系统性优于 B45+S20（Calmar / 2023–26 不踏空）。

## 证伪

任一 **K∈{2,3}** 相对 B45：**Δret 盖住 Δ|MDD|** 且 **2023–26 累计 ≥ 基线** → 记 H1 证伪（邻档有希望，**仍不升格**）。

## 红线

冻结 **研究 ETF 池**；不写 `strategy_exec` / **LIVE_OPS** / champion_mast / 实盘池。

## 主表

三档 K；产物 `research/cloud_batch/SPIKE-S20-ENTRY-PERSIST-K-LIVE1430/`

## 交付

四件套：准则 → `run.py` → `main_table.md` → 证伪一行（`summary.json` / `REPORT.md`）。
