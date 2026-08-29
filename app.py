"""ETF 个性化行情看板（Streamlit）。

对齐《用 AI 手搓一个 ETF 个性化行情看板，比 Wind 都好用》：
自定义 N 日涨跌、实时 IOPV 溢价、BIAS、目标价；AKShare 取数，SQLite 落库。
"""

from __future__ import annotations

import html
from datetime import timedelta

import numpy as np
import pandas as pd
import streamlit as st

from etf_board.akshare_src import AkshareError, refresh_history, refresh_spot
from etf_board.assemble import build_board, rows_to_frame
from etf_board.fixtures import seed_demo
from etf_board.market import market_status, today_iso
from etf_board.store import connect, load_watchlist, save_watchlist

st.set_page_config(page_title="ETF 个性化行情看板", page_icon="▣", layout="wide")

CSS = """
<style>
.stApp { background: #0b1220; }
.block-container { padding-top: 1.1rem; max-width: 1400px; }
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
</style>
"""


def _fmt_px(v: float) -> str:
    return "--" if not np.isfinite(v) else f"{v:.3f}"


def _fmt_yi(v: float) -> str:
    return "--" if not np.isfinite(v) else f"{v:.2f}"


def _fmt_pct(v: float) -> str:
    if not np.isfinite(v):
        return "--"
    return f"{v * 100:+.2f}%"


def _cls(v: float) -> str:
    if not np.isfinite(v) or abs(v) < 1e-12:
        return "flat"
    return "up" if v > 0 else "down"


def _spark_svg(values: list[float]) -> str:
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
            f"<td class='{_cls(chg)}'>{_fmt_px(rec['最新价'])}</td>"
            f"<td class='{_cls(chg)}'>{_fmt_pct(chg)}</td>"
            f"<td>{_fmt_px(rec['IOPV'])}</td>"
            f"<td class='{_cls(prem)}'>{_fmt_pct(prem)}</td>"
            f"<td class='{_cls(ret)}'>{_fmt_pct(ret)}</td>"
            f"<td>{_spark_svg(rec.get('近N日走势') or [])}</td>"
            f"<td class='{_cls(b)}'>{_fmt_pct(b)}</td>"
            f"<td>{_fmt_px(rec[f'{t0}%目标价'])}</td>"
            f"<td>{_fmt_px(rec[f'{t1}%目标价'])}</td>"
            f"<td>{_fmt_yi(rec['成交额(亿)'])}</td>"
            "</tr>"
        )
    return (
        "<div class='board-wrap'><table class='board'><thead><tr>"
        + "".join(f"<th>{h}</th>" for h in headers)
        + "</tr></thead><tbody>"
        + "".join(body)
        + "</tbody></table></div>"
    )


@st.cache_resource
def db_conn():
    return connect()


def ensure_data(conn, codes: list[str], adjust: str, force_hist: bool = False, use_live: bool = True) -> str:
    mode = "akshare"
    if use_live:
        try:
            refresh_spot(conn)
        except Exception as exc:
            st.session_state["live_error"] = str(exc)
            use_live = False
            mode = "demo"
        else:
            st.session_state.pop("live_error", None)
    else:
        mode = "demo"

    need_hist = force_hist
    if not need_hist:
        from etf_board.store import last_daily_date

        need_hist = any(last_daily_date(conn, c, adjust) is None for c in codes)

    if need_hist:
        if use_live:
            try:
                refresh_history(conn, codes, adjust=adjust)
            except Exception as exc:
                st.session_state["hist_error"] = str(exc)
                seed_demo(conn, codes)
                mode = "demo"
            else:
                st.session_state.pop("hist_error", None)
        else:
            seed_demo(conn, codes)
    return mode


def main() -> None:
    st.markdown(CSS, unsafe_allow_html=True)
    cfg = load_watchlist()
    conn = db_conn()

    with st.sidebar:
        st.markdown("**自选与口径**")
        names = [f"{x['code']} {x.get('name','')}" for x in cfg["etfs"]]
        st.caption("默认三只对齐原文演示：黄金 / 纳指 / 沪深300。")
        add_code = st.text_input("添加 ETF 代码", placeholder="例如 159915")
        add_name = st.text_input("备注名称", placeholder="可选")
        if st.button("加入自选") and add_code.strip():
            code = add_code.strip().zfill(6)
            if all(x["code"] != code for x in cfg["etfs"]):
                cfg["etfs"].append({"code": code, "name": add_name.strip() or code})
                save_watchlist(cfg)
                st.rerun()
        drop = st.multiselect("移除自选", names)
        if st.button("确认移除") and drop:
            drop_codes = {x.split()[0] for x in drop}
            cfg["etfs"] = [x for x in cfg["etfs"] if x["code"] not in drop_codes]
            save_watchlist(cfg)
            st.rerun()

        return_days = st.number_input("N 日涨跌幅（含当日）", min_value=2, max_value=60, value=int(cfg.get("return_days", 19)))
        bias_days = st.number_input("BIAS 窗口", min_value=5, max_value=60, value=int(cfg.get("bias_days", 20)))
        t0 = st.number_input("目标 BIAS 1 (%)", min_value=1.0, max_value=40.0, value=float(cfg.get("target_bias_pct", [10, 15])[0]))
        t1 = st.number_input("目标 BIAS 2 (%)", min_value=1.0, max_value=40.0, value=float(cfg.get("target_bias_pct", [10, 15])[1]))
        adjust = st.selectbox("复权", options=["qfq", "hfq", ""], format_func=lambda x: {"qfq": "前复权", "hfq": "后复权", "": "不复权"}[x], index=0)
        refresh_s = st.slider("刷新间隔（秒）", 5, 60, int(cfg.get("refresh_seconds", 15)))
        use_live = st.toggle("走 AKShare 实盘接口", value=True)
        if st.button("重拉历史 K 线"):
            st.session_state["force_hist"] = True
        if st.button("保存口径"):
            cfg.update(
                {
                    "return_days": int(return_days),
                    "bias_days": int(bias_days),
                    "target_bias_pct": [float(t0), float(t1)],
                    "adjust": adjust,
                    "refresh_seconds": int(refresh_s),
                }
            )
            save_watchlist(cfg)
            st.success("已写入 watchlist.json")

        with st.expander("口径（务必核对）"):
            st.markdown(
                f"""
- **{return_days}日涨跌幅（含当日）** = 最新价 / REF(收盘, {return_days}) − 1，至少 {return_days + 1} 根 K 线。
- **BIAS{bias_days}** = 最新价 / MA{bias_days} − 1，MA 含当日复权收盘。
- **目标价** = MA{bias_days} × (1 + 阈值)，方便提前挂单。
- **溢价率** = (最新价 − IOPV) / IOPV。接口「基金折价率」另列核对，不直接当溢价。
- 数据：`fund_etf_spot_em` + `fund_etf_hist_em` → 本地 `data/etf_board.db`。
                """
            )

    status = market_status()
    codes = [x["code"] for x in cfg["etfs"]]
    force_hist = bool(st.session_state.pop("force_hist", False))
    mode = ensure_data(conn, codes, adjust=adjust, force_hist=force_hist, use_live=use_live)

    interval = refresh_s if (use_live and status["should_autorefresh"]) else None

    @st.fragment(run_every=timedelta(seconds=interval) if interval else None)
    def board_fragment():
        live_status = market_status()
        if use_live and live_status["should_autorefresh"]:
            try:
                refresh_spot(conn)
            except AkshareError as exc:
                st.session_state["live_error"] = str(exc)
            except Exception as exc:
                st.session_state["live_error"] = str(exc)

        rows = build_board(
            conn,
            cfg["etfs"],
            return_days=int(return_days),
            bias_days=int(bias_days),
            targets=[float(t0), float(t1)],
            adjust=adjust,
            live_date=today_iso(),
        )
        frame = rows_to_frame(rows, int(return_days), int(bias_days), [float(t0), float(t1)])

        badge = f"<span class='badge {live_status['state']}'>{live_status['label']}</span>"
        src = "AKShare 东财" if mode == "akshare" and use_live else "离线演示"
        st.markdown(
            f"""
            <div class="hero">
              <div>
                <h1>ETF 个性化行情看板</h1>
                <div class="sub">比 Wind 更自由的 N 日 / BIAS / IOPV 溢价 · 数据源 {src} · SQLite 落库</div>
              </div>
              <div style="text-align:right">
                {badge}
                <div class="clock">{live_status['clock']}</div>
              </div>
            </div>
            """,
            unsafe_allow_html=True,
        )
        if st.session_state.get("live_error"):
            st.warning(f"实时接口失败，已用本地/演示数据。{st.session_state['live_error']}")
        if st.session_state.get("hist_error"):
            st.info(f"历史 K 线拉取部分失败。{st.session_state['hist_error']}")

        c1, c2, c3 = st.columns([1, 1, 2])
        with c1:
            st.button("立即刷新", use_container_width=True)
        with c2:
            st.caption(f"{'自动刷新 ' + str(refresh_s) + 's' if interval else '已按交易时段暂停自动刷新'}")
        st.markdown(render_table(frame, int(return_days), int(bias_days), [float(t0), float(t1)]), unsafe_allow_html=True)
        st.markdown(
            "<div class='note'>IOPV 来自东财 `IOPV实时估值`；溢价率本地用 (市价−IOPV)/IOPV 重算。"
            "接口空值显示 --。投资判断自负，上线前请用行情软件逐项勾稽。</div>",
            unsafe_allow_html=True,
        )
        with st.expander("接口折价率核对"):
            check = frame[["代码", "名称", "IOPV", "溢价率", "接口折价率%"]].copy()
            check["溢价率%"] = (check["溢价率"] * 100).round(2)
            st.dataframe(check.drop(columns=["溢价率"]), use_container_width=True, hide_index=True)

    board_fragment()


if __name__ == "__main__":
    main()
