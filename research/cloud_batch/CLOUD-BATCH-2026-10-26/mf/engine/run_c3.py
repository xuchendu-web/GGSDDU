#!/usr/bin/env python3
"""MF-C3：固定60/40，权益=周频T-MA60，债腿纯511260（相对B1等权单改）。"""
import os, sys, pickle, numpy as np, pandas as pd
sys.path.insert(0, "/workspace/etf-multifreq/engine")
sys.path.insert(0, "/workspace/etf-trend/engine")
import mf_common as mf
import mom_engine as e
import trend as t
from pathlib import Path

ID = "MF-C3"
OUT = f"{mf.OUT_ROOT}/{ID}"
Path(OUT).mkdir(parents=True, exist_ok=True)

HYPO = """## 0. 假设与证伪（开跑前写死）
- **假设**：固定 60/40（T-MA60 权益 60% + 债/货币腿 40%）债腿由 B1 等权（511010+511260）改为纯 **511260**，可抬 Calmar 且不破坏压舱回撤。
- **证伪**：Calmar 劣于 60/40(B1)，或 MDD 明显更深（>1pp），或 2021/2022 压舱年明显变差。
- **红线**：不叠冠军强栈；月末再平衡；权益腿信号仍为周频 T-MA60。
"""

D = mf.data()
P, aw, MF = D["P"], D["aw"], mf.MF
B1 = ["511010", "511260"]
BOND = "511260"
BOND_ALT = "511010"
days = P.index[(P.index >= mf.START) & (P.index <= mf.END)]
keep = set(aw)

# 纯周频 T-MA60
w_tm, st_tm = t.weights(t.s_ma(60), keep=keep)
r_tm, to_tm, ex_tm = t.run(w_tm)
print("纯T-MA60", {k: round(float(v), 4) for k, v in mf.stats(r_tm).items()}, flush=True)

# 展开周频权重到日
fri_sorted = sorted(w_tm.keys())
daily_tm = {}
for k, fri_d in enumerate(fri_sorted):
    tw = w_tm[fri_d]
    if k + 1 < len(fri_sorted):
        nxt = fri_sorted[k + 1]
        seg = days[(days >= fri_d) & (days < nxt)]
    else:
        seg = days[days >= fri_d]
    for dd in seg:
        daily_tm[dd] = dict(tw)

# 月末
month_ends = []
for _, g in pd.Series(days, index=days).groupby(days.to_period("M")):
    month_ends.append(g.iloc[-1])
month_ends = [d for d in month_ends if d >= pd.Timestamp(mf.START)]

def build_6040(bond_codes, bond_w_each=None):
    """固定 0.6*T-MA60 + 0.4 债腿。bond_codes 列表；若 bond_w_each 为 None 则等权分 0.4。
    再平衡：月末定目标；月内按日持有（每日权重键仍写出，run_daily 日日调仓——
    为贴近「月末再平衡」，仅在月末与月初段切换目标，月内保持上月末权重结构但随 T-MA60 周信号更新权益袖套）。
    与 C2 固定60/40 一致：每日用当日 T-MA60 袖套×0.6 + 债腿。
    """
    if bond_w_each is None:
        bond_w_each = 0.4 / len(bond_codes)
    W = {}
    for dd in days:
        tw = daily_tm.get(dd, {MF: 1.0})
        ww = {c: v * 0.6 for c, v in tw.items()}
        for c in bond_codes:
            ww[c] = ww.get(c, 0) + bond_w_each
        ww = {c: v for c, v in ww.items() if v > 1e-8}
        W[dd] = ww
    return W

def build_6040_month_reb(bond_codes, bond_w_each=None):
    """严格月末再平衡版：月末锁定「权益袖套快照×0.6 + 债」，月内冻结权重（不跟周信号变）。
    准则：月末再平衡；月内按日持有。同时 C2 对照用的是每日跟 T-MA60。
    主版采用与 C2 固定60/40 相同的「日度跟袖套」以便公平对照；另报月末冻结邻注。
    """
    if bond_w_each is None:
        bond_w_each = 0.4 / len(bond_codes)
    W = {}
    for k, me in enumerate(month_ends):
        tw = daily_tm.get(me, {MF: 1.0})
        snap = {c: v * 0.6 for c, v in tw.items()}
        for c in bond_codes:
            snap[c] = snap.get(c, 0) + bond_w_each
        snap = {c: v for c, v in snap.items() if v > 1e-8}
        nxt = month_ends[k + 1] if k + 1 < len(month_ends) else days[-1]
        if k + 1 < len(month_ends):
            seg = days[(days >= me) & (days < nxt)]
        else:
            seg = days[days >= me]
        for dd in seg:
            W[dd] = dict(snap)
    return W

# 主版：与 C2 固定60/40 同构建（日度跟 T-MA60 袖套），债腿纯 511260
W_c3 = build_6040([BOND], bond_w_each=0.4)
r_c3, to_c3, ex_c3 = mf.run_daily(W_c3, fill="close")
print("C3 纯511260", {k: round(float(v), 4) for k, v in mf.stats(r_c3).items()},
      f"to={to_c3:.2f} ex={ex_c3:.3f}", flush=True)

# 对照：固定60/40(B1)
W_b1 = build_6040(B1)  # 各 0.2
r_b1leg, to_b1leg, ex_b1leg = mf.run_daily(W_b1, fill="close")
print("60/40(B1)", {k: round(float(v), 4) for k, v in mf.stats(r_b1leg).items()}, flush=True)

# 邻档旁注：债腿纯 511010
W_010 = build_6040([BOND_ALT], bond_w_each=0.4)
r_010, to_010, ex_010 = mf.run_daily(W_010, fill="close")
print("邻档 纯511010", {k: round(float(v), 4) for k, v in mf.stats(r_010).items()}, flush=True)

# 月末冻结版（旁注）
W_me = build_6040_month_reb([BOND], bond_w_each=0.4)
r_me, to_me, ex_me = mf.run_daily(W_me, fill="close")
print("旁注 月末冻结", {k: round(float(v), 4) for k, v in mf.stats(r_me).items()},
      f"to={to_me:.2f}", flush=True)

# 纯货币 / 纯 B1 / 纯 T-MA60 已有
W_mf = {dd: {MF: 1.0} for dd in days}
r_mf, to_mf, ex_mf = mf.run_daily(W_mf, fill="close")
W_pure_b1 = {dd: {c: 0.5 for c in B1} for dd in days}
r_pb1, to_pb1, ex_pb1 = mf.run_daily(W_pure_b1, fill="close")
W_pure_260 = {dd: {BOND: 1.0} for dd in days}
r_p260, to_p260, ex_p260 = mf.run_daily(W_pure_260, fill="close")

ch = mf.champ()
books = {
    "MF-C3 60/40(T-MA60:纯511260)": (r_c3, to_c3, ex_c3),
    "邻档 债腿纯511010": (r_010, to_010, ex_010),
    "旁注 月末冻结权重": (r_me, to_me, ex_me),
    "固定60/40(T-MA60:B1)": (r_b1leg, to_b1leg, ex_b1leg),
    "纯周频T-MA60(同A宽基)": (r_tm, to_tm, ex_tm),
    "纯B1等权": (r_pb1, to_pb1, ex_pb1),
    "纯511260": (r_p260, to_p260, ex_p260),
    "纯货币511880": (r_mf, to_mf, ex_mf),
    "冠军同引擎(研究副本)": ch,
}

sc = mf.stats(r_c3); s60 = mf.stats(r_b1leg); st_ = mf.stats(r_tm)
dd_gap = sc["maxDD"] - s60["maxDD"]  # negative if C3 deeper (worse); >1pp deeper means dd_gap < -0.01

def year_ret(r, y):
    s = r[r.index.year == y]
    return (1 + s).prod() - 1 if len(s) > 1 else np.nan

y21_c, y21_b = year_ret(r_c3, 2021), year_ret(r_b1leg, 2021)
y22_c, y22_b = year_ret(r_c3, 2022), year_ret(r_b1leg, 2022)

# 证伪
f1 = sc["Calmar"] < s60["Calmar"]
f2 = dd_gap < -0.01  # MDD 明显更深 >1pp
# 2021/2022 压舱年明显变差：收益低超 2pp 或该年 DD 更深超 2pp
def year_mdd(r, y):
    s = r[r.index.year == y]
    if len(s) < 2:
        return np.nan
    q = (1 + s).cumprod()
    return float((q / q.cummax() - 1).min())

ym21_c, ym21_b = year_mdd(r_c3, 2021), year_mdd(r_b1leg, 2021)
ym22_c, ym22_b = year_mdd(r_c3, 2022), year_mdd(r_b1leg, 2022)
f3 = ((y21_c < y21_b - 0.02) or (ym21_c < ym21_b - 0.02) or
      (y22_c < y22_b - 0.02) or (ym22_c < ym22_b - 0.02))

falsified = f1 or f2 or f3
reasons = []
if f1:
    reasons.append(f"Calmar {sc['Calmar']:.2f} < 60/40(B1) {s60['Calmar']:.2f}")
if f2:
    reasons.append(f"MDD 更深 {-dd_gap*100:.1f}pp（C3 {sc['maxDD']:.1%} vs B1腿 {s60['maxDD']:.1%}）")
if f3:
    reasons.append(
        f"压舱年变差：2021 ret {y21_c:+.1%} vs {y21_b:+.1%} / DD {ym21_c:.1%} vs {ym21_b:.1%}；"
        f"2022 ret {y22_c:+.1%} vs {y22_b:+.1%} / DD {ym22_c:.1%} vs {ym22_b:.1%}"
    )
verdict = "**证伪**" if falsified else "**未证伪**"
fal = ("；".join(reasons) if reasons else
       f"Calmar {sc['Calmar']:.2f}≥{s60['Calmar']:.2f}；MDD差 {dd_gap*100:+.1f}pp；"
       f"2021/22 未明显变差"
       ) + ("。证伪成立。" if falsified else "。未触发证伪闸。")

attr_md = f"""## 归因 · MF-C3 固定60/40 债腿纯511260
_样本 {r_c3.index[0].date()}→{r_c3.index[-1].date()}。相对固定60/40(B1) 只改债腿载体。_

### 择时 / 选品 / 频率 / 成本
- **择时**：权益袖套=周频 T-MA60（同 A宽基）；仓位固定 60/40，无ρ门控、无 RP
- **选品**：权益=T-MA60 多头；债腿=**纯511260**（对照 B1=511010+511260 等权）
- **频率**：月度目标结构；实现上与 C2 固定60/40 一致——日度跟随周频袖套（旁注月末冻结）
- **成本**：换手 {to_c3:.2f}x vs 60/40(B1) {to_b1leg:.2f}x

### vs 固定60/40(B1)
- ret {sc['ret']:.1%} vs {s60['ret']:.1%}；DD {sc['maxDD']:.1%} vs {s60['maxDD']:.1%}（差 {dd_gap*100:+.1f}pp）
- Calmar {sc['Calmar']:.2f} vs {s60['Calmar']:.2f}（Δ {sc['Calmar']-s60['Calmar']:+.2f}）
- 2021：{y21_c:+.1%}/{ym21_c:.1%} vs {y21_b:+.1%}/{ym21_b:.1%}
- 2022：{y22_c:+.1%}/{ym22_c:.1%} vs {y22_b:+.1%}/{ym22_b:.1%}
- vs 纯 T-MA60：Calmar {sc['Calmar']:.2f} vs {st_['Calmar']:.2f}；MDD浅 {sc['maxDD']-st_['maxDD']:+.1%}
"""

main = "MF-C3 60/40(T-MA60:纯511260)"
M = pd.DataFrame([mf.row(k, *v[:3]) for k, v in books.items()])

# 分段
a_c = mf.stats(r_c3[r_c3.index <= "2022-12-31"]); a_60 = mf.stats(r_b1leg[r_b1leg.index <= "2022-12-31"])
b_c = mf.stats(r_c3[r_c3.index >= "2023-01-01"]); b_60 = mf.stats(r_b1leg[r_b1leg.index >= "2023-01-01"])

report = HYPO + f"""
## 1. 准则原文
权益腿不变：周频 T-MA60（A宽基）信号合成的「趋势权益仓」权重目标 **60%**。
债/货币腿目标 **40%**：**只持 511260**（不再用 511010+511260 等权 B1）。
月末再平衡；月内按日持有；0.2%RT；L≤1。

## 2. 实现要点
- 权益袖套 = 同池 T-MA60 日度持仓（周信号展开）；×0.6。
- 债腿 = 511260×0.4（主版）；邻档旁注纯 511010×0.4；对照 B1 各 0.2。
- 主版构建对齐 C2「固定60/40」日度跟袖套，保证同口径对照；另报月末冻结旁注。
- 成本 0.2%RT；{mf.START}→{mf.END}；不碰实盘。

## 3. 主表
{mf.metrics_table(M, main)}

### vs 固定60/40(B1) 证伪闸
- Calmar **{sc['Calmar']:.2f}** vs {s60['Calmar']:.2f}（Δ {sc['Calmar']-s60['Calmar']:+.2f}）
- MDD {sc['maxDD']:.1%} vs {s60['maxDD']:.1%}（差 {dd_gap*100:+.1f}pp；门槛更深>1pp 证伪）
- 2021 ret/DD：{y21_c:+.1%}/{ym21_c:.1%} vs {y21_b:+.1%}/{ym21_b:.1%}
- 2022 ret/DD：{y22_c:+.1%}/{ym22_c:.1%} vs {y22_b:+.1%}/{ym22_b:.1%}

### 分段 2020–22 / 2023–26
- C3：{a_c['ret']:.1%}/{a_c['maxDD']:.1%}/Cal{a_c['Calmar']:.2f} → {b_c['ret']:.1%}/{b_c['maxDD']:.1%}/Cal{b_c['Calmar']:.2f}
- 60/40(B1)：{a_60['ret']:.1%}/{a_60['maxDD']:.1%}/Cal{a_60['Calmar']:.2f} → {b_60['ret']:.1%}/{b_60['maxDD']:.1%}/Cal{b_60['Calmar']:.2f}

### 逐年
"""
Y = pd.concat([mf.yearly(books[k][0]).assign(book=k) for k in [
    main, "固定60/40(T-MA60:B1)", "纯周频T-MA60(同A宽基)", "邻档 债腿纯511010"]])
yp = Y.pivot(index="year", columns="book", values="ret"); yd = Y.pivot(index="year", columns="book", values="mdd")
ks = list(yp.columns)
report += "| 年 | " + " | ".join(ks) + " |\n|---|" + "---|" * len(ks) + "\n"
for y in yp.index:
    report += f"| {y} | " + " | ".join(f"{yp.at[y,k]:+.1%}/{yd.at[y,k]:.1%}" for k in ks) + " |\n"
report += f"""
## 4. 结论
{verdict}。{fal}

**证伪/失效句**：{fal}

产物：{OUT}/；不换冠军、不下单。
"""
mf.deliver(ID, books, main, f"{ID}（60/40 债腿纯511260，0.2%RT）", report, attr_md)
M.to_csv(f"{OUT}/metrics.csv", index=False)
pickle.dump(dict(falsified=falsified, sc=sc, s60=s60, dd_gap=dd_gap), open(f"{OUT}/_res.pkl", "wb"))
print("DONE", verdict, fal, flush=True)
print(M[["book", "ret", "maxDD", "Calmar", "turnover", "avg_expo"]].round(3).to_string(), flush=True)
