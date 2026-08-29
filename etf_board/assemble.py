"""把快照 + 日线拼成看板行。"""

from __future__ import annotations

from dataclasses import asdict, dataclass, field

import numpy as np
import pandas as pd

from etf_board.indicators import bias, n_day_return, overlay_live_close, premium_rate, target_price
from etf_board.store import load_daily, load_spot


@dataclass
class BoardRow:
    code: str
    name: str
    last_price: float
    change_pct: float
    iopv: float
    premium: float
    premium_raw: float
    return_n: float
    bias_n: float
    target_10: float
    target_15: float
    amount_yi: float
    spark: list[float] = field(default_factory=list)
    source: str = "akshare"
    note: str = ""

    def as_dict(self) -> dict:
        return asdict(self)


def _num(value) -> float:
    try:
        v = float(value)
    except (TypeError, ValueError):
        return float("nan")
    return v


def _spot_lookup(spot: pd.DataFrame) -> dict[str, dict]:
    if spot is None or spot.empty:
        return {}
    work = spot.copy()
    if "code" in work.columns and "代码" not in work.columns:
        work = work.rename(
            columns={
                "code": "代码",
                "name": "名称",
                "last_price": "最新价",
                "change_pct": "涨跌幅",
                "iopv": "IOPV实时估值",
                "premium_raw": "基金折价率",
                "amount": "成交额",
                "trade_date": "数据日期",
            }
        )
    work["代码"] = work["代码"].astype(str).str.zfill(6)
    return {row["代码"]: row for row in work.to_dict("records")}


def build_board(
    conn,
    watch: list[dict],
    return_days: int = 19,
    bias_days: int = 20,
    targets: list[float] | None = None,
    adjust: str = "qfq",
    live_date: str | None = None,
    spot_df: pd.DataFrame | None = None,
) -> list[BoardRow]:
    targets = targets or [10.0, 15.0]
    t0 = targets[0] / 100.0
    t1 = (targets[1] if len(targets) > 1 else 15.0) / 100.0
    spot = spot_df if spot_df is not None else load_spot(conn, [str(x["code"]).zfill(6) for x in watch])
    lookup = _spot_lookup(spot)
    rows: list[BoardRow] = []
    for item in watch:
        code = str(item["code"]).zfill(6)
        snap = lookup.get(code, {})
        last_price = _num(snap.get("最新价"))
        iopv = _num(snap.get("IOPV实时估值"))
        hist = load_daily(conn, code, adjust=adjust, limit=120)
        closes = overlay_live_close(hist, last_price, live_date)
        spark_n = max(return_days, 19)
        spark_vals = [float(x) for x in closes.iloc[-spark_n:].tolist() if np.isfinite(x)]
        name = str(snap.get("名称") or item.get("name") or code)
        amount = _num(snap.get("成交额"))
        rows.append(
            BoardRow(
                code=code,
                name=name,
                last_price=last_price,
                change_pct=_num(snap.get("涨跌幅")) / 100.0 if np.isfinite(_num(snap.get("涨跌幅"))) else float("nan"),
                iopv=iopv,
                premium=premium_rate(last_price, iopv),
                premium_raw=_num(snap.get("基金折价率")),
                return_n=n_day_return(closes, return_days),
                bias_n=bias(closes, bias_days, last_price=last_price if np.isfinite(last_price) else None),
                target_10=target_price(closes, bias_days, t0),
                target_15=target_price(closes, bias_days, t1),
                amount_yi=amount / 1e8 if np.isfinite(amount) else float("nan"),
                spark=spark_vals,
                note="" if np.isfinite(last_price) else "无快照",
            )
        )
    return rows


def rows_to_frame(rows: list[BoardRow], return_days: int, bias_days: int, targets: list[float]) -> pd.DataFrame:
    t0 = int(targets[0]) if targets else 10
    t1 = int(targets[1]) if targets and len(targets) > 1 else 15
    records = []
    for row in rows:
        records.append(
            {
                "代码": row.code,
                "名称": row.name,
                "最新价": row.last_price,
                "当日涨跌幅": row.change_pct,
                "IOPV": row.iopv,
                "溢价率": row.premium,
                f"{return_days}日涨跌幅": row.return_n,
                f"BIAS{bias_days}": row.bias_n,
                f"{t0}%目标价": row.target_10,
                f"{t1}%目标价": row.target_15,
                "成交额(亿)": row.amount_yi,
                "近N日走势": row.spark,
                "接口折价率%": row.premium_raw,
            }
        )
    return pd.DataFrame(records)
