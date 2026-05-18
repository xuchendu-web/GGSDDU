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

DARK_BG = "#0E1A2B"
PANEL = "#16273D"
ACCENT = "#E0B574"
ACCENT_2 = "#7BB7E8"
ACCENT_3 = "#7FCBA4"
ACCENT_4 = "#E67D7D"
TEXT = "#F2F4F7"
GRID = "#324863"

plt.rcParams.update(
    {
        "figure.facecolor": DARK_BG,
        "axes.facecolor": PANEL,
        "axes.edgecolor": GRID,
        "axes.labelcolor": TEXT,
        "axes.titlecolor": TEXT,
        "xtick.color": TEXT,
        "ytick.color": TEXT,
        "text.color": TEXT,
        "grid.color": GRID,
        "savefig.facecolor": DARK_BG,
        "savefig.edgecolor": DARK_BG,
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
        "fof_corr", ["#2E5BCB", "#16273D", "#E0B574"]
    )
    im = ax.imshow(data, cmap=cmap, vmin=-0.2, vmax=1.0)
    ax.set_xticks(range(len(labels)), labels, rotation=45, ha="right", fontsize=9)
    ax.set_yticks(range(len(labels)), labels, fontsize=9)
    for i in range(len(labels)):
        for j in range(len(labels)):
            v = data[i, j]
            color = "#0E1A2B" if v > 0.55 else TEXT
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
    ax.axhline(0, color=GRID, linewidth=1.2)
    ax.axvline(0, color=GRID, linewidth=1.2)

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
                    fontsize=9, color=TEXT)
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


def main() -> None:
    print("[charts] 开始生成图表 ...")
    chart_asset_long_term()
    chart_corr_heatmap()
    chart_macro_quadrant()
    chart_all_weather_backtest()
    chart_stress_test()
    chart_attribution()
    print("[charts] 全部生成完毕。")


if __name__ == "__main__":
    main()
