#!/usr/bin/env python3
"""MF-STACK-v1：核心70%固定60/40(T-MA60:B1) + 卫星≤30% MF-B4(breadth门控)。"""
import os, sys, pickle, numpy as np, pandas as pd
sys.path.insert(0, "/workspace/etf-multifreq/engine")
sys.path.insert(0, "/workspace/etf-trend/engine")
import mf_common as mf
import mom_engine as e
import trend as t
import attribution as A
from pathlib import Path

ID = "MF-STACK-v1"
OUT = f"{mf.OUT_ROOT}/{ID}"
Path(OUT).mkdir(parents=True, exist_ok=True)

HYPO = """## 0. 假设与证伪（开跑前写死）
- **假设**：核心固定 60/40（宽基周频 T-MA60 : B1）压舱 + 卫星行业 B4（逆波动）在广度打开时增强，合层 MDD 比最好单腿浅 ≥3pp 且 Calmar 不掉下 ×0.95，两分段均不劣。
- **成功**：MDD 比最好单腿浅 ≥3pp 且 Calmar ≥ 最好单腿 ×0.95；2020–22 与 2023–26 两分段均不劣（Calmar≥单腿×0.95 或 DD 不更深）。
- **证伪**：压力期核心–卫星相关 >0.8 且回撤不改善；或卫星开关重开追高使 2023–26 不优于固定 60/40。
- **breadth 口径**：复用冠军研究副本序列 = **周收 > 周 MA20 池级占比 ≥45%**（`breadth_ma20_v1016.csv` + face 前段）。与 PLAN 原写「MA60」**不一致**；本刀按冠军只读 MA20 执行，旁注自算 MA60≥45% 开启周占比差异。
"""

D = mf.data()
P, aw, ind, MF = D["P"], D["aw"], D["ind"], mf.MF
B1 = ["511010", "511260"]
gi, reb, G = D["gi"], D["reb"], D["G"]
KEEP_AW, KEEP_IND = set(aw), set(ind)

# ---- breadth：冠军口径 MA20 ----
face = pd.read_csv(e.FACE)
face["date"] = pd.to_datetime(face.date.astype(str).str[:10])
bface = face.set_index("date")["b"] if "b" in face.columns else None
bn = pd.read_csv("/workspace/etf-momentum/data_v1016/breadth_ma20_v1016.csv", parse_dates=["date"]).set_index("date").b
if bface is not None:
    B20 = bface[bface.index <= "2026-09-24"].combine_first(bn[bn.index > "2026-09-24"])
else:
    B20 = bn
B20 = B20.reindex(pd.to_datetime(reb)).ffill()  # align; may have NaN early

# 旁注：自算行业+宽基池周线>MA60 占比（与 PLAN 字面）
Wpanel = D["W"]
codes_b = [c for c in list(KEEP_AW | KEEP_IND) if c in Wpanel.columns]
MA60w = Wpanel[codes_b].rolling(12, min_periods=12).mean()  # ~12 weeks ≈ 60 trading days-ish; better use daily
# 用日线：每周五用日 MA60
C_all = P[codes_b]
MA60d = C_all.rolling(60, min_periods=60).mean()
b60_list = {}
for dd in reb:
    if dd not in C_all.index:
        continue
    row, ma = C_all.loc[dd], MA60d.loc[dd]
    ok = row.notna() & ma.notna()
    if ok.sum() == 0:
        continue
    b60_list[dd] = float((row[ok] > ma[ok]).mean())
B60 = pd.Series(b60_list)
print(f"B20≥45 开启周 {(B20.reindex(reb)>=0.45).mean():.1%}；旁注B60≥45 {(B60>=0.45).mean():.1%}", flush=True)
print(f"口径说明：冠军=周收>MA20池级≥45%；PLAN写MA60→不一致，主版用冠军MA20。", flush=True)

# ---- 周频 T-MA60（A宽基）----
w_tm, st_tm = t.weights(t.s_ma(60), keep=KEEP_AW)
print("T-MA60 ready", len(w_tm), flush=True)

# ---- B4 逆波动 & 等权（重建，与 MF-B4 一致）----
def picks_xs(i, N=5):
    s = e.mom(i, 52, 1)
    s = s[[c for c in s.index if c in KEEP_IND]].dropna()
    return e.topn(s, N) if len(s) else []

def invvol_w(dd, codes, look=60):
    if not codes or dd not in P.index:
        return {}
    loc = P.index.get_loc(dd)
    if loc < look:
        return {c: 1 / len(codes) for c in codes}
    seg = P[codes].iloc[loc - look:loc].pct_change().iloc[1:]
    sig = seg.std().replace(0, np.nan)
    inv = (1.0 / sig).dropna()
    inv = inv[[c for c in codes if c in inv.index]]
    if inv.empty or inv.sum() <= 0:
        return {c: 1 / len(codes) for c in codes}
    inv = inv / inv.sum()
    return inv.to_dict()

W_b4_iv, W_b4_ew = {}, {}
for dd in reb:
    i = gi[dd]
    if i < 52:
        W_b4_iv[dd] = {}; W_b4_ew[dd] = {}; continue
    p = picks_xs(i, 5)
    W_b4_iv[dd] = invvol_w(dd, p, 60)
    W_b4_ew[dd] = {c: 1 / 5 for c in p}

# ---- 核心 60/40 构造（在核心预算内）----
def core_weights(dd, core_frac):
    """core_frac * (0.6 * T-MA60_book + 0.4 * B1)。T-MA60 空仓时其内部已是 511880。"""
    tw = w_tm.get(dd, {MF: 1.0})
    ww = {c: v * core_frac * 0.6 for c, v in tw.items()}
    for c in B1:
        ww[c] = ww.get(c, 0.0) + core_frac * 0.4 / 2
    return ww

def sat_weights(dd, sat_frac, use_iv=True, use_breadth=True, breadth_series=B20, thr=0.45):
    on = True
    if use_breadth:
        bv = breadth_series.get(dd, np.nan) if hasattr(breadth_series, "get") else breadth_series.loc[dd] if dd in breadth_series.index else np.nan
        # Series.get works for index
        try:
            bv = float(breadth_series.loc[dd]) if dd in breadth_series.index else np.nan
        except Exception:
            bv = np.nan
        on = (not pd.isna(bv)) and (bv >= thr)
    if not on:
        return {MF: sat_frac}, False
    base = W_b4_iv.get(dd, {}) if use_iv else W_b4_ew.get(dd, {})
    if not base:
        return {MF: sat_frac}, True
    return {c: v * sat_frac for c, v in base.items()}, True

def merge(a, b):
    out = dict(a)
    for c, v in b.items():
        out[c] = out.get(c, 0.0) + v
    return {c: v for c, v in out.items() if v > 1e-12}

def build_stack(core_frac=0.70, sat_frac=0.30, use_iv=True, use_breadth=True, breadth_series=B20):
    assert abs(core_frac + sat_frac - 1.0) < 1e-9
    W = {}; sat_on = {}
    for dd in reb:
        cw = core_weights(dd, core_frac)
        sw, on = sat_weights(dd, sat_frac, use_iv=use_iv, use_breadth=use_breadth, breadth_series=breadth_series)
        W[dd] = merge(cw, sw)
        sat_on[dd] = on
    return W, sat_on

# 主版 70/30
W_main, on_main = build_stack(0.70, 0.30)
r_main, to_main, ex_main = mf.run_weekly(W_main)
print("STACK 70/30", {k: round(float(v), 4) for k, v in mf.stats(r_main).items()}, f"to={to_main:.2f}", f"sat_on={(np.mean(list(on_main.values()))):.1%}", flush=True)

# 邻档
specs = {
    "邻档 核心/卫星 80/20": build_stack(0.80, 0.20),
    "邻档 核心/卫星 60/40": build_stack(0.60, 0.40),
    "邻档 卫星等权代逆波动": build_stack(0.70, 0.30, use_iv=False),
    "邻档 无breadth开关": build_stack(0.70, 0.30, use_breadth=False),
    "旁注 breadth用MA60≥45%": build_stack(0.70, 0.30, breadth_series=B60),
}
books = {"MF-STACK-v1 核心70%(60/40)+卫星30%B4·B20≥45%(主版)": (r_main, to_main, ex_main)}
sat_on_map = {"主版": on_main}
for lab, (Ww, on) in specs.items():
    rr, tt, ee = mf.run_weekly(Ww)
    books[lab] = (rr, tt, ee)
    sat_on_map[lab] = on
    print(lab, {k: round(float(v), 4) for k, v in mf.stats(rr).items()}, f"sat_on={np.mean(list(on.values())):.1%}", flush=True)

# 对照：纯 T-MA60、固定 60/40、纯 B4、冠军、同均仓固定
r_tm, to_tm, ex_tm = t.run(w_tm)
W_6040 = {dd: core_weights(dd, 1.0) for dd in reb}  # 100% 核心 = 全组合 60/40
r_6040, to_6040, ex_6040 = mf.run_weekly(W_6040)
r_b4, to_b4, ex_b4 = mf.run_weekly(W_b4_iv)
ch = mf.champ()

# 同平均仓位固定对照：估主版均权益仓（非 MF/非 B1）
eq_codes = set(aw) | set(ind)
eq_fracs = []
for dd in reb:
    w = W_main[dd]
    eq_fracs.append(sum(v for c, v in w.items() if c in eq_codes))
xbar = float(np.mean(eq_fracs))
# 静态：xbar × 全研究权益等权 + 余现金/债？ 用「同均权益仓 × 宽基+行业等权 + 余 511880」
all_eq = [c for c in list(KEEP_AW | KEEP_IND) if c in P.columns]
W_st = {}
for dd in reb:
    pl = [c for c in all_eq if not pd.isna(P.at[dd, c])]
    if not pl:
        W_st[dd] = {MF: 1.0}; continue
    ww = {c: xbar / len(pl) for c in pl}
    ww[MF] = 1 - xbar
    W_st[dd] = ww
r_st, to_st, ex_st = mf.run_weekly(W_st)

books.update({
    "纯周频T-MA60(同A宽基)": (r_tm, to_tm, ex_tm),
    "固定60/40(T-MA60:B1)": (r_6040, to_6040, ex_6040),
    "纯B4逆波动(卫星腿)": (r_b4, to_b4, ex_b4),
    f"同均仓固定对照(x̄权益={xbar:.2f})": (r_st, to_st, ex_st),
    "冠军同引擎(研究副本)": ch,
})

sm = mf.stats(r_main)
# 最好单腿：在 T-MA60、60/40、B4 中取 Calmar 最高
legs = {"T-MA60": (r_tm, mf.stats(r_tm)), "60/40": (r_6040, mf.stats(r_6040)), "B4": (r_b4, mf.stats(r_b4))}
best_name = max(legs, key=lambda k: legs[k][1]["Calmar"])
best_r, best_s = legs[best_name]
shallow = sm["maxDD"] - best_s["maxDD"]
cal_ok = sm["Calmar"] >= best_s["Calmar"] * 0.95
print(f"最好单腿={best_name} Calmar {best_s['Calmar']:.2f} DD {best_s['maxDD']:.1%}; STACK浅 {shallow*100:+.1f}pp Calmar {sm['Calmar']:.2f}", flush=True)

# 两分段
def seg(r, a, b=None):
    if b:
        s = r[(r.index >= a) & (r.index <= b)]
    else:
        s = r[r.index >= a] if a.endswith("01-01") or "-" in a else r
    return mf.stats(s)

# 2020-22 / 2023-26
def seg_cal(r, which):
    if which == "a":
        return mf.stats(r[r.index <= "2022-12-31"])
    return mf.stats(r[r.index >= "2023-01-01"])

seg_ok = True
for which in ("a", "b"):
    ss, sb = seg_cal(r_main, which), seg_cal(best_r, which)
    # 不劣：Calmar>=×0.95 或 DD 不更深（maxDD 更大）
    if not (ss["Calmar"] >= sb["Calmar"] * 0.95 or ss["maxDD"] >= sb["maxDD"] - 1e-9):
        seg_ok = False
print(f"分段不劣={seg_ok}", flush=True)

# 压力期核心–卫星相关
# 构造核心-only 与 卫星-only 收益序列
W_core_only = {dd: core_weights(dd, 1.0) for dd in reb}
W_sat_only = {}
for dd in reb:
    sw, _ = sat_weights(dd, 1.0, use_iv=True, use_breadth=False)  # 始终开，测腿相关
    W_sat_only[dd] = sw
r_core, _, _ = mf.run_weekly(W_core_only)
r_sat, _, _ = mf.run_weekly(W_sat_only)

stress_windows = [
    ("2020-02", "2020-02-01", "2020-03-31"),
    ("2021-09→2022-10", "2021-09-01", "2022-10-31"),
    ("2022-03", "2022-02-15", "2022-04-30"),
    ("2024-01", "2024-01-01", "2024-02-15"),
    ("下跌长段", "2021-09-01", "2024-09-30"),
]
corr_rows = []
for n, a, b in stress_windows:
    rc = r_core[(r_core.index >= a) & (r_core.index <= b)]
    rs = r_sat[(r_sat.index >= a) & (r_sat.index <= b)]
    # 周度相关：对齐到周
    both = pd.concat([rc.rename("c"), rs.rename("s")], axis=1).dropna()
    # 用周收益（五天合计）更稳
    wk = both.groupby(both.index.to_period("W-FRI")).sum()
    rho = float(wk["c"].corr(wk["s"])) if len(wk) > 5 else np.nan
    dd_s = mf.mdd(r_main, a, b)
    dd_best = mf.mdd(best_r, a, b)
    corr_rows.append(dict(window=n, rho_core_sat=rho, stack_dd=dd_s, best_dd=dd_best, shallow_pp=dd_s - dd_best))
Corr = pd.DataFrame(corr_rows)
Corr.to_csv(f"{OUT}/stress_corr.csv", index=False)
print(Corr.round(3).to_string(), flush=True)

# 2023-26 vs 固定60/40
s23_stack = seg_cal(r_main, "b")
s23_6040 = seg_cal(r_6040, "b")
chase_fail = s23_stack["Calmar"] < s23_6040["Calmar"]  # 2023-26 不优于固定60/40

# 证伪/成功
success = (shallow >= 0.03) and cal_ok and seg_ok
stress_falsify = False
for r in Corr.itertuples():
    if (not pd.isna(r.rho_core_sat)) and r.rho_core_sat > 0.8 and r.shallow_pp < 0.01:
        stress_falsify = True
falsified = (not success) or stress_falsify or chase_fail

reasons = []
if shallow < 0.03:
    reasons.append(f"MDD浅仅 {shallow*100:+.1f}pp(<3pp) vs 最好单腿{best_name}")
if not cal_ok:
    reasons.append(f"Calmar {sm['Calmar']:.2f} < {best_name}×0.95={best_s['Calmar']*0.95:.2f}")
if not seg_ok:
    reasons.append("两分段存在劣于最好单腿")
if stress_falsify:
    reasons.append("压力期核心–卫星相关>0.8且回撤不改善")
if chase_fail:
    reasons.append(f"2023–26 Calmar {s23_stack['Calmar']:.2f} 不优于固定60/40 {s23_6040['Calmar']:.2f}")

if success and not stress_falsify and not chase_fail:
    falsified = False
    reasons = []

verdict = "**证伪**" if falsified else "**未证伪/达成功闸**"
fal = ("；".join(reasons) if reasons else f"MDD浅 {shallow*100:+.1f}pp；Calmar {sm['Calmar']:.2f}≥{best_s['Calmar']*0.95:.2f}；分段过；2023–26≥60/40") + ("。证伪成立。" if falsified else "。达成功标准。")

# 卫星开启周与贡献
on_arr = pd.Series(on_main)
sat_on_pct = float(on_arr.mean())
# 贡献：主版 − 纯核心70%放大？ 更干净：对比「仅核心100%的60/40」与主版的差额归卫星
# 卫星贡献粗估：r_main - r_6040 的算术和（不全对因为核心是70%）；用「核心70%+卫星关」对照
W_core70_satoff, _ = build_stack(0.70, 0.30, use_breadth=True)
# force sat always off
W_c70off = {}
for dd in reb:
    cw = core_weights(dd, 0.70)
    W_c70off[dd] = merge(cw, {MF: 0.30})
r_c70off, to_c70off, ex_c70off = mf.run_weekly(W_c70off)
sat_contrib = (r_main - r_c70off).sum()
sat_contrib_ret = (1 + r_main).prod() - (1 + r_c70off).prod()  # not exact
books["旁注 核心70%+卫星强制关"] = (r_c70off, to_c70off, ex_c70off)

# 归因
e._bench = {**e.benches(), "池等权(318有价,周调,0.2%RT)": (r_st, to_st, ex_st)}
at = A.attribute(ID, "MF-STACK-v1主版", lambda i, dd: W_main.get(dd, {}), OUT, True)

attr_md = at["md"] + f"""

### 合层专项
- 卫星开启周占比 **{sat_on_pct:.1%}**（冠军 B20≥45%）
- 旁注若用 B60≥45%：开启周 {(B60.reindex(reb)>=0.45).mean():.1%}
- 相对「核心70%+卫星强制关」算术超额合计 {sat_contrib:+.1%}；终值差(复利粗) {((1+r_main).prod()-(1+r_c70off).prod()):+.1%}
- 最好单腿 = {best_name}；STACK vs 之 MDD浅 {shallow*100:+.1f}pp，Calmar {sm['Calmar']:.2f} vs {best_s['Calmar']:.2f}
- 2023–26：STACK Calmar {s23_stack['Calmar']:.2f} vs 固定60/40 {s23_6040['Calmar']:.2f}
"""

main = "MF-STACK-v1 核心70%(60/40)+卫星30%B4·B20≥45%(主版)"
M = pd.DataFrame([mf.row(k, *v[:3]) for k, v in books.items()])
# 卫星开启写入 diag
pd.Series({"sat_on_pct_B20": sat_on_pct, "sat_on_pct_B60_note": float((B60.reindex(reb) >= 0.45).mean()),
           "best_leg": best_name, "shallow_pp": shallow, "falsified": falsified, "xbar_eq": xbar,
           "sat_contrib_arith": sat_contrib}).to_csv(f"{OUT}/diag.csv")

report = HYPO + f"""
## 1. 准则原文
核心 70% = 固定 60/40（宽基周频 T-MA60 : B1）；宽基空仓时该 60% 腿进 511880，债 40% 仍持。卫星 ≤30% = MF-B4；开关 = 池级 breadth≥45%。周频再平衡，L≤1，0.2%RT。

## 2. 实现要点
- **breadth**：只读冠军研究副本 `breadth_ma20_v1016.csv`（+ face 前段）= **周收>周MA20 占比≥45%**。与 PLAN「MA60」不一致 → 主版按冠军 MA20；旁注自算日线 MA60 池级≥45%（开启周 {(B60.reindex(reb)>=0.45).mean():.1%} vs MA20 {sat_on_pct:.1%}）。
- 核心：0.7×(0.6×T-MA60册 + 0.4×B1等权)；卫星开：0.3×B4逆波动；卫星关：0.3→511880。
- 邻档：80/20、60/40；卫星等权；无 breadth；旁注 MA60 开关。
- 区间 {mf.START}→{mf.END}；不碰实盘。

## 3. 主表
{mf.metrics_table(M, main)}

### 成功闸
- 最好单腿 = **{best_name}**（Calmar {best_s['Calmar']:.2f}，DD {best_s['maxDD']:.1%}）
- STACK MDD 浅 **{shallow*100:+.1f}pp**（门槛≥3pp）；Calmar {sm['Calmar']:.2f} vs ×0.95门 {best_s['Calmar']*0.95:.2f}：{'过' if cal_ok else '不过'}
- 两分段不劣：{'是' if seg_ok else '否'}
- 卫星开启周 **{sat_on_pct:.1%}**；相对卫星强制关算术贡献 {sat_contrib:+.1%}
- 均权益仓 x̄={xbar:.2f}

### 压力期核心–卫星相关
| 窗口 | ρ(核心,卫星) | STACK DD | 最好单腿 DD | 浅(pp) |
|---|---:|---:|---:|---:|
""" + "\n".join(
    f"| {r.window} | {r.rho_core_sat:.2f} | {mf.fmt_pct(r.stack_dd)} | {mf.fmt_pct(r.best_dd)} | {r.shallow_pp*100:+.1f} |"
    for r in Corr.itertuples()
) + f"""

### 逐年（主版 / 60/40 / B4 / T-MA60）
"""
ks_y = [main, "固定60/40(T-MA60:B1)", "纯B4逆波动(卫星腿)", "纯周频T-MA60(同A宽基)"]
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

breadth 口径备注：冠军 MA20≠PLAN MA60，已按冠军执行并旁注。

产物：{OUT}/；不换冠军、不下单。
"""

# fix typo in attr_md
attr_md = attr_md.replace("+().1%", "+.1%")
mf.deliver(ID, books, main, f"{ID}（核心70%+卫星30%，0.2%RT）", report, attr_md)
M.to_csv(f"{OUT}/metrics.csv", index=False)
pickle.dump(dict(W_main=W_main, on_main=on_main, falsified=falsified, best_name=best_name,
                 shallow=shallow, Corr=Corr, sat_on_pct=sat_on_pct, xbar=xbar), open(f"{OUT}/_res.pkl", "wb"))
print("DONE", verdict, fal, flush=True)
print(M[["book", "ret", "maxDD", "Calmar", "turnover", "avg_expo"]].round(3).to_string(), flush=True)
