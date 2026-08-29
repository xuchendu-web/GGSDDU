import pandas as pd

from etf_board.akshare_src import _normalize_hist, refresh_history, sina_symbol
from etf_board.fixtures import demo_history
from etf_board.store import connect, load_daily


def test_refresh_history_uses_injected_fetcher(tmp_path):
    conn = connect(tmp_path / "t.db")

    def fake_hist(code, start, end, adjust):
        return demo_history(code, n=12)

    written = refresh_history(conn, ["518880"], adjust="qfq", sleep_s=0, hist_fn=fake_hist)
    assert written["518880"] == 12
    assert len(load_daily(conn, "518880")) == 12


def test_sina_symbol_and_normalize_hist():
    assert sina_symbol("518880") == "sh518880"
    assert sina_symbol("159915") == "sz159915"
    raw = pd.DataFrame(
        {
            "date": ["2026-08-27", "2026-08-28"],
            "open": [9.4, 9.5],
            "high": [9.5, 9.6],
            "low": [9.3, 9.4],
            "close": [9.45, 9.47],
            "volume": [1, 2],
            "amount": [3, 4],
        }
    )
    out = _normalize_hist(raw)
    assert list(out.columns[:5]) == ["日期", "开盘", "最高", "最低", "收盘"]
    assert out["收盘"].iloc[-1] == 9.47
