# DESIGN · turnover-softcap

研究池 only；不换冠。

## 面

B45 + spike_ft max5 + E0 + TV25 + SHARPE20-fill；Fri LIVE≥14:30；0.2% RT；L≤1；样本 2020-01-03→2026-10-23。

锚：`LIVE1430-B45-S20-max5` = **131.6% / −18.8% / Calmar 0.70**（针 `05f0f8a4`）。

## 唯一改动

目标 max5 权重算完后，若本周单边换手使 **trailing 52 周单边换手累计** > **T***，则  
`w = w_prev + α(w*−w_prev)`，α 取最大仍满足帽。

| id | T*（单边×/年） |
|----|----------------|
| F0 | 关 |
| TCAP8 | **8**（主档） |
| TCAP6 / TCAP10 | 6 / 10（邻档） |

## H1

TCAP6/8/10 相对 F0 严格尺子全部证伪；2023–26 no-miss。

## 排除

PR#77 成本×λ；PR#55 填席惩罚；LIVE_OPS / champion_mast / strategy_exec。
