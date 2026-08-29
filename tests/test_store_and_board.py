import pandas as pd

from etf_board.assemble import build_board, rows_to_frame
from etf_board.fixtures import demo_history, demo_spot, seed_demo
from etf_board.indicators import n_day_return, overlay_live_close, premium_rate
from etf_board.market import market_status
from etf_board.store import connect, last_daily_date, load_daily, upsert_daily, upsert_spot


def test_sqlite_roundtrip(tmp_path):
    conn = connect(tmp_path / "t.db")
    hist = demo_history("518880", n=25)
    assert upsert_daily(conn, "518880", hist) == 25
    loaded = load_daily(conn, "518880")
    assert len(loaded) == 25
    assert last_daily_date(conn, "518880") == hist["日期"].iloc[-1]
    n = upsert_spot(conn, demo_spot())
    assert n == 3


def test_build_board_matches_indicator_math(tmp_path):
    conn = connect(tmp_path / "t.db")
    seed_demo(conn)
    watch = [{"code": "518880", "name": "黄金ETF"}]
    rows = build_board(conn, watch, return_days=19, bias_days=20, live_date=None)
    assert len(rows) == 1
    row = rows[0]
    hist = load_daily(conn, "518880")
    closes = overlay_live_close(hist, row.last_price, None)
    assert abs(row.return_n - n_day_return(closes, 19)) < 1e-12
    assert abs(row.premium - premium_rate(9.530, 9.540)) < 1e-12
    frame = rows_to_frame(rows, 19, 20, [10, 15])
    assert "19日涨跌幅" in frame.columns
    assert "BIAS20" in frame.columns
    assert "10%目标价" in frame.columns


def test_market_status_weekend_closed():
    ts = pd.Timestamp("2026-08-29 10:00:00", tz="Asia/Shanghai").to_pydatetime()
    # 2026-08-29 is Saturday
    status = market_status(ts)
    assert status["state"] == "closed"
    assert status["should_autorefresh"] is False


def test_market_status_open_weekday():
    ts = pd.Timestamp("2026-08-28 10:00:00", tz="Asia/Shanghai").to_pydatetime()
    status = market_status(ts)
    assert status["state"] == "open"
    assert status["should_autorefresh"] is True
