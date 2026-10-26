#!/usr/bin/env python3
"""MF-HOLD-BGRID: full-pool XS52 skip1 top5; exit buffer B ∈ {6,7,8,9}; separate multifreq ledger."""
from __future__ import annotations

import pickle
import sys
from collections import defaultdict
from pathlib import Path

import numpy as np
import pandas as pd

ENGINE = Path(__file__).resolve().parent
sys.path.insert(0, str(ENGINE))
sys.path.insert(0, "/workspace/etf-momentum/engine")

import mf_common as mf
import mom_engine as e

ID = "MF-HOLD-BGRID"
OUT = mf.OUT_ROOT
Path(OUT).mkdir(parents=True, exist_ok=True)
LOG = open(f"{OUT}/_run.log", "w", buffering=1)


def log(msg: str) -> None:
    print(msg, flush=True)
    LOG.write(msg + "\n")


HYPO = """## 0. 假设与证伪（开跑前写死）
- **假设**：记正锚 **B=8**（169.4%/C0.38 为母机 MF-HOLD-B8 同引擎口径）在邻域 {6,7,9} 仍最优；B=10 已证伪不重开。
- **证伪**（任一）：
  1. ∃B∈{6,7,9}：全样本 ret 盖住 B=8 **且** 2023–26 ret 盖住 B=8；
  2. B=8 相对无缓冲：换手 > 无缓冲×0.8 **且** Calmar < 无缓冲×0.9 **且** 2023–26 < 无缓冲×0.9（三重同时，即 B8 记正失效）。
- **红线**：多频不合层；不叠冠军强栈；不改实盘；产物仅 research/cloud_batch 与 etf-multifreq 镜像。
"""

D = mf.data()
P, W0, G, gi, reb = D["P"], D["W"], D["G"], D["gi"], D["reb"]
MF = mf.MF
N = 5
B_GRID = (6, 7, 8, 9)

pool = pd.read_csv("/workspace/etf-correlation/data/research_pool_v2.csv", dtype={"code": str})
pool["code"] = pool.code.str.zfill(6)
pool = pool.drop_duplicates("code").set_index("code")
CAT_ORDER = ["A股宽基", "行业主题", "港股", "跨境", "商品", "债券货币"]


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
CODES = set(ALL)
W = W0.copy()
missing = [c for c in ALL if c not in W.columns]
if missing:
    W = W.join(P[missing].reindex(G), how="left")
    log(f"extended W with {len(missing)} codes")
if MF not in W.columns and MF in P.columns:
    W[MF] = P[MF].reindex(G)


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


def rank_series(i, codes=None):
    codes = CODES if codes is None else set(codes)
    s = mom_ext(i, 52, 1, codes=codes)
    if s.empty:
        return pd.Series(dtype=float), s
    s2 = s.drop(labels=[MF], errors="ignore")
    ordered = list(s2.sort_values(ascending=False).index)
    ranks = pd.Series({c: j + 1 for j, c in enumerate(ordered)}, dtype=float)
    return ranks, s2


def weights_from_held(held, N=N):
    held = [c for c in held if c != MF]
    n = len(held)
    if n == 0:
        return {MF: 1.0} if MF in P.columns else {}
    w = {c: 1.0 / N for c in held}
    if n < N and MF in P.columns:
        w[MF] = (N - n) / N
    if n > N:
        w = {c: 1.0 / n for c in held}
    return w


def build_mix_xs(N=5, codes=None):
    codes = set(codes or ALL)
    raw = {}
    for dd in reb:
        i = gi[dd]
        if i < 52:
            raw[dd] = {}
            continue
        _, s = rank_series(i, codes)
        if s.empty:
            raw[dd] = {}
            continue
        top = list(s.sort_values(ascending=False).index[:N])
        raw[dd] = {c: 1.0 / len(top) for c in top} if top else {}
    return raw


def build_pool_ew(codes=None):
    codes_all = set(codes or ALL)
    raw = {}
    for dd in reb:
        i = gi[dd]
        row = W.iloc[i]
        pl = [c for c in codes_all if c in row.index and pd.notna(row[c]) and c != MF]
        raw[dd] = {c: 1.0 / len(pl) for c in pl} if pl else ({MF: 1.0} if MF in P.columns else {})
    return raw


def build_hold_buf(B=8, N=5, codes=None, record_meta=None):
    codes = set(codes or ALL)
    raw = {}
    held = set()
    for dd in reb:
        i = gi[dd]
        if i < 52:
            raw[dd] = {}
            held = set()
            continue
        ranks, s = rank_series(i, codes)
        if s.empty:
            raw[dd] = {MF: 1.0} if MF in P.columns else {}
            held = set()
            continue
        sold = []
        survivors = set()
        for c in list(held):
            rk = ranks.get(c, np.inf)
            if pd.isna(rk) or rk > B:
                sold.append(c)
            else:
                survivors.add(c)
        slots = max(0, N - len(survivors))
        candidates = [
            c
            for c in s.sort_values(ascending=False).index
            if c not in survivors and ranks.get(c, np.inf) <= N
        ]
        bought = candidates[:slots]
        new_held = survivors | set(bought)
        topN = set(list(s.sort_values(ascending=False).index[:N]))
        buf_kept = [c for c in survivors if c not in topN]
        held = set(new_held)
        raw[dd] = weights_from_held(held, N)
        if record_meta is not None:
            record_meta.setdefault("held", {})[dd] = sorted(held)
            record_meta.setdefault("topN", {})[dd] = sorted(topN)
            record_meta.setdefault("sold", {})[dd] = sold
            record_meta.setdefault("bought", {})[dd] = bought
            record_meta.setdefault("buf_kept", {})[dd] = buf_kept
    return raw


def avg_hold_weeks_from(held_map):
    spell_lengths = []
    active_spell = {}
    for dd in reb:
        cur = set(held_map.get(dd, []))
        for c in list(active_spell.keys()):
            if c not in cur:
                spell_lengths.append(active_spell.pop(c))
        for c in cur:
            active_spell[c] = active_spell.get(c, 0) + 1
    spell_lengths.extend(active_spell.values())
    return float(np.mean(spell_lengths)) if spell_lengths else float("nan")


def buf_contrib(W_book, buf_kept_map):
    rec = {}
    e.run_weights(lambda i, dd: W_book.get(dd, {}), record=rec)
    C = pd.DataFrame(rec.get("contrib", {})).T.fillna(0.0).sort_index()
    C.index = pd.to_datetime(C.index)
    reb_sorted = sorted(reb)
    parts = []
    buf_weeks = 0
    n_sig = sum(1 for dd in reb if gi[dd] >= 52)
    for k, dd in enumerate(reb_sorted):
        kept = buf_kept_map.get(dd, [])
        if not kept:
            continue
        buf_weeks += 1
        nxt = reb_sorted[k + 1] if k + 1 < len(reb_sorted) else C.index[-1]
        seg = C[(C.index > dd) & (C.index <= nxt)]
        for c in kept:
            if c in seg.columns:
                parts.append(float(seg[c].sum()))
    return {
        "sum": float(np.sum(parts)) if parts else 0.0,
        "buf_weeks": buf_weeks,
        "n_sig": n_sig,
        "pct_weeks": buf_weeks / n_sig if n_sig else 0.0,
    }


log("build panel done; running books ...")
W_mix = build_mix_xs(5, ALL)
r_mix, to_mix, ex_mix = mf.run_weekly(W_mix)
log(f"MIX {mf.stats(r_mix)['ret']:.3f} to={to_mix:.2f}")

results = {}
meta_by_b = {}
for B in B_GRID:
    meta = {}
    Wb = build_hold_buf(B=B, N=5, record_meta=meta)
    rb, tob, exb = mf.run_weekly(Wb)
    results[B] = (rb, tob, exb, Wb, meta)
    log(f"B={B} ret={mf.stats(rb)['ret']:.3f} C={mf.stats(rb)['Calmar']:.2f} to={tob:.2f}")

W_pew = build_pool_ew(ALL)
r_pew, to_pew, ex_pew = mf.run_weekly(W_pew)

main_label = "MF-HOLD-BGRID B=8·XS52取5(记正锚)"
books = {
    main_label: results[8][:3],
    "B=6": results[6][:3],
    "B=7": results[7][:3],
    "B=9": results[9][:3],
    "无缓冲全池混排 XS52跳1取5": (r_mix, to_mix, ex_mix),
    "全池等权周调": (r_pew, to_pew, ex_pew),
}

s8 = mf.stats(results[8][0])
sx = mf.stats(r_mix)
b8 = mf.stats(results[8][0][results[8][0].index >= "2023-01-01"])
bx = mf.stats(r_mix[r_mix.index >= "2023-01-01"])
a8 = mf.stats(results[8][0][results[8][0].index <= "2022-12-31"])
ax = mf.stats(r_mix[r_mix.index <= "2022-12-31"])

# Knife falsification vs B=8 anchor
beaters = []
for B in (6, 7, 9):
    sb = mf.stats(results[B][0])
    bb = mf.stats(results[B][0][results[B][0].index >= "2023-01-01"])
    if sb["ret"] > s8["ret"] and bb["ret"] > b8["ret"]:
        beaters.append(f"B={B}（全样本 {sb['ret']:.1%}>{s8['ret']:.1%} 且 2023–26 {bb['ret']:.1%}>{b8['ret']:.1%}）")

f_b8_triple = (
    results[8][1] > to_mix * 0.8 and s8["Calmar"] < sx["Calmar"] * 0.9 and b8["ret"] < bx["ret"] * 0.9
)
falsified = bool(beaters) or f_b8_triple
reasons = []
if beaters:
    reasons.append("邻档同时盖住 B=8：" + "；".join(beaters))
if f_b8_triple:
    reasons.append("B=8 记正三重失效（换手/Calmar/后段同时劣于无缓冲闸）")
verdict = "**证伪**" if falsified else "**未证伪**"
if not reasons:
    fal = (
        f"B=8 锚 ret {s8['ret']:.1%}/C{s8['Calmar']:.2f}/换手{results[8][1]:.1f}x；"
        f"无缓冲 {sx['ret']:.1%}/C{sx['Calmar']:.2f}/换手{to_mix:.1f}x；"
        f"2023–26 B8 {b8['ret']:.1%} vs 无缓冲 {bx['ret']:.1%}；邻档未双段盖住 B=8。"
    )
else:
    fal = "；".join(reasons)

bc8 = buf_contrib(results[8][3], results[8][4].get("buf_kept", {}))
avg_hold = {B: avg_hold_weeks_from(results[B][4].get("held", {})) for B in B_GRID}
mix_held = {dd: [c for c in W_mix.get(dd, {}) if c != MF] for dd in reb}
avg_hold_mix = avg_hold_weeks_from(mix_held)

# B8 reference from prior MF-HOLD-B8 run (same kit)
REF_B8 = {"ret": 1.694192012033878, "Calmar": 0.3829021898468703, "note": "母机 MF-HOLD-B8/REPORT.md panel_v2"}

grid_rows = []
for B in B_GRID:
    sb = mf.stats(results[B][0])
    bb = mf.stats(results[B][0][results[B][0].index >= "2023-01-01"])
    grid_rows.append(
        dict(B=B, ret=sb["ret"], maxDD=sb["maxDD"], Calmar=sb["Calmar"], turnover=results[B][1],
             ret23_26=bb["ret"], avg_hold_weeks=avg_hold[B])
    )
pd.DataFrame(grid_rows).to_csv(f"{OUT}/grid_b6789.csv", index=False)

M = pd.DataFrame([mf.row(k, *v[:3]) for k, v in books.items()])
report = HYPO + f"""
## 1. 准则原文
宇宙：研究池 `research_pool_v2` ∩ 周频动量可交易（与 MF-HOLD-B8/BUF 全池混排同池）。
选品：XS52 跳1 取5；**唯一改动** 退出缓冲 B∈{{6,7,8,9}}；空位 511880；0.2%RT；{mf.START}→{mf.END}。
数据：CLOUD-BATCH `research_cache`（sina_daily+day+week，缺码 Tencent qfq 日线下载至 `research/prices_daily/`）。

## 2. 实现要点
- 池：宽基{len(CAT['A股宽基'])}/行业{len(CAT['行业主题'])}/港股{len(CAT['港股'])}/跨境{len(CAT['跨境'])}/商品{len(CAT['商品'])}/债{len(CAT['债券货币'])}。
- 记正锚 B=8；网格四档同引擎 `build_hold_buf`；对照无缓冲混排、全池等权；**无冠军栈**。
- 母机记正对照（panel_v2）：ret {REF_B8['ret']:.1%} / C {REF_B8['Calmar']:.2f} — 本次云批 B=8 复跑 {s8['ret']:.1%} / C {s8['Calmar']:.2f}（Δret {(s8['ret']-REF_B8['ret'])*100:+.1f}pp）。

## 3. 主表
{mf.metrics_table(M, main_label)}

### B 网格（四档）
| B | ret | maxDD | Calmar | 换手 | 2023–26 | 均持有周 |
|---:|---:|---:|---:|---:|---:|---:|
""" + "\n".join(
    f"| {r['B']} | {r['ret']:.1%} | {r['maxDD']:.1%} | {r['Calmar']:.2f} | {r['turnover']:.1f}x | {r['ret23_26']:.1%} | {r['avg_hold_weeks']:.2f} |"
    for r in grid_rows
) + f"""

### vs 无缓冲（B=8 记正闸）
- B=8 换手 **{results[8][1]:.1f}x** vs 无缓冲 {to_mix:.1f}x（比 {results[8][1]/to_mix:.2f}×）
- Calmar **{s8['Calmar']:.2f}** vs 无缓冲 {sx['Calmar']:.2f}（Δ {s8['Calmar']-sx['Calmar']:+.2f}）
- 2023–26 **{b8['ret']:.1%}** vs 无缓冲 {bx['ret']:.1%}
- 2020–22：B8 {a8['ret']:.1%}/{a8['maxDD']:.1%}/C{a8['Calmar']:.2f} vs 无缓冲 {ax['ret']:.1%}/{ax['maxDD']:.1%}/C{ax['Calmar']:.2f}
- 该卖未卖 Σ（B=8 缓冲段）**{bc8['sum']:+.4f}**（信号周有保留 {bc8['buf_weeks']}/{bc8['n_sig']}）

### vs 母机 MF-HOLD-B8（记正）
| 指标 | 母机 | 本次云批 B=8 |
|---|---:|---:|
| ret | {REF_B8['ret']:.1%} | {s8['ret']:.1%} |
| Calmar | {REF_B8['Calmar']:.2f} | {s8['Calmar']:.2f} |

### 逐年（B 网格 + 无缓冲）
"""
Y = pd.concat(
    [mf.yearly(books[k][0]).assign(book=k) for k in [main_label, "B=6", "B=7", "B=9", "无缓冲全池混排 XS52跳1取5"]]
)
yp = Y.pivot(index="year", columns="book", values="ret")
yd = Y.pivot(index="year", columns="book", values="mdd")
ks = list(yp.columns)
report += "| 年 | " + " | ".join(ks) + " |\n|---|" + "---|" * len(ks) + "\n"
for y in yp.index:
    report += f"| {y} | " + " | ".join(f"{yp.at[y, k]:+.1%}/{yd.at[y, k]:.1%}" for k in ks) + " |\n"

report += f"""
## 4. 结论
{verdict}。{fal}

**同步路径**：母环境请同步至 `/workspace/etf-multifreq/MF-HOLD-BGRID/`（本跑已镜像 metrics/REPORT/nav）。
产物根目录：`{OUT}/`
"""

attr_md = f"""## 归因 · MF-HOLD-BGRID

### 换手 / 持有
| B | 换手 | 均持有周(spell) |
|---:|---:|---:|
""" + "\n".join(f"| {B} | {results[B][1]:.2f}x | {avg_hold[B]:.2f} |" for B in B_GRID) + f"""
| 无缓冲 | {to_mix:.2f}x | {avg_hold_mix:.2f} |

### B=8 缓冲段贡献
- Σw·r（名次 6–8 保留）= **{bc8['sum']:+.4f}**
- 有缓冲保留周占比 {bc8['pct_weeks']:.1%}
"""

mf.deliver(ID, books, main_label, f"{ID}（B∈{{6,7,8,9}} · XS52取5）", report, attr_md)
pickle.dump(
    dict(grid=grid_rows, s8=s8, sx=sx, falsified=falsified, fal=fal, ref_b8=REF_B8),
    open(f"{OUT}/_res.pkl", "wb"),
)
log("DONE")
LOG.close()
