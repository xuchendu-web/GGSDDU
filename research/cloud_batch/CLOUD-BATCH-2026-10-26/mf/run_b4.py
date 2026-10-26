#!/usr/bin/env python3
"""MF-B4：行业 XS52 取5 + 组内 60 日 σ 倒数加权；邻档 +TV25。"""
import os, sys, pickle, numpy as np, pandas as pd
sys.path.insert(0, "/workspace/etf-multifreq/engine")
import mf_common as mf
import mom_engine as e
import attribution as A
from pathlib import Path

ID = "MF-B4"
OUT = f"{mf.OUT_ROOT}/{ID}"
Path(OUT).mkdir(parents=True, exist_ok=True)

HYPO = """## 0. 假设与证伪（开跑前写死）
- **假设**：XS52 取 5 后按过去 60 日 σ 倒数加权，组内高波应低权，可压回撤、抬 Calmar。
- **证伪**（任一）：Calmar 不高于等权版；或回撤不浅 ≥3pp；或 2020–22 与 2023–26 两分段均不改善（Calmar 与 DD 皆不优于等权）。
"""

D = mf.data()
P, W, SIG, G, gi, reb = D["P"], D["W"], D["SIG"], D["G"], D["gi"], D["reb"]
ind, MF = D["ind"], mf.MF
KEEP = set(ind)
print(f"行业主题 {len(ind)}", flush=True)

def avail_pool(i):
    a = e.avail(i)
    return [c for c in a[a].index if c in KEEP]

def picks_xs(i, N=5):
    s = e.mom(i, 52, 1)
    s = s[[c for c in s.index if c in KEEP]].dropna()
    return e.topn(s, N) if len(s) else []

def invvol_w(i, dd, codes, look=60):
    """过去 look 个交易日日收益 σ 倒数，归一。"""
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

def build_invvol(N=5):
    raw = {}
    for dd in reb:
        i = gi[dd]
        if i < 52:
            raw[dd] = {}; continue
        p = picks_xs(i, N)
        if not p:
            raw[dd] = {}; continue
        raw[dd] = invvol_w(i, dd, p, 60)
    return raw

def build_ew(N=5):
    raw = {}
    for dd in reb:
        i = gi[dd]
        if i < 52:
            raw[dd] = {}; continue
        p = picks_xs(i, N)
        raw[dd] = {c: 1 / N for c in p}
    return raw

def apply_tv(wmap, sig=0.25):
    """TV：按权益腿已实现收益缩放 L≤1，空位不补 MF（与 MOM-VOL 类似；此处满仓 5 只）。"""
    # 先跑未缩放收益估波动
    base = e.run_weights(lambda i, dd: wmap.get(dd, {}))[0]
    out = {}
    for dd in reb:
        w = wmap.get(dd, {})
        if not w:
            out[dd] = {}; continue
        p = base[base.index <= dd]; p = p[p != 0]
        L = 1.0 if len(p) < 20 else min(1.0, sig / max(p.iloc[-20:].std() * np.sqrt(252),
                                                         p.iloc[-60:].std() * np.sqrt(252) if len(p) >= 60 else 1e-9))
        out[dd] = {c: v * L for c, v in w.items()}
    return out

W_iv = build_invvol(5)
r_iv, to_iv, ex_iv = mf.run_weekly(W_iv)
print("INVVOL", {k: round(float(v), 4) for k, v in mf.stats(r_iv).items()}, f"to={to_iv:.2f} ex={ex_iv:.2f}", flush=True)

W_ew = build_ew(5)
r_ew, to_ew, ex_ew = mf.run_weekly(W_ew)
print("EW", {k: round(float(v), 4) for k, v in mf.stats(r_ew).items()}, f"to={to_ew:.2f}", flush=True)

# 邻档 +TV25
W_iv_tv = apply_tv(W_iv, 0.25)
r_ivtv, to_ivtv, ex_ivtv = mf.run_weekly(W_iv_tv)
W_ew_tv = apply_tv(W_ew, 0.25)
r_ewtv, to_ewtv, ex_ewtv = mf.run_weekly(W_ew_tv)
print("INVVOL+TV", {k: round(float(v), 4) for k, v in mf.stats(r_ivtv).items()}, f"to={to_ivtv:.2f} ex={ex_ivtv:.2f}", flush=True)
print("EW+TV", {k: round(float(v), 4) for k, v in mf.stats(r_ewtv).items()}, flush=True)

# 邻档：20 日 / 120 日 σ
def build_invvol_look(look):
    raw = {}
    for dd in reb:
        i = gi[dd]
        if i < 52:
            raw[dd] = {}; continue
        p = picks_xs(i, 5)
        raw[dd] = invvol_w(i, dd, p, look) if p else {}
    return raw
W_20 = build_invvol_look(20); r_20, to_20, ex_20 = mf.run_weekly(W_20)
W_120 = build_invvol_look(120); r_120, to_120, ex_120 = mf.run_weekly(W_120)
print("σ20", {k: round(float(v), 4) for k, v in mf.stats(r_20).items()}, flush=True)
print("σ120", {k: round(float(v), 4) for k, v in mf.stats(r_120).items()}, flush=True)

# 等权池
W_pool = {}
for dd in reb:
    pl = avail_pool(gi[dd])
    W_pool[dd] = {c: 1 / len(pl) for c in pl} if pl else {}
r_pool, to_pool, ex_pool = mf.run_weekly(W_pool)

ch = mf.champ()
books = {
    "MF-B4 XS52取5·逆波动加权(主版)": (r_iv, to_iv, ex_iv),
    "邻档 σ20逆波动": (r_20, to_20, ex_20),
    "邻档 σ120逆波动": (r_120, to_120, ex_120),
    "邻档 主版+TV25": (r_ivtv, to_ivtv, ex_ivtv),
    "同池 XS52等权": (r_ew, to_ew, ex_ew),
    "同池 XS52等权+TV25": (r_ewtv, to_ewtv, ex_ewtv),
    "同池等权(全行业)": (r_pool, to_pool, ex_pool),
    "冠军同引擎(研究副本)": ch,
}

si, se = mf.stats(r_iv), mf.stats(r_ew)
dd_i = mf.mdd(r_iv, "2021-09-01", "2024-09-30")
dd_e = mf.mdd(r_ew, "2021-09-01", "2024-09-30")
shallow = dd_i - dd_e
# 分段
a_i, a_e = mf.stats(r_iv[r_iv.index <= "2022-12-31"]), mf.stats(r_ew[r_ew.index <= "2022-12-31"])
b_i, b_e = mf.stats(r_iv[r_iv.index >= "2023-01-01"]), mf.stats(r_ew[r_ew.index >= "2023-01-01"])
seg_a_better = (a_i["Calmar"] > a_e["Calmar"]) or (a_i["maxDD"] > a_e["maxDD"])  # DD less negative = larger
seg_b_better = (b_i["Calmar"] > b_e["Calmar"]) or (b_i["maxDD"] > b_e["maxDD"])
both_seg_fail = (not seg_a_better) and (not seg_b_better)

f1 = not (si["Calmar"] > se["Calmar"])
f2 = shallow < 0.03
f3 = both_seg_fail
falsified = f1 or f2 or f3
reasons = []
if f1: reasons.append(f"Calmar {si['Calmar']:.2f} 不高于等权 {se['Calmar']:.2f}")
if f2: reasons.append(f"回撤浅仅 {shallow*100:+.1f}pp(<3pp)")
if f3: reasons.append("两分段均不改善")
verdict = "**证伪**" if falsified else "**未证伪**"
fal = ("；".join(reasons) if reasons else f"Calmar {si['Calmar']:.2f}>{se['Calmar']:.2f}；浅 {shallow*100:+.1f}pp") + ("。证伪成立。" if falsified else "。未触发证伪闸。")

e._bench = {**e.benches(), "池等权(318有价,周调,0.2%RT)": (r_pool, to_pool, ex_pool)}
at = A.attribute(ID, "MF-B4主版", lambda i, dd: W_iv.get(dd, {}), OUT, True)

main = "MF-B4 XS52取5·逆波动加权(主版)"
M = pd.DataFrame([mf.row(k, *v[:3]) for k, v in books.items()])
report = HYPO + f"""
## 1. 准则原文
MF-B4：A股行业主题；XS52 跳1 取5 后按过去 60 日 σ 倒数加权（归一），L≤1；邻档可叠 TV25。

## 2. 实现要点
- 池 {len(ind)} 只；选品同 XS52；权重 w_i ∝ 1/σ_60（日收益），归一和为 1。
- 邻档：σ20 / σ120；主版+TV25；等权版+TV25 对照。
- 成本 0.2%RT；{mf.START}→{mf.END}。

## 3. 主表
{mf.metrics_table(M, main)}

### vs 等权
- Calmar {si['Calmar']:.2f} vs 等权 {se['Calmar']:.2f}（Δ {si['Calmar']-se['Calmar']:+.2f}）
- 全样本 DD {si['maxDD']:.1%} vs {se['maxDD']:.1%}；下跌段浅 {shallow*100:+.1f}pp
- 2020–22 Calmar {a_i['Calmar']:.2f} vs {a_e['Calmar']:.2f}；2023–26 {b_i['Calmar']:.2f} vs {b_e['Calmar']:.2f}

### 逐年
"""
Y = pd.concat([mf.yearly(books[k][0]).assign(book=k) for k in [main, "同池 XS52等权", "同池等权(全行业)"]])
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
mf.deliver(ID, books, main, f"{ID}（行业XS+逆波动，0.2%RT）", report, at["md"])
M.to_csv(f"{OUT}/metrics.csv", index=False)
pickle.dump(dict(W_iv=W_iv, falsified=falsified), open(f"{OUT}/_res.pkl", "wb"))
print("DONE", verdict, fal, flush=True)
print(M[["book", "ret", "maxDD", "Calmar", "turnover", "avg_expo"]].round(3).to_string(), flush=True)
