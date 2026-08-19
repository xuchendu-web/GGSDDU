#!/usr/bin/env python3
"""
事件驱动型个股复盘 — 三元归因引擎 + HTML 报告生成器
"""

import json
import sys
import argparse
import math
from datetime import datetime, timedelta
from pathlib import Path


def calc_beta(stock_returns, market_returns):
    """计算 Beta = Cov(stock, market) / Var(market)"""
    if len(stock_returns) < 10 or len(market_returns) < 10:
        return 1.0
    pairs = [(s, m) for s, m in zip(stock_returns, market_returns) if s is not None and m is not None]
    if len(pairs) < 10:
        return 1.0
    n = len(pairs)
    mean_s = sum(s for s, _ in pairs) / n
    mean_m = sum(m for _, m in pairs) / n
    cov = sum((s - mean_s) * (m - mean_m) for s, m in pairs) / (n - 1)
    var_m = sum((m - mean_m) ** 2 for m, _ in pairs) / (n - 1)
    if var_m == 0:
        return 1.0
    return round(cov / var_m, 3)


def daily_return(close_today, close_yesterday):
    """日收益率"""
    if close_yesterday and close_yesterday != 0:
        return (close_today - close_yesterday) / close_yesterday
    return None


def decompose(data: dict) -> dict:
    """执行三元归因拆解"""
    stock_prices = data.get("stock_prices", [])
    market_prices = data.get("market_prices", [])
    sector_return = data.get("sector_return", 0)
    stock_beta = data.get("beta", 1.0)
    pre_window = data.get("pre_window", 3)
    post_window = data.get("post_window", 5)
    event_date = data.get("event_date", "")

    if len(stock_prices) < 2:
        return {"error": "数据不足"}

    # 计算窗口总涨跌幅
    first_price = stock_prices[0].get("close", 0)
    last_price = stock_prices[-1].get("close", 0)
    if first_price and first_price > 0:
        total_return = (last_price - first_price) / first_price * 100
    else:
        total_return = 0

    # 大盘贡献
    if market_prices and len(market_prices) >= 2:
        mkt_first = market_prices[0].get("close", 0)
        mkt_last = market_prices[-1].get("close", 0)
        if mkt_first and mkt_first > 0:
            market_return = (mkt_last - mkt_first) / mkt_first * 100
        else:
            market_return = 0
    else:
        market_return = 0

    market_contrib = stock_beta * market_return

    # 行业贡献
    sector_contrib = sector_return if sector_return else 0

    # Alpha
    alpha = round(total_return - market_contrib - sector_contrib, 2)

    # 每日拆解
    daily_breakdown = []
    for i, sp in enumerate(stock_prices[1:], 1):
        prev_sp = stock_prices[i - 1]
        date_str = sp.get("date", "")
        stk_ret = daily_return(sp.get("close", 0), prev_sp.get("close", 0))
        stk_ret_pct = stk_ret * 100 if stk_ret else 0

        if i <= len(market_prices) - 1 and len(market_prices) > 1:
            prev_mp = market_prices[i - 1] if i - 1 < len(market_prices) else market_prices[0]
            mp = market_prices[i] if i < len(market_prices) else market_prices[-1]
            mkt_ret = daily_return(mp.get("close", 0), prev_mp.get("close", 0))
            mkt_ret_pct = (mkt_ret or 0) * 100
        else:
            mkt_ret_pct = 0

        mkt_daily = round(stock_beta * mkt_ret_pct, 2)
        sec_daily = round(sector_contrib / (len(stock_prices) - 1), 2) if len(stock_prices) > 1 else 0
        alpha_daily = round(stk_ret_pct - mkt_daily - sec_daily, 2)

        daily_breakdown.append({
            "date": date_str,
            "stock": round(stk_ret_pct, 2),
            "market": mkt_daily,
            "sector": sec_daily,
            "alpha": alpha_daily,
        })

    # 成交量分析
    volumes = [sp.get("volume", 0) for sp in stock_prices if sp.get("volume")]
    avg_vol = sum(volumes) / len(volumes) if volumes else 0
    baseline_vol = data.get("baseline_volume", avg_vol)
    vol_ratio = round(avg_vol / baseline_vol, 2) if baseline_vol > 0 else 1.0

    if vol_ratio >= 1.5:
        vol_anomaly = "放量"
    elif vol_ratio <= 0.5:
        vol_anomaly = "缩量"
    else:
        vol_anomaly = "正常"

    return {
        "total_return": round(total_return, 2),
        "market_return": round(market_return, 2),
        "sector_return": round(sector_contrib, 2),
        "market_contrib": round(market_contrib, 2),
        "sector_contrib": round(sector_contrib, 2),
        "alpha": alpha,
        "beta": stock_beta,
        "vol_ratio": vol_ratio,
        "vol_anomaly": vol_anomaly,
        "avg_vol": round(avg_vol, 2),
        "baseline_vol": round(baseline_vol, 2),
        "daily_breakdown": daily_breakdown,
    }


def generate_html(data: dict, result: dict) -> str:
    """生成 HTML 复盘报告"""
    code = data.get("code", "")
    name = data.get("name", code)
    event = data.get("event", "")
    event_date = data.get("event_date", "")
    pre = data.get("pre_window", 3)
    post = data.get("post_window", 5)

    total = result.get("total_return", 0)
    mkt_c = result.get("market_contrib", 0)
    sec_c = result.get("sector_contrib", 0)
    alpha = result.get("alpha", 0)
    beta = result.get("beta", 1.0)
    vol_ratio = result.get("vol_ratio", 1.0)
    vol_anomaly = result.get("vol_anomaly", "正常")

    # 颜色
    color_up = "#E60000"
    color_down = "#009900"
    color_flat = "#999999"
    total_color = color_up if total > 0 else color_down if total < 0 else color_flat

    # 归因数据
    contribs = [
        ("大盘贡献 (Beta)", mkt_c, "#1565c0"),
        ("行业联动 (Sector)", sec_c, "#f57f17"),
        ("个股Alpha", alpha, "#2e7d32" if alpha > 0 else "#c62828"),
    ]

    # 饼图数据
    pie_abs = [abs(mkt_c), abs(sec_c), abs(alpha)]
    pie_sum = sum(pie_abs)
    pie_pcts = [round(x / pie_sum * 100, 1) if pie_sum > 0 else 33 for x in pie_abs]

    # 新闻事件
    events = data.get("events", [])
    announcements = data.get("announcements", [])

    events_html = ""
    for ev in events[:6]:
        events_html += f"""
        <div class="event-row">
            <div class="event-time">{ev.get('time','')}</div>
            <div class="event-desc">{ev.get('title','')}</div>
            <div class="event-src">{ev.get('source','')}</div>
        </div>"""

    ann_html = ""
    for a in announcements[:5]:
        ann_html += f"""
        <div class="event-row">
            <div class="event-time">{a.get('date','')}</div>
            <div class="event-desc">{a.get('title','')}</div>
            <div class="event-src">cjpy公告</div>
        </div>"""

    # 每日拆解表
    daily_rows = ""
    for d in result.get("daily_breakdown", []):
        sc = color_up if d["stock"] > 0 else color_down if d["stock"] < 0 else color_flat
        ac = color_up if d["alpha"] > 0 else color_down if d["alpha"] < 0 else color_flat
        daily_rows += f"""
        <tr>
            <td>{d['date']}</td>
            <td style="color:{sc};font-weight:700;">{d['stock']:+.2f}%</td>
            <td>{d['market']:+.2f}%</td>
            <td>{d['sector']:+.2f}%</td>
            <td style="color:{ac};font-weight:700;">{d['alpha']:+.2f}%</td>
        </tr>"""

    html = f"""<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>个股复盘 — {name} {event_date}</title>
<style>
* {{ margin:0; padding:0; box-sizing:border-box; }}
body {{
    font-family: -apple-system, BlinkMacSystemFont, "Microsoft YaHei", sans-serif;
    background: #f5f6fa; color: #2c3e50; padding: 20px;
}}
.header {{
    text-align: center; padding: 24px 0 16px;
    background: linear-gradient(135deg, #263238 0%, #37474f 100%);
    color: white; border-radius: 12px; margin-bottom: 20px;
}}
.header h1 {{ font-size: 26px; font-weight: 700; margin-bottom: 4px; }}
.header .sub {{ font-size: 13px; opacity: 0.7; }}

.summary-cards {{ display:flex; gap:12px; margin-bottom:20px; flex-wrap:wrap; }}
.card {{
    flex:1; min-width:180px; background:white; border-radius:10px;
    padding:16px; box-shadow:0 2px 8px rgba(0,0,0,0.05);
}}
.card-label {{ font-size:12px; color:#999; margin-bottom:6px; }}
.card-value {{ font-size:26px; font-weight:700; }}
.card-sub {{ font-size:12px; color:#999; margin-top:4px; }}

.section {{
    background:white; border-radius:12px; padding:20px;
    box-shadow:0 2px 8px rgba(0,0,0,0.05); margin-bottom:16px;
}}
.section-title {{
    font-size:16px; font-weight:700; margin-bottom:16px;
    padding-bottom:8px; border-bottom:2px solid #f0f0f0;
}}

.attribution {{ display:flex; gap:16px; align-items:center; }}
.pie-container {{ width:160px; height:160px; flex-shrink:0; }}
.attribution-detail {{ flex:1; }}
.attr-row {{
    display:flex; justify-content:space-between; padding:6px 0;
    border-bottom:1px solid #f0f0f0; font-size:14px;
}}

table {{ width:100%; border-collapse:collapse; font-size:13px; }}
th {{ background:#f5f5f5; padding:8px; text-align:center; font-weight:600; }}
td {{ padding:8px; text-align:center; border-bottom:1px solid #f0f0f0; }}

.event-row {{
    display:flex; gap:12px; padding:8px 0; border-bottom:1px solid #f0f0f0;
    font-size:13px; align-items:baseline;
}}
.event-time {{ color:#999; white-space:nowrap; min-width:70px; }}
.event-desc {{ flex:1; }}
.event-src {{ color:#bbb; font-size:11px; white-space:nowrap; }}

.conclusion {{
    background:#e8f5e9; border-radius:10px; padding:16px; margin-top:12px;
    font-size:14px; line-height:1.6;
}}
.conclusion.down {{ background:#fce4ec; }}

.footer {{ text-align:center; color:#bbb; font-size:12px; margin-top:20px; padding:10px; }}
</style>
</head>
<body>

<div class="header">
    <h1>🔍 个股事件复盘</h1>
    <div class="sub">{name}（{code}）· 事件窗口：T-{pre} ~ T+{post} · {event_date}</div>
</div>

<div class="summary-cards">
    <div class="card">
        <div class="card-label">窗口涨跌幅</div>
        <div class="card-value" style="color:{total_color};">{total:+.2f}%</div>
        <div class="card-sub">事件：{event}</div>
    </div>
    <div class="card">
        <div class="card-label">个股Alpha</div>
        <div class="card-value" style="color:{'#E60000' if alpha>0 else '#009900' if alpha<0 else '#999'};">{alpha:+.2f}%</div>
        <div class="card-sub">Beta = {beta}</div>
    </div>
    <div class="card">
        <div class="card-label">成交量</div>
        <div class="card-value" style="color:{'#E60000' if vol_anomaly=='放量' else '#1565c0' if vol_anomaly=='缩量' else '#999'};">{vol_ratio}x</div>
        <div class="card-sub">{vol_anomaly}</div>
    </div>
    <div class="card">
        <div class="card-label">大盘同期</div>
        <div class="card-value" style="color:{'#E60000' if mkt_c>0 else '#009900' if mkt_c<0 else '#999'};">{mkt_c:+.2f}%</div>
        <div class="card-sub">沪深300贡献</div>
    </div>
</div>

<div class="section">
    <div class="section-title">📊 涨跌归因拆解</div>
    <div class="attribution">
        <div class="pie-container">
            <canvas id="pieCanvas" role="img" aria-label="涨跌归因饼图"></canvas>
        </div>
        <div class="attribution-detail">
"""

    for label, val, c in contribs:
        pct = round(abs(val) / (abs(mkt_c) + abs(sec_c) + abs(alpha)) * 100, 1) if (abs(mkt_c) + abs(sec_c) + abs(alpha)) > 0 else 33
        html += f"""
            <div class="attr-row">
                <span style="color:{c};font-weight:600;">{label}</span>
                <span style="color:{c};font-weight:700;">{val:+.2f}% ({pct}%)</span>
            </div>"""

    html += """
        </div>
    </div>
</div>

<div class="section">
    <div class="section-title">📈 每日拆解明细</div>
    <table>
        <thead>
            <tr><th>日期</th><th>个股涨跌</th><th>大盘贡献</th><th>行业贡献</th><th>Alpha</th></tr>
        </thead>
        <tbody>""" + daily_rows + """</tbody>
    </table>
</div>

<div class="section">
    <div class="section-title">📰 事件与新闻</div>
    <div style="margin-bottom:12px;font-size:13px;font-weight:600;color:#1565c0;">新闻事件</div>
""" + (events_html or '<div style="color:#ccc;font-size:13px;">暂无匹配新闻</div>') + f"""
    <div style="margin:12px 0;font-size:13px;font-weight:600;color:#f57f17;">cjpy 公告</div>
""" + (ann_html or '<div style="color:#ccc;font-size:13px;">窗口内无公告</div>') + """
</div>

<div class="section">
    <div class="section-title">📋 复盘总结</div>
"""

    if alpha > 1:
        summary = f"窗口内个股累计<b style='color:{color_up};'>{total:+.2f}%</b>，其中Alpha贡献<b>{alpha:+.2f}%</b>，个股存在显著独立正面驱动，跑赢大盘和行业。"
    elif alpha < -1:
        summary = f"窗口内个股累计<b style='color:{color_down};'>{total:+.2f}%</b>，其中Alpha拖累<b>{alpha:+.2f}%</b>，个股存在独立负面因素，显著跑输大盘和行业。"
    else:
        summary = f"窗口内个股累计<b>{total:+.2f}%</b>，涨跌主要由大盘和行业联动解释，Alpha仅<b>{alpha:+.2f}%</b>，个股独立驱动不显著。"

    if vol_ratio > 1.5:
        summary += f" 成交量放大<b>{vol_ratio}x</b>，资金博弈激烈。"
    elif vol_ratio < 0.5:
        summary += f" 成交量萎缩至<b>{vol_ratio}x</b>，市场关注度低。"

    html += f"""<div class="conclusion{' down' if total < 0 else ''}">{summary}</div>
</div>

<div class="footer">
    数据来源：cjpy · WebSearch · 生成时间：{datetime.now().strftime("%Y-%m-%d %H:%M")} · 仅供参考
</div>

<script src="https://cdnjs.cloudflare.com/ajax/libs/Chart.js/4.4.1/chart.umd.js"></script>
<script>
new Chart(document.getElementById('pieCanvas'), {{
    type: 'doughnut',
    data: {{
        labels: ['大盘贡献','行业联动','个股Alpha'],
        datasets: [{{ data: [{pie_pcts[0]},{pie_pcts[1]},{pie_pcts[2]}], backgroundColor: ['#1565c0','#f57f17','{"#2e7d32" if alpha>0 else "#c62828"}'] }}]
    }},
    options: {{
        responsive: true, maintainAspectRatio: true,
        plugins: {{ legend: {{ display: false }} }},
        cutout: '55%'
    }}
}});
</script>

</body>
</html>"""

    return html


def main():
    parser = argparse.ArgumentParser(description="事件驱动型个股复盘引擎")
    parser.add_argument("--data", help="JSON 数据文件路径")
    parser.add_argument("--output", help="输出 HTML 路径")
    parser.add_argument("--code", help="股票代码")
    parser.add_argument("--event", default="事件驱动", help="触发事件描述")
    parser.add_argument("--event_date", help="事件日期")
    parser.add_argument("--pre", type=int, default=3, help="事件前窗口天数")
    parser.add_argument("--post", type=int, default=5, help="事件后窗口天数")
    args = parser.parse_args()

    if args.data:
        data_path = Path(args.data)
        with open(data_path, "r", encoding="utf-8") as f:
            data = json.load(f)
    else:
        print("请提供 --data 参数指定 JSON 数据文件")
        sys.exit(1)

    # 补充命令行参数
    if args.code:
        data["code"] = args.code
    if args.event_date:
        data["event_date"] = args.event_date
    data["event"] = data.get("event") or args.event
    data["pre_window"] = data.get("pre_window") or args.pre
    data["post_window"] = data.get("post_window") or args.post

    result = decompose(data)
    html = generate_html(data, result)

    output_path = args.output or f"outputs/review_{data.get('code','stock')}_{data.get('event_date','')}.html"
    Path(output_path).parent.mkdir(parents=True, exist_ok=True)
    Path(output_path).write_text(html, encoding="utf-8")
    print(f"✅ 个股复盘报告已生成：{Path(output_path).resolve()}")

    # 打印摘要
    print(f"\n📊 归因摘要：")
    print(f"  总涨跌: {result.get('total_return',0):+.2f}%")
    print(f"  大盘贡献: {result.get('market_contrib',0):+.2f}%")
    print(f"  行业贡献: {result.get('sector_contrib',0):+.2f}%")
    print(f"  个股Alpha: {result.get('alpha',0):+.2f}%")
    print(f"  量比: {result.get('vol_ratio',1)}x ({result.get('vol_anomaly','正常')})")


if __name__ == "__main__":
    main()
