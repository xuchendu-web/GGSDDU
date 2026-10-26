#!/usr/bin/env python3
"""ETF 多频研究轨共用：只读复用 etf-momentum/etf-trend，写到 etf-multifreq。"""
from __future__ import annotations
import os, sys, math
os.environ["ETF_V"] = "1016"
sys.path.insert(0, "/workspace/etf-momentum/engine")
import numpy as np, pandas as pd
import matplotlib; matplotlib.use("Agg"); import matplotlib.pyplot as plt
plt.rcParams["font.sans-serif"] = ["Noto Sans CJK SC", "WenQuanYi Zen Hei", "SimHei", "DejaVu Sans"]
plt.rcParams["axes.unicode_minus"] = False
import mom_engine as e

START, END = e.START, e.END
CPS = e.CPS  # 0.001 = 单边 0.1% → 0.2%RT
MF = "511880"
OUT_ROOT = "/workspace/etf-multifreq"
OBS = "/workspace/obsidian-notes/ETF多频专题"

# ---- data ----
_D = None
def data():
    global _D
    if _D is not None:
        return _D
    d = e.data()
    P = d["P"].copy()
    # 修正末三周 14:30 ×10（与 etf-trend 一致；mom_engine cache 源文件已校验新三周，但 SIG 可能仍含旧坏点）
    G, W, SIG = d["grid"], d["W"].copy(), d["SIG"].copy()
    # 对齐 codes：研究池分类
    pool = pd.read_csv("/workspace/etf-correlation/data/research_pool_v2.csv", dtype={"code": str})
    pool["code"] = pool.code.str.zfill(6)
    codes = set(d["codes"])
    aw = sorted(set(pool[(pool.l0 == "中国权益") & (pool.family.astype(str).str.startswith("宽基"))].code) & codes)
    ind = sorted(set(pool[(pool.l0 == "中国权益") & (~pool.family.astype(str).str.startswith("宽基"))].code) & codes)
    # OHLC adj open for next-open fills
    raw = pd.read_pickle("/workspace/etf-trend/data/tdx_ohlc_raw.pkl")
    O = {}
    for c in set(aw) | {MF, "511010", "511260"} | set(ind[:1]):  # build all needed below
        pass
    need = sorted(set(aw) | set(ind) | {MF, "511010", "511260"})
    for c in need:
        if c not in raw or c not in P.columns:
            continue
        b = raw[c].copy()
        b.index = pd.to_datetime(b.datetime.str[:10])
        b = b[~b.index.duplicated(keep="last")]
        f = (P[c] / b.close.reindex(P.index))
        O[c] = (b["open"].reindex(P.index) * f)
    Open = pd.DataFrame(O)
    _D = dict(P=P, W=W, SIG=SIG, G=G, aw=aw, ind=ind, Open=Open, codes=list(codes),
              gi={g: i for i, g in enumerate(G)}, reb=[g for g in G if g >= pd.Timestamp(START)][:-1])
    return _D

def stats(s):
    return e.stats(s)

def yearly(s):
    return e.yearly(s)

def mdd(s, a, b):
    q = (1 + s[(s.index >= a) & (s.index <= b)]).cumprod()
    if len(q) < 2:
        return np.nan
    return (q / q.cummax() - 1).min()

def fmt_pct(x):
    if x is None or (isinstance(x, float) and (math.isnan(x) or math.isinf(x))):
        return "—"
    return f"{100 * x:.1f}%"

def fmt_cal(x):
    if x is None or (isinstance(x, float) and (math.isnan(x) or math.isinf(x))):
        return "—"
    return f"{x:.2f}"

# ---- daily backtester (close fill / next-open fill) ----
def run_daily(weight_by_day, fill="close", record=None):
    """weight_by_day: dict date-> {code:w}. fill=close: rebalance at close d, earn close[d]->close[d+1].
    fill=open: signal day d weights applied at open d+1; earn open[d+1]->open[d+2] (adj)."""
    D = data(); P = D["P"]; Open = D["Open"]
    days = P.index[(P.index >= START) & (P.index <= END)]
    r = pd.Series(0.0, index=days)
    cur = {}; to_total = 0.0; expo = []
    if fill == "close":
        # rebalance dates = all days that have weights
        reb = sorted([d for d in weight_by_day if d in days])
        R = P.pct_change()
        for k, dd in enumerate(reb):
            tgt = {c: w for c, w in weight_by_day[dd].items() if w > 0 and c in P.columns and not pd.isna(P.at[dd, c])}
            to = sum(abs(tgt.get(c, 0) - cur.get(c, 0)) for c in set(tgt) | set(cur))
            to_total += to / 2
            r.loc[dd] -= to * CPS
            if record is not None:
                record.setdefault("cost", {})[dd] = to * CPS
            cur = dict(tgt); expo.append(sum(cur.values()))
            nxt = reb[k + 1] if k + 1 < len(reb) else days[-1]
            seg = days[(days > dd) & (days <= nxt)]
            for t in seg:
                if not cur:
                    continue
                rr = R.loc[t, list(cur)].fillna(0.0)
                r.loc[t] += sum(cur[c] * rr[c] for c in cur)
                if record is not None:
                    record.setdefault("contrib", {})[t] = {c: cur[c] * rr[c] for c in cur}
                    record.setdefault("expo", {})[t] = sum(cur.values())
                g = sum(cur[c] * (1 + rr[c]) for c in cur); cash = 1 - sum(cur.values()); tot = g + cash
                if tot > 0:
                    cur = {c: cur[c] * (1 + rr[c]) / tot for c in cur}
    else:  # next open fill
        # weight keyed by signal day d → apply at open of next day
        sig_days = sorted([d for d in weight_by_day if d in days])
        # build open-to-open returns
        Ro = Open.pct_change()
        # map: apply_date (open) -> weights from previous signal
        apply = {}
        for dd in sig_days:
            loc = days.get_loc(dd)
            if loc + 1 >= len(days):
                continue
            apply[days[loc + 1]] = weight_by_day[dd]
        reb = sorted(apply)
        for k, dd in enumerate(reb):
            tgt0 = apply[dd]
            tgt = {c: w for c, w in tgt0.items() if w > 0 and c in Open.columns and not pd.isna(Open.at[dd, c])}
            to = sum(abs(tgt.get(c, 0) - cur.get(c, 0)) for c in set(tgt) | set(cur))
            to_total += to / 2
            # cost booked on calendar day dd (open)
            if dd in r.index:
                r.loc[dd] -= to * CPS
            if record is not None:
                record.setdefault("cost", {})[dd] = to * CPS
            cur = dict(tgt); expo.append(sum(cur.values()))
            nxt = reb[k + 1] if k + 1 < len(reb) else days[-1]
            # earn open[t]->open[t+1] booked on day t+1's calendar (or on t?)
            # Book open-to-open return of day t (open_t -> open_{t+1}) onto calendar day t
            seg = days[(days >= dd) & (days < nxt)]
            for t in seg:
                if not cur:
                    continue
                # return from open t to open next trading day
                loc = days.get_loc(t)
                if loc + 1 >= len(days):
                    break
                t2 = days[loc + 1]
                rets = {}
                for c in list(cur):
                    o1, o2 = Open.at[t, c] if c in Open.columns else np.nan, Open.at[t2, c] if c in Open.columns else np.nan
                    if pd.isna(o1) or pd.isna(o2) or o1 <= 0:
                        rets[c] = 0.0
                    else:
                        rets[c] = o2 / o1 - 1
                r.loc[t] += sum(cur[c] * rets[c] for c in cur)
                if record is not None:
                    record.setdefault("contrib", {})[t] = {c: cur[c] * rets[c] for c in cur}
                    record.setdefault("expo", {})[t] = sum(cur.values())
                g = sum(cur[c] * (1 + rets[c]) for c in cur); cash = 1 - sum(cur.values()); tot = g + cash
                if tot > 0:
                    cur = {c: cur[c] * (1 + rets[c]) / tot for c in cur}
    yrs = (days[-1] - days[0]).days / 365.25
    return r, (to_total / yrs if yrs > 0 else np.nan), float(np.mean(expo) if expo else 0)

# ---- weekly backtester via mom_engine ----
def run_weekly(wmap, record=None):
    return e.run_weights(lambda i, dd: wmap.get(dd, {}), record=record)

def champ():
    return e.benches()["冠军主钉LIVE1430-AUM-max5"]

def row(k, r, to, ex, extra=None):
    s = stats(r); a = stats(r[r.index <= "2022-12-31"]); b = stats(r[r.index >= "2023-01-01"])
    out = dict(book=k, ret=s["ret"], maxDD=s["maxDD"], CAGR=s["CAGR"], Calmar=s["Calmar"],
               ret20_22=a["ret"], dd20_22=a["maxDD"], cal20_22=a["Calmar"],
               ret23_26=b["ret"], dd23_26=b["maxDD"], cal23_26=b["Calmar"],
               dd_down2109_2409=mdd(r, "2021-09-01", "2024-09-30"),
               turnover=to, avg_expo=ex)
    if extra:
        out.update(extra)
    return out

def deliver(ID, books, main, title, report_md, attr_md=None):
    out = f"{OUT_ROOT}/{ID}"
    os.makedirs(out, exist_ok=True)
    M = pd.DataFrame([row(k, *v) if len(v) == 3 else row(k, v[0], v[1], v[2], v[3] if len(v) > 3 else None)
                      for k, v in books.items()])
    # normalize: books values are (r,to,ex) or (r,to,ex,extra_dict)
    rows = []
    for k, v in books.items():
        r, to, ex = v[0], v[1], v[2]
        extra = v[3] if len(v) > 3 else None
        rows.append(row(k, r, to, ex, extra))
    M = pd.DataFrame(rows)
    M.to_csv(f"{out}/metrics.csv", index=False)
    Y = pd.concat([yearly(v[0]).assign(book=k) for k, v in books.items()])
    Y.to_csv(f"{out}/yearly.csv", index=False)
    nav = pd.DataFrame({k: (1 + v[0]).cumprod() for k, v in books.items()})
    nav.to_csv(f"{out}/nav.csv")
    fig, ax = plt.subplots(figsize=(11, 5.5), dpi=120)
    for k in nav:
        ax.plot(nav.index, nav[k], label=k, lw=2.2 if k == main else 1.1)
    ax.set_yscale("log"); ax.grid(alpha=.3); ax.legend(fontsize=7)
    ax.set_title(title); fig.tight_layout(); fig.savefig(f"{out}/nav.png"); plt.close(fig)
    open(f"{out}/REPORT.md", "w").write(report_md)
    if attr_md:
        open(f"{out}/ATTRIBUTION.md", "w").write(attr_md)
    # Obsidian
    os.makedirs(OBS, exist_ok=True)
    open(f"{OBS}/{ID}.md", "w").write(f"# {ID}\n\n#ETF多频专题\n\n" + report_md.split("## 4.")[0] +
        ("\n## 4. 结论\n" + report_md.split("## 4.")[1] if "## 4." in report_md else "") +
        f"\n\n路径：{out}/\n")
    return M

def metrics_table(M, main):
    lines = ["| book | ret | maxDD | CAGR | Calmar | 2020–22 ret/DD/Cal | 2023–26 ret/DD/Cal | 下跌段DD | 换手(单边/年) | 均仓 |",
             "|---|---:|---:|---:|---:|---|---|---:|---:|---:|"]
    order = [main] + [b for b in M.book if b != main]
    for b in order:
        r = M[M.book == b].iloc[0]
        lines.append(
            f"| {r.book} | {fmt_pct(r.ret)} | {fmt_pct(r.maxDD)} | {fmt_pct(r.CAGR)} | {fmt_cal(r.Calmar)} | "
            f"{fmt_pct(r.ret20_22)}/{fmt_pct(r.dd20_22)}/{fmt_cal(r.cal20_22)} | "
            f"{fmt_pct(r.ret23_26)}/{fmt_pct(r.dd23_26)}/{fmt_cal(r.cal23_26)} | "
            f"{fmt_pct(r.dd_down2109_2409)} | "
            f"{'—' if pd.isna(r.turnover) else f'{r.turnover:.1f}x'} | "
            f"{'—' if pd.isna(r.avg_expo) else f'{r.avg_expo:.2f}'} |"
        )
    return "\n".join(lines)

print("mf_common loaded OK", flush=True)
