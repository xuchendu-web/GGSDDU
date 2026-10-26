#!/usr/bin/env python3
"""本地视觉预览：不依赖 workspace 数据路径。"""
import json
import os
import shutil
from jinja2 import Environment, FileSystemLoader

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT = os.path.join(ROOT, "preview", "dist")
env = Environment(loader=FileSystemLoader(f"{ROOT}/templates"), autoescape=False)

# 合成净值曲线 metadata（与 build.chart 输出一致）
def demo_chart():
    import math
    n = 120
    dates = [f"2020-{((i // 4) % 12) + 1:02d}-{(i % 4) * 7 + 1:02d}" for i in range(n)]
    strat = [1 + 0.004 * i + 0.08 * math.sin(i / 8) for i in range(n)]
    bench = [1 + 0.0025 * i + 0.05 * math.sin(i / 10) for i in range(n)]
    dd = [min(0, (v / max(strat[: i + 1]) - 1)) for i, v in enumerate(strat)]
    w, P, H, DH = 600, 40, 280, 110
    lo = min(min(strat), min(bench))
    hi = max(max(strat), max(bench))
    X = lambda i: P + i * (w - P - 10) / (n - 1)
    Y = lambda v: 15 + (hi - v) / (hi - lo) * (H - 35)
    xs = [round(X(i), 1) for i in range(n)]
    mdd = min(dd) or -0.01
    dpts = f"{X(0)},{8} " + " ".join(f"{X(i):.1f},{8 + v / mdd * (DH - 20):.1f}" for i, v in enumerate(dd)) + f" {X(n - 1)},{8}"
    line_s = " ".join(f"{X(i):.1f},{Y(v):.1f}" for i, v in enumerate(strat))
    line_b = " ".join(f"{X(i):.1f},{Y(v):.1f}" for i, v in enumerate(bench))
    meta = dict(
        dates=dates,
        strat=[round(v, 4) for v in strat],
        bench=[round(v, 4) for v in bench],
        dd=[round(v, 4) for v in dd],
        pad=P,
        width=w,
        x=xs,
        yStrat=[round(Y(v), 1) for v in strat],
        yBench=[round(Y(v), 1) for v in bench],
        yDd=[round(8 + v / mdd * (DH - 20), 1) for v in dd],
    )
    meta_js = json.dumps(meta, separators=(",", ":"))
    grid = "".join(
        f'<line x1="{P}" x2="{w - 10}" y1="{Y(lo + (hi - lo) * k / 4):.1f}" y2="{Y(lo + (hi - lo) * k / 4):.1f}" class="g"/>'
        for k in range(5)
    )
    return (
        f'<div class="chart-stack"><div class="chart-panel" data-series=\'{meta_js}\'>'
        f'<div class="legend"><span class="lg s"></span>策略 <span class="lg b"></span>中证偏股基准</div>'
        f'<svg viewBox="0 0 {w} {H}" class="chart chart--nav chart--interactive">'
        f'<line x1="{P}" y1="{H - 20}" x2="{w - 10}" y2="{H - 20}" class="axis-line"/>{grid}'
        f'<polyline class="bl" points="{line_b}"/><polyline class="sl" points="{line_s}"/></svg>'
        f'<div class="legend">回撤（最深 {mdd:.1%}，日频）</div>'
        f'<svg viewBox="0 0 {w} {DH}" class="chart chart--dd chart--interactive">'
        f'<polygon class="ddp" points="{dpts}"/></svg></div></div>'
    )


mock_m = dict(
    start="2016-01-04",
    end="2026-10-17",
    tot="+187.3%",
    cagr="+11.2%",
    mdd="-18.4%",
    calmar="0.61",
    vol="12.3%",
    sharpe="0.82",
    ytd="+8.1%",
)

projs = [
    dict(
        st=dict(name="冠军主钉 · 行业ETF轮动", status="现任冠军", oneliner="宽度开关 + spike 选股。"),
        m=mock_m,
        url="strategy-demo.html",
    ),
    dict(
        st=dict(name="红利袖 · FCF@3.5", status="研究完成", oneliner="高股息 + 正 FCF。"),
        m={**mock_m, "tot": "+92.1%", "cagr": "+7.8%"},
        url="#",
    ),
]

signal = dict(asof="2026-10-17", on=True, breadth="52%", n="98/120")
arts = [
    dict(slug="2026-10-25", name="一周盘面复盘 · 2026-10-25", summ="A股窄幅收阴、小盘相对强；港股恒指周跌约 4.5%；美债收益率回落、布油冲高。"),
]

shutil.rmtree(OUT, ignore_errors=True)
os.makedirs(OUT, exist_ok=True)
shutil.copytree(f"{ROOT}/static", f"{OUT}/static")

pages = {
    "index.html": env.get_template("index.html").render(
        base="",
        built="2026-10-25 17:00",
        bench="中证偏股基金指数 930950",
        nav_home=True,
        projs=projs,
        fut=[],
        pfs=[],
        arts=arts,
        signal=signal,
    ),
    "strategy-demo.html": env.get_template("strategy.html").render(
        base="",
        built="2026-10-25 17:00",
        bench="中证偏股基金指数 930950",
        st=projs[0]["st"],
        m=mock_m,
        yr=[dict(y=2024, v="+12.3%", neg=False, b="+5.1%"), dict(y=2025, v="-3.2%", neg=True, b="+1.0%")],
        chart=demo_chart(),
        signal=signal,
        body="",
    ),
    "about.html": env.get_template("about.html").render(
        base="", built="2026-10-25", bench="中证偏股基金指数 930950", nav_about=True
    ),
    "market-empty.html": env.get_template("market.html").render(
        base="",
        built="2026-10-25",
        bench="中证偏股基金指数 930950",
        nav_market=True,
        arts=[],
    ),
}

active_path = os.path.join(ROOT, "data", "active-etf.json")
with open(active_path, encoding="utf-8") as fh:
    active_data = json.load(fh)

pages["active/index.html"] = env.get_template("active.html").render(
    base="../",
    built="2026-10-26",
    bench="中证偏股基金指数 930950",
    nav_active=True,
    active=active_data,
)
pages["method/index.html"] = env.get_template("method.html").render(
    base="../",
    built="2026-10-26",
    bench="中证偏股基金指数 930950",
    nav_method=True,
)

for name, html in pages.items():
    dest = os.path.join(OUT, name)
    os.makedirs(os.path.dirname(dest), exist_ok=True)
    open(dest, "w").write(html)

print("preview ->", OUT)
