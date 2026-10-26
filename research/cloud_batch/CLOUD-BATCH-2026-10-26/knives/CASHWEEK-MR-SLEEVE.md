# CASHWEEK-MR-SLEEVE


# CASHWEEK-MR-SLEEVE

- 编号 / 日期 / 来源：CASHWEEK-MR-SLEEVE / 2026-10-26 / Cloud research
- 性质：**B45 face 广度强制现金周** 轻度均值回归袖（研究 only）

## 准则原文

相对 **B45+S20-LIVE1430 FACE**（`LIVE1430-B45-S20-max5`；同窗 spike_ft max5 + S20 + E0 + TV25；**广度关时 100% 现金**），**仅在 breadth 强制现金周**（`risk_on=0`，θ=0.45）替换闲置现金腿：

| book | 现金周行为 |
|---|---|
| **B45 FACE** | 基线（强制现金周 = 0 收益） |
| **B45-CASHWEEK-MR** | 袖规则：现金袖集合内 **4 周收益最低** 且 **<0** → 等权做多（并列则等权）；否则仍现金；**0.2%RT**；**L≤1** |
| **B45-CASHWEEK-511010** | 邻档：强制现金周恒持 511010（对照「单债」） |
| **B45-CASHWEEK-511260** | 邻档：强制现金周恒持 511260 |

**risk_on 周**：与 FACE 完全一致（忽略袖）。

现金袖集合（研究缓存盘点）：`511010`、`511260`（`bond_daily/`）；货币类 `511880` 等 **不在** week/day/sina 缓存 → **不纳入**。

## 改动点（唯一）

FACE → 仅 **广度强制现金周** 的停放规则；**不**改 slot 空席、**不**恢复 CASH-511010 永久 idle、**不**叠 HYST/B50。

## 假设

强制现金周轻度 MR 债袖可抬 Calmar 或 Δret 盖住 Δ|MDD|，且不系统性弱化 2023–26。

## 证伪

相对 FACE：主袖 Calmar 未 ≥ FACE 且 Δret 未盖住 Δ|MDD|；或 2023–26 系统性更弱；或债史不足无法诚实评估 → **SKIP/BLOCKED**（禁止 drift 回填）。

## 主表

四本书 + Δ vs FACE；产物 `research/cashweek-mr-sleeve/`

## 共用冻结

- Fri ≥14:30；0.2%RT；L≤1；研究池
- **不换冠**；不碰 strategy_exec / LIVE_OPS / 冠军主钉
- 报：**强制现金周数**、**袖激活周数**、**袖命中率**（激活周中组合周收益 >0 占比）

## 交付

四件套（REPORT / summary.json / table.csv / equity_curve.png + nav）。
