#!/usr/bin/env python3
"""MF-A1 宽基日频趋势：日收盘>MA60 持有，否则 511880；多头等权；L≤1。"""
import os, sys, pickle, numpy as np, pandas as pd
sys.path.insert(0, "/workspace/etf-multifreq/engine")
import mf_common as mf
import mom_engine as e
from pathlib import Path

ID = "MF-A1"
OUT = f"{mf.OUT_ROOT}/{ID}"
Path(OUT).mkdir(parents=True, exist_ok=True)

# ---- 假设与证伪（开跑前）----
HYPO = """## 0. 假设与证伪（开跑前写死）
- **假设**：日频 MA60 能比周频 T-MA60 更早躲急跌（2020-02、2022-03、2024-01），急跌段回撤至少浅 3pp。
- **证伪**：急跌段回撤浅不到周频 T-MA60 的 3pp，或日频相对周频的增量成本吃掉择时增益（ΔCalmar≤0 且成本增量显著）。
- **注意**：必报同平均仓位固定对照与独立择时 ΔCalmar；日频增量换手/成本单独列。
"""

D = mf.data()
P, aw, MF = D["P"], D["aw"], mf.MF
print(f"A宽基池 {len(aw)} 只", flush=True)

# 日线 MA60（含当日收盘）
C = P[aw]
MA60 = C.rolling(60, min_periods=60).mean()

days = P.index[(P.index >= mf.START) & (P.index <= mf.END)]
# 每日权重：多头等权 1/N_pool，空位填 511880
def build_w():
    w = {}
    long_frac = []
    for dd in days:
        row = C.loc[dd]; ma = MA60.loc[dd]
        pl = [c for c in aw if not pd.isna(row[c]) and not pd.isna(ma[c])]
        if not pl:
            w[dd] = {MF: 1.0} if not pd.isna(P.at[dd, MF]) else {}
            long_frac.append(0.0); continue
        L = [c for c in pl if row[c] > ma[c]]
        ww = {c: 1 / len(pl) for c in L}
        if len(L) < len(pl) and not pd.isna(P.at[dd, MF]):
            ww[MF] = (len(pl) - len(L)) / len(pl)
        w[dd] = ww
        long_frac.append(len(L) / len(pl))
    return w, np.mean(long_frac)

W_close, xbar = build_w()
print(f"均多头占比 {xbar:.3f}", flush=True)

# 主版：信号日收盘成交
rec_c = {}
r_c, to_c, ex_c = mf.run_daily(W_close, fill="close", record=rec_c)
print("close fill", {k: round(float(v), 4) for k, v in mf.stats(r_c).items()}, f"to={to_c:.1f}", f"ex={ex_c:.3f}", flush=True)

# 邻档：次日开盘成交
rec_o = {}
r_o, to_o, ex_o = mf.run_daily(W_close, fill="open", record=rec_o)
print("open fill", {k: round(float(v), 4) for k, v in mf.stats(r_o).items()}, f"to={to_o:.1f}", flush=True)

# 同池日频买入持有（每日等权，几乎无换手）
W_bh = {}
for dd in days:
    pl = [c for c in aw if not pd.isna(C.at[dd, c])]
    if pl:
        W_bh[dd] = {c: 1 / len(pl) for c in pl}
r_bh, to_bh, ex_bh = mf.run_daily(W_bh, fill="close")
print("BH daily", {k: round(float(v), 4) for k, v in mf.stats(r_bh).items()}, flush=True)

# 周频 T-MA60（同 A宽基池，研究副本：周五信号/收盘成交）
# 复用 trend 口径：周收/14:30 > MA60
sys.path.insert(0, "/workspace/etf-trend/engine")
import trend as t
# trend.CAT / weights with keep=aw
keep = set(aw)
w_ma, st_ma = t.weights(t.s_ma(60), keep=keep)
r_wma, to_wma, ex_wma = t.run(w_ma)
print("weekly T-MA60 A宽基", {k: round(float(v), 4) for k, v in mf.stats(r_wma).items()}, f"to={to_wma:.1f}", f"long={(st_ma.long/st_ma.pool).mean():.3f}", flush=True)

# 同平均仓位固定对照（用日频主版的 xbar）
W_static = {}
for dd in days:
    pl = [c for c in aw if not pd.isna(C.at[dd, c])]
    if not pl:
        W_static[dd] = {MF: 1.0}; continue
    ww = {c: xbar / len(pl) for c in pl}
    if not pd.isna(P.at[dd, MF]):
        ww[MF] = 1 - xbar
    W_static[dd] = ww
r_st, to_st, ex_st = mf.run_daily(W_static, fill="close")
print("static", {k: round(float(v), 4) for k, v in mf.stats(r_st).items()}, flush=True)

# 冠军同引擎
ch = mf.champ()

# 急跌段 MDD
CRASH = [("2020-02 COVID", "2020-02-01", "2020-03-31"),
         ("2022-03 俄乌", "2022-02-15", "2022-04-30"),
         ("2024-01 微盘", "2024-01-01", "2024-02-15")]
crash_rows = []
for name, a, b in CRASH:
    crash_rows.append(dict(
        window=name, a=a, b=b,
        MF_A1_close=mf.mdd(r_c, a, b),
        MF_A1_open=mf.mdd(r_o, a, b),
        T_MA60_wk=mf.mdd(r_wma, a, b),
        BH=mf.mdd(r_bh, a, b),
        static=mf.mdd(r_st, a, b),
        champ=mf.mdd(ch[0], a, b),
    ))
Crash = pd.DataFrame(crash_rows)
Crash.to_csv(f"{OUT}/crash_windows.csv", index=False)
print(Crash.round(4).to_string(), flush=True)

# 成本
cost_c = sum(rec_c.get("cost", {}).values())
cost_o = sum(rec_o.get("cost", {}).values())
# 周频成本估：turnover * CPS * years * 2? to is oneway/yr, cost≈ to * 0.001 * years... actually run doesn't give total easily
# approximate weekly cost from to_wma
yrs = (days[-1] - days[0]).days / 365.25
cost_wma_est = to_wma * mf.CPS * yrs  # to is oneway/yr; cost per rebalance uses to*CPS with to=sum|dw|/2 so yearly cost ≈ to_oneway * CPS * yrs? 
# In mom_engine: to_total += to/2 where to=sum|dw|; r -= to*CPS. So annual cost drag ≈ (to_total)*2*CPS / yrs wait
# to returned = to_total/yrs where to_total = sum(sum|dw|/2) = sum(oneway). cost sum = sum(sum|dw|*CPS) = 2*to_total*CPS
# so total cost = 2 * to * yrs * CPS
cost_wma = 2 * to_wma * yrs * mf.CPS
cost_c_check = 2 * to_c * yrs * mf.CPS
print(f"cost close={cost_c:.4f} (est {cost_c_check:.4f}), weekly est={cost_wma:.4f}, delta={cost_c-cost_wma:.4f}", flush=True)

sc = mf.stats(r_c); sw = mf.stats(r_wma); ss = mf.stats(r_st)
dCal_vs_static = sc["Calmar"] - ss["Calmar"]
dCal_vs_weekly = sc["Calmar"] - sw["Calmar"]

# 邻档 MA20 / MA120 日频（快速稳健性）
def build_ma(n):
    MAn = C.rolling(n, min_periods=n).mean()
    w = {}
    for dd in days:
        row = C.loc[dd]; ma = MAn.loc[dd]
        pl = [c for c in aw if not pd.isna(row[c]) and not pd.isna(ma[c])]
        if not pl:
            w[dd] = {MF: 1.0} if not pd.isna(P.at[dd, MF]) else {}; continue
        L = [c for c in pl if row[c] > ma[c]]
        ww = {c: 1 / len(pl) for c in L}
        if len(L) < len(pl) and not pd.isna(P.at[dd, MF]):
            ww[MF] = (len(pl) - len(L)) / len(pl)
        w[dd] = ww
    return w

books = {
    "MF-A1 日频MA60·收盘成交(主版)": (r_c, to_c, ex_c),
    "邻档 日频MA60·次日开盘成交": (r_o, to_o, ex_o),
}
for n, lab in [(20, "邻档 日频MA20·收盘"), (120, "邻档 日频MA120·收盘")]:
    ww = build_ma(n)
    rr, tt, ee = mf.run_daily(ww, fill="close")
    books[lab] = (rr, tt, ee)
    print(lab, {k: round(float(v), 4) for k, v in mf.stats(rr).items()}, f"to={tt:.1f}", flush=True)

books["同池日频买入持有"] = (r_bh, to_bh, ex_bh)
books["周频T-MA60(同A宽基)"] = (r_wma, to_wma, ex_wma)
books[f"同均仓固定对照(x̄={xbar:.2f})"] = (r_st, to_st, ex_st)
books["冠军同引擎(研究副本)"] = ch

# 证伪判定
shallow = []
for _, row in Crash.iterrows():
    gap = row["T_MA60_wk"] - row["MF_A1_close"]  # more negative = deeper; shallow means A1 DD less deep → A1 - weekly > 0 in magnitude terms
    # DD are negative; "浅 3pp" means A1_DD - weekly_DD >= 0.03 (e.g. -0.10 vs -0.13)
    pp = float(row["MF_A1_close"] - row["T_MA60_wk"])  # positive if A1 shallower
    shallow.append((row["window"], pp))
min_shallow = min(pp for _, pp in shallow)
falsified_crash = min_shallow < 0.03  # 任一急跌段浅不到3pp → 看「至少」：证伪条件是急跌段回撤浅不到3pp
# PLAN: 急跌段回撤浅不到周频 T-MA60 的 3pp → if NOT (shallow by ≥3pp), falsified
# "至少" listed windows — if none of them achieve ≥3pp shallow, or if overall we require each?
# Interpret: if the improvement in crash DD is <3pp (for the relevant crashes), falsify.
# I'll say: if max improvement across crashes <3pp OR average <3pp → falsified. Strict: if ANY of the three fails to improve by 3pp... 
# Better: require that in those crash windows, daily is ≥3pp shallower. If the best-case crash improvement is still <3pp, falsified. 
# Actually: "急跌段回撤浅不到周频的3pp" means the daily version fails to cut DD by 3pp in crash periods.
all_fail = all(pp < 0.03 for _, pp in shallow)
any_fail = any(pp < 0.03 for _, pp in shallow)
# Use: if not all three achieve ≥3pp shallow, report which; primary falsify if min_shallow < 0.03 (i.e. the worst/least improvement among crashes is under 3pp)
falsified_by_crash = min_shallow < 0.03
falsified_by_cost = (cost_c - cost_wma) > 0 and dCal_vs_weekly <= 0
falsified = falsified_by_crash or falsified_by_cost

verdict = "**证伪**" if falsified else "**未证伪**"
fal_sentence = (
    f"急跌段相对周频T-MA60 最浅改善仅 {min_shallow*100:.1f}pp"
    f"（{'/'.join(f'{n}:{pp*100:+.1f}pp' for n,pp in shallow)}）；"
    f"日频成本 {cost_c:.3f} vs 周频估 {cost_wma:.3f}（+{cost_c-cost_wma:.3f}）；"
    f"ΔCalmar vs 周频 {dCal_vs_weekly:+.2f}，vs 静态 {dCal_vs_static:+.2f}。"
    + (" 证伪成立。" if falsified else " 未触发证伪闸。")
)

# 归因拆解（日频主版）
expo = pd.Series(rec_c.get("expo", {})); expo.index = pd.to_datetime(expo.index); expo = expo.reindex(r_c.index).fillna(0)
cost_s = pd.Series(rec_c.get("cost", {})); cost_s.index = pd.to_datetime(cost_s.index); cost_s = cost_s.reindex(r_c.index).fillna(0)
pool = r_bh.reindex(r_c.index).fillna(0)
Cdf = pd.DataFrame(rec_c.get("contrib", {})).T.fillna(0).reindex(r_c.index).fillna(0)
gross = Cdf.sum(1)
unlev = (gross / expo.replace(0, np.nan)).fillna(0)
dec = pd.DataFrame({
    "池等权β(满仓)": pool,
    "择时(仓位偏离满仓)": (expo - 1) * pool,
    "选品(持仓相对池等权)": expo * (unlev - pool),
    "成本": -cost_s,
})
# 频率：日频相对周频的收益差归到「频率」粗拆
# 对齐周频到日：用 r_wma
freq_proxy = r_c - r_wma.reindex(r_c.index).fillna(0)
yrsN = yrs
dec_sum = dec.sum()
attr_md = f"""## 归因 · MF-A1 日频MA60·收盘成交
_日度算术；样本 {r_c.index[0].date()}→{r_c.index[-1].date()}。_

### 收益拆解（全样本合计 / 年化）
| 分项 | 合计 | 年化 |
|---|---:|---:|
""" + "\n".join(f"| {k} | {v:+.1%} | {v/yrsN:+.1%} |" for k, v in dec_sum.items()) + f"""
| 合计 | {dec_sum.sum():+.1%} | {dec_sum.sum()/yrsN:+.1%} |

### 频率 vs 周频
- 日频主版 Calmar {sc['Calmar']:.2f} vs 周频T-MA60 {sw['Calmar']:.2f}（Δ {dCal_vs_weekly:+.2f}）
- 日频换手 {to_c:.1f}x/年 vs 周频 {to_wma:.1f}x；成本合计 {cost_c:.3f} vs 周频估 {cost_wma:.3f}（增量 {cost_c-cost_wma:+.3f}）
- 同均仓静态 Calmar {ss['Calmar']:.2f} → 独立择时 ΔCalmar {dCal_vs_static:+.2f}

### 急跌段
{Crash.to_string(index=False)}
"""

main = "MF-A1 日频MA60·收盘成交(主版)"
M_rows = []
for k, v in books.items():
    M_rows.append(mf.row(k, v[0], v[1], v[2]))
M = pd.DataFrame(M_rows)
# add crash cols for main books
for name, a, b in CRASH:
    col = f"dd_{name[:7]}"
    M[col] = [mf.mdd(books[k][0], a, b) for k in M.book]

report = HYPO + f"""
## 1. 准则原文
MF-A1：日频，A股宽基池，收盘>MA60 持有、否则 511880；多头等权；信号日收盘算、次日开盘或收盘成交（邻档）。假设日频能比周频早躲急跌。证伪：急跌段回撤浅不到周频 T-MA60 的 3pp，或日频增量成本吃掉择时增益。

## 2. 实现要点
- 池：research_pool_v2 ∩ mom 宇宙 A宽基 **{len(aw)}** 只（panel 有价）。
- 信号：每个交易日收盘价 > 日线 MA60（含当日）；多头权重各 1/N_pool，空位 511880；L≤1。
- 成交主版=信号日收盘；邻档=次日开盘（OHLC 复权开盘，open-to-open 收益）。
- 周频对照：同池 T-MA60（etf-trend 引擎，周五≥14:30/收盘，空=511880）。
- 成本 0.2%RT；区间 {mf.START}→{mf.END}。
- 数据：panel_v2 + 已校验 14:30；OHLC 自 etf-trend/tdx_ohlc_raw；不碰 strategy_exec。

## 3. 主表（0.2%RT，L≤1）
{mf.metrics_table(M, main)}

### 同均仓固定对照与 ΔCalmar
- 日频主版均多头占比 x̄={xbar:.3f}；静态对照 Calmar {ss['Calmar']:.2f}；**独立择时 ΔCalmar = {dCal_vs_static:+.2f}**
- vs 周频 T-MA60：ΔCalmar = {dCal_vs_weekly:+.2f}；增量换手 {to_c-to_wma:+.1f}x/年；增量成本 {cost_c-cost_wma:+.3f}

### 急跌段回撤（负值；「浅」= 数值更大）
| 窗口 | MF-A1收盘 | MF-A1开盘 | 周频T-MA60 | 日频BH | 静态 | 浅于周频(pp) |
|---|---:|---:|---:|---:|---:|---:|
""" + "\n".join(
    f"| {n} | {mf.fmt_pct(Crash.loc[i,'MF_A1_close'])} | {mf.fmt_pct(Crash.loc[i,'MF_A1_open'])} | "
    f"{mf.fmt_pct(Crash.loc[i,'T_MA60_wk'])} | {mf.fmt_pct(Crash.loc[i,'BH'])} | {mf.fmt_pct(Crash.loc[i,'static'])} | "
    f"{(Crash.loc[i,'MF_A1_close']-Crash.loc[i,'T_MA60_wk'])*100:+.1f} |"
    for i, (n,_,_) in enumerate([(x[0],x[1],x[2]) for x in CRASH])
) + f"""

### 逐年（主版 vs 周频 vs BH）
"""
Y = pd.concat([mf.yearly(books[k][0]).assign(book=k) for k in [main, "周频T-MA60(同A宽基)", "同池日频买入持有"]])
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

mf.deliver(ID, books, main, f"{ID}（日频MA60，0.2%RT，L≤1，空=511880）", report, attr_md)
# extras
M.to_csv(f"{OUT}/metrics.csv", index=False)
pickle.dump(dict(W_close=W_close, xbar=xbar, crash=Crash, dec=dec_sum, falsified=falsified), open(f"{OUT}/_res.pkl", "wb"))
print("DONE", verdict, fal_sentence, flush=True)
print(M[["book", "ret", "maxDD", "Calmar", "turnover", "avg_expo"]].round(3).to_string(), flush=True)
