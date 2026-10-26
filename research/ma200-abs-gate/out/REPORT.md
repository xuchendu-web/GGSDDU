# REPORT · ma200-abs-gate

请拍板：维持面层 B45 + spike_ft max5 + E0 + TV25 + SHARPE20，只在组合 risk_on 上 **AND** 一道沪深300（或 kit 内 510300）周收 > 40 周 SMA 的绝对趋势闸；闸关则 100% 现金桩。无论记正与否都不换冠。

```
唯一改动：在面层 B45 + spike_ft max5 + E0 + TV25 + SHARPE20 上，
把 risk_on 改成 (b ≥ 0.45) AND (C_t > SMA_N(代理))。
  主代理锁 CSI300（000300 否则 510300，同一跑不混）。
  N ∈ {关, 30, 40, 50}。四件套 4 本。
  CSI500 × MA40 只作代理旁注，不进 H1。
  闸关 100% 现金桩。出场维持 E0。B、TV、席位、成本不离开面。

H1：MA30-HS300 / MA40-HS300 / MA50-HS300 在严格尺子下相对本次 F0 全部证伪。
  任一记正 → H1 证伪（家族记一笔，不换冠）。
  全部证伪 → H1 成立。
  主簿 MA40 惰性（n_ma_off_breadth_on = 0，或与 F0 逐周持仓相同）
    → 该本记「证伪·惰性」，不能记正。
```

## 锚点门

- F0：ret 131.6% / maxDD -18.8% / Calmar 0.70；空仓周 150 / T=348
- anchor_pass：**True**（对照 131.6% / −18.8% / 0.70 @ `05f0f8a4`）
- 代理：HS300 `510300`；CSI500 `510500`
- family_verdict：**H1_REJECT**（不换冠）

## 主表

| id | ret | maxDD | Calmar | 2020-22 | 2023-26 | n_ma_off_breadth_on | verdict |
|----|-----|-------|--------|---------|---------|---------------------|---------|
| F0 | 131.6% | -18.8% | 0.70 | 18.9% | 94.8% | 0 | ANCHOR |
| MA40-HS300 | 120.5% | -14.7% | 0.84 | 24.8% | 76.7% | 48 | 证伪 |
| MA30-HS300 | 154.3% | -15.0% | 0.98 | 24.4% | 104.4% | 40 | 记正 |
| MA50-HS300 | 139.2% | -15.5% | 0.88 | 31.7% | 81.6% | 47 | 证伪 |
| MA40-CSI500 | 109.5% | -19.1% | 0.60 | 20.5% | 73.8% | 31 | 旁注-证伪 |

## Δ 表（相对 F0）

| id | Δret | Δ|MDD| | covers | 2020-22 | 2023-26 | inert | verdict |
|----|------|--------|--------|---------|---------|-------|---------|
| MA40-HS300 | -11.1pp | -4.1pp | False | True | False | False | 证伪 |
| MA30-HS300 | +22.6pp | -3.8pp | True | True | True | False | 记正 |
| MA50-HS300 | +7.6pp | -3.3pp | True | True | False | False | 证伪 |
| MA40-CSI500 | -22.1pp | +0.3pp | False | True | False | False | 旁注-证伪 |

## 闸质量旁注

- n_ma_off / n_breadth_off / n_both_off 见 `table.csv`；增量现金周 `n_ma_off_breadth_on` 已入主表。
- hit_rate / win_size 仅披露，不进 verdict（惰性除外）。

## 证伪段

- **H1_REJECT**：MA30/MA40/MA50-HS300 记正: MA30-HS300。champion_swap=false，不换冠。
- 记正尺子：Δret ≥ Δ|MDD| 且两窗不踏空；惰性不记正。

## 红线

研究池；未改 LIVE/实盘；未换冠。未重开 Dual-TF / 通道 overlay。

elapsed 27s
