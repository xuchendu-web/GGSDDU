"""沪深 ETF 代码与新浪/腾讯前缀互转。北交所不进本样本。"""

from __future__ import annotations


def to_code(raw: str) -> str:
    text = str(raw).strip().lower()
    if text.startswith(("sh", "sz", "bj")):
        text = text[2:]
    digits = "".join(ch for ch in text if ch.isdigit())
    if len(digits) < 6:
        raise ValueError(f"无法解析代码: {raw!r}")
    return digits[-6:].zfill(6)


def market_prefix(code: str) -> str:
    symbol = to_code(code)
    if symbol.startswith(("5", "6", "9")):
        return "sh"
    if symbol.startswith(("4", "8")):
        return "bj"
    return "sz"


def sina_symbol(code: str) -> str:
    return market_prefix(code) + to_code(code)


def tencent_symbol(code: str) -> str:
    return sina_symbol(code)
