#!/usr/bin/env python3
"""
基金筛选与互补匹配引擎 v2
六维评分 + 收益率走势图 + 相关性矩阵 → HTML 推荐报告
"""

import json, sys, argparse
from datetime import datetime
from pathlib import Path

DIMENSIONS = [
    {"key":"style","name":"风格匹配","weight":25,"desc":"成长/价值/均衡风格吻合度"},
    {"key":"sector","name":"行业匹配","weight":25,"desc":"目标行业暴露度"},
    {"key":"perf","name":"业绩匹配","weight":15,"desc":"近期收益与风险指标"},
    {"key":"size","name":"规模适配","weight":10,"desc":"基金规模与流动性"},
    {"key":"overlap","name":"重叠控制","weight":10,"desc":"与现有组合持仓差异度"},
    {"key":"complement","name":"互补性","weight":15,"desc":"低重叠+低相关=高互补"},
]

CORR_COLORS = ["#1565c0","#5c6bc0","#9fa8da","#EF9A9A","#E57373","#E53935","#C62828","#B71C1C"]


def generate_html(need, candidates, existing=None, timelines=None, corr_matrix=None) -> str:
    dt = datetime.now().strftime("%Y-%m-%d %H:%M")
    n = len(candidates)

    def j(o): return json.dumps(o, ensure_ascii=False).replace("</", "<\\/")

    # Summary cards
    cards = f"""
    <div class="card"><div class="card-label">需求</div><div class="card-value" style="font-size:15px;color:#1565c0;">{need.get('desc','')[:18]}</div></div>
    <div class="card"><div class="card-label">候选池</div><div class="card-value" style="color:#2e7d32;">{n}只</div></div>"""
    if existing:
        cards += f"""<div class="card"><div class="card-label">现有组合</div><div class="card-value" style="font-size:14px;color:#f57f17;">{len(existing)}只</div></div>"""

    # Candidate rows
    rows = ""
    for rank, cand in enumerate(sorted(candidates, key=lambda x: -x.get("total_score", 0)), 1):
        name = cand.get("name",""); code = cand.get("code","")
        score = cand.get("total_score",50); dims = cand.get("dims",{})
        reason = cand.get("reason",""); risk = cand.get("risk","")
        sc = "#2e7d32" if score>=75 else "#f57f17" if score>=60 else "#c62828"
        dim_cells = ""
        for d in DIMENSIONS:
            v = dims.get(d["key"],3)
            dc = "#4caf50" if v>=4 else "#ff9800" if v>=2.5 else "#f44336"
            stars = "★"*int(v)+("☆" if v%1>=0.5 else "")
            dim_cells += f'<td style="text-align:center;color:{dc};font-weight:600;">{stars} {v:.1f}</td>'
        rows += f"""<tr>
            <td style="font-weight:700;text-align:center;">{rank}</td>
            <td><b>{name}</b><br><span style="font-size:11px;color:#999;">{code}</span></td>
            <td style="text-align:center;font-weight:800;font-size:18px;color:{sc};">{score:.0f}</td>
            {dim_cells}
            <td style="font-size:12px;">{reason}</td>
            <td style="font-size:11px;color:#999;">{risk}</td></tr>"""

    # ==== 收益率走势图数据 ====
    chart_names = []
    chart_labels = []
    chart_datasets = []
    if timelines:
        # Collect all dates
        all_dates = set()
        for k, series in timelines.items():
            for pt in series:
                all_dates.add(pt.get("date",""))
        sorted_dates = sorted(all_dates)
        # Only show dates every ~N points to avoid overcrowding
        step = max(1, len(sorted_dates)//15)
        chart_labels = [d for i,d in enumerate(sorted_dates) if i%step==0 or i==len(sorted_dates)-1]

        colors = ["#1565c0","#c62828","#2e7d32","#f57f17","#6a1b9a","#00838f","#e65100","#283593","#00695c"]
        ci = 0
        for name, series in timelines.items():
            date_map = {pt.get("date",""): pt.get("value",0) for pt in series}
            # Use ALL dates from sorted_dates as labels (Chart.js handles dense x-axis with autoSkip)
            chart_labels = [d for i, d in enumerate(sorted_dates) if i % step == 0]
            vals = [date_map.get(d, None) for d in chart_labels]
            # Fill any None gaps
            for i in range(len(vals)):
                if vals[i] is None:
                    vals[i] = vals[i-1] if i > 0 else 0
            chart_datasets.append({
                "label": name[:20],
                "data": [round(v, 1) if v is not None else 0 for v in vals],
                "borderColor": colors[ci%len(colors)],
                "backgroundColor": colors[ci%len(colors)]+"20",
                "tension": 0.2, "pointRadius": 0, "borderWidth": 1.5
            })
            ci += 1

    # ==== 相关性矩阵 ====
    corr_html = ""
    if corr_matrix:
        names = corr_matrix.get("labels", [])
        mat = corr_matrix.get("matrix", [])
        if names and mat:
            corr_html = '<div class="section"><div class="section-title">📈 收益率相关性矩阵</div>'
            corr_html += '<table class="corr-table"><thead><tr><th></th>'
            for n in names:
                corr_html += f'<th>{n[:12]}</th>'
            corr_html += '</tr></thead><tbody>'
            for ri, rname in enumerate(names):
                corr_html += f'<tr><td style="font-weight:600;">{rname[:12]}</td>'
                for ci_val in range(len(names)):
                    if ri < len(mat) and ci_val < len(mat[ri]):
                        v = mat[ri][ci_val]
                        # Color scale: 1.0=dark red, 0=white, -1=dark blue
                        if v >= 0:
                            intensity = int(255*(1-v))
                            bg = f"rgb(255,{intensity},{intensity})"
                            tc = "#fff" if v > 0.7 else "#333"
                        else:
                            av = abs(v)
                            intensity = int(255*(1-av))
                            bg = f"rgb({intensity},{intensity},255)"
                            tc = "#fff" if av > 0.7 else "#333"
                        corr_html += f'<td style="text-align:center;background:{bg};color:{tc};font-weight:600;">{v:.2f}</td>'
                    else:
                        corr_html += '<td></td>'
                corr_html += '</tr>'
            corr_html += '</tbody></table>'
            corr_html += '<div style="font-size:11px;color:#999;margin-top:4px;">红色=正相关，蓝色=负相关。越低越好（说明候选与现有组合走势不趋同）。</div></div>'

    # Complementarity section
    comp_html = ""
    if existing:
        comp_html = '<div class="section"><div class="section-title">🔗 互补性对比</div>'
        comp_html += '<table><thead><tr><th>候选基金</th><th>vs 现有 重叠率</th><th>风格差异</th><th>行业差异</th><th>互补得分</th></tr></thead><tbody>'
        for cand in sorted(candidates, key=lambda x: -x.get("total_score", 0))[:8]:
            name=cand.get("name",""); overlap=cand.get("overlap_pct",50)
            sd=cand.get("style_diff",3); scd=cand.get("sector_diff",3)
            cs=cand.get("dims",{}).get("complement",3)
            oc="#2e7d32" if overlap<30 else "#f57f17" if overlap<60 else "#c62828"
            cc="#2e7d32" if cs>=4 else "#f57f17" if cs>=2.5 else "#c62828"
            comp_html += f'<tr><td style="font-weight:600;">{name}</td><td style="text-align:center;color:{oc};font-weight:700;">{overlap:.0f}%</td><td style="text-align:center;">{"高" if sd>=4 else "中" if sd>=2.5 else "低"}</td><td style="text-align:center;">{"高" if scd>=4 else "中" if scd>=2.5 else "低"}</td><td style="text-align:center;color:{cc};font-weight:700;">{cs:.1f}/5</td></tr>'
        comp_html += '</tbody></table></div>'

    html = f"""<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="UTF-8"><meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>基金筛选推荐 — {dt}</title>
<script src="https://cdnjs.cloudflare.com/ajax/libs/Chart.js/4.4.1/chart.umd.js"></script>
<style>
*{{margin:0;padding:0;box-sizing:border-box}}
body{{font-family:-apple-system,BlinkMacSystemFont,"Microsoft YaHei",sans-serif;background:#f5f6fa;color:#2c3e50;padding:20px}}
.header{{text-align:center;padding:24px 0 16px;background:linear-gradient(135deg,#0d47a1,#1565c0);color:#fff;border-radius:12px;margin-bottom:20px}}
.header h1{{font-size:26px;font-weight:700}}.header .sub{{font-size:13px;opacity:.7;margin-top:4px}}
.cards{{display:flex;gap:10px;margin-bottom:20px;flex-wrap:wrap}}
.card{{flex:1;min-width:130px;background:#fff;border-radius:10px;padding:14px;text-align:center;box-shadow:0 2px 8px rgba(0,0,0,0.05)}}
.card-label{{font-size:12px;color:#999}}.card-value{{font-size:24px;font-weight:700;margin:4px 0}}
.section{{background:#fff;border-radius:12px;padding:20px;box-shadow:0 2px 8px rgba(0,0,0,0.05);margin-bottom:16px}}
.section-title{{font-size:16px;font-weight:700;margin-bottom:16px;border-bottom:2px solid #f0f0f0;padding-bottom:8px}}
table{{width:100%;border-collapse:collapse;font-size:13px}}
th{{background:#f5f5f5;padding:8px 6px;text-align:left;font-weight:600;white-space:nowrap}}
td{{padding:7px 6px;border-bottom:1px solid #f0f0f0;vertical-align:top}}
.corr-table td, .corr-table th{{padding:10px 8px;text-align:center;min-width:50px}}
.footer{{text-align:center;color:#bbb;font-size:12px;margin-top:20px;padding:10px}}
.need-tags{{display:flex;gap:8px;flex-wrap:wrap;margin-bottom:12px}}
.tag{{padding:4px 12px;border-radius:20px;font-size:12px;font-weight:600;background:#e3f2fd;color:#1565c0}}
@media(max-width:800px){{.cards{{flex-direction:column}}}}
</style></head><body>
<div class="header"><h1>🔍 基金筛选与互补匹配</h1><div class="sub">{need.get('desc','')} · {dt}</div></div>
<div class="cards">{cards}</div>

<div class="section">
    <div class="section-title">🏷️ 需求画像</div>
    <div class="need-tags">
        <span class="tag">{need.get('sector','不限行业')}</span>
        <span class="tag">{need.get('style','不限风格')}</span>
        <span class="tag">规模 {need.get('size_range','不限')}</span>
        <span class="tag">互补优先 {need.get('complement_priority','否')}</span>
    </div>
</div>

<div class="section">
    <div class="section-title">📊 候选基金排行（六维打分）</div>
    <table><thead><tr>
        <th>#</th><th>基金</th><th>总分</th>
        {"".join(f'<th style="text-align:center;">{d["name"]}<br><span style="font-weight:400;font-size:10px;color:#999;">{d["weight"]}%</span></th>' for d in DIMENSIONS)}
        <th>推荐理由</th><th>风险</th></tr></thead>
    <tbody>{rows}</tbody></table>
</div>

{"<div class='section'><div class='section-title'>📈 收益率走势对比（近半年累计）</div><div style='position:relative;height:360px'><canvas id='returnChart' role='img' aria-label='收益率走势'></canvas></div></div>" if chart_datasets else ""}

{corr_html}
{comp_html}

<div class="footer">数据来源：cjpy · 六维匹配模型 v2 · 生成时间：{dt} · 仅供参考，不构成投资建议</div>
"""

    if chart_datasets:
        html += f"""
<script>
(function(){{
    var ctx=document.getElementById('returnChart'); if(!ctx)return;
    new Chart(ctx,{{
        type:'line',
        data:{{labels:{j(chart_labels)},datasets:{j(chart_datasets)}}},
        options:{{responsive:true,maintainAspectRatio:false,
        plugins:{{legend:{{position:'top',labels:{{usePointStyle:true,boxWidth:10,font:{{size:11}}}}}}}},
        scales:{{x:{{grid:{{display:false}},ticks:{{maxTicksLimit:10,font:{{size:10}}}}}},y:{{grid:{{color:'#f0f0f0'}},ticks:{{font:{{size:10}},callback:function(v){{return v.toFixed(1)+'%';}}}}}}}}}}
    }});
}})();
</script>"""

    html += "</body></html>"
    return html


def main():
    parser = argparse.ArgumentParser(description="基金筛选推荐引擎 v2")
    parser.add_argument("--data", required=True)
    parser.add_argument("--output")
    args = parser.parse_args()

    with open(args.data, "r", encoding="utf-8") as f:
        data = json.load(f)

    need = data.get("need", {})
    candidates = data.get("candidates", [])
    existing = data.get("existing")
    timelines = data.get("return_timelines")
    corr_matrix = data.get("correlation_matrix")

    html = generate_html(need, candidates, existing, timelines, corr_matrix)

    output_path = args.output or f"outputs/fund_matcher_{datetime.now().strftime('%Y%m%d_%H%M')}.html"
    Path(output_path).parent.mkdir(parents=True, exist_ok=True)
    Path(output_path).write_text(html, encoding="utf-8")
    print(f"✅ 推荐报告已生成：{Path(output_path).resolve()}")

    top3 = sorted(candidates, key=lambda x: -x.get("total_score", 0))[:3]
    print(f"\n📊 TOP3 推荐：")
    for i, c in enumerate(top3, 1):
        print(f"  {i}. {c.get('name','')} ({c.get('code','')}) — 总分{c.get('total_score',0):.0f} — {c.get('reason','')}")


if __name__ == "__main__":
    main()
