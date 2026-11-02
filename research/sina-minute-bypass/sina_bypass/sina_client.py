"""新浪分钟入口。

主入口：quotes.sina.cn CN_MarketDataService.getKLineData scale=1/5。
对照：money.finance.sina.com.cn CN_MarketData.getKLineData —— scale=1 常为 null。
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from typing import Any
from urllib.parse import quote

from .bars import Bar, bar_from_sina_obj
from .http import HttpError, fetch_text, parse_jsonp
from .symbols import sina_symbol, to_code

SINA_CN_KLINE = (
    "https://quotes.sina.cn/cn/api/jsonp_v2.php/"
    "{cb}/CN_MarketDataService.getKLineData"
    "?symbol={symbol}&scale={scale}&ma=no&datalen={datalen}"
)
MONEY_FINANCE_KLINE = (
    "https://money.finance.sina.com.cn/quotes_service/api/json_v2.php/"
    "CN_MarketData.getKLineData"
    "?symbol={symbol}&scale={scale}&ma=no&datalen={datalen}"
)

SINA_HEADERS = {"Referer": "https://finance.sina.com.cn/"}


@dataclass
class FetchResult:
    source: str
    code: str
    scale: int
    ok: bool
    bars: list[Bar] = field(default_factory=list)
    note: str = ""
    error: str = ""

    @property
    def last(self) -> Bar | None:
        return self.bars[-1] if self.bars else None


def _to_objs(payload: Any) -> list[dict[str, Any]]:
    if payload is None:
        return []
    if isinstance(payload, list):
        return [x for x in payload if isinstance(x, dict)]
    if isinstance(payload, dict):
        if payload.get("__ERROR") is not None:
            return []
        data = payload.get("data") or payload.get("result")
        if isinstance(data, list):
            return [x for x in data if isinstance(x, dict)]
        if isinstance(data, dict):
            inner = data.get("data")
            if isinstance(inner, list):
                return [x for x in inner if isinstance(x, dict)]
    return []


def _bars_from_payload(code: str, scale: int, payload: Any, source: str) -> list[Bar]:
    bars = [bar_from_sina_obj(code, scale, obj, source) for obj in _to_objs(payload)]
    bars.sort(key=lambda b: b.ts)
    return bars


def fetch_sina_cn(code: str, scale: int = 1, datalen: int = 240) -> FetchResult:
    symbol = sina_symbol(code)
    raw_code = to_code(code)
    cb = f"var%20_{symbol}_{scale}"
    url = SINA_CN_KLINE.format(cb=cb, symbol=symbol, scale=scale, datalen=datalen)
    try:
        text = fetch_text(url, headers=SINA_HEADERS)
        payload = parse_jsonp(text)
        bars = _bars_from_payload(raw_code, scale, payload, "sina_cn")
        if not bars:
            return FetchResult("sina_cn", raw_code, scale, False, note="empty", error="sina.cn 空表")
        return FetchResult("sina_cn", raw_code, scale, True, bars=bars, note="quotes.sina.cn getKLineData")
    except (HttpError, ValueError, TypeError) as exc:
        return FetchResult("sina_cn", raw_code, scale, False, error=str(exc))


def fetch_money_finance(code: str, scale: int = 1, datalen: int = 240) -> FetchResult:
    symbol = sina_symbol(code)
    raw_code = to_code(code)
    url = MONEY_FINANCE_KLINE.format(symbol=quote(symbol), scale=scale, datalen=datalen)
    try:
        text = fetch_text(url, headers=SINA_HEADERS)
        stripped = text.strip()
        if stripped == "" or stripped == "null":
            return FetchResult(
                "money_finance",
                raw_code,
                scale,
                False,
                note="money.finance scale=1 可能 null",
                error="null",
            )
        payload = parse_jsonp(stripped) if stripped[:1] not in "[{" else json.loads(stripped)
        bars = _bars_from_payload(raw_code, scale, payload, "money_finance")
        if not bars:
            return FetchResult("money_finance", raw_code, scale, False, note="empty", error="empty")
        return FetchResult("money_finance", raw_code, scale, True, bars=bars, note="money.finance getKLineData")
    except (HttpError, ValueError, TypeError) as exc:
        return FetchResult("money_finance", raw_code, scale, False, error=str(exc))
