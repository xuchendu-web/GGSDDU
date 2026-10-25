#!/usr/bin/env python3
"""MF-STACK-v3：固定60/40核心 + 卫星仅在核心权益腿利用率<50%时错峰开启。"""
import os, sys, pickle, numpy as np, pandas as pd
sys.path.insert(0, "/workspace/etf-multifreq/engine")
sys.path.insert(0, "/workspace/etf-trend/engine")
import mf_common as mf
import mom_engine as e
import trend as t
import attribution as A
from pathlib import Path

ID = "MF-STACK-v3"
OUT = f"{mf.OUT_ROOT}/{ID}"
Path(OUT).mkdir(parents=True, exist_ok=True)

HYPO = """## 0. 假设与证伪（开跑前写死）
- **假设**：卫星与核心权益「错峰」——仅当宽基趋势仓 < 0.30 总组合（权益预算 60% 的 50%）时开 B4，权重=min(15%, 腾出权益预算)，可抬收益且 MDD 不深于固定 60/40。
- **成功**：MDD ≤ 60/40（深≤0.5pp 持平）且 Calmar≥×0.95；两分段不劣；压力期 2020-02 与 2021-09→2022-10 回撤不深于 60/40 超过 1pp。
- **证伪**：开启周 <10% 且收益增量 <3pp；或任一压舱年/压力期回撤明显恶化。
- **开关**：主版不用 breadth；breadth 仅邻档双条件。
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
    if loc < look: return {c: 1 / len(codes) for c in codes}
    sig = P[codes].iloc[loc-look:loc].pct_change().iloc[1:].std().replace(0, np.nan)
    inv = (1.0 / sig).dropna()
    inv = inv[[c for c in codes if c in inv.index]]
    if inv.empty or inv.sum() <= 0: return {c: 1 / len(codes) for c in codes}
    return (inv / inv.sum()).to_dict()

W_b4 = {}
for dd in reb:
    i = gi[dd]
    W_b4[dd] = invvol_w(dd, picks_xs(i, 5), 60) if i >= 52 else {}

def tm_long_frac(dd):
    tw = w_tm.get(dd, {MF: 1.0})
    return sum(v for c, v in tw.items() if c != MF)  # = n_long/n_pool ∈ [0,1]

def build(util_thr=0.50, sat_cap=0.15, require_breadth=False, eq_budget=0.60, bond_w=0.40):
    """
    组合：债 bond_w 恒定 B1；权益预算 eq_budget：
      - 宽基趋势实际仓 = eq_budget * long_frac
      - 若 long_frac < util_thr（即趋势仓 < eq_budget*util_thr，默认 <0.30）：
          sat = min(sat_cap, eq_budget - 趋势仓)
        否则 sat=0
      - 余下权益预算 → 511880
    """
    W, meta = {}, []
    for dd in reb:
        lf = tm_long_frac(dd)
        trend_w = eq_budget * lf  # 宽基趋势仓（总组合）
        freed = eq_budget - trend_w
        allow = lf < util_thr
        if require_breadth:
            try:
                bv = float(B20.loc[dd]) if dd in B20.index else np.nan
            except Exception:
                bv = np.nan
            allow = allow and (not pd.isna(bv)) and (bv >= 0.45)
        sat_w = min(sat_cap, freed) if allow else 0.0
        if sat_w > 0 and not W_b4.get(dd):
            sat_w = 0.0
            allow = False
        # T-MA60 权益部分：按册内非MF权重缩放至 trend_w
        tw = w_tm.get(dd, {MF: 1.0})
        eq_part = {c: v for c, v in tw.items() if c != MF}
        sume = sum(eq_part.values())
        ww = {}
        if sume > 0 and trend_w > 0:
            ww = {c: eq_part[c] / sume * trend_w for c in eq_part}
        # 卫星
        if sat_w > 0:
            for c, v in W_b4[dd].items():
                ww[c] = ww.get(c, 0.0) + v * sat_w
        # 债
        for c in B1:
            ww[c] = ww.get(c, 0.0) + bond_w / 2
        # 现金/货币填权益预算剩余
        mf_w = eq_budget - trend_w - sat_w
        if mf_w > 1e-12:
            ww[MF] = ww.get(MF, 0.0) + mf_w
        # 数值归一（应≈1）
        tot = sum(ww.values())
        if abs(tot - 1.0) > 1e-6 and tot > 0:
            ww = {c: v / tot for c, v in ww.items()}
        W[dd] = ww
        meta.append(dict(date=dd, long_frac=lf, trend_w=trend_w, sat_w=sat_w, freed=freed, on=sat_w > 0))
    return W, pd.DataFrame(meta).set_index("date")

# 主版
W_main, meta_main = build(0.50, 0.15, False)
r_main, to_main, ex_main = mf.run_weekly(W_main)
on_pct = float(meta_main.on.mean())
print(f"v3主版 sat_on={on_pct:.1%} avg_sat_w={meta_main.sat_w.mean():.3f}",
      {k: round(float(v), 4) for k, v in mf.stats(r_main).items()}, flush=True)

specs = {
    "邻档 腾挪阈值30%": build(0.30, 0.15, False),
    "邻档 腾挪阈值70%": build(0.70, 0.15, False),
    "邻档 卫星上限10%": build(0.50, 0.10, False),
    "邻档 卫星上限20%": build(0.50, 0.20, False),
    "邻档 腾挪+breadth双条件": build(0.50, 0.15, True),
}
books = {"MF-STACK-v3 错峰卫星min(15%,腾出)·主版": (r_main, to_main, ex_main)}
metas = {"主版": meta_main}
for lab, (Ww, meta) in specs.items():
    rr, tt, ee = mf.run_weekly(Ww)
    books[lab] = (rr, tt, ee)
    metas[lab] = meta
    print(lab, f"on={meta.on.mean():.1%}", {k: round(float(v), 4) for k, v in mf.stats(rr).items()}, flush=True)

# 对照
r_tm, to_tm, ex_tm = t.run(w_tm)
# 固定60/40 = util_thr=0 永不卫星 等价 build with sat always 0
W_6040, _ = build(0.0, 0.15, False)  # lf < 0 never → sat always 0
# wait util_thr=0 means lf < 0 never true → good
r_6040, to_6040, ex_6040 = mf.run_weekly(W_6040)
r_b4, to_b4, ex_b4 = mf.run_weekly(W_b4)
ch = mf.champ()

# v2 主版净值
v2nav = pd.read_csv("/workspace/etf-multifreq/MF-STACK-v2/nav.csv", index_col=0, parse_dates=True)
col_v2 = [c for c in v2nav.columns if "v2" in c and "主版" in c][0]
r_v2 = v2nav[col_v2].pct_change().fillna(0)
v2m = pd.read_csv("/workspace/etf-multifreq/MF-STACK-v2/metrics.csv")
row_v2 = v2m[v2m.book.str.contains("v2") & v2m.book.str.contains("主版")].iloc[0]

books.update({
    "固定60/40(T-MA60:B1)": (r_6040, to_6040, ex_6040),
    "纯周频T-MA60(同A宽基)": (r_tm, to_tm, ex_tm),
    "纯B4逆波动(卫星腿)": (r_b4, to_b4, ex_b4),
    "MF-STACK-v2主版(对照)": (r_v2, float(row_v2.turnover), float(row_v2.avg_expo) if pd.notna(row_v2.avg_expo) else np.nan),
    "冠军同引擎(研究副本)": ch,
})

sm, s60 = mf.stats(r_main), mf.stats(r_6040)
dd_gap = sm["maxDD"] - s60["maxDD"]
mdd_ok = sm["maxDD"] >= s60["maxDD"] - 0.005
cal_ok = sm["Calmar"] >= s60["Calmar"] * 0.95

def seg(r, which):
    return mf.stats(r[r.index <= "2022-12-31"] if which == "a" else r[r.index >= "2023-01-01"])

seg_ok = True
for which in ("a", "b"):
    a, b = seg(r_main, which), seg(r_6040, which)
    if not (a["Calmar"] >= b["Calmar"] * 0.95 or a["maxDD"] >= b["maxDD"] - 1e-12):
        seg_ok = False

# 压力期指定两窗
stress = [("2020-02", "2020-02-01", "2020-03-31"), ("2021-09→2022-10", "2021-09-01", "2022-10-31"),
          ("2022-03", "2022-02-15", "2022-04-30"), ("2024-01", "2024-01-01", "2024-02-15"),
          ("下跌长段", "2021-09-01", "2024-09-30")]
# 相关：核心=60/40，卫星=B4
r_core, _, _ = mf.run_weekly(W_6040)
r_sat, _, _ = mf.run_weekly(W_b4)
corr_rows = []
stress_fail = False
for n, a, b in stress:
    both = pd.concat([r_core.rename("c"), r_sat.rename("s")], axis=1).loc[a:b].dropna()
    wk = both.groupby(both.index.to_period("W-FRI")).sum()
    rho = float(wk["c"].corr(wk["s"])) if len(wk) > 5 else np.nan
    d1, d0 = mf.mdd(r_main, a, b), mf.mdd(r_6040, a, b)
    if n in ("2020-02", "2021-09→2022-10") and d1 < d0 - 0.01:
        stress_fail = True
    corr_rows.append(dict(window=n, rho=rho, stack_dd=d1, c6040_dd=d0, deep_pp=d0 - d1))
# 全样本相关
both_all = pd.concat([r_core.rename("c"), r_sat.rename("s")], axis=1).dropna()
wk_all = both_all.groupby(both_all.index.to_period("W-FRI")).sum()
rho_all = float(wk_all["c"].corr(wk_all["s"]))
Corr = pd.DataFrame(corr_rows)
Corr.to_csv(f"{OUT}/stress_corr.csv", index=False)
meta_main.to_csv(f"{OUT}/weekly_meta.csv")

# 收益增量
ret_gain = sm["ret"] - s60["ret"]
# 压舱年
year_fail = []
for y in sorted(set(r_main.index.year)):
    def yr(r, y):
        s = r[r.index.year == y]
        return mf.stats(s) if len(s) > 5 else None
    a, b = yr(r_main, y), yr(r_6040, y)
    if a and b and a["maxDD"] < b["maxDD"] - 0.01:  # 回撤明显恶化 >1pp
        year_fail.append((y, "dd", a["maxDD"], b["maxDD"]))
    if a and b and a["Calmar"] < b["Calmar"] - 0.05 and a["maxDD"] < b["maxDD"]:
        year_fail.append((y, "cal+dd", a["Calmar"], b["Calmar"]))

low_on = on_pct < 0.10
low_gain = ret_gain < 0.03
sparse_fail = low_on and low_gain

success = mdd_ok and cal_ok and seg_ok and not stress_fail
falsified = (not success) or sparse_fail or bool(year_fail) or stress_fail

reasons = []
if not mdd_ok:
    reasons.append(f"MDD {sm['maxDD']:.1%} 深于60/40 {s60['maxDD']:.1%}（gap {dd_gap*100:+.1f}pp）")
if not cal_ok:
    reasons.append(f"Calmar {sm['Calmar']:.2f} < ×0.95门 {s60['Calmar']*0.95:.2f}")
if not seg_ok:
    reasons.append("两分段存在劣于60/40")
if stress_fail:
    bad = [r for r in Corr.itertuples() if r.window in ("2020-02", "2021-09→2022-10") and r.stack_dd < r.c6040_dd - 0.01]
    reasons.append("指定压力期回撤深>1pp: " + ", ".join(f"{r.window}({r.deep_pp*100:+.1f}pp)" for r in bad))
if sparse_fail:
    reasons.append(f"开启周 {on_pct:.1%}<10% 且收益增量 {ret_gain*100:+.1f}pp<3pp")
if year_fail:
    reasons.append("压舱年回撤/Calmar恶化: " + str(year_fail))

if success and not sparse_fail and not year_fail:
    falsified = False
    reasons = []

verdict = "**证伪**" if falsified else "**未证伪/达成功闸**"
fal = ("；".join(reasons) if reasons else
       f"MDD持平/更浅 gap {dd_gap*100:+.1f}pp；Calmar {sm['Calmar']:.2f}；开启周 {on_pct:.1%}；增量 {ret_gain*100:+.1f}pp") + (
       "。证伪成立。" if falsified else "。达成功标准。")

# 卫星贡献：主版 − 60/40
sat_contrib = (r_main - r_6040).sum()

e._bench = {**e.benches()}
at = A.attribute(ID, "MF-STACK-v3主版", lambda i, dd: W_main.get(dd, {}), OUT, True)
attr_md = at["md"] + f"""

### 合层专项
- 开启周 **{on_pct:.1%}**；均卫星权重 {meta_main.sat_w.mean():.3f}；开启时均卫星权重 {meta_main.loc[meta_main.on,'sat_w'].mean() if meta_main.on.any() else 0:.3f}
- 相对固定60/40 算术贡献 {sat_contrib:+.1%}；收益增量 {ret_gain*100:+.1f}pp
- 核心–卫星周相关：全样本 {rho_all:.2f}；压力期见 stress_corr.csv
- MDD gap vs 60/40 {dd_gap*100:+.1f}pp
"""

main = "MF-STACK-v3 错峰卫星min(15%,腾出)·主版"
M = pd.DataFrame([mf.row(k, *v[:3]) for k, v in books.items()])
pd.Series(dict(on_pct=on_pct, ret_gain=ret_gain, mdd_ok=mdd_ok, cal_ok=cal_ok, seg_ok=seg_ok,
               falsified=falsified, dd_gap=dd_gap, rho_all=rho_all, sat_contrib=sat_contrib,
               avg_sat_w=float(meta_main.sat_w.mean()))).to_csv(f"{OUT}/diag.csv")

report = HYPO + f"""
## 1. 准则原文
核心固定 60/40（T-MA60:B1）；卫星 B4 仅当宽基趋势仓 < 0.30 总组合时开，权重=min(15%, 腾出权益预算)；不用 breadth 主开关。

## 2. 实现要点
- 债 40% 恒定；权益预算 60% = 趋势仓(0.6×long_frac) + 卫星(条件) + 511880。
- 腾挪条件：long_frac < 0.50 ⇔ 趋势仓 < 0.30。
- 邻档：阈值 30%/70%；卫星上限 10%/20%；腾挪+breadth 双条件。
- breadth 不再作主开关（与 v1/v2 不同）。

## 3. 主表
{mf.metrics_table(M, main)}

### 成功闸
- MDD：{sm['maxDD']:.1%} vs 60/40 {s60['maxDD']:.1%}（gap {dd_gap*100:+.1f}pp）：{'过' if mdd_ok else '不过'}
- Calmar：{sm['Calmar']:.2f} vs 门 {s60['Calmar']*0.95:.2f}：{'过' if cal_ok else '不过'}
- 分段不劣：{'是' if seg_ok else '否'}（20–22 {seg(r_main,'a')['Calmar']:.2f} vs {seg(r_6040,'a')['Calmar']:.2f}；23–26 {seg(r_main,'b')['Calmar']:.2f} vs {seg(r_6040,'b')['Calmar']:.2f}）
- 开启周 **{on_pct:.1%}**；收益增量 vs 60/40 **{ret_gain*100:+.1f}pp**；算术贡献 {sat_contrib:+.1%}
- 核心–卫星全样本周相关 **{rho_all:.2f}**

### 压力期
| 窗口 | ρ | STACK DD | 60/40 DD | 深(pp) |
|---|---:|---:|---:|---:|
""" + "\n".join(
    f"| {r.window} | {r.rho:.2f} | {mf.fmt_pct(r.stack_dd)} | {mf.fmt_pct(r.c6040_dd)} | {r.deep_pp*100:+.1f} |"
    for r in Corr.itertuples()
) + f"""

### 逐年
"""
ks_y = [main, "固定60/40(T-MA60:B1)", "MF-STACK-v2主版(对照)", "纯B4逆波动(卫星腿)"]
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

mf.deliver(ID, books, main, f"{ID}（错峰卫星，0.2%RT）", report, attr_md)
M.to_csv(f"{OUT}/metrics.csv", index=False)
pickle.dump(dict(W_main=W_main, meta=meta_main, falsified=falsified, Corr=Corr, rho_all=rho_all),
            open(f"{OUT}/_res.pkl", "wb"))
print("DONE", verdict, fal, flush=True)
print(M[["book", "ret", "maxDD", "Calmar", "turnover"]].round(3).to_string(), flush=True)
print(meta_main.describe().round(3), flush=True)
