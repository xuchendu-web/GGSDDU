# -*- coding: utf-8 -*-
"""从全市场场内 ETF 中识别大类资产,每个调仓日在成交额达标的池内取代表。"""
from __future__ import annotations

import re

# 大类资产:多资产轮动的「资产」维度。行业主题(芯片/酒/军工等)不单独作为
# 一类,避免全市场横截面动量退化成最热门窄基主题的追涨杀跌。
# 每个调仓日仍先用「日均成交额>1000万」过滤,再在各类内选流动性最好的一只。
ASSET_PATTERNS: list[tuple[str, re.Pattern]] = [
    ("货币", re.compile(r"货币|日利|添益|日日鑫|天天金|财富宝|交易货币|增益货币")),
    ("黄金", re.compile(r"(黄金ETF|金ETF|上海金|黄金999|国际金)")),
    ("沪深300", re.compile(r"(沪深300|300ETF|300指数)")),
    ("中证500", re.compile(r"(中证500|500ETF)")),
    ("中证1000", re.compile(r"(中证1000|1000ETF)")),
    ("创业板", re.compile(r"创业板")),
    ("科创", re.compile(r"(科创50|科创板50|科创100)")),
    ("红利", re.compile(r"(红利(?!低波)|红利ETF)")),
    ("港股", re.compile(r"(恒生指数|恒生ETF|恒指|H股ETF|国企ETF|港股通50|恒生中国)")),
    ("美股", re.compile(r"(纳斯达克|纳指|标普500|标普五|道琼斯)")),
    ("日经", re.compile(r"日经")),
    ("德国", re.compile(r"(德国|DAX|欧洲)")),
    ("商品", re.compile(r"(豆粕|原油|石油|能源化工|有色)")),
]


def asset_class(name: str) -> str | None:
    n = str(name)
    # 黄金股是股票行业,不是黄金资产
    if re.search(r"黄金股", n):
        return None
    for cls, pat in ASSET_PATTERNS:
        if pat.search(n):
            return cls
    return None
