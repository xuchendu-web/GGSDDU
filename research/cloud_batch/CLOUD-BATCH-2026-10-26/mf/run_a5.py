#!/usr/bin/env python3
"""MF-A5：周频 T-MA60 选品/开关；日频仅目标波动缩放仓位（σ*=0.15 年化）。禁止日频 MA 进出。"""
import os, sys, pickle, math, numpy as np, pandas as pd
sys.path.insert(0, "/workspace/etf-multifreq/engine")
sys.path.insert(0, "/workspace/etf-trend/engine")
import mf_common as mf
import mom_engine as e
import trend as t
from pathlib import Path

ID = "MF-A5"
OUT = f"{mf.OUT_ROOT}/{ID}"
Path(OUT).mkdir(parents=True, exist_ok=True)

HYPO = """## 0. 假设与证伪（开跑前写死）
- **假设**：选品/开关仍用周频同池 T-MA60；仅对多头组合按日频 20 日实现 σ 做目标波动缩放（σ*=0.15 年化），急跌段 σ 上升应自动降仓，急跌回撤浅于纯周频 ≥3pp，且全样本 ΔCalmar≥0（扣日频增量成本后）。
- **证伪**（任一）：急跌浅不到 ≥3pp；或 ΔCalmar<0（扣日频增量成本后）；或 TV 生效周 <10%。
- **红线**：禁止重跑日频 MA 进出（A1/A4 已证伪）；不叠冠军强栈。
"""

D = mf.data()
P, aw, MF = D["P"], D["aw"], mf.MF
days = P.index[(P.index >= mf.START) & (P.index <= mf.END)]
keep = set(aw)
print(f"A宽基池 {len(aw)} 只", flush=True)

# ---- 周频 T-MA60 权重 → 展开到日度 ----
w_ma, st_ma = t.weights(t.s_ma(60), keep=keep)
r_wma, to_wma, ex_wma = t.run(w_ma)
print("weekly T-MA60", {k: round(float(v), 4) for k, v in mf.stats(r_wma).items()},
      f"to={to_wma:.2f} ex={ex_wma:.3f}", flush=True)

fri_sorted = sorted(w_ma.keys())
daily_tm = {}
for k, fri_d in enumerate(fri_sorted):
    tw = w_ma[fri_d]
    if k + 1 < len(fri_sorted):
        nxt = fri_sorted[k + 1]
        seg = days[(days >= fri_d) & (days < nxt)]
    else:
        seg = days[days >= fri_d]
    for dd in seg:
        daily_tm[dd] = dict(tw)

# 多头组合日收益（等权权益腿，不含 511880）——用于估 σ
# 对每个交易日，取当日 T-MA60 中非 MF 的成分等权日收益
R = P.pct_change()
eq_ret = pd.Series(0.0, index=days)
eq_has = pd.Series(False, index=days)
for dd in days:
    tw = daily_tm.get(dd, {})
    legs = [c for c in tw if c != MF and c in P.columns and tw[c] > 0 and not pd.isna(P.at[dd, c])]
    if not legs:
        continue
    # 用等权腿收益（准则：多头组合过去20日实现σ）
    rr = R.loc[dd, legs].fillna(0.0)
    eq_ret.loc[dd] = float(rr.mean())
    eq_has.loc[dd] = True

def build_tv(sig_star_ann=0.15):
    """日σ* = sig_star_ann/√252；scale=clip(σ*/σ_20,0,1)；权益×scale，余量→511880。"""
    sig_star = sig_star_ann / math.sqrt(252)
    W = {}
    scales = {}
    for dd in days:
        tw = daily_tm.get(dd, {MF: 1.0})
        # 过去20日实现σ（仅有权益收益的日）
        hist = eq_ret.loc[:dd]
        hist = hist[eq_has.loc[hist.index]]
        hist = hist.iloc[-20:] if len(hist) >= 20 else hist
        if len(hist) < 10:
            scale = 1.0
            sig = np.nan
        else:
            sig = float(hist.std(ddof=1))
            if sig <= 1e-12 or np.isnan(sig):
                scale = 1.0
            else:
                scale = float(np.clip(sig_star / sig, 0.0, 1.0))
        scales[dd] = (scale, sig)
        # 拆权益腿 / 原有 MF
        eq_w = {c: v for c, v in tw.items() if c != MF and v > 0}
        mf_w0 = tw.get(MF, 0.0)
        eq_sum = sum(eq_w.values())
        ww = {c: v * scale for c, v in eq_w.items()}
        # 余量（被缩放掉的权益 + 原 MF）→ 511880
        residual = eq_sum * (1 - scale) + mf_w0
        # 若原权重和 <1，也补到 MF（通常 T-MA60 已满仓）
        leftover = 1.0 - sum(ww.values()) - residual
        residual = residual + max(0.0, leftover)
        if residual > 1e-8 and not pd.isna(P.at[dd, MF]):
            ww[MF] = ww.get(MF, 0.0) + residual
        elif residual > 1e-8:
            # MF 无价则按比例放大权益（极少见）
            s = sum(ww.values())
            if s > 0:
                ww = {c: v / s for c, v in ww.items()}
        ww = {c: v for c, v in ww.items() if v > 1e-8}
        W[dd] = ww
    return W, scales

W_main, sc_main = build_tv(0.15)
rec_main = {}
r_main, to_main, ex_main = mf.run_daily(W_main, fill="close", record=rec_main)
print("A5 σ*=0.15", {k: round(float(v), 4) for k, v in mf.stats(r_main).items()},
      f"to={to_main:.2f} ex={ex_main:.3f}", flush=True)

# 邻档
W_012, sc_012 = build_tv(0.12)
r_012, to_012, ex_012 = mf.run_daily(W_012, fill="close")
print("邻档 σ*=0.12", {k: round(float(v), 4) for k, v in mf.stats(r_012).items()},
      f"to={to_012:.2f} ex={ex_012:.3f}", flush=True)
W_020, sc_020 = build_tv(0.20)
r_020, to_020, ex_020 = mf.run_daily(W_020, fill="close")
print("邻档 σ*=0.20", {k: round(float(v), 4) for k, v in mf.stats(r_020).items()},
      f"to={to_020:.2f} ex={ex_020:.3f}", flush=True)

# 同均仓固定对照：用主版均权益仓
eq_expo = []
for dd in days:
    tw = W_main[dd]
    eq_expo.append(sum(v for c, v in tw.items() if c != MF))
xbar = float(np.mean(eq_expo))
print(f"主版均权益仓 x̄={xbar:.3f}", flush=True)

# 静态：每日等权权益 × xbar + MF
C = P[aw]
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

# 买入持有（日频等权宽基）
W_bh = {}
for dd in days:
    pl = [c for c in aw if not pd.isna(C.at[dd, c])]
    if pl:
        W_bh[dd] = {c: 1 / len(pl) for c in pl}
r_bh, to_bh, ex_bh = mf.run_daily(W_bh, fill="close")

# 纯周频日度展开（无 TV）对照：daily_tm 直接跑
r_wk_d, to_wk_d, ex_wk_d = mf.run_daily(daily_tm, fill="close")
print("周频展开日度(无TV)", {k: round(float(v), 4) for k, v in mf.stats(r_wk_d).items()},
      f"to={to_wk_d:.2f}", flush=True)

ch = mf.champ()

# TV 生效周：scale<1 的周占比
# 按周五周：若该周任一日 scale<1 则计生效？准则：「TV生效周：scale<1 的周占比」
# 用每周最后一个交易日的 scale，或周内 mean scale<1
week_scale = {}
for dd, (sc, _) in sc_main.items():
    wk = dd.to_period("W-FRI")
    week_scale.setdefault(wk, []).append(sc)
# 生效周：该周平均 scale < 1（或任一日 <1）——用「周内有任一日 scale<1」更贴近「生效」
active_weeks = sum(1 for vs in week_scale.values() if any(s < 0.999 for s in vs))
n_weeks = len(week_scale)
tv_frac = active_weeks / n_weeks if n_weeks else 0.0
# 也报日级
scales_arr = np.array([sc_main[dd][0] for dd in days])
day_active = float((scales_arr < 0.999).mean())
print(f"TV生效周 {active_weeks}/{n_weeks} = {tv_frac:.1%}；日级生效 {day_active:.1%}；均scale={scales_arr.mean():.3f}", flush=True)

# 急跌段
CRASH = [("2020-02 COVID", "2020-02-01", "2020-03-31"),
         ("2022-03 俄乌", "2022-02-15", "2022-04-30"),
         ("2024-01 微盘", "2024-01-01", "2024-02-15")]
crash_rows = []
for name, a, b in CRASH:
    crash_rows.append(dict(
        window=name, a=a, b=b,
        A5=mf.mdd(r_main, a, b),
        T_MA60_wk=mf.mdd(r_wma, a, b),
        wk_daily=mf.mdd(r_wk_d, a, b),
        BH=mf.mdd(r_bh, a, b),
        static=mf.mdd(r_st, a, b),
        champ=mf.mdd(ch[0], a, b),
        A5_012=mf.mdd(r_012, a, b),
        A5_020=mf.mdd(r_020, a, b),
    ))
Crash = pd.DataFrame(crash_rows)
Crash.to_csv(f"{OUT}/crash_windows.csv", index=False)
print(Crash.round(4).to_string(), flush=True)

yrs = (days[-1] - days[0]).days / 365.25
cost_main = sum(rec_main.get("cost", {}).values())
cost_wma = 2 * to_wma * yrs * mf.CPS
# 日频展开无TV 的成本估
cost_wk_d_est = 2 * to_wk_d * yrs * mf.CPS
print(f"cost A5={cost_main:.4f}, weekly est={cost_wma:.4f}, wk_daily est={cost_wk_d_est:.4f}", flush=True)

sc = mf.stats(r_main); sw = mf.stats(r_wma); ss = mf.stats(r_st); swd = mf.stats(r_wk_d)
dCal_vs_weekly = sc["Calmar"] - sw["Calmar"]
dCal_vs_wkd = sc["Calmar"] - swd["Calmar"]
dCal_vs_static = sc["Calmar"] - ss["Calmar"]

shallow = []
for _, row in Crash.iterrows():
    pp = float(row["A5"] - row["T_MA60_wk"])  # positive if A5 shallower
    shallow.append((row["window"], pp))
min_shallow = min(pp for _, pp in shallow)

falsified_crash = min_shallow < 0.03
falsified_calmar = dCal_vs_weekly < 0  # 扣日频增量成本后：主版已含成本
falsified_tv = tv_frac < 0.10
falsified = falsified_crash or falsified_calmar or falsified_tv
verdict = "**证伪**" if falsified else "**未证伪**"
reasons = []
if falsified_crash:
    reasons.append(f"急跌最浅改善仅 {min_shallow*100:.1f}pp(<3pp；{'/'.join(f'{n}:{pp*100:+.1f}pp' for n,pp in shallow)})")
if falsified_calmar:
    reasons.append(f"ΔCalmar vs 周频T-MA60 {dCal_vs_weekly:+.2f}<0")
if falsified_tv:
    reasons.append(f"TV生效周 {tv_frac:.1%}<10%")
if not reasons:
    reasons.append(
        f"急跌浅 {'/'.join(f'{n}:{pp*100:+.1f}pp' for n,pp in shallow)}；"
        f"ΔCalmar {dCal_vs_weekly:+.2f}；TV生效周 {tv_frac:.1%}"
    )
fal_sentence = "；".join(reasons) + ("。证伪成立。" if falsified else "。未触发证伪闸。")

# 归因
expo = pd.Series(rec_main.get("expo", {})); expo.index = pd.to_datetime(expo.index)
expo = expo.reindex(r_main.index).fillna(0)
cost_s = pd.Series(rec_main.get("cost", {})); cost_s.index = pd.to_datetime(cost_s.index)
cost_s = cost_s.reindex(r_main.index).fillna(0)
pool = r_bh.reindex(r_main.index).fillna(0)
Cdf = pd.DataFrame(rec_main.get("contrib", {})).T.fillna(0).reindex(r_main.index).fillna(0)
gross = Cdf.sum(1)
unlev = (gross / expo.replace(0, np.nan)).fillna(0)
# scale series
scale_s = pd.Series({dd: sc_main[dd][0] for dd in days}).reindex(r_main.index).fillna(1.0)
dec = pd.DataFrame({
    "池等权β(满仓)": pool,
    "择时(仓位偏离满仓)": (expo - 1) * pool,
    "选品(持仓相对池等权)": expo * (unlev - pool),
    "成本": -cost_s,
})
dec_sum = dec.sum()
attr_md = f"""## 归因 · MF-A5 日频目标波动缩放（σ*=0.15）
_日度算术；样本 {r_main.index[0].date()}→{r_main.index[-1].date()}。选品/开关=周频T-MA60；频率改动=日频仓位缩放。_

### 收益拆解（全样本合计 / 年化）
| 分项 | 合计 | 年化 |
|---|---:|---:|
""" + "\n".join(f"| {k} | {v:+.1%} | {v/yrs:+.1%} |" for k, v in dec_sum.items()) + f"""
| 合计 | {dec_sum.sum():+.1%} | {dec_sum.sum()/yrs:+.1%} |

### 择时 / 选品 / 频率 / 成本
- **择时**：周频 T-MA60 开关 + 日频 σ 缩放（均权益仓 {xbar:.3f}；均 scale {scales_arr.mean():.3f}）
- **选品**：同周频 T-MA60 多头等权（未改选品键）
- **频率**：日频仅仓位；TV 生效周 {tv_frac:.1%}（{active_weeks}/{n_weeks}）；日级生效 {day_active:.1%}
- **成本**：A5 合计 {cost_main:.3f} vs 周频估 {cost_wma:.3f}（增量 {cost_main-cost_wma:+.3f}）；换手 {to_main:.2f}x vs 周频 {to_wma:.2f}x

### vs 对照
- vs 周频 T-MA60：ΔCalmar {dCal_vs_weekly:+.2f}；Δret {sc['ret']-sw['ret']:+.1%}
- vs 周频展开日度(无TV)：ΔCalmar {dCal_vs_wkd:+.2f}
- vs 同均仓静态：ΔCalmar {dCal_vs_static:+.2f}

### 急跌段
{Crash.to_string(index=False)}
"""

books = {
    "MF-A5 日频TV σ*=0.15(主版)": (r_main, to_main, ex_main),
    "邻档 σ*=0.12": (r_012, to_012, ex_012),
    "邻档 σ*=0.20": (r_020, to_020, ex_020),
    "周频T-MA60(同A宽基)": (r_wma, to_wma, ex_wma),
    "周频展开日度(无TV)": (r_wk_d, to_wk_d, ex_wk_d),
    f"同均仓固定对照(x̄={xbar:.2f})": (r_st, to_st, ex_st),
    "同池日频买入持有": (r_bh, to_bh, ex_bh),
    "冠军同引擎(研究副本)": ch,
}

main = "MF-A5 日频TV σ*=0.15(主版)"
M = pd.DataFrame([mf.row(k, *v[:3]) for k, v in books.items()])

report = HYPO + f"""
## 1. 准则原文
选品与开关仍用 **周频** 同池 T-MA60（A股宽基；空=511880；多头等权）。
**唯一日频改动**：每个交易日收盘，按多头组合过去 20 日实现 σ，将权益仓位缩为 `clip(σ*/σ, 0, 1)`，空位补 511880；σ*=**0.15**（年化，按 √252 换算日σ）。L≤1。
禁止重跑日频 MA 进出（A1/A4 已证伪）。

## 2. 实现要点
- 池：research_pool_v2 ∩ mom 宇宙 A宽基 **{len(aw)}** 只。
- 周频权重：`trend.weights(s_ma(60), keep=A宽基)`，周五信号展开到下一周五（持有）。
- 日频缩放：多头腿等权日收益的过去 20 日样本标准差 σ；日σ*={0.15/math.sqrt(252):.5f}；scale=clip(σ*/σ,0,1)；权益×scale，余量→511880。
- 邻档 σ*=0.12 / 0.20；对照：纯周频 T-MA60、周频展开日度(无TV)、同均仓固定、买入持有、冠军研究副本。
- 成本 0.2%RT；区间 {mf.START}→{mf.END}；panel_v2；不碰 strategy_exec。

## 3. 主表（0.2%RT，L≤1）
{mf.metrics_table(M, main)}

### TV 生效与仓位
- TV 生效周：**{tv_frac:.1%}**（{active_weeks}/{n_weeks}）；日级生效 {day_active:.1%}；均 scale={scales_arr.mean():.3f}；均权益仓={xbar:.3f}
- ΔCalmar vs 周频 T-MA60：**{dCal_vs_weekly:+.2f}**；vs 无TV日度展开 {dCal_vs_wkd:+.2f}；vs 静态 {dCal_vs_static:+.2f}
- 换手 {to_main:.2f}x vs 周频 {to_wma:.2f}x；成本 {cost_main:.3f} vs 周频估 {cost_wma:.3f}（增量 {cost_main-cost_wma:+.3f}）

### 急跌段回撤（负值；「浅」= 数值更大 / pp>0）
| 窗口 | A5主版 | σ*0.12 | σ*0.20 | 周频T-MA60 | 无TV日度 | 浅于周频(pp) |
|---|---:|---:|---:|---:|---:|---:|
""" + "\n".join(
    f"| {Crash.loc[i,'window']} | {mf.fmt_pct(Crash.loc[i,'A5'])} | {mf.fmt_pct(Crash.loc[i,'A5_012'])} | "
    f"{mf.fmt_pct(Crash.loc[i,'A5_020'])} | {mf.fmt_pct(Crash.loc[i,'T_MA60_wk'])} | "
    f"{mf.fmt_pct(Crash.loc[i,'wk_daily'])} | {(Crash.loc[i,'A5']-Crash.loc[i,'T_MA60_wk'])*100:+.1f} |"
    for i in range(len(Crash))
) + f"""

### 分段 2020–22 / 2023–26
- 主版：{mf.fmt_pct(M[M.book==main].iloc[0].ret20_22)} / {mf.fmt_pct(M[M.book==main].iloc[0].dd20_22)} / Cal {mf.fmt_cal(M[M.book==main].iloc[0].cal20_22)}
  → {mf.fmt_pct(M[M.book==main].iloc[0].ret23_26)} / {mf.fmt_pct(M[M.book==main].iloc[0].dd23_26)} / Cal {mf.fmt_cal(M[M.book==main].iloc[0].cal23_26)}
- 周频T-MA60：{mf.fmt_pct(M[M.book=='周频T-MA60(同A宽基)'].iloc[0].ret20_22)} / {mf.fmt_pct(M[M.book=='周频T-MA60(同A宽基)'].iloc[0].dd20_22)} / Cal {mf.fmt_cal(M[M.book=='周频T-MA60(同A宽基)'].iloc[0].cal20_22)}
  → {mf.fmt_pct(M[M.book=='周频T-MA60(同A宽基)'].iloc[0].ret23_26)} / {mf.fmt_pct(M[M.book=='周频T-MA60(同A宽基)'].iloc[0].dd23_26)} / Cal {mf.fmt_cal(M[M.book=='周频T-MA60(同A宽基)'].iloc[0].cal23_26)}

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

产物：{OUT}/；不换冠军、不下单、不叠强栈。
"""

mf.deliver(ID, books, main, f"{ID}（周频T-MA60+日频TV σ*=0.15，0.2%RT，L≤1）", report, attr_md)
M.to_csv(f"{OUT}/metrics.csv", index=False)
# scale series dump
pd.Series({dd: sc_main[dd][0] for dd in days}).to_csv(f"{OUT}/scale_daily.csv", header=["scale"])
pickle.dump(dict(falsified=falsified, tv_frac=tv_frac, min_shallow=min_shallow,
                 dCal=dCal_vs_weekly, shallow=shallow, Crash=Crash), open(f"{OUT}/_res.pkl", "wb"))
print("DONE", verdict, fal_sentence, flush=True)
print(M[["book", "ret", "maxDD", "Calmar", "turnover", "avg_expo"]].round(3).to_string(), flush=True)
