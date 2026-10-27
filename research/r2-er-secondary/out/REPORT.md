请拍板：在面层 B45 + spike_ft max5 + E0 + TV25、LIVE≥14:30 面上，**填席宇宙仍是 SHARPE20 短名单**，只在短名单内按路径质量次级排序取席。主口径冻结为 **OLS R²(N=90) 降序（R290S）**。邻档只留 **ER(N=20) 降序（ER20S）** 与短名单内 **0.5·z(R²)+0.5·z(ER)（COMBOS）**。不设硬闸、不替 S20、不扫 θ。已持仓不因排序键变差而平。无论记正与否都不换冠。

```
唯一改动：在面层 B45 + spike_ft max5 + E0 + TV25 + SHARPE20 上，
对每周信号日的 S20 短名单做路径质量次级排序后取席。
  主簿 R290S：排序键 OLS R²(N=90)，降序，缺失置底。
  邻档：ER20S（ER(N=20) 降序）、COMBOS（带内 0.5·z(R²)+0.5·z(ER)）。共 4 本（含 F0）。
  填席宇宙仍是 SHARPE20 短名单。不设 R²/ER/accel 硬闸，不替 S20，不扫 θ。
  已持仓不因排序键变差而平。出场维持 E0。
  B、TV、席位、成本、时钟不离开面。

H1：R290S / ER20S / COMBOS 在严格尺子下相对本次 F0 全部证伪。
  任一记正 → H1 证伪（家族记一笔，不换冠、不升格）。
  全部证伪 → H1 成立。
  与 F0 逐周持仓集合相同 → 该本记「证伪·惰性」，不能记正。
  n_short_fills > 0 → 该本 BLOCKED（入口丢席，实现偏离），家族 BLOCKED。
```

## 准则原文

S20 短名单 `band_k=max(2·slots, slots+2)` 内按 R²(N=90) / ER(N=20) / COMBOS 次级排序；无硬闸、不替 S20、无 θ。面层 B45 + spike_ft max5 + E0 + TV25 + Fri≥14:30 + 0.2% RT + L≤1 + AUM≥2 亿。

## 实现要点

针 `05f0f8a4f778fde886f3e7b2976646ff4b7d777b`；`n_short_fills` 全为 0 则 `impl_pass=true`。F0 锚 131.6% / -18.8% / Calmar 0.70。

## 主表

| id | ret | maxDD | Calmar | w2020-22 | w2023-26 | n_rerank | Jaccard | verdict |
|---|---:|---:|---:|---:|---:|---:|---:|---|
| F0 | 131.6% | -18.8% | 0.70 | 18.9% | 94.8% | 0 | 1.000 | ANCHOR |
| R290S | 132.1% | -15.6% | 0.84 | 30.8% | 77.5% | 105 | 0.399 | 证伪 |
| ER20S | 127.1% | -18.4% | 0.70 | 32.1% | 71.9% | 30 | 0.741 | 证伪 |
| COMBOS | 131.0% | -15.1% | 0.87 | 34.3% | 72.0% | 80 | 0.487 | 证伪 |

## ATTRIBUTION

(a) 机制：只在 S20 短名单内做了路径质量次级排序；未动 B45 / spike_ft / max5 / E0 / TV25 / SHARPE20 宇宙 / Fri≥14:30 / 0.2%RT / AUM≥2；无硬闸、无替换 S20、无 θ；第三本 COMBOS。

(b) 席位重叠：
- **R290S** vs F0 Jaccard = 0.399
- **ER20S** vs F0 Jaccard = 0.741
- **COMBOS** vs F0 Jaccard = 0.487

(c) 两窗 Δ：
- **R290S**：Δret 2020–22 = +11.9pp (窗过)；2023–26 = -17.4pp (踏空)
- **ER20S**：Δret 2020–22 = +13.2pp (窗过)；2023–26 = -22.9pp (踏空)
- **COMBOS**：Δret 2020–22 = +15.5pp (窗过)；2023–26 = -22.9pp (踏空)

(d) 换手与空仓周：
- **R290S**：换手 0.1518 vs F0 0.1559；空仓周 150 vs F0 150；n_empty_slots=29
- **ER20S**：换手 0.1535 vs F0 0.1559；空仓周 150 vs F0 150；n_empty_slots=35
- **COMBOS**：换手 0.1540 vs F0 0.1559；空仓周 150 vs F0 150；n_empty_slots=35

(e) 名字·年份与大赢/大亏段：
- **R290S**：有 diff 年份 [2020, 2021, 2022, 2023, 2024, 2025, 2026]；详见 entries_diff_by_year.csv / segment_attribution.csv。
- **ER20S**：有 diff 年份 [2020, 2021, 2022, 2023, 2024, 2025, 2026]；详见 entries_diff_by_year.csv / segment_attribution.csv。
- **COMBOS**：有 diff 年份 [2020, 2021, 2022, 2023, 2024, 2025, 2026]；详见 entries_diff_by_year.csv / segment_attribution.csv。

ATTRIBUTION 不进 verdict。

## 一句判词

锚 `anchor_pass=True`；实现 `impl_pass=True`；ATTRIBUTION `attrib_pass=True`。
**H1 成立：S20 短名单上的 R²/ER 次级排序无记正。** `family_verdict=H1_HOLD`。不换冠。
