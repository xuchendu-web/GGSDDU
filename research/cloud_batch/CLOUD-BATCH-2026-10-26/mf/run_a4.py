#!/usr/bin/env python3
"""MF-A4：周频 T-MA60 底座 + 日频跌破 MA60 降仓；再开仓仅周五。"""
import os, sys, pickle, numpy as np, pandas as pd
sys.path.insert(0, "/workspace/etf-multifreq/engine")
sys.path.insert(0, "/workspace/etf-trend/engine")
import mf_common as mf
import mom_engine as e
import trend as t
from pathlib import Path

ID = "MF-A4"
OUT = f"{mf.OUT_ROOT}/{ID}"
Path(OUT).mkdir(parents=True, exist_ok=True)

HYPO = """## 0. 假设与证伪（开跑前写死）
- **假设**：日频只负责早逃（持仓宽基日收跌破 MA60 → 当日收盘改 511880），周频负责再进（重新开仓仅周五周频信号允许），避免日频来回刷。
- **证伪**（任一）：急跌段相对纯周频浅不到 3pp；或日频增量换手成本 ≥ 择时增益；或 Calmar ≤ 纯周频。
"""

D = mf.data()
P, aw, MF = D["P"], D["aw"], mf.MF
days = P.index[(P.index >= mf.START) & (P.index <= mf.END)]
C = P[aw]
MA60 = C.rolling(60, min_periods=60).mean()
keep = set(aw)

# 周频 T-MA60 权重（研究副本，同 A1）
w_wk, st_wk = t.weights(t.s_ma(60), keep=keep)
r_wk, to_wk, ex_wk = t.run(w_wk)
print("纯周频", {k: round(float(v), 4) for k, v in mf.stats(r_wk).items()}, f"to={to_wk:.2f}", flush=True)

# 周五集合
fri = set(D["reb"]) | set(w_wk.keys())
# 也包含 grid 周末交易日
fri = {d for d in D["G"] if d >= pd.Timestamp(mf.START) and d <= pd.Timestamp(mf.END)}
# 用 trend 的 reb 作为周频调仓日
fri_sorted = sorted(w_wk.keys())
print(f"周频调仓日 {len(fri_sorted)}", flush=True)

# 构建日频叠加权重
# 状态：每个宽基是否「本周允许持有」（来自周五信号），以及是否已被日频砍掉
W_a4 = {}
cuts = []  # (date, code) 日频砍仓事件
reentries_blocked = 0
for k, fri_d in enumerate(fri_sorted):
    # 本周目标：周频多头集合
    tw = w_wk.get(fri_d, {})
    allowed = {c for c, w in tw.items() if c != MF and w > 0}
    mf_w0 = tw.get(MF, 0.0)
    Npool = len([c for c in aw if not pd.isna(C.at[fri_d, c])]) if fri_d in C.index else len(aw)
    # slot weight
    slot = 1.0 / Npool if Npool else 0.0
    # 日频存活集合（初始化=允许集合）
    alive = set(allowed)
    nxt = fri_sorted[k + 1] if k + 1 < len(fri_sorted) else days[-1]
    seg = days[(days >= fri_d) & (days < nxt)] if k + 1 < len(fri_sorted) else days[days >= fri_d]
    if k == len(fri_sorted) - 1:
        seg = days[days >= fri_d]
    for dd in seg:
        # 日频检查：alive 中跌破 MA60 的砍掉（当日收盘）
        # 周五当日：先用周频开仓，再检查是否当日已破（允许当日即砍）
        dead = []
        for c in list(alive):
            px, ma = C.at[dd, c] if c in C.columns else np.nan, MA60.at[dd, c] if c in MA60.columns else np.nan
            if pd.isna(px) or pd.isna(ma):
                continue
            if px <= ma:  # 跌破或等于
                dead.append(c)
        for c in dead:
            if c in alive:
                alive.discard(c)
                cuts.append((dd, c))
        # 权重：存活多头各 slot，其余→511880；与周频同构造（1/N_pool）
        ww = {c: slot for c in alive if not pd.isna(C.at[dd, c])}
        long_w = sum(ww.values())
        if not pd.isna(P.at[dd, MF]):
            ww[MF] = 1.0 - long_w
        W_a4[dd] = ww

r_a4, to_a4, ex_a4 = mf.run_daily(W_a4, fill="close")
print("A4", {k: round(float(v), 4) for k, v in mf.stats(r_a4).items()}, f"to={to_a4:.2f}", f"砍仓次数={len(cuts)}", flush=True)

# 纯日频 MF-A1（复用已有净值或重算）
# 从 A1 nav 或重跑简版
a1nav = pd.read_csv("/workspace/etf-multifreq/MF-A1/nav.csv", index_col=0, parse_dates=True)
col_a1 = [c for c in a1nav.columns if "日频MA60·收盘" in c][0]
r_a1 = a1nav[col_a1].pct_change().fillna(0)
# turnover from A1 metrics
a1m = pd.read_csv("/workspace/etf-multifreq/MF-A1/metrics.csv")
to_a1 = float(a1m.loc[a1m.book.str.contains("日频MA60·收盘"), "turnover"].iloc[0])
ex_a1 = float(a1m.loc[a1m.book.str.contains("日频MA60·收盘"), "avg_expo"].iloc[0])

# 同仓位固定对照：用 A4 的均权益仓
# 估计权益仓 = 1 - MF weight
eq_frac = []
for dd, ww in W_a4.items():
    eq_frac.append(sum(v for c, v in ww.items() if c != MF))
xbar = float(np.mean(eq_frac)) if eq_frac else 0.5
W_st = {}
for dd in days:
    pl = [c for c in aw if not pd.isna(C.at[dd, c])]
    if not pl:
        W_st[dd] = {MF: 1.0}; continue
    ww = {c: xbar / len(pl) for c in pl}
    if not pd.isna(P.at[dd, MF]):
        ww[MF] = 1 - xbar
    W_st[dd] = ww
r_st, to_st, ex_st = mf.run_daily(W_st, fill="close")
print(f"static xbar={xbar:.3f}", {k: round(float(v), 4) for k, v in mf.stats(r_st).items()}, flush=True)

# 邻档：用 MA20 作日频砍仓线；用 MA120
def build_overlay(man):
    MAn = C.rolling(man, min_periods=man).mean()
    W = {}
    for k, fri_d in enumerate(fri_sorted):
        tw = w_wk.get(fri_d, {})
        allowed = {c for c, w in tw.items() if c != MF and w > 0}
        Npool = len([c for c in aw if not pd.isna(C.at[fri_d, c])]) if fri_d in C.index else len(aw)
        slot = 1.0 / Npool if Npool else 0.0
        alive = set(allowed)
        nxt = fri_sorted[k + 1] if k + 1 < len(fri_sorted) else days[-1]
        seg = days[(days >= fri_d) & (days < nxt)] if k + 1 < len(fri_sorted) else days[days >= fri_d]
        if k == len(fri_sorted) - 1:
            seg = days[days >= fri_d]
        for dd in seg:
            for c in list(alive):
                px = C.at[dd, c] if c in C.columns else np.nan
                ma = MAn.at[dd, c] if c in MAn.columns else np.nan
                if not pd.isna(px) and not pd.isna(ma) and px <= ma:
                    alive.discard(c)
            ww = {c: slot for c in alive if not pd.isna(C.at[dd, c])}
            long_w = sum(ww.values())
            if not pd.isna(P.at[dd, MF]):
                ww[MF] = 1.0 - long_w
            W[dd] = ww
    return W

W_m20 = build_overlay(20)
r_m20, to_m20, ex_m20 = mf.run_daily(W_m20, fill="close")
W_m120 = build_overlay(120)
r_m120, to_m120, ex_m120 = mf.run_daily(W_m120, fill="close")
print("邻档MA20", {k: round(float(v), 4) for k, v in mf.stats(r_m20).items()}, f"to={to_m20:.1f}", flush=True)
print("邻档MA120", {k: round(float(v), 4) for k, v in mf.stats(r_m120).items()}, f"to={to_m120:.1f}", flush=True)

ch = mf.champ()
books = {
    "MF-A4 周频T-MA60+日频破MA60砍(主版)": (r_a4, to_a4, ex_a4),
    "邻档 日频砍线MA20": (r_m20, to_m20, ex_m20),
    "邻档 日频砍线MA120": (r_m120, to_m120, ex_m120),
    "纯周频T-MA60(同A宽基)": (r_wk, to_wk, ex_wk),
    "纯日频MF-A1(对照)": (r_a1, to_a1, ex_a1),
    f"同均仓固定对照(x̄={xbar:.2f})": (r_st, to_st, ex_st),
    "冠军同引擎(研究副本)": ch,
}

# 急跌段
CRASH = [("2020-02 COVID", "2020-02-01", "2020-03-31"),
         ("2022-03 俄乌", "2022-02-15", "2022-04-30"),
         ("2024-01 微盘", "2024-01-01", "2024-02-15")]
crash_rows = []
for name, a, b in CRASH:
    crash_rows.append(dict(
        window=name,
        A4=mf.mdd(r_a4, a, b), wk=mf.mdd(r_wk, a, b), a1=mf.mdd(r_a1, a, b),
        static=mf.mdd(r_st, a, b),
        shallow_pp=mf.mdd(r_a4, a, b) - mf.mdd(r_wk, a, b),
    ))
Crash = pd.DataFrame(crash_rows)
Crash.to_csv(f"{OUT}/crash_windows.csv", index=False)
print(Crash.round(4).to_string(), flush=True)

sa, sw, ss = mf.stats(r_a4), mf.stats(r_wk), mf.stats(r_st)
dCal = sa["Calmar"] - sw["Calmar"]
min_shallow = Crash.shallow_pp.min()
yrs = (days[-1] - days[0]).days / 365.25
# 成本：A4 vs 周频增量
# approximate from turnover
cost_a4 = 2 * to_a4 * yrs * mf.CPS
cost_wk = 2 * to_wk * yrs * mf.CPS
inc_cost = cost_a4 - cost_wk
# 择时增益粗估：终值差
gain = sa["ret"] - sw["ret"]  # total return diff (not perfect vs cost)

f1 = min_shallow < 0.03
f2 = inc_cost >= max(gain, 0) and to_a4 > to_wk  # 增量成本≥择时增益
f3 = sa["Calmar"] <= sw["Calmar"]
falsified = f1 or f2 or f3
reasons = []
if f1: reasons.append(f"急跌段最浅改善 {min_shallow*100:+.1f}pp(<3pp)")
if f2: reasons.append(f"增量成本 {inc_cost:.3f} ≥ 收益增益 {gain:+.3f}")
if f3: reasons.append(f"Calmar {sa['Calmar']:.2f} ≤ 周频 {sw['Calmar']:.2f}")
verdict = "**证伪**" if falsified else "**未证伪**"
fal = ("；".join(reasons) if reasons else "未触发") + ("。证伪成立。" if falsified else "。未触发证伪闸。")

# 归因
attr_md = f"""## 归因 · MF-A4
- 主版 ret {sa['ret']:.1%} / DD {sa['maxDD']:.1%} / Calmar {sa['Calmar']:.2f}
- 纯周频 ret {sw['ret']:.1%} / DD {sw['maxDD']:.1%} / Calmar {sw['Calmar']:.2f}
- ΔCalmar vs 周频 {dCal:+.2f}；vs 静态 {sa['Calmar']-ss['Calmar']:+.2f}
- 换手 A4 {to_a4:.1f}x vs 周频 {to_wk:.1f}x（增量 {to_a4-to_wk:+.1f}x）；成本估 {cost_a4:.3f} vs {cost_wk:.3f}
- 日频砍仓事件 {len(cuts)} 次；均权益仓 {xbar:.3f}
- 择时=日频早逃；选品=同周频宽基；频率=日频叠加周频；成本=增量换手
"""

main = "MF-A4 周频T-MA60+日频破MA60砍(主版)"
M = pd.DataFrame([mf.row(k, *v[:3]) for k, v in books.items()])
report = HYPO + f"""
## 1. 准则原文
MF-A4：底座周频宽基 T-MA60；日频若持仓宽基日收跌破 MA60，当日收盘降为 511880；重新开仓只在周五周频信号允许时。

## 2. 实现要点
- 池 A宽基 {len(aw)} 只；周频信号与 etf-trend T-MA60 同构造（1/N_pool，空=511880）。
- 周内：仅允许砍仓，不允许把已砍品种买回；下周五按周频信号重置。
- 成本 0.2%RT；{mf.START}→{mf.END}。砍仓事件 {len(cuts)} 次。

## 3. 主表
{mf.metrics_table(M, main)}

### ΔCalmar / 成本
- vs 纯周频：ΔCalmar {dCal:+.2f}；增量换手 {to_a4-to_wk:+.1f}x；增量成本 {inc_cost:+.3f}；收益差 {gain:+.1%}
- vs 静态(x̄={xbar:.2f})：ΔCalmar {sa['Calmar']-ss['Calmar']:+.2f}

### 急跌段（浅于周频 pp）
| 窗口 | A4 | 周频 | A1日频 | 浅于周频(pp) |
|---|---:|---:|---:|---:|
""" + "\n".join(
    f"| {r.window} | {mf.fmt_pct(r.A4)} | {mf.fmt_pct(r.wk)} | {mf.fmt_pct(r.a1)} | {r.shallow_pp*100:+.1f} |"
    for r in Crash.itertuples()
) + f"""

### 逐年
"""
Y = pd.concat([mf.yearly(books[k][0]).assign(book=k) for k in [main, "纯周频T-MA60(同A宽基)", "纯日频MF-A1(对照)"]])
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
mf.deliver(ID, books, main, f"{ID}（周频+日频早逃，0.2%RT）", report, attr_md)
M.to_csv(f"{OUT}/metrics.csv", index=False)
pickle.dump(dict(cuts=cuts, xbar=xbar, falsified=falsified, Crash=Crash), open(f"{OUT}/_res.pkl", "wb"))
print("DONE", verdict, fal, flush=True)
print(M[["book", "ret", "maxDD", "Calmar", "turnover"]].round(3).to_string(), flush=True)
