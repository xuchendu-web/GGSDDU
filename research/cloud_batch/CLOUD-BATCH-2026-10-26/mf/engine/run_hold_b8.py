#!/usr/bin/env python3
"""MF-HOLD-B8：全池混排 XS52 跳1取5 + 持仓名次缓冲 B（主版 B=8）；空位 511880。
相对已证伪 MF-HOLD-BUF（B=10）仅改 B：10→8。不覆写 MF-HOLD-BUF/。"""
from __future__ import annotations
import os, sys, pickle, math
from collections import defaultdict
from pathlib import Path
import numpy as np
import pandas as pd

sys.path.insert(0, "/workspace/etf-multifreq/engine")
sys.path.insert(0, "/workspace/etf-momentum/engine")
import mf_common as mf
import mom_engine as e
import attribution as A

ID = "MF-HOLD-B8"
OUT = f"{mf.OUT_ROOT}/{ID}"
Path(OUT).mkdir(parents=True, exist_ok=True)
LOG = open(f"{OUT}/_run.log", "w", buffering=1)

def log(msg):
    print(msg, flush=True)
    LOG.write(msg + "\n")

HYPO = """## 0. 假设与证伪（开跑前写死）
- **假设**：相对已证伪 B=10，收窄缓冲至 B=8，可在保留换手下降的同时减轻「该卖未卖」拖累，使 Calmar ≥ 无缓冲×0.95 且 2023–26 ≥ 无缓冲×0.9。
- **证伪**（任一）：
  1. 换手仍 > 无缓冲 ×0.8；
  2. ΔCalmar ≤ −0.05 或 Calmar < 无缓冲 ×0.9；
  3. 2023–26 收益 < 无缓冲 ×0.9。
- **红线**：不合层、不叠强栈、不换冠、不碰实盘/LIVE/SPIKE/OPT；不覆写 MF-HOLD-BUF/。
"""

# ---------- data / pool（与 HOLD-BUF / CAT-MOM 混排同池）----------
D = mf.data()
P, W0, SIG, G, gi, reb = D["P"], D["W"], D["SIG"], D["G"], D["gi"], D["reb"]
MF = mf.MF  # 511880
N = 5

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
    add = P[missing].reindex(G)
    W = W.join(add, how="left")
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

def avail_codes(i, codes):
    row = W.iloc[i]
    return [c for c in codes if c in row.index and pd.notna(row[c])]

def rank_series(i, codes=None):
    """XS52 descending: rank 1 = strongest. Returns Series code->rank (int)."""
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
        if MF in P.columns:
            return {MF: 1.0}
        return {}
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
            raw[dd] = {}; continue
        ranks, s = rank_series(i, codes)
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
        pl = [c for c in avail_codes(i, codes_all) if c != MF]
        raw[dd] = {c: 1.0 / len(pl) for c in pl} if pl else ({MF: 1.0} if MF in P.columns else {})
    return raw

def build_hold_buf(B=10, N=5, codes=None, record_meta=None):
    """Holding buffer: sell only if rank > B; buy into empty slots from rank≤N not held."""
    codes = set(codes or ALL)
    raw = {}
    held = set()
    for dd in reb:
        i = gi[dd]
        if i < 52:
            raw[dd] = {}; held = set(); continue
        ranks, s = rank_series(i, codes)
        if s.empty:
            raw[dd] = {MF: 1.0} if MF in P.columns else {}
            held = set()
            if record_meta is not None:
                record_meta.setdefault("held", {})[dd] = []
                record_meta.setdefault("topN", {})[dd] = []
                record_meta.setdefault("sold", {})[dd] = []
                record_meta.setdefault("bought", {})[dd] = []
                record_meta.setdefault("buf_kept", {})[dd] = []
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
        candidates = [c for c in s.sort_values(ascending=False).index
                      if c not in survivors and ranks.get(c, np.inf) <= N]
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
            record_meta.setdefault("ranks", {})[dd] = {c: int(ranks[c]) for c in held if c in ranks.index}
    return raw

def build_confirm2(N=5, codes=None, record_meta=None):
    """连续确认邻档：无名次缓冲；新进/换出须该方向信号连续 2 个周五成立才成交。"""
    codes = set(codes or ALL)
    raw = {}
    held = set()
    in_streak = defaultdict(int)
    out_streak = defaultdict(int)
    for dd in reb:
        i = gi[dd]
        if i < 52:
            raw[dd] = {}; held = set(); in_streak.clear(); out_streak.clear()
            continue
        ranks, s = rank_series(i, codes)
        if s.empty:
            raw[dd] = {MF: 1.0} if MF in P.columns else {}
            held = set(); in_streak.clear(); out_streak.clear()
            continue
        topN = set(list(s.sort_values(ascending=False).index[:N]))
        for c in list(in_streak.keys()):
            if c in held or c not in topN:
                in_streak[c] = 0
        for c in list(out_streak.keys()):
            if c not in held or c in topN:
                out_streak[c] = 0
        for c in topN:
            if c not in held:
                in_streak[c] = in_streak.get(c, 0) + 1
            else:
                in_streak[c] = 0
        for c in list(held):
            if c not in topN:
                out_streak[c] = out_streak.get(c, 0) + 1
            else:
                out_streak[c] = 0
        sold = [c for c in list(held) if out_streak.get(c, 0) >= 2]
        for c in sold:
            held.discard(c)
            out_streak[c] = 0
        slots = max(0, N - len(held))
        cand = [c for c in s.sort_values(ascending=False).index
                if c not in held and in_streak.get(c, 0) >= 2]
        bought = cand[:slots]
        for c in bought:
            held.add(c)
            in_streak[c] = 0
        raw[dd] = weights_from_held(held, N)
        if record_meta is not None:
            record_meta.setdefault("held", {})[dd] = sorted(held)
            record_meta.setdefault("topN", {})[dd] = sorted(topN)
            record_meta.setdefault("sold", {})[dd] = sold
            record_meta.setdefault("bought", {})[dd] = bought
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


def buf_contrib(W_book, buf_kept_map, label=""):
    """该卖未卖：缓冲保留名次 N+1..B 的日度贡献加总。"""
    rec = {}
    _ = e.run_weights(lambda i, dd: W_book.get(dd, {}), record=rec)
    C = pd.DataFrame(rec.get("contrib", {})).T.fillna(0.0).sort_index()
    C.index = pd.to_datetime(C.index)
    reb_sorted = sorted(reb)
    parts = []
    buf_weeks = 0
    buf_kept_count = 0
    for k, dd in enumerate(reb_sorted):
        kept = buf_kept_map.get(dd, [])
        if not kept:
            continue
        buf_weeks += 1
        buf_kept_count += len(kept)
        nxt = reb_sorted[k + 1] if k + 1 < len(reb_sorted) else C.index[-1]
        seg = C[(C.index > dd) & (C.index <= nxt)]
        if seg.empty:
            continue
        for c in kept:
            if c in seg.columns:
                parts.append(float(seg[c].sum()))
    n_sig = sum(1 for dd in reb if gi[dd] >= 52)
    return {
        "sum": float(np.sum(parts)) if parts else 0.0,
        "buf_weeks": buf_weeks,
        "n_sig": n_sig,
        "pct_weeks": buf_weeks / n_sig if n_sig else 0.0,
        "kept_count": buf_kept_count,
        "label": label,
    }


# ---------- build books ----------
log("building 无缓冲混排 XS52取5 ...")
W_mix = build_mix_xs(5, ALL)
r_mix, to_mix, ex_mix = mf.run_weekly(W_mix)
log(f"MIX { {k: round(float(v),4) for k,v in mf.stats(r_mix).items()} } to={to_mix:.2f}")

log("building 主版 B=8 ...")
meta_main = {}
W_main = build_hold_buf(B=8, N=5, record_meta=meta_main)
r_main, to_main, ex_main = mf.run_weekly(W_main)
log(f"B8 { {k: round(float(v),4) for k,v in mf.stats(r_main).items()} } to={to_main:.2f} ex={ex_main:.2f}")

log("building 旁注 B=10（对齐 HOLD-BUF 主版）...")
meta_b10 = {}
W_b10 = build_hold_buf(B=10, N=5, record_meta=meta_b10)
r_b10, to_b10, ex_b10 = mf.run_weekly(W_b10)
log(f"B10 { {k: round(float(v),4) for k,v in mf.stats(r_b10).items()} } to={to_b10:.2f}")

log("building 邻档 B=6 ...")
meta_b6 = {}
W_b6 = build_hold_buf(B=6, N=5, record_meta=meta_b6)
r_b6, to_b6, ex_b6 = mf.run_weekly(W_b6)
log(f"B6 { {k: round(float(v),4) for k,v in mf.stats(r_b6).items()} } to={to_b6:.2f}")

log("building 邻档 连续确认×2 ...")
meta_c2 = {}
W_c2 = build_confirm2(N=5, record_meta=meta_c2)
r_c2, to_c2, ex_c2 = mf.run_weekly(W_c2)
log(f"C2 { {k: round(float(v),4) for k,v in mf.stats(r_c2).items()} } to={to_c2:.2f}")

log("building 全池等权 ...")
W_pew = build_pool_ew(ALL)
r_pew, to_pew, ex_pew = mf.run_weekly(W_pew)
log(f"POOL_EW { {k: round(float(v),4) for k,v in mf.stats(r_pew).items()} } to={to_pew:.2f}")

ch = mf.champ()

books = {
    "MF-HOLD-B8 B=8·XS52取5(主版)": (r_main, to_main, ex_main),
    "旁注 B=10(对齐HOLD-BUF)": (r_b10, to_b10, ex_b10),
    "邻档 B=6": (r_b6, to_b6, ex_b6),
    "邻档 连续确认×2": (r_c2, to_c2, ex_c2),
    "无缓冲全池混排 XS52跳1取5": (r_mix, to_mix, ex_mix),
    "全池等权周调": (r_pew, to_pew, ex_pew),
    "冠军同引擎(研究副本)": ch,
}

# ---------- falsification (vs 无缓冲) ----------
sm, sx = mf.stats(r_main), mf.stats(r_mix)
s10 = mf.stats(r_b10)
s6 = mf.stats(r_b6)
sc2 = mf.stats(r_c2)
a_m = mf.stats(r_main[r_main.index <= "2022-12-31"])
a_x = mf.stats(r_mix[r_mix.index <= "2022-12-31"])
a_10 = mf.stats(r_b10[r_b10.index <= "2022-12-31"])
b_m = mf.stats(r_main[r_main.index >= "2023-01-01"])
b_x = mf.stats(r_mix[r_mix.index >= "2023-01-01"])
b_10 = mf.stats(r_b10[r_b10.index >= "2023-01-01"])

f1 = to_main > to_mix * 0.8
f2 = ((sm["Calmar"] - sx["Calmar"]) <= -0.05) or (sm["Calmar"] < sx["Calmar"] * 0.9)
f3 = b_m["ret"] < b_x["ret"] * 0.9
falsified = f1 or f2 or f3
reasons = []
if f1:
    reasons.append(f"换手 {to_main:.1f}x > 无缓冲×0.8={to_mix*0.8:.1f}x（无缓冲 {to_mix:.1f}x）")
if f2:
    reasons.append(f"Calmar {sm['Calmar']:.2f} vs 无缓冲 {sx['Calmar']:.2f}（Δ{sm['Calmar']-sx['Calmar']:+.2f}；闸 Δ≤−0.05 或 <×0.9）")
if f3:
    reasons.append(f"2023–26 ret {b_m['ret']:.1%} < 无缓冲×0.9={b_x['ret']*0.9:.1%}（无缓冲 {b_x['ret']:.1%}）")
verdict = "**证伪**" if falsified else "**未证伪**"
mdd_delta = sm["maxDD"] - sx["maxDD"]
fal = ("；".join(reasons) if reasons else
       f"换手 {to_main:.1f}x vs 无缓冲 {to_mix:.1f}x（比 {to_main/to_mix:.2f}×，闸 >×0.8）；"
       f"Calmar {sm['Calmar']:.2f} vs {sx['Calmar']:.2f}（Δ{sm['Calmar']-sx['Calmar']:+.2f}）；"
       f"2023–26 {b_m['ret']:.1%} vs {b_x['ret']:.1%}"
       ) + ("。证伪成立。" if falsified else "。未触发证伪闸。")

# ---------- attribution ----------
held_map = meta_main.get("held", {})
topN_map = meta_main.get("topN", {})
buf_kept_map = meta_main.get("buf_kept", {})

avg_hold_weeks = avg_hold_weeks_from(held_map)
avg_hold_b10 = avg_hold_weeks_from(meta_b10.get("held", {}))
avg_hold_b6 = avg_hold_weeks_from(meta_b6.get("held", {}))

mix_held = {}
for dd in reb:
    mix_held[dd] = [c for c in W_mix.get(dd, {}) if c != MF and W_mix[dd][c] > 0]
avg_hold_mix = avg_hold_weeks_from(mix_held)

log("computing buf contrib B=8 / B=10 ...")
bc8 = buf_contrib(W_main, buf_kept_map, "B8")
bc10 = buf_contrib(W_b10, meta_b10.get("buf_kept", {}), "B10")
# B=6 buffer band is ranks 6 only (N+1..B) — still report
bc6 = buf_contrib(W_b6, meta_b6.get("buf_kept", {}), "B6")

ann_cost_main = to_main * 0.002
ann_cost_mix = to_mix * 0.002
ann_cost_b10 = to_b10 * 0.002

log(f"avg_hold_weeks B8={avg_hold_weeks:.2f} B10={avg_hold_b10:.2f} mix={avg_hold_mix:.2f}")
log(f"buf_contrib B8={bc8['sum']:+.4f} B10={bc10['sum']:+.4f} (narrowed={bc8['sum']-bc10['sum']:+.4f})")

try:
    e._bench = {**e.benches(), "池等权(318有价,周调,0.2%RT)": (r_pew, to_pew, ex_pew)}
    at = A.attribute(ID, "MF-HOLD-B8主版", lambda i, dd: W_main.get(dd, {}), OUT, True)
    attr_mod = at["md"]
except Exception as ex:
    log(f"attribution module err: {ex}")
    attr_mod = f"_attribution 模块异常：{ex}_\n"

side_rows = []
for dd in reb:
    if gi[dd] < 52:
        continue
    side_rows.append({
        "dd": dd,
        "held": ",".join(held_map.get(dd, [])),
        "topN": ",".join(topN_map.get(dd, [])),
        "buf_kept": ",".join(buf_kept_map.get(dd, [])),
        "n_held": len(held_map.get(dd, [])),
        "n_buf_kept": len(buf_kept_map.get(dd, [])),
        "sold": ",".join(meta_main.get("sold", {}).get(dd, [])),
        "bought": ",".join(meta_main.get("bought", {}).get(dd, [])),
        "ranks": ",".join(f"{c}:{meta_main.get('ranks',{}).get(dd,{}).get(c,'')}"
                          for c in held_map.get(dd, [])),
    })
pd.DataFrame(side_rows).to_csv(f"{OUT}/side_weekly_holdings.csv", index=False)

# attr side compare csv
pd.DataFrame([
    {"B": 8, "turnover": to_main, "ann_cost_rt": ann_cost_main,
     "avg_hold_weeks": avg_hold_weeks, "buf_contrib_sum": bc8["sum"],
     "buf_weeks": bc8["buf_weeks"], "buf_kept_count": bc8["kept_count"],
     "ret": sm["ret"], "maxDD": sm["maxDD"], "Calmar": sm["Calmar"],
     "ret_2023_26": b_m["ret"]},
    {"B": 10, "turnover": to_b10, "ann_cost_rt": ann_cost_b10,
     "avg_hold_weeks": avg_hold_b10, "buf_contrib_sum": bc10["sum"],
     "buf_weeks": bc10["buf_weeks"], "buf_kept_count": bc10["kept_count"],
     "ret": s10["ret"], "maxDD": s10["maxDD"], "Calmar": s10["Calmar"],
     "ret_2023_26": b_10["ret"]},
    {"B": 6, "turnover": to_b6, "ann_cost_rt": to_b6 * 0.002,
     "avg_hold_weeks": avg_hold_b6, "buf_contrib_sum": bc6["sum"],
     "buf_weeks": bc6["buf_weeks"], "buf_kept_count": bc6["kept_count"],
     "ret": s6["ret"], "maxDD": s6["maxDD"], "Calmar": s6["Calmar"],
     "ret_2023_26": mf.stats(r_b6[r_b6.index >= "2023-01-01"])["ret"]},
    {"B": 0, "turnover": to_mix, "ann_cost_rt": ann_cost_mix,
     "avg_hold_weeks": avg_hold_mix, "buf_contrib_sum": 0.0,
     "buf_weeks": 0, "buf_kept_count": 0,
     "ret": sx["ret"], "maxDD": sx["maxDD"], "Calmar": sx["Calmar"],
     "ret_2023_26": b_x["ret"]},
]).to_csv(f"{OUT}/attr_buffer_compare.csv", index=False)

drag_narrowed = bc8["sum"] - bc10["sum"]  # less negative = narrowed drag (positive delta good if both negative)
attr_md = f"""## 归因 · MF-HOLD-B8

### 拆解摘要（模块）
{attr_mod}

### 换手 / 成本
| 项 | 主版 B=8 | 旁注 B=10 | 无缓冲混排 | B8/无缓冲 |
|---|---:|---:|---:|---:|
| 换手(单边/年) | {to_main:.2f}x | {to_b10:.2f}x | {to_mix:.2f}x | {to_main/to_mix:.2f}× |
| 估年化成本(×0.2%RT) | {ann_cost_main:.2%} | {ann_cost_b10:.2%} | {ann_cost_mix:.2%} | 节省 {(ann_cost_mix-ann_cost_main):.2%} |
| 平均持有周数(spell) | {avg_hold_weeks:.2f} | {avg_hold_b10:.2f} | {avg_hold_mix:.2f} | {avg_hold_weeks/avg_hold_mix if avg_hold_mix else float('nan'):.2f}× |

证伪闸换手：主版 {'>' if f1 else '≤'} 无缓冲×0.8 = {to_mix*0.8:.2f}x → {'触发' if f1 else '未触发'}。

### 因缓冲「本该卖未卖」（名次 6–B 保留贡献 Σ）
- 定义：某信号周持仓中 **不在当周 XS52 前 {N}**、但因 rank≤B 被保留的代码。
- **B=8**：有缓冲保留信号周 {bc8['buf_weeks']}/{bc8['n_sig']}（{bc8['pct_weeks']:.1%}）；累计代码·周 ≈ {bc8['kept_count']}；Σw·r = **{bc8['sum']:+.4f}**
- **B=10**（同引擎重跑）：周 {bc10['buf_weeks']}/{bc10['n_sig']}（{bc10['pct_weeks']:.1%}）；代码·周 ≈ {bc10['kept_count']}；Σw·r = **{bc10['sum']:+.4f}**
- **相对 B=10 拖累是否收窄**：ΔΣ = {drag_narrowed:+.4f}（正=B8 缓冲段贡献高于 B10，即拖累收窄或盈利更多；负=更差）
- **B=6**：Σw·r = {bc6['sum']:+.4f}（周 {bc6['buf_weeks']}/{bc6['n_sig']}）
- 旁注 CSV：`side_weekly_holdings.csv`、`attr_buffer_compare.csv`

### 邻档速览
- B=6 换手 {to_b6:.1f}x / C {s6['Calmar']:.2f} / ret {s6['ret']:.1%} / DD {s6['maxDD']:.1%}
- B=10 换手 {to_b10:.1f}x / C {s10['Calmar']:.2f} / ret {s10['ret']:.1%} / DD {s10['maxDD']:.1%}
- 连续确认×2 换手 {to_c2:.1f}x / C {sc2['Calmar']:.2f} / ret {sc2['ret']:.1%} / DD {sc2['maxDD']:.1%}
"""

# ---------- REPORT ----------
main = "MF-HOLD-B8 B=8·XS52取5(主版)"
M = pd.DataFrame([mf.row(k, *v[:3]) for k, v in books.items()])

success_hint = (
    (to_main <= to_mix * 0.8)
    and (sm["Calmar"] >= sx["Calmar"] * 0.95)
    and (sm["maxDD"] >= sx["maxDD"] - 0.03)
    and (b_m["ret"] >= b_x["ret"] * 0.9)
)

# HOLD-BUF prior reference (documented; this run's B10 is authoritative)
HOLD_BUF_PRIOR = "既有 HOLD-BUF 主表旁注：91.4%/−46.4%/C0.22、换手4.3x、2023–26 6.4%——以本次 B=10 重跑为准"

report = HYPO + f"""
## 1. 准则原文
宇宙：研究池 `research_pool_v2` ∩ 周频动量可交易（与 MF-HOLD-BUF / 全池混排同池）。
选品键不变：XS52 跳1。唯一改 — 持仓缓冲主版 **B=8**、N=5 等权：已持仓仅 rank>B 才卖；6–8 保留；空位从未持有且 rank≤N 补入；空余 511880。相对已证伪 HOLD-BUF 只改 B：10→8。

## 2. 实现要点
- 池同混排：宽基{len(CAT['A股宽基'])}/行业{len(CAT['行业主题'])}/港股{len(CAT['港股'])}/跨境{len(CAT['跨境'])}/商品{len(CAT['商品'])}/债{len(CAT['债券货币'])}；W 网格补债券。
- 复用 `build_hold_buf(B=...)`；主版 B=8；旁注必含 B=10（同引擎重跑）；邻档 B=6 + 连续确认×2。
- 状态机跨周 `held`：先卖后买；槽位权重 1/N，未满槽补 511880；排名排除纯现金 511880。
- 对照：无缓冲混排；全池等权；冠军研究副本只读。
- 成本 0.2%RT；{mf.START}→{mf.END}；panel_v2 / mf_common。产物只写 `{OUT}/`（不覆写 MF-HOLD-BUF/）。
- {HOLD_BUF_PRIOR}：本次 B10 = {s10['ret']:.1%}/{s10['maxDD']:.1%}/C{s10['Calmar']:.2f}、换手{to_b10:.1f}x、2023–26 {b_10['ret']:.1%}。

## 3. 主表
{mf.metrics_table(M, main)}

### vs 无缓冲（证伪闸）
- 换手 **{to_main:.1f}x** vs 无缓冲 {to_mix:.1f}x（比 **{to_main/to_mix:.2f}×**；闸：>×0.8={to_mix*0.8:.1f}x）→ {'触发' if f1 else '未触发'}
- Calmar **{sm['Calmar']:.2f}** vs 无缓冲 {sx['Calmar']:.2f}（Δ {sm['Calmar']-sx['Calmar']:+.2f}；闸：Δ≤−0.05 或 <×0.9={sx['Calmar']*0.9:.2f}）→ {'触发' if f2 else '未触发'}
- 2023–26 ret **{b_m['ret']:.1%}** vs 无缓冲 {b_x['ret']:.1%}（闸：<×0.9={b_x['ret']*0.9:.1%}）→ {'触发' if f3 else '未触发'}
- 全样本 ret/DD：{sm['ret']:.1%}/{sm['maxDD']:.1%} vs 无缓冲 {sx['ret']:.1%}/{sx['maxDD']:.1%}（ΔMDD {mdd_delta:+.1%}）
- 2020–22：{a_m['ret']:.1%}/{a_m['maxDD']:.1%}/C{a_m['Calmar']:.2f} vs 无缓冲 {a_x['ret']:.1%}/{a_x['maxDD']:.1%}/C{a_x['Calmar']:.2f}
- 平均持有周：主版 {avg_hold_weeks:.2f} vs 无缓冲 {avg_hold_mix:.2f}
- 成功倾向四条件（换手≤×0.8 ∧ C≥×0.95 ∧ MDD不深>3pp ∧ 后段≥×0.9）：{'是' if success_hint else '否'}

### vs B=10（同引擎重跑）
- B8 {sm['ret']:.1%}/{sm['maxDD']:.1%}/C{sm['Calmar']:.2f}/换手{to_main:.1f}x / 2023–26 {b_m['ret']:.1%}
- B10 {s10['ret']:.1%}/{s10['maxDD']:.1%}/C{s10['Calmar']:.2f}/换手{to_b10:.1f}x / 2023–26 {b_10['ret']:.1%}
- ΔC(B8−B10) {sm['Calmar']-s10['Calmar']:+.2f}；该卖未卖 Σ B8 {bc8['sum']:+.4f} vs B10 {bc10['sum']:+.4f}（Δ {drag_narrowed:+.4f}）
- 均持有周 B8 {avg_hold_weeks:.2f} vs B10 {avg_hold_b10:.2f}

### 邻档
- B=6：{s6['ret']:.1%}/{s6['maxDD']:.1%}/C{s6['Calmar']:.2f}/换手{to_b6:.1f}x
- 连续确认×2：{sc2['ret']:.1%}/{sc2['maxDD']:.1%}/C{sc2['Calmar']:.2f}/换手{to_c2:.1f}x

### 逐年
"""
Y = pd.concat([mf.yearly(books[k][0]).assign(book=k) for k in [
    main, "无缓冲全池混排 XS52跳1取5", "旁注 B=10(对齐HOLD-BUF)", "邻档 B=6", "邻档 连续确认×2"]])
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

产物：{OUT}/；不换冠军、不下单；未覆写 MF-HOLD-BUF/。
"""

mf.deliver(ID, books, main, f"{ID}（持仓缓冲 B=8 · XS52取5，0.2%RT）", report, attr_md)
M.to_csv(f"{OUT}/metrics.csv", index=False)
Y.to_csv(f"{OUT}/yearly.csv", index=False)
pickle.dump(dict(
    W_main=W_main, meta_main=meta_main, falsified=falsified,
    sm=sm, sx=sx, s10=s10, to_main=to_main, to_mix=to_mix, to_b10=to_b10,
    fal=fal, verdict=verdict,
    avg_hold_weeks=avg_hold_weeks, avg_hold_mix=avg_hold_mix, avg_hold_b10=avg_hold_b10,
    buf_contrib_b8=bc8, buf_contrib_b10=bc10, buf_contrib_b6=bc6,
    f1=f1, f2=f2, f3=f3,
    a_m=a_m, b_m=b_m, a_x=a_x, b_x=b_x, b_10=b_10,
), open(f"{OUT}/_res.pkl", "wb"))

# fill knife falsification sentence (both copies)
for knife_path in [
    Path("/workspace/etf-multifreq/knives/MF-HOLD-B8.md"),
    Path("/workspace/strategy-weekly/knives/MF-HOLD-B8.md"),
]:
    if knife_path.exists():
        txt = knife_path.read_text()
        if "（测试填）" in txt:
            knife_path.write_text(txt.replace("（测试填）", fal))
            log(f"filled knife: {knife_path}")

# Obsidian note
obs = Path("/workspace/obsidian-notes/ETF多频专题/MF-HOLD-B8.md")
obs.parent.mkdir(parents=True, exist_ok=True)
obs.write_text(
    f"""# MF-HOLD-B8

产物：`/workspace/etf-multifreq/MF-HOLD-B8/`

主版 B=8：{sm['ret']:.1%}/{sm['maxDD']:.1%}/C{sm['Calmar']:.2f}；换手 {to_main:.1f}x；2023–26 {b_m['ret']:.1%}；该卖未卖 Σ {bc8['sum']:+.4f}；均持有周 {avg_hold_weeks:.2f}。

vs 无缓冲 {sx['ret']:.1%}/{sx['maxDD']:.1%}/C{sx['Calmar']:.2f}/换手{to_mix:.1f}x/2023–26 {b_x['ret']:.1%}。
vs B=10（本次重跑）{s10['ret']:.1%}/{s10['maxDD']:.1%}/C{s10['Calmar']:.2f}/换手{to_b10:.1f}x/2023–26 {b_10['ret']:.1%}；Σ {bc10['sum']:+.4f}。

{verdict}。{fal}

#ETF多频专题
"""
)
log(f"wrote Obsidian {obs}")

log("DONE " + verdict + " " + fal)
log(M[["book", "ret", "maxDD", "Calmar", "turnover", "avg_expo"]].round(3).to_string())
LOG.close()
