# -*- coding: utf-8 -*-
"""industry-quadrant-monitor · 渲染层（第三期 D2 render）

职责（规划文档 S1）：plotly 图 + HTML 报告 + Excel 底稿 + PDF 打印版。
本模块不含算法，只把打分结果画出来 / 导出来。

含第三期渲染修复：
  · N3  customdata 类型：改用「预格式化字符串 + 无格式符 hovertemplate」，
         彻底消除 fillna('N/A') 把整列退化为 object 数组导致 .1f 失效的问题。
  · C3  象限标注：用 fig.add_annotation() 逐个追加，避免 plotly 6.x 下
         update_layout(annotations=[...]) 覆盖式合并导致标注消失。
  · N-5 X 轴范围与标注定位：用统一计算的 xhi/yhi，标注点恒在轴内。
  · N-3 标题跟随 sw_label（不再写死「二级」）。
  · D22 文字标签规则：仅一级行业（sw_level=="1"）在散点图上标注行业名；
        二级/三级行业数量多（~130/~340），标注会严重重叠，故只画气泡不标文字。
        轴标题与象限角标始终保留。
  · E14 GBK：emoji 由 datasource.init_console 在导入时加固，本层只负责不出错。
"""

import html
import logging
import os
import re
from pathlib import Path

import numpy as np
import pandas as pd

# 中文 PDF 字体（优先用系统 TTF；TTF 在 platypus 与 graphics 中均可靠渲染中文）
_CJK_FONT = None
HERE = Path(__file__).resolve().parent

import config
from config import (
    QUADRANT_ORDER, QUADRANT_LABEL, QUADRANT_COLOR, QUADRANT_KEY, QUADRANT_EMOJI,
    BUBBLE_MIN, BUBBLE_MAX, SW3_WARN_N, SW3_LABEL_TOPN,
)

logger = logging.getLogger("iqm")


# HTML 报告采用 cj-style-longpic 的红 / 黑 / 灰研究风，但保留四象限自身的
# 红 / 橙 / 绿 / 蓝业务语义。这里只影响 HTML，不改变 Excel / PDF 的配色。
_HTML_QUADRANT_COLOR = {
    "Q1": "#E10000",
    "Q2": "#D88900",
    "Q3": "#2A8A5B",
    "Q4": "#3F6F9E",
}
_HTML_QUADRANT_TITLE = {
    "Q1": "相对较强行业",
    "Q2": "情绪驱动",
    "Q3": "相对较弱行业",
    "Q4": "价值洼地",
}
_HTML_QUADRANT_DESC = {
    "Q1": "基本面与技术面同向偏强",
    "Q2": "技术面走强，基本面仍待验证",
    "Q3": "基本面与技术面同向偏弱",
    "Q4": "基本面较好，价格尚未充分反应",
}


_REPORT_CSS = r"""
:root {
  --red: #E10000;
  --deep-red: #B90000;
  --black: #202020;
  --hero-copy: #3A3A3A;
  --gray: #666666;
  --muted: #767676;
  --line: #DDDDDD;
  --soft: #F4F4F4;
  --soft-2: #F8F8F8;
  --pale-red: #FCECEC;
  --pale-red-line: #F3BBBB;
  --white: #FFFFFF;
  --positive: #16784A;
  --warning: #9A6700;
  --danger: #B42318;
  --page-max: 1280px;
  --gutter: clamp(18px, 4vw, 52px);
  --radius: 12px;
  --font: "Microsoft YaHei", "微软雅黑", "Microsoft YaHei UI", "PingFang SC", "Noto Sans CJK SC", "STHeiti", "Segoe UI", Arial, sans-serif;
}

* { box-sizing: border-box; }
html { background: var(--soft); color-scheme: light; }
body {
  margin: 0;
  background: var(--soft);
  color: var(--black);
  font-family: var(--font);
  font-size: 16px;
  line-height: 1.62;
  text-rendering: optimizeLegibility;
  -webkit-font-smoothing: antialiased;
}
h1, h2, p { margin-top: 0; }
.top-rule { width: 100%; height: 8px; background: var(--red); }
.report-shell {
  width: min(100%, var(--page-max));
  margin: 0 auto;
  overflow: hidden;
  background: var(--white);
  border-inline: 1px solid #ECECEC;
}

.report-hero {
  padding: 52px var(--gutter) 44px;
  border-bottom: 1px solid var(--line);
  background: var(--white);
}
.hero-kicker,
.section-eyebrow {
  margin: 0 0 12px;
  color: var(--red);
  font-size: 13px;
  font-weight: 800;
  line-height: 1.3;
  letter-spacing: 1.7px;
  text-transform: uppercase;
}
.report-hero h1 {
  max-width: 1000px;
  margin: 0 0 16px;
  color: var(--black);
  font-size: clamp(32px, 4vw, 48px);
  font-weight: 800;
  line-height: 1.2;
  letter-spacing: -0.8px;
}
.hero-summary {
  max-width: 930px;
  margin: 0 0 24px;
  color: var(--hero-copy);
  font-size: clamp(16px, 1.65vw, 20px);
  line-height: 1.7;
}
.tag-row { display: flex; flex-wrap: wrap; gap: 10px; }
.tag {
  display: inline-flex;
  min-height: 34px;
  align-items: center;
  padding: 6px 13px;
  border-radius: 999px;
  background: var(--pale-red);
  color: var(--deep-red);
  font-size: 13px;
  font-weight: 700;
  line-height: 1.3;
  white-space: nowrap;
}

.report-section {
  padding: 42px var(--gutter);
  background: var(--white);
}
.report-section--soft { background: var(--soft); }
.section-heading {
  display: grid;
  grid-template-columns: 6px minmax(0, 1fr);
  gap: 16px;
  align-items: start;
  margin: 0 0 10px;
}
.section-heading::before {
  content: "";
  width: 6px;
  height: 42px;
  margin-top: 2px;
  border-radius: 1px;
  background: var(--red);
}
.section-heading-copy { min-width: 0; }
.section-heading .section-eyebrow { margin-bottom: 4px; }
.section-title {
  margin: 0;
  color: var(--black);
  font-size: clamp(24px, 2.5vw, 32px);
  font-weight: 800;
  line-height: 1.3;
  letter-spacing: -0.4px;
}
.section-lead {
  max-width: 980px;
  margin: 0 0 24px 22px;
  color: var(--gray);
  font-size: 15px;
  line-height: 1.7;
}

.quadrant-grid {
  display: grid;
  grid-template-columns: repeat(4, minmax(0, 1fr));
  gap: 14px;
}
.quadrant-card {
  min-width: 0;
  padding: 20px 18px 18px;
  border: 1px solid var(--line);
  border-top: 5px solid var(--quad-color);
  border-radius: var(--radius);
  background: var(--white);
}
.quadrant-card--q1 { --quad-color: #E10000; }
.quadrant-card--q2 { --quad-color: #D88900; }
.quadrant-card--q3 { --quad-color: #2A8A5B; }
.quadrant-card--q4 { --quad-color: #3F6F9E; }
.quadrant-label {
  margin: 0 0 12px;
  color: var(--quad-color);
  font-size: 14px;
  font-weight: 800;
}
.quadrant-value-row {
  display: flex;
  align-items: baseline;
  gap: 8px;
  margin-bottom: 8px;
}
.quadrant-value {
  color: var(--black);
  font-size: 30px;
  font-weight: 800;
  font-variant-numeric: tabular-nums;
  line-height: 1;
}
.quadrant-share { color: var(--muted); font-size: 13px; }
.quadrant-desc { margin: 0; color: var(--gray); font-size: 13px; line-height: 1.55; }

.chart-card,
.table-card {
  overflow: hidden;
  border: 1px solid var(--line);
  border-radius: var(--radius);
  background: var(--white);
}
.chart-card { padding: 10px 14px 6px; }
.plotly-graph-div {
  width: 100% !important;
  max-width: 100% !important;
}
.chart-footnote {
  display: flex;
  flex-wrap: wrap;
  gap: 8px 18px;
  margin: 14px 2px 0;
  color: var(--muted);
  font-size: 12px;
}
.chart-footnote span::before { content: "•"; margin-right: 7px; color: var(--red); }

.table-card { overflow-x: auto; scrollbar-color: #BDBDBD var(--soft); }
.table-scroll-hint {
  display: none;
  margin: -6px 0 10px;
  color: var(--deep-red);
  font-size: 12px;
  font-weight: 700;
}
.improvement-table {
  width: 100%;
  min-width: 1120px;
  border-collapse: collapse;
  color: var(--black);
  font-size: 13px;
  line-height: 1.45;
  text-align: center;
  font-variant-numeric: tabular-nums;
}
.improvement-table th {
  padding: 13px 12px;
  border-bottom: 1px solid #3A3A3A;
  background: var(--black);
  color: var(--white);
  font-weight: 700;
  white-space: nowrap;
}
.improvement-table td {
  padding: 11px 12px;
  border-bottom: 1px solid #E8E8E8;
  background: var(--white);
  white-space: nowrap;
}
.improvement-table tbody tr:nth-child(even) td { background: var(--soft-2); }
.improvement-table tbody tr:hover td { background: #FFF4F4; }
.improvement-table tbody tr:last-child td { border-bottom: 0; }
.improvement-table th:first-child,
.improvement-table td:first-child { text-align: left; font-weight: 700; }
.value-positive { color: var(--positive); font-weight: 800; }
.value-hot { color: var(--danger); font-weight: 800; }
.value-warm { color: #A84C00; font-weight: 700; }
.table-note {
  margin: 13px 2px 0;
  color: var(--muted);
  font-size: 12px;
  line-height: 1.65;
}
.empty-state {
  padding: 30px;
  border: 1px dashed #CFCFCF;
  border-radius: var(--radius);
  background: var(--soft-2);
  color: var(--gray);
  text-align: center;
}

.report-section--lineage { background: var(--white); }
.lineage {
  overflow: hidden;
  border: 1px solid var(--line);
  border-left: 7px solid var(--status-color);
  border-radius: var(--radius);
  background: var(--status-bg);
}
.lineage--ok { --status-color: #1F7A4D; --status-bg: #EDF8F1; }
.lineage--warn { --status-color: #9A6700; --status-bg: #FFF8E6; }
.lineage--bad { --status-color: #B42318; --status-bg: #FFF0EE; }
.lineage-top {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 16px;
  padding: 17px 20px;
  border-bottom: 1px solid rgba(32, 32, 32, 0.10);
}
.lineage-title { color: var(--black); font-size: 16px; font-weight: 800; }
.status-badge {
  display: inline-flex;
  align-items: center;
  padding: 5px 10px;
  border-radius: 999px;
  background: var(--white);
  color: var(--status-color);
  font-size: 12px;
  font-weight: 800;
  white-space: nowrap;
}
.lineage-table {
  width: 100%;
  border-collapse: collapse;
  color: var(--black);
  font-size: 13px;
  line-height: 1.6;
}
.lineage-table th,
.lineage-table td { padding: 9px 20px; border-bottom: 1px solid rgba(32, 32, 32, 0.08); }
.lineage-table tr:last-child th,
.lineage-table tr:last-child td { border-bottom: 0; }
.lineage-table th {
  width: 118px;
  color: var(--gray);
  font-weight: 700;
  text-align: left;
  vertical-align: top;
  white-space: nowrap;
}
.lineage-table td { text-align: left; overflow-wrap: anywhere; }
.lineage-warn {
  margin: 0 20px 18px;
  padding: 11px 13px;
  border-left: 5px solid var(--status-color);
  background: rgba(255, 255, 255, 0.72);
  color: var(--black);
  font-size: 13px;
  line-height: 1.6;
}

@media (max-width: 920px) {
  .quadrant-grid { grid-template-columns: repeat(2, minmax(0, 1fr)); }
  .chart-card { padding-inline: 4px; }
  .table-scroll-hint { display: block; }
}
@media (max-width: 620px) {
  :root { --gutter: 18px; }
  .top-rule { height: 6px; }
  .report-shell { border-inline: 0; }
  .report-hero { padding-top: 34px; padding-bottom: 30px; }
  .report-section { padding-top: 30px; padding-bottom: 30px; }
  .hero-summary { line-height: 1.6; }
  .quadrant-grid { grid-template-columns: 1fr; gap: 10px; }
  .quadrant-card { padding: 16px; }
  .section-heading { gap: 12px; }
  .section-lead { margin-left: 18px; }
  .lineage-top { align-items: flex-start; flex-direction: column; }
  .lineage-table,
  .lineage-table tbody,
  .lineage-table tr,
  .lineage-table th,
  .lineage-table td { display: block; width: 100%; }
  .lineage-table tr { padding: 9px 16px; border-bottom: 1px solid rgba(32, 32, 32, 0.08); }
  .lineage-table th,
  .lineage-table td { padding: 0; border: 0; white-space: normal; }
  .lineage-table td { margin-top: 2px; }
  .lineage-warn { margin-inline: 16px; }
}
@media print {
  @page { size: A4 landscape; margin: 10mm; }
  html, body { background: var(--white); }
  .top-rule { height: 5px; }
  .report-shell { width: 100%; max-width: none; border: 0; }
  .report-hero, .report-section { padding-inline: 18px; }
  .table-card { overflow: visible; }
  .improvement-table { min-width: 0; font-size: 9px; }
  .improvement-table th, .improvement-table td { padding: 5px 4px; white-space: normal; }
}
"""

try:
    import plotly.graph_objects as go
    from plotly.subplots import make_subplots
except Exception:  # pragma: no cover
    go = None
    make_subplots = None

try:
    from openpyxl.styles import Font, PatternFill, Alignment
except Exception:  # pragma: no cover
    Font = PatternFill = Alignment = None

try:
    from reportlab.lib.pagesizes import A4
    from reportlab.lib import colors
    from reportlab.lib.units import mm
    from reportlab.platypus import (
        SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, KeepTogether)
    from reportlab.graphics.shapes import Drawing, Circle, Line, Rect, String
    from reportlab.graphics import renderPDF
    from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
except Exception:  # pragma: no cover
    A4 = colors = mm = SimpleDocTemplate = Paragraph = Spacer = Table = None
    TableStyle = KeepTogether = Drawing = Circle = Line = Rect = String = None
    renderPDF = getSampleStyleSheet = ParagraphStyle = None


# ═══════════════════════════════════════════════════════════════
# 数据血统条（[清单#17]）
# ═══════════════════════════════════════════════════════════════
def build_lineage_html(meta):
    ok = meta.get("coverage_ok", True)
    degraded = meta.get("degraded_notes") or []

    if ok and not degraded:
        tone, title = "ok", "数据完整"
    elif ok and degraded:
        tone, title = "warn", "数据基本完整，但有降级项"
    else:
        tone, title = "bad", "数据不完整 —— 结论不可用"

    def pct(v):
        return "N/A" if v is None else "{:.1%}".format(v)

    items = [
        ("行业层级", "{}（{}），共 {} 个行业入图".format(
            meta.get("sw_label", "?"), meta.get("industry_col", "?"), meta.get("n_industries", "?"))),
        ("财报期", "{}　同比基准 {}　（{}，当期覆盖 {}）".format(
            meta.get("latest_quarter", "?"), meta.get("yoy_quarter", "?"),
            meta.get("quarter_source", "?"), pct(meta.get("quarter_coverage")))),
        ("基本面口径", "{}（TTM 锚点 {} / 同比基准 TTM@{}）".format(
            meta.get("fund_method", "累计同比"), meta.get("ttm_anchor", "?"),
            meta.get("ttm_basis", "?"))),
        ("技术面截面", "T0={}　→　T1={}　→　T2={}　（回看 {} 交易日）".format(
            meta.get("t0", "?"), meta.get("t1", "?"), meta.get("t2", "?"),
            meta.get("lookback", "?"))),
        ("股票池", "{} 只 A 股候选（SZ/SH，已排除北交所）；剔除 ST/停牌退市 {} 只后剩 {} 只；行业截面 {}".format(
            meta.get("universe_raw", "?"), meta.get("excluded", 0),
            meta.get("universe", "?"), meta.get("industry_asof", "?"))),
        ("覆盖率", "行业分类 {}　|　财务 {}　|　技术面 {}　|　PE {}　（门槛 {}）".format(
            pct(meta.get("cov_industry")), pct(meta.get("cov_financial")),
            pct(meta.get("cov_technical")), pct(meta.get("cov_pe")),
            pct(meta.get("min_coverage")))),
        ("有效样本", "基本面 {} 只　|　技术面 T0→T1 {} 只 / T1→T2 {} 只".format(
            meta.get("fund_sample", "?"), meta.get("tech_sample_prev", "?"),
            meta.get("tech_sample_curr", "?"))),
        ("失败批次", "行业 {} / 财务 {} / 技术面 {} / PE {}".format(
            meta.get("fail_industry", 0), meta.get("fail_financial", 0),
            meta.get("fail_technical", 0), meta.get("fail_pe", 0))),
        ("估值口径", meta.get("pe_desc", "未计算")),
        ("缓存", _cache_lineage(meta)),
        ("运行信息", "脚本 v{}　|　生成于 {}　|　耗时 {:.1f}s　|　Python {}".format(
            meta.get("script_version", "?"), meta.get("generated_at", "?"),
            meta.get("elapsed", 0.0), meta.get("python", "?"))),
    ]

    rows = "".join(
        '<tr><th scope="row">{}</th><td>{}</td></tr>'.format(
            html.escape(str(k)), html.escape(str(v)))
        for k, v in items
    )
    warn_html = ""
    if degraded:
        warn_html = '<div class="lineage-warn">降级项：{}</div>'.format(
            html.escape("；".join(str(note) for note in degraded)))

    return (
        '<section class="report-section report-section--lineage" '
        'aria-labelledby="lineage-heading">'
        '<div class="section-heading">'
        '<div class="section-heading-copy">'
        '<div class="section-eyebrow">DATA LINEAGE</div>'
        '<h2 class="section-title" id="lineage-heading">数据血统与运行口径</h2>'
        '</div></div>'
        '<p class="section-lead">完整记录本次报告的数据日期、覆盖率、计算口径与运行环境。</p>'
        '<div class="lineage lineage--{tone}">'
        '<div class="lineage-top"><div class="lineage-title">数据完整性检查</div>'
        '<div class="status-badge">{title}</div></div>'
        '<table class="lineage-table" aria-label="数据血统明细">{rows}</table>{warn}'
        '</div></section>'
    ).format(tone=tone, title=html.escape(title), rows=rows, warn=warn_html)


def _cache_lineage(meta):
    cs = meta.get("cache_summary")
    if not cs:
        return "未使用（--no-cache 或首跑）"
    parts = []
    if cs.get("fin_hit"):
        parts.append("财务命中 {} 次".format(cs["fin_hit"]))
    if cs.get("pettm_hit"):
        parts.append("PETTM 命中 {} 次".format(cs["pettm_hit"]))
    if not parts:
        parts.append("首跑（无命中）")
    return "；".join(parts)


# ═══════════════════════════════════════════════════════════════
# HTML 报告
# ═══════════════════════════════════════════════════════════════
def _fmt_cell(v, kind):
    """把单元格格式化成字符串（N3 修复：hover 用预格式化字符串，不再依赖 .1f）。"""
    if v is None or (isinstance(v, float) and pd.isna(v)):
        return "N/A"
    if kind == "int":
        try:
            return "{:.0f}".format(v)
        except Exception:
            return str(v)
    if kind == "pct1":
        return "{:.1f}%".format(v)
    if kind == "pct0":
        return "{:.0f}%".format(v)
    if kind == "f2":
        return "{:.2f}".format(v)
    return str(v)


def _build_quadrant_summary_html(df):
    """生成四象限概览卡；只汇总现有结果，不引入新的判断口径。"""
    total = len(df)
    cards = []
    for quad in QUADRANT_ORDER:
        count = int((df["象限"] == quad).sum())
        share = count / total * 100 if total else 0.0
        cards.append(
            '<article class="quadrant-card quadrant-card--{q}">'
            '<div class="quadrant-label">{label}</div>'
            '<div class="quadrant-value-row">'
            '<span class="quadrant-value">{count}</span>'
            '<span class="quadrant-share">个行业 · {share:.1f}%</span>'
            '</div>'
            '<p class="quadrant-desc">{desc}</p>'
            '</article>'.format(
                q=quad.lower(),
                label=html.escape(_HTML_QUADRANT_TITLE[quad]),
                count=count,
                share=share,
                desc=html.escape(_HTML_QUADRANT_DESC[quad]),
            )
        )
    return "".join(cards)


def _build_tag_html(values):
    return "".join(
        '<span class="tag">{}</span>'.format(html.escape(str(value)))
        for value in values if value not in (None, "")
    )


def create_report(df, improvement_table, output_path, lookback_days, latest_quarter,
                  meta=None, industry_col=None):
    """生成 HTML 报告：数据血统条 + 四象限散点图 + 技术面改善表格。"""
    meta = meta if meta is not None else {}
    industry_col = industry_col or meta.get("industry_col")
    if df is None or len(df) == 0:
        raise config.EmptyResultError("没有任何行业进入报告，拒绝生成空图表。")

    sw_label = meta.get("sw_label", "申万行业")
    pe_col = "PE分位数" if "PE分位数" in df.columns else None

    # ── 气泡大小 = PE 分位数（0-100，越大越贵） ──
    if pe_col:
        # 气泡：PE 越低越大（越低估越醒目），与估值表达一致；
        # tooltip 仍显示真实 PE 分位数，仅尺寸取反，不改变数值含义。
        bubble_size = ((BUBBLE_MIN + BUBBLE_MAX) - df["PE分位数"].fillna(50)).clip(BUBBLE_MIN, BUBBLE_MAX)
    else:
        bubble_size = df["成分股数"].clip(3, 100)

    # ── 轴范围与标注定位统一计算（N-5） ──
    x_pos = max(float(df["基本面得分"].max()), 0.0)
    xhi = max(x_pos * 1.15, 1.0)
    y_span = max(abs(float(df["技术面得分"].max())), abs(float(df["技术面得分"].min())), 0.0)
    yhi = max(y_span * 1.15, 1.0)

    # ── 文字标签规则（用户拍板）：仅一级行业标注全部行业名；二级/三级行业
    # 数量较多（~130 / ~340 个），标注会严重重叠杂乱，故只画气泡、不标文字，
    # 明细仍可通过 HTML 悬停 / Excel 底稿查看。轴标题与象限角标始终保留。
    show_labels = (meta.get("sw_level") == "1")

    fig = make_subplots(rows=1, cols=1)

    for quad in QUADRANT_ORDER:
        label = _HTML_QUADRANT_TITLE[quad]
        subset = df[df["象限"] == quad]
        if len(subset) == 0:
            continue
        custom_rows = []
        for _, row in subset.iterrows():
            custom_rows.append([
                str(row[industry_col]),
                _fmt_cell(row["成分股数"], "int"),
                _fmt_cell(row["净利润增速中位数"], "pct1"),
                _fmt_cell(row["营收增速中位数"], "pct1"),
                _fmt_cell(row["价格动量中位数"], "pct1"),
                _fmt_cell(row["量能变化中位数"], "f2"),
                _fmt_cell(row.get("PE分位数"), "pct0") if pe_col else "N/A",
            ])
        fig.add_trace(
            go.Scatter(
                x=subset["基本面得分"],
                y=subset["技术面得分"],
                mode=("markers+text" if show_labels else "markers"),
                name=label,
                marker=dict(
                    size=np.sqrt(bubble_size.loc[subset.index].clip(BUBBLE_MIN, BUBBLE_MAX)) * 1.8,
                    color=_HTML_QUADRANT_COLOR[quad], opacity=0.78,
                    line=dict(width=1.2, color="white"),
                ),
                text=(list(subset[industry_col]) if show_labels else []),
                textposition="top center" if show_labels else None,
                textfont=dict(size=9),
                hovertemplate=(
                    "<b>%{customdata[0]}</b><br>"
                    "成分股: %{customdata[1]}只<br>"
                    "基本面得分: %{x:.2f}<br>技术面得分: %{y:.2f}<br>"
                    "净利润增速(中位): %{customdata[2]}<br>"
                    "营收增速(中位): %{customdata[3]}<br>"
                    "价格动量(中位): %{customdata[4]}<br>"
                    "量能变化(中位): %{customdata[5]}<br>"
                    "PE分位数: %{customdata[6]}<br>"
                    "<extra></extra>"
                ),
                customdata=custom_rows,
            ),
            row=1, col=1,
        )

    fig.add_hline(y=0, line_dash="dash", line_color="#8C8C8C", opacity=0.65)
    fig.add_vline(x=0, line_dash="dash", line_color="#8C8C8C", opacity=0.65)

    fig.update_layout(
        xaxis=dict(
            title=dict(text="基本面得分　← 弱 ｜ 强 →", font=dict(size=14, color="#3A3A3A")),
            range=[-1.0, xhi], zeroline=False,
            showline=True, linecolor="#CFCFCF", linewidth=1,
            gridcolor="#E8E8E8", gridwidth=1,
            tickfont=dict(size=12, color="#555555"),
        ),
        yaxis=dict(
            title=dict(text="技术面得分　← 弱 ｜ 强 →", font=dict(size=14, color="#3A3A3A")),
            range=[-yhi, yhi], zeroline=False,
            showline=True, linecolor="#CFCFCF", linewidth=1,
            gridcolor="#E8E8E8", gridwidth=1,
            tickfont=dict(size=12, color="#555555"),
        ),
        height=720, autosize=True,
        hovermode="closest", template="plotly_white",
        paper_bgcolor="#FFFFFF", plot_bgcolor="#FFFFFF",
        font=dict(
            family="Microsoft YaHei, Microsoft YaHei UI, PingFang SC, Arial, sans-serif",
            size=13, color="#202020",
        ),
        margin=dict(t=92, l=74, r=34, b=70),
        legend=dict(
            orientation="h", yanchor="bottom", y=1.035,
            xanchor="center", x=0.5,
            bgcolor="rgba(255,255,255,0.92)",
            bordercolor="#DDDDDD", borderwidth=1,
            font=dict(size=12, color="#202020"),
        ),
        hoverlabel=dict(
            bgcolor="#202020", bordercolor="#202020",
            font=dict(color="#FFFFFF", size=13,
                      family="Microsoft YaHei, Microsoft YaHei UI, Arial, sans-serif"),
        ),
    )
    # C3 修复：逐个追加标注，避免 update_layout(annotations=[...]) 覆盖式合并导致标注消失
    # emoji 统一走 QUADRANT_EMOJI（与 QUADRANT_COLOR / 中国习惯 红强绿弱 对齐）
    _corners = {
        "Q1": (xhi * 0.55, yhi * 0.55),
        "Q2": (-xhi * 0.55, yhi * 0.55),
        "Q3": (-xhi * 0.55, -yhi * 0.55),
        "Q4": (xhi * 0.55, -yhi * 0.55),
    }
    for _q, (_cx, _cy) in _corners.items():
        fig.add_annotation(x=_cx, y=_cy,
                           text=_HTML_QUADRANT_TITLE[_q],
                           font=dict(size=14, color=_HTML_QUADRANT_COLOR[_q]),
                           bgcolor="rgba(255,255,255,0.78)",
                           borderpad=5, showarrow=False)

    quadrant_summary_html = _build_quadrant_summary_html(df)
    table_html = build_improvement_html(improvement_table, industry_col)
    lineage_html = build_lineage_html(meta)
    chart_div = fig.to_html(
        full_html=False,
        include_plotlyjs=True,
        config={
            "responsive": True,
            "displaylogo": False,
            "scrollZoom": False,
            "modeBarButtonsToRemove": ["lasso2d", "select2d"],
        },
    )

    granularity_zh = {
        "daily": "日频",
        "weekly": "周频",
        "monthly": "月频",
    }.get(meta.get("pe_granularity"), str(meta.get("pe_granularity", "周频")))
    as_of = meta.get("t2") or meta.get("industry_asof") or "自动"
    pe_tag = (
        "PE {} · {}年窗口".format(granularity_zh, meta.get("pe_window_years", 2))
        if pe_col else "PE 分位未计算"
    )
    hero_tags = _build_tag_html([
        sw_label,
        "{} 个行业".format(len(df)),
        "截至 {}".format(as_of),
        "财报期 {}".format(latest_quarter),
        "技术回看 {} 日".format(lookback_days),
        pe_tag,
    ])
    chart_size_note = (
        "气泡越大代表 PETTM 历史分位越低"
        if pe_col else "未计算 PE 分位，气泡按成分股数显示"
    )
    safe_sw_label = html.escape(str(sw_label))
    safe_latest_quarter = html.escape(str(latest_quarter))

    full_html = f"""<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<meta name="color-scheme" content="light">
<title>{safe_sw_label}行业四象限监控 | {safe_latest_quarter}</title>
<style>{_REPORT_CSS}</style>
</head>
<body>
<div class="top-rule" aria-hidden="true"></div>
<main class="report-shell">
  <header class="report-hero">
    <div class="hero-kicker">INDUSTRY RESEARCH · QUADRANT MONITOR</div>
    <h1>{safe_sw_label}行业四象限监控报告</h1>
    <p class="hero-summary">以基本面和技术面双轴定位行业状态，并结合 PETTM 历史分位呈现估值位置。图表支持离线浏览与悬停查看行业明细。</p>
    <div class="tag-row">{hero_tags}</div>
  </header>
  <section class="report-section" aria-labelledby="overview-heading">
    <div class="section-heading">
      <div class="section-heading-copy">
        <div class="section-eyebrow">QUADRANT OVERVIEW</div>
        <h2 class="section-title" id="overview-heading">四象限概览</h2>
      </div>
    </div>
    <p class="section-lead">先看各象限的行业数量与占比，再进入散点图观察行业之间的相对位置。</p>
    <div class="quadrant-grid">{quadrant_summary_html}</div>
  </section>
  <section class="report-section report-section--soft" aria-labelledby="chart-heading">
    <div class="section-heading">
      <div class="section-heading-copy">
        <div class="section-eyebrow">QUADRANT MAP</div>
        <h2 class="section-title" id="chart-heading">基本面 × 技术面行业分布</h2>
      </div>
    </div>
    <p class="section-lead">横轴表示基本面强弱，纵轴表示技术面强弱；鼠标悬停可查看增速、动量、量能与 PE 分位。</p>
    <div class="chart-card">{chart_div}</div>
    <div class="chart-footnote">
      <span>{html.escape(chart_size_note)}</span>
      <span>分数为全市场截面标准化结果</span>
      <span>象限边界为 0</span>
    </div>
  </section>
  {table_html}
  {lineage_html}
</main>
</body>
</html>"""

    _atomic_write(str(output_path), full_html)
    logger.info("报告已保存: %s (%.1f MB)", output_path,
                os_path_size(str(output_path)) / 1024 / 1024)


def _atomic_write(path, content):
    import os
    tmp = path + ".tmp"
    try:
        with open(tmp, "w", encoding="utf-8") as f:
            f.write(content)
        os.replace(tmp, path)
    except OSError as e:
        raise config.OutputError("写入报告失败：{}（{}）".format(path, e))


def os_path_size(path):
    import os
    try:
        return os.path.getsize(path)
    except OSError:
        return 0


def build_improvement_html(df, industry_col):
    """构建「基本面较好 + 技术面转好」表格（industry_col 显式传入）。"""
    if df is None or len(df) == 0:
        return """
        <section class="report-section" aria-labelledby="improvement-heading">
          <div class="section-heading">
            <div class="section-heading-copy">
              <div class="section-eyebrow">TECHNICAL IMPROVEMENT</div>
              <h2 class="section-title" id="improvement-heading">基本面较好且技术面转好的行业</h2>
            </div>
          </div>
          <p class="section-lead">筛选基本面得分不低于 0、且技术面变化不低于 0 的行业。</p>
          <div class="empty-state">本期暂无满足条件的行业。</div>
        </section>
        """

    df = df.copy()
    df["排序分"] = df["技术面变化"] * config.IMPROVE_TECH_W + df["基本面得分"] * config.IMPROVE_FUND_W
    df = df.sort_values("排序分", ascending=False)

    rows = []
    for _, r in df.iterrows():
        pe = "{:.0f}%".format(r["PE分位数"]) if not pd.isna(r.get("PE分位数")) else "N/A"
        tech_delta = r["技术面变化"]
        abs_delta = r.get("技术面变化(绝对)", np.nan)
        arrow = "↑↑" if tech_delta > 0.5 else ("↑" if tech_delta > 0 else "↓")
        abs_str = "{:+.1f}pp".format(abs_delta) if pd.notna(abs_delta) else "N/A"
        industry_name = html.escape(str(r[industry_col]))
        rows.append(f"""
        <tr>
          <td>{industry_name}</td>
          <td>{r['成分股数']:.0f}</td>
          <td class="value-positive">{r['基本面得分']:+.2f}</td>
          <td>{r['上期技术得分']:+.2f} → {r['技术面得分']:+.2f}</td>
          <td class="value-hot">{arrow} {tech_delta:+.2f}</td>
          <td class="value-warm">{abs_str}</td>
          <td>{pe}</td>
          <td>{r['净利润增速中位数']:.1f}%</td>
          <td>{r['营收增速中位数']:.1f}%</td>
          <td>{r['价格动量中位数']:.1f}%</td>
        </tr>""")

    return f"""
    <section class="report-section" aria-labelledby="improvement-heading">
      <div class="section-heading">
        <div class="section-heading-copy">
          <div class="section-eyebrow">TECHNICAL IMPROVEMENT</div>
          <h2 class="section-title" id="improvement-heading">基本面较好且技术面转好的行业</h2>
        </div>
      </div>
      <p class="section-lead">基本面得分 ≥ 0 且技术面变化 ≥ 0；按“技术面相对变化 × 0.7 + 基本面得分 × 0.3”降序排列。</p>
      <p class="table-scroll-hint" aria-hidden="true">左右滑动表格，可查看全部字段 →</p>
      <div class="table-card" role="region" aria-label="改善行业明细，可横向滚动" tabindex="0">
        <table class="improvement-table">
          <thead>
            <tr>
              <th scope="col">行业</th><th scope="col">成分股</th><th scope="col">基本面得分</th>
              <th scope="col">技术面轨迹</th><th scope="col">改善幅度（相对）</th>
              <th scope="col">改善幅度（绝对）</th><th scope="col">PE 分位</th>
              <th scope="col">净利润增速</th><th scope="col">营收增速</th><th scope="col">价格动量</th>
            </tr>
          </thead>
          <tbody>{''.join(rows)}</tbody>
        </table>
      </div>
      <p class="table-note">相对改善为标准化分数之差；绝对改善为原始价格动量中位差（pp，百分点）。PE 分位为行业中位数 PETTM 在历史窗口中的连续分位，数值越高表示估值越高。</p>
    </section>
    """


def print_summary(df, industry_col):
    print("\n" + "=" * 70)
    print("{} 四象限监控 — 汇总".format(industry_col))
    print("=" * 70)
    for quad in QUADRANT_ORDER:
        label = QUADRANT_LABEL[quad]
        subset = df[df["象限"] == quad]
        count = len(subset)
        pct = count / len(df) * 100 if len(df) > 0 else 0
        print("\n{}: {} 个行业 ({:.1f}%)".format(label, count, pct))
        if count > 0:
            top = subset.nlargest(min(8, count),
                                  "技术面得分" if QUADRANT_KEY[quad] in ("相对较强", "情绪") else "基本面得分")
            for _, row in top.iterrows():
                pe_str = ("PE分位={:.0f}%".format(row["PE分位数"])
                          if "PE分位数" in row and not pd.isna(row["PE分位数"]) else "")
                print("  {:<18s} 基本面={:+.2f}  技术面={:+.2f}  {}".format(
                    str(row[industry_col]), row["基本面得分"], row["技术面得分"], pe_str))
    print("\n" + "=" * 70)


# ═══════════════════════════════════════════════════════════════
# Excel 底稿（D18）：多 sheet 覆盖底层数据
# ═══════════════════════════════════════════════════════════════
def build_excel(df, improvement, pe_pct, meta, industry_col, output_path):
    """导出行业得分全表 + 改善表 + 四象限汇总 + 数据血统 + PE 明细 到 xlsx。"""
    import os
    try:
        from openpyxl.styles import Font as _Font, PatternFill as _Fill, Alignment as _Align
    except Exception:
        raise config.OutputError("缺少 openpyxl，无法导出 Excel（pip install openpyxl）。")
    df = df.copy()
    if "PE分位数" not in df.columns:
        df["PE分位数"] = np.nan

    # 行业得分全表
    score_cols = [industry_col, "成分股数", "基本面得分", "技术面得分",
                  "净利润增速中位数", "营收增速中位数", "价格动量中位数", "量能变化中位数",
                  "PE分位数", "PE最新", "PE窗口低", "PE窗口高",
                  "技术面变化", "技术面变化(绝对)", "量能变化(绝对)", "技术面改善", "象限", "排序分"]
    score_cols = [c for c in score_cols if c in df.columns]
    score_tbl = df[score_cols].copy()
    score_tbl["技术面改善"] = score_tbl["技术面改善"].map({True: "是", False: "否"})

    # 四象限汇总
    summary_rows = []
    for quad in QUADRANT_ORDER:
        sub = df[df["象限"] == quad]
        summary_rows.append({
            "象限": QUADRANT_LABEL[quad],
            "行业数": len(sub),
            "占比": "{:.1f}%".format(len(sub) / len(df) * 100) if len(df) else "0%",
            "代表行业": "、".join(sub.nlargest(3, "基本面得分")[industry_col].astype(str)) if len(sub) else "",
        })
    summary_tbl = pd.DataFrame(summary_rows)

    # 数据血统
    lineage_rows = [
        ("行业层级", "{}（{}）".format(meta.get("sw_label"), meta.get("industry_col"))),
        ("财报期", "{} / 同比基准 {}".format(meta.get("latest_quarter"), meta.get("yoy_quarter"))),
        ("技术面截面", "T0={} T1={} T2={}".format(meta.get("t0"), meta.get("t1"), meta.get("t2"))),
        ("股票池", "候选 {} / 剔除 {} / 有效 {}".format(
            meta.get("universe_raw"), meta.get("excluded"), meta.get("universe"))),
        ("覆盖率", "行业{} 财务{} 技术面{} PE{}".format(
            _p(meta.get("cov_industry")), _p(meta.get("cov_financial")),
            _p(meta.get("cov_technical")), _p(meta.get("cov_pe")))),
        ("PE 口径", meta.get("pe_desc", "未计算")),
        ("缓存", _cache_lineage(meta)),
        ("生成时间", meta.get("generated_at", "?")),
        ("耗时(秒)", "{:.1f}".format(meta.get("elapsed", 0.0))),
    ]
    lineage_tbl = pd.DataFrame(lineage_rows, columns=["项目", "内容"])

    imp_tbl = improvement.copy() if improvement is not None and len(improvement) else pd.DataFrame()
    pe_tbl = pe_pct.copy() if pe_pct is not None and len(pe_pct) else pd.DataFrame()

    out = str(output_path)
    with pd.ExcelWriter(out, engine="openpyxl") as xw:
        summary_tbl.to_excel(xw, sheet_name="四象限汇总", index=False)
        score_tbl.to_excel(xw, sheet_name="行业得分", index=False)
        if len(imp_tbl):
            imp_tbl.to_excel(xw, sheet_name="改善行业", index=False)
        if len(pe_tbl):
            pe_tbl.to_excel(xw, sheet_name="PE分位明细", index=False)
        lineage_tbl.to_excel(xw, sheet_name="数据血统", index=False)
        _style_excel(xw, _Font, _Fill, _Align)
    logger.info("Excel 底稿已保存: %s", out)
    return out


def _p(v):
    return "N/A" if v is None else "{:.1%}".format(v)


# 通用符号剥离（PDF 用 simhei 等无 emoji 字形的字体时，必须先把
# 🔴🟡🟢🔵 等前缀去掉，否则会渲染成 □）
_EMOJI_RE = re.compile(
    r"[\U0001F300-\U0001FAFF\u2600-\u27BF\u2300-\u23FF\u2B00-\u2BFF]+",
    flags=re.UNICODE,
)


def _strip_emoji(s):
    """去掉字符串首部的 emoji / 符号前缀，返回纯中文部分（用于 PDF 表格）。"""
    if not s:
        return s
    return _EMOJI_RE.sub("", s).strip()


def _style_excel(xw, Font, Fill, Align):
    """CJK-aware formatting suitable for viewing and printing on blank PCs."""
    try:
        header_fill = Fill(start_color="2C3E50", end_color="2C3E50", fill_type="solid")
        for ws in xw.book.worksheets:
            for cell in ws[1]:
                cell.font = Font(bold=True, color="FFFFFF")
                cell.fill = header_fill
                cell.alignment = Align(horizontal="center", vertical="center")
            ws.auto_filter.ref = ws.dimensions
            ws.sheet_view.showGridLines = False
            ws.sheet_properties.pageSetUpPr.fitToPage = True
            ws.page_setup.fitToWidth, ws.page_setup.fitToHeight = 1, 0
            for col in ws.columns:
                width = max((sum(2 if ord(ch) > 255 else 1 for ch in str(c.value)) for c in col if c.value is not None), default=8)
                letter = col[0].column_letter
                ws.column_dimensions[letter].width = min(max(width + 2, 10), 34)
                for cell in col:
                    if isinstance(cell.value, float): cell.number_format = "0.00"
                    cell.alignment = Align(vertical="center", wrap_text=True)
            ws.freeze_panes = "A2"
    except Exception as e:
        logger.debug("Excel 样式跳过：%s", e)


# ═══════════════════════════════════════════════════════════════
# PDF 打印版（D18）：reportlab 原生绘制（无 HTML→PDF 外部依赖）
# ═══════════════════════════════════════════════════════════════
def _ensure_cjk_font():
    """注册支持中文的字体。

    优先使用系统自带的中文字体文件（TTF/OTF）。TTF 在 reportlab 的
    platypus（段落/表格）与 graphics（散点图文字）中均能正确渲染中文，
    彻底规避「STSong-Light 等 CID 字体在 graphics.String 下不显示」的通病。
    注册失败时回退 Helvetica（中文将显示为方框，但不会崩溃）。整个进程只注册一次。
    """
    global _CJK_FONT
    if _CJK_FONT is not None:
        return _CJK_FONT

    windir = os.environ.get("WINDIR", r"C:\Windows")
    font_dir = os.path.join(windir, "Fonts")
    # Do not package a font: prefer the standard Windows Microsoft YaHei,
    # then other common CJK fonts. Fail closed if none is installed.
    candidates = [
        (os.path.join(font_dir, "msyh.ttc"), 0),  # 微软雅黑
        (os.path.join(font_dir, "msyhbd.ttc"), 0),
        (os.path.join(font_dir, "simhei.ttf"), 0),
        (os.path.join(font_dir, "STXIHEI.TTF"), 0),
        (os.path.join(font_dir, "STSONG.TTF"), 0),
        (os.path.join(font_dir, "simfang.ttf"), 0),
        (os.path.join(font_dir, "simsun.ttc"), 0),
    ]
    try:
        from reportlab.pdfbase import pdfmetrics
        from reportlab.pdfbase.ttfonts import TTFont
        for path, idx in candidates:
            if not os.path.exists(path):
                continue
            try:
                if path.lower().endswith(".ttc"):
                    pdfmetrics.registerFont(TTFont("CJK", path, subfontIndex=idx))
                else:
                    pdfmetrics.registerFont(TTFont("CJK", path))
                _CJK_FONT = "CJK"
                logger.info("[PDF] 已注册中文 TTF 字体: %s", path)
                return _CJK_FONT
            except Exception as e:
                logger.debug("[PDF] TTF 候选失败 %s: %s", path, e)
    except Exception as e:
        logger.debug("[PDF] 加载 TTFont 模块失败: %s", e)

    raise config.OutputError("未找到可用的系统中文字体（优先微软雅黑）；拒绝生成可能乱码的 PDF。")


def build_pdf(df, improvement, meta, industry_col, output_path):
    """导出打印版 PDF：标题 + 数据血统 + 四象限汇总 + 改善表 + 象限散点图。"""
    try:
        from reportlab.lib.pagesizes import A4 as _A4
        from reportlab.lib import colors as _colors
        from reportlab.lib.units import mm as _mm
        from reportlab.platypus import (SimpleDocTemplate as _SDT, Paragraph as _P,
                                         Spacer as _Sp, Table as _T, TableStyle as _TS)
        from reportlab.lib.styles import getSampleStyleSheet as _gss, ParagraphStyle as _PS
        from reportlab.graphics.shapes import (Drawing as _DW, Circle as _C,
                                               Line as _L, Rect as _R, String as _S)
    except Exception:
        raise config.OutputError("缺少 reportlab，无法导出 PDF（pip install reportlab）。")

    out = str(output_path)
    doc = _SDT(out, pagesize=_A4)
    f = _ensure_cjk_font()  # 中文矢量字体，避免乱码
    ss = _gss()
    h1 = _PS("h1", parent=ss["Title"], fontSize=18, textColor=_colors.HexColor("#2c3e50"), fontName=f)
    body = _PS("body", parent=ss["Normal"], fontSize=9, leading=13, fontName=f)
    sub = _PS("sub", parent=ss["Normal"], fontSize=10, textColor=_colors.HexColor("#555555"), fontName=f)

    story = []
    story.append(_P("{}行业四象限监控报告".format(meta.get("sw_label", "申万行业")), h1))
    story.append(_P("财报期 {} ｜ 技术回看 {} 日 ｜ 生成于 {}".format(
        meta.get("latest_quarter", "?"), meta.get("lookback", "?"),
        meta.get("generated_at", "?")), sub))
    story.append(_Sp(0, 6))

    # 数据血统
    lineage = [
        ["行业层级", "{}（{}）".format(meta.get("sw_label"), meta.get("industry_col"))],
        ["财报期", "{} / 同比 {}".format(meta.get("latest_quarter"), meta.get("yoy_quarter"))],
        ["基本面口径", "{}（TTM 锚点 {} / TTM@{}）".format(
            meta.get("fund_method", "累计同比"), meta.get("ttm_anchor"), meta.get("ttm_basis"))],
        ["股票池", "候选 {} / 剔除 {} / 有效 {}".format(
            meta.get("universe_raw"), meta.get("excluded"), meta.get("universe"))],
        ["覆盖率", "行业{} 财务{} 技术面{} PE{}".format(
            _p(meta.get("cov_industry")), _p(meta.get("cov_financial")),
            _p(meta.get("cov_technical")), _p(meta.get("cov_pe")))],
        ["PE 口径", meta.get("pe_desc", "未计算")],
        ["缓存", _cache_lineage(meta)],
    ]
    lineage = [[_P(str(a), body), _P(str(b), body)] for a, b in lineage]
    t = _T(lineage, colWidths=[28 * _mm, 150 * _mm], repeatRows=0)
    t.setStyle(_TS([
        ("FONTSIZE", (0, 0), (-1, -1), 8),
        ("FONTNAME", (0, 0), (-1, -1), f),
        ("TEXTCOLOR", (0, 0), (0, -1), _colors.HexColor("#666666")),
        ("GRID", (0, 0), (-1, -1), 0.4, _colors.HexColor("#dddddd")),
        ("BACKGROUND", (0, 0), (0, -1), _colors.HexColor("#f0f3f6")),
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
    ]))
    story.append(_P("数据血统", sub))
    story.append(t)
    story.append(_Sp(0, 8))

    # 四象限汇总（PDF 中剥掉 emoji 前缀，避免 simhei 等字体无字形时出现 □）
    qrows = [["象限", "行业数", "占比", "代表行业"]]
    for quad in QUADRANT_ORDER:
        sub_df = df[df["象限"] == quad]
        qrows.append([
            _strip_emoji(QUADRANT_LABEL[quad]), str(len(sub_df)),
            "{:.1f}%".format(len(sub_df) / len(df) * 100) if len(df) else "0%",
            "、".join(sub_df.nlargest(3, "基本面得分")[industry_col].astype(str)) if len(sub_df) else "",
        ])
    qt = _T(qrows, colWidths=[40 * _mm, 18 * _mm, 18 * _mm, 102 * _mm], repeatRows=1)
    qt.setStyle(_TS([
        ("FONTSIZE", (0, 0), (-1, -1), 8),
        ("FONTNAME", (0, 0), (-1, -1), f),
        ("BACKGROUND", (0, 0), (-1, 0), _colors.HexColor("#2c3e50")),
        ("TEXTCOLOR", (0, 0), (-1, 0), _colors.white),
        ("GRID", (0, 0), (-1, -1), 0.4, _colors.HexColor("#dddddd")),
    ]))
    story.append(_P("四象限汇总", sub))
    story.append(qt)
    story.append(_Sp(0, 8))

    # 改善表
    if improvement is not None and len(improvement):
        irows = [["行业", "基本面", "技术轨迹", "改善(相对)", "PE分位"]]
        for _, r in improvement.head(20).iterrows():
            pe = "{:.0f}%".format(r["PE分位数"]) if not pd.isna(r.get("PE分位数")) else "N/A"
            irows.append([
                str(r[industry_col]), "{:+.2f}".format(r["基本面得分"]),
                "{:+.2f}→{:+.2f}".format(r["上期技术得分"], r["技术面得分"]),
                "{:+.2f}".format(r["技术面变化"]), pe,
            ])
        it = _T(irows, colWidths=[40 * _mm, 20 * _mm, 34 * _mm, 26 * _mm, 20 * _mm], repeatRows=1)
        it.setStyle(_TS([
            ("FONTSIZE", (0, 0), (-1, -1), 8),
            ("FONTNAME", (0, 0), (-1, -1), f),
            ("BACKGROUND", (0, 0), (-1, 0), _colors.HexColor("#2c3e50")),
            ("TEXTCOLOR", (0, 0), (-1, 0), _colors.white),
            ("GRID", (0, 0), (-1, -1), 0.4, _colors.HexColor("#dddddd")),
        ]))
        story.append(_P("基本面较好 + 技术面转好（Top {}）".format(min(20, len(improvement))), sub))
        story.append(it)
        story.append(_Sp(0, 8))

    # 象限散点图（reportlab 原生绘制）
    story.append(_P("四象限散点", sub))
    story.append(_draw_quadrant(df, industry_col, show_labels=(meta.get("sw_level") == "1")))

    doc.build(story)
    logger.info("PDF 打印版已保存: %s", out)
    return out


def _draw_quadrant(df, industry_col, show_labels=True):
    """用 reportlab 原生图形画象限散点（不依赖 plotly/matplotlib）。

    所有文字（轴标题、象限角标、行业名）均使用已注册的中文字体；
    在 TTF 字体下可正确渲染（CID 字体在 graphics.String 中不可见）。
    show_labels=False 时仅画气泡、不画逐点行业名（二级/三级行业避免重叠杂乱）。
    """
    from reportlab.graphics.shapes import (Drawing as _DW, Circle as _C,
                                           Line as _L, Rect as _R, String as _S)
    from reportlab.lib import colors as _colors

    W, H = 490, 412
    d = _DW(W, H)
    f = _ensure_cjk_font()  # 图表全部文字统一走中文字体

    # 绘图区边距（为轴标题留出空间）
    left, right = 46, W - 16
    bottom, top = 30, H - 22
    cx, cy = (left + right) / 2.0, (bottom + top) / 2.0

    # 背景象限
    bg = {"Q1": "#fdecea", "Q2": "#fef9e7", "Q3": "#eafaf1", "Q4": "#eaf2fb"}
    quads_pos = {
        "Q1": (cx, cy, right - cx, top - cy),
        "Q2": (left, cy, cx - left, top - cy),
        "Q3": (left, bottom, cx - left, cy - bottom),
        "Q4": (cx, bottom, right - cx, cy - bottom),
    }
    for q, (x0, y0, w, h) in quads_pos.items():
        d.add(_R(x0, y0, w, h, fillColor=_colors.HexColor(bg[q]),
                 strokeColor=None, strokeWidth=0))

    # 轴
    d.add(_L(cx, bottom, cx, top, strokeColor=_colors.grey, strokeDashArray=[3, 3]))
    d.add(_L(left, cy, right, cy, strokeColor=_colors.grey, strokeDashArray=[3, 3]))

    # 坐标映射
    xmin, xmax = -1.0, max(float(df["基本面得分"].max()), 1.0)
    y_abs = max(abs(float(df["技术面得分"].max())), abs(float(df["技术面得分"].min())), 1.0)
    ymin, ymax = -y_abs, y_abs

    def mx(v):
        return left + (v - xmin) / (xmax - xmin) * (right - left)

    def my(v):
        return bottom + (v - ymin) / (ymax - ymin) * (top - bottom)

    # 散点 + 行业名标签（右半区标签放左侧，避免出界）
    for _, r in df.iterrows():
        quad = r["象限"]
        x = mx(r["基本面得分"])
        y = my(r["技术面得分"])
        rad = 4
        if "PE分位数" in r and not pd.isna(r["PE分位数"]):
            # 半径取反：PE 越低半径越大（与 HTML 气泡一致）
            rad = 3 + (((BUBBLE_MIN + BUBBLE_MAX) - r["PE分位数"]) / 100.0) * 5
        d.add(_C(x, y, rad, fillColor=_colors.HexColor(config.QUADRANT_COLOR[quad]),
                 strokeColor=_colors.white, strokeWidth=0.6))
        if show_labels:
            name = str(r[industry_col])
            tw = len(name) * 6.5  # 近似文字宽度
            if x > cx:
                lx, anchor = x - rad - 1.5 - tw, "end"
            else:
                lx, anchor = x + rad + 1.5, "start"
            d.add(_S(lx, y + 1.0, name, fontSize=6.5, fontName=f,
                     fillColor=_colors.HexColor("#333333"), textAnchor=anchor))

    # 象限角标（中文 + 对应颜色，TTF 下可见）
    _corner = {
        "Q1": (cx + (right-cx) * 0.55, cy + (top-cy) * 0.78),
        "Q2": (left + (cx-left) * 0.08, cy + (top-cy) * 0.78),
        "Q3": (left + (cx-left) * 0.08, bottom + (cy-bottom) * 0.08),
        "Q4": (cx + (right-cx) * 0.55, bottom + (cy-bottom) * 0.08),
    }
    for q, (lx, ly) in _corner.items():
        d.add(_S(lx, ly, config.QUADRANT_KEY[q], fontSize=12,
                 fontName=f, fillColor=_colors.HexColor(config.QUADRANT_COLOR[q])))

    # 轴标题（明确强弱方向，避免 graphics 下文字缺失造成“无标识”）
    d.add(_S(cx, bottom - 16, "基本面得分（左弱 → 右强）", fontSize=9,
             fontName=f, fillColor=_colors.HexColor("#555555"), textAnchor="middle"))
    d.add(_S(cx, top + 4, "技术面得分（下弱 ↑ 上强）", fontSize=9,
             fontName=f, fillColor=_colors.HexColor("#555555"), textAnchor="middle"))
    return d
