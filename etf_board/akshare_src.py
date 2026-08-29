"""AKShare 取数封装。全市场 ETF 快照一次拉齐，日线按自选增量写库。"""

from __future__ import annotations

import logging
import time
from typing import Callable

import pandas as pd

from etf_board.market import recent_calendar_start, today_yyyymmdd
from etf_board.store import last_daily_date, upsert_daily, upsert_spot

logger = logging.getLogger(__name__)

SPOT_TTL_SECONDS = 12


class AkshareError(RuntimeError):
    pass


def _import_akshare():
    try:
        import akshare as ak
    except Exception as exc:  # pragma: no cover
        raise AkshareError(f"未安装 akshare: {exc}") from exc
    return ak


def _retry(fn, times: int = 3, pause: float = 0.8):
    last = None
    for i in range(times):
        try:
            return fn()
        except Exception as exc:  # noqa: BLE001
            last = exc
            logger.warning("retry %s/%s failed: %s", i + 1, times, exc)
            if i < times - 1:
                time.sleep(pause * (i + 1))
    raise last


def fetch_etf_spot(ak_module=None) -> pd.DataFrame:
    ak = ak_module or _import_akshare()

    def _call():
        df = ak.fund_etf_spot_em()
        if df is None or df.empty:
            raise AkshareError("fund_etf_spot_em 返回空表")
        return df

    try:
        df = _retry(_call)
    except Exception as exc:
        raise AkshareError(f"fund_etf_spot_em 失败: {exc}") from exc
    if "代码" in df.columns:
        df["代码"] = df["代码"].astype(str).str.zfill(6)
    return df


def sina_symbol(code: str) -> str:
    symbol = str(code).zfill(6)
    if symbol.startswith(("5", "6", "9")):
        return "sh" + symbol
    return "sz" + symbol


def _normalize_hist(df: pd.DataFrame) -> pd.DataFrame:
    if df is None or df.empty:
        return pd.DataFrame()
    work = df.copy()
    rename = {
        "date": "日期",
        "open": "开盘",
        "high": "最高",
        "low": "最低",
        "close": "收盘",
        "volume": "成交量",
        "amount": "成交额",
    }
    work = work.rename(columns=rename)
    if "日期" not in work.columns:
        return pd.DataFrame()
    work["日期"] = pd.to_datetime(work["日期"], errors="coerce")
    work = work.dropna(subset=["日期", "收盘"]).sort_values("日期")
    work["日期"] = work["日期"].dt.strftime("%Y-%m-%d")
    return work.reset_index(drop=True)


def fetch_etf_hist(
    code: str,
    start_date: str,
    end_date: str,
    adjust: str = "qfq",
    ak_module=None,
) -> pd.DataFrame:
    ak = ak_module or _import_akshare()
    symbol = str(code).zfill(6)

    def _etf():
        df = ak.fund_etf_hist_em(
            symbol=symbol,
            period="daily",
            start_date=start_date,
            end_date=end_date,
            adjust=adjust,
        )
        if df is None or df.empty:
            raise AkshareError(f"fund_etf_hist_em {symbol} 空表")
        return _normalize_hist(df)

    def _stock():
        df = ak.stock_zh_a_hist(
            symbol=symbol,
            period="daily",
            start_date=start_date,
            end_date=end_date,
            adjust=adjust,
        )
        if df is None or df.empty:
            raise AkshareError(f"stock_zh_a_hist {symbol} 空表")
        return _normalize_hist(df)

    def _sina():
        df = ak.fund_etf_hist_sina(symbol=sina_symbol(symbol))
        if df is None or df.empty:
            raise AkshareError(f"fund_etf_hist_sina {symbol} 空表")
        work = _normalize_hist(df)
        start = pd.to_datetime(start_date).strftime("%Y-%m-%d")
        end = pd.to_datetime(end_date).strftime("%Y-%m-%d")
        return work[(work["日期"] >= start) & (work["日期"] <= end)].reset_index(drop=True)

    for name, fn in (("fund_etf_hist_em", _etf), ("stock_zh_a_hist", _stock), ("fund_etf_hist_sina", _sina)):
        try:
            return _retry(fn, times=2, pause=0.5)
        except Exception as exc:
            logger.warning("%s 失败: %s", name, exc)
    raise AkshareError(f"历史K线 {symbol} 东财/新浪均失败")


def refresh_spot(conn, ak_module=None, ttl: int = SPOT_TTL_SECONDS) -> pd.DataFrame:
    from etf_board.store import load_spot, spot_age_seconds

    age = spot_age_seconds(conn)
    if age is not None and age < ttl:
        return load_spot(conn)
    df = fetch_etf_spot(ak_module=ak_module)
    upsert_spot(conn, df)
    return df


def refresh_history(
    conn,
    codes: list[str],
    adjust: str = "qfq",
    sleep_s: float = 0.35,
    ak_module=None,
    hist_fn: Callable[..., pd.DataFrame] | None = None,
) -> dict[str, int]:
    """增量补日线。已有数据则从最后日期往前重叠 7 天再拉。"""
    written: dict[str, int] = {}
    end_date = today_yyyymmdd()
    getter = hist_fn or (lambda code, start, end, adj: fetch_etf_hist(code, start, end, adj, ak_module=ak_module))
    for i, code in enumerate(codes):
        last = last_daily_date(conn, code, adjust)
        if last:
            start = pd.Timestamp(last) - pd.Timedelta(days=7)
            start_date = start.strftime("%Y%m%d")
        else:
            start_date = recent_calendar_start(140)
        hist = getter(code, start_date, end_date, adjust)
        written[code] = upsert_daily(conn, code, hist, adjust=adjust)
        if i < len(codes) - 1 and sleep_s > 0:
            time.sleep(sleep_s)
    return written
