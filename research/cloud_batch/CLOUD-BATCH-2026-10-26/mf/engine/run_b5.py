#!/usr/bin/env python3
"""MF-B5：B4 底座 + 池级 breadth(MA20上方占比)≥θ 才开卫星，否则全 511880。禁止单品 MA20 筛。"""
import os, sys, pickle, numpy as np, pandas as pd
sys.path.insert(0, "/workspace/etf-multifreq/engine")
import mf_common as mf
import mom_engine as e
import attribution as A
from pathlib import Path

ID = "MF-B5"
OUT = f"{mf.OUT_ROOT}/{ID}"
Path(OUT).mkdir(parents=True, exist_ok=True)

HYPO = """## 0. 假设与证伪（开跑前写死）
- **假设**：在 MF-B4（行业主题 XS52取5 + 60日逆波动）上，加池级 breadth（主题池收盘>MA20 占比）≥45% 才持有卫星，否则全 511880，可改善 2020–22 压舱段且下跌段回撤浅于 B4。
- **证伪**（任一）：与 B4 持仓差周 <10% 且指标无改善；或 2023–26 相对 B4 收益×0.9 以下（踏空）；或换手 > B4×1.5。
- **红线**：禁止单品 MA20 逐只筛；不叠 HYST/B50/511260 冠军栈。
"""

D = mf.data()
P, W, SIG, G, gi, reb = D["P"], D["W"], D["SIG"], D["G"], D["gi"], D["reb"]
ind, MF = D["ind"], mf.MF
KEEP = set(ind)
print(f"行业主题 {len(ind)}", flush=True)

# 日线 MA20（含当日）
C_ind = P[[c for c in ind if c in P.columns]]
MA20 = C_ind.rolling(20, min_periods=20).mean()

def avail_pool(i):
    a = e.avail(i)
    return [c for c in a[a].index if c in KEEP]

def picks_xs(i, N=5):
    s = e.mom(i, 52, 1)
    s = s[[c for c in s.index if c in KEEP]].dropna()
    return e.topn(s, N) if len(s) else []

def invvol_w(i, dd, codes, look=60):
    if dd not in P.index:
        return {c: 1 / len(codes) for c in codes} if codes else {}
    loc = P.index.get_loc(dd)
    if loc < look:
        return {c: 1 / len(codes) for c in codes} if codes else {}
    seg = P[codes].iloc[loc - look:loc].pct_change().iloc[1:]
    sig = seg.std()
    inv = 1.0 / sig.replace(0, np.nan)
    inv = inv.dropna()
    inv = inv[[c for c in codes if c in inv.index]]
    if inv.empty or inv.sum() <= 0:
        return {c: 1 / len(codes) for c in codes}
    inv = inv / inv.sum()
    return inv.to_dict()

def pool_breadth(dd):
    """主题池中收盘>MA20 的占比（有价且 MA20 有效）。"""
    if dd not in C_ind.index:
        return np.nan
    row = C_ind.loc[dd]; ma = MA20.loc[dd]
    valid = [c for c in C_ind.columns if not pd.isna(row[c]) and not pd.isna(ma[c])]
    if not valid:
        return np.nan
    above = sum(1 for c in valid if row[c] > ma[c])
    return above / len(valid)

def build_b4():
    raw = {}
    for dd in reb:
        i = gi[dd]
        if i < 52:
            raw[dd] = {}; continue
        p = picks_xs(i, 5)
        raw[dd] = invvol_w(i, dd, p, 60) if p else {}
    return raw

def build_ew():
    raw = {}
    for dd in reb:
        i = gi[dd]
        if i < 52:
            raw[dd] = {}; continue
        p = picks_xs(i, 5)
        raw[dd] = {c: 1 / 5 for c in p}
    return raw

def apply_breadth(wmap, theta=0.45):
    """池级门：breadth≥θ 才持有卫星，否则全 511880。返回 (wmap_gated, signal_df)。"""
    out = {}; rows = []
    for dd in reb:
        br = pool_breadth(dd)
        base = wmap.get(dd, {})
        open_ok = (not pd.isna(br)) and br >= theta
        if open_ok and base:
            out[dd] = dict(base)
        else:
            # 全 511880
            out[dd] = {MF: 1.0} if not pd.isna(P.at[dd, MF]) else {}
        rows.append(dict(date=dd, breadth=br, open=open_ok, n_sat=len(base)))
    return out, pd.DataFrame(rows).set_index("date")

W_b4 = build_b4()
r_b4, to_b4, ex_b4 = mf.run_weekly(W_b4)
print("B4 base", {k: round(float(v), 4) for k, v in mf.stats(r_b4).items()},
      f"to={to_b4:.2f} ex={ex_b4:.2f}", flush=True)

W_main, sig45 = apply_breadth(W_b4, 0.45)
r_main, to_main, ex_main = mf.run_weekly(W_main)
print("B5 θ=0.45", {k: round(float(v), 4) for k, v in mf.stats(r_main).items()},
      f"to={to_main:.2f} ex={ex_main:.2f} open={sig45.open.mean():.1%}", flush=True)

W_40, sig40 = apply_breadth(W_b4, 0.40)
r_40, to_40, ex_40 = mf.run_weekly(W_40)
print("邻档 θ=0.40", {k: round(float(v), 4) for k, v in mf.stats(r_40).items()},
      f"to={to_40:.2f} open={sig40.open.mean():.1%}", flush=True)

W_50, sig50 = apply_breadth(W_b4, 0.50)
r_50, to_50, ex_50 = mf.run_weekly(W_50)
print("邻档 θ=0.50", {k: round(float(v), 4) for k, v in mf.stats(r_50).items()},
      f"to={to_50:.2f} open={sig50.open.mean():.1%}", flush=True)

W_ew = build_ew()
r_ew, to_ew, ex_ew = mf.run_weekly(W_ew)

W_pool = {}
for dd in reb:
    pl = avail_pool(gi[dd])
    W_pool[dd] = {c: 1 / len(pl) for c in pl} if pl else {}
r_pool, to_pool, ex_pool = mf.run_weekly(W_pool)

ch = mf.champ()

# 持仓差周：卫星成分集合相对 B4 不同的周占比
# 「差」= 开/关不同，或开仓时成分不同
diff_weeks = 0
n_cmp = 0
for dd in reb:
    b4 = set(c for c, w in W_b4.get(dd, {}).items() if w > 0)
    b5 = set(c for c, w in W_main.get(dd, {}).items() if w > 0 and c != MF)
    # B5 关仓时 b5 空、B4 有仓 → 差；或成分不等 → 差
    # 也计 B4 空且 B5 只有 MF 为「同空」？B4 空时两者都无卫星 → 不算差
    if not b4 and not b5:
        n_cmp += 1
        continue
    n_cmp += 1
    if b4 != b5:
        diff_weeks += 1
diff_frac = diff_weeks / n_cmp if n_cmp else 0.0
print(f"持仓差周 {diff_weeks}/{n_cmp} = {diff_frac:.1%}", flush=True)

sig45.to_csv(f"{OUT}/breadth_signal.csv")

books = {
    "MF-B5 B4+breadth≥45%(主版)": (r_main, to_main, ex_main),
    "邻档 θ=0.40": (r_40, to_40, ex_40),
    "邻档 θ=0.50": (r_50, to_50, ex_50),
    "MF-B4 XS52取5·逆波动(底座)": (r_b4, to_b4, ex_b4),
    "同池 XS52等权": (r_ew, to_ew, ex_ew),
    "同池等权(全行业)": (r_pool, to_pool, ex_pool),
    "冠军同引擎(研究副本)": ch,
}

sm, sb = mf.stats(r_main), mf.stats(r_b4)
# 分段
a_m = mf.stats(r_main[r_main.index <= "2022-12-31"]); a_b = mf.stats(r_b4[r_b4.index <= "2022-12-31"])
b_m = mf.stats(r_main[r_main.index >= "2023-01-01"]); b_b = mf.stats(r_b4[r_b4.index >= "2023-01-01"])
dd_m = mf.mdd(r_main, "2021-09-01", "2024-09-30")
dd_b = mf.mdd(r_b4, "2021-09-01", "2024-09-30")
shallow_down = dd_m - dd_b  # positive if B5 shallower

# 证伪
# 1) 持仓差周<10% 且指标无改善
no_improve = (sm["Calmar"] <= sb["Calmar"]) and (sm["maxDD"] <= sb["maxDD"]) and (shallow_down < 0.01)
f1 = (diff_frac < 0.10) and no_improve
# 2) 2023-26 相对 B4 踏空：收益 ×0.9 以下
f2 = b_m["ret"] < b_b["ret"] * 0.9
# 3) 换手 > B4×1.5
f3 = to_main > to_b4 * 1.5

falsified = f1 or f2 or f3
reasons = []
if f1:
    reasons.append(f"持仓差周仅 {diff_frac:.1%}<10% 且指标无改善(Calmar {sm['Calmar']:.2f} vs B4 {sb['Calmar']:.2f})")
if f2:
    reasons.append(f"2023–26 踏空：ret {b_m['ret']:.1%} < B4×0.9={b_b['ret']*0.9:.1%}（B4={b_b['ret']:.1%}）")
if f3:
    reasons.append(f"换手 {to_main:.2f}x > B4×1.5={to_b4*1.5:.2f}x")
# 倾向旁注
tend = []
if shallow_down >= 0.03:
    tend.append(f"下跌段浅于B4 {shallow_down*100:+.1f}pp")
se = mf.stats(r_ew)
a_ew = mf.stats(r_ew[r_ew.index <= "2022-12-31"])
if a_m["Calmar"] >= a_ew["Calmar"]:
    tend.append(f"2020–22 Calmar {a_m['Calmar']:.2f} ≥ 同池等权 {a_ew['Calmar']:.2f}")
if sm["Calmar"] >= sb["Calmar"]:
    tend.append(f"全样本 Calmar {sm['Calmar']:.2f} ≥ B4 {sb['Calmar']:.2f}")

verdict = "**证伪**" if falsified else "**未证伪**"
fal = ("；".join(reasons) if reasons else
       f"差周 {diff_frac:.1%}；2023–26 ret {b_m['ret']:.1%} vs B4 {b_b['ret']:.1%}；换手 {to_main:.2f} vs {to_b4:.2f}"
       ) + ("。证伪成立。" if falsified else "。未触发证伪闸。")
if tend and not falsified:
    fal += " 倾向：" + "；".join(tend) + "。"
elif tend:
    fal += " （旁注倾向部分：" + "；".join(tend) + "）"

# 归因
e._bench = {**e.benches(), "池等权(行业,周调,0.2%RT)": (r_pool, to_pool, ex_pool)}
try:
    at = A.attribute(ID, "MF-B5主版", lambda i, dd: W_main.get(dd, {}), OUT, True)
    attr_md = at["md"]
except Exception as ex:
    attr_md = f"## 归因 · MF-B5\n_attribution 模块异常：{ex}_\n"

attr_md += f"""
### 择时 / 选品 / 频率 / 成本（本刀补记）
- **择时**：池级 breadth≥45% 开关（开仓周 {sig45.open.mean():.1%}；均 breadth {sig45.breadth.mean():.2f}）
- **选品**：同 B4（XS52取5 + 60日逆波动）；未改选品键、禁止单品 MA20
- **频率**：周频（周五 reb）；相对 B4 持仓差周 **{diff_frac:.1%}**
- **成本**：换手 {to_main:.2f}x vs B4 {to_b4:.2f}x（×{to_main/to_b4 if to_b4 else float('nan'):.2f}）

### vs B4
- Calmar {sm['Calmar']:.2f} vs {sb['Calmar']:.2f}（Δ {sm['Calmar']-sb['Calmar']:+.2f}）
- DD {sm['maxDD']:.1%} vs {sb['maxDD']:.1%}；下跌段浅 {shallow_down*100:+.1f}pp
- 2020–22 Calmar {a_m['Calmar']:.2f} vs {a_b['Calmar']:.2f}；2023–26 ret {b_m['ret']:.1%} vs {b_b['ret']:.1%} / Calmar {b_m['Calmar']:.2f} vs {b_b['Calmar']:.2f}
"""

main = "MF-B5 B4+breadth≥45%(主版)"
M = pd.DataFrame([mf.row(k, *v[:3]) for k, v in books.items()])
report = HYPO + f"""
## 1. 准则原文
底座 = **MF-B4**：行业主题池，XS52 跳1 取5 + 60 日逆波动加权。
**唯一加项**：池级 breadth（主题池 MA20 上方占比）≥**45%** 才持有卫星组合，否则全 511880。
周五≥14:30 / 收盘；0.2%RT；L≤1。**禁止** 单品日/周 MA20 逐只筛。

## 2. 实现要点
- 池 {len(ind)} 只行业主题；选品/加权同 B4。
- 每周 reb 日计算池级 breadth = (# 收盘>日MA20) / (# 有价且 MA20 有效)；≥θ 开卫星，否则 {{511880:1}}。
- 邻档 θ=0.40 / 0.50；对照 B4、同池 XS52 等权、等权全行业、冠军研究副本。
- 成本 0.2%RT；{mf.START}→{mf.END}；不叠冠军强栈。

## 3. 主表
{mf.metrics_table(M, main)}

### vs B4 与证伪闸
- 持仓差周：**{diff_frac:.1%}**（{diff_weeks}/{n_cmp}）
- 开仓周占比：θ0.45={sig45.open.mean():.1%} / θ0.40={sig40.open.mean():.1%} / θ0.50={sig50.open.mean():.1%}
- 均 breadth={sig45.breadth.mean():.3f}
- Calmar {sm['Calmar']:.2f} vs B4 {sb['Calmar']:.2f}（Δ {sm['Calmar']-sb['Calmar']:+.2f}）
- 下跌段 2021-09→2024-09 DD {dd_m:.1%} vs B4 {dd_b:.1%}（浅 {shallow_down*100:+.1f}pp）
- 2020–22 Calmar {a_m['Calmar']:.2f} vs B4 {a_b['Calmar']:.2f} / 同池等权 {a_ew['Calmar']:.2f}
- 2023–26 ret {b_m['ret']:.1%} vs B4 {b_b['ret']:.1%}（门槛 B4×0.9={b_b['ret']*0.9:.1%}）；换手 {to_main:.2f} vs B4×1.5={to_b4*1.5:.2f}

### 逐年
"""
Y = pd.concat([mf.yearly(books[k][0]).assign(book=k) for k in [main, "MF-B4 XS52取5·逆波动(底座)", "同池 XS52等权"]])
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
mf.deliver(ID, books, main, f"{ID}（B4+池级breadth≥45%，0.2%RT）", report, attr_md)
M.to_csv(f"{OUT}/metrics.csv", index=False)
pickle.dump(dict(falsified=falsified, diff_frac=diff_frac, sig45=sig45,
                 shallow_down=shallow_down, W_main=W_main), open(f"{OUT}/_res.pkl", "wb"))
print("DONE", verdict, fal, flush=True)
print(M[["book", "ret", "maxDD", "Calmar", "turnover", "avg_expo"]].round(3).to_string(), flush=True)
