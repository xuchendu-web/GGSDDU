#!/usr/bin/env python3
"""MF-STACK-v2：核心85%固定60/40 + 卫星≤15% B4（breadth门控）；硬约束 MDD≤60/40。"""
import os, sys, pickle, numpy as np, pandas as pd
sys.path.insert(0, "/workspace/etf-multifreq/engine")
sys.path.insert(0, "/workspace/etf-trend/engine")
import mf_common as mf
import mom_engine as e
import trend as t
import attribution as A
from pathlib import Path

ID = "MF-STACK-v2"
OUT = f"{mf.OUT_ROOT}/{ID}"
Path(OUT).mkdir(parents=True, exist_ok=True)

HYPO = """## 0. 假设与证伪（开跑前写死）
- **假设**：把卫星预算从 30% 降到 ≤15%，可保留 breadth 择时增益，同时不破坏固定 60/40 核心的压舱回撤。
- **成功**：MDD ≤ 固定60/40（允许深 ≤0.5pp 算持平）且 Calmar ≥ 60/40×0.95；2020–22 与 2023–26 两分段均不劣于 60/40。
- **证伪**：任一压舱年（或 2020–22）Calmar 低于 60/40，或压力期回撤深于 60/40 超过 1pp。
- **breadth**：冠军同款周收>周MA20≥45%（主版）；MA60 旁注。
"""

D = mf.data()
P, aw, ind, MF = D["P"], D["aw"], D["ind"], mf.MF
B1 = ["511010", "511260"]
gi, reb = D["gi"], D["reb"]
KEEP_AW, KEEP_IND = set(aw), set(ind)

# breadth MA20（冠军）
face = pd.read_csv(e.FACE)
face["date"] = pd.to_datetime(face.date.astype(str).str[:10])
bface = face.set_index("date")["b"] if "b" in face.columns else None
bn = pd.read_csv("/workspace/etf-momentum/data_v1016/breadth_ma20_v1016.csv", parse_dates=["date"]).set_index("date").b
B20 = bface[bface.index <= "2026-09-24"].combine_first(bn[bn.index > "2026-09-24"]) if bface is not None else bn

# 旁注 MA60
codes_b = [c for c in list(KEEP_AW | KEEP_IND) if c in P.columns]
MA60d = P[codes_b].rolling(60, min_periods=60).mean()
B60 = pd.Series({dd: float((P.loc[dd, codes_b].notna() & MA60d.loc[dd].notna() &
                            (P.loc[dd, codes_b] > MA60d.loc[dd])).sum() /
                           max((P.loc[dd, codes_b].notna() & MA60d.loc[dd].notna()).sum(), 1))
                 for dd in reb if dd in P.index})

w_tm, _ = t.weights(t.s_ma(60), keep=KEEP_AW)

def picks_xs(i, N=5):
    s = e.mom(i, 52, 1)
    s = s[[c for c in s.index if c in KEEP_IND]].dropna()
    return e.topn(s, N) if len(s) else []

def invvol_w(dd, codes, look=60):
    if not codes or dd not in P.index: return {}
    loc = P.index.get_loc(dd)
    if loc < look: return {c: 1 / len(codes) for c in codes}
    sig = P[codes].iloc[loc-look:loc].pct_change().iloc[1:].std().replace(0, np.nan)
    inv = (1.0 / sig).dropna()
    inv = inv[[c for c in codes if c in inv.index]]
    if inv.empty or inv.sum() <= 0: return {c: 1 / len(codes) for c in codes}
    return (inv / inv.sum()).to_dict()

W_b4 = {}
for dd in reb:
    i = gi[dd]
    if i < 52: W_b4[dd] = {}; continue
    W_b4[dd] = invvol_w(dd, picks_xs(i, 5), 60)

def core_weights(dd, core_frac):
    tw = w_tm.get(dd, {MF: 1.0})
    ww = {c: v * core_frac * 0.6 for c, v in tw.items()}
    for c in B1:
        ww[c] = ww.get(c, 0.0) + core_frac * 0.4 / 2
    return ww

def core_equity_frac(dd, core_frac):
    """核心权益腿实际仓位（T-MA60 中非 MF 部分 × core_frac×0.6 的和 / (core_frac×0.6) 预算）。"""
    tw = w_tm.get(dd, {MF: 1.0})
    eq = sum(v for c, v in tw.items() if c != MF)
    budget = core_frac * 0.6
    return eq * core_frac * 0.6, budget  # actual equity in portfolio from core, and budget

def merge(a, b):
    out = dict(a)
    for c, v in b.items():
        out[c] = out.get(c, 0.0) + v
    return {c: v for c, v in out.items() if v > 1e-12}

def build(core_frac, sat_frac, breadth_series=B20, thr=0.45, risk_budget_gate=False):
    W, sat_on, gated = {}, {}, {}
    for dd in reb:
        cw = core_weights(dd, core_frac)
        try:
            bv = float(breadth_series.loc[dd]) if dd in breadth_series.index else np.nan
        except Exception:
            bv = np.nan
        on = (not pd.isna(bv)) and (bv >= thr)
        if risk_budget_gate:
            # 卫星仅在核心权益腿仓位 < 核心权益预算的 50% 时才允许开
            actual_eq, budget = core_equity_frac(dd, core_frac)
            # actual_eq is portfolio weight in equity from core; budget = core_frac*0.6
            # 「核心权益腿仓位」相对预算：actual_eq/budget = T-MA60 多头占比
            tw = w_tm.get(dd, {MF: 1.0})
            long_frac = sum(v for c, v in tw.items() if c != MF)  # already 多头/池 占比≈long/N * N = long_frac of book that's equity
            # T-MA60 book: equity weight = sum non-MF = long/N_pool * N_long... actually sum of non-MF weights = n_long/n_pool
            eq_leg_util = long_frac  # 0..1 fraction of the 60% equity sleeve that is invested
            allow = eq_leg_util < 0.50
            gated[dd] = allow
            on = on and allow
        else:
            gated[dd] = True
        if on and W_b4.get(dd):
            sw = {c: v * sat_frac for c, v in W_b4[dd].items()}
        else:
            sw = {MF: sat_frac}
            on = False if not (on and W_b4.get(dd)) else on
            if not W_b4.get(dd):
                on = False
                sw = {MF: sat_frac}
        if not on:
            sw = {MF: sat_frac}
        W[dd] = merge(cw, sw)
        sat_on[dd] = bool(on)
    return W, sat_on, gated

# 主版 85/15
W_main, on_main, _ = build(0.85, 0.15)
r_main, to_main, ex_main = mf.run_weekly(W_main)
print("v2 85/15", {k: round(float(v), 4) for k, v in mf.stats(r_main).items()},
      f"sat_on={np.mean(list(on_main.values())):.1%}", flush=True)

specs = {
    "邻档 卫星10%(核心90%)": build(0.90, 0.10),
    "邻档 卫星20%(核心80%)": build(0.80, 0.20),
    "旁注 风险预算腾挪(核心权益腿<50%才开卫星)": build(0.85, 0.15, risk_budget_gate=True),
    "旁注 breadth用MA60≥45%": build(0.85, 0.15, breadth_series=B60),
}
books = {"MF-STACK-v2 核心85%+卫星15%B4·B20≥45%(主版)": (r_main, to_main, ex_main)}
extra_on = {"主版": on_main}
for lab, (Ww, on, gated) in specs.items():
    rr, tt, ee = mf.run_weekly(Ww)
    books[lab] = (rr, tt, ee)
    extra_on[lab] = on
    print(lab, {k: round(float(v), 4) for k, v in mf.stats(rr).items()},
          f"sat_on={np.mean(list(on.values())):.1%}", flush=True)

# 对照
r_tm, to_tm, ex_tm = t.run(w_tm)
W_6040 = {dd: core_weights(dd, 1.0) for dd in reb}
r_6040, to_6040, ex_6040 = mf.run_weekly(W_6040)
r_b4, to_b4, ex_b4 = mf.run_weekly(W_b4)
ch = mf.champ()

# 同均仓
eq_codes = set(aw) | set(ind)
xbar = float(np.mean([sum(v for c, v in W_main[dd].items() if c in eq_codes) for dd in reb]))
all_eq = [c for c in eq_codes if c in P.columns]
W_st = {}
for dd in reb:
    pl = [c for c in all_eq if not pd.isna(P.at[dd, c])]
    W_st[dd] = ({c: xbar / len(pl) for c in pl} | {MF: 1 - xbar}) if pl else {MF: 1.0}
r_st, to_st, ex_st = mf.run_weekly(W_st)

# 卫星强制关
W_off = {dd: merge(core_weights(dd, 0.85), {MF: 0.15}) for dd in reb}
r_off, to_off, ex_off = mf.run_weekly(W_off)

books.update({
    "纯周频T-MA60(同A宽基)": (r_tm, to_tm, ex_tm),
    "固定60/40(T-MA60:B1)": (r_6040, to_6040, ex_6040),
    "纯B4逆波动(卫星腿)": (r_b4, to_b4, ex_b4),
    f"同均仓固定对照(x̄权益={xbar:.2f})": (r_st, to_st, ex_st),
    "旁注 核心85%+卫星强制关": (r_off, to_off, ex_off),
    "冠军同引擎(研究副本)": ch,
})

sm, s60 = mf.stats(r_main), mf.stats(r_6040)
dd_gap = sm["maxDD"] - s60["maxDD"]  # ≥ -0.005 算持平或更好（maxDD 是负的；浅=更大）
# MDD ≤ 60/40 允许深0.5pp：sm.maxDD >= s60.maxDD - 0.005
mdd_ok = sm["maxDD"] >= s60["maxDD"] - 0.005
cal_ok = sm["Calmar"] >= s60["Calmar"] * 0.95

def seg(r, which):
    return mf.stats(r[r.index <= "2022-12-31"] if which == "a" else r[r.index >= "2023-01-01"])

seg_ok = True
for which in ("a", "b"):
    a, b = seg(r_main, which), seg(r_6040, which)
    if not (a["Calmar"] >= b["Calmar"] * 0.95 or a["maxDD"] >= b["maxDD"] - 1e-12):
        seg_ok = False

# 压舱年 / 2020-22 Calmar 低于 60/40
years = sorted(set(r_main.index.year))
year_fail = []
for y in years:
    def yr(r, y):
        s = r[r.index.year == y]
        return mf.stats(s) if len(s) > 5 else None
    a, b = yr(r_main, y), yr(r_6040, y)
    if a and b and a["Calmar"] < b["Calmar"]:
        year_fail.append((y, a["Calmar"], b["Calmar"]))
seg2022_fail = seg(r_main, "a")["Calmar"] < seg(r_6040, "a")["Calmar"]

# 压力期
stress = [("2020-02", "2020-02-01", "2020-03-31"), ("2021-09→2022-10", "2021-09-01", "2022-10-31"),
          ("2022-03", "2022-02-15", "2022-04-30"), ("2024-01", "2024-01-01", "2024-02-15"),
          ("下跌长段", "2021-09-01", "2024-09-30")]
# 核心/卫星相关 + DD
W_core = {dd: core_weights(dd, 1.0) for dd in reb}
W_sat = {dd: ({c: v for c, v in W_b4[dd].items()} if W_b4[dd] else {MF: 1.0}) for dd in reb}
r_core, _, _ = mf.run_weekly(W_core)
r_sat, _, _ = mf.run_weekly(W_sat)
corr_rows = []
stress_fail = False
for n, a, b in stress:
    both = pd.concat([r_core.rename("c"), r_sat.rename("s")], axis=1).loc[a:b].dropna()
    wk = both.groupby(both.index.to_period("W-FRI")).sum()
    rho = float(wk["c"].corr(wk["s"])) if len(wk) > 5 else np.nan
    d1, d0 = mf.mdd(r_main, a, b), mf.mdd(r_6040, a, b)
    deep = d0 - d1  # positive if stack deeper (more negative d1)
    # 深于60/40超过1pp：d1 < d0 - 0.01
    if d1 < d0 - 0.01:
        stress_fail = True
    corr_rows.append(dict(window=n, rho=rho, stack_dd=d1, c6040_dd=d0, deep_pp=d0 - d1))
Corr = pd.DataFrame(corr_rows)
Corr.to_csv(f"{OUT}/stress_corr.csv", index=False)

success = mdd_ok and cal_ok and seg_ok
falsified = (not success) or seg2022_fail or bool(year_fail) or stress_fail
# 证伪：任一压舱年（或2020-22）Calmar低于60/40，或压力期回撤深于60/40超过1pp
# 也若成功闸不过则证伪
reasons = []
if not mdd_ok:
    reasons.append(f"MDD {sm['maxDD']:.1%} 深于60/40 {s60['maxDD']:.1%} 超过0.5pp持平带（gap={dd_gap*100:+.1f}pp）")
if not cal_ok:
    reasons.append(f"Calmar {sm['Calmar']:.2f} < 60/40×0.95={s60['Calmar']*0.95:.2f}")
if not seg_ok:
    reasons.append("两分段存在劣于60/40")
if seg2022_fail:
    reasons.append(f"2020–22 Calmar {seg(r_main,'a')['Calmar']:.2f} < 60/40 {seg(r_6040,'a')['Calmar']:.2f}")
if year_fail:
    reasons.append("压舱年Calmar低于60/40: " + ", ".join(f"{y}({a:.2f}<{b:.2f})" for y, a, b in year_fail))
if stress_fail:
    bad = Corr[Corr.apply(lambda r: r.stack_dd < r.c6040_dd - 0.01, axis=1)]
    reasons.append("压力期回撤深于60/40>1pp: " + ", ".join(f"{r.window}({r.deep_pp*100:+.1f}pp)" for r in bad.itertuples()))

if success and not seg2022_fail and not year_fail and not stress_fail:
    falsified = False
    reasons = []

verdict = "**证伪**" if falsified else "**未证伪/达成功闸**"
fal = ("；".join(reasons) if reasons else f"MDD持平/更浅；Calmar {sm['Calmar']:.2f}≥{s60['Calmar']*0.95:.2f}；分段与压力期过") + ("。证伪成立。" if falsified else "。达成功标准。")

sat_on_pct = float(np.mean(list(on_main.values())))
sat_contrib = (r_main - r_off).sum()

e._bench = {**e.benches(), "池等权(318有价,周调,0.2%RT)": (r_st, to_st, ex_st)}
at = A.attribute(ID, "MF-STACK-v2主版", lambda i, dd: W_main.get(dd, {}), OUT, True)
attr_md = at["md"] + f"""

### 合层专项
- 卫星开启周 **{sat_on_pct:.1%}**（B20≥45%）
- 相对卫星强制关算术贡献 {sat_contrib:+.1%}
- vs 固定60/40：MDD gap {dd_gap*100:+.1f}pp（≥−0.5pp 算持平）；Calmar {sm['Calmar']:.2f} vs {s60['Calmar']:.2f}
- 均权益仓 x̄={xbar:.2f}
"""

main = "MF-STACK-v2 核心85%+卫星15%B4·B20≥45%(主版)"
M = pd.DataFrame([mf.row(k, *v[:3]) for k, v in books.items()])
pd.Series(dict(sat_on_pct=sat_on_pct, mdd_ok=mdd_ok, cal_ok=cal_ok, seg_ok=seg_ok,
               falsified=falsified, dd_gap=dd_gap, xbar=xbar, sat_contrib=sat_contrib,
               b60_on=float((B60.reindex(reb) >= 0.45).mean()))).to_csv(f"{OUT}/diag.csv")

report = HYPO + f"""
## 1. 准则原文
核心 85% 固定 60/40（T-MA60:B1）；卫星 ≤15% MF-B4，breadth 开才上。成功：MDD≤60/40（深≤0.5pp 持平）且 Calmar≥×0.95；两分段不劣。证伪：压舱年/2020–22 Calmar 低于 60/40，或压力期回撤深于 60/40 >1pp。

## 2. 实现要点
- 同 v1 构造，仅卫星预算 15%（邻档 10%/20%）；breadth=冠军 MA20≥45%；旁注 MA60 与「核心权益腿利用率<50%才开卫星」。
- {mf.START}→{mf.END}；0.2%RT；L≤1。

## 3. 主表
{mf.metrics_table(M, main)}

### 成功闸 vs 固定60/40
- MDD：STACK {sm['maxDD']:.1%} vs 60/40 {s60['maxDD']:.1%}（gap {dd_gap*100:+.1f}pp；持平带 −0.5pp）：{'过' if mdd_ok else '不过'}
- Calmar：{sm['Calmar']:.2f} vs ×0.95门 {s60['Calmar']*0.95:.2f}：{'过' if cal_ok else '不过'}
- 两分段不劣：{'是' if seg_ok else '否'}（20–22 {seg(r_main,'a')['Calmar']:.2f}/{seg(r_main,'a')['maxDD']:.1%} vs {seg(r_6040,'a')['Calmar']:.2f}/{seg(r_6040,'a')['maxDD']:.1%}；23–26 {seg(r_main,'b')['Calmar']:.2f} vs {seg(r_6040,'b')['Calmar']:.2f}）
- 卫星开启周 **{sat_on_pct:.1%}**；算术贡献 {sat_contrib:+.1%}

### 压力期
| 窗口 | ρ(核心,卫星) | STACK DD | 60/40 DD | 深于核心(pp) |
|---|---:|---:|---:|---:|
""" + "\n".join(
    f"| {r.window} | {r.rho:.2f} | {mf.fmt_pct(r.stack_dd)} | {mf.fmt_pct(r.c6040_dd)} | {r.deep_pp*100:+.1f} |"
    for r in Corr.itertuples()
) + f"""

### 逐年
"""
ks_y = [main, "固定60/40(T-MA60:B1)", "旁注 核心85%+卫星强制关", "纯B4逆波动(卫星腿)"]
Y = pd.concat([mf.yearly(books[k][0]).assign(book=k) for k in ks_y])
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

mf.deliver(ID, books, main, f"{ID}（核心85%+卫星15%，0.2%RT）", report, attr_md)
M.to_csv(f"{OUT}/metrics.csv", index=False)
pickle.dump(dict(W_main=W_main, on_main=on_main, falsified=falsified, Corr=Corr), open(f"{OUT}/_res.pkl", "wb"))
print("DONE", verdict, fal, flush=True)
print(M[["book", "ret", "maxDD", "Calmar", "turnover"]].round(3).to_string(), flush=True)
print("year_fail", year_fail, flush=True)
