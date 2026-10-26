# DUAL-TF-ABS-REL-WEEKLY · TiltFolio 式双周期 vs B45 face

- 编号 / 日期：DUAL-TF-ABS-REL-WEEKLY / 2026-10-26
- 性质：**CODE+BACKTEST**（PR#48 双动量证伪后的补位刀；非换冠；**No LIVE**）
- 对照：B45 face = `LIVE1430-B45-S20`（breadth≥45% + spike_ft max5 + E0 + TV25 + SHARPE20，延窗至 2026-10-23）

## 准则原文

在研究 ETF 袖（replace-only，静态 AUM≥2 亿）上**周频**：先用**长周期绝对趋势**（52 周跳 1 周 ROC>0）过滤可投名，再用**短周期相对 ROC**（默认 26 周跳 1）横截面排序取前 N=5 等权；周五≥14:30 研究收盘价、同收成交、0.2%RT、L≤1；无人过绝对门则现金。与 Antonacci 双动量（绝对/相对同一 lookback）区分；与 B45 的 breadth+spike 面层闸区分。交付四件套 + 主表含 Sharpe/换手。不碰 strategy_exec / LIVE_OPS。

## 机制

- PR#48：同 TF 绝对门+相对排序在全池几乎常开，不能替代 breadth 开关，2023–26 踏空。
- 本条：**双 TF** — 绝对门仍用 52 周趋势，相对排序用更短 ROC，意图更快轮动、减抱团滞回；仍保留 B45 face 对照行。
- 预期：若短 TF 相对能抬 2023–26 且 Δret 盖住 Δ|MDD| → 记正；否则延续「XS 选品有效、面层闸不可替代」叙事。

## 证伪

主簿 `DT-A52s1-R26s1-N5` 相对同窗 B45：Δret 未盖住 Δ|MDD|，或 2023–26 相对 B45 系统性落后 → **探索证伪**。邻档 R13/R52、A26、N3/N8 同向不插值。不换冠。

## 冻结

- 成交：周五研究收盘（LIVE1430 周线缓存）/ 同收；0.2%RT；L≤1
- 宇宙：研究池 ≠ 实盘池
- 红线：不写 LIVE；不改冠军主钉
