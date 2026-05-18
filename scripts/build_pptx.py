"""Generate the 42-page PPTX:
《资产配置视角下的公募FOF投资新思路》

依赖: python-pptx, charts.py 生成的 PNG（位于 charts/ 下）
输出: output/FOF资产配置新思路.pptx
"""

from __future__ import annotations

import os
from pathlib import Path
from typing import Iterable

from pptx import Presentation
from pptx.dml.color import RGBColor
from pptx.enum.shapes import MSO_SHAPE
from pptx.enum.text import PP_ALIGN, MSO_ANCHOR
from pptx.util import Cm, Emu, Pt

PROJECT_ROOT = Path(__file__).resolve().parent.parent
CHARTS_DIR = PROJECT_ROOT / "charts"
OUTPUT_DIR = PROJECT_ROOT / "output"
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
OUTPUT_FILE = OUTPUT_DIR / "FOF资产配置新思路.pptx"

# Theme colors -----------------------------------------------------------------
BG_DARK   = RGBColor(0x0E, 0x1A, 0x2B)
BG_PANEL  = RGBColor(0x16, 0x27, 0x3D)
BG_PANEL2 = RGBColor(0x1B, 0x2F, 0x4A)
TXT_MAIN  = RGBColor(0xF2, 0xF4, 0xF7)
TXT_DIM   = RGBColor(0xB6, 0xC4, 0xD6)
ACCENT    = RGBColor(0xE0, 0xB5, 0x74)   # gold
ACCENT_2  = RGBColor(0x7B, 0xB7, 0xE8)   # blue
ACCENT_3  = RGBColor(0x7F, 0xCB, 0xA4)   # green
ACCENT_4  = RGBColor(0xE6, 0x7D, 0x7D)   # red
DIVIDER   = RGBColor(0x32, 0x48, 0x63)

FONT_HEAD = "微软雅黑"
FONT_BODY = "微软雅黑"

TOTAL_PAGES = 42
TITLE_FULL  = "资产配置视角下的公募FOF投资新思路"

# Slide size: 16:9 widescreen --------------------------------------------------
SLIDE_W = Cm(33.867)
SLIDE_H = Cm(19.05)

CHAPTERS = [
    ("一", "宏观新常态下的配置困局"),
    ("二", "资产配置理论的演进与公募FOF的位置"),
    ("三", "全球多元资产研究与对比"),
    ("四", "组合管理：风险预算 / 风险控制 / 收益拆解"),
    ("五", "公募FOF投资新思路（6条）"),
    ("六", "公募FOF 在银行场景的落地"),
    ("七", "案例与展望"),
]


# Helpers ----------------------------------------------------------------------

def _set_solid_fill(shape, rgb: RGBColor) -> None:
    shape.fill.solid()
    shape.fill.fore_color.rgb = rgb
    shape.line.fill.background()


def _add_rect(slide, x, y, w, h, rgb: RGBColor):
    shape = slide.shapes.add_shape(MSO_SHAPE.RECTANGLE, x, y, w, h)
    _set_solid_fill(shape, rgb)
    return shape


def _add_text(
    slide,
    text: str,
    x, y, w, h,
    *,
    size: int = 18,
    color: RGBColor = TXT_MAIN,
    bold: bool = False,
    align=PP_ALIGN.LEFT,
    anchor=MSO_ANCHOR.TOP,
    font: str = FONT_BODY,
):
    box = slide.shapes.add_textbox(x, y, w, h)
    tf = box.text_frame
    tf.margin_left = Cm(0.1)
    tf.margin_right = Cm(0.1)
    tf.margin_top = Cm(0.05)
    tf.margin_bottom = Cm(0.05)
    tf.word_wrap = True
    tf.vertical_anchor = anchor
    p = tf.paragraphs[0]
    p.alignment = align
    run = p.add_run()
    run.text = text
    run.font.name = font
    run.font.size = Pt(size)
    run.font.bold = bold
    run.font.color.rgb = color
    return box


def _add_multiline(
    slide,
    lines: Iterable[str],
    x, y, w, h,
    *,
    size: int = 16,
    color: RGBColor = TXT_MAIN,
    bullet_color: RGBColor = ACCENT,
    line_space: float = 1.35,
    font: str = FONT_BODY,
):
    box = slide.shapes.add_textbox(x, y, w, h)
    tf = box.text_frame
    tf.word_wrap = True
    tf.margin_left = Cm(0.2)
    tf.margin_right = Cm(0.2)
    tf.margin_top = Cm(0.1)
    tf.margin_bottom = Cm(0.1)
    lines = list(lines)
    for i, line in enumerate(lines):
        p = tf.paragraphs[0] if i == 0 else tf.add_paragraph()
        p.alignment = PP_ALIGN.LEFT
        p.line_spacing = line_space
        # bullet square
        r1 = p.add_run()
        r1.text = "■  "
        r1.font.name = font
        r1.font.size = Pt(size)
        r1.font.color.rgb = bullet_color
        r1.font.bold = True
        # main text
        r2 = p.add_run()
        r2.text = line
        r2.font.name = font
        r2.font.size = Pt(size)
        r2.font.color.rgb = color
    return box


def _set_slide_background(slide, rgb: RGBColor = BG_DARK) -> None:
    bg = slide.shapes.add_shape(MSO_SHAPE.RECTANGLE, 0, 0, SLIDE_W, SLIDE_H)
    _set_solid_fill(bg, rgb)
    # send to back
    spTree = bg._element.getparent()
    spTree.remove(bg._element)
    spTree.insert(2, bg._element)


def _add_header_footer(slide, chapter_label: str, page_idx: int) -> None:
    # Header bar
    _add_text(
        slide, chapter_label,
        Cm(1.2), Cm(0.55), Cm(20), Cm(0.7),
        size=11, color=TXT_DIM, font=FONT_HEAD,
    )
    # accent bar under header
    bar = slide.shapes.add_shape(MSO_SHAPE.RECTANGLE,
                                 Cm(1.2), Cm(1.25), Cm(2.5), Cm(0.10))
    _set_solid_fill(bar, ACCENT)

    # Footer text (left)
    _add_text(
        slide, TITLE_FULL,
        Cm(1.2), SLIDE_H - Cm(0.95), Cm(22), Cm(0.55),
        size=10, color=TXT_DIM, font=FONT_BODY,
    )
    # Footer page (right)
    _add_text(
        slide, f"{page_idx} / {TOTAL_PAGES}",
        SLIDE_W - Cm(4.5), SLIDE_H - Cm(0.95), Cm(3.3), Cm(0.55),
        size=10, color=TXT_DIM, align=PP_ALIGN.RIGHT, font=FONT_BODY,
    )


def _add_main_title(slide, title: str, subtitle: str | None = None) -> None:
    _add_text(
        slide, title,
        Cm(1.2), Cm(1.6), Cm(31), Cm(1.6),
        size=26, color=TXT_MAIN, bold=True, font=FONT_HEAD,
    )
    if subtitle:
        _add_text(
            slide, subtitle,
            Cm(1.2), Cm(3.0), Cm(31), Cm(0.9),
            size=14, color=ACCENT, font=FONT_BODY,
        )


# Slide builders ---------------------------------------------------------------

def add_blank(prs: Presentation):
    return prs.slides.add_slide(prs.slide_layouts[6])


def make_title_slide(prs: Presentation) -> None:
    slide = add_blank(prs)
    _set_slide_background(slide, BG_DARK)

    # Left vertical accent band
    band = slide.shapes.add_shape(MSO_SHAPE.RECTANGLE,
                                  Cm(0), Cm(0), Cm(0.6), SLIDE_H)
    _set_solid_fill(band, ACCENT)

    # Soft panel right
    panel = slide.shapes.add_shape(MSO_SHAPE.RECTANGLE,
                                   Cm(18), Cm(2.5), Cm(14.5), Cm(14))
    _set_solid_fill(panel, BG_PANEL)

    # Top mini-label
    _add_text(
        slide, "ASSET  ALLOCATION  ·  FOF  ·  2026",
        Cm(2.0), Cm(2.4), Cm(20), Cm(0.8),
        size=12, color=ACCENT, font=FONT_HEAD, bold=True,
    )

    # Main title
    _add_text(
        slide, "资产配置视角下的",
        Cm(2.0), Cm(4.5), Cm(22), Cm(2.0),
        size=40, color=TXT_MAIN, bold=True, font=FONT_HEAD,
    )
    _add_text(
        slide, "公募FOF投资新思路",
        Cm(2.0), Cm(6.7), Cm(22), Cm(2.3),
        size=46, color=ACCENT, bold=True, font=FONT_HEAD,
    )

    # Divider
    div = slide.shapes.add_shape(MSO_SHAPE.RECTANGLE,
                                 Cm(2.0), Cm(9.7), Cm(8), Cm(0.08))
    _set_solid_fill(div, ACCENT)

    # Subtitle: double main lines
    _add_text(
        slide, "双主线：全球多元资产研究  ×  组合管理（风险预算 / 风险控制 / 收益拆解）",
        Cm(2.0), Cm(10.2), Cm(28), Cm(1.0),
        size=16, color=TXT_DIM, font=FONT_BODY,
    )

    # Right panel content
    _add_text(
        slide, "演讲提纲",
        Cm(18.7), Cm(3.0), Cm(13), Cm(0.9),
        size=14, color=ACCENT, bold=True, font=FONT_HEAD,
    )
    panel_lines = [
        "宏观新常态下的配置困局",
        "资产配置理论与公募FOF定位",
        "全球多元资产研究与对比",
        "组合管理：风险预算 / 控制 / 归因",
        "公募FOF投资 6 条新思路",
        "银行场景下的落地路径",
        "案例与展望",
    ]
    _add_multiline(
        slide, panel_lines,
        Cm(18.7), Cm(4.0), Cm(13.0), Cm(11),
        size=14, color=TXT_MAIN, bullet_color=ACCENT, line_space=1.45,
    )

    # Bottom presenter line
    _add_text(
        slide, "面向 银行总部  |  分享时长 约 60 分钟  |  共 42 页",
        Cm(2.0), SLIDE_H - Cm(2.2), Cm(28), Cm(0.8),
        size=12, color=TXT_DIM, font=FONT_BODY,
    )
    _add_text(
        slide, "演讲人：　　　　　　　　　　　日期：2026",
        Cm(2.0), SLIDE_H - Cm(1.3), Cm(28), Cm(0.7),
        size=11, color=TXT_DIM, font=FONT_BODY,
    )


def make_toc_slide(prs: Presentation) -> None:
    slide = add_blank(prs)
    _set_slide_background(slide)
    _add_header_footer(slide, "目录  CONTENTS", 2)
    _add_main_title(slide, "目录", "Seven Chapters · 42 Pages · ≈ 60 min")

    rows = CHAPTERS + [("　", "结语 + Q&A")]

    # Two columns
    col_w = Cm(15.0)
    col_h = Cm(1.6)
    start_y = Cm(4.6)
    gap_y   = Cm(1.7)

    for i, (num, name) in enumerate(rows):
        col = i // 4
        row = i % 4
        x = Cm(1.5) + col * Cm(16.5)
        y = start_y + row * gap_y

        # number block
        n = slide.shapes.add_shape(MSO_SHAPE.RECTANGLE, x, y, Cm(1.6), col_h)
        _set_solid_fill(n, BG_PANEL)
        _add_text(slide, num, x, y, Cm(1.6), col_h,
                  size=22, color=ACCENT, bold=True, align=PP_ALIGN.CENTER,
                  anchor=MSO_ANCHOR.MIDDLE, font=FONT_HEAD)
        # name block
        nb = slide.shapes.add_shape(MSO_SHAPE.RECTANGLE,
                                    x + Cm(1.7), y, col_w - Cm(1.7), col_h)
        _set_solid_fill(nb, BG_PANEL2)
        _add_text(slide, name,
                  x + Cm(1.9), y, col_w - Cm(2.0), col_h,
                  size=15, color=TXT_MAIN, anchor=MSO_ANCHOR.MIDDLE,
                  font=FONT_BODY)


def make_section_divider(prs: Presentation, chapter_idx: int,
                          subtitle: str, page_idx: int) -> None:
    num, name = CHAPTERS[chapter_idx]
    slide = add_blank(prs)
    _set_slide_background(slide, BG_DARK)
    # left band
    band = slide.shapes.add_shape(MSO_SHAPE.RECTANGLE,
                                  Cm(0), Cm(0), Cm(0.6), SLIDE_H)
    _set_solid_fill(band, ACCENT)

    # Huge chapter mark
    _add_text(
        slide, f"第 {num} 章",
        Cm(2.5), Cm(4.5), Cm(12), Cm(2.0),
        size=22, color=ACCENT, bold=True, font=FONT_HEAD,
    )
    _add_text(
        slide, name,
        Cm(2.5), Cm(6.5), Cm(28), Cm(3.0),
        size=40, color=TXT_MAIN, bold=True, font=FONT_HEAD,
    )
    # divider
    div = slide.shapes.add_shape(MSO_SHAPE.RECTANGLE,
                                 Cm(2.5), Cm(10.5), Cm(6), Cm(0.08))
    _set_solid_fill(div, ACCENT)
    _add_text(
        slide, subtitle,
        Cm(2.5), Cm(11.0), Cm(28), Cm(2.0),
        size=16, color=TXT_DIM, font=FONT_BODY,
    )
    _add_text(
        slide, f"CHAPTER  0{chapter_idx + 1}",
        Cm(2.5), SLIDE_H - Cm(2.3), Cm(20), Cm(0.8),
        size=11, color=DIVIDER, font=FONT_HEAD, bold=True,
    )
    # page no
    _add_text(
        slide, f"{page_idx} / {TOTAL_PAGES}",
        SLIDE_W - Cm(4.5), SLIDE_H - Cm(0.95), Cm(3.3), Cm(0.55),
        size=10, color=TXT_DIM, align=PP_ALIGN.RIGHT, font=FONT_BODY,
    )


def make_content_slide(
    prs: Presentation,
    chapter_label: str,
    title: str,
    subtitle: str | None,
    bullets: list[str],
    page_idx: int,
    *,
    image: str | None = None,
    image_width_cm: float = 18.0,
    image_right: bool = True,
    footnote: str | None = None,
) -> None:
    slide = add_blank(prs)
    _set_slide_background(slide)
    _add_header_footer(slide, chapter_label, page_idx)
    _add_main_title(slide, title, subtitle)

    body_top = Cm(4.7)
    body_h = SLIDE_H - Cm(6.5)

    if image:
        img_path = CHARTS_DIR / image
        if image_right:
            text_x, text_w = Cm(1.2), Cm(12.5)
            img_x = Cm(14.2)
        else:
            text_x, text_w = Cm(16.5), Cm(15.5)
            img_x = Cm(1.2)
        img_w = Cm(image_width_cm)
        # add image (height auto, but clamp later)
        pic = slide.shapes.add_picture(str(img_path), img_x, body_top, width=img_w)
        # if too tall, scale down
        if pic.height > body_h:
            ratio = body_h / pic.height
            pic.height = int(pic.height * ratio)
            pic.width = int(pic.width * ratio)
        _add_multiline(
            slide, bullets,
            text_x, body_top, text_w, body_h,
            size=14, line_space=1.45,
        )
    else:
        _add_multiline(
            slide, bullets,
            Cm(1.2), body_top, SLIDE_W - Cm(2.4), body_h,
            size=17, line_space=1.55,
        )

    if footnote:
        _add_text(
            slide, footnote,
            Cm(1.2), SLIDE_H - Cm(1.6), Cm(31), Cm(0.6),
            size=10, color=TXT_DIM, font=FONT_BODY,
        )


def make_table_slide(
    prs: Presentation,
    chapter_label: str,
    title: str,
    subtitle: str | None,
    headers: list[str],
    rows: list[list[str]],
    page_idx: int,
    *,
    col_widths_cm: list[float] | None = None,
    footnote: str | None = None,
    intro: str | None = None,
) -> None:
    slide = add_blank(prs)
    _set_slide_background(slide)
    _add_header_footer(slide, chapter_label, page_idx)
    _add_main_title(slide, title, subtitle)

    top = Cm(4.6)
    if intro:
        _add_text(
            slide, intro,
            Cm(1.2), top, SLIDE_W - Cm(2.4), Cm(1.3),
            size=13, color=TXT_DIM, font=FONT_BODY,
        )
        top = top + Cm(1.4)

    n_cols = len(headers)
    n_rows = len(rows) + 1
    table_w = SLIDE_W - Cm(2.4)
    table_h = Cm(min(11, 0.9 + 0.78 * n_rows))

    tbl_shape = slide.shapes.add_table(n_rows, n_cols, Cm(1.2), top,
                                       table_w, table_h)
    tbl = tbl_shape.table

    # set column widths
    if col_widths_cm and len(col_widths_cm) == n_cols:
        total = sum(col_widths_cm)
        for i, cw in enumerate(col_widths_cm):
            tbl.columns[i].width = int(table_w * (cw / total))

    # header row
    for i, h in enumerate(headers):
        cell = tbl.cell(0, i)
        cell.fill.solid()
        cell.fill.fore_color.rgb = ACCENT
        tf = cell.text_frame
        tf.word_wrap = True
        tf.margin_left = Cm(0.15)
        tf.margin_right = Cm(0.15)
        tf.margin_top = Cm(0.08)
        tf.margin_bottom = Cm(0.08)
        p = tf.paragraphs[0]
        p.alignment = PP_ALIGN.CENTER
        p.text = ""
        run = p.add_run()
        run.text = h
        run.font.name = FONT_HEAD
        run.font.size = Pt(13)
        run.font.bold = True
        run.font.color.rgb = BG_DARK

    # body rows
    for ri, row in enumerate(rows, start=1):
        row_color = BG_PANEL if ri % 2 == 1 else BG_PANEL2
        for ci, val in enumerate(row):
            cell = tbl.cell(ri, ci)
            cell.fill.solid()
            cell.fill.fore_color.rgb = row_color
            tf = cell.text_frame
            tf.word_wrap = True
            tf.margin_left = Cm(0.18)
            tf.margin_right = Cm(0.15)
            tf.margin_top = Cm(0.06)
            tf.margin_bottom = Cm(0.06)
            p = tf.paragraphs[0]
            p.alignment = PP_ALIGN.LEFT if ci == 0 else PP_ALIGN.LEFT
            p.text = ""
            run = p.add_run()
            run.text = val
            run.font.name = FONT_BODY
            run.font.size = Pt(11.5)
            run.font.color.rgb = TXT_MAIN
            if ci == 0:
                run.font.bold = True
                run.font.color.rgb = ACCENT

    if footnote:
        _add_text(
            slide, footnote,
            Cm(1.2), SLIDE_H - Cm(1.6), Cm(31), Cm(0.6),
            size=10, color=TXT_DIM, font=FONT_BODY,
        )


def make_end_slide(prs: Presentation, page_idx: int) -> None:
    slide = add_blank(prs)
    _set_slide_background(slide, BG_DARK)
    # decorative
    panel = slide.shapes.add_shape(MSO_SHAPE.RECTANGLE,
                                   Cm(0), Cm(7.5), SLIDE_W, Cm(4.0))
    _set_solid_fill(panel, BG_PANEL)

    _add_text(
        slide, "Q & A",
        Cm(0), Cm(8.0), SLIDE_W, Cm(3.0),
        size=80, color=ACCENT, bold=True,
        align=PP_ALIGN.CENTER, anchor=MSO_ANCHOR.MIDDLE,
        font=FONT_HEAD,
    )
    _add_text(
        slide, "全球多元资产  ×  风险预算驱动的组合管理 ——  公募FOF 的下一个十年",
        Cm(0), Cm(12.5), SLIDE_W, Cm(1.2),
        size=18, color=TXT_MAIN, align=PP_ALIGN.CENTER, font=FONT_BODY,
    )
    _add_text(
        slide, "感谢聆听  ·  欢迎指正",
        Cm(0), Cm(14.2), SLIDE_W, Cm(1.0),
        size=14, color=TXT_DIM, align=PP_ALIGN.CENTER, font=FONT_BODY,
    )
    _add_text(
        slide, f"{page_idx} / {TOTAL_PAGES}",
        SLIDE_W - Cm(4.5), SLIDE_H - Cm(0.95), Cm(3.3), Cm(0.55),
        size=10, color=TXT_DIM, align=PP_ALIGN.RIGHT, font=FONT_BODY,
    )


# Main composition -------------------------------------------------------------

def build() -> None:
    prs = Presentation()
    prs.slide_width = SLIDE_W
    prs.slide_height = SLIDE_H

    # P1
    make_title_slide(prs)
    # P2
    make_toc_slide(prs)

    # ========== Chapter 1 ==========
    ch1 = "第一章  宏观新常态下的配置困局"
    # P3
    make_content_slide(
        prs, ch1,
        "全球宏观新常态：旧范式的失效",
        "低增长 · 再通胀 · 利率高位 · 地缘碎片化",
        [
            "潜在增速下移：全球GDP长期中枢从 3.5% 下调至 2.6%—2.8%",
            "再通胀压力反复：去全球化、能源转型、薪资黏性共同抬升通胀中枢",
            "地缘政治碎片化：供应链区域化重构，安全溢价取代效率溢价",
            "主要经济体利率中枢明显抬升，并在高位震荡，"
            "2022 年股债负相关失效",
            "单一资产 / 单一市场的“长牛”叙事被打破 → 多元化成为必选项",
        ],
        page_idx=3,
    )
    # P4
    make_content_slide(
        prs, ch1,
        "中国宏观与资产环境的三大切换",
        "地产链转型 · 利率中枢下移 · 居民资产再平衡",
        [
            "地产链转型：房地产从居民资产负债表核心位置后撤，"
            "存量博弈替代增量驱动",
            "无风险利率中枢下移：10Y 国债收益率 2.0%—2.5%，"
            "传统理财难以满足客户回报预期",
            "居民资产再平衡：从存款 / 房产向金融资产迁移，"
            "未来 5 年潜在迁移规模数十万亿",
            "公募基金、ETF、REITs、QDII 等工具持续丰富，"
            "FOF 是最适合承接的“一站式”载体",
            "对银行渠道而言：财富管理转型的核心是“配置型解决方案”",
        ],
        page_idx=4,
    )
    # P5 - chart
    make_content_slide(
        prs, ch1,
        "大类资产长期画像（2010–2025）",
        "单一资产的“可行域”受限，需要全球化与另类化扩边界",
        [
            "海外权益（标普 / 纳指）长期回报显著高于沪深300，"
            "且波动并未明显更高",
            "黄金的“收益—波动”性价比并不差，"
            "且与股债的相关性都很低",
            "债券类资产波动低但回报有限，"
            "单靠债券难以匹配理财客户的目标回报",
            "若只用国内股债，组合的有效前沿"
            "明显落后于全球多元配置",
            "结论：扩边界的两个方向 = 全球化 + 另类化",
        ],
        image="chart_asset_long_term.png",
        image_right=True,
        image_width_cm=18.0,
        footnote="数据来源：基于公开市场指数口径估算，仅供示意",
        page_idx=5,
    )
    # P6
    make_content_slide(
        prs, ch1,
        "单一资产 / 单一基金的困境 → FOF 与多元配置的必然性",
        "回答“靠天吃饭”与“靠人吃饭”两个问题",
        [
            "单一资产 → “靠天吃饭”：宏观情景一变，组合即遭重创",
            "单一基金 → “靠人吃饭”：α 集中暴露于单一管理人，风格漂移、规模冲击难以规避",
            "多元资产配置：在“天”的维度上分散风险来源",
            "FOF 双层结构：在“人”的维度上分散管理人 α 风险",
            "全球 FOF 规模超 3 万亿美元，国内仅 1500 亿元，"
            "渗透率仅为美国市场的 1/30，潜在空间巨大",
        ],
        page_idx=6,
    )

    # ========== Chapter 2 ==========
    ch2 = "第二章  资产配置理论的演进与公募FOF的位置"
    # P7
    make_content_slide(
        prs, ch2,
        "资产配置理论的演进脉络",
        "从均值方差 → 风险平价 → 因子投资 → 目标日期 / 目标风险",
        [
            "1952 年 Markowitz 均值方差：现代资产配置的起点，"
            "但对预期收益估计极度敏感",
            "1990 年代 Black-Litterman：引入主观观点，"
            "解决“极端权重”问题",
            "2005 年前后 桥水 全天候 / 风险平价：从“资金预算”转向“风险预算”",
            "2010 年代 因子投资 / Smart Beta：把超额收益拆解为可复制的风险溢价",
            "2010 年代后 TDF / TRF：把投资目标与客户生命周期对齐，"
            "公募 FOF 是其在国内的产品落地",
        ],
        page_idx=7,
    )
    # P8
    make_content_slide(
        prs, ch2,
        "SAA / TAA / 动态再平衡 三层框架",
        "把投资过程“拆三层”，明确各自的目标与边界",
        [
            "战略配置 SAA：基于长期均衡假设与客户风险偏好，"
            "确定大类资产中枢；解释组合 70%—80% 的长期回报",
            "战术配置 TAA：基于 6—12 个月的宏观 / 估值 / 趋势判断，"
            "对中枢做 ±5%—±15% 的偏离",
            "动态再平衡：按既定规则把组合拉回目标，"
            "长期可贡献 0.3%—0.8% 的年化 α",
            "三层的清晰分工 → 让“配置”与“择时”可以分别归因、分别考核",
            "公募 FOF 的合规优势：边界明确，便于把三层框架写进产品合同",
        ],
        page_idx=8,
    )
    # P9
    make_content_slide(
        prs, ch2,
        "中国公募FOF市场现状",
        "8 年发展 · 1500 亿元规模 · 头部集中",
        [
            "运作时间：自 2017 年首批获批至今，已运行 8 年",
            "市场规模：产品数量超 500 只，总规模约 1500 亿元，"
            "相比海外仍有 10 倍空间",
            "产品分类：普通 FOF / 养老目标日期 / 养老目标风险 / ETF-FOF 四类",
            "头部集中：前 10 名管理人占行业规模约 60%",
            "三大趋势：①养老 FOF 借第三支柱起量　②ETF-FOF 成本优势凸显"
            "　③全球配置型逐步推出",
        ],
        page_idx=9,
    )
    # P10 - table
    make_table_slide(
        prs, ch2,
        "公募FOF 监管边界一页清单",
        "做 FOF 前必须牢记的“红线”",
        headers=["维度", "具体规定", "对组合管理的影响"],
        rows=[
            ["投资标的下限", "≥80% 基金资产投资于经核准/注册的公募基金份额",
             "决定了 FOF 必须以基金为底层资产"],
            ["禁止直投", "不得直接投资股票、债券、期货、期权、互换等",
             "对冲与商品敞口须通过底层基金间接实现"],
            ["单只基金上限", "投资单只基金 ≤ FOF 资产净值的 20%（ETF联接除外）",
             "保证组合分散度，避免过度依赖某只产品"],
            ["同名产品限制", "不得持有同一只基金的不同份额合计超过限额",
             "选基时需考虑份额结构与认购规则"],
            ["双重收费", "需充分披露管理费与综合费率，"
                       "投本管理人产品须豁免相应管理费",
             "影响产品定价与净值表现，须前置披露"],
            ["流动性", "不得投资封闭式基金等流动性受限品种（特殊产品除外）",
             "组合流动性必须与客户赎回机制匹配"],
        ],
        col_widths_cm=[5.5, 14, 11.5],
        footnote="资料来源：《公开募集证券投资基金运作指引第2号》及相关监管规则；表述经精简，以监管原文为准",
        page_idx=10,
    )

    # ========== Chapter 3 ==========
    ch3 = "第三章【主线一】全球多元资产研究与对比"
    # P11
    make_content_slide(
        prs, ch3,
        "可投大类资产画像总览",
        "九类资产 = SAA 的“原子集合”",
        [
            "境内权益：沪深300 / 中证500 / 中证1000 —— 长期 β 与风格暴露",
            "港股：恒生 / 恒生科技 / 高股息 —— 差异化 β、估值修复期权",
            "海外权益：标普 / 纳指 / 欧洲 / 日本 / 印度 / 越南 —— 独立 β 来源",
            "利率债 / 信用债：组合的“减震器”与稳定 carry 来源",
            "黄金：避险与抗通胀；商品 ETF（豆粕 / 有色 / 能化）：再通胀场景对冲",
            "公募 REITs：股债之外的第三类现金流，与股债相关性低",
            "现金 / 货基：流动性管理与战术弹药",
        ],
        page_idx=11,
    )
    # P12 - chart
    make_content_slide(
        prs, ch3,
        "大类资产相关性矩阵：构建组合的“地基”",
        "把风险来源分布在尽量多的“独立桶”里",
        [
            "境内权益之间相关性 0.9+：多放几只 A 股基金并不能真正分散",
            "A 股 vs 海外股票 相关性 0.3 左右 → 跨境配置是最有效的分散源",
            "黄金、REITs、利率债 与 A 股 相关性 ≤ 0.1（甚至负相关）",
            "原油与权益相关性 0.3—0.4，再通胀场景下提供尾部对冲",
            "结论：好组合 ≠ 多只基金，而是“多个独立的风险桶”",
        ],
        image="chart_corr_heatmap.png",
        image_right=True,
        image_width_cm=16.5,
        footnote="数据来源：基于公开指数月度收益估算，仅供示意",
        page_idx=12,
    )
    # P13 - chart
    make_content_slide(
        prs, ch3,
        "宏观情景四象限：资产轮动地图",
        "美林时钟的升级版，叠加全球流动性与汇率视角",
        [
            "复苏（增长↑通胀↓）：成长股 / 信用债 / REITs / 纳指",
            "过热（增长↑通胀↑）：工业商品 / 原油 / 新兴市场股 / 价值股",
            "滞胀（增长↓通胀↑）：黄金 / 短债 / 防御股 / 现金",
            "衰退（增长↓通胀↓）：长久期利率债 / 美元资产 / 高等级信用",
            "TAA 应用：在 SAA 中枢基础上做 ±10% 偏离，"
            "对应不同象限的资产轮动",
        ],
        image="chart_macro_quadrant.png",
        image_right=True,
        image_width_cm=17.0,
        footnote="说明：象限内资产推荐为方向性示意，实操中需结合估值与拥挤度",
        page_idx=13,
    )
    # P14
    make_content_slide(
        prs, ch3,
        "境内权益拆解：市值 × 风格的二维矩阵",
        "境内权益不是单一资产，而是一个可主动管理的“矩阵”",
        [
            "市值维度：沪深300（大盘价值/质量）/ 中证500（中盘成长）/"
            " 中证1000（小盘高弹性）",
            "风格维度：红利低波（震荡市占优）/ 质量与成长（景气上行期占优）",
            "行业维度：科创板 / 创业板 / 中证消费 / 中证医药 等主题指数补足结构性敞口",
            "公募 FOF 的实战做法：宽基 + 风格 + 主题 三层组合，"
            "并通过风格轮动信号做动态再平衡",
            "工具选择：宽基用 ETF 控成本，风格 / 主题可结合主动基金获取增厚",
        ],
        page_idx=14,
    )
    # P15
    make_content_slide(
        prs, ch3,
        "港股与中概：被低估的差异化 β",
        "AH 折价 30%+ · 高股息 + 恒生科技 双引擎",
        [
            "恒生科技：新经济与互联网平台的核心代理",
            "恒生高股息：低估值 + 高股息率（多年 6%+），"
            "适合稳健型组合的“类债”仓位",
            "AH 溢价：长期处于 130—150 区间，"
            "提供 A/H 套利与配置切换空间",
            "与 A 股相关性 ~0.6：相关但不重合，"
            "提供边际分散",
            "工具：港股通主动基金、恒生科技 ETF、恒生高股息 ETF",
        ],
        page_idx=15,
    )
    # P16
    make_content_slide(
        prs, ch3,
        "海外权益：公募FOF 通过 QDII 实现",
        "把全球权益纳入战略配置，是公募FOF 的差异化新阵地",
        [
            "核心 β：标普500 / 纳指100 —— 海外权益敞口的 50%+",
            "成熟市场补充：欧洲STOXX 50 / 日经225 / TOPIX —— 配置 10%—20%",
            "新兴市场 α 增厚：印度 Nifty / 越南 VN30 —— 占比 10%—20%",
            "QDII 额度紧约束：建议同类备 2—3 只替代品，"
            "并跟踪基金申购暂停 / 限购公告",
            "汇率维度：美元升值期 QDII 享汇兑收益，"
            "贬值期需评估是否对冲（公募 FOF 主要靠不同币种 QDII 间接调节）",
        ],
        page_idx=16,
    )
    # P17
    make_content_slide(
        prs, ch3,
        "固定收益：四个工具桶",
        "稳定 carry · 久期防御 · 信用 alpha · option 切换",
        [
            "利率债（国债 / 政金债）：组合的减震器，与权益负相关或低相关",
            "高等级信用债：稳定 carry，"
            "需控制单券集中度与行业暴露",
            "可转债：股性 / 债性切换的“option”，"
            "在权益估值底部具备非对称性",
            "中资美元债（QDII）：捕捉美元利率与中资信用利差，"
            "兼具汇率敞口",
            "稳健型 FOF 债券底仓建议："
            "利率 40% · 信用 40% · 转债 10% · 美元债 10%",
        ],
        page_idx=17,
    )
    # P18
    make_content_slide(
        prs, ch3,
        "黄金与商品：公募FOF 唯一的“类商品”通道",
        "在公募合规边界内，把商品敞口纳入组合",
        [
            "黄金 ETF：境内多只规模超百亿，"
            "提供避险 + 抗通胀 + 美元对冲三重价值",
            "豆粕 ETF：农产品代理，"
            "对冲食品 / CPI 上行风险",
            "有色金属 ETF：铜 / 铝周期代理，"
            "再通胀场景受益",
            "能源化工 ETF：油气链条代理，"
            "对冲地缘冲突与能源价格上行",
            "实操要点：警惕升贴水与展期损耗，"
            "建议黄金 5%—10%、商品 ETF 0%—5%",
        ],
        page_idx=18,
    )
    # P19
    make_content_slide(
        prs, ch3,
        "公募REITs：第三类资产的崛起",
        "2021 年起 · 规模约 1500 亿 · 分红率 4%—8%",
        [
            "底层资产：产业园 / 仓储物流 / 保障房 / 高速公路 / 能源等",
            "现金流稳定，与股债相关性较低，"
            "对稳健型 FOF 是天然 α 来源",
            "估值敏感度：受贴现率（10Y 国债）变动影响较大，"
            "需关注利率周期",
            "流动性：单只 REITs 流动性有限，"
            "建议组合内 3%—8% 配比，分散于不同类型",
            "未来扩募 + 二级市场流动性改善 → 配置空间持续打开",
        ],
        page_idx=19,
    )
    # P20 - table
    make_table_slide(
        prs, ch3,
        "公募FOF 全球配置工具箱总表",
        "九类资产 → 可用的代表性公募基金类型",
        headers=["资产类别", "公募 FOF 可用工具", "典型用途"],
        rows=[
            ["境内权益", "宽基 ETF / 风格 ETF / 行业主题 ETF / 主动权益基金",
             "组合长期 β + 风格 / 行业 α"],
            ["港股 / 中概", "港股通主动基金 / 恒生科技 ETF / 恒生高股息 ETF",
             "差异化 β + 高股息底仓"],
            ["海外权益", "QDII 主动基金 / 跨境 ETF（标普 / 纳指 / 欧日印越）",
             "独立 β + 跨境分散"],
            ["利率债", "中长期纯债基金 / 国债 ETF / 政金债 ETF",
             "组合“减震器”、对冲权益"],
            ["信用债", "信用债基金 / 中短债基金",
             "稳定 carry + 收益增厚"],
            ["可转债", "可转债基金 / 转债 ETF",
             "股债切换的“option”"],
            ["海外债券", "中资美元债 QDII / 全球债 QDII",
             "美元 carry + 汇率对冲"],
            ["黄金 / 商品", "黄金 ETF / 豆粕 ETF / 有色 / 能化 ETF",
             "避险、抗通胀、尾部对冲"],
            ["公募 REITs", "公募 REITs 二级市场份额",
             "第三类现金流，低相关 α"],
            ["现金 / 货基", "货币基金 / 同业存单指数基金",
             "流动性管理 + 战术弹药"],
        ],
        col_widths_cm=[5.5, 14.5, 11.0],
        footnote="说明：本表为映射关系示意，非任何产品推荐；实操中需结合管理人内部白名单与风控准入",
        page_idx=20,
    )

    # ========== Chapter 4 ==========
    ch4 = "第四章【主线二】组合管理：风险预算 / 风险控制 / 收益拆解"
    # P21
    make_content_slide(
        prs, ch4,
        "从“资金预算”到“风险预算”：范式转变",
        "让真实风险敞口与管理者意图保持一致",
        [
            "传统 60/40 组合：股票占资金 60%，但贡献组合波动 90%+",
            "风险预算：按风险贡献分配，"
            "若希望股债风险贡献 50/50，股票资金权重通常仅 25%—30%",
            "意义：避免“假分散”——名义多资产，实质权益单一暴露",
            "落地：以波动率 / VaR / 边际贡献作为度量，进入组合优化器",
            "公募 FOF 的合规优势：风险预算可被结构化写入合同与日常合规监控",
        ],
        page_idx=21,
    )
    # P22
    make_content_slide(
        prs, ch4,
        "风险平价与全天候：核心方法对比",
        "ERC / MDP / MV 的适用场景",
        [
            "桥水全天候：股 / 债 / 商品 / 黄金按风险贡献等权，"
            "再加杠杆达到目标波动率",
            "ERC（等风险贡献）：稳健、可解释，"
            "公募 FOF 实务主流方案（低波约束下）",
            "MDP（最大分散化）：追求多样性比率最大，"
            "适合资产数量较多的组合",
            "MV（最小方差）：追求绝对波动最低，"
            "适合极致稳健型产品",
            "公募 FOF 不能加杠杆 → 实践中常用“低波约束下的 ERC”作为核心配置算法",
        ],
        page_idx=22,
    )
    # P23
    make_content_slide(
        prs, ch4,
        "风险预算三层下沉",
        "大类资产层 → 风格因子层 → 子基金层",
        [
            "第一层：大类资产间的风险预算（股 / 债 / 商品 / REITs / 现金）",
            "第二层：风格因子之间的风险预算"
            "（价值 / 成长 / 红利 / 低波 / 质量）",
            "第三层：具体子基金之间的风险预算"
            "（含规模、换手、容量、稳定性等约束）",
            "事前预算 + 事后归因 形成闭环 →"
            "回撤发生时可精确定位贡献来源",
            "三层下沉的好处：从“黑盒组合”到“透明组合”，"
            "可向客户与渠道清晰解释",
        ],
        page_idx=23,
    )
    # P24 - chart
    make_content_slide(
        prs, ch4,
        "案例：用公募工具构造“类全天候”组合",
        "完全在公募 FOF 框架内可落地的实战样例",
        [
            "样例权重：黄金 ETF 20% · 国债 ETF 30% · 红利低波 ETF 20%"
            " · QDII 纳指 15% · 消费 / 医药 10% · 信用债 5%",
            "回测示意（10 年）：年化 ~7.2% · 波动 ~6.5% · 最大回撤 ~-10%",
            "对比 60/40：年化相近、波动 ~11% / 回撤 ~-22%，明显占优",
            "对比沪深300：年化相近、波动仅为其 1/3、回撤为其 1/5",
            "意义：公募 FOF 完全有能力做出“类全天候”体验",
        ],
        image="chart_all_weather_backtest.png",
        image_right=True,
        image_width_cm=17.5,
        footnote="回测口径为示意性估算，未考虑费用与冲击成本，正式产品需用真实净值数据回测",
        page_idx=24,
    )
    # P25
    make_content_slide(
        prs, ch4,
        "事前风控：把“边界”写进合同",
        "参数化的风控约束 = 组合的“骨架”",
        [
            "波动率目标：例如年化 ≤ 10%（稳健型）/ ≤ 14%（平衡型）",
            "最大回撤目标：例如 ≤ -15%（稳健型）/ ≤ -25%（平衡型）",
            "CVaR / 尾部约束：5% 尾部预期损失 ≤ -2%（按月）",
            "跟踪误差约束：相对业绩比较基准 TE ≤ 4%",
            "集中度限制：单只基金 ≤ 10% · 单一管理人 ≤ 20% ·"
            " 单一策略 ≤ 30%",
            "流动性约束：T+1 / T+2 可赎部分 ≥ 30%",
        ],
        page_idx=25,
    )
    # P26
    make_content_slide(
        prs, ch4,
        "事中风控：让“活的风险”被持续看见",
        "周 / 月度体检表 —— 早发现、早处置",
        [
            "相关性监控：压力情景下相关性会“齐涨齐跌”，"
            "需要提前感知与减仓",
            "风格漂移识别：买价值跑成长 → 立即评估替换",
            "规模 / 换手 / 流动性预警：规模骤增 → 策略容量稀释；"
            "换手骤降 → 经理风险偏好变化",
            "申购暂停 / 限购预警：QDII 尤其需要监控",
            "考核与挂钩：把事中风控指标纳入投资经理 KPI",
        ],
        page_idx=26,
    )
    # P27 - chart
    make_content_slide(
        prs, ch4,
        "事后压力测试：四个情景下的“消防演习”",
        "用当前持仓拟合历史极端环境的损益",
        [
            "情景选择：2008 金融危机 / 2015 A 股股灾 /"
            " 2020 疫情冲击 / 2022 股债双杀",
            "结果（示意）：类全天候组合四情景最大回撤"
            "均控制在 -12% 以内",
            "60/40 组合最差时 -22%；沪深300 在 2008 年 -58%",
            "提示：压力测试不是“事后解释”，"
            "而是事前调整组合结构的依据",
            "组合调整方向：增加避险 / 反相关资产 / 限制单一情景敞口",
        ],
        image="chart_stress_test.png",
        image_right=True,
        image_width_cm=17.5,
        footnote="数据为示意性估算，正式压力测试需使用历史价格序列与因子模型",
        page_idx=27,
    )
    # P28
    make_content_slide(
        prs, ch4,
        "再平衡机制：低买高卖的物化",
        "定期 · 阈值 · 波动率触发  三种机制对比",
        [
            "定期：每季 / 每半年，简单有纪律，但可能错过结构性机会",
            "阈值：偏离目标权重 ±5% / ±10% 即触发，"
            "智能但交易频率不可控",
            "波动率触发：组合波动突破阈值即降仓，"
            "适合追求稳定波动的产品",
            "实践组合：定期为主 + 阈值为辅 + 波动率为应急",
            "长期 α 贡献：经验上 0.3%—0.8% 年化，"
            "且能显著平滑客户体验",
        ],
        page_idx=28,
    )
    # P29 - chart
    make_content_slide(
        prs, ch4,
        "收益拆解（一）：Brinson 三层归因",
        "资产配置贡献 + 子基金选择贡献 + 交互项",
        [
            "资产配置贡献：是否把权重放在了表现好的大类上",
            "子基金选择贡献：是否在每个大类内选到了好基金",
            "交互项：配置与选基的协同效应",
            "FOF 适配版：进一步拆为“大类 → 子板块 → 子基金”三层",
            "客户价值：让客户清楚知道自己付的管理费换回了什么",
        ],
        image="chart_attribution.png",
        image_right=True,
        image_width_cm=17.5,
        footnote="示例数字为方法论展示用，非具体产品业绩",
        page_idx=29,
    )
    # P30 - table
    make_table_slide(
        prs, ch4,
        "收益拆解（二）：风险归因 + 多因子归因",
        "把“赚了多少”与“承担了多少风险”一并讲清楚",
        headers=["归因维度", "常用度量 / 工具", "回答的问题"],
        rows=[
            ["收益归因", "Brinson 三层归因（FOF 适配版）",
             "组合超额收益由哪一层贡献？"],
            ["风险归因", "边际 VaR / 边际波动贡献",
             "每只基金 / 每类资产对总风险的贡献度？"],
            ["股票因子归因", "Barra：市值 / 价值 / 动量 / 成长 / 质量 / 波动",
             "权益部分的风格敞口与超额来源？"],
            ["债券因子归因", "久期 / 信用利差 / 曲线斜率 / 凸性",
             "债券部分的久期与信用敞口？"],
            ["跨资产因子", "Beta / Carry / Momentum / Value",
             "组合究竟在赚哪一类风险溢价？"],
            ["子基金穿透", "持仓穿透 + 净值穿透",
             "实际风格与基金合同 / 名称是否一致？"],
        ],
        col_widths_cm=[7.0, 13.5, 10.5],
        footnote="完整归因报告建议包含“收益贡献”与“风险贡献”两列，并可下钻到单只子基金",
        page_idx=30,
    )

    # ========== Chapter 5 ==========
    ch5 = "第五章  公募FOF 投资新思路（6 条）"
    # P31
    make_content_slide(
        prs, ch5,
        "思路 1：从“组合基金”到“配置工具”",
        "让 FOF 成为客户的“唯一持仓”",
        [
            "形态升级：FOF 不再是某类资产的简单打包，"
            "而是全天候、可适配多场景的配置解决方案",
            "对内要求：SAA 必须经过严格的全周期回测，"
            "TAA 必须有清晰的偏离边界",
            "子基金覆盖：必须横跨所有可投资产类别，避免“缺角”",
            "渠道价值：极大降低客户的选择成本，"
            "是银行渠道粘性的关键产品",
            "商业意义：复购率与留存显著高于单一基金，"
            "是 AUM 长期增长的“锚”",
        ],
        page_idx=31,
    )
    # P32
    make_content_slide(
        prs, ch5,
        "思路 2：用公募工具构造类全天候 / 风险平价",
        "公募 FOF 相对单一基金 / 传统 60/40 的差异化卖点",
        [
            "公募 ETF + LOF + QDII 已足以拼出“类全天候”体验",
            "差异点：监管合规、客户可理解、成本可控、信息披露透明",
            "局限：不能加杠杆 → 绝对收益空间小于真正的全天候",
            "优势：风险调整后收益（Sharpe / Calmar）完全可媲美",
            "落地：建议产品名清晰传达“多元资产 / 风险平价”定位，"
            "便于客户认知与渠道营销",
        ],
        page_idx=32,
    )
    # P33
    make_content_slide(
        prs, ch5,
        "思路 3：全球化升级 —— QDII + 跨境 ETF",
        "海外配置从 5%—10% 提升至 15%—25%",
        [
            "核心抓手：QDII 主动基金 + 跨境 ETF "
            "（标普 / 纳指 / 欧 / 日 / 印 / 越）",
            "配置目标：不是“追海外热点”，"
            "而是在组合中获得“独立 β”",
            "实操难点：QDII 额度紧约束 → 提前储备 2—3 只替代品",
            "费用维度：跨境 ETF 综合费率更低，"
            "适合作为长期底仓",
            "客户教育：净值波动期需要持续输出宏观与汇率视角的解读",
        ],
        page_idx=33,
    )
    # P34
    make_content_slide(
        prs, ch5,
        "思路 4：另类敞口 —— 公募 REITs + 商品 ETF",
        "把另类纳入组合，补全公募 FOF 的资产维度",
        [
            "现状：传统公募 FOF 的另类敞口几乎为零",
            "目标：未来提升至 5%—15%",
            "构成：公募 REITs 3%—8%、黄金 ETF 5%—10%、商品 ETF 0%—5%",
            "效果：显著降低尾部风险，"
            "经验上 Sharpe 提升 0.1—0.3",
            "差异化：在公募 FOF 的“红海产品”中形成清晰区分度",
        ],
        page_idx=34,
    )
    # P35
    make_content_slide(
        prs, ch5,
        "思路 5：风险预算驱动的子基金筛选",
        "把风险预算前置到“选基”环节",
        [
            "传统模式：偏定性，容易陷入“明星基金经理”陷阱",
            "新流程：先定每只基金的目标风险贡献（如 3%），"
            "倒推目标波动率与权重",
            "定量筛选：风格穿透（持仓 + 净值双穿透）、"
            "稳定性、容量评估、最大回撤匹配",
            "定性补充：基金经理画像（任期、换手、决策风格、"
            "组织环境）",
            "动态白名单：每季度刷新，配套准入流程与“降级”机制",
        ],
        page_idx=35,
    )
    # P36
    make_content_slide(
        prs, ch5,
        "思路 6：养老 FOF 与目标日期下滑曲线的本土化",
        "第三支柱 Y 份额 —— 未来 5—10 年最确定的增量",
        [
            "下滑曲线：客户距离退休年限缩短 →"
            "权益仓位从 80% 逐步降至 20%",
            "本土化要点 1：下滑曲线斜率更陡（国内权益波动更大）",
            "本土化要点 2：退休后阶段把高股息 + REITs 作为核心仓位",
            "本土化要点 3：海外资产作为分散源，降低单一市场风险",
            "渠道落地：与银行养老金账户深度结合，"
            "嵌入定投与“目标日期一键配置”",
        ],
        page_idx=36,
    )

    # ========== Chapter 6 ==========
    ch6 = "第六章  公募FOF 在银行场景的落地"
    # P37 - table
    make_table_slide(
        prs, ch6,
        "银行代销 / 自营 FOF 的选品框架",
        "把“尽职调查”做成标准化评分卡",
        headers=["维度", "关注要点", "评分参考"],
        rows=[
            ["1. 双重收费", "总管理费 + 综合费率上限是否透明",
             "综合费率越低、披露越细越优"],
            ["2. 规模", "10—100 亿区间最佳，"
                     "避免过小（运作不稳）或过大（容量受限）",
             "中性规模 + 增长稳定为佳"],
            ["3. 风格", "稳健 / 平衡 / 进取分层，"
                     "与客户分层精准匹配",
             "标签清晰、风格穿透一致"],
            ["4. 回撤控制", "历史最大回撤与产品定位是否匹配",
             "稳健型 ≤ -15%，平衡型 ≤ -20%"],
            ["5. 管理人能力", "SAA 框架 / 子基金研究 /"
                          "归因体系是否完整",
             "三位一体齐全为优秀，单点缺失需关注"],
        ],
        col_widths_cm=[5.5, 14.5, 11.0],
        footnote="建议把以上五维度做成 100 分制评分卡，每季度刷新代销 / 自营白名单",
        page_idx=37,
    )
    # P38 - table
    make_table_slide(
        prs, ch6,
        "公募FOF  vs  理财FOF：边界与协同",
        "两类 FOF 不是替代关系，而是阶梯式产品矩阵",
        headers=["维度", "公募 FOF", "理财 FOF / MOM"],
        rows=[
            ["监管框架", "证监会 · 公募基金运作指引",
             "金融监管总局 · 理财公司监管"],
            ["投资范围", "≥80% 投公募基金，"
                       "不可直投股票 / 债券 / 衍生品",
             "可投公募 / 私募 / 衍生品 / 收益凭证 / 信托等，"
             "工具更丰富"],
            ["风险等级", "R2—R3 为主",
             "R3—R4 为主"],
            ["客户对象", "广义零售 / 大众富裕",
             "私行 / 高净值客户"],
            ["信息披露", "标准化、高频",
             "相对灵活、个性化"],
            ["产品矩阵建议", "覆盖养老 / 稳健 / 平衡 / 进取四档",
             "覆盖含权策略 / 量化对冲 / 多策略 / 跨境组合"],
        ],
        col_widths_cm=[5.0, 12.5, 13.5],
        footnote="阶梯式产品体系：公募 FOF 做大众富裕的“底盘”，理财 FOF / MOM 做私行的“高级形态”",
        page_idx=38,
    )
    # P39
    make_content_slide(
        prs, ch6,
        "养老金融与第三支柱：银行的主场",
        "个人养老金 Y 份额公募FOF —— 渗透率仍不足 10%",
        [
            "政策：个人养老金账户 12000 元 / 年税优额度，"
            "Y 份额已超 200 只、规模约 800 亿",
            "渠道地位：银行作为账户主开户方，"
            "是养老 FOF 推广的核心阵地",
            "产品端抓手：重点配置目标日期 2030—2045 与稳健型目标风险 FOF",
            "客户教育抓手：把“长钱长投 / 复利 / 下滑曲线”做成可视化材料",
            "中长期愿景：第三支柱将成为公募 FOF 最大的单一资金池",
        ],
        page_idx=39,
    )

    # ========== Chapter 7 ==========
    ch7 = "第七章  案例与展望"
    # P40 - table
    make_table_slide(
        prs, ch7,
        "国内代表性公募FOF 案例剖析（匿名化）",
        "稳健型 FOF  +  目标日期养老 FOF",
        headers=["维度", "案例 A：稳健型 FOF", "案例 B：目标日期 2040 养老 FOF"],
        rows=[
            ["规模 / 运作期", "约 80 亿元 / 运作 6 年",
             "约 25 亿元 / 运作 4 年"],
            ["大类配置", "股 30% · 债 55% · 商品 / REITs 15%",
             "权益 70%（A 股 40% · 港股 10% · QDII 20%）· 债 25% · 黄金 5%"],
            ["年化收益（示意）", "约 6.8%",
             "约 8.5%"],
            ["年化波动 / 最大回撤", "波动 ~6.2% · 回撤 ~-7%",
             "波动 ~13% · 回撤 ~-18%"],
            ["子基金", "约 30 只 · 覆盖 8 类资产",
             "约 25 只 · 含 QDII / REITs / 黄金 ETF"],
            ["管理特征", "每季度风险预算再校准 + 季报披露完整归因",
             "下滑曲线每年降权益 3% · 设“波动率触发”降仓机制"],
        ],
        col_widths_cm=[5.5, 12.5, 13.0],
        footnote="数据为示意性估算，仅作方法论展示，不构成任何产品推荐",
        page_idx=40,
    )
    # P41
    make_content_slide(
        prs, ch7,
        "展望：AI 投研 · 数据基础设施 · 客户陪伴",
        "公募 FOF 下一个十年的三大变量",
        [
            "AI 投研：大模型加速基金研究 / 经理画像 / 会议纪要信号提取，"
            "单分析师覆盖基金数提升 3—5 倍",
            "数据基础设施：底层持仓穿透库 + 统一风险因子模型 +"
            "自动化归因平台 = FOF 专业化的“地基”",
            "客户陪伴：净值波动期的可信解读 比 净值上涨 更重要",
            "组织能力：FOF 团队从“选基组”升级为“配置研究院”",
            "监管演进：合规边界持续清晰化，"
            "公募 FOF 的产品创新空间反而被打开",
        ],
        page_idx=41,
    )

    # Final Q&A page
    make_end_slide(prs, 42)

    prs.save(OUTPUT_FILE)
    print(f"[build] Generated: {OUTPUT_FILE.relative_to(PROJECT_ROOT)}")


if __name__ == "__main__":
    build()
