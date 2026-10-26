# REPORT · turnover-softcap

请拍板：维持面层 B45 + spike_ft max5 + E0 + TV25 + SHARPE20（LIVE≥14:30），仅在目标 max5 权重落地前加 **52 周滚动单边换手软帽 T***（主档 8×/年）；超帽则按持仓 pro-rata 缩仓。无论记正与否都不换冠。

```
唯一改动：在面层 B45 + spike_ft max5 + E0 + TV25 + SHARPE20 上，
算完当周目标 max5 权重后，若本周单边换手会使 trailing 52 周单边换手累计 > T*，
则 w = w_prev + α(w*−w_prev)，α∈[0,1] 取最大仍满足帽。
  T* 主档 8×/年（单边）；邻档仅 6×、10×。四件套 4 本（含 F0 关帽）。
  出场维持 E0。B、TV、席位、填席键、0.2%RT 不离开面。
  非 PR#77 成本×λ 联合；非填席换手惩罚（PR#55）。

H1：TCAP6 / TCAP8 / TCAP10 在严格尺子下相对本次 F0 全部证伪。
  任一记正 → H1 证伪（家族记一笔，不换冠）。
  全部证伪 → H1 成立。
  惰性（n_cap_bind=0 或与 F0 逐周权重相同）→ 记「证伪·惰性」，不能记正。
```

## 换手软帽定义（Choffstein 路径：cost / turnover）

- **单边换手（周）**：再平衡日目标杠杆权重相对上周持仓权重，`TO_1w = ½ Σ|Δw|`（与 kit `run_live_tv` / X-metric 一致）。
- **滚动 52 周帽**：含当周的 trailing 和「过去 51 周 + 本周」单边换手之和 ≤ T*；T* 为年化单边换手倍数（主档 8×/年，邻档 6×、10×）。
- **软帽执行**：先算 FACE 目标 max5 等权 × TV25 杠杆权重 `w*`；若加入本周会使 trailing 和超 `T*`，取最大 `α∈[0,1]` 使 `w = w_prev + α(w*−w_prev)` 仍满足帽（pro-rata 缩交易，非改费率）。
- **成本**：往返 **0.2% RT**；当周成本 `TO_1w × 0.2%`（单边×RT）。**非** PR#77 RT×λ 联合，**非** PR#55 填席惩罚。

## 锚点门

- F0：ret 131.6% / maxDD -18.8% / Calmar 0.70；空仓周 150 / T=348
- anchor_pass：**True**（对照 131.6% / −18.8% / 0.70 @ `05f0f8a4`）
- family_verdict：**H1_HOLD**（不换冠）

## 主表

| id | T* | ret | maxDD | Calmar | 2020-22 | 2023-26 | TO年化(单边) | n_cap_bind | verdict |
|----|-----|-----|-------|--------|---------|---------|--------------|------------|---------|
| F0 | off | 131.6% | -18.8% | 0.70 | 18.9% | 94.8% | 8.11× | 0 | ANCHOR |
| TCAP6 | 6× | 76.2% | -15.0% | 0.58 | 0.7% | 75.0% | 5.18× | 100 | 证伪 |
| TCAP8 | 8× | 106.3% | -18.0% | 0.62 | 16.9% | 76.5% | 6.63× | 68 | 证伪 |
| TCAP10 | 10× | 126.5% | -18.8% | 0.68 | 18.9% | 90.5% | 7.75× | 20 | 证伪 |

## Δ 表（相对 F0）

| id | Δret | Δ|MDD| | covers | 2020-22 | 2023-26 | inert | verdict |
|----|------|--------|--------|---------|---------|-------|---------|
| TCAP6 | -55.4pp | -3.8pp | False | False | False | False | 证伪 |
| TCAP8 | -25.3pp | -0.8pp | False | False | False | False | 证伪 |
| TCAP10 | -5.1pp | +0.0pp | False | True | False | False | 证伪 |

## 帽质量旁注

- 逐周 `cap_weeks_*.csv`：`to_1way`、`trail52_1way`、`alpha`、`cap_bind`。
- hit_rate / win_size 见 `table.csv`，不进 verdict（惰性除外）。

## 证伪段

- **H1_HOLD**：TCAP6/TCAP8/TCAP10 all 证伪。champion_swap=false，不换冠。
- 记正尺子：Δret ≥ Δ|MDD| 且 2020–22、2023–26 均 ≥ F0；`n_cap_bind=0` 惰性不记正。

## 红线

研究池；未改 LIVE/实盘/冠；未重开 PR#77 成本×换手联合、PR#55 填席换手惩罚。

elapsed 6s
