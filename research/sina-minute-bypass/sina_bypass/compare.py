"""新浪 vs 腾讯互校。收盘价相对偏差 >0.3% 标黄。"""

from __future__ import annotations

from dataclasses import dataclass, field

from .bars import Bar
from .sina_client import FetchResult

YELLOW_PCT = 0.003
RED_STALE_MINUTES = 3
CSV_COLUMNS = [
    "code",
    "name",
    "scale",
    "ts",
    "trade_date",
    "open",
    "high",
    "low",
    "close",
    "volume",
    "amount",
    "source",
]


@dataclass
class CompareResult:
    code: str
    name: str
    scale: int
    flag: str
    reasons: list[str] = field(default_factory=list)
    last_ts: str | None = None
    sina_close: float | None = None
    tencent_close: float | None = None
    last_abs_pct: float | None = None
    max_abs_pct: float | None = None
    overlap: int = 0
    sina_n: int = 0
    tencent_n: int = 0
    sina_ok: bool = False
    tencent_ok: bool = False
    sina_source: str = "sina_cn"
    tencent_source: str = "tencent"

    def as_row(self) -> dict:
        return {
            "code": self.code,
            "name": self.name,
            "scale": self.scale,
            "flag": self.flag,
            "reasons": ";".join(self.reasons),
            "last_ts": self.last_ts or "",
            "sina_close": self.sina_close,
            "tencent_close": self.tencent_close,
            "last_abs_pct": self.last_abs_pct,
            "max_abs_pct": self.max_abs_pct,
            "overlap": self.overlap,
            "sina_n": self.sina_n,
            "tencent_n": self.tencent_n,
        }


def _pct(a: float | None, b: float | None) -> float | None:
    if a is None or b is None:
        return None
    if b == 0:
        return None
    return abs(a - b) / abs(b)


def _quality_bad(bars: list[Bar]) -> bool:
    return any(not b.ohlc_ok() for b in bars[-20:]) if bars else False


def compare_symbol(
    sina: FetchResult,
    tencent: FetchResult,
    *,
    name: str = "",
    session: str = "open",
    yellow_pct: float = YELLOW_PCT,
) -> CompareResult:
    out = CompareResult(
        code=sina.code or tencent.code,
        name=name,
        scale=sina.scale or tencent.scale,
        flag="GREEN",
        sina_ok=sina.ok,
        tencent_ok=tencent.ok,
        sina_n=len(sina.bars),
        tencent_n=len(tencent.bars),
        sina_source=sina.source,
        tencent_source=tencent.source,
    )
    if not sina.ok or not sina.bars:
        out.flag = "RED"
        out.reasons.append(f"sina_fail:{sina.error or sina.note or 'empty'}")
    if not tencent.ok or not tencent.bars:
        if session in {"inferred_closed", "closed_prior", "closed_non_trading", "no_data"}:
            if out.flag != "RED":
                out.flag = "YELLOW"
            out.reasons.append(f"tencent_missing_closed:{tencent.error or 'empty'}")
        else:
            out.flag = "RED"
            out.reasons.append(f"tencent_fail:{tencent.error or tencent.note or 'empty'}")
    if _quality_bad(sina.bars):
        out.flag = "RED"
        out.reasons.append("sina_ohlc_invalid")
    if _quality_bad(tencent.bars):
        out.flag = "RED"
        out.reasons.append("tencent_ohlc_invalid")

    sina_map = {b.ts_key: b for b in sina.bars if b.close is not None}
    tec_map = {b.ts_key: b for b in tencent.bars if b.close is not None}
    keys = sorted(set(sina_map) & set(tec_map))
    out.overlap = len(keys)
    diffs: list[float] = []
    for key in keys:
        pct = _pct(sina_map[key].close, tec_map[key].close)
        if pct is not None:
            diffs.append(pct)
    if diffs:
        out.max_abs_pct = max(diffs)

    last_key = None
    if keys:
        last_key = keys[-1]
    elif sina.bars:
        last_key = sina.bars[-1].ts_key
    out.last_ts = last_key
    if last_key and last_key in sina_map:
        out.sina_close = sina_map[last_key].close
    if last_key and last_key in tec_map:
        out.tencent_close = tec_map[last_key].close
    out.last_abs_pct = _pct(out.sina_close, out.tencent_close)

    if out.flag != "RED" and out.overlap == 0 and sina.ok and tencent.ok:
        out.flag = "RED"
        out.reasons.append("no_overlap")

    yellow_hit = any(
        v is not None and v > yellow_pct for v in (out.last_abs_pct, out.max_abs_pct)
    )
    if yellow_hit and out.flag != "RED":
        out.flag = "YELLOW"
        out.reasons.append(f"abs_pct>{yellow_pct:.1%}")

    if session == "open" and sina.ok and tencent.ok and sina.bars and tencent.bars:
        delta = abs((sina.bars[-1].ts - tencent.bars[-1].ts).total_seconds()) / 60.0
        if delta > RED_STALE_MINUTES:
            out.flag = "RED"
            out.reasons.append(f"stale_last_ts:{delta:.1f}min")

    if out.flag == "GREEN" and not out.reasons:
        out.reasons.append("aligned")
    return out
