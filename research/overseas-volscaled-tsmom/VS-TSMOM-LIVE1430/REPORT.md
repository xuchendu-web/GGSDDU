# VS-TSMOM-SLEEVE · REPORT

## 1. 准则原文（可执行摘要）

- 主簿 VS-TSMOM-12；`n_declared=2`，宣布袖：OX, CMD。
- RATES 库存：`SKIP`（earliest honest bar 2024-02-26 after 2019-01-03）。
- σ*=12%，52 周方向 / 60 周波动，L≤1 只缩不放；成本 0.2% 往返。
- 四闸相对同窗 TSMOM-UNSCALED（U）与 EW-BH（H），不与 FACE 绝对值横比。

## 2. 实现要点

- 评窗：2020-01-03 → 2026-10-23；研究周五网格来自 `weekly_panel.parquet`。
- OX 十六只 / CMD 五只已按研究池核对；价格来源示例：research/cloud_batch/CLOUD-BATCH-2026-10-26/data/research_cache/day/159329.json, research/cloud_batch/CLOUD-BATCH-2026-10-26/data/research_cache/day/159509.json, research/cloud_batch/CLOUD-BATCH-2026-10-26/data/research_cache/day/159529.json, research/cloud_batch/CLOUD-BATCH-2026-10-26/data/research_cache/day/159561.json, research/cloud_batch/CLOUD-BATCH-2026-10-26/data/research_cache/day/159687.json, research/cloud_batch/CLOUD-BATCH-2026-10-26/data/research_cache/day/159920.json, research/cloud_batch/CLOUD-BATCH-2026-10-26/data/research_cache/day/159941.json, research/cloud_batch/CLOUD-BATCH-2026-10-26/data/research_cache/day/159980.json…
- 平均 gross exposure（主簿）：0.4635；现金周占比：16.85%。
- 未读入 FACE / LIVE1430 净值。

## 3. 主表

           book      ret     maxDD     CAGR   Calmar   Sharpe      vol    avgTO    annTO  ret_2020_22  maxDD_2020_22  Calmar_2020_22  ret_2023_26  maxDD_2023_26  Calmar_2023_26  avg_gross_exposure  cash_week_pct  erc_fallback_weeks
    VS-TSMOM-12 0.574622 -0.073121 0.069009 0.943764 1.154402 0.052249 0.014551 0.756649     0.057505      -0.050106        0.376749     0.488998      -0.073121        1.509287            0.463488       0.168539                   0
 TSMOM-UNSCALED 0.812436 -0.092392 0.091340 0.988610 1.072091 0.074321 0.017622 0.916322     0.115603      -0.076973        0.484165     0.624625      -0.092392        1.473153            0.636624       0.168539                   0
          EW-BH 0.892903 -0.132749 0.098330 0.740719 0.951581 0.090319 0.003771 0.196085     0.100089      -0.132749        0.244224     0.720682      -0.112421        1.364510            0.831461       0.168539                   0
   VS-TSMOM-ERC 0.578207 -0.065337 0.069366 1.061664 1.176462 0.052001 0.016615 0.863959     0.050448      -0.050515        0.328580     0.502412      -0.065337        1.729216            0.466280       0.168539                  60
       VS-BH-12 0.621455 -0.095082 0.073624 0.774318 1.011458 0.064093 0.005906 0.307118     0.045083      -0.095082        0.156269     0.551509      -0.078440        1.560847            0.605531       0.168539                   0
VS-TSMOM-OXONLY 0.397616 -0.110477 0.050435 0.456525 0.636425 0.072854 0.016087 0.836500    -0.038517      -0.097175       -0.134312     0.453604      -0.110477        0.935567            0.437063       0.250000                   0
  VS-TSMOM-OXHK 0.482227 -0.061090 0.059550 0.974790 1.069567 0.048884 0.016100 0.837201     0.043769      -0.047975        0.300812     0.420072      -0.061090        1.581407            0.443811       0.168539                   0

### 四闸（主簿 vs U/H）

- G1 缩放增量：Sharpe 1.154 vs U 1.072；Calmar 0.944 vs U 0.989 → 未过
- G2 趋势增量：Calmar_P 0.944 vs H 0.741；Δret(P−H)=-0.3183，Δ|MDD|=-0.0596 → 过
- G3 后段 2023–26：ret_P 0.4890 vs min(U,H) 0.6246 → 未过
- G4 缩放绑定：vol_P 0.0522 vs vol_U 0.0743 → 过

邻档四本见上表各行；旁注不升格主簿判词。

## 4. 判词

证伪（不换冠）：VS-TSMOM-12 未过闸 G1,G3。 G1–G4 见上。未与 FACE 绝对值横比。
三袖普遍性 SKIP，利率债面板不够 2019 起评。