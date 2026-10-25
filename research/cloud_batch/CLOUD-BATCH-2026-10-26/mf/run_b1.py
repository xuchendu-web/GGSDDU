#!/usr/bin/env python3
"""MF-B1 行业周频动量：先剔 TS52≤0，再 XS52 跳1 取5；不足补 511880；禁止 MA20。"""
import os, sys, pickle, numpy as np, pandas as pd
sys.path.insert(0, "/workspace/etf-multifreq/engine")
import mf_common as mf
import mom_engine as e
from pathlib import Path

ID = "MF-B1"
OUT = f"{mf.OUT_ROOT}/{ID}"
Path(OUT).mkdir(parents=True, exist_ok=True)

HYPO = """## 0. 假设与证伪（开跑前写死）
- **假设**：先用 52 周时间序列动量剔掉负收益品种，再做截面 XS52 排名，可避免 FILTER-FIRST 的短线追涨，同时保留行业动量。
- **证伪**（任一）：与同池 XS52 持仓差异周 <10%；或下跌段 2021-09→2024-09 回撤不浅 ≥3pp（即相对 XS52 浅不到 3pp）；或换手 > XS52 ×1.5。
- **禁止**：日/周 MA20 逐只筛。
"""

D = mf.data()
P, W, SIG, G, gi, reb = D["P"], D["W"], D["SIG"], D["G"], D["gi"], D["reb"]
ind = D["ind"]  # 行业主题
MF = mf.MF
KEEP = set(ind)
print(f"行业主题池 {len(ind)} 只", flush=True)

def avail_pool(i):
    a = e.avail(i)
    return [c for c in a[a].index if c in KEEP]

def mom_pool(i, L=52, skip=1):
    s = e.mom(i, L, skip)
    return s[[c for c in s.index if c in KEEP]].dropna()

def picks_b1(i, dd, ts_L=52, N=5):
    """先剔 TS≤0，再 XS 取 N。返回 picks, n_removed, n_cand, n_pos_ts"""
    cand = avail_pool(i)
    if i - ts_L < 0 or not cand:
        return [], 0, len(cand), 0
    # TS：用当期 SIG / ts_L 周前周收（与 filter_first 一致）
    t = SIG.iloc[i] / W.iloc[i - ts_L] - 1
    pos = [c for c in cand if t.get(c, np.nan) > 0]
    rem = len(cand) - len(pos)
    s = e.mom(i, 52, 1)
    s = s[[c for c in s.index if c in pos]].dropna()
    return e.topn(s, N), rem, len(cand), len(pos)

def picks_xs(i, N=5):
    s = mom_pool(i, 52, 1)
    return e.topn(s, N) if len(s) else []

def picks_dual(i, N=5):
    """先排名再过滤 TS>0（DUAL）"""
    s = mom_pool(i, 52, 1)
    if len(s) < 1:
        return []
    top = e.topn(s, N)
    return [c for c in top if s[c] > 0]

def picks_ff(i, dd, N=5):
    """FILTER-FIRST 同池：TS52>0 & ≥MA20，再 XS"""
    cand = avail_pool(i)
    if i - 52 < 0:
        return [], 0, len(cand)
    t = SIG.iloc[i] / W.iloc[i - 52] - 1
    # MA20
    ps = P[list(KEEP)].shift(1).rolling(19).sum()
    ma = (ps.loc[dd] + SIG.loc[dd].reindex(KEEP)) / 20 if dd in ps.index else pd.Series(dtype=float)
    rem = set()
    for c in cand:
        if not (t.get(c, np.nan) > 0):
            rem.add(c)
        elif not (SIG.at[dd, c] >= ma.get(c, np.nan) if c in ma.index else False):
            rem.add(c)
    s = e.mom(i, 52, 1)
    s = s[[c for c in s.index if c in cand and c not in rem]].dropna()
    return e.topn(s, N), len(rem), len(cand)

def build_w(pick_fn, fill_mf=True, N=5, **kw):
    raw = {}; log = {}
    for dd in reb:
        i = gi[dd]
        out = pick_fn(i, dd, **kw) if "dd" in pick_fn.__code__.co_varnames else pick_fn(i, **kw)
        if isinstance(out, tuple):
            p = out[0]; log[dd] = out
        else:
            p = out; log[dd] = (p,)
        w = {c: 1 / N for c in p}
        if fill_mf and len(p) < N and not pd.isna(P.at[dd, MF]):
            w[MF] = (N - len(p)) / N
        raw[dd] = w
    return raw, log

# 主版 B1
W_b1, log_b1 = build_w(picks_b1, ts_L=52, N=5)
r_b1, to_b1, ex_b1 = mf.run_weekly(W_b1)
print("B1", {k: round(float(v), 4) for k, v in mf.stats(r_b1).items()}, f"to={to_b1:.1f} ex={ex_b1:.2f}", flush=True)

# 同池 XS52
W_xs, log_xs = build_w(lambda i, N=5: picks_xs(i, N), N=5)
r_xs, to_xs, ex_xs = mf.run_weekly(W_xs)
print("XS", {k: round(float(v), 4) for k, v in mf.stats(r_xs).items()}, f"to={to_xs:.1f}", flush=True)

# 同池 DUAL
W_du, _ = build_w(lambda i, N=5: picks_dual(i, N), N=5)
r_du, to_du, ex_du = mf.run_weekly(W_du)
print("DUAL", {k: round(float(v), 4) for k, v in mf.stats(r_du).items()}, f"to={to_du:.1f}", flush=True)

# 同池 FILTER-FIRST（含 MA20，对照用）
W_ff, log_ff = build_w(picks_ff, N=5)
r_ff, to_ff, ex_ff = mf.run_weekly(W_ff)
print("FF", {k: round(float(v), 4) for k, v in mf.stats(r_ff).items()}, f"to={to_ff:.1f}", flush=True)

# 等权
W_ew = {}
for dd in reb:
    pl = avail_pool(gi[dd])
    W_ew[dd] = {c: 1 / len(pl) for c in pl} if pl else {}
r_ew, to_ew, ex_ew = mf.run_weekly(W_ew)
print("EW", {k: round(float(v), 4) for k, v in mf.stats(r_ew).items()}, flush=True)

# 邻档：TS26 过滤；取 N=3；取 N=8
W_ts26, _ = build_w(picks_b1, ts_L=26, N=5)
r_ts26, to_ts26, ex_ts26 = mf.run_weekly(W_ts26)
W_n3, _ = build_w(picks_b1, ts_L=52, N=3)
r_n3, to_n3, ex_n3 = mf.run_weekly(W_n3)
W_n8, _ = build_w(lambda i, dd, ts_L=52, N=8: picks_b1(i, dd, ts_L, N), N=8)
# fix N=8 build
def build_n(N, ts_L=52):
    raw = {}
    for dd in reb:
        i = gi[dd]
        p, *_ = picks_b1(i, dd, ts_L=ts_L, N=N)
        w = {c: 1 / N for c in p}
        if len(p) < N and not pd.isna(P.at[dd, MF]):
            w[MF] = (N - len(p)) / N
        raw[dd] = w
    return raw
W_n3 = build_n(3); r_n3, to_n3, ex_n3 = mf.run_weekly(W_n3)
W_n8 = build_n(8); r_n8, to_n8, ex_n8 = mf.run_weekly(W_n8)
print("邻档 TS26/N3/N8", flush=True)
for lab, rr, tt in [("TS26", r_ts26, to_ts26), ("N3", r_n3, to_n3), ("N8", r_n8, to_n8)]:
    print(lab, {k: round(float(v), 4) for k, v in mf.stats(rr).items()}, f"to={tt:.1f}", flush=True)

# 持仓差异周
diff_weeks = []
short_weeks = []
empty_weeks = []
removed = []
for dd in reb:
    if gi[dd] < 52:
        continue
    pb = set(log_b1[dd][0]) if dd in log_b1 else set()
    px = set(picks_xs(gi[dd], 5))
    if pb != px:
        diff_weeks.append(dd)
    if len(pb) < 5:
        short_weeks.append(dd)
    if len(pb) == 0:
        empty_weeks.append(dd)
    if dd in log_b1 and len(log_b1[dd]) >= 2:
        removed.append(log_b1[dd][1] / max(log_b1[dd][2], 1))

n_wk = sum(1 for dd in reb if gi[dd] >= 52)
diff_pct = len(diff_weeks) / n_wk if n_wk else 0
print(f"持仓差异周 {len(diff_weeks)}/{n_wk} = {diff_pct:.1%}; 不足5只 {len(short_weeks)/n_wk:.1%}; 空仓 {len(empty_weeks)/n_wk:.1%}; 均剔除占比 {np.mean(removed):.1%}", flush=True)

# 下跌段
dd_b1 = mf.mdd(r_b1, "2021-09-01", "2024-09-30")
dd_xs = mf.mdd(r_xs, "2021-09-01", "2024-09-30")
shallow_pp = dd_b1 - dd_xs  # positive if B1 shallower
print(f"下跌段 DD B1={dd_b1:.1%} XS={dd_xs:.1%} 浅 {shallow_pp*100:+.1f}pp", flush=True)

# 证伪
f1 = diff_pct < 0.10
f2 = shallow_pp < 0.03  # 不浅≥3pp
f3 = to_b1 > to_xs * 1.5
falsified = f1 or f2 or f3
reasons = []
if f1: reasons.append(f"持仓差异周 {diff_pct:.1%}<10%")
if f2: reasons.append(f"下跌段回撤浅仅 {shallow_pp*100:+.1f}pp(<3pp)")
if f3: reasons.append(f"换手 {to_b1:.1f}x > XS×1.5={to_xs*1.5:.1f}x")
verdict = "**证伪**" if falsified else "**未证伪**"
fal_sentence = ("；".join(reasons) if reasons else f"持仓差异 {diff_pct:.1%}；下跌段浅 {shallow_pp*100:+.1f}pp；换手 {to_b1:.1f}x vs XS {to_xs:.1f}x") + ("。证伪成立。" if falsified else "。未触发证伪闸。")

ch = mf.champ()
books = {
    "MF-B1 先TS52>0再XS52取5(主版)": (r_b1, to_b1, ex_b1),
    "邻档 TS26过滤+XS52取5": (r_ts26, to_ts26, ex_ts26),
    "邻档 N=3": (r_n3, to_n3, ex_n3),
    "邻档 N=8": (r_n8, to_n8, ex_n8),
    "同池 XS52取5": (r_xs, to_xs, ex_xs),
    "同池 DUAL(先排后TS)": (r_du, to_du, ex_du),
    "同池 FILTER-FIRST(TS+MA20)": (r_ff, to_ff, ex_ff),
    "同池等权": (r_ew, to_ew, ex_ew),
    "冠军同引擎(研究副本)": ch,
}

# 归因
import attribution as A
# patch bench pool to industry EW
e._bench = {**e.benches(), "池等权(318有价,周调,0.2%RT)": (r_ew, to_ew, ex_ew)}
at = A.attribute(ID, "MF-B1主版", lambda i, dd: W_b1.get(dd, {}), OUT, True)

# 分类别贡献：持仓里的 family
main = "MF-B1 先TS52>0再XS52取5(主版)"
M_rows = [mf.row(k, *v[:3]) for k, v in books.items()]
M = pd.DataFrame(M_rows)

# 空仓周占比
empty_pct = len(empty_weeks) / n_wk if n_wk else 0
mf_w = np.mean([W_b1[dd].get(MF, 0) for dd in reb if gi[dd] >= 52])

report = HYPO + f"""
## 1. 准则原文
MF-B1：周频，A股行业主题池；先剔 52 周收益≤0，再 XS52 跳1 取5；不足补 511880；**禁止** MA20 逐只筛。对照同池 XS52、FILTER-FIRST、DUAL、等权。

## 2. 实现要点
- 池：行业主题 **{len(ind)}** 只（research_pool_v2 ∩ mom 宇宙）。
- 信号：周五≥14:30；TS52 = SIG/ W_{{t-52}} −1；过滤后 XS52 skip1 取5，等权 1/5，空位 511880。
- 无 TV、无 MA20。邻档：TS26 过滤、N=3、N=8。
- 成本 0.2%RT；{mf.START}→{mf.END}。

## 3. 主表
{mf.metrics_table(M, main)}

### 逻辑闸诊断
- 与 XS52 持仓差异周：**{len(diff_weeks)}/{n_wk} = {diff_pct:.1%}**（证伪闸 <10%）
- 下跌段 2021-09→2024-09：B1 DD {dd_b1:.1%} vs XS {dd_xs:.1%}，浅 **{shallow_pp*100:+.1f}pp**（证伪闸需≥3pp）
- 换手：B1 {to_b1:.1f}x vs XS {to_xs:.1f}x（×{to_b1/to_xs if to_xs else float('nan'):.2f}；证伪闸 >1.5×）
- 均剔除占比 {np.mean(removed):.1%}；不足5只周 {len(short_weeks)/n_wk:.1%}；空仓周 {empty_pct:.1%}；均 511880 权重 {mf_w:.2f}

### 逐年（主版 / XS / EW）
"""
Y = pd.concat([mf.yearly(books[k][0]).assign(book=k) for k in [main, "同池 XS52取5", "同池等权"]])
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

mf.deliver(ID, books, main, f"{ID}（周频，行业主题，0.2%RT）", report, at["md"])
M.to_csv(f"{OUT}/metrics.csv", index=False)
diag = dict(diff_pct=diff_pct, shallow_pp=shallow_pp, to_b1=to_b1, to_xs=to_xs, falsified=falsified,
            n_removed_mean=float(np.mean(removed)), empty_pct=empty_pct)
pickle.dump(dict(W_b1=W_b1, diag=diag, log_b1=log_b1), open(f"{OUT}/_res.pkl", "wb"))
pd.Series(diag).to_csv(f"{OUT}/diag.csv")
print("DONE", verdict, fal_sentence, flush=True)
print(M[["book", "ret", "maxDD", "Calmar", "turnover", "avg_expo"]].round(3).to_string(), flush=True)
