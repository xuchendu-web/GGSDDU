"""统一分钟 K 线行。"""

from __future__ import annotations

from dataclasses import asdict, dataclass
from datetime import datetime
from typing import Any


def parse_ts(raw: Any) -> datetime:
    text = str(raw).strip()
    if not text:
        raise ValueError("empty timestamp")
    compact = (
        text.replace("/", "")
        .replace("-", "")
        .replace(":", "")
        .replace("T", "")
        .replace(" ", "")
    )
    if len(compact) >= 12 and compact[:12].isdigit():
        return datetime.strptime(compact[:12], "%Y%m%d%H%M")
    for fmt in (
        "%Y-%m-%d %H:%M:%S",
        "%Y-%m-%d %H:%M",
        "%Y/%m/%d %H:%M:%S",
        "%Y/%m/%d %H:%M",
    ):
        try:
            return datetime.strptime(text[:19], fmt)
        except ValueError:
            continue
    raise ValueError(f"无法解析时间: {raw!r}")


def _f(raw: Any) -> float | None:
    if raw is None or raw == "":
        return None
    try:
        return float(raw)
    except (TypeError, ValueError):
        return None


@dataclass(frozen=True)
class Bar:
    code: str
    scale: int
    ts: datetime
    open: float | None
    high: float | None
    low: float | None
    close: float | None
    volume: float | None
    amount: float | None
    source: str

    @property
    def ts_key(self) -> str:
        return self.ts.strftime("%Y-%m-%d %H:%M")

    @property
    def trade_date(self) -> str:
        return self.ts.strftime("%Y-%m-%d")

    def ohlc_ok(self) -> bool:
        if self.close is None or self.close <= 0:
            return False
        nums = [v for v in (self.open, self.high, self.low, self.close) if v is not None]
        if self.high is not None and self.low is not None and self.high < self.low:
            return False
        if self.high is not None and max(nums) - self.high > 1e-9:
            return False
        if self.low is not None and self.low - min(nums) > 1e-9:
            return False
        return True

    def as_row(self) -> dict[str, Any]:
        row = asdict(self)
        row["ts"] = self.ts_key
        row["trade_date"] = self.trade_date
        return row


def bar_from_sina_obj(code: str, scale: int, obj: dict[str, Any], source: str) -> Bar:
    return Bar(
        code=code,
        scale=scale,
        ts=parse_ts(obj.get("day") or obj.get("time") or obj.get("date")),
        open=_f(obj.get("open")),
        high=_f(obj.get("high")),
        low=_f(obj.get("low")),
        close=_f(obj.get("close")),
        volume=_f(obj.get("volume") or obj.get("vol")),
        amount=_f(obj.get("amount")),
        source=source,
    )


def bars_from_akshare_rows(code: str, scale: int, rows: list[dict[str, Any]], source: str = "akshare") -> list[Bar]:
    out: list[Bar] = []
    for obj in rows:
        key = obj.get("day") or obj.get("时间") or obj.get("datetime")
        if key is None:
            continue
        mapped = {
            "day": key,
            "open": obj.get("open", obj.get("开盘")),
            "high": obj.get("high", obj.get("最高")),
            "low": obj.get("low", obj.get("最低")),
            "close": obj.get("close", obj.get("收盘")),
            "volume": obj.get("volume", obj.get("成交量")),
            "amount": obj.get("amount", obj.get("成交额")),
        }
        out.append(bar_from_sina_obj(code, scale, mapped, source))
    return out
