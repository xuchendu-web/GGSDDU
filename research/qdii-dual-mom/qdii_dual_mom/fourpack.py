"""2x2 four-pack: NAV, drawdown, excess vs benchmark, yearly bars."""

from __future__ import annotations

from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import pandas as pd

from .metrics import yearly_stats

from matplotlib import font_manager

_CN = font_manager.FontProperties(family="WenQuanYi Micro Hei")
plt.rcParams["font.sans-serif"] = ["WenQuanYi Micro Hei", "Droid Sans Fallback", "DejaVu Sans"]
plt.rcParams["axes.unicode_minus"] = False


def _dd(nav: pd.Series) -> pd.Series:
    q = nav.astype(float)
    return q / q.cummax().clip(lower=1e-12) - 1.0


def render_fourpack(
    books: dict[str, pd.Series],
    bench_name: str,
    out_png: Path,
    title: str,
    main_name: str | None = None,
) -> Path:
    main_name = main_name or bench_name
    if bench_name not in books:
        raise KeyError(f"bench {bench_name} missing")
    names = list(books)
    fig, axes = plt.subplots(2, 2, figsize=(12.8, 8.2), dpi=140)
    fig.suptitle(title, fontsize=13, fontproperties=_CN)

    ax = axes[0, 0]
    for name, nav in books.items():
        q = nav / nav.iloc[0]
        lw = 2.0 if name == main_name else 1.3
        ls = "-" if name == main_name else "--" if name == "CASH" else "-"
        ax.plot(q.index, q.to_numpy(), label=name, lw=lw, ls=ls)
    ax.set_title("NAV (rebased)", fontproperties=_CN)
    ax.legend(loc="upper left", fontsize=8, frameon=False)
    ax.grid(True, alpha=0.25)

    ax = axes[0, 1]
    for name, nav in books.items():
        ax.plot(nav.index, _dd(nav).to_numpy(), label=name, lw=1.3)
    ax.set_title("Drawdown", fontproperties=_CN)
    ax.grid(True, alpha=0.25)
    ax.yaxis.set_major_formatter(plt.FuncFormatter(lambda x, _p: f"{x:.0%}"))

    ax = axes[1, 0]
    bench = books[bench_name]
    for name, nav in books.items():
        if name == bench_name:
            continue
        aligned = pd.concat([nav, bench], axis=1, join="inner")
        aligned.columns = ["s", "b"]
        xs = aligned["s"] / aligned["s"].iloc[0] / (aligned["b"] / aligned["b"].iloc[0]) - 1.0
        ax.plot(xs.index, xs.to_numpy(), label=f"{name} vs {bench_name}")
    ax.axhline(0.0, color="k", lw=0.8, alpha=0.5)
    ax.set_title(f"Excess vs {bench_name}", fontproperties=_CN)
    ax.legend(loc="upper left", fontsize=8, frameon=False)
    ax.grid(True, alpha=0.25)
    ax.yaxis.set_major_formatter(plt.FuncFormatter(lambda x, _p: f"{x:.0%}"))

    ax = axes[1, 1]
    width = 0.8 / max(len(names), 1)
    years = None
    for i, name in enumerate(names):
        ydf = yearly_stats(books[name])
        if ydf.empty:
            continue
        if years is None:
            years = ydf["year"].tolist()
        x = range(len(ydf))
        ax.bar(
            [xi + (i - (len(names) - 1) / 2) * width for xi in x],
            ydf["ret"],
            width=width,
            label=name,
        )
    if years:
        ax.set_xticks(range(len(years)))
        ax.set_xticklabels([str(y) for y in years])
    ax.axhline(0.0, color="k", lw=0.8, alpha=0.5)
    ax.set_title("Calendar-year return", fontproperties=_CN)
    ax.legend(loc="upper left", fontsize=7, frameon=False)
    ax.grid(True, axis="y", alpha=0.25)
    ax.yaxis.set_major_formatter(plt.FuncFormatter(lambda x, _p: f"{x:.0%}"))

    fig.tight_layout(rect=(0, 0, 1, 0.96))
    out_png = Path(out_png)
    out_png.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(out_png)
    plt.close(fig)
    return out_png
