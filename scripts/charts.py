"""生成 PPT 所需的 6 张数据图表 PNG。

数据均为基于公开市场口径的示意性估算（2010-2025 年），
仅用于本次分享的图示，正式使用前需以 Wind/Bloomberg 数据校核。
"""

from __future__ import annotations

import os
from pathlib import Path

import matplotlib
import matplotlib.pyplot as plt
import numpy as np
from matplotlib import font_manager

matplotlib.use("Agg")

PROJECT_ROOT = Path(__file__).resolve().parent.parent
CHARTS_DIR = PROJECT_ROOT / "charts"
CHARTS_DIR.mkdir(parents=True, exist_ok=True)


def _set_chinese_font() -> None:
    """挑选系统中可用的中文字体，避免中文显示为方块。"""
    candidates = [
        "WenQuanYi Micro Hei",
        "Noto Sans CJK SC",
        "Noto Sans SC",
        "Source Han Sans CN",
        "Microsoft YaHei",
        "SimHei",
        "PingFang SC",
        "Heiti SC",
        "Droid Sans Fallback",
    ]
    available = {f.name for f in font_manager.fontManager.ttflist}
    chosen = next((c for c in candidates if c in available), None)
    if chosen is None:
        chosen = "DejaVu Sans"
    matplotlib.rcParams["font.sans-serif"] = [chosen]
    matplotlib.rcParams["axes.unicode_minus"] = False


_set_chinese_font()

# Light/fresh theme palette
BG_PAGE   = "#FFFFFF"
BG_CARD   = "#F8FAFC"   # slate-50, used as inner panel/card
BG_CARD2  = "#F1F5F9"   # slate-100
INK       = "#0F172A"   # slate-900, primary text + contrast on accent
TEXT      = INK
TXT_DIM   = "#64748B"   # slate-500
GRID      = "#E2E8F0"   # slate-200

# Accent palette (used to highlight categories / steps)
ACCENT    = "#F59E0B"   # amber - primary
ACCENT_2  = "#3B82F6"   # blue
ACCENT_3  = "#10B981"   # emerald
ACCENT_4  = "#EF4444"   # red
ACCENT_5  = "#8B5CF6"   # violet

# Back-compat aliases used by older chart code:
#   DARK_BG → page background (now white)
#   BG_DARK → INK (dark color used as text-on-accent / contrast)
#   PANEL   → light card background
DARK_BG = BG_PAGE
BG_DARK = INK
PANEL   = BG_CARD

plt.rcParams.update(
    {
        "figure.facecolor": BG_PAGE,
        "axes.facecolor": BG_PAGE,
        "axes.edgecolor": "#CBD5E1",   # slate-300
        "axes.labelcolor": INK,
        "axes.titlecolor": INK,
        "xtick.color": TXT_DIM,
        "ytick.color": TXT_DIM,
        "text.color": INK,
        "grid.color": GRID,
        "savefig.facecolor": BG_PAGE,
        "savefig.edgecolor": BG_PAGE,
        "figure.dpi": 160,
    }
)


def save(fig: plt.Figure, name: str) -> Path:
    path = CHARTS_DIR / name
    fig.tight_layout()
    fig.savefig(path, bbox_inches="tight", facecolor=DARK_BG)
    plt.close(fig)
    print(f"  saved -> {path.relative_to(PROJECT_ROOT)}")
    return path


def chart_asset_long_term() -> None:
    """大类资产长期收益—波动散点（2010-2025 示意性估算）。"""
    assets = [
        ("沪深300",      8.5, 22.0),
        ("中证500",      6.8, 26.0),
        ("恒生指数",     2.5, 22.5),
        ("恒生科技",     4.0, 32.0),
        ("标普500",     12.5, 17.5),
        ("纳指100",     16.5, 21.0),
        ("欧洲STOXX",    7.0, 17.0),
        ("日经225",      9.0, 18.5),
        ("印度Nifty",   12.0, 19.0),
        ("中债综合",     4.2,  2.5),
        ("中资美元债",   5.0,  6.0),
        ("黄金(美元)",   8.0, 14.5),
        ("原油(布油)",   3.5, 33.0),
        ("公募REITs",    5.5, 11.0),
    ]
    fig, ax = plt.subplots(figsize=(10, 5.6))
    colors = [ACCENT_2 if "债" in n or "REIT" in n else
              ACCENT_3 if n in ("黄金(美元)", "原油(布油)") else
              ACCENT for n, _, _ in assets]
    xs = [v for _, _, v in assets]
    ys = [r for _, r, _ in assets]
    sizes = [320 for _ in assets]
    ax.scatter(xs, ys, s=sizes, c=colors, alpha=0.85, edgecolors=TEXT, linewidth=0.6)
    for (name, r, v) in assets:
        ax.annotate(name, (v, r), xytext=(6, 6), textcoords="offset points",
                    fontsize=9, color=TEXT)
    ax.set_xlabel("年化波动率(%)", fontsize=11)
    ax.set_ylabel("年化收益率(%)", fontsize=11)
    ax.set_title("大类资产长期收益—风险画像（2010–2025，示意）", fontsize=13, pad=12)
    ax.grid(True, linestyle="--", alpha=0.35)
    ax.set_xlim(0, max(xs) * 1.15)
    ax.set_ylim(min(ys) - 2, max(ys) + 3)
    save(fig, "chart_asset_long_term.png")


def chart_corr_heatmap() -> None:
    """大类资产相关性热力图（2010-2025 示意性估算月度收益相关）。"""
    labels = ["沪深300", "中证500", "恒生", "标普500", "纳指100",
              "欧洲", "日本", "中债", "美元债", "黄金", "原油", "REITs"]
    data = np.array([
        # 沪深300
        [1.00, 0.92, 0.62, 0.32, 0.30, 0.45, 0.30, -0.05, 0.18, 0.10, 0.30, 0.55],
        # 中证500
        [0.92, 1.00, 0.58, 0.28, 0.27, 0.42, 0.28, -0.08, 0.15, 0.08, 0.28, 0.52],
        # 恒生
        [0.62, 0.58, 1.00, 0.48, 0.45, 0.52, 0.42, -0.02, 0.30, 0.15, 0.32, 0.40],
        # 标普500
        [0.32, 0.28, 0.48, 1.00, 0.92, 0.78, 0.60, 0.05, 0.40, 0.08, 0.42, 0.50],
        # 纳指
        [0.30, 0.27, 0.45, 0.92, 1.00, 0.72, 0.58, 0.05, 0.38, 0.05, 0.35, 0.42],
        # 欧洲
        [0.45, 0.42, 0.52, 0.78, 0.72, 1.00, 0.62, 0.02, 0.42, 0.12, 0.45, 0.48],
        # 日本
        [0.30, 0.28, 0.42, 0.60, 0.58, 0.62, 1.00, 0.00, 0.30, 0.10, 0.32, 0.36],
        # 中债
        [-0.05, -0.08, -0.02, 0.05, 0.05, 0.02, 0.00, 1.00, 0.35, 0.20, -0.05, 0.10],
        # 美元债
        [0.18, 0.15, 0.30, 0.40, 0.38, 0.42, 0.30, 0.35, 1.00, 0.25, 0.20, 0.30],
        # 黄金
        [0.10, 0.08, 0.15, 0.08, 0.05, 0.12, 0.10, 0.20, 0.25, 1.00, 0.18, 0.12],
        # 原油
        [0.30, 0.28, 0.32, 0.42, 0.35, 0.45, 0.32, -0.05, 0.20, 0.18, 1.00, 0.30],
        # REITs
        [0.55, 0.52, 0.40, 0.50, 0.42, 0.48, 0.36, 0.10, 0.30, 0.12, 0.30, 1.00],
    ])
    fig, ax = plt.subplots(figsize=(8.8, 7.0))
    cmap = matplotlib.colors.LinearSegmentedColormap.from_list(
        "fof_corr_light",
        ["#DBEAFE", "#FFFFFF", "#FEF3C7", "#F59E0B", "#B45309"],
    )
    im = ax.imshow(data, cmap=cmap, vmin=-0.2, vmax=1.0)
    ax.set_xticks(range(len(labels)), labels, rotation=45, ha="right", fontsize=9)
    ax.set_yticks(range(len(labels)), labels, fontsize=9)
    for i in range(len(labels)):
        for j in range(len(labels)):
            v = data[i, j]
            color = "#FFFFFF" if v > 0.65 else INK
            ax.text(j, i, f"{v:.2f}", ha="center", va="center",
                    color=color, fontsize=7.5)
    cb = fig.colorbar(im, ax=ax, fraction=0.04, pad=0.03)
    cb.ax.tick_params(colors=TEXT)
    ax.set_title("大类资产月度收益相关性矩阵（2010–2025，示意）",
                 fontsize=13, pad=14)
    save(fig, "chart_corr_heatmap.png")


def chart_macro_quadrant() -> None:
    """增长×通胀宏观四象限下的资产轮动地图。"""
    fig, ax = plt.subplots(figsize=(9.5, 6.0))
    ax.axhline(0, color="#94A3B8", linewidth=1.5)
    ax.axvline(0, color="#94A3B8", linewidth=1.5)

    quadrants = {
        ( 1,  1): ("增长↑ + 通胀↑\n（过热）",   ["权益", "工业商品", "原油", "新兴市场股"], ACCENT),
        (-1,  1): ("增长↓ + 通胀↑\n（滞胀）",   ["黄金", "现金", "短债", "防御股"],          ACCENT_4),
        (-1, -1): ("增长↓ + 通胀↓\n（衰退）",   ["利率债", "长久期债", "美元资产"],          ACCENT_2),
        ( 1, -1): ("增长↑ + 通胀↓\n（复苏）",   ["成长股", "纳指", "信用债", "REITs"],       ACCENT_3),
    }
    for (gx, gy), (label, assets, color) in quadrants.items():
        x = 0.55 * gx
        y = 0.65 * gy
        ax.text(x, y + 0.18, label, ha="center", va="center",
                fontsize=12, color=color, weight="bold")
        ax.text(x, y - 0.10, "  ·  ".join(assets), ha="center", va="center",
                fontsize=10, color=TEXT, wrap=True)

    ax.set_xlim(-1, 1)
    ax.set_ylim(-1, 1)
    ax.set_xticks([])
    ax.set_yticks([])
    ax.text(0.98, 0.02, "通胀 →", ha="right", color=TEXT, fontsize=11)
    ax.text(0.02, 0.98, "↑ 增长", ha="left", va="top", color=TEXT, fontsize=11)
    ax.set_title("宏观情景四象限下的资产轮动地图（示意）", fontsize=13, pad=12)
    for spine in ax.spines.values():
        spine.set_color(GRID)
    save(fig, "chart_macro_quadrant.png")


def chart_all_weather_backtest() -> None:
    """类全天候组合 vs 60/40 vs 沪深300 回测净值（示意）。

    为保证示意图与文字叙事一致（年化相近、波动差异显著），
    对每条路径做均值归一化，使其终值 ≈ exp(mu * T)。
    """
    n_years = 10
    months = n_years * 12

    def gen_path(mu_a: float, sig_a: float, seed: int) -> np.ndarray:
        rng = np.random.default_rng(seed)
        mu_m = np.log(1 + mu_a) / 12
        sig_m = sig_a / np.sqrt(12)
        r = rng.normal(mu_m, sig_m, size=months)
        # 归一化使均值严格等于 mu_m → 终值 = exp(mu_a * T) 的一阶近似
        r = r - r.mean() + mu_m
        return np.exp(np.cumsum(r))

    nv_aw    = gen_path(0.072, 0.065, 7)
    nv_6040  = gen_path(0.068, 0.110, 13)
    nv_hs300 = gen_path(0.075, 0.220, 21)

    fig, ax = plt.subplots(figsize=(10, 5.4))
    x = np.arange(months) / 12
    ax.plot(x, nv_aw, label="类全天候(公募工具)", color=ACCENT, linewidth=2.4)
    ax.plot(x, nv_6040, label="60/40 股债组合", color=ACCENT_2, linewidth=2.0)
    ax.plot(x, nv_hs300, label="沪深300", color=ACCENT_4, linewidth=1.6, alpha=0.85)
    ax.set_xlabel("年", fontsize=11)
    ax.set_ylabel("净值（起始=1）", fontsize=11)
    ax.set_title("用公募工具构造类全天候组合：净值对比（10 年，示意）",
                 fontsize=13, pad=12)
    ax.grid(True, linestyle="--", alpha=0.35)
    ax.legend(facecolor=PANEL, edgecolor=GRID, labelcolor=TEXT, loc="upper left")
    save(fig, "chart_all_weather_backtest.png")


def chart_stress_test() -> None:
    """四个历史情景下三类组合的最大回撤对比（示意）。"""
    scenarios = ["2008 金融危机", "2015 A 股股灾", "2020 疫情冲击", "2022 股债双杀"]
    aw =     [-12, -10,  -8, -10]
    p6040 =  [-22, -16, -14, -18]
    hs300 = [-58, -45, -15, -22]

    x = np.arange(len(scenarios))
    w = 0.26
    fig, ax = plt.subplots(figsize=(10, 5.2))
    ax.bar(x - w, aw, width=w, label="类全天候(公募)", color=ACCENT)
    ax.bar(x,     p6040, width=w, label="60/40 股债", color=ACCENT_2)
    ax.bar(x + w, hs300, width=w, label="沪深300",     color=ACCENT_4)
    for xi, vals in zip(x, zip(aw, p6040, hs300)):
        for off, v in zip([-w, 0, w], vals):
            ax.text(xi + off, v - 1.4, f"{v}%", ha="center", va="top",
                    fontsize=9, color=INK, weight="bold")
    ax.set_xticks(x, scenarios, fontsize=10)
    ax.set_ylabel("最大回撤(%)", fontsize=11)
    ax.set_title("四情景压力测试：最大回撤对比（示意）", fontsize=13, pad=12)
    ax.axhline(0, color=GRID, linewidth=1)
    ax.grid(True, axis="y", linestyle="--", alpha=0.35)
    ax.legend(facecolor=PANEL, edgecolor=GRID, labelcolor=TEXT, loc="lower right")
    save(fig, "chart_stress_test.png")


def chart_attribution() -> None:
    """Brinson 三层归因瀑布图（示意）。"""
    items = [
        ("基准收益",        6.5,  ACCENT_2),
        ("资产配置贡献",    2.4,  ACCENT_3),
        ("子基金选择贡献",  1.6,  ACCENT),
        ("交互项",          0.3,  "#9B8DD9"),
        ("费用与摩擦",     -0.6,  ACCENT_4),
        ("组合实际收益",    None, ACCENT),
    ]
    fig, ax = plt.subplots(figsize=(10, 5.4))
    cumulative = 0.0
    bottoms, heights, colors, labels = [], [], [], []
    for name, v, c in items[:-1]:
        bottoms.append(cumulative if v >= 0 else cumulative + v)
        heights.append(abs(v))
        colors.append(c)
        labels.append(name)
        cumulative += v

    final = cumulative
    bottoms.append(0)
    heights.append(final)
    colors.append(items[-1][2])
    labels.append(items[-1][0])

    x = np.arange(len(labels))
    bars = ax.bar(x, heights, bottom=bottoms, color=colors, edgecolor=GRID, linewidth=0.6)
    running = 0.0
    for i, (name, v, _) in enumerate(items):
        if i < len(items) - 1:
            top = bottoms[i] + heights[i] if v >= 0 else bottoms[i] + heights[i]
            ax.text(i, top + 0.18, f"{v:+.1f}%", ha="center", color=TEXT, fontsize=10)
        else:
            ax.text(i, final + 0.18, f"{final:.1f}%", ha="center",
                    color=ACCENT, fontsize=11, weight="bold")
    ax.set_xticks(x, labels, fontsize=10)
    ax.set_ylabel("收益贡献(%)", fontsize=11)
    ax.set_title("FOF 业绩归因瀑布图：从基准到组合实际收益（示意）",
                 fontsize=13, pad=12)
    ax.axhline(0, color=GRID, linewidth=1)
    ax.grid(True, axis="y", linestyle="--", alpha=0.35)
    save(fig, "chart_attribution.png")


def chart_theory_timeline() -> None:
    """资产配置理论演进时间线（P7），等距节点布局。"""
    nodes = [
        (1952, "MPT",              "Markowitz\n均值方差"),
        (1990, "BL 模型",           "Black-Litterman\n引入主观观点"),
        (2005, "全天候 / 风险平价",  "桥水：从资金预算\n到风险预算"),
        (2012, "因子投资",          "Smart Beta\n风险溢价可复制"),
        (2018, "TDF / TRF",        "目标日期 / 目标风险\n生命周期对齐"),
    ]
    n = len(nodes)
    fig, ax = plt.subplots(figsize=(14, 4.8))
    xs = np.arange(n) + 0.5
    ax.set_xlim(0, n)
    ax.set_ylim(-1.1, 1.2)
    ax.axhline(0, color="#94A3B8", linewidth=2, xmin=0.02, xmax=0.98)
    ax.annotate("", xy=(n - 0.02, 0), xytext=(n - 0.18, 0),
                arrowprops=dict(arrowstyle="->", color=ACCENT, lw=2.5))
    for x, (year, name, desc) in zip(xs, nodes):
        ax.scatter([x], [0], s=1000, color=ACCENT, zorder=5,
                   edgecolors=BG_PAGE, linewidth=2.2)
        ax.text(x, 0, str(year), ha="center", va="center",
                color="#FFFFFF", fontsize=11, weight="bold", zorder=6)
        ax.text(x, 0.65, name, ha="center", va="center",
                color=INK, fontsize=13, weight="bold")
        ax.text(x, -0.65, desc, ha="center", va="center",
                color=TXT_DIM, fontsize=10.5)
        ax.plot([x, x], [0.07, 0.50], color="#CBD5E1", linewidth=0.8)
        ax.plot([x, x], [-0.07, -0.45], color="#CBD5E1", linewidth=0.8)
    ax.set_xticks([])
    ax.set_yticks([])
    for spine in ax.spines.values():
        spine.set_visible(False)
    ax.set_title("资产配置理论的演进脉络（70 年）", fontsize=14, pad=14)
    save(fig, "chart_theory_timeline.png")


def chart_three_layer_pyramid() -> None:
    """SAA / TAA / 再平衡 三层金字塔（P8）。"""
    from matplotlib.patches import Polygon
    fig, ax = plt.subplots(figsize=(9.5, 5.6))

    layers = [
        # (y_low, y_high, half_width_low, half_width_high, label, sub, color)
        (0.0, 0.36, 0.95, 0.78,
         "战略配置 SAA", "长期均衡 · 决定 70%—80% 长期回报", ACCENT_2),
        (0.36, 0.66, 0.78, 0.55,
         "战术配置 TAA", "6—12 月偏离 ±5%—±15% · 把握中期机会", ACCENT_3),
        (0.66, 0.92, 0.55, 0.20,
         "动态再平衡", "纪律化 · 长期 α 0.3%—0.8%", ACCENT),
    ]
    for y0, y1, hw0, hw1, label, sub, color in layers:
        poly = Polygon(
            [(-hw0, y0), (hw0, y0), (hw1, y1), (-hw1, y1)],
            closed=True, facecolor=color, edgecolor=BG_PAGE, linewidth=2,
            alpha=0.95,
        )
        ax.add_patch(poly)
        cy = (y0 + y1) / 2
        ax.text(0, cy + 0.04, label, ha="center", va="center",
                color="#FFFFFF", fontsize=15, weight="bold")
        ax.text(0, cy - 0.05, sub, ha="center", va="center",
                color="#FFFFFF", fontsize=10.5)

    # 右侧注释
    ax.annotate("回答：长期“配什么”",
                xy=(0.95, 0.18), xytext=(1.25, 0.18),
                color=ACCENT_2, fontsize=11, va="center",
                arrowprops=dict(arrowstyle="-", color=ACCENT_2, lw=1))
    ax.annotate("回答：阶段性“偏多少”",
                xy=(0.78, 0.51), xytext=(1.25, 0.51),
                color=ACCENT_3, fontsize=11, va="center",
                arrowprops=dict(arrowstyle="-", color=ACCENT_3, lw=1))
    ax.annotate("回答：何时“拉回来”",
                xy=(0.55, 0.79), xytext=(1.25, 0.79),
                color=ACCENT, fontsize=11, va="center",
                arrowprops=dict(arrowstyle="-", color=ACCENT, lw=1))

    ax.set_xlim(-1.1, 2.5)
    ax.set_ylim(-0.08, 1.05)
    ax.set_xticks([])
    ax.set_yticks([])
    for spine in ax.spines.values():
        spine.set_visible(False)
    ax.set_title("SAA / TAA / 动态再平衡 三层框架", fontsize=14, pad=10)
    save(fig, "chart_three_layer_pyramid.png")


def chart_fof_market_growth() -> None:
    """公募 FOF 市场规模与产品数增长（P9）。"""
    years = list(range(2017, 2026))
    # 示意性估算（亿元）
    size = [10, 60, 220, 510, 880, 1100, 1300, 1400, 1500]
    count = [5, 60, 140, 220, 320, 380, 440, 480, 520]

    fig, ax1 = plt.subplots(figsize=(10, 5.5))
    bars = ax1.bar(years, size, color=ACCENT, alpha=0.92,
                   edgecolor=BG_DARK, width=0.65, label="规模(亿元)")
    for b, v in zip(bars, size):
        ax1.text(b.get_x() + b.get_width()/2, v + 30, f"{v}",
                 ha="center", color=TEXT, fontsize=9)
    ax1.set_ylabel("规模(亿元)", color=ACCENT, fontsize=11)
    ax1.set_xlabel("年份", fontsize=11)
    ax1.set_ylim(0, max(size) * 1.25)
    ax1.tick_params(axis="y", colors=ACCENT)
    ax1.grid(True, axis="y", linestyle="--", alpha=0.3)

    ax2 = ax1.twinx()
    ax2.plot(years, count, color=ACCENT_2, marker="o",
             linewidth=2.2, label="产品数")
    ax2.set_ylabel("产品数(只)", color=ACCENT_2, fontsize=11)
    ax2.tick_params(axis="y", colors=ACCENT_2)
    ax2.set_ylim(0, max(count) * 1.3)

    ax1.set_title("中国公募 FOF 市场：规模与产品数（2017—2025，示意）",
                  fontsize=13, pad=12)
    ax1.set_xticks(years)
    # combined legend
    h1, l1 = ax1.get_legend_handles_labels()
    h2, l2 = ax2.get_legend_handles_labels()
    ax1.legend(h1 + h2, l1 + l2, facecolor=PANEL, edgecolor=GRID,
               labelcolor=TEXT, loc="upper left")
    save(fig, "chart_fof_market_growth.png")


def chart_nine_assets_grid() -> None:
    """九类资产 3×3 画像卡片（P11）。"""
    from matplotlib.patches import FancyBboxPatch
    cells = [
        # (name, return%, vol%, corr_to_a),
        ("境内权益",     "年化 7%—8%",  "波动 22%",   "与 A 股 1.00"),
        ("港股",         "年化 3%—5%",  "波动 23%",   "与 A 股 0.60"),
        ("海外权益",     "年化 10%—14%", "波动 18%",   "与 A 股 0.30"),
        ("利率债",       "年化 4%",      "波动 2.5%",  "与 A 股 -0.05"),
        ("信用债",       "年化 5%",      "波动 4%",    "与 A 股 0.15"),
        ("可转债",       "年化 6%—8%",   "波动 12%",   "与 A 股 0.70"),
        ("黄金 / 商品",  "年化 7%",      "波动 14%",   "与 A 股 0.10"),
        ("公募 REITs",   "年化 5%—6%",   "波动 11%",   "与 A 股 0.40"),
        ("现金 / 货基",  "年化 2%",      "波动 0.2%",  "与 A 股 0.00"),
    ]
    fig, ax = plt.subplots(figsize=(14, 6.2))
    ax.set_xlim(0, 3)
    ax.set_ylim(0, 3)
    ax.set_aspect("auto")
    pad = 0.06
    colors_cycle = [ACCENT, ACCENT_2, ACCENT_3, ACCENT, ACCENT_2,
                    ACCENT_3, ACCENT, ACCENT_2, ACCENT_3]
    for idx, (name, r, v, c) in enumerate(cells):
        col = idx % 3
        row = 2 - idx // 3
        x = col + pad
        y = row + pad
        w = 1 - 2 * pad
        h = 1 - 2 * pad
        box = FancyBboxPatch(
            (x, y), w, h, boxstyle="round,pad=0.01,rounding_size=0.04",
            linewidth=1.2, edgecolor="#CBD5E1", facecolor=BG_CARD,
        )
        ax.add_patch(box)
        bar = FancyBboxPatch(
            (x, y), 0.06, h, boxstyle="round,pad=0.0,rounding_size=0.02",
            linewidth=0, facecolor=colors_cycle[idx],
        )
        ax.add_patch(bar)
        ax.text(x + 0.13, y + h - 0.20, name,
                color=INK, fontsize=14, weight="bold", va="center")
        ax.text(x + 0.13, y + h - 0.45, r,
                color=colors_cycle[idx], fontsize=11, va="center",
                weight="bold")
        ax.text(x + 0.13, y + h - 0.65, v,
                color=TXT_DIM, fontsize=11, va="center")
        ax.text(x + 0.13, y + h - 0.85, c,
                color=TXT_DIM, fontsize=11, va="center")
    ax.set_xticks([])
    ax.set_yticks([])
    for spine in ax.spines.values():
        spine.set_visible(False)
    ax.set_title("九类可投资产画像卡片（示意）", fontsize=14, pad=10)
    save(fig, "chart_nine_assets_grid.png")


def chart_equity_matrix() -> None:
    """境内权益 市值 × 风格 2D 矩阵图（P14）。"""
    from matplotlib.patches import FancyBboxPatch
    rows = ["大盘", "中盘", "小盘"]          # 市值
    cols = ["价值 / 红利", "质量", "成长"]    # 风格
    cells = {
        ("大盘", "价值 / 红利"): ("沪深 300 / 红利低波", ACCENT_2),
        ("大盘", "质量"):       ("中证 A50 / 上证 50", ACCENT),
        ("大盘", "成长"):       ("沪深 300 成长", ACCENT_3),
        ("中盘", "价值 / 红利"): ("中证 500 红利", ACCENT_2),
        ("中盘", "质量"):       ("中证 500 质量", ACCENT),
        ("中盘", "成长"):       ("中证 500 / 创业板", ACCENT_3),
        ("小盘", "价值 / 红利"): ("中证 1000 红利", ACCENT_2),
        ("小盘", "质量"):       ("中证 1000 质量", ACCENT),
        ("小盘", "成长"):       ("中证 1000 / 科创板", ACCENT_3),
    }
    fig, ax = plt.subplots(figsize=(11, 5.6))
    n_rows, n_cols = len(rows), len(cols)
    ax.set_xlim(0, n_cols + 1.1)
    ax.set_ylim(0, n_rows + 0.8)
    # column header
    for j, c in enumerate(cols):
        ax.text(j + 1.4, n_rows + 0.45, c, ha="center", va="center",
                color=ACCENT, fontsize=12, weight="bold")
    # row header
    for i, r in enumerate(rows):
        ax.text(0.4, n_rows - i - 0.5, r, ha="center", va="center",
                color=ACCENT, fontsize=12, weight="bold")
    for (rn, cn), (label, color) in cells.items():
        i = rows.index(rn)
        j = cols.index(cn)
        x = j + 0.9
        y = n_rows - i - 1 + 0.1
        box = FancyBboxPatch(
            (x, y), 1.0, 0.8, boxstyle="round,pad=0.01,rounding_size=0.06",
            facecolor=PANEL, edgecolor=color, linewidth=1.5,
        )
        ax.add_patch(box)
        ax.text(x + 0.5, y + 0.4, label, ha="center", va="center",
                color=TEXT, fontsize=11)
    ax.set_xticks([])
    ax.set_yticks([])
    for spine in ax.spines.values():
        spine.set_visible(False)
    ax.set_title("境内权益：市值 × 风格  二维矩阵（示意）", fontsize=14, pad=8)
    ax.text(n_cols + 1.0, n_rows + 0.45, "→ 风格",
            color=TXT_DIM, fontsize=10, ha="right", va="center")
    ax.text(0.4, 0.1, "↑ 市值", color=TXT_DIM, fontsize=10,
            ha="center", va="center")
    save(fig, "chart_equity_matrix.png")


def chart_bond_allocation() -> None:
    """稳健型 FOF 债券底仓建议配比（P17）饼图。"""
    labels = ["利率债 40%", "高等级信用 40%", "可转债 10%", "中资美元债 10%"]
    sizes = [40, 40, 10, 10]
    colors = [ACCENT_2, ACCENT_3, ACCENT, ACCENT_5]
    fig, ax = plt.subplots(figsize=(8.5, 5.6))
    wedges, _ = ax.pie(
        sizes, colors=colors, startangle=90,
        wedgeprops=dict(width=0.42, edgecolor=BG_PAGE, linewidth=2),
    )
    # central label
    ax.text(0, 0.05, "债券底仓", ha="center", va="center",
            color=ACCENT, fontsize=14, weight="bold")
    ax.text(0, -0.18, "稳健型 FOF 建议", ha="center", va="center",
            color=TXT_DIM, fontsize=10)
    # outer labels
    angles = []
    cum = 0
    for s in sizes:
        cum += s
        angles.append((cum - s / 2) / 100 * 360 + 90)
    for ang, label, color in zip(angles, labels, colors):
        rad = np.deg2rad(ang)
        x = 1.25 * np.cos(rad)
        y = 1.25 * np.sin(rad)
        ha = "left" if x >= 0 else "right"
        ax.text(x, y, label, ha=ha, va="center", color=color,
                fontsize=12, weight="bold")
    ax.set_xlim(-1.9, 1.9)
    ax.set_ylim(-1.4, 1.4)
    ax.set_title("稳健型 FOF 债券底仓建议（示意）", fontsize=13, pad=12)
    save(fig, "chart_bond_allocation.png")


def chart_risk_budget() -> None:
    """60/40 资金权重 vs 风险贡献 对比柱状图（P21）。"""
    categories = ["资金权重", "风险贡献"]
    stock = [60, 92]
    bond  = [40, 8]
    x = np.arange(len(categories))
    width = 0.55

    fig, ax = plt.subplots(figsize=(10, 5.6))
    b1 = ax.bar(x, stock, width, color=ACCENT_4, label="股票", edgecolor=BG_PAGE)
    b2 = ax.bar(x, bond,  width, bottom=stock, color=ACCENT_2,
                label="债券", edgecolor=BG_PAGE)
    for i in range(len(x)):
        ax.text(i, stock[i] / 2, f"股票 {stock[i]}%",
                ha="center", va="center", color="#FFFFFF",
                fontsize=14, weight="bold")
        ax.text(i, stock[i] + bond[i] / 2, f"债券 {bond[i]}%",
                ha="center", va="center", color="#FFFFFF",
                fontsize=12, weight="bold")
        ax.text(i, 105, categories[i], ha="center",
                color=INK, fontsize=14, weight="bold")
    ax.set_ylim(0, 115)
    ax.set_xticks([])
    ax.set_yticks([0, 25, 50, 75, 100])
    ax.set_yticklabels(["0%", "25%", "50%", "75%", "100%"])
    ax.axhline(50, color=GRID, linewidth=1, linestyle="--", alpha=0.6)
    ax.text(1.45, 70, "→  名义“股 6 债 4”\n     实质“股 9 债 1”",
            color=ACCENT, fontsize=12, va="center")
    ax.set_title("同一个 60 / 40 组合：资金权重 vs 风险贡献",
                 fontsize=13, pad=14)
    ax.legend(facecolor=PANEL, edgecolor=GRID, labelcolor=TEXT,
              loc="upper right")
    save(fig, "chart_risk_budget.png")


def chart_rebalance_compare() -> None:
    """再平衡机制三种触发方式对比（P28）。"""
    fig, axes = plt.subplots(1, 3, figsize=(14, 4.6))

    # Panel 1: 定期（日历）
    ax = axes[0]
    months = np.arange(0, 24)
    target = np.ones_like(months) * 60
    actual = 60 + 8 * np.sin(months / 2.0)
    ax.plot(months, target, color=ACCENT, linewidth=1.5, linestyle="--",
            label="目标 60%")
    ax.plot(months, actual, color=ACCENT_2, linewidth=1.8, label="实际权重")
    # quarterly triggers
    for q in range(3, 24, 3):
        ax.axvline(q, color=ACCENT_4, alpha=0.5, linewidth=1)
    ax.set_title("定期触发（每季度）", color=TEXT, fontsize=12, pad=8)
    ax.set_xlabel("月", color=TEXT)
    ax.set_ylim(45, 75)
    ax.legend(facecolor=PANEL, edgecolor=GRID, labelcolor=TEXT, fontsize=9,
              loc="upper right")
    ax.grid(True, linestyle="--", alpha=0.3)

    # Panel 2: 阈值
    ax = axes[1]
    actual2 = 60 + 6 * np.sin(months / 1.8) + 3 * np.cos(months / 1.1)
    ax.plot(months, np.ones_like(months) * 60, color=ACCENT,
            linestyle="--", linewidth=1.5, label="目标 60%")
    ax.plot(months, actual2, color=ACCENT_2, linewidth=1.8, label="实际权重")
    ax.fill_between(months, 55, 65, color=ACCENT_3, alpha=0.15,
                    label="±5% 区间带")
    # trigger points
    for i, v in enumerate(actual2):
        if v > 65 or v < 55:
            ax.scatter([months[i]], [v], color=ACCENT_4, s=40, zorder=5)
    ax.set_title("阈值触发（±5%）", color=TEXT, fontsize=12, pad=8)
    ax.set_xlabel("月", color=TEXT)
    ax.set_ylim(45, 75)
    ax.legend(facecolor=PANEL, edgecolor=GRID, labelcolor=TEXT,
              fontsize=9, loc="upper right")
    ax.grid(True, linestyle="--", alpha=0.3)

    # Panel 3: 波动率触发
    ax = axes[2]
    vol = 8 + 4 * np.sin(months / 1.5) + np.random.default_rng(7).normal(0, 1.0, 24)
    threshold = 12
    ax.plot(months, vol, color=ACCENT_2, linewidth=1.8, label="组合波动率(%)")
    ax.axhline(threshold, color=ACCENT_4, linestyle="--", linewidth=1.5,
               label="降仓阈值 12%")
    for i, v in enumerate(vol):
        if v > threshold:
            ax.scatter([months[i]], [v], color=ACCENT_4, s=40, zorder=5)
    ax.set_title("波动率触发（突破即降仓）", color=TEXT, fontsize=12, pad=8)
    ax.set_xlabel("月", color=TEXT)
    ax.set_ylim(2, 16)
    ax.legend(facecolor=PANEL, edgecolor=GRID, labelcolor=TEXT,
              fontsize=9, loc="upper right")
    ax.grid(True, linestyle="--", alpha=0.3)

    fig.suptitle("再平衡的三种触发机制：直观对比", fontsize=14,
                 color=TEXT, y=1.02)
    save(fig, "chart_rebalance_compare.png")


def chart_alternative_alloc() -> None:
    """另类敞口配置区间（P34）堆叠条形图。"""
    fig, ax = plt.subplots(figsize=(10, 5.6))
    # 三类另类资产，每类给 min/max 区间
    categories = ["公募 REITs", "黄金 ETF", "商品 ETF"]
    mins = [3, 3, 0]
    maxs = [6, 7, 2]
    colors = [ACCENT_2, ACCENT, ACCENT_3]
    y = np.arange(len(categories))
    for i, (mn, mx, c) in enumerate(zip(mins, maxs, colors)):
        ax.barh(y[i], mx - mn, left=mn, color=c, height=0.55,
                edgecolor=BG_PAGE)
        ax.text(mn - 0.3, y[i], f"{mn}%", ha="right", va="center",
                color=TXT_DIM, fontsize=10)
        ax.text(mx + 0.3, y[i], f"{mx}%", ha="left", va="center",
                color=INK, fontsize=11, weight="bold")
        ax.text((mn + mx) / 2, y[i], categories[i],
                ha="center", va="center", color="#FFFFFF",
                fontsize=12, weight="bold")
    # total range overlay
    ax.axvspan(6, 15, color=ACCENT, alpha=0.08)
    ax.axvline(6,  color=ACCENT, linewidth=1, linestyle="--", alpha=0.7)
    ax.axvline(15, color=ACCENT, linewidth=1, linestyle="--", alpha=0.7)
    ax.text(10.5, -0.65,
            "另类合计配比建议 6%—15%   →   Sharpe 提升 0.1—0.3",
            ha="center", color=ACCENT, fontsize=11, weight="bold")
    ax.set_yticks(y)
    ax.set_yticklabels([])
    ax.set_xlabel("组合占比 (%)", color=TEXT)
    ax.set_xlim(-1.2, 17)
    ax.set_ylim(-1.0, len(categories) - 0.4)
    ax.set_xticks(range(0, 17, 2))
    ax.grid(True, axis="x", linestyle="--", alpha=0.3)
    ax.set_title("公募 FOF 另类敞口配置区间（示意）", fontsize=13, pad=12)
    save(fig, "chart_alternative_alloc.png")


def chart_glide_path() -> None:
    """目标日期 FOF 下滑曲线（P36）。"""
    years_to_retire = np.arange(40, -1, -1)
    # 国际通用版（如 Vanguard 风格）
    intl = np.piecewise(
        years_to_retire.astype(float),
        [years_to_retire >= 25, (years_to_retire < 25) & (years_to_retire >= 5),
         years_to_retire < 5],
        [lambda y: 90.0 - (40 - y) * 0,
         lambda y: 90 - (25 - y) / 20 * 60,
         lambda y: 30 - (5 - y) / 5 * 10],
    )
    # 本土化更陡版
    cn = np.piecewise(
        years_to_retire.astype(float),
        [years_to_retire >= 30, (years_to_retire < 30) & (years_to_retire >= 5),
         years_to_retire < 5],
        [lambda y: 80.0,
         lambda y: 80 - (30 - y) / 25 * 55,
         lambda y: 25 - (5 - y) / 5 * 5],
    )
    fig, ax = plt.subplots(figsize=(10, 5.4))
    ax.plot(years_to_retire, intl, color=ACCENT_2, linewidth=2.0,
            label="国际通用下滑曲线", linestyle="--")
    ax.plot(years_to_retire, cn, color=ACCENT, linewidth=2.6,
            label="国内本土化（更陡）")
    ax.fill_between(years_to_retire, 0, cn, color=ACCENT, alpha=0.10)
    ax.set_xlabel("距退休年限", color=TEXT)
    ax.set_ylabel("权益资产占比 (%)", color=TEXT)
    ax.invert_xaxis()  # 离退休越近越靠右
    ax.set_ylim(0, 100)
    ax.set_xlim(40, 0)
    # 关键节点标注
    ax.scatter([40], [intl[0]], color=ACCENT_2, s=60, zorder=5)
    ax.scatter([0],  [intl[-1]], color=ACCENT_2, s=60, zorder=5)
    ax.scatter([40], [cn[0]],   color=ACCENT, s=80, zorder=5)
    ax.scatter([0],  [cn[-1]],  color=ACCENT, s=80, zorder=5)
    ax.annotate("入职期\n权益 80%—90%", xy=(40, 85), xytext=(35, 92),
                color=TEXT, fontsize=10,
                arrowprops=dict(arrowstyle="->", color=GRID))
    ax.annotate("退休后\n权益 20%—25%", xy=(0, 22), xytext=(6, 8),
                color=TEXT, fontsize=10,
                arrowprops=dict(arrowstyle="->", color=GRID))
    ax.grid(True, linestyle="--", alpha=0.3)
    ax.legend(facecolor=PANEL, edgecolor=GRID, labelcolor=TEXT,
              loc="upper right")
    ax.set_title("养老 FOF 下滑曲线：国际通用 vs 国内本土化（示意）",
                 fontsize=13, pad=12)
    save(fig, "chart_glide_path.png")


def chart_single_vs_fof() -> None:
    """单一资产/单一基金 vs FOF 结构对比（P6）。"""
    from matplotlib.patches import FancyBboxPatch, FancyArrowPatch
    fig, ax = plt.subplots(figsize=(13.5, 6.0))
    ax.set_xlim(0, 12)
    ax.set_ylim(0, 7)

    def box(x, y, w, h, label, color, sub=None, fc=BG_CARD):
        rect = FancyBboxPatch(
            (x, y), w, h, boxstyle="round,pad=0.02,rounding_size=0.08",
            facecolor=fc, edgecolor=color, linewidth=2,
        )
        ax.add_patch(rect)
        ax.text(x + w / 2, y + h / 2 + (0.10 if sub else 0),
                label, ha="center", va="center",
                color=INK, fontsize=12, weight="bold")
        if sub:
            ax.text(x + w / 2, y + h / 2 - 0.30, sub,
                    ha="center", va="center", color=TXT_DIM, fontsize=10)

    def arrow(x0, y0, x1, y1, color=TXT_DIM):
        a = FancyArrowPatch((x0, y0), (x1, y1),
                            arrowstyle="->", color=color, lw=1.4,
                            mutation_scale=14)
        ax.add_patch(a)

    # === 左：单一基金 ===
    ax.text(2.6, 6.5, "单一基金", color=ACCENT_4, fontsize=15,
            weight="bold", ha="center")
    ax.text(2.6, 6.05, "→ 靠人 + 靠天 双重风险",
            color=TXT_DIM, fontsize=10.5, ha="center")
    box(1.6, 4.6, 2.0, 0.9, "客户", ACCENT_2)
    arrow(2.6, 4.55, 2.6, 4.05)
    box(1.6, 3.0, 2.0, 0.9, "1 位基金经理", ACCENT_4)
    arrow(2.6, 2.95, 2.6, 2.45)
    box(0.6, 1.4, 4.0, 0.9, "单一资产 / 单一风格暴露", ACCENT_4,
        sub="若行情逆风，组合无避风港")

    # === 右：FOF ===
    ax.text(9.0, 6.5, "FOF 双层结构", color=ACCENT_3, fontsize=15,
            weight="bold", ha="center")
    ax.text(9.0, 6.05, "→ 在“人”与“天”两个维度同时分散",
            color=TXT_DIM, fontsize=10.5, ha="center")
    box(8.0, 4.6, 2.0, 0.9, "客户", ACCENT_2)
    arrow(9.0, 4.55, 9.0, 4.05)
    box(8.0, 3.0, 2.0, 0.9, "1 位 FOF 管理人", ACCENT_3)
    # arrows to sub-managers
    for sx in [7.0, 9.0, 11.0]:
        arrow(9.0, 2.95, sx, 2.45)
    box(6.4, 1.4, 1.2, 0.9, "经理 A", ACCENT)
    box(8.4, 1.4, 1.2, 0.9, "经理 B", ACCENT)
    box(10.4, 1.4, 1.2, 0.9, "经理 C", ACCENT)
    # below: assets
    ax.text(9.0, 0.7,
            "  全球股 · 债 · 商品 · 黄金 · REITs · 跨市场跨风格的子基金组合  ",
            ha="center", va="center", color=INK, fontsize=10.5,
            weight="bold",
            bbox=dict(boxstyle="round,pad=0.4", fc=BG_CARD2,
                      ec=ACCENT_3, lw=1.2))

    # divider line
    ax.plot([5.5, 5.5], [0.5, 6.5], color="#CBD5E1",
            linewidth=1, linestyle="--")

    ax.set_xticks([])
    ax.set_yticks([])
    for spine in ax.spines.values():
        spine.set_visible(False)
    ax.set_title("单一基金  vs  FOF 双层结构（资产 × 管理人 双维度分散）",
                 fontsize=14, pad=10)
    save(fig, "chart_single_vs_fof.png")


def chart_ah_premium() -> None:
    """AH 溢价指数历史走势示意（P15）。"""
    rng = np.random.default_rng(42)
    years = np.arange(2010, 2026, 0.25)
    n = len(years)
    # 大致复刻历史区间走势（示意性）
    trend = (115
             + 25 * np.sin(np.arange(n) / 9.0 + 1.0)
             + 8 * np.cos(np.arange(n) / 3.0)
             + rng.normal(0, 3, n))
    # ensure peaks/troughs roughly
    trend[20:28] += 18   # 2015 牛市
    trend[40:48] += 10   # 2020 港股反弹
    trend = np.clip(trend, 95, 165)

    fig, ax = plt.subplots(figsize=(11, 5.4))
    ax.fill_between(years, 100, trend, where=(trend >= 100),
                    color=ACCENT, alpha=0.18)
    ax.plot(years, trend, color=ACCENT, linewidth=2.4)
    ax.axhline(100, color=TXT_DIM, linewidth=1, linestyle="--",
               label="100 = AH 等价")
    ax.axhline(130, color=ACCENT_2, linewidth=1, linestyle=":")
    ax.axhline(150, color=ACCENT_4, linewidth=1, linestyle=":")
    ax.text(2010.2, 132, "中枢 ~130", color=ACCENT_2, fontsize=10, va="bottom")
    ax.text(2010.2, 152, "极端 ~150", color=ACCENT_4, fontsize=10, va="bottom")

    # 关键事件
    notes = [
        (2015.4, "2015 A 股牛市"),
        (2018.6, "贸易摩擦"),
        (2020.6, "疫情反弹"),
        (2024.5, "估值修复期权"),
    ]
    for x, txt in notes:
        ax.scatter([x], [np.interp(x, years, trend)],
                   color=ACCENT_4, s=42, zorder=5,
                   edgecolors=BG_PAGE, linewidth=1.2)
        ax.annotate(txt, xy=(x, np.interp(x, years, trend)),
                    xytext=(x + 0.2, np.interp(x, years, trend) + 8),
                    fontsize=9.5, color=INK,
                    arrowprops=dict(arrowstyle="-", color=TXT_DIM, lw=0.8))
    ax.set_xlabel("年份", color=INK)
    ax.set_ylabel("AH 溢价指数", color=INK)
    ax.set_ylim(95, 170)
    ax.set_xlim(2010, 2026)
    ax.grid(True, linestyle="--", alpha=0.5)
    ax.legend(facecolor=BG_CARD, edgecolor=GRID, labelcolor=INK,
              loc="lower right")
    ax.set_title("AH 溢价指数走势（2010—2025，示意）", fontsize=14, pad=10)
    save(fig, "chart_ah_premium.png")


def chart_global_equity_alloc() -> None:
    """海外权益区域配置建议（P16），水平堆叠条形。"""
    regions = [
        ("标普 500",   30, ACCENT_2),
        ("纳指 100",   20, ACCENT_3),
        ("欧洲 STOXX", 15, ACCENT),
        ("日本",       12, ACCENT_5),
        ("印度",       10, ACCENT_4),
        ("越南 / 新兴",  8, "#06B6D4"),
        ("罗素 2000",   5, "#EC4899"),
    ]
    fig, ax = plt.subplots(figsize=(11, 4.0))
    left = 0
    for name, w, c in regions:
        ax.barh([0], [w], left=left, color=c, height=0.55,
                edgecolor=BG_PAGE, linewidth=2)
        ax.text(left + w / 2, 0, f"{name}\n{w}%",
                ha="center", va="center", color="#FFFFFF",
                fontsize=10.5, weight="bold")
        left += w
    ax.set_xlim(0, 100)
    ax.set_ylim(-1.4, 1.4)
    ax.set_yticks([])
    ax.set_xticks([0, 25, 50, 75, 100])
    ax.set_xticklabels(["0%", "25%", "50%", "75%", "100%"], color=TXT_DIM)
    ax.set_title("公募 FOF 海外权益敞口的区域配置建议（示意）",
                 fontsize=14, pad=14)
    ax.text(50, -0.95,
            "美股核心 50%  ·  欧日均衡 27%  ·  新兴 α 增厚 18%  ·  小盘补完 5%",
            ha="center", color=INK, fontsize=11, weight="bold")
    for spine in ["top", "right", "left"]:
        ax.spines[spine].set_visible(False)
    ax.spines["bottom"].set_color("#CBD5E1")
    save(fig, "chart_global_equity_alloc.png")


def chart_commodity_etfs() -> None:
    """四类商品 ETF 卡片对比（P18）。"""
    from matplotlib.patches import FancyBboxPatch
    cards = [
        ("黄金 ETF",   "5%—10%", "避险 · 抗通胀\n美元对冲",         ACCENT),
        ("豆粕 ETF",   "0%—3%",  "农产品代理\n对冲 CPI 上行",      ACCENT_3),
        ("有色金属",   "0%—3%",  "铜 / 铝周期代理\n再通胀场景受益", ACCENT_4),
        ("能化 ETF",   "0%—2%",  "油气链条代理\n地缘冲突对冲",      ACCENT_5),
    ]
    fig, ax = plt.subplots(figsize=(13.5, 4.6))
    ax.set_xlim(0, 4)
    ax.set_ylim(0, 1)
    for i, (name, pct, use, color) in enumerate(cards):
        x = i + 0.08
        w = 0.84
        rect = FancyBboxPatch(
            (x, 0.10), w, 0.80,
            boxstyle="round,pad=0.02,rounding_size=0.06",
            facecolor=BG_CARD, edgecolor=color, linewidth=2,
        )
        ax.add_patch(rect)
        # top color strip
        top_strip = FancyBboxPatch(
            (x, 0.78), w, 0.12,
            boxstyle="round,pad=0.0,rounding_size=0.04",
            facecolor=color, edgecolor=color,
        )
        ax.add_patch(top_strip)
        ax.text(x + w / 2, 0.835, name, ha="center", va="center",
                color="#FFFFFF", fontsize=14, weight="bold")
        ax.text(x + w / 2, 0.62, pct, ha="center", va="center",
                color=color, fontsize=22, weight="bold")
        ax.text(x + w / 2, 0.48, "建议组合占比",
                ha="center", color=TXT_DIM, fontsize=9.5)
        ax.text(x + w / 2, 0.30, use, ha="center", va="center",
                color=INK, fontsize=11)
    ax.set_xticks([])
    ax.set_yticks([])
    for spine in ax.spines.values():
        spine.set_visible(False)
    ax.set_title("公募 FOF 的“类商品”通道：四类 ETF 工具", fontsize=14, pad=10)
    save(fig, "chart_commodity_etfs.png")


def chart_reits_breakdown() -> None:
    """公募 REITs 底层资产类型 + 关键指标（P19）。"""
    sectors = [
        ("产业园 / 物流", 35, ACCENT_2),
        ("保障性租赁",   20, ACCENT_3),
        ("仓储 / 物流",  15, ACCENT),
        ("高速公路",     15, ACCENT_5),
        ("能源 / 水务",  10, ACCENT_4),
        ("生态环保",      5, "#06B6D4"),
    ]
    fig, axes = plt.subplots(1, 2, figsize=(13.5, 5.5),
                             gridspec_kw={"width_ratios": [1.05, 1]})

    ax = axes[0]
    sizes = [s[1] for s in sectors]
    colors = [s[2] for s in sectors]
    labels = [f"{s[0]}  {s[1]}%" for s in sectors]
    wedges, _ = ax.pie(sizes, colors=colors, startangle=90,
                       wedgeprops=dict(width=0.45,
                                       edgecolor=BG_PAGE, linewidth=2))
    ax.text(0, 0.08, "公募 REITs", ha="center", va="center",
            color=ACCENT, fontsize=14, weight="bold")
    ax.text(0, -0.18, "底层资产构成", ha="center", va="center",
            color=TXT_DIM, fontsize=11)
    ax.legend(wedges, labels, facecolor=BG_CARD, edgecolor=GRID,
              labelcolor=INK, loc="center left",
              bbox_to_anchor=(1.0, 0.5), fontsize=10)
    ax.set_title("REITs 底层资产构成（示意）", fontsize=13, pad=10)

    # right: key metrics card
    ax = axes[1]
    ax.set_xlim(0, 1)
    ax.set_ylim(0, 1)
    metrics = [
        ("分红率",      "4%—8%",   "高于 10Y 国债 2—5%"),
        ("市场规模",    "≈1500 亿", "2021 年起 4 年增长 8 倍"),
        ("与 A 股相关",  "0.40",    "提供 α + 分散度"),
        ("建议占比",    "3%—8%",   "稳健 FOF 的“第三类资产”"),
    ]
    from matplotlib.patches import FancyBboxPatch
    for i, (k, v, sub) in enumerate(metrics):
        y = 0.78 - i * 0.22
        rect = FancyBboxPatch(
            (0.04, y - 0.09), 0.92, 0.18,
            boxstyle="round,pad=0.01,rounding_size=0.03",
            facecolor=BG_CARD, edgecolor=GRID, linewidth=1,
        )
        ax.add_patch(rect)
        ax.text(0.10, y + 0.02, k, color=TXT_DIM, fontsize=11)
        ax.text(0.10, y - 0.05, sub, color=INK, fontsize=10.5)
        ax.text(0.90, y - 0.01, v, color=ACCENT, fontsize=18,
                weight="bold", ha="right", va="center")
    ax.set_xticks([])
    ax.set_yticks([])
    for spine in ax.spines.values():
        spine.set_visible(False)
    ax.set_title("REITs 关键指标", fontsize=13, pad=10)
    save(fig, "chart_reits_breakdown.png")


def chart_rp_methods() -> None:
    """ERC / MDP / MV 三种风险预算方法对比（P22）。"""
    methods = ["ERC（等风险贡献）", "MDP（最大分散）", "MV（最小方差）"]
    assets = ["权益", "信用债", "利率债", "黄金"]
    weights = {
        "ERC（等风险贡献）": [25, 25, 30, 20],
        "MDP（最大分散）":   [30, 20, 25, 25],
        "MV（最小方差）":    [10, 25, 50, 15],
    }
    colors = [ACCENT, ACCENT_3, ACCENT_2, ACCENT_5]

    fig, axes = plt.subplots(1, 3, figsize=(13.5, 5.0))
    for ax, m in zip(axes, methods):
        w = weights[m]
        ax.pie(w, colors=colors, startangle=90,
               wedgeprops=dict(width=0.50,
                               edgecolor=BG_PAGE, linewidth=2),
               labels=[f"{a}\n{wi}%" for a, wi in zip(assets, w)],
               labeldistance=1.18, textprops=dict(color=INK, fontsize=10))
        ax.set_title(m, fontsize=12.5, color=INK, weight="bold", pad=8)

    # legend on bottom
    fig.suptitle("同一资产池在三种风险预算算法下的配比（示意）",
                 fontsize=14, color=INK, y=1.02)
    save(fig, "chart_rp_methods.png")


def chart_three_layer_funnel() -> None:
    """风险预算三层下沉漏斗（P23）。"""
    from matplotlib.patches import Polygon
    fig, ax = plt.subplots(figsize=(10.5, 5.8))
    layers = [
        (0.66, 0.92, 0.90, 0.70,
         "第 1 层 · 大类资产",
         "股 / 债 / 商品 / REITs / 现金", ACCENT_2),
        (0.34, 0.66, 0.70, 0.45,
         "第 2 层 · 风格因子",
         "价值 / 成长 / 红利 / 低波 / 质量", ACCENT_3),
        (0.02, 0.34, 0.45, 0.20,
         "第 3 层 · 子基金",
         "经理画像 / 容量 / 风格穿透", ACCENT),
    ]
    for y0, y1, hw0, hw1, label, sub, color in layers:
        poly = Polygon(
            [(-hw0, y0), (hw0, y0), (hw1, y1), (-hw1, y1)],
            facecolor=color, edgecolor=BG_PAGE, linewidth=2, alpha=0.95,
        )
        ax.add_patch(poly)
        cy = (y0 + y1) / 2
        ax.text(0, cy + 0.04, label, ha="center", va="center",
                color="#FFFFFF", fontsize=14, weight="bold")
        ax.text(0, cy - 0.05, sub, ha="center", va="center",
                color="#FFFFFF", fontsize=10.5)
    # 右侧注释
    ax.annotate("总风险预算 100%", xy=(0.90, 0.79), xytext=(1.20, 0.79),
                color=ACCENT_2, fontsize=11, va="center",
                arrowprops=dict(arrowstyle="-", color=ACCENT_2, lw=1))
    ax.annotate("风格风险 60%", xy=(0.70, 0.50), xytext=(1.20, 0.50),
                color=ACCENT_3, fontsize=11, va="center",
                arrowprops=dict(arrowstyle="-", color=ACCENT_3, lw=1))
    ax.annotate("单基金 ≤ 3%", xy=(0.45, 0.18), xytext=(1.20, 0.18),
                color=ACCENT, fontsize=11, va="center",
                arrowprops=dict(arrowstyle="-", color=ACCENT, lw=1))
    ax.set_xlim(-1.1, 2.4)
    ax.set_ylim(-0.05, 1.05)
    ax.set_xticks([])
    ax.set_yticks([])
    for spine in ax.spines.values():
        spine.set_visible(False)
    ax.set_title("风险预算三层下沉：从“黑盒组合”到“透明组合”",
                 fontsize=14, pad=10)
    save(fig, "chart_three_layer_funnel.png")


def chart_prerisk_radar() -> None:
    """事前风控五维雷达图（P25）。"""
    metrics = ["波动率\n上限", "最大回撤\n限制", "CVaR\n约束",
               "跟踪误差\n约束", "单基金\n集中度"]
    # 稳健型 vs 平衡型 vs 进取型（值越大约束越宽）
    stable    = [3, 3, 3, 2, 3]
    balanced  = [4, 4, 4, 3, 4]
    aggressive = [5, 5, 5, 5, 5]
    angles = np.linspace(0, 2 * np.pi, len(metrics), endpoint=False)
    angles = np.concatenate([angles, [angles[0]]])

    def close(values):
        return values + [values[0]]

    fig, ax = plt.subplots(figsize=(8.5, 5.6),
                           subplot_kw=dict(polar=True))
    ax.set_facecolor(BG_PAGE)
    ax.plot(angles, close(stable),    color=ACCENT_2, linewidth=2.4,
            label="稳健型")
    ax.fill(angles, close(stable),    color=ACCENT_2, alpha=0.12)
    ax.plot(angles, close(balanced),  color=ACCENT_3, linewidth=2.4,
            label="平衡型")
    ax.fill(angles, close(balanced),  color=ACCENT_3, alpha=0.12)
    ax.plot(angles, close(aggressive), color=ACCENT, linewidth=2.4,
            label="进取型")
    ax.fill(angles, close(aggressive), color=ACCENT, alpha=0.10)
    ax.set_yticks([1, 2, 3, 4, 5])
    ax.set_yticklabels(["紧", "", "", "", "宽"], color=TXT_DIM,
                       fontsize=9)
    ax.set_xticks(angles[:-1])
    ax.set_xticklabels(metrics, color=INK, fontsize=10.5)
    ax.set_ylim(0, 5.5)
    ax.grid(color=GRID)
    ax.spines["polar"].set_color(GRID)
    ax.set_title("事前风控参数：三档风险偏好对比（示意）",
                 fontsize=13, pad=20)
    ax.legend(facecolor=BG_CARD, edgecolor=GRID, labelcolor=INK,
              loc="upper right", bbox_to_anchor=(1.30, 1.10))
    save(fig, "chart_prerisk_radar.png")


def chart_pension_metrics() -> None:
    """养老 FOF 关键数据 4 卡片（P39）。"""
    from matplotlib.patches import FancyBboxPatch
    cards = [
        ("¥12,000", "/年税优额度", "个人养老金账户上限",   ACCENT),
        ("≈ 200",   "只 Y 份额",   "公募 FOF 已上线",       ACCENT_2),
        ("≈ ¥800 亿", "Y 份额规模",   "2025 年末",             ACCENT_3),
        ("< 10%",   "渗透率",       "未来 5—10 年最确定增量", ACCENT_4),
    ]
    fig, ax = plt.subplots(figsize=(13.5, 4.6))
    ax.set_xlim(0, 4)
    ax.set_ylim(0, 1)
    for i, (big, unit, sub, color) in enumerate(cards):
        x = i + 0.06
        w = 0.88
        rect = FancyBboxPatch(
            (x, 0.10), w, 0.80,
            boxstyle="round,pad=0.02,rounding_size=0.06",
            facecolor=BG_CARD, edgecolor=color, linewidth=2,
        )
        ax.add_patch(rect)
        # top accent strip
        top = FancyBboxPatch(
            (x, 0.82), w, 0.08,
            boxstyle="round,pad=0.0,rounding_size=0.04",
            facecolor=color, edgecolor=color,
        )
        ax.add_patch(top)
        ax.text(x + w / 2, 0.60, big, ha="center", va="center",
                color=color, fontsize=28, weight="bold")
        ax.text(x + w / 2, 0.40, unit, ha="center", va="center",
                color=INK, fontsize=12)
        ax.text(x + w / 2, 0.22, sub, ha="center", va="center",
                color=TXT_DIM, fontsize=10.5)
    ax.set_xticks([])
    ax.set_yticks([])
    for spine in ax.spines.values():
        spine.set_visible(False)
    ax.set_title("第三支柱个人养老金：公募 FOF 最确定的增量",
                 fontsize=14, pad=10)
    save(fig, "chart_pension_metrics.png")


def chart_outlook_pillars() -> None:
    """三大变量三柱图（P41）。"""
    from matplotlib.patches import FancyBboxPatch
    pillars = [
        ("AI 投研",        "+3—5×",    "单分析师覆盖基金数",
         ["大模型加速研报分析",
          "经理风格自动标签",
          "会议纪要信号提取"], ACCENT_2),
        ("数据基础设施",   "持仓穿透 + 因子库",  "FOF 专业化的“地基”",
         ["底层持仓数据库",
          "统一风险因子模型",
          "自动化归因平台"], ACCENT_3),
        ("客户陪伴",       "波动期 > 上涨期", "可信解读决定留存",
         ["定期净值解读",
          "波动期主动沟通",
          "可视化业绩归因"], ACCENT),
    ]
    fig, ax = plt.subplots(figsize=(13.5, 5.8))
    ax.set_xlim(0, 3)
    ax.set_ylim(0, 1)
    for i, (title, hero, sub, lines, color) in enumerate(pillars):
        x = i + 0.06
        w = 0.88
        rect = FancyBboxPatch(
            (x, 0.06), w, 0.88,
            boxstyle="round,pad=0.02,rounding_size=0.06",
            facecolor=BG_CARD, edgecolor=color, linewidth=2,
        )
        ax.add_patch(rect)
        top = FancyBboxPatch(
            (x, 0.84), w, 0.10,
            boxstyle="round,pad=0.0,rounding_size=0.04",
            facecolor=color, edgecolor=color,
        )
        ax.add_patch(top)
        ax.text(x + w / 2, 0.89, title, ha="center", va="center",
                color="#FFFFFF", fontsize=14, weight="bold")
        ax.text(x + w / 2, 0.66, hero, ha="center", va="center",
                color=color, fontsize=20, weight="bold")
        ax.text(x + w / 2, 0.54, sub, ha="center", va="center",
                color=TXT_DIM, fontsize=10.5)
        # bullet lines
        for k, line in enumerate(lines):
            ax.text(x + 0.10, 0.40 - k * 0.09,
                    f"·  {line}", ha="left", va="center",
                    color=INK, fontsize=11)
    ax.set_xticks([])
    ax.set_yticks([])
    for spine in ax.spines.values():
        spine.set_visible(False)
    ax.set_title("公募 FOF 的下一个十年：三大变量",
                 fontsize=14, pad=10)
    save(fig, "chart_outlook_pillars.png")


def main() -> None:
    print("[charts] 开始生成图表 ...")
    # 一期 6 张
    chart_asset_long_term()
    chart_corr_heatmap()
    chart_macro_quadrant()
    chart_all_weather_backtest()
    chart_stress_test()
    chart_attribution()
    # 二期 10 张
    chart_theory_timeline()
    chart_three_layer_pyramid()
    chart_fof_market_growth()
    chart_nine_assets_grid()
    chart_equity_matrix()
    chart_bond_allocation()
    chart_risk_budget()
    chart_rebalance_compare()
    chart_alternative_alloc()
    chart_glide_path()
    # 三期 10 张（白底主题）
    chart_single_vs_fof()
    chart_ah_premium()
    chart_global_equity_alloc()
    chart_commodity_etfs()
    chart_reits_breakdown()
    chart_rp_methods()
    chart_three_layer_funnel()
    chart_prerisk_radar()
    chart_pension_metrics()
    chart_outlook_pillars()
    print("[charts] 全部生成完毕。")


if __name__ == "__main__":
    main()
