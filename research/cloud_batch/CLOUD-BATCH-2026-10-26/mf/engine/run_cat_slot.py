#!/usr/bin/env python3
"""MF-CAT-SLOT：6 类互斥 · 组内 AUM 降序取 K（无 ρ 去重/无 XS）· 类间等权；空位 511880。
相对 CAT-MOM：关掉组内动量与去重，只留强制类间席位预算。"""
from __future__ import annotations
import os, sys, pickle, math, random
from collections import defaultdict
from pathlib import Path
import numpy as np
import pandas as pd
from scipy.cluster.hierarchy import linkage, fcluster
from scipy.spatial.distance import squareform

sys.path.insert(0, "/workspace/etf-multifreq/engine")
sys.path.insert(0, "/workspace/etf-momentum/engine")
import mf_common as mf
import mom_engine as e
import attribution as A

ID = "MF-CAT-SLOT"
OUT = f"{mf.OUT_ROOT}/{ID}"
Path(OUT).mkdir(parents=True, exist_ok=True)
LOG = open(f"{OUT}/_run.log", "w", buffering=1)

def log(msg):
    print(msg, flush=True)
    LOG.write(msg + "\n")

HYPO = """## 0. 假设与证伪（开跑前写死）
- **假设**：关掉组内 ρ 去重与 XS52，仅保留同 K 的 AUM 占位 + 类间等权，若仍接近/优于 CAT-MOM 或优于混排 Calmar，则坐实「超额在跨类席位」。
- **证伪**（任一）：
  1. Calmar < 混排×0.9（或 ΔCalmar≤−0.05 vs 混排）；或
  2. 2023–26 收益 < 混排×0.9；或
  3. 相对 CAT-MOM ΔCalmar ≤ −0.08 **且** 2023–26 明显弱于 CAT-MOM。
- **成功倾向**：全样本 Calmar ≥ 混排，且相对 CAT-MOM ΔCalmar ≥ −0.05；2023–26 ≥ 混排×0.9。
- **红线**：不合层、不叠强栈、不换冠、不碰实盘/LIVE/SPIKE/OPT。
"""

# ---------- data ----------
D = mf.data()
P, W0, SIG, G, gi, reb = D["P"], D["W"], D["SIG"], D["G"], D["gi"], D["reb"]
MF = mf.MF  # 511880

pool = pd.read_csv("/workspace/etf-correlation/data/research_pool_v2.csv", dtype={"code": str})
pool["code"] = pool.code.str.zfill(6)
pool = pool.drop_duplicates("code").set_index("code")
if "aum" not in pool.columns:
    raise SystemExit("FATAL: research_pool_v2 缺 aum 列，停跑勿猜")
AUM = pool["aum"].astype(float)
if AUM.isna().all():
    raise SystemExit("FATAL: aum 全空，停跑勿猜")

CAT_ORDER = ["A股宽基", "行业主题", "港股", "跨境", "商品", "债券货币"]
K_MAIN = {"A股宽基": 2, "行业主题": 3, "港股": 2, "跨境": 1, "商品": 1, "债券货币": 1}

def cat_of(c: str):
    if c not in pool.index:
        return None
    r = pool.loc[c]
    l0, fam = r.l0, str(r.family)
    if l0 == "中国权益" and fam.startswith("宽基"):
        return "A股宽基"
    if l0 == "中国权益":
        return "行业主题"
    if l0 == "港股中资离岸":
        return "港股"
    if l0 == "海外权益":
        return "跨境"
    if l0 == "商品":
        return "商品"
    if l0 == "债券货币":
        return "债券货币"
    return None

CAT = {k: [] for k in CAT_ORDER}
for c in P.columns:
    k = cat_of(c)
    if k:
        CAT[k].append(c)
for k in CAT_ORDER:
    CAT[k] = sorted(set(CAT[k]))
    log(f"CAT {k}: {len(CAT[k])}")

ALL = sorted({c for cs in CAT.values() for c in cs})
CN_CATS = ["A股宽基", "行业主题"]

W = W0.copy()
missing = [c for c in ALL if c not in W.columns]
if missing:
    add = P[missing].reindex(G)
    W = W.join(add, how="left")
    log(f"extended W with {len(missing)} codes (bonds etc)")
if MF not in W.columns and MF in P.columns:
    W[MF] = P[MF].reindex(G)

R_daily = P.pct_change()

def mom_ext(i, L=52, skip=1, codes=None):
    if i - L < 0:
        return pd.Series(dtype=float)
    end = W.iloc[i - skip]
    s = end / W.iloc[i - L] - 1
    av = W.iloc[i].notna()
    s = s[av].dropna()
    if codes is not None:
        s = s[[c for c in s.index if c in codes]]
    return s

def avail_codes(i, codes):
    row = W.iloc[i]
    return [c for c in codes if c in row.index and pd.notna(row[c])]

def aum_of(c):
    if c in AUM.index and pd.notna(AUM[c]):
        return float(AUM[c])
    return -1.0

def dedup_keep(dd, codes, look=60):
    """CAT-MOM 复用：ρ≥0.9 去重留 AUM 最大。"""
    if len(codes) <= 1:
        return list(codes), 0
    if dd not in P.index:
        return list(codes), 0
    loc = P.index.get_loc(dd)
    if isinstance(loc, slice):
        return list(codes), 0
    if loc < look:
        return list(codes), 0
    seg = R_daily[codes].iloc[loc - look:loc]
    ok = [c for c in codes if seg[c].notna().sum() >= int(look * 0.8)]
    n_hist_drop = len(codes) - len(ok)
    if len(ok) <= 1:
        return ok, n_hist_drop
    C = seg[ok].corr(min_periods=int(look * 0.6))
    C = C.dropna(how="all").dropna(axis=1, how="all")
    if C.shape[0] <= 1:
        return list(C.index), n_hist_drop + (len(ok) - C.shape[0])
    Cv = C.values.copy()
    np.fill_diagonal(Cv, 1.0)
    Cv = np.where(np.isnan(Cv), 0.0, Cv)
    Cv = (Cv + Cv.T) / 2
    np.fill_diagonal(Cv, 1.0)
    Dist = np.clip(1.0 - Cv, 0, 2)
    np.fill_diagonal(Dist, 0.0)
    try:
        condensed = squareform(Dist, checks=False)
        Z = linkage(condensed, method="complete")
        lab = fcluster(Z, t=0.1, criterion="distance")
    except Exception as ex:
        log(f"  cluster fail {dd.date()} n={len(ok)}: {ex}")
        return ok, n_hist_drop
    kept = []
    for k in set(lab):
        mem = list(C.index[lab == k])
        if len(mem) == 1:
            kept.append(mem[0])
        else:
            aums = [(c, aum_of(c)) for c in mem]
            aums.sort(key=lambda x: -x[1])
            kept.append(aums[0][0])
    n_dup_drop = len(ok) - len(kept)
    return kept, n_hist_drop + n_dup_drop

def picks_aum(i, cat, K):
    """AUM 降序取前 K；禁止 mom/XS。可投不足 K 则有多少取多少。"""
    members = CAT[cat]
    base = avail_codes(i, members)
    base = [c for c in base if c != MF]  # 货币不作风险占位
    if not base:
        return []
    ranked = sorted(base, key=lambda c: (-aum_of(c), c))
    return ranked[:K]

def picks_random(i, cat, K, rng):
    members = CAT[cat]
    base = avail_codes(i, members)
    base = [c for c in base if c != MF]
    if not base:
        return []
    k = min(K, len(base))
    return list(rng.sample(base, k))

def picks_cat_mom(i, dd, cat, K, do_dedup=True):
    """CAT-MOM 同口径：ρ去重 + XS52 取 K。"""
    members = CAT[cat]
    if i < 52:
        return [], 0
    base = avail_codes(i, members)
    if do_dedup:
        kept, n_drop = dedup_keep(dd, base, 60)
    else:
        kept, n_drop = base, 0
    if not kept:
        return [], n_drop
    s = mom_ext(i, 52, 1, codes=set(kept))
    if s.empty:
        return [], n_drop
    top = list(s.sort_values(ascending=False).index[:K])
    return top, n_drop

def build_wmap_aum(K_map, cats=None, fill_mf=True, record_meta=None, mode="aum", seed=42):
    """mode=aum|random；组内占位后类间等权。"""
    cats = cats or CAT_ORDER
    rng = random.Random(seed)
    raw = {}
    for dd in reb:
        i = gi[dd]
        # per-week seeded RNG for reproducibility of random mode
        week_rng = random.Random(seed + int(pd.Timestamp(dd).strftime("%Y%m%d")))
        active = {}
        for cat in cats:
            K = K_map.get(cat, 1)
            if mode == "aum":
                p = picks_aum(i, cat, K)
            elif mode == "random":
                p = picks_random(i, cat, K, week_rng)
            else:
                raise ValueError(mode)
            if p:
                active[cat] = p
        if record_meta is not None:
            record_meta.setdefault("active", {})[dd] = {c: list(v) for c, v in active.items()}
            record_meta.setdefault("n_active", {})[dd] = len(active)
        if not active:
            raw[dd] = {MF: 1.0} if fill_mf and MF in P.columns and not pd.isna(P.at[dd, MF]) else {}
            continue
        n = len(active)
        w = {}
        for cat, picks in active.items():
            share = 1.0 / n
            ew = share / len(picks)
            for c in picks:
                w[c] = w.get(c, 0.0) + ew
        s = sum(w.values())
        if fill_mf and s < 1 - 1e-9 and MF in P.columns and not pd.isna(P.at[dd, MF]):
            w[MF] = w.get(MF, 0.0) + (1.0 - s)
        raw[dd] = w
    return raw

def build_wmap_mom(K_map, do_dedup=True, cats=None, fill_mf=True, record_meta=None):
    """同引擎重跑 CAT-MOM 主版。"""
    cats = cats or CAT_ORDER
    raw = {}
    for dd in reb:
        i = gi[dd]
        active = {}
        drops = {}
        for cat in cats:
            K = K_map.get(cat, 1)
            p, nd = picks_cat_mom(i, dd, cat, K, do_dedup=do_dedup)
            drops[cat] = nd
            if p:
                active[cat] = p
        if record_meta is not None:
            record_meta.setdefault("active", {})[dd] = {c: list(v) for c, v in active.items()}
            record_meta.setdefault("drops", {})[dd] = dict(drops)
            record_meta.setdefault("n_active", {})[dd] = len(active)
        if not active:
            raw[dd] = {MF: 1.0} if fill_mf and MF in P.columns and not pd.isna(P.at[dd, MF]) else {}
            continue
        n = len(active)
        w = {}
        for cat, picks in active.items():
            share = 1.0 / n
            ew = share / len(picks)
            for c in picks:
                w[c] = w.get(c, 0.0) + ew
        s = sum(w.values())
        if fill_mf and s < 1 - 1e-9 and MF in P.columns and not pd.isna(P.at[dd, MF]):
            w[MF] = w.get(MF, 0.0) + (1.0 - s)
        raw[dd] = w
    return raw

def build_mix_xs(N=5, codes=None):
    codes = set(codes or ALL)
    raw = {}
    for dd in reb:
        i = gi[dd]
        if i < 52:
            raw[dd] = {}; continue
        s = mom_ext(i, 52, 1, codes=codes)
        if s.empty:
            raw[dd] = {}; continue
        top = list(s.sort_values(ascending=False).index[:N])
        raw[dd] = {c: 1.0 / len(top) for c in top} if top else {}
    return raw

def build_pool_ew(codes=None):
    codes_all = set(codes or ALL)
    raw = {}
    for dd in reb:
        i = gi[dd]
        pl = avail_codes(i, codes_all)
        pl = [c for c in pl if c != MF]
        raw[dd] = {c: 1.0 / len(pl) for c in pl} if pl else ({MF: 1.0} if MF in P.columns else {})
    return raw

def build_cat_ew_no_mom(cats=None, fill_mf=True):
    cats = cats or CAT_ORDER
    raw = {}
    for dd in reb:
        i = gi[dd]
        active = {}
        for cat in cats:
            pl = avail_codes(i, CAT[cat])
            pl = [c for c in pl if c != MF]
            if pl:
                active[cat] = pl
        if not active:
            raw[dd] = {MF: 1.0} if fill_mf and MF in P.columns and not pd.isna(P.at[dd, MF]) else {}
            continue
        n = len(active)
        w = {}
        for cat, picks in active.items():
            share = 1.0 / n
            ew = share / len(picks)
            for c in picks:
                w[c] = w.get(c, 0.0) + ew
        raw[dd] = w
    return raw

def holdings_set(wmap_dd):
    """非货币持仓代码集合。"""
    return {c for c, w in wmap_dd.items() if w > 1e-12 and c != MF}

def jaccard(a, b):
    if not a and not b:
        return 1.0
    u = a | b
    if not u:
        return 1.0
    return len(a & b) / len(u)

# ---------- build books ----------
log("building MAIN CAT-SLOT (AUM-K) ...")
meta_main = {}
W_main = build_wmap_aum(K_MAIN, mode="aum", record_meta=meta_main)
r_main, to_main, ex_main = mf.run_weekly(W_main)
log(f"MAIN { {k: round(float(v),4) for k,v in mf.stats(r_main).items()} } to={to_main:.2f} ex={ex_main:.2f}")

log("building CAT-MOM 主版同引擎重跑 ...")
meta_mom = {}
W_mom = build_wmap_mom(K_MAIN, do_dedup=True, record_meta=meta_mom)
r_mom, to_mom, ex_mom = mf.run_weekly(W_mom)
log(f"CATMOM { {k: round(float(v),4) for k,v in mf.stats(r_mom).items()} } to={to_mom:.2f}")

log("building 邻档 随机取K seed=42 ...")
meta_rnd = {}
W_rnd = build_wmap_aum(K_MAIN, mode="random", seed=42, record_meta=meta_rnd)
r_rnd, to_rnd, ex_rnd = mf.run_weekly(W_rnd)
log(f"RAND { {k: round(float(v),4) for k,v in mf.stats(r_rnd).items()} } to={to_rnd:.2f}")

log("building 旁注仅中国权益 AUM-K ...")
meta_cn = {}
W_cn = build_wmap_aum({c: K_MAIN[c] for c in CN_CATS}, cats=CN_CATS, mode="aum", record_meta=meta_cn)
r_cn, to_cn, ex_cn = mf.run_weekly(W_cn)
log(f"CN { {k: round(float(v),4) for k,v in mf.stats(r_cn).items()} } to={to_cn:.2f}")

log("building 混排 XS52取5 ...")
W_mix = build_mix_xs(5, ALL)
r_mix, to_mix, ex_mix = mf.run_weekly(W_mix)
log(f"MIX { {k: round(float(v),4) for k,v in mf.stats(r_mix).items()} } to={to_mix:.2f}")

log("building 全池等权 ...")
W_pew = build_pool_ew(ALL)
r_pew, to_pew, ex_pew = mf.run_weekly(W_pew)
log(f"POOL_EW { {k: round(float(v),4) for k,v in mf.stats(r_pew).items()} } to={to_pew:.2f}")

log("building 类内等权·类间等权(无动量) ...")
W_cew = build_cat_ew_no_mom()
r_cew, to_cew, ex_cew = mf.run_weekly(W_cew)
log(f"CAT_EW { {k: round(float(v),4) for k,v in mf.stats(r_cew).items()} } to={to_cew:.2f}")

ch = mf.champ()

books = {
    "MF-CAT-SLOT AUM取K·类间等权(主版)": (r_main, to_main, ex_main),
    "MF-CAT-MOM 类内XS+去重·类间等权(同引擎重跑)": (r_mom, to_mom, ex_mom),
    "邻档 组内随机取K(seed=42)": (r_rnd, to_rnd, ex_rnd),
    "类内等权再类间等权(无动量)": (r_cew, to_cew, ex_cew),
    "旁注 仅中国权益两类(AUM-K)": (r_cn, to_cn, ex_cn),
    "全池混排 XS52跳1取5": (r_mix, to_mix, ex_mix),
    "全池等权周调": (r_pew, to_pew, ex_pew),
    "冠军同引擎(研究副本)": ch,
}

# ---------- falsification ----------
sm, sx, so = mf.stats(r_main), mf.stats(r_mix), mf.stats(r_mom)
a_m = mf.stats(r_main[r_main.index <= "2022-12-31"])
a_x = mf.stats(r_mix[r_mix.index <= "2022-12-31"])
a_o = mf.stats(r_mom[r_mom.index <= "2022-12-31"])
b_m = mf.stats(r_main[r_main.index >= "2023-01-01"])
b_x = mf.stats(r_mix[r_mix.index >= "2023-01-01"])
b_o = mf.stats(r_mom[r_mom.index >= "2023-01-01"])

dC_mix = sm["Calmar"] - sx["Calmar"]
dC_mom = sm["Calmar"] - so["Calmar"]

f1 = (sm["Calmar"] < sx["Calmar"] * 0.9) or (dC_mix <= -0.05)
f2 = b_m["ret"] < b_x["ret"] * 0.9
# 闸3：ΔC vs CAT-MOM ≤ -0.08 且 2023-26 明显弱于 CAT-MOM（< CAT-MOM ×0.9）
f3 = (dC_mom <= -0.08) and (b_m["ret"] < b_o["ret"] * 0.9)
falsified = f1 or f2 or f3
reasons = []
if f1:
    reasons.append(
        f"Calmar {sm['Calmar']:.2f} vs 混排 {sx['Calmar']:.2f}（Δ{dC_mix:+.2f}；闸 <×0.9={sx['Calmar']*0.9:.2f} 或 Δ≤−0.05）"
    )
if f2:
    reasons.append(
        f"2023–26 ret {b_m['ret']:.1%} < 混排×0.9={b_x['ret']*0.9:.1%}（混排 {b_x['ret']:.1%}）"
    )
if f3:
    reasons.append(
        f"vs CAT-MOM ΔCalmar {dC_mom:+.2f}≤−0.08 且 2023–26 {b_m['ret']:.1%} < CAT-MOM×0.9={b_o['ret']*0.9:.1%}（CAT-MOM {b_o['ret']:.1%}）"
    )
verdict = "**证伪**" if falsified else "**未证伪**"
fal = ("；".join(reasons) if reasons else
       f"Calmar {sm['Calmar']:.2f} vs 混排 {sx['Calmar']:.2f}（Δ{dC_mix:+.2f}）/ vs CAT-MOM {so['Calmar']:.2f}（Δ{dC_mom:+.2f}）；"
       f"2023–26 {b_m['ret']:.1%} vs 混排 {b_x['ret']:.1%} / CAT-MOM {b_o['ret']:.1%}"
       ) + ("。证伪成立。" if falsified else "。未触发证伪闸。")

# ---------- overlap Jaccard ----------
jacs = []
overlap_rows = []
for dd in reb:
    a = holdings_set(W_main.get(dd, {}))
    b = holdings_set(W_mom.get(dd, {}))
    j = jaccard(a, b)
    jacs.append(j)
    overlap_rows.append({
        "dd": dd,
        "n_slot": len(a),
        "n_mom": len(b),
        "n_inter": len(a & b),
        "n_union": len(a | b),
        "jaccard": j,
    })
jac_mean = float(np.mean(jacs)) if jacs else float("nan")
pd.DataFrame(overlap_rows).to_csv(f"{OUT}/side_overlap_jaccard.csv", index=False)
log(f"mean weekly Jaccard(AUM-K vs CAT-MOM) = {jac_mean:.3f}")

# ---------- attribution ----------
n_weeks = len(reb)
active_map = meta_main.get("active", {})
open_cnt = {c: 0 for c in CAT_ORDER}
for dd in reb:
    act = active_map.get(dd, {})
    for c in CAT_ORDER:
        if c in act and act[c]:
            open_cnt[c] += 1

rec = {}
_ = e.run_weights(lambda i, dd: W_main.get(dd, {}), record=rec)
C = pd.DataFrame(rec.get("contrib", {})).T.fillna(0.0).sort_index()
C.index = pd.to_datetime(C.index)
code2cat = {c: cat_of(c) for c in C.columns}
cat_daily = pd.DataFrame(0.0, index=C.index, columns=CAT_ORDER + ["其他"])
mf_daily = pd.Series(0.0, index=C.index)
for c in C.columns:
    if c == MF:
        mf_daily += C[c]
        continue
    k = code2cat.get(c)
    if k in CAT_ORDER:
        cat_daily[k] += C[c]
    else:
        cat_daily["其他"] += C[c]
cat_daily["空位511880"] = mf_daily
cat_tot = cat_daily.sum()
cat_weekly = cat_daily.copy()
cat_weekly["week"] = cat_weekly.index.to_period("W")
cw = cat_weekly.groupby("week").sum()

side = pd.DataFrame({
    "category": CAT_ORDER,
    "n_members": [len(CAT[c]) for c in CAT_ORDER],
    "open_weeks": [open_cnt[c] for c in CAT_ORDER],
    "open_pct": [open_cnt[c] / n_weeks for c in CAT_ORDER],
    "contrib_sum": [float(cat_tot.get(c, 0)) for c in CAT_ORDER],
})
side.to_csv(f"{OUT}/side_category.csv", index=False)
cw.to_csv(f"{OUT}/side_cat_weekly_contrib.csv")
pd.DataFrame([
    {"dd": dd, "n_active": meta_main.get("n_active", {}).get(dd, 0),
     **{f"pick_{c}": ",".join(active_map.get(dd, {}).get(c, [])) for c in CAT_ORDER}}
    for dd in reb
]).to_csv(f"{OUT}/side_weekly_picks.csv", index=False)

log("side_category:\n" + side.to_string(index=False))

try:
    e._bench = {**e.benches(), "池等权(318有价,周调,0.2%RT)": (r_pew, to_pew, ex_pew)}
    at = A.attribute(ID, "MF-CAT-SLOT主版", lambda i, dd: W_main.get(dd, {}), OUT, True)
    attr_mod = at["md"]
except Exception as ex:
    log(f"attribution module err: {ex}")
    attr_mod = f"_attribution 模块异常：{ex}_\n"

attr_md = f"""## 归因 · MF-CAT-SLOT

### 拆解摘要（模块）
{attr_mod}

### 类别开启周占比（主版 AUM-K，共 {n_weeks} 个信号周）
| 类别 | 成员数 | 开启周 | 开启占比 | 贡献Σ |
|---|---:|---:|---:|---:|
"""
for r in side.itertuples(index=False):
    attr_md += (f"| {r.category} | {int(r.n_members)} | {int(r.open_weeks)} | {r.open_pct:.1%} | "
                f"{r.contrib_sum:+.3f} |\n")
attr_md += f"""
空位 511880 贡献Σ = {float(mf_daily.sum()):+.3f}

### 席位重合率（AUM-K vs CAT-MOM 同引擎重跑）
- 周均 Jaccard（|∩|/|∪|，剔货币）= **{jac_mean:.3f}**
- 明细：`side_overlap_jaccard.csv`

### 择时 / 选品 / 成本（定性）
- **择时**：无 TV/breadth/HYST；仓位由有信号类别数决定（类间等权，常近满仓）。
- **选品**：组内 **AUM 降序取 K**（占位，非动量）；无 ρ 去重、无 XS52。相对 CAT-MOM 关掉组内选品信息，只留强制类间席位。
- **成本**：0.2%RT；主版换手 {to_main:.1f}x / 年（单边）vs 混排 {to_mix:.1f}x / CAT-MOM {to_mom:.1f}x。

旁注 CSV：`side_category.csv` / `side_cat_weekly_contrib.csv` / `side_weekly_picks.csv` / `side_overlap_jaccard.csv`
"""

# ---------- REPORT ----------
main = "MF-CAT-SLOT AUM取K·类间等权(主版)"
M = pd.DataFrame([mf.row(k, *v[:3]) for k, v in books.items()])
report = HYPO + f"""
## 1. 准则原文
研究池 6 类互斥（l0+family，与 CAT-MOM 一致）：A股宽基 / 行业主题 / 港股 / 跨境 / 商品 / 债券货币。
每周五对**每一类独立**：①**不做** ρ 去重；②**不做** 组内动量；③按 **AUM 降序取前 K**（2/3/2/1/1/1）组内等权；④类间有信号等权，空位 511880。无 TV/breadth/HYST。

## 2. 实现要点
- 引擎：`run_cat_slot.py`（模板自 `run_cat_mom.py`）；池宽基{len(CAT['A股宽基'])}/行业{len(CAT['行业主题'])}/港{len(CAT['港股'])}/跨境{len(CAT['跨境'])}/商品{len(CAT['商品'])}/债{len(CAT['债券货币'])}。
- 组内占位：`avail_codes` → AUM 降序取 K（缺 AUM 视 −1）；**禁止** mom_ext/XS 进主版。
- **MF-CAT-MOM 主版**：同引擎重跑（`build_wmap_mom` do_dedup=True + XS52），口径对齐（非读旧表）。
- 对照：全池混排 XS52跳1取5；全池等权；类内等权再类间等权；冠军研究副本只读。
- 邻档：组内随机取K（seed=42，按周派生）；旁注仅中国权益两类（AUM-K）。
- 成本 0.2%RT；{mf.START}→{mf.END}；panel_v2 / mf_common。

## 3. 主表
{mf.metrics_table(M, main)}

### vs 混排 / vs CAT-MOM（证伪闸）
- Calmar **{sm['Calmar']:.2f}** vs 混排 {sx['Calmar']:.2f}（Δ {dC_mix:+.2f}；闸：<×0.9={sx['Calmar']*0.9:.2f} 或 Δ≤−0.05）
- Calmar vs CAT-MOM {so['Calmar']:.2f}（Δ {dC_mom:+.2f}；成功倾向 ≥−0.05；证伪闸3 ≤−0.08 且 2023–26 弱）
- 2023–26 ret **{b_m['ret']:.1%}** vs 混排 {b_x['ret']:.1%}（闸：<×0.9={b_x['ret']*0.9:.1%}）/ vs CAT-MOM {b_o['ret']:.1%}
- 换手 **{to_main:.1f}x** vs 混排 {to_mix:.1f}x / CAT-MOM {to_mom:.1f}x
- 全样本 ret/DD：{sm['ret']:.1%}/{sm['maxDD']:.1%} vs 混排 {sx['ret']:.1%}/{sx['maxDD']:.1%} / CAT-MOM {so['ret']:.1%}/{so['maxDD']:.1%}
- 2020–22：{a_m['ret']:.1%}/{a_m['maxDD']:.1%}/C{a_m['Calmar']:.2f} vs 混排 {a_x['ret']:.1%}/{a_x['maxDD']:.1%}/C{a_x['Calmar']:.2f} / CAT-MOM {a_o['ret']:.1%}/{a_o['maxDD']:.1%}/C{a_o['Calmar']:.2f}
- 席位重合率（周均 Jaccard）= **{jac_mean:.3f}**

### 类别旁注（主版 AUM-K）
| 类别 | 开启占比 | 贡献Σ |
|---|---:|---:|
"""
for r in side.itertuples(index=False):
    report += f"| {r.category} | {r.open_pct:.1%} | {r.contrib_sum:+.3f} |\n"

report += f"""
### 逐年
"""
Y = pd.concat([mf.yearly(books[k][0]).assign(book=k) for k in [
    main,
    "MF-CAT-MOM 类内XS+去重·类间等权(同引擎重跑)",
    "全池混排 XS52跳1取5",
    "邻档 组内随机取K(seed=42)",
    "类内等权再类间等权(无动量)",
]])
yp = Y.pivot(index="year", columns="book", values="ret")
yd = Y.pivot(index="year", columns="book", values="mdd")
ks = list(yp.columns)
report += "| 年 | " + " | ".join(ks) + " |\n|---|" + "---|" * len(ks) + "\n"
for y in yp.index:
    report += f"| {y} | " + " | ".join(
        f"{yp.at[y,k]:+.1%}/{yd.at[y,k]:.1%}" for k in ks) + " |\n"

report += f"""
## 4. 结论
{verdict}。{fal}

**证伪/失效句**：{fal}

产物：{OUT}/；不换冠军、不下单。CAT-MOM 列为同引擎重跑。
"""

mf.deliver(ID, books, main, f"{ID}（AUM占位·类间等权，0.2%RT）", report, attr_md)
M.to_csv(f"{OUT}/metrics.csv", index=False)
pickle.dump(dict(
    W_main=W_main, W_mom=W_mom, meta_main=meta_main, meta_mom=meta_mom,
    falsified=falsified, sm=sm, sx=sx, so=so,
    to_main=to_main, to_mix=to_mix, to_mom=to_mom,
    jac_mean=jac_mean, fal=fal, verdict=verdict,
    b_m=b_m, b_x=b_x, b_o=b_o, a_m=a_m, a_x=a_x, a_o=a_o,
    dC_mix=dC_mix, dC_mom=dC_mom,
), open(f"{OUT}/_res.pkl", "wb"))

# patch knife 一句证伪句
for knife_path in [
    Path("/workspace/etf-multifreq/knives/MF-CAT-SLOT.md"),
    Path("/workspace/strategy-weekly/knives/MF-CAT-SLOT.md"),
]:
    if knife_path.exists():
        txt = knife_path.read_text()
        if "（测试填）" in txt:
            knife_path.write_text(txt.replace("（测试填）", fal))
            log(f"patched knife: {knife_path}")

# Obsidian note
obs_dir = Path(mf.OBS)
obs_dir.mkdir(parents=True, exist_ok=True)
obs_path = obs_dir / "MF-CAT-SLOT.md"
obs_body = f"""# MF-CAT-SLOT

准则：`/workspace/etf-multifreq/knives/MF-CAT-SLOT.md`  
产物：`/workspace/etf-multifreq/MF-CAT-SLOT/`

{verdict} · 主版 {sm['ret']:.1%}/{sm['maxDD']:.1%}/C{sm['Calmar']:.2f} · 换手 {to_main:.1f}x  
vs 混排 {sx['ret']:.1%}/{sx['maxDD']:.1%}/C{sx['Calmar']:.2f}（ΔC{dC_mix:+.2f}）  
vs CAT-MOM(重跑) {so['ret']:.1%}/{so['maxDD']:.1%}/C{so['Calmar']:.2f}（ΔC{dC_mom:+.2f}）  
2023–26 {b_m['ret']:.1%} vs 混排{b_x['ret']:.1%} / CAT-MOM{b_o['ret']:.1%}  
席位重合周均 Jaccard={jac_mean:.3f}

**证伪句**：{fal}

#ETF多频专题
"""
obs_path.write_text(obs_body)
log(f"obsidian: {obs_path}")

log("DONE " + verdict + " " + fal)
log(M[["book", "ret", "maxDD", "Calmar", "turnover", "avg_expo"]].round(3).to_string())
LOG.close()
