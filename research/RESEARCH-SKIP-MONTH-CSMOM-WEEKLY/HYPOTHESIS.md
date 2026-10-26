# RESEARCH-SKIP-MONTH-CSMOM-WEEKLY · 研究池 vs B45 face

- 编号 / 日期：RESEARCH-SKIP-MONTH-CSMOM-WEEKLY / 2026-10-26
- 性质：**CODE+BACKTEST**（探索刀；非换冠；**No LIVE**）
- 对照：B45 face = `LIVE1430-B45-S20`（breadth≥45% + spike_ft max5 + E0 + TV25 + SHARPE20，延窗至 2026-10-23）

## 准则原文

在**研究 ETF 池**（replace-only 436，静态 AUM≥2 亿）上按**周频**做 Jegadeesh 式**跳月截面动量（CSMOM）**：

- 排序：月频形成期 **t−12…t−2**（跳过最近完整月 **t−1**）；做多前 **N=5**（邻档 N=3/7）
- 对照：同池同引擎 **无跳月**（形成期 **t−12…t−1**）
- 可选附表：仅当研究广度代理 ≥45% 时 risk-on（非 LIVE breadth 序列，侧表）
- 周五收盘信号、同收成交；**0.2% RT**；**L≤1**；日历与 dual_momentum 研究周线一致（节前周四 bar 映射周五）

交付四件套。不碰 strategy_exec / LIVE_OPS / champion。

## 机制

- 跳月旨在削弱近月反转/微结构噪声，相对无跳月应更高 Calmar 或同等回撤下更高 ret。
- 纯 CSMOM 无 B45 结构闸；若相对 face 盖不住回撤或 2023–26 踏空 → 与 XS-MOM 同类证伪。

## 证伪

1. 主簿 **CSMOM-M12s1-N5** 未稳赢 **CSMOM-M12s0-N5**（Calmar 与 ret 联合）→ **跳月无增量**
2. 和/或相对同窗 B45：Δret 盖不住 Δ|MDD|，或 2023–26 相对 B45 系统性落后 → **探索证伪**。不换冠。

## 冻结

- 成交：周五收盘 / 同收；0.2%RT；L≤1
- 形成期：12 个月锚到月末（周线最后周五）；skip=1 月
- 红线：不换冠；不写 LIVE
