请拍板：维持面层 B45 + spike_ft max5 + E0 + TV25 + SHARPE20，对**已冻结规则**做 104w/26w 滚动 OOS 过程审计；OOS Calmar 无论塌或不塌都不换冠。

```
唯一动作：在面层 B45 + spike_ft max5 + E0 + TV25 + SHARPE20 上，
  回放一次冻结路径，按 104/26/26 滚动切开。
  训练窗不选型。邻档只改窗长：78/26、104/13、130/26。
  评判只看主档 OOS 拼接的 Calmar / maxDD。

H1：全样本 Calmar 0.70 经不起冻结规则的滚动 OOS；
    主档 OOS 拼接 Calmar 相对 F0 塌过闸。

  主档塌      → H1 成立（过程审计未过）。不换冠。
  主档未塌    → H1 证伪，只记 HOLD_CAVEAT（强势段占 OOS 多数）。不换冠。
  邻档无论塌或不塌，都不改 H1、不升格。
```

## 锚点门

F0 本次 131.6% / -18.8% / Calmar 0.70 （锚 LIVE1430-B45-S20-max5 = 131.6% / −18.8% / 0.70，SHA 05f0f8a4）→ 通过。

## 强势段注

- 已发表分段（仅引用）：2020–22 Calmar **0.37**；2023–26 Calmar **1.39**（PR#28/27 主表）。
- 主档 OOS 拼接日历：**2022-01-10 → 2026-08-14**（周 [104, 338)，234 持有周；leftover 10 周不评分）。
- OOS 时间权重偏后段；OOS Calmar 高于全样本 0.70 **不是**稳健确认。

## 主表（F0 + 四协议 OOS 拼接）

| id | ret | maxDD | Calmar | Sharpe | verdict | 三闸 |
|---|---:|---:|---:|---:|---|---|
| F0 | 131.6% | -18.8% | 0.70 | 0.82 | ANCHOR | G1=False G2=False G3=False
WF-P10426 | 83.8% | -13.8% | 1.03 | 0.92 | HOLD_CAVEAT | G1=False G2=False G3=False
WF-N7826 | 77.3% | -18.8% | 0.63 | 0.78 | HOLD_CAVEAT | G1=False G2=False G3=False
WF-N10413 | 83.8% | -13.8% | 1.03 | 0.92 | HOLD_CAVEAT | G1=False G2=False G3=False
WF-N13026 | 81.5% | -13.8% | 1.14 | 0.98 | HOLD_CAVEAT | G1=False G2=False G3=False

## 主档折表（WF-P10426）

| fold | test 周 | test_end | period_tag | ret | maxDD | Calmar |
|---:|---|---|---|---:|---:|---:|
| 0 | 104–130 | 2022-07-08 | WEAK_2020_22 | 1.2% | -6.2% | 0.40 |
| 1 | 130–156 | 2023-01-13 | MIX | -3.8% | -9.8% | -0.75 |
| 2 | 156–182 | 2023-07-21 | STRONG_2023_26 | 2.0% | -8.7% | 0.47 |
| 3 | 182–208 | 2024-01-26 | STRONG_2023_26 | -1.0% | -1.2% | -1.72 |
| 4 | 208–234 | 2024-08-02 | STRONG_2023_26 | 4.6% | -5.2% | 1.79 |
| 5 | 234–260 | 2025-01-27 | STRONG_2023_26 | 4.1% | -13.8% | 0.62 |
| 6 | 260–286 | 2025-08-01 | STRONG_2023_26 | 7.4% | -8.7% | 1.82 |
| 7 | 286–312 | 2026-01-30 | STRONG_2023_26 | 47.2% | -8.8% | 13.67 |
| 8 | 312–338 | 2026-08-07 | STRONG_2023_26 | 8.5% | -5.3% | 3.27 |

## 三闸（仅主档 OOS 拼接）

- G1 阈：`0.50 × Calmar_FACE` = **0.3495**（本次 F0 Calmar=0.6990）
- G3 阈：`1.50 × |maxDD_FACE|` = **0.2820**（本次 |maxDD|=0.1880）
- 主档 OOS Calmar=1.0265；FLAG_G1/2/3 = False/False/False

## 证伪段

**HOLD_CAVEAT（不换冠）**：主档 OOS 未过塌缩闸；后段已发表 Calmar 1.39 vs 前段 0.37，OOS 偏高不等于稳健确认，禁止 CONFIRMED/换冠。

`family_verdict=HOLD_CAVEAT`；`positive_ids=[]`；`champion_swap=false`。

## 红线

未重开 CLOUD-BATCH / MOM121 / RET / corr-dedup / residual-mom / PR#54 TV-WF；未混用 158.3%/0.94 或 68.1%/0.31 锚；未改 LIVE_OPS / champion_mast。

耗时 1793030110.4s。
