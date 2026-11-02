"""腾讯分钟互校。与新浪旁路对称，只作对照，不写 LIVE。

入口：ifzq.gtimg.cn appstock/app/kline/mkline param=sh510300,m1,,N
行格式：[YYYYMMDDHHmm, open, close, high, low, volume, ...]
成交量单位与新浪不同（常见为手），互校只比收盘价。
"""

from __future__ import annotations

import json

from .bars import Bar, parse_ts
from .http import HttpError, fetch_text
from .sina_client import FetchResult
from .symbols import tencent_symbol, to_code

MKLINE = "https://ifzq.gtimg.cn/appstock/app/kline/mkline?param={symbol},m{scale},,{datalen}"
TENCENT_HEADERS = {"Referer": "https://gu.qq.com/"}


def _f(raw) -> float | None:
    try:
        return float(raw)
    except (TypeError, ValueError):
        return None


def parse_mkline_payload(code: str, scale: int, payload: dict) -> list[Bar]:
    symbol = tencent_symbol(code)
    block = (payload.get("data") or {}).get(symbol) or {}
    rows = block.get(f"m{scale}") or []
    bars: list[Bar] = []
    for row in rows:
        if not isinstance(row, (list, tuple)) or len(row) < 6:
            continue
        bars.append(
            Bar(
                code=to_code(code),
                scale=scale,
                ts=parse_ts(row[0]),
                open=_f(row[1]),
                close=_f(row[2]),
                high=_f(row[3]),
                low=_f(row[4]),
                volume=_f(row[5]),
                amount=None,
                source="tencent",
            )
        )
    bars.sort(key=lambda b: b.ts)
    return bars


def fetch_tencent_mkline(code: str, scale: int = 1, datalen: int = 240) -> FetchResult:
    symbol = tencent_symbol(code)
    raw_code = to_code(code)
    url = MKLINE.format(symbol=symbol, scale=scale, datalen=datalen)
    try:
        text = fetch_text(url, headers=TENCENT_HEADERS)
        payload = json.loads(text)
        if payload.get("code") not in (0, "0", None):
            return FetchResult(
                "tencent",
                raw_code,
                scale,
                False,
                error=str(payload.get("msg") or payload.get("code")),
            )
        bars = parse_mkline_payload(raw_code, scale, payload)
        if not bars:
            return FetchResult("tencent", raw_code, scale, False, error="empty", note="mkline 空表")
        return FetchResult("tencent", raw_code, scale, True, bars=bars, note="ifzq mkline")
    except (HttpError, ValueError, TypeError, KeyError) as exc:
        return FetchResult("tencent", raw_code, scale, False, error=str(exc))


def load_tencent_csv(path: str, scale: int | None = None) -> dict[str, list[Bar]]:
    """读取腾讯旁路脚本吐出的 CSV（与本工具列同构）。"""
    import csv
    from pathlib import Path

    grouped: dict[str, list[Bar]] = {}
    with Path(path).open(encoding="utf-8") as fh:
        reader = csv.DictReader(fh)
        for row in reader:
            row_scale = int(row.get("scale") or 0)
            if scale is not None and row_scale != scale:
                continue
            code = to_code(row["code"])
            bar = Bar(
                code=code,
                scale=row_scale,
                ts=parse_ts(row["ts"]),
                open=_f(row.get("open")),
                high=_f(row.get("high")),
                low=_f(row.get("low")),
                close=_f(row.get("close")),
                volume=_f(row.get("volume")),
                amount=_f(row.get("amount")),
                source=row.get("source") or "tencent",
            )
            grouped.setdefault(code, []).append(bar)
    for code, bars in grouped.items():
        bars.sort(key=lambda b: b.ts)
    return grouped
