"""AKShare stock_zh_a_minute 旁路。

审阅口径：这是实盘实时旁路，不是回测权威。
禁止走 fund_etf_hist_min_em / stock_zh_a_hist_min_em 等东财 *_em 主力。
未安装 akshare 时走与文档相同的 sina.cn getKLineData，标记为 akshare_compat。
"""

from __future__ import annotations

from dataclasses import replace

from .bars import bars_from_akshare_rows
from .sina_client import FetchResult, fetch_sina_cn
from .symbols import sina_symbol, to_code


def fetch_akshare_minute(code: str, scale: int = 1, adjust: str = "") -> FetchResult:
    raw_code = to_code(code)
    symbol = sina_symbol(code)
    try:
        import akshare as ak  # type: ignore
    except Exception:
        compat = fetch_sina_cn(raw_code, scale=scale)
        return FetchResult(
            source="akshare_compat",
            code=raw_code,
            scale=scale,
            ok=compat.ok,
            bars=[replace(b, source="akshare_compat") for b in compat.bars],
            note="akshare 未安装，回退 sina.cn getKLineData（与 stock_zh_a_minute 同源）",
            error=compat.error,
        )
    try:
        df = ak.stock_zh_a_minute(symbol=symbol, period=str(scale), adjust=adjust)
        if df is None or getattr(df, "empty", True):
            return FetchResult(
                "akshare",
                raw_code,
                scale,
                False,
                note="stock_zh_a_minute 空表（1m 若走 money.finance 可能 null）",
                error="empty",
            )
        rows = df.to_dict(orient="records")
        bars = bars_from_akshare_rows(raw_code, scale, rows, source="akshare")
        bars.sort(key=lambda b: b.ts)
        if not bars:
            return FetchResult("akshare", raw_code, scale, False, error="parse_empty")
        return FetchResult("akshare", raw_code, scale, True, bars=bars, note="ak.stock_zh_a_minute")
    except Exception as exc:  # noqa: BLE001
        return FetchResult("akshare", raw_code, scale, False, error=str(exc))
