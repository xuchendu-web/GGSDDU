#!/usr/bin/env python3
"""
行业景气度追踪 — 核心计算引擎
基于 cjpy 数据，对 31 个申万一级行业进行五维景气评分
"""

import json
import sys
import argparse
from datetime import datetime
from pathlib import Path

# ============================================================
# 申万一级行业（31个）与 cjpy 行业因子映射
# ============================================================
SW_INDUSTRIES = [
    "农林牧渔", "基础化工", "钢铁", "有色金属", "电子",
    "汽车", "家用电器", "食品饮料", "纺织服饰", "轻工制造",
    "医药生物", "公用事业", "交通运输", "房地产", "商贸零售",
    "社会服务", "银行", "非银金融", "综合", "建筑材料",
    "建筑装饰", "电力设备", "国防军工", "计算机", "传媒",
    "通信", "煤炭", "石油石化", "环保", "美容护理",
    "机械设备",
]

# 五维度配置
DIMENSIONS = {
    "盈利质量": {
        "weight": 0.30,
        "metrics": ["ROE", "毛利率", "净利率"],
        "positive": True,  # 越高越好
    },
    "增长动能": {
        "weight": 0.25,
        "metrics": ["营收增速", "净利润增速"],
        "positive": True,
    },
    "库存效率": {
        "weight": 0.20,
        "metrics": ["存货周转率变化", "库存/总资产变化"],
        "positive": False,  # 库存增加为负向
    },
    "市场定价": {
        "weight": 0.15,
        "metrics": ["PE分位数", "1月动量", "3月动量"],
        "positive": True,
    },
    "资金关注": {
        "weight": 0.10,
        "metrics": ["换手率变化", "成交额变化"],
        "positive": True,
    },
}

# 边际变化信号阈值
SIGNAL_THRESHOLDS = {
    "景气上行": 15,    # 连续2期上升 + 最新>60
    "边际改善": 5,     # 单期上升5%+
    "持平": 5,         # ±5% 以内
    "边际恶化": -5,    # 单期下降5%+
    "景气下行": -15,   # 连续2期下降 + 最新<40
}


def normalize_score(raw_value, all_values, positive=True):
    """将原始值标准化到 0-100 分（基于行业排名）"""
    if not all_values:
        return 50.0
    sorted_vals = sorted(all_values)
    n = len(sorted_vals)
    if n == 0:
        return 50.0

    # 计算百分位排名
    if positive:
        rank = sum(1 for v in sorted_vals if v <= raw_value)
    else:
        rank = sum(1 for v in sorted_vals if v >= raw_value)

    percentile = (rank / n) * 100
    return round(percentile, 1)


def calc_dimension_score(industry_data, dimension_name, all_industries_data):
    """计算单个行业在某个维度的得分"""
    dim_config = DIMENSIONS[dimension_name]
    metrics = dim_config["metrics"]
    positive = dim_config["positive"]

    metric_scores = []
    for metric in metrics:
        # 收集所有行业在该指标的原始值
        all_values = []
        for ind in all_industries_data.values():
            val = ind.get("metrics", {}).get(metric)
            if val is not None:
                all_values.append(val)

        raw_val = industry_data.get("metrics", {}).get(metric)
        if raw_val is not None and all_values:
            score = normalize_score(raw_val, all_values, positive)
            metric_scores.append(score)

    if not metric_scores:
        return 50.0

    return round(sum(metric_scores) / len(metric_scores), 1)


def calc_total_score(industry_data, all_industries_data):
    """计算行业景气总得分"""
    total = 0.0
    dim_scores = {}
    for dim_name, dim_config in DIMENSIONS.items():
        score = calc_dimension_score(industry_data, dim_name, all_industries_data)
        dim_scores[dim_name] = score
        total += score * dim_config["weight"]
    return round(total, 1), dim_scores


def get_signal(current_score, previous_score, current_dim_scores=None, prev_dim_scores=None):
    """判断边际变化信号"""
    if previous_score is None:
        return "➡️", "持平"

    change_pct = ((current_score - previous_score) / previous_score * 100) if previous_score > 0 else 0

    if change_pct >= SIGNAL_THRESHOLDS["景气上行"] and current_score > 60:
        return "🔥", "景气上行"
    elif change_pct >= SIGNAL_THRESHOLDS["边际改善"]:
        return "✅", "边际改善"
    elif change_pct <= SIGNAL_THRESHOLDS["景气下行"] and current_score < 40:
        return "❄️", "景气下行"
    elif change_pct <= SIGNAL_THRESHOLDS["边际恶化"]:
        return "⚠️", "边际恶化"
    else:
        return "➡️", "持平"


def generate_html_report(data: dict, all_scores: dict) -> str:
    """生成 HTML 景气矩阵热力图"""
    report_date = data.get("date", datetime.now().strftime("%Y-%m-%d"))
    data_period = data.get("data_period", "最新季报")

    # 按总得分排序
    sorted_industries = sorted(all_scores.items(), key=lambda x: x[1].get("total_score", 0), reverse=True)

    # 生成表格行
    rows_html = ""
    for ind_name, ind_data in sorted_industries:
        total = ind_data.get("total_score", 50)
        dim_scores = ind_data.get("dim_scores", {})
        signal_icon = ind_data.get("signal_icon", "➡️")
        signal_text = ind_data.get("signal_text", "持平")
        rank = ind_data.get("rank", "-")

        # 颜色
        if total >= 70:
            bg = "#e8f5e9"
            text_color = "#2e7d32"
        elif total >= 50:
            bg = "#fff8e1"
            text_color = "#f57f17"
        else:
            bg = "#fce4ec"
            text_color = "#c62828"

        dim_cells = ""
        for dim_name in DIMENSIONS:
            score = dim_scores.get(dim_name, 50)
            if score >= 70:
                d_color = "#4caf50"
            elif score >= 50:
                d_color = "#ff9800"
            else:
                d_color = "#f44336"
            dim_cells += f'<td style="text-align:center;color:{d_color};font-weight:700;">{score:.0f}</td>'

        rows_html += f"""
        <tr style="background:{bg};">
            <td style="font-weight:600;">{rank}</td>
            <td style="font-weight:600;">{ind_name}</td>
            <td style="text-align:center;font-size:20px;font-weight:700;color:{text_color};">{total:.0f}</td>
            {dim_cells}
            <td style="text-align:center;">{signal_icon} {signal_text}</td>
        </tr>"""

    html = f"""<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>行业景气度追踪 — {report_date}</title>
<style>
* {{ margin:0; padding:0; box-sizing:border-box; }}
body {{
    font-family: -apple-system, BlinkMacSystemFont, "Microsoft YaHei", sans-serif;
    background: #f5f6fa; color: #2c3e50; padding: 20px;
}}
.header {{
    text-align: center; padding: 24px 0 16px;
    background: linear-gradient(135deg, #1565c0 0%, #0d47a1 100%);
    color: white; border-radius: 12px; margin-bottom: 20px;
}}
.header h1 {{ font-size: 28px; font-weight: 700; margin-bottom: 4px; }}
.header .sub {{ font-size: 14px; opacity: 0.7; }}

.summary {{ display:flex; gap:16px; margin-bottom:20px; }}
.summary-card {{
    flex:1; background:white; border-radius:12px; padding:16px;
    box-shadow:0 2px 12px rgba(0,0,0,0.06); text-align:center;
}}
.summary-card .value {{ font-size:32px; font-weight:800; }}
.summary-card .label {{ font-size:13px; color:#999; margin-top:4px; }}
.summary-card .value.green {{ color:#2e7d32; }}
.summary-card .value.orange {{ color:#f57f17; }}
.summary-card .value.red {{ color:#c62828; }}

.table-wrap {{
    background:white; border-radius:12px; padding:16px;
    box-shadow:0 2px 12px rgba(0,0,0,0.06); overflow-x:auto;
}}
table {{ width:100%; border-collapse:collapse; font-size:13px; }}
th {{
    background:#1565c0; color:white; padding:10px 8px; text-align:center;
    font-weight:600; white-space:nowrap; position:sticky; top:0;
}}
th:first-child, th:nth-child(2) {{ text-align:left; }}
td {{ padding:10px 8px; border-bottom:1px solid #eee; }}

.legend {{ display:flex; gap:16px; margin:16px 0; font-size:12px; align-items:center; }}
.legend-item {{ display:flex; align-items:center; gap:4px; }}
.legend-dot {{ width:12px; height:12px; border-radius:3px; }}

.footer {{
    text-align:center; color:#bbb; font-size:12px; margin-top:20px; padding:10px;
}}

.signal-list {{ margin-top:20px; background:white; border-radius:12px; padding:20px; box-shadow:0 2px 12px rgba(0,0,0,0.06); }}
.signal-list h3 {{ margin-bottom:12px; }}
.signal-item {{ padding:6px 0; font-size:14px; border-bottom:1px solid #f0f0f0; }}
.signal-item:last-child {{ border-bottom:none; }}
</style>
</head>
<body>

<div class="header">
    <h1>📊 行业景气度追踪</h1>
    <div class="sub">申万一级行业 · 五维评分矩阵 · {report_date}</div>
    <div class="sub">数据报告期：{data_period}</div>
</div>

<div class="summary">
"""

    # 统计摘要
    high = sum(1 for _, d in sorted_industries if d.get("total_score", 0) >= 70)
    mid = sum(1 for _, d in sorted_industries if 50 <= d.get("total_score", 0) < 70)
    low = sum(1 for _, d in sorted_industries if d.get("total_score", 0) < 50)
    up = sum(1 for _, d in sorted_industries if d.get("signal_text") in ("景气上行", "边际改善"))
    down = sum(1 for _, d in sorted_industries if d.get("signal_text") in ("景气下行", "边际恶化"))

    html += f"""
    <div class="summary-card">
        <div class="value green">{high}</div>
        <div class="label">高景气行业 (≥70)</div>
    </div>
    <div class="summary-card">
        <div class="value orange">{mid}</div>
        <div class="label">中等景气 (50-70)</div>
    </div>
    <div class="summary-card">
        <div class="value red">{low}</div>
        <div class="label">低景气 (&lt;50)</div>
    </div>
    <div class="summary-card">
        <div class="value" style="color:#1565c0;">{up}</div>
        <div class="label">边际改善 🔥✅</div>
    </div>
    <div class="summary-card">
        <div class="value" style="color:#e65100;">{down}</div>
        <div class="label">边际恶化 ⚠️❄️</div>
    </div>
"""

    html += """
</div>

<div class="table-wrap">
    <table>
        <thead>
            <tr>
                <th>排名</th>
                <th>行业</th>
                <th>总得分</th>
"""

    for dim_name in DIMENSIONS:
        html += f'<th>{dim_name}<br><small>({int(DIMENSIONS[dim_name]["weight"]*100)}%)</small></th>'

    html += '<th>边际变化</th></tr></thead><tbody>'
    html += rows_html
    html += '</tbody></table></div>'

    # 图例
    html += """
<div class="legend">
    <span>得分图例：</span>
    <div class="legend-item"><div class="legend-dot" style="background:#4caf50;"></div> ≥70 高景气</div>
    <div class="legend-item"><div class="legend-dot" style="background:#ff9800;"></div> 50-70 中景气</div>
    <div class="legend-item"><div class="legend-dot" style="background:#f44336;"></div> &lt;50 低景气</div>
    <span style="margin-left:16px;">信号：</span>
    <div class="legend-item">🔥 景气上行</div>
    <div class="legend-item">✅ 边际改善</div>
    <div class="legend-item">➡️ 持平</div>
    <div class="legend-item">⚠️ 边际恶化</div>
    <div class="legend-item">❄️ 景气下行</div>
</div>
"""

    # 信号列表
    signal_items = [(n, d) for n, d in sorted_industries if d.get("signal_text") not in ("持平",)]
    if signal_items:
        html += '<div class="signal-list"><h3>🔔 边际变化信号</h3>'
        for name, data in signal_items:
            html += f'<div class="signal-item">{data["signal_icon"]} <b>{name}</b>：{data["signal_text"]}（{data.get("previous_score", "—")} → {data["total_score"]:.0f}）</div>'
        html += '</div>'

    html += f"""
<div class="footer">
    数据来源：cjpy · 申万行业分类 · 生成时间：{datetime.now().strftime("%Y-%m-%d %H:%M")} · 仅供参考，不构成投资建议
</div>

</body>
</html>"""

    return html


def main():
    parser = argparse.ArgumentParser(description="行业景气度追踪引擎")
    parser.add_argument("--data", help="JSON 数据文件路径（完整模式）")
    parser.add_argument("--mode", default="report", choices=["report", "matrix"], help="输出模式")
    parser.add_argument("--format", default="html", choices=["html", "json"], help="输出格式")
    parser.add_argument("--output", help="输出文件路径")
    args = parser.parse_args()

    if args.data:
        data_path = Path(args.data)
        if not data_path.exists():
            print(f"错误：数据文件不存在 {data_path}", file=sys.stderr)
            sys.exit(1)

        with open(data_path, "r", encoding="utf-8") as f:
            data = json.load(f)

        # 计算各行业得分
        all_industries_data = data.get("industries", {})
        previous_data = data.get("previous", {})
        all_scores = {}

        # 使用数据中的行业列表（支持一级或二级行业）
        industry_names = list(all_industries_data.keys())
        for idx, ind_name in enumerate(industry_names, 1):
            ind_data = all_industries_data.get(ind_name, {})
            prev_data = previous_data.get(ind_name, {})

            total_score, dim_scores = calc_total_score(ind_data, all_industries_data)
            prev_score = prev_data.get("total_score")

            signal_icon, signal_text = get_signal(total_score, prev_score)

            all_scores[ind_name] = {
                "total_score": total_score,
                "dim_scores": dim_scores,
                "previous_score": prev_score,
                "signal_icon": signal_icon,
                "signal_text": signal_text,
                "rank": idx,
            }

        # 按总得分排序，更新排名
        sorted_scores = sorted(all_scores.items(), key=lambda x: x[1]["total_score"], reverse=True)
        for rank, (ind_name, ind_data) in enumerate(sorted_scores, 1):
            ind_data["rank"] = rank

        if args.format == "json":
            output = json.dumps({k: {"total_score": v["total_score"],
                                      "dim_scores": v["dim_scores"],
                                      "signal": v["signal_text"],
                                      "rank": v["rank"]}
                                 for k, v in sorted_scores},
                                ensure_ascii=False, indent=2)
            if args.output:
                Path(args.output).write_text(output, encoding="utf-8")
            print(output)
        else:
            html = generate_html_report(data, all_scores)
            output_path = args.output or f"outputs/industry_prosperity_{data.get('date', datetime.now().strftime('%Y%m%d'))}.html"
            Path(output_path).parent.mkdir(parents=True, exist_ok=True)
            Path(output_path).write_text(html, encoding="utf-8")
            print(f"✅ 行业景气度报告已生成：{Path(output_path).resolve()}")
    else:
        # 无数据文件模式：输出框架说明
        print("""
行业景气度追踪引擎 v1.0

用法：
  --data <json>  输入行业财务+行情聚合数据
  --mode report  生成 HTML 报告（默认）
  --format html  输出格式

需要先通过 cjpy 提取各行业财务/行情数据并聚合为 JSON。
���见 SKILL.md 工作流说明。
""".strip())


if __name__ == "__main__":
    main()
