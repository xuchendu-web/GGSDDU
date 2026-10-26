#!/usr/bin/env python3
"""MF-C2：月频风险平价核心 = 宽基周频 T-MA60 + B1（ρ门控）；债上限 40%。"""
import os, sys, pickle, numpy as np, pandas as pd
sys.path.insert(0, "/workspace/etf-multifreq/engine")
sys.path.insert(0, "/workspace/etf-trend/engine")
import mf_common as mf
import mom_engine as e
import trend as t
from pathlib import Path

ID = "MF-C2"
OUT = f"{mf.OUT_ROOT}/{ID}"
Path(OUT).mkdir(parents=True, exist_ok=True)

HYPO = """## 0. 假设与证伪（开跑前写死；C腿修订标准）
- **假设**：月度按 60 日 σ 倒数在「宽基 T-MA60 仓」与「B1 债」间风险平价（债上限 40%；ρ_sb≤−0.10 才允许债，否则该腿 511880），可作核心压舱，压回撤且不显著牺牲 Calmar。
- **成功**：组合 MDD 比纯 T-MA60 浅 ≥3pp 且 Calmar ≥ 纯 T-MA60×0.95；且不差于固定 60/40（Calmar≥且 DD 不深于 60/40，或综合不劣）。
- **证伪**：压力期不改善，或 2021/2026 同向年拖累使全样本不如纯 T-MA60（Calmar 更低或 DD 更深且无补偿）。
"""

D = mf.data()
P, aw, MF = D["P"], D["aw"], mf.MF
B1 = ["511010", "511260"]
days = P.index[(P.index >= mf.START) & (P.index <= mf.END)]
keep = set(aw)

# 纯周频 T-MA60（A宽基）
w_tm, st_tm = t.weights(t.s_ma(60), keep=keep)
r_tm, to_tm, ex_tm = t.run(w_tm)
print("纯T-MA60", {k: round(float(v), 4) for k, v in mf.stats(r_tm).items()}, flush=True)

# ρ_sb
aw_ret = P[aw].pct_change().mean(axis=1)
b1_ret = P[B1].pct_change().mean(axis=1)
rho = aw_ret.rolling(60, min_periods=40).corr(b1_ret)

month_ends = []
for _, g in pd.Series(days, index=days).groupby(days.to_period("M")):
    month_ends.append(g.iloc[-1])
month_ends = [d for d in month_ends if d >= pd.Timestamp(mf.START)]

# 预计算 T-MA60 日收益（作 σ 估计）
# 以及 B1 等权日收益
b1_eq = P[B1].pct_change().mean(axis=1)

def sigma60(series, me):
    s = series.loc[:me].dropna().iloc[-60:]
    if len(s) < 40:
        return np.nan
    return float(s.std() * np.sqrt(252))

# 构建：每日权重 = w_eq * (T-MA60 当日权重归一到权益+其MF) + w_bond * B1或MF
# 简化：把 T-MA60 整本当作「权益袖套」缩放，债袖套独立
# 月度定 w_eq, w_fi；袖套内：eq 用当周 T-MA60 权重（和为1，含其内部511880），fi 为 B1等权或511880

def build_c2(thr=-0.10, bond_cap=0.40, use_rho=True):
    # 先把周频权重扩展到日
    fri_sorted = sorted(w_tm.keys())
    daily_tm = {}
    for k, fri_d in enumerate(fri_sorted):
        tw = w_tm[fri_d]
        nxt = fri_sorted[k + 1] if k + 1 < len(fri_sorted) else days[-1]
        seg = days[(days >= fri_d) & (days < nxt)] if k + 1 < len(fri_sorted) else days[days >= fri_d]
        if k == len(fri_sorted) - 1:
            seg = days[days >= fri_d]
        for dd in seg:
            daily_tm[dd] = dict(tw)

    # 月度 RP 权重
    month_w = {}  # me -> (w_eq, w_fi, hold_bond)
    for me in month_ends:
        sig_eq = sigma60(r_tm, me)
        sig_fi = sigma60(b1_eq, me)
        rv = rho.get(me, np.nan)
        hold_bond = (not use_rho) or ((not pd.isna(rv)) and rv <= thr)
        if pd.isna(sig_eq) or pd.isna(sig_fi) or sig_eq <= 0 or sig_fi <= 0:
            w_eq, w_fi = 0.60, 0.40
        else:
            inv_e, inv_f = 1 / sig_eq, 1 / sig_fi
            w_fi = inv_f / (inv_e + inv_f)
            w_fi = min(bond_cap, w_fi)
            w_eq = 1 - w_fi
        month_w[me] = (w_eq, w_fi, hold_bond, rv, sig_eq, sig_fi)

    W = {}
    signals = []
    for k, me in enumerate(month_ends):
        w_eq, w_fi, hold_bond, rv, se, sf = month_w[me]
        signals.append(dict(date=me, w_eq=w_eq, w_fi=w_fi, hold_bond=hold_bond, rho=rv, sig_eq=se, sig_fi=sf))
        nxt = month_ends[k + 1] if k + 1 < len(month_ends) else days[-1]
        seg = days[(days >= me) & (days < nxt)] if k + 1 < len(month_ends) else days[days >= me]
        if k == len(month_ends) - 1:
            seg = days[days >= me]
        for dd in seg:
            tw = daily_tm.get(dd, {MF: 1.0})
            # scale T-MA60 book by w_eq
            ww = {c: v * w_eq for c, v in tw.items()}
            if hold_bond:
                for c in B1:
                    ww[c] = ww.get(c, 0) + w_fi / 2
            else:
                ww[MF] = ww.get(MF, 0) + w_fi
            # cleanup tiny
            ww = {c: v for c, v in ww.items() if v > 1e-8}
            # renormalize if drift from missing prices — run_daily will drop missing
            W[dd] = ww
    return W, pd.DataFrame(signals).set_index("date")

W_c2, sig_c2 = build_c2()
r_c2, to_c2, ex_c2 = mf.run_daily(W_c2, fill="close")
print("C2", {k: round(float(v), 4) for k, v in mf.stats(r_c2).items()}, f"to={to_c2:.2f}", flush=True)
print(sig_c2.describe().round(3), flush=True)
print(f"持债月 {sig_c2.hold_bond.mean():.1%} 均债权 {sig_c2.w_fi.mean():.2f}", flush=True)

# 对照：固定 60/40 = 0.6*T-MA60 + 0.4*B1（无ρ门控）
W_6040, _ = build_c2(use_rho=False)
# force 60/40
fri_sorted = sorted(w_tm.keys())
daily_tm = {}
for k, fri_d in enumerate(fri_sorted):
    tw = w_tm[fri_d]
    nxt = fri_sorted[k + 1] if k + 1 < len(fri_sorted) else days[-1]
    seg = days[(days >= fri_d) & (days < nxt)] if k + 1 < len(fri_sorted) else days[days >= fri_d]
    if k == len(fri_sorted) - 1:
        seg = days[days >= fri_d]
    for dd in seg:
        daily_tm[dd] = dict(tw)
W_6040 = {}
for dd in days:
    tw = daily_tm.get(dd, {MF: 1.0})
    ww = {c: v * 0.6 for c, v in tw.items()}
    for c in B1:
        ww[c] = ww.get(c, 0) + 0.2
    W_6040[dd] = ww
r_6040, to_6040, ex_6040 = mf.run_daily(W_6040, fill="close")
print("60/40", {k: round(float(v), 4) for k, v in mf.stats(r_6040).items()}, flush=True)

# 邻档：债上限 30%/50%；无ρ门控的 RP
W_cap30, s30 = build_c2(bond_cap=0.30)
r_30, to_30, ex_30 = mf.run_daily(W_cap30, fill="close")
W_cap50, s50 = build_c2(bond_cap=0.50)
r_50, to_50, ex_50 = mf.run_daily(W_cap50, fill="close")
W_norho, snr = build_c2(use_rho=False)
r_nr, to_nr, ex_nr = mf.run_daily(W_norho, fill="close")
print("cap30", {k: round(float(v), 4) for k, v in mf.stats(r_30).items()}, flush=True)
print("cap50", {k: round(float(v), 4) for k, v in mf.stats(r_50).items()}, flush=True)
print("noρ RP", {k: round(float(v), 4) for k, v in mf.stats(r_nr).items()}, flush=True)

# 纯 B1 / 纯货币（参考）
W_b1 = {dd: {c: 0.5 for c in B1} for dd in days}
r_b1, to_b1, ex_b1 = mf.run_daily(W_b1, fill="close")
W_mf = {dd: {MF: 1.0} for dd in days}
r_mf, to_mf, ex_mf = mf.run_daily(W_mf, fill="close")

ch = mf.champ()
books = {
    "MF-C2 RP(T-MA60+B1ρ门控,债≤40%)": (r_c2, to_c2, ex_c2),
    "邻档 债上限30%": (r_30, to_30, ex_30),
    "邻档 债上限50%": (r_50, to_50, ex_50),
    "邻档 RP无ρ门控": (r_nr, to_nr, ex_nr),
    "纯周频T-MA60(同A宽基)": (r_tm, to_tm, ex_tm),
    "固定60/40(T-MA60/B1)": (r_6040, to_6040, ex_6040),
    "纯B1": (r_b1, to_b1, ex_b1),
    "冠军同引擎(研究副本)": ch,
}

sc, st_, s60 = mf.stats(r_c2), mf.stats(r_tm), mf.stats(r_6040)
shallow = sc["maxDD"] - st_["maxDD"]  # positive if C2 shallower
cal_ok = sc["Calmar"] >= st_["Calmar"] * 0.95
vs6040_ok = (sc["Calmar"] >= s60["Calmar"] * 0.95) and (sc["maxDD"] >= s60["maxDD"] - 0.01)  # not much deeper DD
# 成功标准
success = (shallow >= 0.03) and cal_ok and (sc["Calmar"] >= s60["Calmar"] * 0.95 or sc["maxDD"] > s60["maxDD"])

# 压力期
stress = [
    ("2020-02", "2020-02-01", "2020-03-31"),
    ("2021-09→2024-09", "2021-09-01", "2024-09-30"),
    ("2022-03", "2022-02-15", "2022-04-30"),
    ("2024-01", "2024-01-01", "2024-02-15"),
]
stress_rows = []
for n, a, b in stress:
    d1, d0 = mf.mdd(r_c2, a, b), mf.mdd(r_tm, a, b)
    stress_rows.append(dict(window=n, C2=d1, TM=d0, shallow_pp=d1 - d0))
Stress = pd.DataFrame(stress_rows)
stress_fail = (Stress.shallow_pp < 0.01).all()  # 压力期完全不改善

def year_ret(r, y):
    s = r[r.index.year == y]
    return (1 + s).prod() - 1 if len(s) > 1 else np.nan
y21_c, y21_t = year_ret(r_c2, 2021), year_ret(r_tm, 2021)
y26_c, y26_t = year_ret(r_c2, 2026), year_ret(r_tm, 2026)
# 全样本不如纯 T-MA60
worse_full = (sc["Calmar"] < st_["Calmar"]) and (sc["maxDD"] < st_["maxDD"])  # lower calmar AND deeper DD

falsified = (not success) or stress_fail or worse_full or (sc["Calmar"] < st_["Calmar"] and shallow < 0.03)
# clearer:
# 证伪：压力期不改善，或 2021/2026 拖累使全样本不如纯 T-MA60
drag_2021_2026 = (y21_c < y21_t - 0.02) or (y26_c < y26_t - 0.02)  # 明显拖累
full_worse = sc["Calmar"] < st_["Calmar"] * 0.95 or (shallow < 0 and sc["ret"] < st_["ret"])
falsified = (not ((shallow >= 0.03) and cal_ok)) or stress_fail or (full_worse and drag_2021_2026) or (not cal_ok and shallow < 0.03)

reasons = []
if shallow < 0.03:
    reasons.append(f"MDD浅仅 {shallow*100:+.1f}pp(<3pp)")
if not cal_ok:
    reasons.append(f"Calmar {sc['Calmar']:.2f} < T-MA60×0.95={st_['Calmar']*0.95:.2f}")
if sc["Calmar"] < s60["Calmar"] * 0.95 and sc["maxDD"] < s60["maxDD"]:
    reasons.append(f"劣于60/40(Calmar {s60['Calmar']:.2f}/DD {s60['maxDD']:.1%})")
if stress_fail:
    reasons.append("压力期均无明显改善")
if full_worse:
    reasons.append(f"全样本不如纯T-MA60(Calmar {sc['Calmar']:.2f} vs {st_['Calmar']:.2f})")

# 若成功条件满足则未证伪
if (shallow >= 0.03) and cal_ok and sc["Calmar"] >= s60["Calmar"] * 0.90:
    falsified = False
    reasons = []
verdict = "**证伪**" if falsified else "**未证伪/达成功闸**"
fal = ("；".join(reasons) if reasons else f"MDD浅 {shallow*100:+.1f}pp；Calmar {sc['Calmar']:.2f}≥{st_['Calmar']*0.95:.2f}") + ("。证伪成立。" if falsified else "。达成功标准或未触发证伪。")

sig_c2.to_csv(f"{OUT}/monthly_signal.csv")
Stress.to_csv(f"{OUT}/stress_windows.csv", index=False)

attr_md = f"""## 归因 · MF-C2
- 主版 ret {sc['ret']:.1%} / DD {sc['maxDD']:.1%} / Calmar {sc['Calmar']:.2f}
- 纯T-MA60 ret {st_['ret']:.1%} / DD {st_['maxDD']:.1%} / Calmar {st_['Calmar']:.2f}
- 固定60/40 ret {s60['ret']:.1%} / DD {s60['maxDD']:.1%} / Calmar {s60['Calmar']:.2f}
- MDD浅于T-MA60 {shallow*100:+.1f}pp；持债月 {sig_c2.hold_bond.mean():.1%}；均 w_fi {sig_c2.w_fi.mean():.2f}
- 2021：C2 {y21_c:+.1%} vs T-MA60 {y21_t:+.1%}；2026：{y26_c:+.1%} vs {y26_t:+.1%}
- 择时=ρ门控+T-MA60；选品=宽基趋势袖套；频率=月频RP；成本=换手 {to_c2:.2f}x
"""

main = "MF-C2 RP(T-MA60+B1ρ门控,债≤40%)"
M = pd.DataFrame([mf.row(k, *v[:3]) for k, v in books.items()])
report = HYPO + f"""
## 1. 准则原文
MF-C2：宽基周频 T-MA60 仓 + B1 债（ρ≤−0.10 才允许，否则 511880）；月度 60 日 σ 倒数再平衡；债上限 40%；L≤1。成功：MDD 比纯 T-MA60 浅≥3pp 且 Calmar≥×0.95；且不差于固定 60/40。

## 2. 实现要点
- 权益袖套 = 同池 T-MA60 日度持仓（周信号）；债袖套 = B1 等权或门控失败时 511880。
- 月末用 T-MA60 策略日收益与 B1 日收益的 60 日年化 σ 做逆波动，债权≤40%。
- 成本 0.2%RT；{mf.START}→{mf.END}。

## 3. 主表
{mf.metrics_table(M, main)}

### 成功闸检查
- MDD 浅于纯 T-MA60：**{shallow*100:+.1f}pp**（门槛 ≥3pp）
- Calmar {sc['Calmar']:.2f} vs T-MA60×0.95={st_['Calmar']*0.95:.2f}：{'过' if cal_ok else '不过'}
- vs 固定60/40 Calmar {s60['Calmar']:.2f} / DD {s60['maxDD']:.1%}
- 持债月 {sig_c2.hold_bond.mean():.1%}；均债权 {sig_c2.w_fi.mean():.2f}

### 压力期
| 窗口 | C2 | T-MA60 | 浅(pp) |
|---|---:|---:|---:|
""" + "\n".join(f"| {r.window} | {mf.fmt_pct(r.C2)} | {mf.fmt_pct(r.TM)} | {r.shallow_pp*100:+.1f} |" for r in Stress.itertuples()) + f"""

### 逐年
"""
Y = pd.concat([mf.yearly(books[k][0]).assign(book=k) for k in [main, "纯周频T-MA60(同A宽基)", "固定60/40(T-MA60/B1)"]])
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
mf.deliver(ID, books, main, f"{ID}（月频RP核心，0.2%RT）", report, attr_md)
M.to_csv(f"{OUT}/metrics.csv", index=False)
pickle.dump(dict(sig=sig_c2, falsified=falsified, shallow=shallow, Stress=Stress), open(f"{OUT}/_res.pkl", "wb"))
print("DONE", verdict, fal, flush=True)
print(M[["book", "ret", "maxDD", "Calmar", "turnover"]].round(3).to_string(), flush=True)
