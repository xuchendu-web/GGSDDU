#!/usr/bin/env python3
"""MF-C1 债/货币月频配比：ρ_sb≤−0.10 持 B1=511010+511260 等权，否则 511880。"""
import os, sys, pickle, numpy as np, pandas as pd
sys.path.insert(0, "/workspace/etf-multifreq/engine")
import mf_common as mf
import mom_engine as e
from pathlib import Path

ID = "MF-C1"
OUT = f"{mf.OUT_ROOT}/{ID}"
Path(OUT).mkdir(parents=True, exist_ok=True)

HYPO = """## 0. 假设与证伪（开跑前写死）
- **假设**：债只在与宽基 60 日相关 ≤ −0.10 时上场，可避开 2021/2026 股债同向年，相对纯货币改善 Calmar。
- **证伪**：2021 与 2026YTD 相对纯货币不改善，或全样本 Calmar ≤ 纯货币。
- **独立**：不依附任何权益开关（承接 R4b 证伪结论）。
"""

D = mf.data()
P, aw = D["P"], D["aw"]
MF = mf.MF
B1 = ["511010", "511260"]
print("B1 codes", B1, "aw", len(aw), flush=True)

days = P.index[(P.index >= mf.START) & (P.index <= mf.END)]
# 宽基等权日收益
aw_px = P[aw]
aw_ret = aw_px.pct_change().mean(axis=1)  # equal-weight portfolio daily ret (approx; ignores reconstitution)
# B1 等权
b1_px = P[B1].mean(axis=1)  # price average — better use equal weight returns
b1_ret = P[B1].pct_change().mean(axis=1)
mf_ret = P[MF].pct_change()

# 60 日滚动相关（用已实现收益，月末决策只用 ≤ 月末的数据）
rho = aw_ret.rolling(60, min_periods=40).corr(b1_ret)

# 月末交易日
month_ends = []
for _, g in pd.Series(days, index=days).groupby(days.to_period("M")):
    month_ends.append(g.iloc[-1])
month_ends = [d for d in month_ends if d >= pd.Timestamp(mf.START)]
print(f"月度数 {len(month_ends)}, rho 描述:\n{rho.reindex(month_ends).describe()}", flush=True)

THR = -0.10

def build_monthly(thr=THR):
    """月末定仓，持有到下月末；权重在月内每日保持（月度再平衡）。"""
    w = {}
    signal = {}
    for k, me in enumerate(month_ends):
        rv = rho.get(me, np.nan)
        hold_bond = (not pd.isna(rv)) and (rv <= thr)
        signal[me] = dict(rho=rv, hold_bond=hold_bond)
        if hold_bond:
            ww = {c: 0.5 for c in B1}
        else:
            ww = {MF: 1.0}
        # apply to all days from me to next me (exclusive of next, inclusive of me for close-fill)
        nxt = month_ends[k + 1] if k + 1 < len(month_ends) else days[-1]
        seg = days[(days >= me) & (days < nxt)] if k + 1 < len(month_ends) else days[days >= me]
        for dd in seg:
            w[dd] = dict(ww)
        # also last day
        if k == len(month_ends) - 1:
            w[days[-1]] = dict(ww)
    return w, signal

W_c1, sig = build_monthly(THR)
r_c1, to_c1, ex_c1 = mf.run_daily(W_c1, fill="close")
print("C1", {k: round(float(v), 4) for k, v in mf.stats(r_c1).items()}, f"to={to_c1:.2f}", flush=True)

# 对照：纯货币
W_mf = {dd: {MF: 1.0} for dd in days}
r_mf, to_mf, ex_mf = mf.run_daily(W_mf, fill="close")
print("纯货币", {k: round(float(v), 4) for k, v in mf.stats(r_mf).items()}, flush=True)

# 纯 B1
W_b1 = {dd: {c: 0.5 for c in B1} for dd in days}
r_b1p, to_b1p, ex_b1p = mf.run_daily(W_b1, fill="close")
print("纯B1", {k: round(float(v), 4) for k, v in mf.stats(r_b1p).items()}, flush=True)

# 固定 60/40 = 60% B1 + 40% MF
W_6040 = {dd: {**{c: 0.3 for c in B1}, MF: 0.4} for dd in days}
r_6040, to_6040, ex_6040 = mf.run_daily(W_6040, fill="close")
print("60/40", {k: round(float(v), 4) for k, v in mf.stats(r_6040).items()}, flush=True)

# 邻档 thr=-0.05 / -0.20 / 0.00
neigh = {}
for thr, lab in [(-0.05, "邻档 ρ≤−0.05"), (-0.20, "邻档 ρ≤−0.20"), (0.0, "邻档 ρ≤0")]:
    ww, _ = build_monthly(thr)
    rr, tt, ee = mf.run_daily(ww, fill="close")
    neigh[lab] = (rr, tt, ee)
    print(lab, {k: round(float(v), 4) for k, v in mf.stats(rr).items()}, flush=True)

# 持债月占比
hold_months = sum(1 for v in sig.values() if v["hold_bond"])
print(f"持债月 {hold_months}/{len(sig)} = {hold_months/len(sig):.1%}", flush=True)

# 逐年 + 2021/2026 相对纯货币
def year_ret(r, y):
    s = r[r.index.year == y]
    if len(s) < 2:
        return np.nan
    return (1 + s).prod() - 1

y2021_c1, y2021_mf = year_ret(r_c1, 2021), year_ret(r_mf, 2021)
y2026_c1, y2026_mf = year_ret(r_c1, 2026), year_ret(r_mf, 2026)
sc, sm = mf.stats(r_c1), mf.stats(r_mf)
print(f"2021 C1={y2021_c1:.2%} MF={y2021_mf:.2%}; 2026 C1={y2026_c1:.2%} MF={y2026_mf:.2%}", flush=True)
print(f"全样本 Calmar C1={sc['Calmar']:.2f} MF={sm['Calmar']:.2f}", flush=True)

# 证伪
f_2021 = not (y2021_c1 > y2021_mf)  # 不改善
f_2026 = not (y2026_c1 > y2026_mf)
f_cal = not (sc["Calmar"] > sm["Calmar"])
# PLAN: 2021 与 2026YTD 相对纯货币不改善，或全样本 Calmar ≤ 纯货币
# "与" could mean both years fail, or either — typically both named years should improve; falsify if either fails to improve OR calmar≤
falsified = f_2021 or f_2026 or f_cal
reasons = []
if f_2021: reasons.append(f"2021 相对纯货币不改善（{y2021_c1:+.2%} vs {y2021_mf:+.2%}）")
if f_2026: reasons.append(f"2026YTD 相对纯货币不改善（{y2026_c1:+.2%} vs {y2026_mf:+.2%}）")
if f_cal: reasons.append(f"全样本 Calmar {sc['Calmar']:.2f} ≤ 纯货币 {sm['Calmar']:.2f}")
verdict = "**证伪**" if falsified else "**未证伪**"
fal_sentence = ("；".join(reasons) if reasons else f"2021/2026 均改善且 Calmar {sc['Calmar']:.2f}>{sm['Calmar']:.2f}") + ("。证伪成立。" if falsified else "。未触发证伪闸。")

ch = mf.champ()
books = {
    "MF-C1 ρ≤−0.10持债(主版)": (r_c1, to_c1, ex_c1),
    **neigh,
    "纯货币511880": (r_mf, to_mf, ex_mf),
    "纯B1(511010+511260等权)": (r_b1p, to_b1p, ex_b1p),
    "固定60/40(B1/货币)": (r_6040, to_6040, ex_6040),
    "冠军同引擎(研究副本)": ch,
}

# 归因：择时=相对纯货币的超额；选品=债种选择（此处仅 B1）；频率=月频
excess = r_c1 - r_mf.reindex(r_c1.index).fillna(0)
# bond exposure series
bond_expo = pd.Series({dd: sum(W_c1[dd].get(c, 0) for c in B1) for dd in W_c1})
bond_expo.index = pd.to_datetime(bond_expo.index)
bond_expo = bond_expo.reindex(r_c1.index).fillna(0)

attr_md = f"""## 归因 · MF-C1
- 全样本 ret {sc['ret']:.1%} / DD {sc['maxDD']:.1%} / Calmar {sc['Calmar']:.2f}
- 纯货币 ret {sm['ret']:.1%} / DD {sm['maxDD']:.1%} / Calmar {sm['Calmar']:.2f}
- 相对纯货币超额合计 {(excess).sum():+.1%}（算术）
- 持债月占比 {hold_months/len(sig):.1%}；均债仓 {bond_expo.mean():.2f}
- 2021：C1 {y2021_c1:+.2%} vs 货币 {y2021_mf:+.2%}（Δ {y2021_c1-y2021_mf:+.2%}）
- 2026YTD：C1 {y2026_c1:+.2%} vs 货币 {y2026_mf:+.2%}（Δ {y2026_c1-y2026_mf:+.2%}）
- 择时：仅在 ρ_sb≤−0.10 持债；选品：B1=5年+10年国债 ETF 等权；频率：月频；成本：换手 {to_c1:.2f}x/年
"""

# rho 时间序列存档
sig_df = pd.DataFrame(sig).T
sig_df.to_csv(f"{OUT}/monthly_signal.csv")

main = "MF-C1 ρ≤−0.10持债(主版)"
M = pd.DataFrame([mf.row(k, *v[:3]) for k, v in books.items()])

report = HYPO + f"""
## 1. 准则原文
MF-C1：月末，B1 债池（511010+511260 等权）vs 511880；仅当 ρ_sb(宽基,B1)≤−0.10 持债，否则货币；独立于权益开关。

## 2. 实现要点
- 宽基 = A股宽基 {len(aw)} 只日收益等权均值；B1 = 511010+511260 日收益等权均值。
- ρ_sb = 过去 60 日滚动相关；月末交易日取值；ρ≤−0.10 → 下月持 B1 等权，否则全 511880。
- 成交：月内按日持有（换仓记在月初日收盘）；成本 0.2%RT。
- 对照：纯货币、纯 B1、固定 60/40。邻档阈值 −0.05/−0.20/0。

## 3. 主表
{mf.metrics_table(M, main)}

### 关键诊断
- 持债月 {hold_months}/{len(sig)} = {hold_months/len(sig):.1%}
- 2021：C1 {y2021_c1:+.2%} vs 纯货币 {y2021_mf:+.2%}（Δ {y2021_c1-y2021_mf:+.2%}）
- 2026YTD：C1 {y2026_c1:+.2%} vs 纯货币 {y2026_mf:+.2%}（Δ {y2026_c1-y2026_mf:+.2%}）
- 全样本 Calmar {sc['Calmar']:.2f} vs 纯货币 {sm['Calmar']:.2f}

### 逐年
"""
Y = pd.concat([mf.yearly(books[k][0]).assign(book=k) for k in [main, "纯货币511880", "纯B1(511010+511260等权)", "固定60/40(B1/货币)"]])
yp = Y.pivot(index="year", columns="book", values="ret")
yd = Y.pivot(index="year", columns="book", values="mdd")
ks = list(yp.columns)
report += "| 年 | " + " | ".join(ks) + " |\n|---|" + "---|" * len(ks) + "\n"
for y in yp.index:
    report += f"| {y} | " + " | ".join(f"{yp.at[y,k]:+.1%}/{yd.at[y,k]:.1%}" for k in ks) + " |\n"

report += f"""
## 4. 结论
{verdict}。{fal_sentence}

**证伪/失效句**：{fal_sentence}

产物：{OUT}/；不换冠军、不下单。
"""

mf.deliver(ID, books, main, f"{ID}（月频债/货币，0.2%RT）", report, attr_md)
M.to_csv(f"{OUT}/metrics.csv", index=False)
pickle.dump(dict(sig=sig, falsified=falsified, hold_pct=hold_months/len(sig)), open(f"{OUT}/_res.pkl", "wb"))
print("DONE", verdict, fal_sentence, flush=True)
print(M[["book", "ret", "maxDD", "Calmar", "turnover", "avg_expo"]].round(3).to_string(), flush=True)
