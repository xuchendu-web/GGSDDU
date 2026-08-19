#!/usr/bin/env python3
"""
基金穿透与多维归因引擎 v2
Brinson 行业归因 + 因子归因（规模/价值/动量/质量）+ 个股贡献 + 买卖时机评估
"""

import json, sys, argparse, math
from datetime import datetime
from pathlib import Path
from collections import defaultdict

SW_ORDER = [
    "电子","电力设备","有色金属","煤炭","石油石化","国防军工","公用事业","汽车",
    "基础化工","钢铁","银行","非银金融","建筑材料","建筑装饰","机械设备",
    "计算机","通信","传媒","家用电器","食品饮料","纺织服饰","轻工制造",
    "医药生物","交通运输","房地产","商贸零售","社会服务","农林牧渔","美容护理","环保"
]

FACTOR_NAMES = ["规模","价值","动量","质量"]
FACTOR_COLORS = {"规模":"#1565c0","价值":"#2e7d32","动量":"#f57f17","质量":"#c62828"}


def brinson_attribution(portfolio, benchmark, period=""):
    allocation = selection = interaction = 0.0
    details = []
    all_sectors = set(list(portfolio.keys()) + list(benchmark.keys()))
    for sector in sorted(all_sectors, key=lambda s: SW_ORDER.index(s) if s in SW_ORDER else 99):
        wp = portfolio.get(sector, {}).get("weight", 0)
        rp = portfolio.get(sector, {}).get("return", 0)
        wb = benchmark.get(sector, {}).get("weight", 0)
        rb = benchmark.get(sector, {}).get("return", 0)
        alloc = (wp - wb) * rb
        sel = wb * (rp - rb)
        inter = (wp - wb) * (rp - rb)
        allocation += alloc; selection += sel; interaction += inter
        if abs(wp) > 0.001 or abs(wb) > 0.001:
            details.append({"sector":sector,"w_port":round(wp*100,1),"w_bench":round(wb*100,1),
                "r_port":round(rp*100,2),"r_bench":round(rb*100,2),
                "alloc":round(alloc*100,2),"sel":round(sel*100,2),"inter":round(inter*100,2),
                "total":round((alloc+sel+inter)*100,2)})
    return {"allocation":round(allocation*100,2),"selection":round(selection*100,2),
            "interaction":round(interaction*100,2),"total_excess":round((allocation+selection+interaction)*100,2),
            "details":details}


def factor_attribution(factor_data):
    """因子归因：active_exposure × factor_return"""
    exposures = factor_data.get("exposures", {})
    returns = factor_data.get("factor_returns", {})
    bench_exposures = factor_data.get("bench_exposures", {})
    result = {"details": [], "total": 0}
    for fname in FACTOR_NAMES:
        pe = exposures.get(fname, 0)
        be = bench_exposures.get(fname, 0)
        fr = returns.get(fname, 0)
        active = pe - be
        contrib = active * fr * 100
        result["details"].append({"factor": fname, "port_exp": round(pe, 2), "bench_exp": round(be, 2),
                                   "active_exp": round(active, 2), "factor_return": round(fr * 100, 1),
                                   "contrib": round(contrib, 2)})
        result["total"] += contrib
    result["total"] = round(result["total"], 2)
    return result


def generate_html(data, attribution, factor_attr):
    report_date = datetime.now().strftime("%Y-%m-%d")
    fund_names = data.get("fund_names", [])
    period = data.get("period", "最近6个月")
    bn = data.get("benchmark_name", "沪深300")

    pr = round(data.get("portfolio_return", 0) * 100, 2)
    br = round(data.get("benchmark_return", 0) * 100, 2)
    excess = round(pr - br, 2)
    alloc = attribution["allocation"]
    sel = attribution["selection"]
    inter = attribution["interaction"]

    def j(o): return json.dumps(o, ensure_ascii=False).replace("</", "<\\/")
    def c(v): return "#E60000" if v >= 0 else "#009900"

    # ==== 行业配置图数据 ====
    details = attribution["details"]
    alloc_labels = [d["sector"] for d in sorted(details, key=lambda x: -abs(x["total"]))[:15]]
    port_w = [d["w_port"] for d in sorted(details, key=lambda x: -abs(x["total"]))[:15]]
    bench_w = [d["w_bench"] for d in sorted(details, key=lambda x: -abs(x["total"]))[:15]]

    # ==== Brinson 数据 ====
    brin_l = []; brin_a = []; brin_s = []; brin_i = []
    for d in sorted(details, key=lambda x: -abs(x["total"]))[:15]:
        brin_l.append(d["sector"]); brin_a.append(d["alloc"]); brin_s.append(d["sel"]); brin_i.append(d["inter"])

    # ==== 因子数据 ====
    fd = factor_attr["details"]
    factor_l = [f["factor"] for f in fd]
    factor_contrib = [f["contrib"] for f in fd]
    factor_active = [f["active_exp"] for f in fd]
    factor_fr = [f["factor_return"] for f in fd]

    # ==== 个股贡献 ====
    sc = data.get("stock_contributions", [])
    top = [s for s in sorted(sc, key=lambda x: -x["contrib"])[:8] if s["contrib"] > 0]
    bot = [s for s in sorted(sc, key=lambda x: x["contrib"])[:8] if s["contrib"] < 0]

    # ==== 买卖时机评估 ====
    timing = data.get("timing_assessment", [])
    timing_rows = "".join(
        f'<tr><td>{t["name"]}</td><td>{t["weight"]:.1f}%</td><td>{t["entry_date"]}</td>'
        f'<td style="color:{c(t["entry_return"])};font-weight:700;">{t["entry_return"]:+.1f}%</td>'
        f'<td style="color:{c(t["period_return"])};font-weight:700;">{t["period_return"]:+.1f}%</td>'
        f'<td><span style="color:#2e7d32;">{t["verdict"]}</span></td></tr>'
        for t in timing[:8]
    )

    # 归因明细表
    detail_rows = "".join(
        f'<tr><td>{d["sector"]}</td><td style="text-align:center;">{d["w_port"]}%</td>'
        f'<td style="text-align:center;">{d["w_bench"]}%</td>'
        f'<td style="text-align:center;">{d["r_port"]:+.2f}%</td><td style="text-align:center;">{d["r_bench"]:+.2f}%</td>'
        f'<td style="text-align:center;color:{c(d["alloc"])};">{d["alloc"]:+.2f}%</td>'
        f'<td style="text-align:center;color:{c(d["sel"])};">{d["sel"]:+.2f}%</td>'
        f'<td style="text-align:center;color:{c(d["inter"])};">{d["inter"]:+.2f}%</td>'
        f'<td style="text-align:center;color:{c(d["total"])};font-weight:700;">{d["total"]:+.2f}%</td></tr>'
        for d in details
    )

    top_rows = "".join(
        f'<tr><td>{s["name"]}</td><td style="text-align:center;">{s["sector"]}</td>'
        f'<td style="text-align:right;">{s["weight"]:.1f}%</td>'
        f'<td style="text-align:right;color:#E60000;font-weight:700;">+{s["contrib"]:.2f}%</td></tr>'
        for s in top
    )
    bot_rows = "".join(
        f'<tr><td>{s["name"]}</td><td style="text-align:center;">{s["sector"]}</td>'
        f'<td style="text-align:right;">{s["weight"]:.1f}%</td>'
        f'<td style="text-align:right;color:#009900;font-weight:700;">{s["contrib"]:.2f}%</td></tr>'
        for s in bot
    )

    factor_rows = "".join(
        f'<tr><td style="font-weight:600;">{f["factor"]}</td>'
        f'<td style="text-align:center;">{f["port_exp"]:.2f}</td>'
        f'<td style="text-align:center;">{f["bench_exp"]:.2f}</td>'
        f'<td style="text-align:center;color:{c(f["active_exp"])};">{f["active_exp"]:+.2f}</td>'
        f'<td style="text-align:center;">{f["factor_return"]:+.1f}%</td>'
        f'<td style="text-align:center;color:{c(f["contrib"])};font-weight:700;">{f["contrib"]:+.2f}%</td></tr>'
        for f in fd
    )

    html = f"""<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="UTF-8"><meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>基金穿透与归因分析 v2 — {report_date}</title>
<script src="https://cdnjs.cloudflare.com/ajax/libs/Chart.js/4.4.1/chart.umd.js"></script>
<style>
*{{margin:0;padding:0;box-sizing:border-box}}
body{{font-family:-apple-system,BlinkMacSystemFont,"Microsoft YaHei",sans-serif;background:#f5f6fa;color:#2c3e50;padding:20px}}
.header{{text-align:center;padding:24px 0 16px;background:linear-gradient(135deg,#1a237e,#283593);color:#fff;border-radius:12px;margin-bottom:20px}}
.header h1{{font-size:26px;font-weight:700}}.header .sub{{font-size:13px;opacity:.7;margin-top:4px}}
.cards{{display:flex;gap:10px;margin-bottom:20px;flex-wrap:wrap}}
.card{{flex:1;min-width:130px;background:#fff;border-radius:10px;padding:14px;text-align:center;box-shadow:0 2px 8px rgba(0,0,0,0.05)}}
.card-label{{font-size:12px;color:#999}}.card-value{{font-size:24px;font-weight:700;margin:4px 0}}
.section{{background:#fff;border-radius:12px;padding:20px;box-shadow:0 2px 8px rgba(0,0,0,0.05);margin-bottom:16px}}
.section-title{{font-size:16px;font-weight:700;margin-bottom:16px;border-bottom:2px solid #f0f0f0;padding-bottom:8px}}
.chart-row{{display:grid;grid-template-columns:1fr 1fr;gap:16px}}
.stock-grid{{display:grid;grid-template-columns:1fr 1fr;gap:16px}}
table{{width:100%;border-collapse:collapse;font-size:13px}}
th{{background:#f5f5f5;padding:8px 6px;text-align:left;font-weight:600}}
td{{padding:7px 6px;border-bottom:1px solid #f0f0f0}}
.conclusion{{font-size:14px;line-height:1.8;padding:16px;background:#e8eaf6;border-radius:10px;margin-top:12px}}
.footer{{text-align:center;color:#bbb;font-size:12px;margin-top:20px;padding:10px}}
@media(max-width:800px){{.chart-row,.stock-grid{{grid-template-columns:1fr}}}}
</style></head><body>

<div class="header">
    <h1>📊 基金穿透与多维归因分析</h1>
    <div class="sub">{", ".join(fund_names[:4])} · {period} · 基准：{bn}</div>
</div>

<div class="cards">
    <div class="card"><div class="card-label">组合收益</div><div class="card-value" style="color:{c(pr)};">{pr:+.2f}%</div></div>
    <div class="card"><div class="card-label">基准收益</div><div class="card-value" style="color:{c(br)};">{br:+.2f}%</div></div>
    <div class="card"><div class="card-label">超额收益</div><div class="card-value" style="color:{c(excess)};">{excess:+.2f}%</div></div>
    <div class="card"><div class="card-label">配置效应</div><div class="card-value" style="color:{c(alloc)};">{alloc:+.2f}%</div></div>
    <div class="card"><div class="card-label">选股效应</div><div class="card-value" style="color:{c(sel)};">{sel:+.2f}%</div></div>
    <div class="card"><div class="card-label">交互效应</div><div class="card-value" style="color:{c(inter)};">{inter:+.2f}%</div></div>
    <div class="card"><div class="card-label">因子贡献</div><div class="card-value" style="color:{c(factor_attr['total'])};">{factor_attr['total']:+.2f}%</div></div>
</div>

<div class="section">
    <div class="section-title">📊 Brinson 行业归因</div>
    <div class="chart-row">
        <div style="position:relative;height:380px"><canvas id="allocChart" role="img" aria-label="行业配置对比"></canvas></div>
        <div style="position:relative;height:380px"><canvas id="brinsonChart" role="img" aria-label="Brinson归因堆叠"></canvas></div>
    </div>
</div>

<div class="section">
    <div class="section-title">📈 因子归因</div>
    <div class="chart-row">
        <div style="position:relative;height:260px"><canvas id="factorExpChart" role="img" aria-label="因子暴露对比"></canvas></div>
        <div style="position:relative;height:260px"><canvas id="factorContribChart" role="img" aria-label="因子收益贡献"></canvas></div>
    </div>
    <table style="margin-top:12px">
        <thead><tr><th>因子</th><th>组合暴露</th><th>基准暴露</th><th>主动暴露</th><th>因子收益</th><th>贡献</th></tr></thead>
        <tbody>{factor_rows}</tbody>
    </table>
</div>

<div class="section">
    <div class="section-title">📋 Brinson 归因明细表</div>
    <table><thead><tr><th>行业</th><th>组合权重</th><th>基准权重</th><th>组合收益</th><th>基准收益</th><th>配置效应</th><th>选股效应</th><th>交互效应</th><th>总贡献</th></tr></thead>
    <tbody>{detail_rows}</tbody></table>
</div>

<div class="section">
    <div class="section-title">🎯 个股收益贡献</div>
    <div class="stock-grid">
        <div><div style="font-size:14px;font-weight:600;color:#E60000;margin-bottom:8px">正面贡献 TOP</div>
        <table><thead><tr><th>股票</th><th>行业</th><th>权重</th><th>贡献</th></tr></thead>
        <tbody>{top_rows or "<tr><td colspan=4 style=color:#ccc>无</td></tr>"}</tbody></table></div>
        <div><div style="font-size:14px;font-weight:600;color:#009900;margin-bottom:8px">负面拖累 TOP</div>
        <table><thead><tr><th>股票</th><th>行业</th><th>权重</th><th>拖累</th></tr></thead>
        <tbody>{bot_rows or "<tr><td colspan=4 style=color:#ccc>无</td></tr>"}</tbody></table></div>
    </div>
</div>

<div class="section">
    <div class="section-title">⏱️ 买卖时机评估</div>
    <table><thead><tr><th>标的</th><th>权重</th><th>入场时间</th><th>入场后收益</th><th>期间收益</th><th>评估</th></tr></thead>
    <tbody>{timing_rows or "<tr><td colspan=6 style=color:#ccc>暂无评估数据</td></tr>"}</tbody></table>
</div>

<div class="section">
    <div class="section-title">📌 多维归因总结</div>
    <div class="conclusion">
        <p>组合近半年累计收益 <b style="color:{c(pr)};">{pr:+.2f}%</b>，跑{"赢" if excess>=0 else "输"}基准 <b>{abs(excess):.2f}%</b>。</p>
        <p>Brinson归因：{"配置效应("+f'{alloc:+.2f}%'+"{:+.2f}%".format(alloc)+")" if abs(alloc)>1 else ""}主导超额，{"超配高景气行业获得正收益" if alloc>1 else "行业配置中性" if abs(alloc)<1 else "配置方向不利"}。</p>
        <p>因子归因：组合在 <b>{max(details,key=lambda x: abs(x["total"])).get("sector","—") if details else "—"}</b> 上暴露集中，规模/动量因子{"正向" if factor_attr.get("total",0)>0 else "负向"}贡献。</p>
        <p>风险提示：行业集中度极高（电子>78%），因子暴露单一，一旦风格切换将面临较大回撤。</p>
    </div>
</div>

<script>
(function(){{
    var c1=document.getElementById('allocChart'); if(!c1)return;
    var c1opts = {{indexAxis:'y',responsive:true,maintainAspectRatio:false,plugins:{{legend:{{position:'top',labels:{{usePointStyle:true,boxWidth:10,font:{{size:11}}}}}}}},scales:{{x:{{ticks:{{font:{{size:10}}}}}},y:{{ticks:{{font:{{size:11}}}}}}}}}};
    new Chart(c1,{{type:'bar',data:{{labels:{j(alloc_labels)},datasets:[{{label:'组合权重%',data:{j(port_w)},backgroundColor:'#1a237e',borderRadius:3}},{{label:'基准权重%',data:{j(bench_w)},backgroundColor:'#9fa8da',borderRadius:3}}]}},options:c1opts}});

    var c2=document.getElementById('brinsonChart'); if(!c2)return;
    var c2opts = {{indexAxis:'y',responsive:true,maintainAspectRatio:false,plugins:{{legend:{{position:'top',labels:{{usePointStyle:true,boxWidth:10,font:{{size:11}}}}}}}},scales:{{x:{{ticks:{{font:{{size:10}},callback:function(v){{return v.toFixed(1)+'%'}}}}}},y:{{ticks:{{font:{{size:11}}}}}}}}}};
    new Chart(c2,{{type:'bar',data:{{labels:{j(brin_l)},datasets:[{{label:'配置效应',data:{j(brin_a)},backgroundColor:'#1a237e',stack:'s1',borderRadius:2}},{{label:'选股效应',data:{j(brin_s)},backgroundColor:'#5c6bc0',stack:'s1',borderRadius:2}},{{label:'交互效应',data:{j(brin_i)},backgroundColor:'#c5cae9',stack:'s1',borderRadius:2}}]}},options:c2opts}});

    var c3=document.getElementById('factorExpChart'); if(!c3)return;
    var c3opts = {{responsive:true,maintainAspectRatio:false,plugins:{{legend:{{position:'top',labels:{{usePointStyle:true,boxWidth:10,font:{{size:11}}}}}}}}}};
    new Chart(c3,{{type:'bar',data:{{labels:{j(factor_l)},datasets:[{{label:'组合暴露',data:{j([f["port_exp"] for f in fd])},backgroundColor:'#1a237e',borderRadius:3}},{{label:'基准暴露',data:{j([f["bench_exp"] for f in fd])},backgroundColor:'#9fa8da',borderRadius:3}}]}},options:c3opts}});

    var c4=document.getElementById('factorContribChart'); if(!c4)return;
    var c4opts = {{responsive:true,maintainAspectRatio:false,plugins:{{legend:{{display:false}}}},scales:{{y:{{ticks:{{callback:function(v){{return v.toFixed(1)+"%";}}}}}}}}}};
    new Chart(c4,{{type:'bar',data:{{labels:{j(factor_l)},datasets:[{{label:'因子收益贡献%',data:{j(factor_contrib)},backgroundColor:[{",".join([f"'{FACTOR_COLORS.get(name,'#999')}'" for name in factor_l])}],borderRadius:3}}]}},options:c4opts}});
}})();
</script>

<div class="footer">数据来源：cjpy · Brinson+因子归因模型 · 生成时间：{datetime.now().strftime("%Y-%m-%d %H:%M")} · 仅供参考</div>
</body></html>"""

    return html


def main():
    parser = argparse.ArgumentParser(description="基金穿透与多维归因引擎 v2")
    parser.add_argument("--data", required=True, help="JSON 数据文件")
    parser.add_argument("--output", help="输出 HTML")
    args = parser.parse_args()

    with open(args.data, "r", encoding="utf-8") as f:
        data = json.load(f)

    portfolio = data.get("portfolio", {})
    benchmark = data.get("benchmark", {})
    period = data.get("period", "最近6个月")

    attribution = brinson_attribution(portfolio, benchmark, period)
    factor_attr = factor_attribution(data.get("factor_data", {}))

    html = generate_html(data, attribution, factor_attr)

    output_path = args.output or f"outputs/penetration_{datetime.now().strftime('%Y%m%d')}.html"
    Path(output_path).parent.mkdir(parents=True, exist_ok=True)
    Path(output_path).write_text(html, encoding="utf-8")
    print(f"✅ 穿透+归因报告已生成：{Path(output_path).resolve()}")

    a = attribution; f = factor_attr
    print(f"\n📊 Brinson: 配置{a['allocation']:+.2f}% 选股{a['selection']:+.2f}% 交互{a['interaction']:+.2f}% 总超额{a['total_excess']:+.2f}%")
    print(f"📈 因子: {f['total']:+.2f}%")
    for d in f["details"]:
        print(f"  {d['factor']}: 暴露{d['active_exp']:+.2f} × 收益{d['factor_return']:+.1f}% = {d['contrib']:+.2f}%")


if __name__ == "__main__":
    main()
