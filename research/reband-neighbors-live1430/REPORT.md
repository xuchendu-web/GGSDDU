# REBAND 邻域稳健 · LIVE1430 四件套

- 样本：2020-01-03 → 2026-10-23
- 持仓路径：单一 `LIVE1430-B45-S20` simulate（与 EXTEND-REBASE 同窗）
- 唯一改动：`run_live_tv_reband(reband_tol)` — |Δw|≤tol 不调（成员/开关翻转强制）
- 总判卷：**旁注（边际/不插值）**（不换冠）

## 主表（FACE + 邻档 3/5/10）

| book | reband_tol | ret | maxDD | Calmar | 2023–26 ret | 2023–26 Calmar | skip周 | 判卷 |
|---|---:|---:|---:|---:|---:|---:|---:|---|
| LIVE1430-FACE-B45-S20 | 0% | 131.6% | -18.8% | 0.70 | 94.8% | 1.39 | 0 | FACE |
| LIVE1430-REBAND3 | 3% | 132.4% | -18.8% | 0.70 | 95.4% | 1.40 | 80 | 旁注 |
| LIVE1430-REBAND5 | 5% | 131.0% | -18.8% | 0.70 | 94.3% | 1.38 | 82 | 旁注 |
| LIVE1430-REBAND10 | 10% | 131.0% | -18.8% | 0.70 | 94.3% | 1.38 | 82 | 旁注 |

## 旁注 REBAND7

- LIVE1430-REBAND7: Calmar 0.70; 2023–26 94.3% · **旁注**

## 相对 FACE（Δ）

- **LIVE1430-REBAND3**: Δret +0.8pp; ΔCalmar +0.00
- **LIVE1430-REBAND5**: Δret -0.6pp; ΔCalmar -0.00
- **LIVE1430-REBAND10**: Δret -0.6pp; ΔCalmar -0.00

## 引擎溯源

- PEER E30 原产物：`spike_mom_rank/SPIKE-S20-REBAND5-LIVE1430/`（源码未入库）
- 旋钮口径：`research/research-kb/JUDGING_LOG.md`（|Δw|≤5% 不调；邻档 10%）
- FACE 对齐 EXTEND B45：Δret=0.00pp (FACE tol=0 vs EXTEND B45)
