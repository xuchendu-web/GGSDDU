#!/usr/bin/env python3
"""MF-HOLD-BUF：全池混排 XS52 跳1取5 + 持仓名次缓冲 B（主版 B=10）；空位 511880。"""
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

ID = "MF-HOLD-BUF"
OUT = f"{mf.OUT_ROOT}/{ID}"
Path(OUT).mkdir(parents=True, exist_ok=True)
LOG = open(f"{OUT}/_run.log", "w", buffering=1)

def log(msg):
    print(msg, flush=True)
    LOG.write(msg + "\n")

HYPO = """## 0. 假设与证伪（开跑前写死）
- **假设**：在全池混排 XS52 跳1取5 上只加退出缓冲带 B=10（进场仍须进前 5），可把换手压到无缓冲 ×0.8 以下，同时保住 Calmar（≥×0.95）且 2023–26 不踏空。
- **证伪**（任一）：
  1. 换手仍 > 无缓冲 ×0.8；
  2. ΔCalmar ≤ −0.05 或 Calmar < 无缓冲 ×0.9；
  3. 2023–26 收益 < 无缓冲 ×0.9。
- **红线**：不合层、不叠 B50+HYST+511260、不换冠、不碰实盘/LIVE/SPIKE/OPT。
"""

# ---------- data / pool（与 CAT-MOM 混排同池）----------
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
    # exclude pure cash MF from risk ranking if present — still allow other bonds
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
    # if somehow n > N (shouldn't), renormalize equal among held
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
        # sell: rank > B (or missing rank)
        sold = []
        survivors = set()
        for c in list(held):
            rk = ranks.get(c, np.inf)
            if pd.isna(rk) or rk > B:
                sold.append(c)
            else:
                survivors.add(c)
        # buy: empty slots from never-held (not in survivors) with rank ≤ N, by mom
        slots = max(0, N - len(survivors))
        candidates = [c for c in s.sort_values(ascending=False).index
                      if c not in survivors and ranks.get(c, np.inf) <= N]
        bought = candidates[:slots]
        new_held = survivors | set(bought)
        # buffer-kept: survivors not in top N
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
    """连续确认邻档：无名次缓冲；新进/换出须该方向信号连续 2 个周五成立才成交。
    进场信号：rank≤N；出场信号：rank>N（或不在有价）。"""
    codes = set(codes or ALL)
    raw = {}
    held = set()
    # streak of "want in" / "want out" consecutive weeks
    in_streak = defaultdict(int)   # code -> consecutive weeks with rank≤N while not held
    out_streak = defaultdict(int)  # code -> consecutive weeks with rank>N while held
    prev_top = set()
    for dd in reb:
        i = gi[dd]
        if i < 52:
            raw[dd] = {}; held = set(); in_streak.clear(); out_streak.clear(); prev_top = set()
            continue
        ranks, s = rank_series(i, codes)
        if s.empty:
            raw[dd] = {MF: 1.0} if MF in P.columns else {}
            held = set(); in_streak.clear(); out_streak.clear(); prev_top = set()
            continue
        topN = set(list(s.sort_values(ascending=False).index[:N]))
        # update streaks
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
        # execute exits: held & out_streak >= 2
        sold = [c for c in list(held) if out_streak.get(c, 0) >= 2]
        for c in sold:
            held.discard(c)
            out_streak[c] = 0
        # execute entries: not held & in_streak >= 2, fill to N by mom
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
        prev_top = topN
    return raw

def build_cat_mom_with_buf(B=10, N_cap=None):
    """旁注：CAT-MOM 主版理想持仓 + 同名次缓冲执行（只改执行）。
    理想集 = 各类内 XS+去重取 K 后类间等权之持仓集合；卖出仅当不在理想集且全局 rank>B；
    买入从理想集按 XS52 补入。"""
    # lightweight inline CAT-MOM picks (reuse logic simplified — import from pickle if exists)
    pkl = Path("/workspace/etf-multifreq/MF-CAT-MOM/_res.pkl")
    if pkl.exists():
        res = pickle.load(open(pkl, "rb"))
        W_cat = res.get("W_main", {})
        log("loaded CAT-MOM W_main from _res.pkl for 旁注")
    else:
        log("CAT-MOM _res.pkl missing — skip 旁注")
        return None, None

    raw = {}
    held = set()
    meta = {}
    for dd in reb:
        i = gi[dd]
        ideal_w = W_cat.get(dd, {})
        ideal = {c for c, w in ideal_w.items() if w > 0 and c != MF}
        if i < 52 or not ideal:
            # fall through: follow ideal / cash
            held = set(ideal)
            raw[dd] = dict(ideal_w) if ideal_w else ({MF: 1.0} if MF in P.columns else {})
            continue
        ranks, s = rank_series(i, CODES)
        survivors = set()
        sold = []
        for c in list(held):
            rk = ranks.get(c, np.inf) if not ranks.empty else np.inf
            if c in ideal or (not pd.isna(rk) and rk <= B):
                survivors.add(c)
            else:
                sold.append(c)
        # capacity = size of ideal (CAT-MOM active count)
        cap = len(ideal) if N_cap is None else N_cap
        slots = max(0, cap - len(survivors))
        # buy from ideal not held, by XS52
        if not s.empty:
            cand = [c for c in s.sort_values(ascending=False).index if c in ideal and c not in survivors]
        else:
            cand = [c for c in ideal if c not in survivors]
        bought = cand[:slots]
        held = survivors | set(bought)
        # rebuild weights: preserve CAT-MOM inter-cat structure approximately —
        # equal among held risk names, MF fills rest to match original MF weight intent
        if not held:
            raw[dd] = {MF: 1.0} if MF in P.columns else {}
        else:
            # match CAT exposure: if ideal had n names equal within cats summing to 1,
            # use equal among held (sum=1), no forced MF unless held empty
            raw[dd] = {c: 1.0 / len(held) for c in held}
        meta.setdefault("held", {})[dd] = sorted(held)
        meta.setdefault("ideal", {})[dd] = sorted(ideal)
        meta.setdefault("sold", {})[dd] = sold
        meta.setdefault("bought", {})[dd] = bought
    return raw, meta


# ---------- build books ----------
log("building 无缓冲混排 XS52取5 ...")
W_mix = build_mix_xs(5, ALL)
r_mix, to_mix, ex_mix = mf.run_weekly(W_mix)
log(f"MIX { {k: round(float(v),4) for k,v in mf.stats(r_mix).items()} } to={to_mix:.2f}")

log("building 主版 B=10 ...")
meta_main = {}
W_main = build_hold_buf(B=10, N=5, record_meta=meta_main)
r_main, to_main, ex_main = mf.run_weekly(W_main)
log(f"B10 { {k: round(float(v),4) for k,v in mf.stats(r_main).items()} } to={to_main:.2f} ex={ex_main:.2f}")

log("building 邻档 B=8 ...")
W_b8 = build_hold_buf(B=8, N=5)
r_b8, to_b8, ex_b8 = mf.run_weekly(W_b8)
log(f"B8 { {k: round(float(v),4) for k,v in mf.stats(r_b8).items()} } to={to_b8:.2f}")

log("building 邻档 B=15 ...")
W_b15 = build_hold_buf(B=15, N=5)
r_b15, to_b15, ex_b15 = mf.run_weekly(W_b15)
log(f"B15 { {k: round(float(v),4) for k,v in mf.stats(r_b15).items()} } to={to_b15:.2f}")

log("building 邻档 连续确认×2 ...")
meta_c2 = {}
W_c2 = build_confirm2(N=5, record_meta=meta_c2)
r_c2, to_c2, ex_c2 = mf.run_weekly(W_c2)
log(f"C2 { {k: round(float(v),4) for k,v in mf.stats(r_c2).items()} } to={to_c2:.2f}")

log("building 全池等权 ...")
W_pew = build_pool_ew(ALL)
r_pew, to_pew, ex_pew = mf.run_weekly(W_pew)
log(f"POOL_EW { {k: round(float(v),4) for k,v in mf.stats(r_pew).items()} } to={to_pew:.2f}")

log("building 旁注 CAT-MOM+缓冲 ...")
W_catbuf, meta_catbuf = build_cat_mom_with_buf(B=10)
if W_catbuf is not None:
    r_catbuf, to_catbuf, ex_catbuf = mf.run_weekly(W_catbuf)
    log(f"CATBUF { {k: round(float(v),4) for k,v in mf.stats(r_catbuf).items()} } to={to_catbuf:.2f}")
else:
    r_catbuf = to_catbuf = ex_catbuf = None

ch = mf.champ()

books = {
    "MF-HOLD-BUF B=10·XS52取5(主版)": (r_main, to_main, ex_main),
    "邻档 B=8": (r_b8, to_b8, ex_b8),
    "邻档 B=15": (r_b15, to_b15, ex_b15),
    "邻档 连续确认×2": (r_c2, to_c2, ex_c2),
    "无缓冲全池混排 XS52跳1取5": (r_mix, to_mix, ex_mix),
    "全池等权周调": (r_pew, to_pew, ex_pew),
    "冠军同引擎(研究副本)": ch,
}
if r_catbuf is not None:
    books["旁注 CAT-MOM持仓+B10缓冲"] = (r_catbuf, to_catbuf, ex_catbuf)

# ---------- falsification ----------
sm, sx = mf.stats(r_main), mf.stats(r_mix)
a_m = mf.stats(r_main[r_main.index <= "2022-12-31"])
a_x = mf.stats(r_mix[r_mix.index <= "2022-12-31"])
b_m = mf.stats(r_main[r_main.index >= "2023-01-01"])
b_x = mf.stats(r_mix[r_mix.index >= "2023-01-01"])

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
mdd_delta = sm["maxDD"] - sx["maxDD"]  # less negative = shallower = positive delta good
fal = ("；".join(reasons) if reasons else
       f"换手 {to_main:.1f}x vs 无缓冲 {to_mix:.1f}x（比 {to_main/to_mix:.2f}×，闸 >×0.8）；"
       f"Calmar {sm['Calmar']:.2f} vs {sx['Calmar']:.2f}（Δ{sm['Calmar']-sx['Calmar']:+.2f}）；"
       f"2023–26 {b_m['ret']:.1%} vs {b_x['ret']:.1%}"
       ) + ("。证伪成立。" if falsified else "。未触发证伪闸。")

# ---------- attribution: holding weeks + buffer-kept contrib ----------
held_map = meta_main.get("held", {})
topN_map = meta_main.get("topN", {})
buf_kept_map = meta_main.get("buf_kept", {})

# average holding weeks: spell lengths
spell_lengths = []
active_spell = {}  # code -> weeks so far
prev_held = set()
for dd in reb:
    cur = set(held_map.get(dd, []))
    for c in list(active_spell.keys()):
        if c not in cur:
            spell_lengths.append(active_spell.pop(c))
    for c in cur:
        active_spell[c] = active_spell.get(c, 0) + 1
    prev_held = cur
spell_lengths.extend(active_spell.values())
avg_hold_weeks = float(np.mean(spell_lengths)) if spell_lengths else float("nan")
# also for mix (no buffer)
mix_held = {}
for dd in reb:
    mix_held[dd] = [c for c in W_mix.get(dd, {}) if c != MF and W_mix[dd][c] > 0]
spell_m = []; act_m = {}
for dd in reb:
    cur = set(mix_held.get(dd, []))
    for c in list(act_m.keys()):
        if c not in cur:
            spell_m.append(act_m.pop(c))
    for c in cur:
        act_m[c] = act_m.get(c, 0) + 1
spell_m.extend(act_m.values())
avg_hold_mix = float(np.mean(spell_m)) if spell_m else float("nan")

# buffer-kept weekly contribution: codes in held but not in topN, weight * next-period return
rec_main = {}
_ = e.run_weights(lambda i, dd: W_main.get(dd, {}), record=rec_main)
C = pd.DataFrame(rec_main.get("contrib", {})).T.fillna(0.0).sort_index()
C.index = pd.to_datetime(C.index)

# Map each day to latest rebalance's buf_kept set
reb_sorted = sorted(reb)
buf_daily_contrib = []
buf_weeks = 0
buf_kept_count = 0
# For each rebalance, the holdings apply until next rebalance; contrib on days in between
for k, dd in enumerate(reb_sorted):
    kept = buf_kept_map.get(dd, [])
    if not kept:
        continue
    buf_weeks += 1
    buf_kept_count += len(kept)
    nxt = reb_sorted[k + 1] if k + 1 < len(reb_sorted) else C.index[-1]
    # days after dd up to nxt
    seg = C[(C.index > dd) & (C.index <= nxt)]
    if seg.empty:
        continue
    w = W_main.get(dd, {})
    for c in kept:
        if c in seg.columns:
            # sum of daily contrib already = w*r path; use that
            buf_daily_contrib.append(float(seg[c].sum()))

buf_contrib_sum = float(np.sum(buf_daily_contrib)) if buf_daily_contrib else 0.0
# also relative: same days' contrib of those codes under mix (they wouldn't be held) = 0 by definition
# vs counterfactual: if we had sold them into MF — MF contrib approx small; report raw sum

# weeks with any buffer keep
n_sig = sum(1 for dd in reb if gi[dd] >= 52)
pct_buf_weeks = buf_weeks / n_sig if n_sig else 0.0

# cost savings estimate
cost_main = to_main * mf.CPS * 2  # rough annual RT cost proxy (to is one-way/yr; RT=2*CPS)
cost_mix = to_mix * mf.CPS * 2
# actually CPS is one-side; turnover metric is one-way/yr; annual cost ≈ to * CPS * 2 for RT? 
# knife 0.2%RT = 2*CPS with CPS=0.001. Annual cost fraction ≈ turnover_oneway * 0.002
ann_cost_main = to_main * 0.002
ann_cost_mix = to_mix * 0.002

log(f"avg_hold_weeks B10={avg_hold_weeks:.2f} mix={avg_hold_mix:.2f}")
log(f"buf_kept weeks={buf_weeks}/{n_sig} ({pct_buf_weeks:.1%}) contrib_sum={buf_contrib_sum:+.4f}")

# standard attribution module
try:
    e._bench = {**e.benches(), "池等权(318有价,周调,0.2%RT)": (r_pew, to_pew, ex_pew)}
    at = A.attribute(ID, "MF-HOLD-BUF主版", lambda i, dd: W_main.get(dd, {}), OUT, True)
    attr_mod = at["md"]
except Exception as ex:
    log(f"attribution module err: {ex}")
    attr_mod = f"_attribution 模块异常：{ex}_\n"

# side CSV
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
    })
pd.DataFrame(side_rows).to_csv(f"{OUT}/side_weekly_holdings.csv", index=False)

attr_md = f"""## 归因 · MF-HOLD-BUF

### 拆解摘要（模块）
{attr_mod}

### 换手 / 成本
| 项 | 主版 B=10 | 无缓冲混排 | 比 |
|---|---:|---:|---:|
| 换手(单边/年) | {to_main:.2f}x | {to_mix:.2f}x | {to_main/to_mix:.2f}× |
| 估年化成本(×0.2%RT) | {ann_cost_main:.2%} | {ann_cost_mix:.2%} | 节省 {(ann_cost_mix-ann_cost_main):.2%} |
| 平均持有周数(spell) | {avg_hold_weeks:.2f} | {avg_hold_mix:.2f} | {avg_hold_weeks/avg_hold_mix if avg_hold_mix else float('nan'):.2f}× |

证伪闸换手：主版 {'>' if f1 else '≤'} 无缓冲×0.8 = {to_mix*0.8:.2f}x → {'触发' if f1 else '未触发'}。

### 因缓冲「本该卖未卖」
- 定义：某信号周持仓中 **不在当周 XS52 前 {N}**、但因 rank≤B 被保留的代码。
- 有缓冲保留的信号周：{buf_weeks}/{n_sig}（{pct_buf_weeks:.1%}）；累计保留代码·周 ≈ {buf_kept_count}。
- 这些代码在持有段内的日度贡献加总 Σw·r = **{buf_contrib_sum:+.4f}**（相对无缓冲：无缓冲当周不会持有它们，对照贡献为 0；正=缓冲段事后赚钱，负=拖延止损亏钱）。
- 旁注 CSV：`side_weekly_holdings.csv`

### 邻档速览
- B=8 换手 {to_b8:.1f}x / C {mf.stats(r_b8)['Calmar']:.2f}
- B=15 换手 {to_b15:.1f}x / C {mf.stats(r_b15)['Calmar']:.2f}
- 连续确认×2 换手 {to_c2:.1f}x / C {mf.stats(r_c2)['Calmar']:.2f}
"""
if r_catbuf is not None:
    sc = mf.stats(r_catbuf)
    attr_md += f"- 旁注 CAT-MOM+B10：ret {sc['ret']:.1%} / DD {sc['maxDD']:.1%} / C {sc['Calmar']:.2f} / 换手 {to_catbuf:.1f}x\n"

# ---------- REPORT ----------
main = "MF-HOLD-BUF B=10·XS52取5(主版)"
M = pd.DataFrame([mf.row(k, *v[:3]) for k, v in books.items()])

success_hint = (
    (to_main <= to_mix * 0.8)
    and (sm["Calmar"] >= sx["Calmar"] * 0.95)
    and (sm["maxDD"] >= sx["maxDD"] - 0.03)  # not deeper by >3pp (maxDD less negative = larger)
    and (b_m["ret"] >= b_x["ret"] * 0.9)
)

report = HYPO + f"""
## 1. 准则原文
宇宙：研究池 `research_pool_v2` ∩ 周频动量可交易（与 MF-CAT-MOM 全池混排同池）。
选品键不变：XS52 跳1。唯一改 — 持仓缓冲主版 B=10、N=5 等权：已持仓仅 rank>B 才卖；6–B 保留；空位从未持有且 rank≤N 补入；空余 511880。无 TV/breadth/类别配额/冠军栈。

## 2. 实现要点
- 池同 CAT-MOM 混排：宽基{len(CAT['A股宽基'])}/行业{len(CAT['行业主题'])}/港股{len(CAT['港股'])}/跨境{len(CAT['跨境'])}/商品{len(CAT['商品'])}/债{len(CAT['债券货币'])}；W 网格补债券。
- 状态机跨周 `held`：先卖后买；槽位权重 1/N，未满槽补 511880；排名排除纯现金 511880。
- 邻档：B=8 / B=15；连续确认×2（进/出均需该方向信号连续 2 个周五）。
- 旁注：CAT-MOM 主版理想持仓 + B=10 缓冲执行（有则报）。
- 对照：无缓冲混排；全池等权；冠军研究副本。
- 成本 0.2%RT；{mf.START}→{mf.END}；panel_v2 / mf_common。

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

### 逐年
"""
Y = pd.concat([mf.yearly(books[k][0]).assign(book=k) for k in [
    main, "无缓冲全池混排 XS52跳1取5", "邻档 B=8", "邻档 连续确认×2"]])
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

mf.deliver(ID, books, main, f"{ID}（持仓缓冲 B=10 · XS52取5，0.2%RT）", report, attr_md)
M.to_csv(f"{OUT}/metrics.csv", index=False)
pickle.dump(dict(
    W_main=W_main, meta_main=meta_main, falsified=falsified,
    sm=sm, sx=sx, to_main=to_main, to_mix=to_mix, fal=fal, verdict=verdict,
    avg_hold_weeks=avg_hold_weeks, avg_hold_mix=avg_hold_mix,
    buf_contrib_sum=buf_contrib_sum, f1=f1, f2=f2, f3=f3,
), open(f"{OUT}/_res.pkl", "wb"))

knife = Path("/workspace/etf-multifreq/knives/MF-HOLD-BUF.md")
if knife.exists():
    txt = knife.read_text()
    if "（测试填）" in txt:
        knife.write_text(txt.replace("（测试填）", fal))

log("DONE " + verdict + " " + fal)
log(M[["book", "ret", "maxDD", "Calmar", "turnover", "avg_expo"]].round(3).to_string())
LOG.close()
