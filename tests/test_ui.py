import pandas as pd

from etf_board.ui import render_table


def test_render_table_uses_ashare_colors_and_headers():
    df = pd.DataFrame(
        [
            {
                "代码": "518880",
                "名称": "黄金ETF",
                "最新价": 9.475,
                "当日涨跌幅": 0.0031,
                "IOPV": 9.4696,
                "溢价率": 0.00057,
                "19日涨跌幅": 0.1257,
                "BIAS20": 0.0439,
                "10%目标价": 9.984,
                "15%目标价": 10.438,
                "成交额(亿)": 44.63,
                "近N日走势": [9.1, 9.2, 9.4],
            }
        ]
    )
    html = render_table(df, 19, 20, [10, 15])
    assert "19日涨跌幅" in html
    assert "BIAS20" in html
    assert "518880" in html
    assert "class='up'" in html
    assert "+12.57%" in html
    assert "+0.31%" in html
