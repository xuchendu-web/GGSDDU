请拍板：在面层 B45 + spike_ft max5 + E0 + TV25、LIVE≥14:30 面上，**填席宇宙仍是 SHARPE20 短名单**，只在短名单内按 Clenow score 次级排序取席。主口径冻结为 **N=90、`score = (e^{β·252} − 1) × R²` 降序（CS90S）**。四本锁定为 `F0/CS90S/CS60S/CS90R`。不替 S20，不设硬闸，不扫 θ/N/k。已持仓不因排序键变差而平。无论记正与否都不换冠。

```
唯一改动：在面层 B45 + spike_ft max5 + E0 + TV25 + SHARPE20 上，
对每周信号日的 S20 短名单按 Clenow 次级排序后取席。
  主簿 CS90S：排序键 (e^{β·252}−1)×R²，N=90，降序，缺失置底。
  邻档：CS60S（同公式，N=60）、CS90R（只按 e^{β·252}−1，N=90，不乘 R²）。
  四本锁定为 F0/CS90S/CS60S/CS90R。
  填席宇宙仍是 SHARPE20 短名单。不替 S20，不设硬闸，不扫 θ/N/k。
  已持仓不因排序键变差而平。出场维持 E0。
  B、TV、席位、成本、时钟不离开面。

H1：CS90S / CS60S / CS90R 在严格尺子下相对本次 F0 全部证伪。
  任一记正 → H1 证伪（家族记一笔，不换冠、不升格）。
  全部证伪 → H1 成立。
  与 F0 逐周持仓集合相同 → 该本记「证伪·惰性」，不能记正。
  n_short_fills > 0 → 该本 BLOCKED（入口丢席，实现偏离），家族 BLOCKED。
```

## 1. 准则原文（摘要）

- 面：B45 + spike_ft max5 + E0 + TV25 + SHARPE20 短名单次级 Clenow 排序；研究池 AUM≥2（324 只）；窗 2020-01-03→2026-10-23（349 周，T=348）。
- 四本：F0 / CS90S（主）/ CS60S / CS90R；第三本只按 slope_ann，不乘 R²。
- 尺子：记正 = Δret≥Δ|MDD| 且两窗 ret ≥ F0 且非惰性。

## 2. 实现要点

- 引擎 fork `05f0f8a4f778`；`band_k=max(2·slots, slots+2)`；缺失置底不删名。
- 锚点门：F0 ret=131.6% maxDD=-18.8% Calmar=0.70 （目标 131.6% / −18.8% / 0.70）→ 通过。 实现门：n_short_fills 全 0、CS90S/CS90R miss 相等 → 通过。
- F0 n_rerank=0；CS90S/CS90R n_miss_clenow=269（须相等）。

## 3. 主表

| id | book | ret | maxDD | Calmar | 2020–22 / 2023–26 ret | n_rerank | n_miss | Jaccard | verdict |
|---|---|---:|---:|---:|---|---:|---:|---:|---|
| F0 | LIVE1430-B45-S20-max5 | 131.6% | -18.8% | 0.70 | 18.9%/94.8% | 0 | 0 | 1.000 | ANCHOR |
| CS90S | LIVE1430-B45-S20-CS90S-max5 | 97.9% | -14.9% | 0.71 | 36.8%/44.7% | 109 | 269 | 0.376 | 证伪 |
| CS60S | LIVE1430-B45-S20-CS60S-max5 | 118.7% | -15.7% | 0.78 | 32.3%/65.3% | 109 | 125 | 0.379 | 证伪 |
| CS90R | LIVE1430-B45-S20-CS90R-max5 | 124.4% | -14.9% | 0.85 | 35.0%/66.2% | 110 | 269 | 0.379 | 证伪 |

## ATTRIBUTION

(a) 机制：仅在 S20 短名单（band_k）内做 Clenow 次级排序；B45/spike_ft/max5/E0/TV25/SHARPE20 宇宙/Fri≥14:30/0.2%RT/AUM≥2 未动；无替席、无硬闸、无 θ/N/k；第三本 CS90R；四本 F0/CS90S/CS60S/CS90R。

(b) 席位重叠（入场 Jaccard vs F0）：CS90S Jaccard=0.376; CS60S Jaccard=0.379; CS90R Jaccard=0.379

(c) 窗 Δ：CS90S Δret=-33.7pp 2020–22=过 2023–26=踏空; CS60S Δret=-12.9pp 2020–22=过 2023–26=踏空; CS90R Δret=-7.2pp 2020–22=过 2023–26=踏空

(d) 换手与空仓周：CS90S TO1w Δ=-0.007 cash周=150 n_empty_slots=34; CS60S TO1w Δ=-0.006 cash周=150 n_empty_slots=33; CS90R TO1w Δ=-0.005 cash周=150 n_empty_slots=34；F0 n_cash_weeks=150。

(e) 名字·年份：见 `entries_diff_by_year.csv`；大赢/大亏段见 `segment_attribution.csv`（惰性格 delta=0）。

ATTRIBUTION 不进 verdict。

## 5. 一句判词

**H1 成立（不换冠）**：三本 Clenow 次级排序相对本次 F0 均为证伪/惰性，无记正。

family_verdict=H1_HOLD；anchor_pass=True；impl_pass=True；attrib_pass=True；耗时 46.5s。
