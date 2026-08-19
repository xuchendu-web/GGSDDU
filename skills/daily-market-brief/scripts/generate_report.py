#!/usr/bin/env python3
"""
每日市场快报 HTML 生成器
输入：JSON 数据文件（行情 + 新闻）
输出：三栏结构化 HTML 日报
"""

import json
import sys
import argparse
from datetime import datetime
from pathlib import Path


def format_pct(val, digits=2):
    """格式化百分比"""
    if val is None:
        return "—"
    return f"{val:+.{digits}f}%"


def format_num(val, unit="亿", digits=0):
    """格式化数值"""
    if val is None:
        return "—"
    if isinstance(val, float) and unit == "亿":
        return f"{val:.{digits}f}"
    return f"{val:,}"


def color_class(val, is_pct=True):
    """根据涨跌返回 CSS class"""
    if val is None:
        return "neutral"
    if val > 0:
        return "up"
    elif val < 0:
        return "down"
    else:
        return "neutral"


def render_index_card(name, code, ret, price, volume, pe, pb):
    """渲染单个指数卡片"""
    cls = color_class(ret)
    arrow = "▲" if (ret or 0) > 0 else "▼" if (ret or 0) < 0 else "—"
    pct_str = format_pct(ret)
    price_str = format_num(price, unit="点", digits=2) if price else "—"
    vol_str = format_num(volume) if volume else "—"

    return f"""
    <div class="index-card {cls}">
        <div class="index-name">{name}</div>
        <div class="index-code">{code}</div>
        <div class="index-price">{price_str}</div>
        <div class="index-change {cls}">{arrow} {pct_str}</div>
        <div class="index-meta">
            <span>成交 {vol_str}亿</span>
        </div>
    </div>"""


def render_sentiment_gauge(avg_ret):
    """渲染情绪温度计"""
    if avg_ret is None:
        gauge_val = 50
        label = "数据缺失"
        emoji = "❓"
    elif avg_ret > 1.5:
        gauge_val = min(100, 50 + avg_ret * 12)
        label = "偏热"
        emoji = "🔥"
    elif avg_ret > 0.5:
        gauge_val = 50 + avg_ret * 20
        label = "偏暖"
        emoji = "☀️"
    elif avg_ret > -0.5:
        gauge_val = 50
        label = "中性"
        emoji = "⚖️"
    elif avg_ret > -1.5:
        gauge_val = 50 + avg_ret * 20
        label = "偏冷"
        emoji = "🌧️"
    else:
        gauge_val = max(0, 50 + avg_ret * 12)
        label = "冰点"
        emoji = "❄️"

    gauge_color = "#E60000" if gauge_val > 60 else "#009900" if gauge_val < 40 else "#999999"

    return f"""
    <div class="sentiment-gauge">
        <div class="gauge-label">市场情绪温度计 {emoji}</div>
        <div class="gauge-bar-bg">
            <div class="gauge-bar-fill" style="width:{gauge_val}%;background:{gauge_color}"></div>
        </div>
        <div class="gauge-value">{label} ({gauge_val:.0f}°)</div>
    </div>"""


def render_news_item(item):
    """渲染单条新闻，有 url 则标题可点击跳转"""
    impact_class = {"利好": "impact-positive", "利空": "impact-negative", "中性": "impact-neutral"}
    cls = impact_class.get(item.get("impact", "中性"), "impact-neutral")
    title = item.get("title", "")
    url = item.get("url", "")
    if url:
        title_html = f'<a href="{url}" target="_blank" class="news-link">{title}</a>'
    else:
        title_html = f'<span class="news-text">{title}</span>'
    return f"""
    <div class="news-item">
        <span class="impact-tag {cls}">{item.get("impact", "中性")}</span>
        {title_html}
    </div>"""


def json_escape(obj):
    """安全输出 JSON 到 HTML script 标签。仅转义 </script> 防止标签提前闭合"""
    return json.dumps(obj, ensure_ascii=False).replace("</script>", "<\\/script>")


def generate_html(data: dict) -> str:
    """生成完整 HTML 日报"""
    report_date = data.get("date", datetime.now().strftime("%Y-%m-%d"))
    indices_data = data.get("indices", {})
    market_stats = data.get("market_stats", {})
    news_items = data.get("news", [])
    overseas = data.get("overseas", [])
    volume_timeline = data.get("volume_timeline", [])
    pe_timeline = data.get("pe_timeline", [])
    sectors_top5 = data.get("sectors_top5", [])
    sectors_bottom5 = data.get("sectors_bottom5", [])
    fund_flow = data.get("fund_flow", {})
    sentiment = data.get("sentiment", {})
    capital_flow = data.get("capital_flow", {})
    liquidity = data.get("liquidity", {})
    inst_summary = data.get("institutional_summary", {})
    has_charts = bool(volume_timeline or pe_timeline)
    has_sectors = bool(sectors_top5 or sectors_bottom5)

    # 计算综合涨跌幅（六指数均值）
    rets = [indices_data.get(k, {}).get("日收益率") for k in ["上证指数","深证成指","创业板指","沪深300","上证50","科创50"]]
    rets = [r for r in rets if r is not None]
    avg_ret = sum(rets) / len(rets) if rets else None

    # 指数卡片
    index_cards = ""
    index_order = [
        ("上证指数", "SH000001"),
        ("深证成指", "SZ399001"),
        ("创业板指", "SZ399006"),
        ("沪深300", "SH000300"),
        ("上证50", "SH000016"),
        ("科创50", "SH000688"),
    ]
    for name, code in index_order:
        d = indices_data.get(name, {})
        index_cards += render_index_card(
            name, code,
            d.get("日收益率"),
            d.get("收盘价"),
            d.get("成交额"),
            d.get("指数PETTM"),
            d.get("指数PBMRQ"),
        )

    # 新闻列表
    news_html = "".join(render_news_item(n) for n in news_items[:8]) if news_items else '<div class="empty-hint">暂无新闻数据</div>'

    # 外围市场
    overseas_html = "".join(
        f'<div class="overseas-item {color_class(o.get("change"), False)}">{o.get("name","")}: {format_pct(o.get("change"))}</div>'
        for o in overseas
    ) if overseas else '<div class="empty-hint">暂无数据</div>'

    # 资金面 - 成交额
    sh_vol = market_stats.get("上证成交额", "—")
    sz_vol = market_stats.get("深证成交额", "—")
    total_vol = market_stats.get("两市成交额")
    vol_ratio = market_stats.get("量比")

    pe_data = indices_data.get("沪深300", {}).get("指数PETTM")
    pb_data = indices_data.get("沪深300", {}).get("指数PBMRQ")

    html = f"""<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>每日市场快报 — {report_date}</title>
<style>
* {{ margin:0; padding:0; box-sizing:border-box; }}
body {{
    font-family: -apple-system, BlinkMacSystemFont, "Microsoft YaHei", "PingFang SC", sans-serif;
    background: #f5f6fa;
    color: #2c3e50;
    padding: 20px;
}}
.header {{
    text-align: center;
    padding: 24px 0 16px;
    background: linear-gradient(135deg, #1a1a2e 0%, #16213e 100%);
    color: white;
    border-radius: 12px;
    margin-bottom: 20px;
}}
.header h1 {{ font-size: 28px; font-weight: 700; margin-bottom: 6px; }}
.header .date {{ font-size: 14px; opacity: 0.7; }}

.grid {{
    display: grid;
    grid-template-columns: 1fr 1fr 1fr;
    gap: 16px;
}}

.column {{
    background: white;
    border-radius: 12px;
    padding: 20px;
    box-shadow: 0 2px 12px rgba(0,0,0,0.06);
}}
.column-title {{
    font-size: 18px;
    font-weight: 700;
    margin-bottom: 16px;
    padding-bottom: 10px;
    border-bottom: 3px solid #eee;
    display: flex;
    align-items: center;
    gap: 8px;
}}
.column-title .icon {{ font-size: 22px; }}

/* 指数卡片 */
.index-grid {{
    display: grid;
    grid-template-columns: 1fr 1fr;
    gap: 10px;
    margin-bottom: 16px;
}}
.index-card {{
    background: #f8f9fc;
    border-radius: 8px;
    padding: 12px;
    text-align: center;
    border-left: 3px solid #ddd;
}}
.index-card.up {{ border-left-color: #E60000; }}
.index-card.down {{ border-left-color: #009900; }}
.index-name {{ font-size: 14px; font-weight: 600; }}
.index-code {{ font-size: 11px; color: #999; margin: 2px 0; }}
.index-price {{ font-size: 18px; font-weight: 700; margin: 4px 0; }}
.index-change {{ font-size: 16px; font-weight: 700; }}
.index-change.up {{ color: #E60000; }}
.index-change.down {{ color: #009900; }}
.index-change.neutral {{ color: #999999; }}
.index-meta {{ font-size: 11px; color: #999; margin-top: 4px; }}

/* 情绪温度计 */
.sentiment-gauge {{
    margin-top: 12px;
    padding: 12px;
    background: #f8f9fc;
    border-radius: 8px;
}}
.gauge-label {{ font-size: 14px; font-weight: 600; margin-bottom: 8px; }}
.gauge-bar-bg {{
    height: 12px;
    background: #e9ecef;
    border-radius: 6px;
    overflow: hidden;
}}
.gauge-bar-fill {{
    height: 100%;
    border-radius: 6px;
    transition: width 0.6s ease;
}}
.gauge-value {{ font-size: 13px; color: #666; margin-top: 6px; text-align: right; }}

/* 交易统计 */
.stats-grid {{
    display: grid;
    grid-template-columns: 1fr 1fr;
    gap: 10px;
    margin-top: 12px;
}}
.stat-item {{
    background: #f8f9fc;
    border-radius: 8px;
    padding: 12px;
    text-align: center;
}}
.stat-label {{ font-size: 12px; color: #999; }}
.stat-value {{ font-size: 20px; font-weight: 700; margin-top: 2px; }}
.stat-value.up {{ color: #E60000; }}
.stat-value.down {{ color: #009900; }}

/* 资金面 */
.fund-section {{
    margin-bottom: 16px;
}}
.fund-section h3 {{
    font-size: 15px;
    font-weight: 600;
    margin-bottom: 10px;
    color: #555;
}}
.fund-table {{
    width: 100%;
    border-collapse: collapse;
}}
.fund-table td {{
    padding: 8px 4px;
    border-bottom: 1px solid #f0f0f0;
    font-size: 13px;
}}
.fund-table td:first-child {{ color: #888; }}
.fund-table td:last-child {{ text-align: right; font-weight: 600; }}
.valuation-row {{
    display: flex;
    justify-content: space-between;
    padding: 8px 0;
    border-bottom: 1px solid #f0f0f0;
}}
.valuation-label {{ color: #888; font-size: 13px; }}
.valuation-value {{ font-weight: 700; font-size: 14px; }}

/* 新闻 */
.news-item {{
    padding: 10px 0;
    border-bottom: 1px solid #f0f0f0;
    display: flex;
    align-items: flex-start;
    gap: 8px;
}}
.news-item:last-child {{ border-bottom: none; }}
.news-text {{ font-size: 13px; line-height: 1.5; }}
.news-link {{
    font-size: 13px; line-height: 1.5; color: #2c3e50; text-decoration: none;
    border-bottom: 1px dotted #ccc;
}}
.news-link:hover {{ color: #1565c0; border-bottom-color: #1565c0; }}
.impact-tag {{
    font-size: 11px;
    padding: 2px 6px;
    border-radius: 4px;
    white-space: nowrap;
    font-weight: 600;
    flex-shrink: 0;
}}
.impact-positive {{ background: #fde8e8; color: #E60000; }}
.impact-negative {{ background: #e8f5e9; color: #009900; }}
.impact-neutral {{ background: #f0f0f0; color: #666; }}

/* 外围市场 */
.overseas-item {{
    padding: 6px 0;
    font-size: 13px;
    font-weight: 600;
}}
.overseas-item.up {{ color: #E60000; }}
.overseas-item.down {{ color: #009900; }}
.overseas-item.neutral {{ color: #999; }}

.empty-hint {{ color: #ccc; font-size: 13px; text-align: center; padding: 20px 0; }}

/* 底部 */
.footer {{
    text-align: center;
    color: #bbb;
    font-size: 12px;
    margin-top: 20px;
    padding: 10px;
}}

@media (max-width: 900px) {{
    .grid {{ grid-template-columns: 1fr; }}
    .index-grid {{ grid-template-columns: 1fr 1fr 1fr; }}
    .chart-row {{ grid-template-columns: 1fr; }}
    .sector-row {{ grid-template-columns: 1fr; }}
}}

/* 图表区域 */
.chart-row {{
    display: grid;
    grid-template-columns: 1fr 1fr;
    gap: 16px;
    margin-top: 16px;
}}
.chart-card {{
    background: white;
    border-radius: 12px;
    padding: 16px;
    box-shadow: 0 2px 12px rgba(0,0,0,0.06);
}}
.chart-card h3 {{
    font-size: 15px; font-weight: 600; margin-bottom: 12px;
    color: #444;
}}

/* 行业排行 */
.sector-row {{
    display: grid;
    grid-template-columns: 1fr 1fr;
    gap: 16px;
    margin-top: 16px;
}}
.sector-card {{
    background: white;
    border-radius: 12px;
    padding: 16px;
    box-shadow: 0 2px 12px rgba(0,0,0,0.06);
}}
.sector-card h3 {{ font-size: 15px; font-weight: 600; margin-bottom: 10px; }}
.sector-item {{
    display: flex; justify-content: space-between; align-items: center;
    padding: 7px 0; border-bottom: 1px solid #f5f5f5;
}}
.sector-item:last-child {{ border-bottom: none; }}
.sector-rank {{
    width: 24px; height: 24px; border-radius: 6px;
    display: flex; align-items: center; justify-content: center;
    font-size: 12px; font-weight: 700; margin-right: 8px;
    background: #f0f0f0; color: #666; flex-shrink: 0;
}}
.sector-rank.r1,.sector-rank.r2,.sector-rank.r3 {{ background: #E60000; color: #fff; }}
.sector-name {{ flex:1; font-size:13px; font-weight:500; }}
.sector-change {{ font-size:14px; font-weight:700; }}
</style>
<script src="https://cdn.jsdelivr.net/npm/chart.js@4.4.1/dist/chart.umd.min.js" crossorigin="anonymous"></script>
</head>
<body>

<div class="header">
    <h1>📊 每日市场快报</h1>
    <div class="date">{report_date}</div>
</div>

<div class="grid">

    <!-- ============ 左栏：市场情绪 ============ -->
    <div class="column">
        <div class="column-title"><span class="icon">🎯</span> 市场情绪</div>

        <div class="index-grid">
            {index_cards}
        </div>

        {render_sentiment_gauge(avg_ret)}

        <div class="stats-grid">
            <div class="stat-item">
                <div class="stat-label">两市成交额</div>
                <div class="stat-value">{format_num(total_vol)}亿</div>
            </div>
            <div class="stat-item">
                <div class="stat-label">量比（vs 5日均）</div>
                <div class="stat-value {color_class(vol_ratio-1 if vol_ratio else 0, False)}">{format_num(vol_ratio, unit="", digits=2)}</div>
            </div>
"""

    # 赚钱效应卡片
    ad_ratio = sentiment.get("涨跌家数比", "")
    zt = sentiment.get("涨停家数")
    dt = sentiment.get("跌停家数")
    zbl = sentiment.get("炸板率")
    market_type = sentiment.get("行情定性", "")
    money_effect = sentiment.get("赚钱效应", "")

    html += f"""
            <div class="stat-item">
                <div class="stat-label">涨跌家数</div>
                <div class="stat-value" style="font-size:16px;">{ad_ratio}</div>
            </div>
            <div class="stat-item">
                <div class="stat-label">涨跌停</div>
                <div class="stat-value"><span style="color:#E60000;">{zt}↑</span>/<span style="color:#009900;">{dt}↓</span></div>
            </div>
        </div>
        <div style="margin-top:10px;padding:8px 12px;background:#f8f9fc;border-radius:8px;font-size:13px;">
            <span style="color:#888;">赚钱效应：</span><b>{money_effect}</b>
            <span style="margin-left:12px;color:#888;">炸板率：</span><b>{zbl}%</b>
            <span style="margin-left:12px;color:#888;">行情定性：</span><b style="color:{'#E60000' if '普涨' in market_type else '#f57f17' if '分化' in market_type else '#009900'};">{market_type}</b>
        </div>
    </div>
"""
    pe_display = f"{pe_data}" if pe_data else "—"
    pb_display = f"{pb_data}" if pb_data else "—"
    html += f"""
    <!-- ============ 中栏：资金面 ============ -->
    <div class="column">
        <div class="column-title"><span class="icon">💰</span> 资金面</div>

        <div class="fund-section">
            <h3>📈 估值水位（沪深300）</h3>
            <div class="valuation-row">
                <span class="valuation-label">PETTM</span>
                <span class="valuation-value">{pe_display}</span>
            </div>
            <div class="valuation-row">
                <span class="valuation-label">PBMRQ</span>
                <span class="valuation-value">{pb_display}</span>
            </div>
        </div>
"""

    # 北向资金 + 流动性
    nb = capital_flow.get("北向净流入")
    nb_days = capital_flow.get("北向连续净流入天数", 0)
    ops = liquidity.get("央行操作", "")
    if nb is not None or ops:
        html += '<div class="fund-section"><h3>🏦 资金流向</h3>'
        if nb is not None:
            nbc = "#E60000" if nb > 0 else "#009900"
            html += f'<div class="valuation-row"><span class="valuation-label">北向资金</span><span class="valuation-value" style="color:{nbc};">{nb:+.1f}亿</span></div>'
        if ops:
            html += f'<div class="valuation-row"><span class="valuation-label">央行操作</span><span style="font-size:13px;color:#555;">{ops}</span></div>'
        html += '</div>'

    # 行业资金TOP
    flow_in = capital_flow.get("行业净流入TOP", [])
    flow_out = capital_flow.get("行业净流出TOP", [])
    if flow_in or flow_out:
        html += '<div class="fund-section"><h3>📊 行业资金TOP</h3>'
        html += '<table class="fund-table"><thead><tr><th>流入TOP</th><th>金额</th></tr></thead><tbody>'
        for f in flow_in[:3]:
            html += f'<tr><td>{f["name"]}</td><td style="color:#E60000;">+{f["amount"]}亿</td></tr>'
        html += '</tbody></table>'
        html += '<table class="fund-table" style="margin-top:4px;"><thead><tr><th>流出TOP</th><th>金额</th></tr></thead><tbody>'
        for f in flow_out[:3]:
            html += f'<tr><td>{f["name"]}</td><td style="color:#009900;">{f["amount"]}亿</td></tr>'
        html += '</tbody></table></div>'

    html += """
        <div class="fund-section">
            <h3>📊 指数换手率</h3>
            <table class="fund-table">
"""

    # 换手率表
    for name, _ in index_order:
        d = indices_data.get(name, {})
        hsl = d.get("换手率")
        if hsl is not None:
            html += f'<tr><td>{name}</td><td>{hsl:.2f}%</td></tr>\n'

    html += """
            </table>
        </div>

        <div class="fund-section">
            <h3>📋 资金面点评</h3>
            <div style="font-size:13px;line-height:1.6;color:#555;">
"""

    # 资金面自动点评
    if total_vol and total_vol > 10000:
        html += '<p>✅ 两市成交额超万亿，市场交投活跃。</p>'
    elif total_vol and total_vol > 8000:
        html += '<p>⚡ 两市成交额处于中等偏上水平。</p>'
    elif total_vol and total_vol > 5000:
        html += '<p>⚠️ 两市成交额偏低，市场观望情绪浓厚。</p>'
    else:
        html += '<p>📌 成交额数据待确认。</p>'

    if vol_ratio and vol_ratio > 1.2:
        html += '<p>📈 量能较前5日均值明显放大。</p>'
    elif vol_ratio and vol_ratio < 0.8:
        html += '<p>📉 量能较前5日均值明显萎缩。</p>'

    if pe_data and pe_data < 12:
        html += '<p>🟢 沪深300 PE处于历史偏低区间。</p>'
    elif pe_data and pe_data > 18:
        html += '<p>🔴 沪深300 PE处于历史偏高区间。</p>'
    else:
        html += '<p>🟡 沪深300 PE处于历史中位附近。</p>'

    html += """
            </div>
        </div>
    </div>

    <!-- ============ 右栏：事件面 ============ -->
    <div class="column">
        <div class="column-title"><span class="icon">📰</span> 事件面</div>

        <div class="fund-section">
            <h3>🔔 今日要闻</h3>
"""

    html += news_html

    html += """
        </div>

        <div class="fund-section" style="margin-top:16px;">
            <h3>🌍 外围市场</h3>
"""

    html += overseas_html

    html += f"""
        </div>

        <div class="fund-section" style="margin-top:16px;">
            <h3>📌 事件点评</h3>
            <div style="font-size:13px;line-height:1.6;color:#555;">
                <p>事件面数据基于当日新闻流自动整理，每条新闻标注影响方向（利好/利空/中性），辅助判断短期市场催化剂。</p>
            </div>
        </div>
    </div>

</div>

"""

    # ============= 图表行：成交额柱状图 + PE折线图 =============
    if has_charts:
        html += """
<div class="chart-row">
"""
        if volume_timeline:
            vol_labels = json_escape([v["date"] for v in volume_timeline])
            vol_data = json_escape([v["volume"] for v in volume_timeline])
            html += f"""
    <div class="chart-card">
        <h3>两市成交额（近半年日度）</h3>
        <div style="position:relative;width:100%;height:280px;">
            <canvas id="volChart"></canvas>
        </div>
    </div>
"""

        if pe_timeline:
            pe_labels = json_escape([p["date"] for p in pe_timeline])
            pe_values = json_escape([p["pe"] for p in pe_timeline])
            pb_values = json_escape([p["pb"] for p in pe_timeline])
            html += f"""
    <div class="chart-card">
        <h3>沪深300 估值走势（近半年）</h3>
        <div style="position:relative;width:100%;height:280px;">
            <canvas id="peChart"></canvas>
        </div>
    </div>
"""
        html += """
</div>
"""

    # ============= 行业排行行：涨幅前5 + 跌幅前5 =============
    if has_sectors:
        html += """
<div class="sector-row">
"""
        if sectors_top5:
            html += """
    <div class="sector-card">
        <h3 style="color:#E60000;">涨幅前5 中信三级行业</h3>
"""
            for i, s in enumerate(sectors_top5, 1):
                rc = f" r{i}" if i <= 3 else ""
                chg = s.get("change", 0)
                color = "#E60000" if chg > 0 else "#009900" if chg < 0 else "#999"
                html += f"""
        <div class="sector-item">
            <span class="sector-rank{rc}">{i}</span>
            <span class="sector-name">{s.get("name","")}</span>
            <span class="sector-change" style="color:{color}">{chg:+.2f}%</span>
        </div>"""
            html += """
    </div>
"""

        if sectors_bottom5:
            html += """
    <div class="sector-card">
        <h3 style="color:#009900;">跌幅前5 中信三级行业</h3>
"""
            for i, s in enumerate(sectors_bottom5, 1):
                rc = f" r{i}" if i <= 3 else ""
                chg = s.get("change", 0)
                color = "#E60000" if chg > 0 else "#009900" if chg < 0 else "#999"
                html += f"""
        <div class="sector-item">
            <span class="sector-rank{rc}">{i}</span>
            <span class="sector-name">{s.get("name","")}</span>
            <span class="sector-change" style="color:{color}">{chg:+.2f}%</span>
        </div>"""
            html += """
    </div>
"""
        html += """
</div>
"""

    # ============= 机构专属小结 =============
    if inst_summary:
        cl = inst_summary.get("core_logic", "")
        no = inst_summary.get("next_day_outlook", "")
        al = inst_summary.get("allocation", "")
        kr = inst_summary.get("key_risks", "")
        html += f"""
<div class="section" style="margin-top:16px;">
    <div class="section-title">🏛️ 机构专属小结</div>
    <div style="display:grid;grid-template-columns:1fr 1fr;gap:16px;">
        <div><div style="font-weight:600;color:#1565c0;margin-bottom:6px;">当日行情核心逻辑</div><div style="font-size:13px;line-height:1.7;">{cl}</div></div>
        <div><div style="font-weight:600;color:#f57f17;margin-bottom:6px;">次日走势判断</div><div style="font-size:13px;line-height:1.7;">{no}</div></div>
    </div>
    <div style="display:grid;grid-template-columns:1fr 1fr;gap:16px;margin-top:14px;padding-top:14px;border-top:1px solid #f0f0f0;">
        <div><div style="font-weight:600;color:#2e7d32;margin-bottom:6px;">配置参考</div><div style="font-size:13px;line-height:1.7;">{al}</div></div>
        <div><div style="font-weight:600;color:#c62828;margin-bottom:6px;">关键风险提示</div><div style="font-size:13px;line-height:1.7;">{kr}</div></div>
    </div>
</div>
"""

    html += f"""
<div class="footer">
    数据来源：cjpy · 生成时间：{datetime.now().strftime("%Y-%m-%d %H:%M")} · 仅供参考，不构成投资建议
</div>

"""

    # ============= Chart.js 渲染 =============
    if volume_timeline:
        html += f"""
<script>
(function(){{
    var ctx = document.getElementById('volChart');
    if(!ctx) return;
    new Chart(ctx, {{
        type: 'bar',
        data: {{
            labels: {vol_labels},
            datasets: [{{
                label: '成交额(亿)',
                data: {vol_data},
                backgroundColor: '#378add88',
                borderColor: '#378add',
                borderWidth: 0.5,
                borderRadius: 2,
                barPercentage: 0.95,
                categoryPercentage: 0.95
            }}]
        }},
        options: {{
            responsive: true, maintainAspectRatio: false,
            plugins: {{ legend: {{ display: false }} }},
            scales: {{
                x: {{ grid: {{ display: false }}, ticks: {{ maxTicksLimit: 8, font:{{size:10}} }} }},
                y: {{ grid: {{ color:'#f0f0f0' }}, ticks: {{ font:{{size:10}}, callback: function(v){{ return (v/10000).toFixed(1)+'万亿'; }} }} }}
            }}
        }}
    }});
}})();
</script>
"""

    if pe_timeline:
        html += f"""
<script>
(function(){{
    var ctx = document.getElementById('peChart');
    if(!ctx) return;
    new Chart(ctx, {{
        type: 'line',
        data: {{
            labels: {pe_labels},
            datasets: [
                {{
                    label: 'PETTM',
                    data: {pe_values},
                    borderColor: '#E60000',
                    backgroundColor: '#E6000015',
                    fill: false, tension: 0.3, pointRadius: 0, borderWidth: 2,
                    yAxisID: 'y'
                }},
                {{
                    label: 'PBMRQ',
                    data: {pb_values},
                    borderColor: '#1565c0',
                    backgroundColor: '#1565c015',
                    fill: false, tension: 0.3, pointRadius: 0, borderWidth: 2,
                    yAxisID: 'y1'
                }}
            ]
        }},
        options: {{
            responsive: true, maintainAspectRatio: false,
            plugins: {{ legend: {{ position:'top', labels:{{ usePointStyle:true, boxWidth:12, font:{{size:11}} }} }} }},
            scales: {{
                x: {{ grid: {{ display: false }}, ticks: {{ maxTicksLimit: 8, font:{{size:10}} }} }},
                y: {{
                    type:'linear', position:'left',
                    grid: {{ color:'#f0f0f0' }},
                    ticks: {{ font:{{size:10}}, callback: function(v){{ return v.toFixed(1); }} }},
                    title: {{ display:true, text:'PETTM', font:{{size:10}} }}
                }},
                y1: {{
                    type:'linear', position:'right',
                    grid: {{ drawOnChartArea:false }},
                    ticks: {{ font:{{size:10}}, callback: function(v){{ return v.toFixed(2); }} }},
                    title: {{ display:true, text:'PBMRQ', font:{{size:10}} }}
                }}
            }}
        }}
    }});
}})();
</script>
"""

    html += """
</body>
</html>"""

    return html


def main():
    parser = argparse.ArgumentParser(description="每日市场快报 HTML 生成器")
    parser.add_argument("--data", required=True, help="JSON 数据文件路径")
    parser.add_argument("--output", default=None, help="输出 HTML 文件路径")
    args = parser.parse_args()

    data_path = Path(args.data)
    if not data_path.exists():
        print(f"错误：数据文件不存在 {data_path}", file=sys.stderr)
        sys.exit(1)

    with open(data_path, "r", encoding="utf-8") as f:
        data = json.load(f)

    html = generate_html(data)

    # 确定输出路径
    if args.output:
        output_path = Path(args.output)
    else:
        report_date = data.get("date", datetime.now().strftime("%Y%m%d"))
        output_path = Path(f"daily_brief_{report_date}.html")

    output_path.parent.mkdir(parents=True, exist_ok=True)
    with open(output_path, "w", encoding="utf-8") as f:
        f.write(html)

    print(f"✅ 日报已生成：{output_path.resolve()}")


if __name__ == "__main__":
    main()
