"""ETF 个性化行情看板（Streamlit）。

对齐《用 AI 手搓一个 ETF 个性化行情看板，比 Wind 都好用》：
自定义 N 日涨跌、实时 IOPV 溢价、BIAS、目标价；AKShare 取数，SQLite 落库。
"""

from __future__ import annotations

from datetime import timedelta

import streamlit as st

from etf_board.akshare_src import AkshareError, refresh_history, refresh_spot
from etf_board.assemble import build_board, rows_to_frame
from etf_board.fixtures import seed_demo
from etf_board.market import market_status, today_iso
from etf_board.store import connect, last_daily_date, load_watchlist, save_watchlist
from etf_board.ui import STREAMLIT_CSS, render_table

st.set_page_config(page_title="ETF 个性化行情看板", page_icon="▣", layout="wide")


@st.cache_resource
def db_conn():
    return connect()


def ensure_data(conn, codes: list[str], adjust: str, force_hist: bool = False, use_live: bool = True) -> str:
    mode = "akshare"
    if use_live:
        try:
            refresh_spot(conn)
        except Exception as exc:  # noqa: BLE001
            st.session_state["live_error"] = str(exc)
            use_live = False
            mode = "demo"
        else:
            st.session_state.pop("live_error", None)
    else:
        mode = "demo"

    need_hist = force_hist or any(last_daily_date(conn, c, adjust) is None for c in codes)
    if need_hist:
        if use_live:
            try:
                refresh_history(conn, codes, adjust=adjust)
            except Exception as exc:  # noqa: BLE001
                st.session_state["hist_error"] = str(exc)
                seed_demo(conn, codes)
                mode = "demo"
            else:
                st.session_state.pop("hist_error", None)
        else:
            seed_demo(conn, codes)
    return mode


def main() -> None:
    st.markdown(STREAMLIT_CSS, unsafe_allow_html=True)
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
- 数据：`fund_etf_spot_em` + 日线（东财失败回退新浪）→ 本地 `data/etf_board.db`。
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
            except (AkshareError, Exception) as exc:  # noqa: BLE001
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

        c1, c2, _c3 = st.columns([1, 1, 2])
        with c1:
            st.button("立即刷新", width="stretch")
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
            st.dataframe(check.drop(columns=["溢价率"]), width="stretch", hide_index=True)

    board_fragment()


if __name__ == "__main__":
    main()
