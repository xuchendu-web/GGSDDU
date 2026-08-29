"""看板 HTML 渲染，Streamlit 与静态导出共用。"""

from __future__ import annotations

import html

import numpy as np
import pandas as pd

TABLE_CSS = """
.hero {
  display: flex; justify-content: space-between; align-items: flex-end;
  border-bottom: 1px solid #2a3344; padding-bottom: 12px; margin-bottom: 14px;
}
.hero h1 { color: #f3e6b8; font-size: 1.55rem; margin: 0; letter-spacing: 0.04em; }
.hero .sub { color: #8b97a8; font-size: 0.85rem; margin-top: 4px; }
.badge { padding: 4px 10px; border-radius: 999px; font-size: 0.8rem; font-weight: 600; }
.badge.open { background: #1f3d2b; color: #7dffa6; }
.badge.lunch, .badge.pre { background: #3d3420; color: #f5d48b; }
.badge.closed { background: #2a3140; color: #9aa6b8; }
.clock { color: #d4af37; font-variant-numeric: tabular-nums; font-size: 1.15rem; }
.board-wrap { overflow-x: auto; border: 1px solid #2a3344; border-radius: 12px; }
table.board { width: 100%; border-collapse: collapse; font-size: 0.92rem; }
table.board th {
  background: #101827; color: #c9b37a; font-weight: 600; text-align: right;
  padding: 10px 12px; border-bottom: 1px solid #2a3344; white-space: nowrap;
}
table.board th:nth-child(1), table.board th:nth-child(2),
table.board td:nth-child(1), table.board td:nth-child(2) { text-align: left; }
table.board td {
  padding: 11px 12px; border-bottom: 1px solid #1c2534; color: #e8edf5;
  font-variant-numeric: tabular-nums; white-space: nowrap;
}
table.board tr:hover td { background: #182033; }
.up { color: #ef4444; }
.down { color: #22c55e; }
.flat { color: #9aa6b8; }
.note { color: #8b97a8; font-size: 0.8rem; margin-top: 10px; }
"""

STREAMLIT_CSS = f"""
<style>
.stApp {{ background: #0b1220; }}
.block-container {{ padding-top: 1.1rem; max-width: 1400px; }}
{TABLE_CSS}
</style>
"""


def fmt_px(v: float) -> str:
    return "--" if not np.isfinite(v) else f"{v:.3f}"


def fmt_yi(v: float) -> str:
    return "--" if not np.isfinite(v) else f"{v:.2f}"


def fmt_pct(v: float) -> str:
    if not np.isfinite(v):
        return "--"
    return f"{v * 100:+.2f}%"


def color_cls(v: float) -> str:
    if not np.isfinite(v) or abs(v) < 1e-12:
        return "flat"
    return "up" if v > 0 else "down"


def spark_svg(values: list[float]) -> str:
    vals = [x for x in values if np.isfinite(x)]
    if len(vals) < 2:
        return ""
    lo, hi = min(vals), max(vals)
    span = hi - lo or 1.0
    w, h = 88, 28
    pts = []
    for i, v in enumerate(vals):
        x = i / (len(vals) - 1) * (w - 2) + 1
        y = h - 2 - (v - lo) / span * (h - 4)
        pts.append(f"{x:.1f},{y:.1f}")
    color = "#ef4444" if vals[-1] >= vals[0] else "#22c55e"
    return (
        f'<svg width="{w}" height="{h}" viewBox="0 0 {w} {h}">'
        f'<polyline fill="none" stroke="{color}" stroke-width="1.4" points="{" ".join(pts)}"/>'
        f"</svg>"
    )


def render_table(df: pd.DataFrame, return_days: int, bias_days: int, targets: list[float]) -> str:
    t0, t1 = int(targets[0]), int(targets[1] if len(targets) > 1 else 15)
    headers = [
        "代码",
        "名称",
        "最新价",
        "当日涨跌幅",
        "IOPV",
        "溢价率",
        f"{return_days}日涨跌幅",
        "近N日",
        f"BIAS{bias_days}",
        f"{t0}%目标价",
        f"{t1}%目标价",
        "成交额(亿)",
    ]
    body = []
    for rec in df.to_dict("records"):
        chg = rec["当日涨跌幅"]
        prem = rec["溢价率"]
        ret = rec[f"{return_days}日涨跌幅"]
        b = rec[f"BIAS{bias_days}"]
        body.append(
            "<tr>"
            f"<td>{html.escape(str(rec['代码']))}</td>"
            f"<td>{html.escape(str(rec['名称']))}</td>"
            f"<td class='{color_cls(chg)}'>{fmt_px(rec['最新价'])}</td>"
            f"<td class='{color_cls(chg)}'>{fmt_pct(chg)}</td>"
            f"<td>{fmt_px(rec['IOPV'])}</td>"
            f"<td class='{color_cls(prem)}'>{fmt_pct(prem)}</td>"
            f"<td class='{color_cls(ret)}'>{fmt_pct(ret)}</td>"
            f"<td>{spark_svg(rec.get('近N日走势') or [])}</td>"
            f"<td class='{color_cls(b)}'>{fmt_pct(b)}</td>"
            f"<td>{fmt_px(rec[f'{t0}%目标价'])}</td>"
            f"<td>{fmt_px(rec[f'{t1}%目标价'])}</td>"
            f"<td>{fmt_yi(rec['成交额(亿)'])}</td>"
            "</tr>"
        )
    return (
        "<div class='board-wrap'><table class='board'><thead><tr>"
        + "".join(f"<th>{h}</th>" for h in headers)
        + "</tr></thead><tbody>"
        + "".join(body)
        + "</tbody></table></div>"
    )
