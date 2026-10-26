#!/usr/bin/env python3
"""MF-CAT-MOM：6 类互斥 · 组内 ρ≥0.9 去重留 AUM 最大 · XS52 取 K · 类间等权；空位 511880。"""
from __future__ import annotations
import os, sys, pickle, math
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

ID = "MF-CAT-MOM"
OUT = f"{mf.OUT_ROOT}/{ID}"
Path(OUT).mkdir(parents=True, exist_ok=True)
LOG = open(f"{OUT}/_run.log", "w", buffering=1)

def log(msg):
    print(msg, flush=True)
    LOG.write(msg + "\n")

HYPO = """## 0. 假设与证伪（开跑前写死）
- **假设**：关掉全池混排、强制 6 类内独立选品（ρ≥0.9 去重留 AUM 最大 + XS52 取 K）再类间等权，可在压同质化/回撤的同时保住相对混排的 Calmar。
- **证伪**（任一）：
  1. Calmar < 混排 ×0.9 或 ΔCalmar≤−0.05；
  2. 2023–26 收益 < 混排 ×0.9；
  3. 换手 > 混排 ×1.5 且 Calmar 无改善。
- **红线**：不合层、不叠 B50+HYST+511260、不换冠、不碰实盘/LIVE/SPIKE/OPT。
"""

# ---------- data ----------
D = mf.data()
P, W0, SIG, G, gi, reb = D["P"], D["W"], D["SIG"], D["G"], D["gi"], D["reb"]
MF = mf.MF  # 511880

pool = pd.read_csv("/workspace/etf-correlation/data/research_pool_v2.csv", dtype={"code": str})
pool["code"] = pool.code.str.zfill(6)
pool = pool.drop_duplicates("code").set_index("code")
AUM = pool["aum"].astype(float)

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

# members with daily price
CAT = {k: [] for k in CAT_ORDER}
for c in P.columns:
    k = cat_of(c)
    if k:
        CAT[k].append(c)
for k in CAT_ORDER:
    CAT[k] = sorted(set(CAT[k]))
    log(f"CAT {k}: {len(CAT[k])}")

ALL = sorted({c for cs in CAT.values() for c in cs})
# China-only subset for 旁注
CN_CATS = ["A股宽基", "行业主题"]

# Extend weekly panel for bonds / anything in P but missing from W
W = W0.copy()
missing = [c for c in ALL if c not in W.columns]
if missing:
    add = P[missing].reindex(G)
    W = W.join(add, how="left")
    log(f"extended W with {len(missing)} codes (bonds etc)")
# ensure MF weekly exists for availability checks (not used in mom ranking necessarily)
if MF not in W.columns and MF in P.columns:
    W[MF] = P[MF].reindex(G)

R_daily = P.pct_change()

def mom_ext(i, L=52, skip=1, codes=None):
    """XS momentum on extended W; optional code filter."""
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
    """codes with price on grid i."""
    row = W.iloc[i]
    return [c for c in codes if c in row.index and pd.notna(row[c])]

def dedup_keep(dd, codes, look=60):
    """Complete-linkage on 60d corr; keep max-AUM per cluster (ρ≥0.9 ↔ dist≤0.1).
    Returns (kept_list, n_dropped). Codes with <look days history dropped before cluster."""
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
    # require ≥80% non-na in window
    ok = [c for c in codes if seg[c].notna().sum() >= int(look * 0.8)]
    n_hist_drop = len(codes) - len(ok)
    if len(ok) <= 1:
        return ok, n_hist_drop
    C = seg[ok].corr(min_periods=int(look * 0.6))
    C = C.dropna(how="all").dropna(axis=1, how="all")
    if C.shape[0] <= 1:
        return list(C.index), n_hist_drop + (len(ok) - C.shape[0])
    # fill residual nan on off-diag with 0 (uncorrelated) so clustering can proceed
    Cv = C.values.copy()
    np.fill_diagonal(Cv, 1.0)
    Cv = np.where(np.isnan(Cv), 0.0, Cv)
    # symmetrize
    Cv = (Cv + Cv.T) / 2
    np.fill_diagonal(Cv, 1.0)
    D = np.clip(1.0 - Cv, 0, 2)
    np.fill_diagonal(D, 0.0)
    try:
        condensed = squareform(D, checks=False)
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
            # max AUM
            aums = [(c, float(AUM[c]) if c in AUM.index and pd.notna(AUM[c]) else -1) for c in mem]
            aums.sort(key=lambda x: -x[1])
            kept.append(aums[0][0])
    n_dup_drop = len(ok) - len(kept)
    return kept, n_hist_drop + n_dup_drop

def picks_cat(i, dd, cat, K, do_dedup=True):
    """Return list of codes (len≤K) for one category."""
    members = CAT[cat]
    if i < 52:
        return [], 0
    base = avail_codes(i, members)
    # also need 60d history for dedup; mom needs L=52 weeks
    if do_dedup:
        kept, n_drop = dedup_keep(dd, base, 60)
    else:
        # still drop insufficient 60d for fair mom? knife 无去重邻档: only skip dedup
        kept, n_drop = base, 0
    if not kept:
        return [], n_drop
    s = mom_ext(i, 52, 1, codes=set(kept))
    if s.empty:
        return [], n_drop
    top = list(s.sort_values(ascending=False).index[:K])
    return top, n_drop

def build_wmap(K_map, do_dedup=True, cats=None, fill_mf=True, record_meta=None):
    """Category-internal XS + inter-cat EW. record_meta collects per-week stats if dict."""
    cats = cats or CAT_ORDER
    raw = {}
    for dd in reb:
        i = gi[dd]
        active = {}  # cat -> list of picks
        drops = {}
        for cat in cats:
            K = K_map.get(cat, 1)
            p, nd = picks_cat(i, dd, cat, K, do_dedup=do_dedup)
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
            # shouldn't happen if cats EW to 1, but guard
            w[MF] = w.get(MF, 0.0) + (1.0 - s)
        raw[dd] = w
    return raw

def build_mix_xs(N=5, codes=None):
    """Full-pool mixed XS52 topN EW (混排)."""
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
        # exclude pure MF from "pool EW" of research names? include all ALL
        pl = [c for c in pl if c != MF]  # cash not in equal-weight risk pool
        raw[dd] = {c: 1.0 / len(pl) for c in pl} if pl else ({MF: 1.0} if MF in P.columns else {})
    return raw

def build_cat_ew_no_mom(cats=None, fill_mf=True):
    """各类别内等权（有价全员）再类间等权，无动量、无去重。"""
    cats = cats or CAT_ORDER
    raw = {}
    for dd in reb:
        i = gi[dd]
        active = {}
        for cat in cats:
            pl = avail_codes(i, CAT[cat])
            pl = [c for c in pl if c != MF]  # 货币不进「类别等权」风险腿；仍可作空位
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

# ---------- build books ----------
log("building main CAT-MOM ...")
meta_main = {}
W_main = build_wmap(K_MAIN, do_dedup=True, record_meta=meta_main)
r_main, to_main, ex_main = mf.run_weekly(W_main)
log(f"MAIN { {k: round(float(v),4) for k,v in mf.stats(r_main).items()} } to={to_main:.2f} ex={ex_main:.2f}")

log("building 无去重 ...")
W_nodup = build_wmap(K_MAIN, do_dedup=False)
r_nodup, to_nodup, ex_nodup = mf.run_weekly(W_nodup)
log(f"NODUP { {k: round(float(v),4) for k,v in mf.stats(r_nodup).items()} } to={to_nodup:.2f}")

log("building K=1 ...")
K1 = {c: 1 for c in CAT_ORDER}
W_k1 = build_wmap(K1, do_dedup=True)
r_k1, to_k1, ex_k1 = mf.run_weekly(W_k1)
log(f"K1 { {k: round(float(v),4) for k,v in mf.stats(r_k1).items()} } to={to_k1:.2f}")

log("building 行业K=5 ...")
K_ind5 = dict(K_MAIN); K_ind5["行业主题"] = 5
W_ind5 = build_wmap(K_ind5, do_dedup=True)
r_ind5, to_ind5, ex_ind5 = mf.run_weekly(W_ind5)
log(f"IND5 { {k: round(float(v),4) for k,v in mf.stats(r_ind5).items()} } to={to_ind5:.2f}")

log("building 旁注仅中国权益 ...")
meta_cn = {}
W_cn = build_wmap({c: K_MAIN[c] for c in CN_CATS}, do_dedup=True, cats=CN_CATS, record_meta=meta_cn)
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
    "MF-CAT-MOM 类内XS+去重·类间等权(主版)": (r_main, to_main, ex_main),
    "邻档 无去重(同K)": (r_nodup, to_nodup, ex_nodup),
    "邻档 每类取1": (r_k1, to_k1, ex_k1),
    "邻档 行业K=5": (r_ind5, to_ind5, ex_ind5),
    "旁注 仅中国权益两类": (r_cn, to_cn, ex_cn),
    "全池混排 XS52跳1取5": (r_mix, to_mix, ex_mix),
    "全池等权周调": (r_pew, to_pew, ex_pew),
    "类内等权再类间等权(无动量)": (r_cew, to_cew, ex_cew),
    "冠军同引擎(研究副本)": ch,
}

# ---------- falsification ----------
sm, sx = mf.stats(r_main), mf.stats(r_mix)
a_m = mf.stats(r_main[r_main.index <= "2022-12-31"])
a_x = mf.stats(r_mix[r_mix.index <= "2022-12-31"])
b_m = mf.stats(r_main[r_main.index >= "2023-01-01"])
b_x = mf.stats(r_mix[r_mix.index >= "2023-01-01"])

f1 = (sm["Calmar"] < sx["Calmar"] * 0.9) or ((sm["Calmar"] - sx["Calmar"]) <= -0.05)
f2 = b_m["ret"] < b_x["ret"] * 0.9
f3 = (to_main > to_mix * 1.5) and not (sm["Calmar"] > sx["Calmar"])
falsified = f1 or f2 or f3
reasons = []
if f1:
    reasons.append(f"Calmar {sm['Calmar']:.2f} vs 混排 {sx['Calmar']:.2f}（Δ{sm['Calmar']-sx['Calmar']:+.2f}；闸 <×0.9 或 Δ≤−0.05）")
if f2:
    reasons.append(f"2023–26 ret {b_m['ret']:.1%} < 混排×0.9={b_x['ret']*0.9:.1%}（混排 {b_x['ret']:.1%}）")
if f3:
    reasons.append(f"换手 {to_main:.1f}x > 混排×1.5={to_mix*1.5:.1f}x 且 Calmar 无改善")
verdict = "**证伪**" if falsified else "**未证伪**"
fal = ("；".join(reasons) if reasons else
       f"Calmar {sm['Calmar']:.2f} vs 混排 {sx['Calmar']:.2f}（Δ{sm['Calmar']-sx['Calmar']:+.2f}）；"
       f"2023–26 {b_m['ret']:.1%} vs 混排 {b_x['ret']:.1%}；换手 {to_main:.1f}x vs {to_mix:.1f}x"
       ) + ("。证伪成立。" if falsified else "。未触发证伪闸。")

# ---------- attribution side notes ----------
# category open weeks, weekly contrib, dedup drops
n_weeks = len(reb)
active_map = meta_main.get("active", {})
drops_map = meta_main.get("drops", {})
open_cnt = {c: 0 for c in CAT_ORDER}
drop_sum = {c: 0 for c in CAT_ORDER}
drop_weeks = {c: 0 for c in CAT_ORDER}
for dd in reb:
    act = active_map.get(dd, {})
    for c in CAT_ORDER:
        if c in act and act[c]:
            open_cnt[c] += 1
    dr = drops_map.get(dd, {})
    for c in CAT_ORDER:
        d = int(dr.get(c, 0) or 0)
        drop_sum[c] += d
        if d > 0:
            drop_weeks[c] += 1

# weekly category contribution via recorded holdings × next-week returns
# Use run_weights record for ETF contrib, then map to category
rec = {}
_= e.run_weights(lambda i, dd: W_main.get(dd, {}), record=rec)
C = pd.DataFrame(rec.get("contrib", {})).T.fillna(0.0).sort_index()
C.index = pd.to_datetime(C.index)
cat_daily = pd.DataFrame(0.0, index=C.index, columns=CAT_ORDER + ["货币511880", "其他"])
code2cat = {c: cat_of(c) for c in C.columns}
for c in C.columns:
    k = code2cat.get(c)
    if c == MF or k == "债券货币" and c == MF:
        cat_daily["货币511880"] += C[c]
    elif k in CAT_ORDER:
        cat_daily[k] += C[c]
    else:
        cat_daily["其他"] += C[c]
# if MF classified as 债券货币, move its contrib note: already in 债券货币; also track MF weight separately
# Recompute cleanly:
cat_daily = pd.DataFrame(0.0, index=C.index, columns=CAT_ORDER + ["其他"])
mf_daily = pd.Series(0.0, index=C.index)
for c in C.columns:
    if c == MF:
        mf_daily += C[c]
        # also attribute MF under 债券货币? Knife wants 各类别周贡献 — MF as cash fill separate
        continue
    k = code2cat.get(c)
    if k in CAT_ORDER:
        cat_daily[k] += C[c]
    else:
        cat_daily["其他"] += C[c]
cat_daily["空位511880"] = mf_daily

cat_tot = cat_daily.sum()
# weekly agg
cat_weekly = cat_daily.copy()
cat_weekly["week"] = cat_weekly.index.to_period("W")
cw = cat_weekly.groupby("week").sum()

# save side CSVs
side = pd.DataFrame({
    "category": CAT_ORDER,
    "n_members": [len(CAT[c]) for c in CAT_ORDER],
    "open_weeks": [open_cnt[c] for c in CAT_ORDER],
    "open_pct": [open_cnt[c] / n_weeks for c in CAT_ORDER],
    "dedup_drop_sum": [drop_sum[c] for c in CAT_ORDER],
    "dedup_drop_per_week": [drop_sum[c] / n_weeks for c in CAT_ORDER],
    "weeks_with_drop": [drop_weeks[c] for c in CAT_ORDER],
    "contrib_sum": [float(cat_tot.get(c, 0)) for c in CAT_ORDER],
})
side.to_csv(f"{OUT}/side_category.csv", index=False)
cw.to_csv(f"{OUT}/side_cat_weekly_contrib.csv")
pd.DataFrame([
    {"dd": dd, "n_active": meta_main.get("n_active", {}).get(dd, 0),
     **{f"pick_{c}": ",".join(active_map.get(dd, {}).get(c, [])) for c in CAT_ORDER},
     **{f"drop_{c}": drops_map.get(dd, {}).get(c, 0) for c in CAT_ORDER}}
    for dd in reb
]).to_csv(f"{OUT}/side_weekly_picks.csv", index=False)

log("side_category:\n" + side.to_string(index=False))

# standard attribution module (may fail on bonds)
try:
    e._bench = {**e.benches(), "池等权(318有价,周调,0.2%RT)": (r_pew, to_pew, ex_pew)}
    at = A.attribute(ID, "MF-CAT-MOM主版", lambda i, dd: W_main.get(dd, {}), OUT, True)
    attr_mod = at["md"]
except Exception as ex:
    log(f"attribution module err: {ex}")
    attr_mod = f"_attribution 模块异常：{ex}_\n"

attr_md = f"""## 归因 · MF-CAT-MOM

### 拆解摘要（模块）
{attr_mod}

### 类别开启周占比（主版，共 {n_weeks} 个信号周）
| 类别 | 成员数 | 开启周 | 开启占比 | 去重剔除合计 | 剔除/周 | 有剔除周数 | 贡献Σ |
|---|---:|---:|---:|---:|---:|---:|---:|
"""
for r in side.itertuples(index=False):
    attr_md += (f"| {r.category} | {int(r.n_members)} | {int(r.open_weeks)} | {r.open_pct:.1%} | "
                f"{int(r.dedup_drop_sum)} | {r.dedup_drop_per_week:.2f} | {int(r.weeks_with_drop)} | "
                f"{r.contrib_sum:+.3f} |\n")
attr_md += f"""
空位 511880 贡献Σ = {float(mf_daily.sum()):+.3f}

### 择时 / 选品 / 去重 / 成本（定性）
- **择时**：无 TV / breadth / HYST；仓位由「有信号类别数」决定（类间等权，常近满仓）；空仓周极少。
- **选品**：相对混排，强制类内名额 → 港/跨境/商品/债 不再被 A 股强势主题挤出；亦限制行业主题吃满 5 席。
- **去重**：ρ≥0.9 complete-linkage 簇内留 AUM 最大；行业主题剔除/周最高（见上表）。
- **成本**：0.2%RT；主版换手 {to_main:.1f}x / 年（单边）vs 混排 {to_mix:.1f}x。

旁注 CSV：`side_category.csv` / `side_cat_weekly_contrib.csv` / `side_weekly_picks.csv`
"""

# ---------- REPORT ----------
main = "MF-CAT-MOM 类内XS+去重·类间等权(主版)"
M = pd.DataFrame([mf.row(k, *v[:3]) for k, v in books.items()])
report = HYPO + f"""
## 1. 准则原文
研究池 6 类互斥（l0+family）：A股宽基 / 行业主题 / 港股 / 跨境 / 商品 / 债券货币。
每周五对**每一类独立**：①60 日日收益 complete-linkage，ρ≥0.9 簇内留 AUM 最大；②XS52 跳1 取 K（2/3/2/1/1/1）组内等权；③类间有信号等权，空位 511880。禁止全池混排选品。无 TV/breadth/HYST。

## 2. 实现要点
- 池：宽基{len(CAT['A股宽基'])} / 行业{len(CAT['行业主题'])} / 港股{len(CAT['港股'])} / 跨境{len(CAT['跨境'])} / 商品{len(CAT['商品'])} / 债{len(CAT['债券货币'])}；债券等不在原周频 W 的代码由日频 P 对齐网格补全。
- 去重：`linkage(1−ρ, complete)` + `fcluster(t=0.1)`；不足 60 日有价剔除。
- 对照：全池混排 XS52取5；全池等权；类内等权再类间等权（无动量）；冠军研究副本。
- 邻档：无去重；每类取1；行业K=5；旁注仅中国权益两类。
- 成本 0.2%RT；{mf.START}→{mf.END}；panel_v2 / mf_common。

## 3. 主表
{mf.metrics_table(M, main)}

### vs 混排（证伪闸）
- Calmar **{sm['Calmar']:.2f}** vs 混排 {sx['Calmar']:.2f}（Δ {sm['Calmar']-sx['Calmar']:+.2f}；闸：<×0.9={sx['Calmar']*0.9:.2f} 或 Δ≤−0.05）
- 2023–26 ret **{b_m['ret']:.1%}** vs 混排 {b_x['ret']:.1%}（闸：<×0.9={b_x['ret']*0.9:.1%}）
- 换手 **{to_main:.1f}x** vs 混排 {to_mix:.1f}x（闸：>×1.5={to_mix*1.5:.1f}x 且 C 无改善）
- 全样本 ret/DD：{sm['ret']:.1%}/{sm['maxDD']:.1%} vs 混排 {sx['ret']:.1%}/{sx['maxDD']:.1%}
- 2020–22：{a_m['ret']:.1%}/{a_m['maxDD']:.1%}/C{a_m['Calmar']:.2f} vs 混排 {a_x['ret']:.1%}/{a_x['maxDD']:.1%}/C{a_x['Calmar']:.2f}

### 类别旁注（主版）
| 类别 | 开启占比 | 去重剔除/周 | 贡献Σ |
|---|---:|---:|---:|
"""
for r in side.itertuples(index=False):
    report += f"| {r.category} | {r.open_pct:.1%} | {r.dedup_drop_per_week:.2f} | {r.contrib_sum:+.3f} |\n"

report += f"""
### 逐年
"""
Y = pd.concat([mf.yearly(books[k][0]).assign(book=k) for k in [
    main, "全池混排 XS52跳1取5", "邻档 无去重(同K)", "类内等权再类间等权(无动量)"]])
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

产物：{OUT}/；不换冠军、不下单。
"""

mf.deliver(ID, books, main, f"{ID}（类内动量+去重·类间等权，0.2%RT）", report, attr_md)
M.to_csv(f"{OUT}/metrics.csv", index=False)
pickle.dump(dict(
    W_main=W_main, meta_main=meta_main, falsified=falsified,
    sm=sm, sx=sx, to_main=to_main, to_mix=to_mix, fal=fal, verdict=verdict,
), open(f"{OUT}/_res.pkl", "wb"))

# patch knife 一句证伪句
knife = Path("/workspace/etf-multifreq/knives/MF-CAT-MOM.md")
if knife.exists():
    txt = knife.read_text()
    if "（测试填）" in txt:
        knife.write_text(txt.replace("（测试填）", fal))

log("DONE " + verdict + " " + fal)
log(M[["book", "ret", "maxDD", "Calmar", "turnover", "avg_expo"]].round(3).to_string())
LOG.close()
