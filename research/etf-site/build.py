#!/usr/bin/env python3
"""ETF 分析站构建：python3 build.py → dist/"""
import json, os, re, glob, shutil, datetime as dt
import pandas as pd, markdown
from jinja2 import Environment, FileSystemLoader
from sources import *
ROOT=os.path.dirname(os.path.abspath(__file__)); OUT=os.path.join(ROOT,"dist")
env=Environment(loader=FileSystemLoader(f"{ROOT}/templates"),autoescape=False)
BAN=re.compile(r"持仓|账户|成本价|我的仓位|份额|下单")
def pct(v,sign=True): return f"{v:+.1%}" if sign else f"{v:.1%}"

def load_nav(path,col):
    try:
        df=pd.read_csv(path,index_col=0,parse_dates=True)
        s=(df[col] if col and col in df else df.iloc[:,0]).dropna(); return s/s.iloc[0]
    except Exception as e: print("WARN nav",path,e); return None
BM=load_nav(BENCH["csv"],BENCH["col"])
def bench_for(s):
    if s is None or BM is None: return None
    b=BM[(BM.index>=s.index[0])&(BM.index<=s.index[-1])]
    return b/b.iloc[0] if len(b)>10 else None
def metrics(s):
    if s is None or len(s)<10: return None
    yrs=(s.index[-1]-s.index[0]).days/365.25; r=s.pct_change().dropna(); ppy=len(r)/yrs
    dd=(s/s.cummax()-1).min(); cagr=s.iloc[-1]**(1/yrs)-1; vol=r.std()*ppy**.5
    return dict(start=f"{s.index[0]:%Y-%m-%d}",end=f"{s.index[-1]:%Y-%m-%d}",tot=pct(s.iloc[-1]-1),cagr=pct(cagr),
                mdd=pct(dd),calmar=f"{cagr/abs(dd):.2f}",vol=pct(vol,False),sharpe=f"{(r.mean()*ppy-0.015)/vol:.2f}",
                ytd=pct(s.iloc[-1]/s[s.index.year<s.index[-1].year].iloc[-1]-1) if (s.index.year<s.index[-1].year).any() else "-")
def yearly(s,b=None):
    if s is None: return []
    def y(x): e=x.resample("YE").last(); return pd.concat([x.iloc[:1],e]).pct_change().dropna()
    ys=y(s); yb=y(b) if b is not None else None
    return [dict(y=d.year,v=pct(v),neg=v<0,b=(pct(yb.loc[d]) if yb is not None and d in yb.index else "-")) for d,v in ys.items()]
MDD_D={}
def chart(s,b=None,w=600):
    if s is None: return ""
    s0=s; MDD_D[id(s0)]=(s/s.cummax()-1).min()
    s=s.resample("W").last().dropna(); bb=b.resample("W").last().reindex(s.index).ffill() if b is not None else None
    lo=min(s.min(),bb.min() if bb is not None else 9); hi=max(s.max(),bb.max() if bb is not None else 0)
    H,P=280,40; n=len(s); X=lambda i:P+i*(w-P-10)/(max(n-1,1)); Y=lambda v:15+(hi-v)/(hi-lo)*(H-35)
    line=lambda x:" ".join(f"{X(i):.1f},{Y(v):.1f}" for i,v in enumerate(x))
    grid="".join(f'<line x1="{P}" x2="{w-10}" y1="{Y(v):.1f}" y2="{Y(v):.1f}" class="g"/><text x="4" y="{Y(v)+4:.1f}">{v:.2f}</text>' for v in [lo+(hi-lo)*k/4 for k in range(5)])
    years=sorted(set(s.index.year)); xt="".join(f'<text x="{X(list(s.index.year).index(yy)):.0f}" y="{H-4}">{yy}</text>' for yy in years[1:])
    dd_full=s0/s0.cummax()-1; dd_w=dd_full.resample("W").last().reindex(s.index).ffill()
    DH=110; mdd=dd_full.min() or -0.01; mdd_d=MDD_D.get(id(s0),mdd)
    dpts=f"{X(0)},{8}"+" "+" ".join(f"{X(i):.1f},{8+v/mdd*(DH-20):.1f}" for i,v in enumerate(dd_w.fillna(0)))+f" {X(n-1)},8"
    leg=f'<span class="lg s"></span>策略' + (f' <span class="lg b"></span>{BENCH["name"]}' if bb is not None else "")
    dates=[f"{d:%Y-%m-%d}" for d in s.index]
    xs=[round(X(i),1) for i in range(n)]
    meta=dict(dates=dates,strat=[round(float(v),4) for v in s],bench=[round(float(v),4) for v in bb] if bb is not None else None,
              dd=[round(float(v),4) for v in dd_w],pad=P,width=w,x=xs,
              yStrat=[round(Y(v),1) for v in s],yBench=[round(Y(v),1) for v in bb] if bb is not None else None,
              yDd=[round(8+v/mdd*(DH-20),1) for v in dd_w.fillna(0)])
    meta_js=json.dumps(meta,separators=(",",":"))
    nav=(f'<div class="chart-panel" data-series=\'{meta_js}\'><div class="legend">{leg}</div>'
         f'<svg viewBox="0 0 {w} {H}" class="chart chart--nav chart--interactive" role="img" aria-label="净值曲线">'
         f'<line x1="{P}" y1="{H-20}" x2="{w-10}" y2="{H-20}" class="axis-line"/>{grid}{xt}'
         + (f'<polyline class="bl" points="{line(bb)}"/>' if bb is not None else "")
         + f'<polyline class="sl" points="{line(s)}"/></svg>'
         f'<div class="legend">回撤（最深 {mdd_d:.1%}，日频）</div>'
         f'<svg viewBox="0 0 {w} {DH}" class="chart chart--dd chart--interactive" role="img" aria-label="回撤曲线">'
         f'<line x1="{P}" x2="{w-10}" y1="8" y2="8" class="g axis-line"/>'
         f'<text x="4" y="12">0%</text><text x="4" y="{DH-10}">{mdd:.0%}</text><polygon class="ddp" points="{dpts}"/></svg></div>')
    return f'<div class="chart-stack">{nav}</div>'
def page(tpl,path,**kw):
    p=os.path.join(OUT,path); os.makedirs(os.path.dirname(p),exist_ok=True)
    kw.setdefault("base","../"*path.count("/"))
    open(p,"w").write(env.get_template(tpl).render(built=BUILT,bench=BENCH["name"],**kw))
def book(path):
    return json.load(open(path)) if path and os.path.exists(path) else {}

def report_body(rep_path):
    if not os.path.exists(rep_path): return ""
    md=re.sub(r"^# .*\n","",open(rep_path).read(),count=1)
    md=re.sub(r"`?/workspace/[^\s`)，。]*`?","（内部文件）",md)
    return '<details class="rep"><summary>完整研究报告（含参数邻档、分段、换手）</summary><article>'+markdown.markdown(md,extensions=["tables"])+'</article></details>'

def static_metrics(summary):
    """SUMMARY 手填行 → 与 metrics() 同键，供对比表；无 nav 时用。"""
    if not summary: return None
    return dict(start="—", end="SUMMARY", tot=summary.get("ret","—"),
                cagr=summary.get("ret","—"), mdd=summary.get("mdd","—"),
                calmar=summary.get("calmar","—"), vol="—", sharpe="—", ytd="—",
                _static=True, _src=summary.get("src",""))

BUILT=dt.datetime.now().strftime("%Y-%m-%d %H:%M")
shutil.rmtree(OUT,ignore_errors=True); shutil.copytree(f"{ROOT}/static",f"{OUT}/static")
# 冠军最新信号（只取开关/宽度，不含个人信息）
cb=book(STRATEGIES[0].get("book")).get("last_signal",{})
SIGNAL=dict(asof=cb.get("asof","-"),on=cb.get("risk_on"),breadth=f"{cb.get('breadth',0):.0%}",n=f"{cb.get('n_above','-')}/{cb.get('n_ready','-')}",
            hold=len(cb.get("holdings") or []),eq=f"{cb.get('target_equity_weight',0):.0%}") if cb else None
projs=[]
for st in STRATEGIES:
    s=load_nav(st["csv"],st["col"]); b=bench_for(s); m=metrics(s)
    projs.append(dict(st,m=m,url=f"projects/{st['slug']}.html",kind="live"))
    page("strategy.html",f"projects/{st['slug']}.html",st=st,m=m,mb=metrics(b),yr=yearly(s,b),chart=chart(s,b),
         signal=SIGNAL if st["slug"]=="champion" else None)
fut=[]
for sid,desc,one,eta in FUTURE:
    d=os.path.join(MOMENTUM_DIR,sid if os.path.isdir(os.path.join(MOMENTUM_DIR,sid)) else sid.replace("+","-")); navf=os.path.join(d,"nav.csv"); rep=os.path.join(d,"REPORT.md")
    s=load_nav(navf,"nav") if os.path.exists(navf) else None; b=bench_for(s); m=metrics(s)
    body=report_body(rep)
    slug=sid.lower().replace("+","-")
    st=dict(name=f"{sid} · {desc}",oneliner=one,status="研究完成 · 未替换冠军" if m else f"开发中 · 预计 {eta} 出结果",eta=eta,
            rules=[],note="统一口径：行业ETF池、周五14:30信号/收盘成交、扣0.2%双边、不加杠杆。")
    fut.append(dict(st,slug=slug,m=m,url=f"projects/{slug}.html",kind="dev",track="动量"))
    page("strategy.html",f"projects/{slug}.html",st=st,m=m,mb=metrics(b),yr=yearly(s,b),chart=chart(s,b),body=body,signal=None)

# —— 趋势轨 ——
trend_rows=[]
for t in TREND:
    d=os.path.join(TREND_DIR,t["id"]); navf=os.path.join(d,"nav.csv"); rep=os.path.join(d,"REPORT.md")
    s=None
    if t.get("col") and os.path.exists(navf):
        s=load_nav(navf,t["col"])
    elif os.path.exists(navf):
        s=load_nav(navf,None)
    b=bench_for(s); m=metrics(s)
    body=report_body(rep)
    slug=t["id"].lower()
    tag=t.get("tag") or ""
    # 避免「止损 · 止损」类重复
    st_label=t["status"] if (not tag or tag in t["status"]) else f"{t['status']} · {tag}"
    st=dict(name=t["name"],oneliner=t["oneliner"],
            status=f"趋势 · {st_label}",
            rules=["池：333 只（含 15 债），空=511880","逐只趋势开关，单槽 1/N，L≤1","周五≥14:30 信号 / 收盘成交，0.2%RT"],
            note="研究结论不代表已采用；不换冠军、不下单。趋势收益 38–45% 不接近冠军同引擎。")
    row=dict(st,slug=slug,m=m,url=f"projects/{slug}.html",kind="dev",track="趋势",
             in_cmp=t.get("in_cmp",False), tag=t.get("tag",""))
    trend_rows.append(row)
    page("strategy.html",f"projects/{slug}.html",st=st,m=m,mb=metrics(b),yr=yearly(s,b),chart=chart(s,b),body=body,signal=None)

# —— 多频可用积木 ——
mf_rows=[]
missing=[]
for mf in MULTIFREQ:
    s=None
    if mf.get("csv") and os.path.exists(mf["csv"]) and mf.get("col"):
        s=load_nav(mf["csv"],mf["col"])
    b=bench_for(s); m=metrics(s)
    if m is None:
        m=static_metrics(mf.get("summary"))
        missing.append(f"{mf['id']}: nav 未加载，对比表用 SUMMARY 静态行（{mf.get('summary',{}).get('src','')}）")
        print("WARN static", mf["id"])
    slug=mf["id"].lower().replace("+","-")
    st=dict(name=mf["name"],oneliner=mf["oneliner"],
            status=f"多频 · {mf['status']}",
            rules=["来源：etf-multifreq SUMMARY 10-17","口径：0.2%RT，L≤1；周频为主"],
            note="多频合层已暂停；固定60/40 作核心压舱，B4 仅卫星旁注不单飞。不换冠军、不下单。")
    body=""
    # 挂上多频 SUMMARY 摘录（若存在）
    sum_path=f"{W}/etf-multifreq/SUMMARY/SUMMARY.md"
    if os.path.exists(sum_path) and mf["id"] in ("MF-6040","MF-B4"):
        body='<details class="rep"><summary>多频 SUMMARY 摘录</summary><article>'+markdown.markdown(open(sum_path).read(),extensions=["tables"])+'</article></details>'
    row=dict(st,slug=slug,m=m,url=f"projects/{slug}.html",kind="dev",track="多频",
             in_cmp=mf.get("in_cmp",True), tag=mf.get("tag",""))
    mf_rows.append(row)
    page("strategy.html",f"projects/{slug}.html",st=st,m=m,mb=metrics(b) if s is not None else None,
         yr=yearly(s,b) if s is not None else [], chart=chart(s,b) if s is not None else "",
         body=body,signal=None)

# 横向对比：冠军/红利 + 动量有结果 + 趋势未证伪 + 多频可用
cmp_extra=[r for r in trend_rows if r.get("in_cmp") and r.get("m")]
cmp_extra += [r for r in mf_rows if r.get("in_cmp") and r.get("m")]

page("projects.html","projects/index.html",projs=projs,fut=fut,trend=trend_rows,mf=mf_rows,
     cmp_extra=cmp_extra, tracks=TRACK_COMPARE)
page("compare.html","projects/compare.html",projs=projs,fut=fut,trend=trend_rows,mf=mf_rows,
     cmp_extra=cmp_extra, tracks=TRACK_COMPARE)

arts=[]
for d in MARKET_DIRS:
    for f in sorted(glob.glob(f"{d}/20*.md"),reverse=True):
        lines=[l for l in open(f).read().splitlines() if not BAN.search(l) or "不写持仓" in l]
        slug=os.path.basename(f)[:-3]; title=next((l.lstrip("# ") for l in lines if l.startswith("#")),slug)
        lines=[l for l in lines if l.lstrip("# ")!=title]
        summ=next((re.sub(r"[*#>]","",l) for l in lines if len(l)>40 and not l.startswith(("|","**"))),"")[:90]
        arts.append(dict(slug=slug,name=title,date=slug,summ=summ))
        page("article.html",f"market/{slug}.html",title=title,date=slug,body=markdown.markdown("\n".join(lines),extensions=["tables"]))
page("market.html","market/index.html",arts=arts)
pfs=[]
for p in [p for p in PORTFOLIOS if p.get("enabled",True)]:
    s=load_nav(p["csv"],p["col"]); b=bench_for(s); bk=book(p["book"]); m=metrics(s)
    pos=[x for x in (bk.get("positions") or []) if isinstance(x,dict)]
    cashw=1-sum(x.get("weight",0) for x in pos) if bk else None
    pfs.append(dict(p,m=m,url=f"portfolios/{p['slug']}.html",asof=bk.get("last_signal",{}).get("asof")))
    page("portfolio.html",f"portfolios/{p['slug']}.html",p=p,m=m,mb=metrics(b),yr=yearly(s,b),chart=chart(s,b),
         pos=pos,cashw=cashw,asof=bk.get("last_signal",{}).get("asof"),live=bool(bk))
page("portfolios.html","portfolios/index.html",pfs=pfs)
page("index.html","index.html",projs=projs,fut=fut,arts=arts[:3],pfs=pfs,signal=SIGNAL,base="")
def _json(rel):
    p=os.path.join(ROOT,rel)
    return json.load(open(p,encoding="utf-8")) if os.path.exists(p) else {}
page("active.html","active/index.html",active=_json("data/active-etf.json"),nav_active=True)
page("method.html","method/index.html",nav_method=True)
page("about.html","about.html")
print("built ->",OUT)
if missing:
    print("STATIC_FALLBACK:", "; ".join(missing))
