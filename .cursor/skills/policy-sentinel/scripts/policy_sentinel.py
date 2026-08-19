#!/usr/bin/env python3
"""
政策与舆情雷达 — 分级预警引擎 + HTML 日报生成器
"""

import json
import sys
import argparse
from datetime import datetime
from pathlib import Path

# 预警分级与配色
ALERT_LEVELS = {
    "red":    {"label": "🔴 红色预警", "css": "#c62828", "bg": "#fce4ec", "desc": "重大利空"},
    "orange": {"label": "🟠 橙色预警", "css": "#e65100", "bg": "#fff3e0", "desc": "显著负面"},
    "yellow": {"label": "🟡 黄色关注", "css": "#f57f17", "bg": "#fff8e1", "desc": "一般关注"},
    "blue":   {"label": "🔵 信息提示", "css": "#1565c0", "bg": "#e3f2fd", "desc": "中性信息"},
    "green":  {"label": "🟢 正面催化", "css": "#2e7d32", "bg": "#e8f5e9", "desc": "正面利好"},
}

# cjpy 公告类型 → 预警等级映射
ANNOUNCEMENT_ALERT_MAP = {
    "风险警示公告": ("red", "风险警示"),
    "立案调查": ("red", "被立案调查"),
    "处罚": ("orange", "监管处罚"),
    "诉讼": ("orange", "涉及诉讼"),
    "违规": ("orange", "违规事项"),
    "问询函": ("orange", "交易所问询"),
    "关注函": ("orange", "监管关注"),
    "澄清公告": ("yellow", "发布澄清"),
    "高管变动": ("blue", "高管变动"),
    "董监高辞职": ("yellow", "董监高辞职"),
    "股权质押": ("yellow", "股权质押"),
    "对外担保": ("yellow", "对外担保"),
    "减持": ("orange", "股东减持"),
    "增持": ("green", "股东增持"),
}


def classify_alert(item):
    """根据事件内容判断预警等级"""
    level = item.get("level", "blue")
    if level not in ALERT_LEVELS:
        # 尝试根据关键词判断
        title = item.get("title", "") + item.get("summary", "")
        if any(kw in title for kw in ["立案", "调查", "强制", "退市", "ST", "*ST", "破产"]):
            level = "red"
        elif any(kw in title for kw in ["问询", "处罚", "违规", "诉讼", "减持", "下滑", "下降", "亏损"]):
            level = "orange"
        elif any(kw in title for kw in ["澄清", "风险", "质押", "冻结", "辞职"]):
            level = "yellow"
        elif any(kw in title for kw in ["回购", "增持", "利好", "超预期", "突破"]):
            level = "green"
        else:
            level = "blue"
    return level


def generate_html_report(data: dict) -> str:
    """生成 HTML 舆情日报"""
    report_date = data.get("date", datetime.now().strftime("%Y-%m-%d"))

    # 分类提取信号
    policy_signals = data.get("policy", [])
    industry_signals = data.get("industry", [])
    stock_signals = data.get("stocks", [])

    # 合并并按等级排序
    all_signals = []
    for s in policy_signals:
        s["_category"] = "政策舆情"
        all_signals.append(s)
    for s in industry_signals:
        s["_category"] = "产业舆情"
        all_signals.append(s)
    for s in stock_signals:
        s["_category"] = "个股预警"
        all_signals.append(s)

    # 分类统计
    counts = {"red": 0, "orange": 0, "yellow": 0, "blue": 0, "green": 0}
    for s in all_signals:
        lvl = classify_alert(s)
        s["_level"] = lvl
        counts[lvl] = counts.get(lvl, 0) + 1

    # 按等级排序：red > orange > yellow > blue > green
    level_order = {"red": 0, "orange": 1, "yellow": 2, "blue": 3, "green": 4}
    all_signals.sort(key=lambda x: (level_order.get(x.get("_level", "blue"), 99), x.get("time", "")))

    # 顶部统计条
    stats_html = ""
    for lvl_key, lvl_info in ALERT_LEVELS.items():
        cnt = counts.get(lvl_key, 0)
        if cnt > 0 or lvl_key in ("red", "orange"):
            stats_html += f"""
            <div class="stat-card" style="border-left:4px solid {lvl_info['css']};background:{lvl_info['bg']};">
                <div class="stat-value" style="color:{lvl_info['css']};">{cnt}</div>
                <div class="stat-label">{lvl_info['label']}</div>
            </div>"""

    # 信号列表
    rows_html = ""
    for s in all_signals:
        lvl = s.get("_level", "blue")
        lvl_info = ALERT_LEVELS[lvl]
        summary = s.get("summary", s.get("title", "")) or ""
        if len(summary) > 80:
            summary = summary[:77] + "..."
        title = s.get("title", summary)
        source = s.get("source", "")
        time_str = s.get("time", "")
        category = s.get("_category", "")
        target = s.get("target", "")

        rows_html += f"""
        <div class="signal-row" style="border-left:4px solid {lvl_info['css']};background:{lvl_info['bg']};">
            <div class="signal-level" style="color:{lvl_info['css']};">{lvl_info['label']}</div>
            <div class="signal-body">
                <div class="signal-title">{title}</div>
                <div class="signal-summary">{summary}</div>
                <div class="signal-meta">
                    <span>{category}</span>
                    {"<span>" + target + "</span>" if target else ""}
                    <span>{source}</span>
                    <span>{time_str}</span>
                </div>
            </div>
        </div>"""

    html = f"""<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>政策与舆情雷达 — {report_date}</title>
<style>
* {{ margin:0; padding:0; box-sizing:border-box; }}
body {{
    font-family: -apple-system, BlinkMacSystemFont, "Microsoft YaHei", sans-serif;
    background: #f5f6fa; color: #2c3e50; padding: 20px;
}}
.header {{
    text-align: center; padding: 24px 0 16px;
    background: linear-gradient(135deg, #1a1a2e 0%, #16213e 100%);
    color: white; border-radius: 12px; margin-bottom: 20px;
}}
.header h1 {{ font-size: 26px; font-weight: 700; margin-bottom: 4px; }}
.header .sub {{ font-size: 13px; opacity: 0.7; }}

.stats-bar {{ display:flex; gap:12px; margin-bottom:20px; flex-wrap:wrap; }}
.stat-card {{
    flex:1; min-width:120px; border-radius:10px; padding:14px; text-align:center;
}}
.stat-value {{ font-size:32px; font-weight:800; }}
.stat-label {{ font-size:13px; color:#666; margin-top:2px; }}

.section-title {{
    font-size:17px; font-weight:700; margin: 20px 0 12px;
    padding-bottom:8px; border-bottom:2px solid #e0e0e0;
}}

.signal-row {{
    border-radius:8px; padding:14px; margin-bottom:10px;
    display:flex; gap:12px; align-items:flex-start;
}}
.signal-level {{
    font-size:13px; font-weight:700; white-space:nowrap;
    min-width:80px; text-align:center; padding-top:2px;
}}
.signal-body {{ flex:1; min-width:0; }}
.signal-title {{ font-size:14px; font-weight:600; margin-bottom:4px; }}
.signal-summary {{ font-size:13px; color:#555; line-height:1.5; margin-bottom:6px; }}
.signal-meta {{
    display:flex; flex-wrap:wrap; gap:8px; font-size:11px; color:#999;
}}
.signal-meta span {{
    background:#f0f0f0; padding:2px 8px; border-radius:4px;
}}

.section-divider {{
    margin: 24px 0;
    display:flex; align-items:center; gap:12px;
}}
.section-divider::before,.section-divider::after {{
    content:''; flex:1; height:1px; background:#e0e0e0;
}}
.section-divider span {{
    font-size:13px; color:#999; font-weight:500;
}}

.footer {{
    text-align:center; color:#bbb; font-size:12px; margin-top:24px; padding:10px;
}}

@media (max-width:600px) {{
    .stats-bar {{ flex-direction:column; }}
    .signal-row {{ flex-direction:column; }}
    .signal-level {{ min-width:auto; }}
}}
</style>
</head>
<body>

<div class="header">
    <h1>📡 政策与舆情雷达</h1>
    <div class="sub">{report_date} · 三级监控：政策舆情 / 产业舆情 / 个股负面预警</div>
</div>

<div class="stats-bar">{stats_html}</div>

<div class="section-title">🔴 红色 / 🟠 橙色预警（重点关注）</div>
"""

    # 红色+橙色信号
    critical = [s for s in all_signals if s.get("_level") in ("red", "orange")]
    if critical:
        for s in critical:
            lvl = s["_level"]
            lvl_info = ALERT_LEVELS[lvl]
            summary = s.get("summary", s.get("title", "")) or ""
            if len(summary) > 80:
                summary = summary[:77] + "..."
            html += f"""
        <div class="signal-row" style="border-left:4px solid {lvl_info['css']};background:{lvl_info['bg']};">
            <div class="signal-level" style="color:{lvl_info['css']};">{lvl_info['label']}</div>
            <div class="signal-body">
                <div class="signal-title">{s.get('title','')}</div>
                <div class="signal-summary">{summary}</div>
                <div class="signal-meta">
                    <span>{s.get('_category','')}</span>
                    {"<span>" + s.get('target','') + "</span>" if s.get('target') else ""}
                    <span>{s.get('source','')}</span>
                    <span>{s.get('time','')}</span>
                </div>
            </div>
        </div>"""
    else:
        html += '<div style="text-align:center;color:#ccc;padding:20px;font-size:14px;">暂无红色/橙色预警信号</div>'

    # 黄色及以下信号
    html += '<div class="section-divider"><span>其他信号</span></div>'
    others = [s for s in all_signals if s.get("_level") not in ("red", "orange")]
    if others:
        for s in others:
            lvl = s["_level"]
            lvl_info = ALERT_LEVELS[lvl]
            summary = s.get("summary", s.get("title", "")) or ""
            if len(summary) > 80:
                summary = summary[:77] + "..."
            html += f"""
        <div class="signal-row" style="border-left:4px solid {lvl_info['css']};background:{lvl_info['bg']};">
            <div class="signal-level" style="color:{lvl_info['css']};">{lvl_info['label']}</div>
            <div class="signal-body">
                <div class="signal-title">{s.get('title','')}</div>
                <div class="signal-summary">{summary}</div>
                <div class="signal-meta">
                    <span>{s.get('_category','')}</span>
                    {"<span>" + s.get('target','') + "</span>" if s.get('target') else ""}
                    <span>{s.get('source','')}</span>
                    <span>{s.get('time','')}</span>
                </div>
            </div>
        </div>"""
    else:
        html += '<div style="text-align:center;color:#ccc;padding:20px;font-size:14px;">暂无其他信号</div>'

    html += f"""
<div class="footer">
    数据来源：cjpy · WebSearch · 生成时间：{datetime.now().strftime("%Y-%m-%d %H:%M")} · 仅供参考，不构成投资建议
</div>

</body>
</html>"""

    return html


def main():
    parser = argparse.ArgumentParser(description="政策与舆情雷达引擎")
    parser.add_argument("--data", help="JSON 数据文件路径")
    parser.add_argument("--output", help="输出 HTML 文件路径")
    parser.add_argument("--mode", default="report", choices=["report", "json"], help="输出模式")
    args = parser.parse_args()

    if args.data:
        data_path = Path(args.data)
        if not data_path.exists():
            print(f"错误：数据文件不存在 {data_path}", file=sys.stderr)
            sys.exit(1)

        with open(data_path, "r", encoding="utf-8") as f:
            data = json.load(f)

        if args.mode == "json":
            print(json.dumps(data, ensure_ascii=False, indent=2))
        else:
            html = generate_html_report(data)
            output_path = args.output or f"outputs/policy_sentinel_{data.get('date', datetime.now().strftime('%Y%m%d'))}.html"
            Path(output_path).parent.mkdir(parents=True, exist_ok=True)
            Path(output_path).write_text(html, encoding="utf-8")
            print(f"✅ 舆情日报已生成：{Path(output_path).resolve()}")
    else:
        print("""
政策与舆情雷达引擎 v1.0

用法：
  --data <json>   输入舆情数据 JSON
  --output <path> 输出 HTML 路径
  --mode json     输出 JSON（用于管道）

JSON 格式示例：
{
  "date": "2026-07-23",
  "policy": [
    {"title":"...", "summary":"...", "level":"red", "source":"...", "time":"...", "target":"..."}
  ],
  "industry": [...],
  "stocks": [...]
}
""".strip())


if __name__ == "__main__":
    main()
