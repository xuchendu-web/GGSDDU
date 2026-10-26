#!/usr/bin/env python3
"""MF-STACK-v4：腾挪∧breadth 双条件主版。"""
import os, sys, pickle, numpy as np, pandas as pd
sys.path.insert(0, "/workspace/etf-multifreq/engine")
sys.path.insert(0, "/workspace/etf-trend/engine")
import mf_common as mf
import mom_engine as e
import trend as t
import attribution as A
import matplotlib; matplotlib.use("Agg"); import matplotlib.pyplot as plt
plt.rcParams["font.sans-serif"]=["Noto Sans CJK SC","WenQuanYi Zen Hei","DejaVu Sans"]
plt.rcParams["axes.unicode_minus"]=False
from pathlib import Path

ID = "MF-STACK-v4"
OUT = f"{mf.OUT_ROOT}/{ID}"
Path(OUT).mkdir(parents=True, exist_ok=True)

HYPO = """## 0. 假设与证伪（开跑前写死）
- **假设**：腾挪（趋势仓<0.30）∧ breadth≥45% 双条件开 B4，可在压舱不坏的前提下贡献增量。
- **成功**：MDD≤60/40（深≤0.5pp持平）且 Calmar≥×0.95；两分段不劣；2020-02 与 2021-09→2022-10 深≤1pp。
- **证伪**：开启周<10%且相对60/40收益增量<5pp；或邻档过半 DD 深于60/40超过1pp；或2020–22 Calmar低于60/40。
"""

D = mf.data()
P, aw, ind, MF = D["P"], D["aw"], D["ind"], mf.MF
B1 = ["511010", "511260"]
gi, reb = D["gi"], D["reb"]
KEEP_AW, KEEP_IND = set(aw), set(ind)

face = pd.read_csv(e.FACE)
face["date"] = pd.to_datetime(face.date.astype(str).str[:10])
bface = face.set_index("date")["b"] if "b" in face.columns else None
bn = pd.read_csv("/workspace/etf-momentum/data_v1016/breadth_ma20_v1016.csv", parse_dates=["date"]).set_index("date").b
B20 = bface[bface.index <= "2026-09-24"].combine_first(bn[bn.index > "2026-09-24"]) if bface is not None else bn

w_tm, _ = t.weights(t.s_ma(60), keep=KEEP_AW)

def picks_xs(i, N=5):
    s = e.mom(i, 52, 1)
    s = s[[c for c in s.index if c in KEEP_IND]].dropna()
    return e.topn(s, N) if len(s) else []

def invvol_w(dd, codes, look=60):
    if not codes or dd not in P.index: return {}
    loc = P.index.get_loc(dd)
    if loc < look: return {c: 1/len(codes) for c in codes}
    sig = P[codes].iloc[loc-look:loc].pct_change().iloc[1:].std().replace(0, np.nan)
    inv = (1.0/sig).dropna()
    inv = inv[[c for c in codes if c in inv.index]]
    if inv.empty or inv.sum()<=0: return {c: 1/len(codes) for c in codes}
    return (inv/inv.sum()).to_dict()

W_b4 = {dd: (invvol_w(dd, picks_xs(gi[dd], 5), 60) if gi[dd]>=52 else {}) for dd in reb}

def tm_lf(dd):
    tw = w_tm.get(dd, {MF: 1.0})
    return sum(v for c, v in tw.items() if c != MF)

def build(util_thr=0.50, sat_cap=0.15, use_tengnuo=True, use_breadth=True, eq_budget=0.60, bond_w=0.40):
    W, meta = {}, []
    for dd in reb:
        lf = tm_lf(dd)
        trend_w = eq_budget * lf
        freed = eq_budget - trend_w
        allow = True
        if use_tengnuo:
            allow = allow and (lf < util_thr)
        if use_breadth:
            try:
                bv = float(B20.loc[dd]) if dd in B20.index else np.nan
            except Exception:
                bv = np.nan
            allow = allow and (not pd.isna(bv)) and (bv >= 0.45)
        sat_w = min(sat_cap, freed) if allow else 0.0
        if sat_w > 0 and not W_b4.get(dd):
            sat_w = 0.0
        tw = w_tm.get(dd, {MF: 1.0})
        eq_part = {c: v for c, v in tw.items() if c != MF}
        sume = sum(eq_part.values())
        ww = {c: eq_part[c]/sume*trend_w for c in eq_part} if sume>0 and trend_w>0 else {}
        if sat_w > 0:
            for c, v in W_b4[dd].items():
                ww[c] = ww.get(c, 0.0) + v*sat_w
        for c in B1:
            ww[c] = ww.get(c, 0.0) + bond_w/2
        mf_w = eq_budget - trend_w - sat_w
        if mf_w > 1e-12:
            ww[MF] = ww.get(MF, 0.0) + mf_w
        tot = sum(ww.values())
        if tot > 0 and abs(tot-1)>1e-6:
            ww = {c: v/tot for c, v in ww.items()}
        W[dd] = ww
        meta.append(dict(date=dd, long_frac=lf, trend_w=trend_w, sat_w=sat_w, on=sat_w>0))
    return W, pd.DataFrame(meta).set_index("date")

# 主版：双条件
W_main, meta_main = build(0.50, 0.15, True, True)
r_main, to_main, ex_main = mf.run_weekly(W_main)
on_pct = float(meta_main.on.mean())
print(f"v4主版 on={on_pct:.1%} avg_sat={meta_main.sat_w.mean():.3f}",
      {k: round(float(v),4) for k,v in mf.stats(r_main).items()}, flush=True)

specs = {
    "邻档 卫星上限10%": build(0.50, 0.10, True, True),
    "邻档 卫星上限20%": build(0.50, 0.20, True, True),
    "邻档 腾挪阈值30%": build(0.30, 0.15, True, True),
    "邻档 腾挪阈值70%": build(0.70, 0.15, True, True),
    "邻档 只breadth(复验)": build(0.50, 0.15, False, True),
    "邻档 只腾挪(复验)": build(0.50, 0.15, True, False),
}
books = {"MF-STACK-v4 腾挪∧breadth·主版": (r_main, to_main, ex_main)}
neigh_dd = {}
for lab, (Ww, meta) in specs.items():
    rr, tt, ee = mf.run_weekly(Ww)
    books[lab] = (rr, tt, ee)
    neigh_dd[lab] = mf.stats(rr)["maxDD"]
    print(lab, f"on={meta.on.mean():.1%}", {k: round(float(v),4) for k,v in mf.stats(rr).items()}, flush=True)

# 对照
r_tm, to_tm, ex_tm = t.run(w_tm)
W_6040, _ = build(0.0, 0.15, True, False)  # never sat
r_6040, to_6040, ex_6040 = mf.run_weekly(W_6040)
r_b4, to_b4, ex_b4 = mf.run_weekly(W_b4)
ch = mf.champ()

# 同均仓固定对照
eq_codes = set(aw)|set(ind)
xbar = float(np.mean([sum(v for c,v in W_main[dd].items() if c in eq_codes) for dd in reb]))
all_eq = [c for c in eq_codes if c in P.columns]
W_st = {dd: ({c: xbar/len(pl) for c in pl}|{MF:1-xbar}) if (pl:=[c for c in all_eq if not pd.isna(P.at[dd,c])]) else {MF:1.0} for dd in reb}
r_st, to_st, ex_st = mf.run_weekly(W_st)

# v3 主版
v3nav = pd.read_csv("/workspace/etf-multifreq/MF-STACK-v3/nav.csv", index_col=0, parse_dates=True)
col3 = [c for c in v3nav.columns if "v3" in c and "主版" in c][0]
r_v3 = v3nav[col3].pct_change().fillna(0)
v3m = pd.read_csv("/workspace/etf-multifreq/MF-STACK-v3/metrics.csv")
row3 = v3m[v3m.book.str.contains("v3") & v3m.book.str.contains("主版")].iloc[0]

books.update({
    "固定60/40(T-MA60:B1)": (r_6040, to_6040, ex_6040),
    "纯周频T-MA60(同A宽基)": (r_tm, to_tm, ex_tm),
    "纯B4逆波动(卫星腿)": (r_b4, to_b4, ex_b4),
    f"同均仓固定对照(x̄权益={xbar:.2f})": (r_st, to_st, ex_st),
    "MF-STACK-v3主版(对照)": (r_v3, float(row3.turnover), float(row3.avg_expo) if pd.notna(row3.avg_expo) else np.nan),
    "冠军同引擎(研究副本)": ch,
})

sm, s60 = mf.stats(r_main), mf.stats(r_6040)
dd_gap = sm["maxDD"] - s60["maxDD"]
mdd_ok = sm["maxDD"] >= s60["maxDD"] - 0.005
cal_ok = sm["Calmar"] >= s60["Calmar"] * 0.95

def seg(r, which):
    return mf.stats(r[r.index<="2022-12-31"] if which=="a" else r[r.index>="2023-01-01"])
seg_ok = all(
    (seg(r_main,w)["Calmar"] >= seg(r_6040,w)["Calmar"]*0.95) or (seg(r_main,w)["maxDD"] >= seg(r_6040,w)["maxDD"]-1e-12)
    for w in ("a","b")
)
cal2022_fail = seg(r_main,"a")["Calmar"] < seg(r_6040,"a")["Calmar"]

stress = [("2020-02","2020-02-01","2020-03-31"),("2021-09→2022-10","2021-09-01","2022-10-31"),
          ("2022-03","2022-02-15","2022-04-30"),("2024-01","2024-01-01","2024-02-15"),("下跌长段","2021-09-01","2024-09-30")]
r_core, _, _ = mf.run_weekly(W_6040)
r_sat, _, _ = mf.run_weekly(W_b4)
corr_rows=[]; stress_fail=False
for n,a,b in stress:
    both=pd.concat([r_core.rename("c"), r_sat.rename("s")],axis=1).loc[a:b].dropna()
    wk=both.groupby(both.index.to_period("W-FRI")).sum()
    rho=float(wk["c"].corr(wk["s"])) if len(wk)>5 else np.nan
    d1,d0=mf.mdd(r_main,a,b), mf.mdd(r_6040,a,b)
    if n in ("2020-02","2021-09→2022-10") and d1 < d0 - 0.01:
        stress_fail=True
    corr_rows.append(dict(window=n, rho=rho, stack_dd=d1, c6040_dd=d0, deep_pp=d0-d1))
rho_all=float(pd.concat([r_core.rename("c"),r_sat.rename("s")],axis=1).dropna().groupby(lambda x: x.to_period("W-FRI")).sum().corr().iloc[0,1])
Corr=pd.DataFrame(corr_rows); Corr.to_csv(f"{OUT}/stress_corr.csv", index=False)
meta_main.to_csv(f"{OUT}/weekly_meta.csv")

ret_gain = sm["ret"] - s60["ret"]
sparse_fail = (on_pct < 0.10) and (ret_gain < 0.05)
# 邻档过半 DD 深于60/40超过1pp
neigh_deep = sum(1 for lab,dd in neigh_dd.items() if dd < s60["maxDD"] - 0.01)
neigh_fail = neigh_deep > len(neigh_dd)/2

success = mdd_ok and cal_ok and seg_ok and not stress_fail
falsified = (not success) or sparse_fail or neigh_fail or cal2022_fail

reasons=[]
if not mdd_ok: reasons.append(f"MDD {sm['maxDD']:.1%} 深于60/40 {s60['maxDD']:.1%}（gap {dd_gap*100:+.1f}pp）")
if not cal_ok: reasons.append(f"Calmar {sm['Calmar']:.2f}<门{s60['Calmar']*0.95:.2f}")
if not seg_ok: reasons.append("两分段存在劣于60/40")
if stress_fail:
    bad=[r for r in Corr.itertuples() if r.window in ("2020-02","2021-09→2022-10") and r.stack_dd<r.c6040_dd-0.01]
    reasons.append("指定压力期深>1pp: "+", ".join(f"{r.window}({r.deep_pp*100:+.1f}pp)" for r in bad))
if sparse_fail: reasons.append(f"开启周{on_pct:.1%}<10%且增量{ret_gain*100:+.1f}pp<5pp（噪声）")
if neigh_fail: reasons.append(f"邻档{neigh_deep}/{len(neigh_dd)}只DD深于60/40>1pp")
if cal2022_fail: reasons.append(f"2020–22 Calmar {seg(r_main,'a')['Calmar']:.2f}<60/40 {seg(r_6040,'a')['Calmar']:.2f}")

if success and not sparse_fail and not neigh_fail and not cal2022_fail:
    falsified=False; reasons=[]

verdict = "**证伪**" if falsified else "**未证伪/达成功闸**"
fal = ("；".join(reasons) if reasons else f"MDD gap {dd_gap*100:+.1f}pp；Calmar {sm['Calmar']:.2f}；开{on_pct:.1%}；增量{ret_gain*100:+.1f}pp") + ("。证伪成立。" if falsified else "。达成功标准。")

sat_contrib = (r_main - r_6040).sum()
e._bench = {**e.benches(), "池等权(318有价,周调,0.2%RT)": (r_st, to_st, ex_st)}
at = A.attribute(ID, "MF-STACK-v4主版", lambda i,dd: W_main.get(dd,{}), OUT, True)
attr_md = at["md"] + f"""

### 合层专项
- 开启周 **{on_pct:.1%}**；均卫星权重 {meta_main.sat_w.mean():.3f}
- 相对60/40 收益增量 {ret_gain*100:+.1f}pp；算术贡献 {sat_contrib:+.1%}
- 核心–卫星全样本周相关 {rho_all:.2f}；MDD gap {dd_gap*100:+.1f}pp；x̄权益={xbar:.2f}
"""

main="MF-STACK-v4 腾挪∧breadth·主版"
M=pd.DataFrame([mf.row(k,*v[:3]) for k,v in books.items()])
pd.Series(dict(on_pct=on_pct, ret_gain=ret_gain, mdd_ok=mdd_ok, cal_ok=cal_ok, seg_ok=seg_ok,
               falsified=falsified, dd_gap=dd_gap, rho_all=rho_all, sat_contrib=sat_contrib,
               xbar=xbar, neigh_deep=neigh_deep)).to_csv(f"{OUT}/diag.csv")

report = HYPO + f"""
## 1. 准则原文
核心固定60/40；卫星 B4 需同时满足腾挪（趋势仓<0.30）与 breadth≥45%（冠军MA20）；sat=min(15%,腾出)。

## 2. 实现要点
- 同 v3 仓位会计；主开关 = 腾挪 ∧ breadth（v3 邻档升主版）。
- 邻档：上限10/20；阈值30/70；只breadth、只腾挪复验。
- {mf.START}→{mf.END}；0.2%RT。

## 3. 主表
{mf.metrics_table(M, main)}

### 成功闸
- MDD {sm['maxDD']:.1%} vs 60/40 {s60['maxDD']:.1%}（gap {dd_gap*100:+.1f}pp）：{'过' if mdd_ok else '不过'}
- Calmar {sm['Calmar']:.2f} vs 门 {s60['Calmar']*0.95:.2f}：{'过' if cal_ok else '不过'}
- 分段不劣：{'是' if seg_ok else '否'}；2020–22 Calmar {seg(r_main,'a')['Calmar']:.2f} vs {seg(r_6040,'a')['Calmar']:.2f}
- 开启周 **{on_pct:.1%}**；增量 **{ret_gain*100:+.1f}pp**；算术贡献 {sat_contrib:+.1%}；ρ全样本 {rho_all:.2f}；x̄权益 {xbar:.2f}

### 压力期
| 窗口 | ρ | STACK | 60/40 | 深(pp) |
|---|---:|---:|---:|---:|
""" + "\n".join(f"| {r.window} | {r.rho:.2f} | {mf.fmt_pct(r.stack_dd)} | {mf.fmt_pct(r.c6040_dd)} | {r.deep_pp*100:+.1f} |" for r in Corr.itertuples()) + f"""

### 逐年
"""
ks_y=[main,"固定60/40(T-MA60:B1)","MF-STACK-v3主版(对照)","纯B4逆波动(卫星腿)"]
Y=pd.concat([mf.yearly(books[k][0]).assign(book=k) for k in ks_y])
yp=Y.pivot(index="year",columns="book",values="ret"); yd=Y.pivot(index="year",columns="book",values="mdd")
ks=list(yp.columns)
report+="| 年 | "+" | ".join(ks)+" |\n|---|"+"---|"*len(ks)+"\n"
for y in yp.index:
    report+=f"| {y} | "+" | ".join(f"{yp.at[y,k]:+.1%}/{yd.at[y,k]:.1%}" for k in ks)+" |\n"
report+=f"""
## 4. 结论
{verdict}。{fal}

**证伪/失效句**：{fal}

产物：{OUT}/；不换冠军、不下单。
"""
mf.deliver(ID, books, main, f"{ID}（腾挪∧breadth，0.2%RT）", report, attr_md)
M.to_csv(f"{OUT}/metrics.csv", index=False)
pickle.dump(dict(falsified=falsified, on_pct=on_pct, meta=meta_main, Corr=Corr, sm=sm, s60=s60,
                 ret_gain=ret_gain, dd_gap=dd_gap, books_nav={k:(1+v[0]).cumprod() for k,v in books.items()}),
            open(f"{OUT}/_res.pkl","wb"))
print("DONE", verdict, fal, flush=True)
print(M[["book","ret","maxDD","Calmar","turnover"]].round(3).to_string(), flush=True)

# 返回给后续 SUMMARY
open(f"{OUT}/_verdict.txt","w").write(f"{'FALSIFIED' if falsified else 'PASS'}\n{fal}\n")
