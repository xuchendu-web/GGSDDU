#!/usr/bin/env python3
"""Al Brooks weekly scan → data/scan.json + index.html + README.md."""

from __future__ import annotations

import csv
import json
import math
import ssl
import time
import urllib.error
import urllib.request
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
UNIVERSE = Path(__file__).resolve().parent / "universe.csv"
RAW_DIR = ROOT / "data" / "raw"
SCAN_JSON = ROOT / "data" / "scan.json"
INDEX_HTML = ROOT / "index.html"
README = ROOT / "README.md"

ASOF = date(2026, 10, 9)
ASOF_S = ASOF.isoformat()
END_S = "2026-10-09"
START_S = "2024-01-01"
UA = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
    )
}
CTX = ssl.create_default_context()
WORKERS = 8
RETRIES = 2

MANAGERS = (
    "华泰柏瑞", "易方达", "华夏", "国泰", "嘉实", "南方", "华安", "华宝",
    "国联安", "银华", "富国", "汇添富", "永赢", "鹏华", "广发", "万家",
    "博时", "招商", "天弘", "华富", "平安", "工银", "东财", "申万菱信",
    "西部利得", "弘毅远方", "融通", "鹏扬", "建信", "交银", "大成",
    "方正富邦", "鑫元", "汇安", "浦银", "国投瑞银", "泰康", "景顺长城",
    "景顺", "摩根", "中银", "中金", "南华", "前海开源", "国寿安保",
    "国寿", "浙商", "中加", "兴全", "中航", "诺安", "圆信永丰",
)


# ---------------------------------------------------------------------------
# HTTP
# ---------------------------------------------------------------------------

def http_get(url: str, timeout: int = 20) -> bytes:
    req = urllib.request.Request(url, headers=UA)
    with urllib.request.urlopen(req, timeout=timeout, context=CTX) as resp:
        return resp.read()


def http_get_retry(url: str, tries: int = RETRIES + 1) -> bytes:
    last: Exception | None = None
    for i in range(tries):
        try:
            return http_get(url)
        except urllib.error.HTTPError as e:
            last = e
            if e.code == 429:
                time.sleep(3 + i * 2)
                continue
            if i < tries - 1:
                time.sleep(0.6 + i)
                continue
            raise
        except Exception as e:
            last = e
            if i < tries - 1:
                time.sleep(0.6 + i)
    raise last or RuntimeError(url)


def market(code: str) -> str:
    return "sh" if code[0] in "56" else "sz"


# ---------------------------------------------------------------------------
# Universe metadata
# ---------------------------------------------------------------------------

def load_universe() -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    with UNIVERSE.open(encoding="utf-8") as f:
        for r in csv.DictReader(f):
            aum = r.get("aum") or ""
            rows.append(
                {
                    "code": r["code"].strip(),
                    "name": (r.get("name") or "").strip(),
                    "index": (r.get("index") or "").strip(),
                    "family": (r.get("family") or "").strip(),
                    "l0": (r.get("l0") or "").strip(),
                    "aum": float(aum) if aum else None,
                }
            )
    if len(rows) != 436:
        raise SystemExit(f"universe must be 436 rows, got {len(rows)}")
    return rows


def classify_l0_family(name: str, code: str) -> tuple[str, str, str]:
    """Return (index_guess, family, l0) from a Tencent short name. Not invented tickers."""
    n = name or ""
    theme = n
    for m in MANAGERS:
        theme = theme.replace(m, "")
    theme = theme.replace("ETF", "").replace("(QDII)", "").replace("QDII", "").strip()
    if not theme:
        theme = n.replace("ETF", "").strip() or code

    # l0 — keyword first, then a few code-specific listings
    if any(k in n for k in ("豆粕", "能源化工", "大宗商品")) or code in {
        "518880", "518600", "159980", "159985", "159981", "510170",
    }:
        if "黄金股" in n or "黄金产业" in n or "黄金股票" in n:
            l0 = "中国权益"
        elif "金ETF" in n or n.startswith("黄金ETF") or "黄金ETF" in n or code in {
            "518880", "518600",
        }:
            l0 = "商品"
        elif code in {"159980", "159985", "159981", "510170"} or any(
            k in n for k in ("豆粕", "能源化工", "大宗商品")
        ):
            l0 = "商品"
        else:
            l0 = "中国权益"
    elif any(
        k in n
        for k in (
            "恒生", "港股", "恒指", "中概", "香港", "港股通",
        )
    ):
        l0 = "港股"
    elif any(
        k in n
        for k in (
            "纳指", "标普500", "道琼斯", "日经", "东证", "德国", "法国",
            "沙特", "巴西", "东南亚", "亚太", "美国50", "新兴亚洲",
            "标普消费", "纳指科技", "纳指生物", "标普油气", "标普生物",
        )
    ) or code == "513360":
        l0 = "海外"
    else:
        l0 = "中国权益"

    def fam(*pairs: tuple[str, str], default: str) -> str:
        for kw, lab in pairs:
            if kw in n or kw in theme:
                return lab
        return default

    if l0 == "商品":
        family = fam(
            ("黄金", "商品·贵金属"),
            ("金ETF", "商品·贵金属"),
            ("豆粕", "商品·农产品"),
            ("能源化工", "商品·能源"),
            ("有色", "商品·有色"),
            ("大宗", "商品·综合"),
            default="商品·其他",
        )
    elif l0 == "港股":
        family = fam(
            ("红利", "港股·红利"),
            ("创新药", "港股·医药"),
            ("医药", "港股·医药"),
            ("医疗", "港股·医药"),
            ("科技", "港股·科技"),
            ("互联网", "港股·科技"),
            ("中概", "港股·中概"),
            ("证券", "港股·金融"),
            ("金融", "港股·金融"),
            ("非银", "港股·金融"),
            ("消费", "港股·消费"),
            ("汽车", "港股·周期"),
            ("恒生", "港股·恒生"),
            ("国企", "港股·恒生"),
            default="港股·其他",
        )
    elif l0 == "海外":
        family = fam(
            ("纳指", "海外·美股"),
            ("标普", "海外·美股"),
            ("道琼斯", "海外·美股"),
            ("美国", "海外·美股"),
            ("日经", "海外·亚太"),
            ("东证", "海外·亚太"),
            ("东南亚", "海外·亚太"),
            ("亚太", "海外·亚太"),
            ("沙特", "海外·新兴"),
            ("巴西", "海外·新兴"),
            ("新兴", "海外·新兴"),
            ("德国", "海外·欧洲"),
            ("法国", "海外·欧洲"),
            ("教育", "海外·主题"),
            default="海外·其他",
        )
    else:
        family = fam(
            ("芯片", "行业·半导体族"),
            ("半导体", "行业·半导体族"),
            ("集成电路", "行业·半导体族"),
            ("人工智能", "行业·人工智能"),
            ("科创AI", "行业·人工智能"),
            ("机器人", "行业·机器人"),
            ("创新药", "行业·创新药"),
            ("中药", "行业·医药"),
            ("医疗", "行业·医药"),
            ("医药", "行业·医药"),
            ("生物", "行业·医药"),
            ("疫苗", "行业·医药"),
            ("证券", "行业·证券"),
            ("非银", "行业·非银金融"),
            ("保险", "行业·非银金融"),
            ("银行", "行业·银行"),
            ("通信", "行业·TMT其他"),
            ("5G", "行业·TMT其他"),
            ("卫星", "行业·TMT其他"),
            ("软件", "行业·TMT其他"),
            ("计算机", "行业·TMT其他"),
            ("云计算", "行业·TMT其他"),
            ("金融科技", "行业·TMT其他"),
            ("信创", "行业·TMT其他"),
            ("游戏", "行业·TMT其他"),
            ("传媒", "行业·TMT其他"),
            ("影视", "行业·TMT其他"),
            ("TMT", "行业·TMT其他"),
            ("物联网", "行业·TMT其他"),
            ("信息安全", "行业·TMT其他"),
            ("互联网", "行业·TMT其他"),
            ("电子", "行业·TMT其他"),
            ("有色", "行业·有色"),
            ("稀土", "行业·有色"),
            ("稀有金属", "行业·有色"),
            ("煤炭", "行业·周期资源"),
            ("化工", "行业·周期资源"),
            ("石化", "行业·周期资源"),
            ("钢铁", "行业·周期资源"),
            ("石油", "行业·周期资源"),
            ("油气", "行业·周期资源"),
            ("能源", "行业·周期资源"),
            ("黄金股", "行业·黄金股"),
            ("黄金", "行业·黄金股"),
            ("酒", "行业·消费"),
            ("消费", "行业·消费"),
            ("食品", "行业·消费"),
            ("家电", "行业·消费"),
            ("农业", "行业·消费"),
            ("养殖", "行业·消费"),
            ("农牧", "行业·消费"),
            ("旅游", "行业·消费"),
            ("家居", "行业·消费"),
            ("电网", "行业·电力"),
            ("绿电", "行业·电力"),
            ("绿色电力", "行业·电力"),
            ("电力", "行业·电力"),
            ("光伏", "行业·电力"),
            ("新能源", "行业·电力"),
            ("电池", "行业·电力"),
            ("储能", "行业·电力"),
            ("军工", "行业·军工"),
            ("国防", "行业·军工"),
            ("航空", "行业·军工"),
            ("船舶", "行业·军工"),
            ("地产", "行业·地产"),
            ("房地产", "行业·地产"),
            ("红利", "风格·红利族"),
            ("股息", "风格·红利族"),
            ("低波", "风格·红利族"),
            ("现金流", "风格·现金流族"),
            ("价值", "风格·因子"),
            ("成长", "风格·因子"),
            ("质量", "风格·因子"),
            ("科创50", "宽基·科创"),
            ("科创100", "宽基·科创"),
            ("科创200", "宽基·科创"),
            ("科创综指", "宽基·科创"),
            ("科创创业", "宽基·科创"),
            ("创业板", "宽基·创业板"),
            ("沪深300", "宽基·市值阶梯"),
            ("中证500", "宽基·市值阶梯"),
            ("中证1000", "宽基·市值阶梯"),
            ("中证2000", "宽基·市值阶梯"),
            ("中证800", "宽基·市值阶梯"),
            ("A500", "宽基·市值阶梯"),
            ("A50", "宽基·市值阶梯"),
            ("A100", "宽基·市值阶梯"),
            ("上证50", "宽基·市值阶梯"),
            ("上证180", "宽基·市值阶梯"),
            ("上证", "宽基·交易所其他"),
            ("深证", "宽基·交易所其他"),
            ("深成", "宽基·交易所其他"),
            ("科技", "行业·TMT其他"),
            ("信息技术", "行业·TMT其他"),
            ("信息科技", "行业·TMT其他"),
            ("数字经济", "行业·TMT其他"),
            ("大数据", "行业·TMT其他"),
            ("智能驾驶", "行业·汽车"),
            ("汽车", "行业·汽车"),
            ("工业母机", "行业·制造"),
            ("工程机械", "行业·制造"),
            ("机械", "行业·制造"),
            ("高端制造", "行业·制造"),
            ("智能制造", "行业·制造"),
            ("专精特新", "行业·制造"),
            ("基建", "行业·基建"),
            ("建材", "行业·基建"),
            ("一带一路", "行业·基建"),
            ("粮食", "行业·消费"),
            ("金融", "行业·非银金融"),
            ("资源", "行业·周期资源"),
            ("碳中和", "主题·绿色"),
            ("环保", "主题·绿色"),
            ("长江保护", "主题·绿色"),
            ("沪港深", "宽基·跨境"),
            ("国证2000", "宽基·市值阶梯"),
            ("中小100", "宽基·市值阶梯"),
            ("创业大盘", "宽基·创业板"),
            ("MSCI", "宽基·市值阶梯"),
            ("ESG", "风格·因子"),
            ("央企", "风格·央企国企"),
            ("国企", "风格·央企国企"),
            ("民企", "风格·央企国企"),
            ("战略新兴", "主题·新兴"),
            default="主题·其他",
        )
        if "科创" in n and family == "主题·其他":
            family = "宽基·科创"

    return theme, family, l0


def fetch_quotes(codes: list[str]) -> dict[str, dict[str, Any]]:
    out: dict[str, dict[str, Any]] = {}
    for i in range(0, len(codes), 50):
        batch = codes[i : i + 50]
        q = ",".join(f"{market(c)}{c}" for c in batch)
        raw = http_get_retry(f"https://qt.gtimg.cn/q={q}").decode("gbk", "replace")
        for line in raw.split(";"):
            line = line.strip()
            if not line or "=" not in line or "~" not in line:
                continue
            left, right = line.split("=", 1)
            code = left.split("_")[-1][-6:]
            fields = right.strip().strip(";").strip('"').split("~")
            name = fields[1] if len(fields) > 1 else ""
            aum = None
            if len(fields) > 44:
                try:
                    aum = float(fields[44])
                except ValueError:
                    aum = None
            out[code] = {"name": name, "aum": aum}
        time.sleep(0.12)
    return out


# ---------------------------------------------------------------------------
# Weekly bars
# ---------------------------------------------------------------------------

@dataclass
class Bar:
    date: str
    o: float
    h: float
    l: float
    c: float


def _f(x: Any) -> float:
    return float(x)


def parse_tencent_bars(payload: dict[str, Any], code: str) -> list[Bar]:
    data = payload.get("data") or {}
    key = f"{market(code)}{code}"
    node = data.get(key) or (next(iter(data.values())) if data else None)
    if not isinstance(node, dict):
        return []
    rows = node.get("qfqweek") or node.get("week") or []
    bars: list[Bar] = []
    for row in rows:
        if not row:
            continue
        d = str(row[0])[:10]
        if d > ASOF_S:
            continue
        # Tencent weekly: date, open, close, high, low
        o, cl, h, l = _f(row[1]), _f(row[2]), _f(row[3]), _f(row[4])
        if min(o, cl, h, l) <= 0:
            continue
        bars.append(Bar(d, o, h, l, cl))
    bars.sort(key=lambda b: b.date)
    return bars


def parse_yahoo_bars(payload: dict[str, Any]) -> list[Bar]:
    result = ((payload.get("chart") or {}).get("result") or [None])[0]
    if not result:
        return []
    ts = result.get("timestamp") or []
    q = (result.get("indicators") or {}).get("quote") or [{}]
    q0 = q[0]
    opens, highs, lows, closes = q0.get("open"), q0.get("high"), q0.get("low"), q0.get("close")
    bars: list[Bar] = []
    for i, t in enumerate(ts):
        if opens[i] is None or highs[i] is None or lows[i] is None or closes[i] is None:
            continue
        dt = datetime.fromtimestamp(int(t), tz=timezone.utc)
        # Yahoo weekly is typically week-start. Normalize to Friday week-end.
        wd = dt.weekday()
        if wd == 6:
            end = dt.date() + timedelta(days=5)
        elif wd <= 4:
            end = dt.date() + timedelta(days=(4 - wd))
        else:
            end = dt.date() - timedelta(days=wd - 4)
        if end > ASOF:
            continue
        o, h, l, c = float(opens[i]), float(highs[i]), float(lows[i]), float(closes[i])
        if min(o, h, l, c) <= 0:
            continue
        bars.append(Bar(end.isoformat(), o, h, l, c))
    bars.sort(key=lambda b: b.date)
    # de-dup
    uniq: dict[str, Bar] = {}
    for b in bars:
        uniq[b.date] = b
    return list(uniq.values())


def fetch_tencent_week(code: str) -> tuple[list[Bar], str]:
    m = market(code)
    url = (
        "https://web.ifzq.gtimg.cn/appstock/app/fqkline/get"
        f"?param={m}{code},week,{START_S},{END_S},200,qfq"
    )
    payload = json.loads(http_get_retry(url))
    bars = parse_tencent_bars(payload, code)
    return bars, "tencent_qfq_week"


def fetch_yahoo_week(code: str) -> tuple[list[Bar], str]:
    suffix = ".SS" if code[0] in "56" else ".SZ"
    p1 = int(datetime(2024, 1, 1, tzinfo=timezone.utc).timestamp())
    p2 = int(datetime(2026, 10, 9, 16, tzinfo=timezone(timedelta(hours=8))).timestamp())
    url = (
        "https://query1.finance.yahoo.com/v8/finance/chart/"
        f"{code}{suffix}?interval=1wk&period1={p1}&period2={p2}&events=history"
    )
    payload = json.loads(http_get_retry(url))
    bars = parse_yahoo_bars(payload)
    return bars, "yahoo_weekly"


def cache_covers_asof(cached: dict[str, Any]) -> bool:
    bars = cached.get("bars") or []
    if not bars:
        return False
    if cached.get("end") == END_S:
        return True
    last = max(str(b.get("date") or "") for b in bars)
    return last >= ASOF_S


def load_or_download_bars(code: str) -> dict[str, Any]:
    cache = RAW_DIR / f"{code}.json"
    if cache.exists():
        try:
            cached = json.loads(cache.read_text(encoding="utf-8"))
            if cache_covers_asof(cached):
                return cached
        except Exception:
            pass
    err = None
    for fn in (fetch_tencent_week, fetch_yahoo_week):
        try:
            bars, src = fn(code)
            if bars:
                rec = {
                    "code": code,
                    "source": src,
                    "end": END_S,
                    "bars": [
                        {"date": b.date, "o": b.o, "h": b.h, "l": b.l, "c": b.c}
                        for b in bars
                    ],
                }
                cache.write_text(json.dumps(rec, ensure_ascii=False), encoding="utf-8")
                return rec
            err = f"{src}_empty"
        except Exception as e:
            err = f"{fn.__name__}:{type(e).__name__}"
    rec = {"code": code, "source": None, "end": END_S, "bars": [], "error": err or "download_failed"}
    cache.write_text(json.dumps(rec, ensure_ascii=False), encoding="utf-8")
    return rec


# ---------------------------------------------------------------------------
# Brooks classification
# ---------------------------------------------------------------------------

def body(b: Bar) -> float:
    return abs(b.c - b.o)


def brange(b: Bar) -> float:
    return max(b.h - b.l, 1e-9)


def is_bull(b: Bar) -> bool:
    return b.c > b.o


def is_bear(b: Bar) -> bool:
    return b.c < b.o


def body_overlap(a: Bar, b: Bar) -> float:
    a1, a2 = min(a.o, a.c), max(a.o, a.c)
    b1, b2 = min(b.o, b.c), max(b.o, b.c)
    return max(0.0, min(a2, b2) - max(a1, b1))


def ema_series(values: list[float], span: int = 20) -> list[float]:
    if not values:
        return []
    if len(values) < span:
        span = max(2, len(values))
    k = 2.0 / (span + 1)
    out: list[float] = []
    sma = sum(values[:span]) / span
    for i, v in enumerate(values):
        if i < span - 1:
            out.append(sum(values[: i + 1]) / (i + 1))
        elif i == span - 1:
            out.append(sma)
        else:
            out.append(v * k + out[-1] * (1 - k))
    return out


def swing_indices(bars: list[Bar], left: int = 2, right: int = 2) -> tuple[list[int], list[int]]:
    n = len(bars)
    hi, lo = [], []
    if n < left + right + 1:
        return hi, lo
    for i in range(left, n - right):
        h, l = bars[i].h, bars[i].l
        if all(h >= bars[j].h for j in range(i - left, i + right + 1)):
            hi.append(i)
        if all(l <= bars[j].l for j in range(i - left, i + right + 1)):
            lo.append(i)
    return hi, lo


def last8_structure(bars: list[Bar]) -> tuple[int, int]:
    if len(bars) < 2:
        return 0, 0
    start = max(1, len(bars) - 8)
    hh_hl = lh_ll = 0
    for i in range(start, len(bars)):
        a, b = bars[i - 1], bars[i]
        if b.h > a.h and b.l > a.l:
            hh_hl += 1
        if b.h < a.h and b.l < a.l:
            lh_ll += 1
    return hh_hl, lh_ll


def median(xs: list[float]) -> float:
    if not xs:
        return 0.0
    s = sorted(xs)
    m = len(s) // 2
    return s[m] if len(s) % 2 else 0.5 * (s[m - 1] + s[m])


def large_bar(b: Bar, med_body: float, med_range: float) -> bool:
    return body(b) >= max(1.15 * med_body, 0.55 * brange(b)) and brange(b) >= 0.85 * med_range


def find_impulse(bars: list[Bar], side: str) -> tuple[Bar, Bar] | None:
    """Last clean swing used for a 100% measured move."""
    sh, sl = swing_indices(bars)
    if not sh or not sl:
        window = bars[-12:] if len(bars) >= 12 else bars
        lo = min(window, key=lambda b: b.l)
        hi = max(window, key=lambda b: b.h)
        return (lo, hi) if hi.date >= lo.date else (hi, lo)
    if side == "Long":
        last_hi = sh[-1]
        prior_lo = [i for i in sl if i < last_hi]
        if not prior_lo:
            return None
        return bars[prior_lo[-1]], bars[last_hi]
    if side == "Short":
        last_lo = sl[-1]
        prior_hi = [i for i in sh if i < last_lo]
        if not prior_hi:
            return None
        return bars[prior_hi[-1]], bars[last_lo]
    window = bars[-16:] if len(bars) >= 16 else bars
    return min(window, key=lambda b: b.l), max(window, key=lambda b: b.h)


def argmin_low(bars: list[Bar], lo: int, hi: int) -> int:
    return min(range(lo, hi), key=lambda i: bars[i].l)


def argmax_high(bars: list[Bar], lo: int, hi: int) -> int:
    return max(range(lo, hi), key=lambda i: bars[i].h)


def last_pivot_low(bars: list[Bar], look: int = 20) -> int:
    n = len(bars)
    sh, sl = swing_indices(bars, 2, 1 if n < 14 else 2)
    cands = [i for i in sl if i >= max(0, n - look) and i < n - 1]
    if cands:
        return min(cands, key=lambda i: bars[i].l)
    return argmin_low(bars, max(0, n - look), max(1, n - 1))


def last_pivot_high(bars: list[Bar], look: int = 20) -> int:
    n = len(bars)
    sh, sl = swing_indices(bars, 2, 1 if n < 14 else 2)
    cands = [i for i in sh if i >= max(0, n - look) and i < n - 1]
    if cands:
        return max(cands, key=lambda i: bars[i].h)
    return argmax_high(bars, max(0, n - look), max(1, n - 1))


def spike_run_now(bars: list[Bar]) -> tuple[int, int]:
    """Return (direction +1/-1/0, large-bar count) for the current tail."""
    n = len(bars)
    if n < 3:
        return 0, 0
    recent = bars[-20:] if n >= 20 else bars
    med_b = median([body(b) for b in recent]) or 1e-9
    med_r = median([brange(b) for b in recent]) or 1e-9
    tail = bars[-5:]
    direction = 1 if is_bull(tail[-1]) else (-1 if is_bear(tail[-1]) else 0)
    run: list[Bar] = []
    for b in reversed(tail):
        d = 1 if is_bull(b) else (-1 if is_bear(b) else 0)
        if d == 0 and run:
            run.append(b)
            continue
        if direction == 0:
            direction = d
        if d == direction or d == 0:
            run.append(b)
        else:
            break
    run = list(reversed(run))
    large = [b for b in run if large_bar(b, med_b, med_r)]
    ov = 0.0
    bodies = [b for b in run if body(b) > 0]
    if len(bodies) >= 2:
        ovs = [
            body_overlap(bodies[i], bodies[i + 1])
            / max(min(body(bodies[i]), body(bodies[i + 1])), 1e-9)
            for i in range(len(bodies) - 1)
        ]
        ov = sum(ovs) / len(ovs)
    if direction and len(large) >= 2 and ov < 0.40:
        return direction, len(large)
    # two large same-way bars with one inside bar between (gold Aug pattern)
    last4 = bars[-4:]
    large_idx = [i for i, b in enumerate(last4) if large_bar(b, med_b, med_r)]
    if len(large_idx) >= 2:
        a, b = last4[large_idx[0]], last4[large_idx[-1]]
        if is_bull(a) and is_bull(b) and b.h >= a.h and ov < 0.5:
            return 1, len(large_idx)
        if is_bear(a) and is_bear(b) and b.l <= a.l:
            return -1, len(large_idx)
    return 0, 0


def running_pullback(seg: list[Bar], side: str) -> float:
    if not seg:
        return 1.0
    span = max(max(b.h for b in seg) - min(b.l for b in seg), 1e-9)
    worst = 0.0
    if side == "Long":
        run = seg[0].h
        for b in seg:
            run = max(run, b.h)
            worst = max(worst, (run - b.l) / span)
    else:
        run = seg[0].l
        for b in seg:
            run = min(run, b.l)
            worst = max(worst, (b.h - run) / span)
    return worst


def channel_from(bars: list[Bar], start: int, side: str) -> dict[str, Any] | None:
    n = len(bars)
    if start < 0 or n - start < 4:
        return None
    seg = bars[start:]
    hh = ll = 0
    for i in range(start + 1, n):
        a, b = bars[i - 1], bars[i]
        if b.h > a.h and b.l > a.l:
            hh += 1
        if b.h < a.h and b.l < a.l:
            ll += 1
    lo = min(b.l for b in seg)
    hi = max(b.h for b in seg)
    last = bars[-1]
    span = max(hi - lo, 1e-9)
    pb = running_pullback(seg, side)
    hi_i = max(range(start, n), key=lambda i: bars[i].h)
    lo_i = min(range(start, n), key=lambda i: bars[i].l)
    if side == "Long":
        rising = hh >= ll + 1
        held = last.c > lo + 0.40 * span
        fresh = hi_i >= n - 3
        if not (rising and held):
            return None
        loc = (last.c - lo) / span
        spike_dir, spike_n = spike_run_now(bars)
        if spike_dir > 0 and spike_n >= 2 and loc >= 0.70:
            phase = "冲击"
        elif pb <= 0.48 and loc >= 0.65 and fresh and hh >= ll + 2 and n - start >= 6:
            phase = "紧通道"
        else:
            phase = "宽通道"
        return {
            "side": "Long",
            "phase": phase,
            "start": start,
            "weeks": n - start,
            "pb": pb,
            "hh": hh,
            "ll": ll,
            "loc": loc,
            "fresh": fresh,
        }
    falling = ll >= hh + 1
    held = last.c < hi - 0.40 * span
    fresh = lo_i >= n - 3
    loc = (hi - last.c) / span
    if not (falling and held and loc >= 0.55):
        return None
    spike_dir, spike_n = spike_run_now(bars)
    if spike_dir < 0 and spike_n >= 2 and loc >= 0.70:
        phase = "冲击"
    elif pb <= 0.48 and loc >= 0.65 and fresh and ll >= hh + 2 and n - start >= 6:
        phase = "紧通道"
    else:
        phase = "宽通道"
    return {
        "side": "Short",
        "phase": phase,
        "start": start,
        "weeks": n - start,
        "pb": pb,
        "hh": hh,
        "ll": ll,
        "loc": loc,
        "fresh": fresh,
    }


def detect_channel(bars: list[Bar]) -> dict[str, Any] | None:
    n = len(bars)
    if n < 6:
        return None
    low_i = last_pivot_low(bars, 22)
    high_i = last_pivot_high(bars, 22)
    up = channel_from(bars, low_i, "Long")
    dn = channel_from(bars, high_i, "Short")
    cands = [c for c in (up, dn) if c]
    if not cands:
        return None

    def score(c: dict[str, Any]) -> tuple:
        tight = 2 if c["phase"] == "冲击" else (1 if c["phase"] == "紧通道" else 0)
        return (c["start"], tight, c.get("loc", 0))

    # More recent origin wins; a bounce kills an old short.
    return max(cands, key=score)


def find_bull_climax(bars: list[Bar], look: int = 16) -> dict[str, Any] | None:
    n = len(bars)
    if n < 8:
        return None
    recent = bars[-30:] if n >= 30 else bars
    med_r = median([brange(b) for b in recent]) or 1e-9
    lo = max(0, n - look)
    ext_i = argmax_high(bars, lo, n)
    ext_h = bars[ext_i].h
    best = None
    for i in range(lo, n):
        if bars[i].h < ext_h * 0.985:
            continue
        run_s = max(lo, i - 2)
        run = bars[run_s : i + 1]
        wide = max(brange(b) for b in run) >= 1.65 * med_r
        bodies = sum(1 for b in run if is_bull(b) and body(b) >= 0.5 * brange(b))
        climax_bar = brange(bars[i]) >= 1.75 * med_r
        if not (wide or climax_bar):
            continue
        if bodies < 1 and not climax_bar:
            continue
        origin = min(b.l for b in run)
        if run_s > 0:
            origin = min(origin, bars[run_s - 1].l)
        score = bars[i].h + 0.3 * max(brange(b) for b in run)
        rec = {
            "side": "up",
            "start": run_s,
            "end": i,
            "high": bars[i].h,
            "origin": origin,
            "score": score,
        }
        if best is None or rec["high"] > best["high"] or (rec["high"] == best["high"] and score > best["score"]):
            best = rec
    return best


def reversal_state(bars: list[Bar], climax: dict[str, Any] | None) -> tuple[bool, bool]:
    """Return (mtr_complete, failed_spike). Failed spike is a late climax still unresolved."""
    if not climax or climax["side"] != "up":
        return False, False
    n = len(bars)
    end = climax["end"]
    if end >= n - 2:
        return False, False  # spike is current, not failed
    hi = climax["high"]
    origin = climax["origin"]
    height = hi - origin
    if height <= 0:
        return False, False
    post_low_i = argmin_low(bars, end + 1, n)
    post_low = bars[post_low_i].l
    collapse = (hi - post_low) / height
    if collapse < 0.50:
        return False, False
    after = bars[end + 1 :]
    ch_break = any(b.c < origin for b in after) or any(b.c < bars[end].l for b in after[:5])
    bounce_hi = max(b.h for b in bars[post_low_i:]) if post_low_i < n else post_low
    failed_retest = bounce_hi < hi * 0.995 and bounce_hi > post_low + 0.25 * (hi - post_low)
    second = False
    if failed_retest and post_low_i < n - 1:
        peak = argmax_high(bars, post_low_i, n)
        if peak < n - 1:
            second = any(bars[i].l < post_low for i in range(peak + 1, n))
    mtr = bool(ch_break and failed_retest and second)
    now = bars[-1].c
    recovered = (now - post_low) / max(hi - post_low, 1e-9)
    # still mid-box or lower, and the climax is the last major high
    still_failed = (not mtr) and recovered <= 0.62 and now < hi - 0.30 * height
    return mtr, still_failed


def range_like(bars: list[Bar], look: int = 12) -> bool:
    w = bars[-look:] if len(bars) >= look else bars
    if len(w) < 6:
        return False
    hh, ll = 0, 0
    for i in range(1, len(w)):
        if w[i].h > w[i - 1].h and w[i].l > w[i - 1].l:
            hh += 1
        if w[i].h < w[i - 1].h and w[i].l < w[i - 1].l:
            ll += 1
    hi, lo = max(b.h for b in w), min(b.l for b in w)
    mid = 0.5 * (hi + lo)
    top = any(b.h >= mid + 0.25 * (hi - lo) for b in w)
    bot = any(b.l <= mid - 0.25 * (hi - lo) for b in w)
    return top and bot and abs(hh - ll) <= 2


def box_break_pending_up(bars: list[Bar]) -> bool:
    n = len(bars)
    if n < 10:
        return False
    box = bars[-12:-1]
    if not range_like(box, look=len(box)):
        return False
    box_h = max(b.h for b in box)
    box_l = min(b.l for b in box)
    last = bars[-1]
    prev = bars[-2]
    if not (last.c > box_h and is_bull(last)):
        return False
    if prev.c > box_h:
        return False
    # ignore if the "box" is just a tight channel (steadily rising lows)
    rising = sum(1 for i in range(1, len(box)) if box[i].l > box[i - 1].l)
    if rising >= len(box) * 0.6:
        return False
    if box_h - box_l <= 0:
        return False
    return True


def classify(bars: list[Bar]) -> dict[str, Any]:
    n = len(bars)
    last = bars[-1]
    closes = [b.c for b in bars]
    emas = ema_series(closes, 20)
    ema = emas[-1]
    above = below = 0
    if last.c >= ema:
        for i in range(n - 1, -1, -1):
            if bars[i].c >= emas[i]:
                above += 1
            else:
                break
    else:
        for i in range(n - 1, -1, -1):
            if bars[i].c < emas[i]:
                below += 1
            else:
                break

    y25 = [b for b in bars if b.date >= "2025-01-01"] or bars
    sh = max(y25, key=lambda b: b.h)
    after = [b for b in bars if b.date > sh.date]
    sub_low = min(after, key=lambda b: b.l) if after else last
    pct_below = (last.c / sh.h - 1.0) * 100.0
    hh, ll = last8_structure(bars)

    channel = detect_channel(bars)
    climax = find_bull_climax(bars, look=16)
    mtr, failed_spike = reversal_state(bars, climax)
    spike_dir, spike_n = spike_run_now(bars)
    pending = box_break_pending_up(bars)

    new_long = bool(
        channel
        and channel["side"] == "Long"
        and channel["phase"] in {"冲击", "紧通道"}
        and channel["weeks"] >= 5
    )
    new_short = bool(
        channel
        and channel["side"] == "Short"
        and channel["phase"] in {"冲击", "紧通道"}
        and channel["weeks"] >= 5
    )

    drop = sh.h - sub_low.l
    retrace = (last.c - sub_low.l) / drop if drop > 0 else 0.0

    if new_long:
        always_in = "Long"
        phase = channel["phase"]
        if spike_dir > 0 and spike_n >= 2:
            phase = "冲击"
        failed_spike = False
    elif failed_spike:
        always_in = "不清楚"
        phase = "震荡"
    elif new_short and mtr:
        always_in = "Short"
        phase = channel["phase"]
    elif channel and channel["side"] == "Long":
        phase = channel["phase"]
        if phase in {"冲击", "紧通道"} or pct_below > -15 or retrace >= 0.62:
            always_in = "Long"
        else:
            always_in = "不清楚"
    elif channel and channel["side"] == "Short" and channel.get("loc", 0) >= 0.65:
        always_in = "Short"
        phase = channel["phase"]
    elif spike_dir > 0 and spike_n >= 2:
        always_in = "Long"
        phase = "冲击"
    else:
        always_in = "不清楚"
        phase = "震荡"

    box_h, box_l = (
        max(b.h for b in (bars[-14:-1] if n > 14 else bars[:-1] or bars)),
        min(b.l for b in (bars[-14:-1] if n > 14 else bars[:-1] or bars)),
    )

    impulse = find_impulse(bars, always_in)
    magnet = None
    magnet_note = ""
    if always_in == "Long" and impulse:
        a, b = impulse
        span = b.h - a.l
        magnet = round(b.h + span, 4)
        magnet_note = "冲击腿100%等距"
    elif always_in == "Short" and impulse:
        a, b = impulse
        span = a.h - b.l
        magnet = round(b.l - span, 4)
        magnet_note = "冲击腿100%等距"
    else:
        magnet = round(box_l if last.c > 0.5 * (box_h + box_l) else box_h, 4)
        magnet_note = "箱体对边"

    sh_i, sl_i = swing_indices(bars)
    falsify = None
    if always_in == "Long":
        lows = [i for i in sl_i if i >= n - 16] or sl_i[-2:]
        falsify = round(bars[lows[-1]].l, 4) if lows else round(min(b.l for b in bars[-6:]), 4)
    elif always_in == "Short":
        highs = [i for i in sh_i if i >= n - 16] or sh_i[-2:]
        falsify = round(bars[highs[-1]].h, 4) if highs else round(max(b.h for b in bars[-6:]), 4)

    in_play = False
    in_play_kind = None
    bucket = "其他"
    established = pct_below > -12.0 or retrace >= 0.62
    if always_in == "Long" and phase == "紧通道" and established:
        in_play, in_play_kind, bucket = True, "tight_long", "在结构里"
    elif always_in == "Long" and phase == "冲击":
        in_play, in_play_kind, bucket = True, "spike_ft", "在结构里"
    elif pending and always_in in {"Long", "不清楚"}:
        in_play, in_play_kind, bucket = True, "box_pending", "在结构里"
    elif always_in == "Short" and mtr:
        in_play, in_play_kind, bucket = True, "short_mtr", "空头结构"
    elif failed_spike:
        bucket = "高潮失败"

    sentence = make_sentence(
        always_in, phase, bucket, in_play_kind == "box_pending", mtr, failed_spike, hh, ll
    )

    return {
        "always_in": always_in,
        "phase": phase,
        "in_play": in_play,
        "in_play_kind": in_play_kind,
        "bucket": bucket,
        "pending_second_week": bool(in_play_kind == "box_pending"),
        "mtr_complete": mtr,
        "failed_spike": failed_spike,
        "last_close": round(last.c, 4),
        "last_bar_date": last.date,
        "swing_high": {"date": sh.date, "price": round(sh.h, 4)},
        "pct_below_high": round(pct_below, 2),
        "subsequent_low": {"date": sub_low.date, "price": round(sub_low.l, 4)},
        "weeks_above_ema20": above,
        "weeks_below_ema20": below,
        "ema20": round(ema, 4),
        "last8_hh_hl": hh,
        "last8_lh_ll": ll,
        "magnet": magnet,
        "magnet_note": magnet_note,
        "falsify_close": falsify,
        "sentence": sentence,
    }


def make_sentence(
    always_in: str,
    phase: str,
    bucket: str,
    pending: bool,
    mtr: bool,
    failed_spike: bool,
    hh: int,
    ll: int,
) -> str:
    if bucket == "高潮失败":
        return "高潮回吐，缺二次下跌"
    if pending and bucket == "在结构里":
        return "箱体刚破，待第二周确认"
    if always_in == "Long" and phase == "紧通道":
        return "多头紧通道，回撤浅未破"
    if always_in == "Long" and phase == "冲击":
        return "多头冲击，跟进仍在"
    if always_in == "Short" and mtr:
        return "空头反转完成，第二腿走"
    if always_in == "Short" and phase == "紧通道":
        return "空头紧通道，尚未走完MTR"
    if always_in == "Long" and phase == "宽通道":
        return "多头宽通道，回撤加深"
    if always_in == "不清楚" and phase == "宽通道":
        return "宽通道未换边，箱体仍在"
    if always_in == "不清楚" or phase == "震荡":
        if hh <= ll:
            return "双破失败，仍是震荡"
        return "箱体来回，突破未跟"
    if phase == "宽通道":
        return "通道展宽，趋势衰减"
    return "结构未清，不侧向解释"


def pack_weekly(bars: list[Bar], n: int = 40) -> list[list[Any]]:
    out = []
    for b in bars[-n:]:
        out.append([b.date, round(b.o, 4), round(b.h, 4), round(b.l, 4), round(b.c, 4)])
    return out


# ---------------------------------------------------------------------------
# Pipeline
# ---------------------------------------------------------------------------

def scan_one(meta: dict[str, Any], quote: dict[str, Any] | None) -> dict[str, Any]:
    code = meta["code"]
    name = meta["name"]
    index = meta["index"]
    family = meta["family"]
    l0 = meta["l0"]
    aum = meta["aum"]
    if quote:
        if not name:
            name = quote.get("name") or ""
        if aum is None:
            aum = quote.get("aum")
    if not family or not l0 or not index:
        theme, fam, l0g = classify_l0_family(name, code)
        index = index or theme
        family = family or fam
        l0 = l0 or l0g

    raw = load_or_download_bars(code)
    bars_d = raw.get("bars") or []
    row: dict[str, Any] = {
        "code": code,
        "name": name or code,
        "index": index or "",
        "family": family or "主题·其他",
        "l0": l0 or "中国权益",
        "aum": aum,
        "source": raw.get("source"),
        "thin_history": False,
        "data_error": None,
        "always_in": None,
        "phase": None,
        "in_play": False,
        "in_play_kind": None,
        "bucket": "其他",
        "pending_second_week": False,
        "mtr_complete": False,
        "failed_spike": False,
        "last_close": None,
        "last_bar_date": None,
        "swing_high": None,
        "pct_below_high": None,
        "subsequent_low": None,
        "weeks_above_ema20": None,
        "weeks_below_ema20": None,
        "ema20": None,
        "last8_hh_hl": None,
        "last8_lh_ll": None,
        "magnet": None,
        "magnet_note": None,
        "falsify_close": None,
        "sentence": None,
        "weekly": [],
        "us_week_open": bool(
            l0 == "海外" or "QDII" in (name or "").upper()
        ),
    }
    if not bars_d:
        row["data_error"] = raw.get("error") or "无周线"
        return row
    bars = [Bar(b["date"], b["o"], b["h"], b["l"], b["c"]) for b in bars_d]
    bars = [b for b in bars if b.date <= ASOF_S]
    if not bars:
        row["data_error"] = raw.get("error") or "无周线"
        return row
    if len(bars) < 30:
        row["thin_history"] = True
    try:
        if len(bars) < 5:
            last = bars[-1]
            sh = max(bars, key=lambda b: b.h)
            sl = min(bars, key=lambda b: b.l)
            row.update(
                {
                    "always_in": "不清楚",
                    "phase": "震荡",
                    "in_play": False,
                    "bucket": "其他",
                    "last_close": round(last.c, 4),
                    "last_bar_date": last.date,
                    "swing_high": {"date": sh.date, "price": round(sh.h, 4)},
                    "pct_below_high": round((last.c / sh.h - 1.0) * 100.0, 2),
                    "subsequent_low": {"date": sl.date, "price": round(sl.l, 4)},
                    "weeks_above_ema20": 0,
                    "weeks_below_ema20": 0,
                    "last8_hh_hl": 0,
                    "last8_lh_ll": 0,
                    "magnet": None,
                    "magnet_note": "历史过短",
                    "falsify_close": None,
                    "sentence": "上市过短，结构未立",
                    "weekly": pack_weekly(bars),
                    "n_bars": len(bars),
                }
            )
            return row
        row.update(classify(bars))
        row["weekly"] = pack_weekly(bars)
        row["n_bars"] = len(bars)
    except Exception as e:
        row["data_error"] = f"classify:{type(e).__name__}"
    return row


def run() -> dict[str, Any]:
    RAW_DIR.mkdir(parents=True, exist_ok=True)
    universe = load_universe()
    print(f"universe {len(universe)}", flush=True)
    quotes = fetch_quotes([r["code"] for r in universe])
    print(f"quotes {len(quotes)}", flush=True)

    rows: list[dict[str, Any]] = []
    with ThreadPoolExecutor(max_workers=WORKERS) as ex:
        futs = {ex.submit(scan_one, meta, quotes.get(meta["code"])): meta["code"] for meta in universe}
        done = 0
        for fut in as_completed(futs):
            rows.append(fut.result())
            done += 1
            if done % 40 == 0:
                print(f"  scanned {done}/{len(universe)}", flush=True)
    order = {r["code"]: i for i, r in enumerate(universe)}
    rows.sort(key=lambda r: order[r["code"]])
    failed = sum(1 for r in rows if r.get("data_error"))
    scanned_ok = len(rows) - failed
    payload = {
        "asof": ASOF_S,
        "generated": ASOF_S,
        "tz": "Asia/Shanghai",
        "a_week_closed": True,
        "us_week_closed": False,
        "universe": "ETF每指数最优工具_20260830",
        "source": "Tencent fqkline qfq weekly; Yahoo 1wk fallback",
        "n": len(rows),
        "scanned_ok": scanned_ok,
        "failed": failed,
        "always_in_long": sum(1 for r in rows if r.get("always_in") == "Long"),
        "in_play": sum(1 for r in rows if r.get("in_play")),
        "rows": rows,
    }
    return payload


# ---------------------------------------------------------------------------
# HTML
# ---------------------------------------------------------------------------

HTML = r"""<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>每指数冠军 ETF · Brooks 周线</title>
<link rel="preconnect" href="https://fonts.googleapis.com">
<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link href="https://fonts.googleapis.com/css2?family=IBM+Plex+Mono:wght@400;500&family=IBM+Plex+Sans+SC:wght@400;500;600&family=IBM+Plex+Sans:wght@400;500;600&family=Noto+Serif+SC:wght@500;600;700&family=Source+Serif+4:wght@500;600&display=swap" rel="stylesheet">
<style>
:root{
  --paper:#F8F7F3;
  --paper-2:#F0EFEA;
  --ink:#1A1917;
  --ink-soft:#4A463F;
  --rule:#C8C2B6;
  --lacquer:#9C3B2C;
  --up:#1F6B4A;
  --warn:#8A6A2F;
}
*{box-sizing:border-box;margin:0;padding:0}
html,body{background:var(--paper);color:var(--ink)}
body{
  font-family:"IBM Plex Sans SC","IBM Plex Sans","PingFang SC","Hiragino Sans GB","Microsoft YaHei",sans-serif;
  font-size:14px;line-height:1.5;
}
.wrap{max-width:1120px;margin:0 auto;padding:28px 20px 64px}
header{padding-bottom:22px;border-bottom:1px solid var(--rule);margin-bottom:28px}
.brand{
  font-family:"IBM Plex Sans SC","IBM Plex Sans",sans-serif;
  font-size:11px;letter-spacing:0.14em;color:var(--ink-soft);
}
.lac-bar{width:32px;height:2px;background:var(--lacquer);margin:10px 0 14px}
h1{
  font-family:"Noto Serif SC","Source Serif 4","Songti SC","STSong","SimSun",serif;
  font-weight:600;font-size:28px;letter-spacing:0.02em;line-height:1.25;
}
.sub{
  margin-top:8px;font-size:11px;letter-spacing:0.16em;color:var(--ink-soft);
  font-family:"IBM Plex Mono",ui-monospace,monospace;
}
.asof{margin-top:14px;font-size:12px;color:var(--ink-soft)}
.nums{display:grid;grid-template-columns:repeat(3,1fr);gap:0;border:1px solid var(--rule);margin-bottom:22px}
.num{padding:18px 16px;border-right:1px solid var(--rule)}
.num:last-child{border-right:0}
.num .v{
  font-family:"Noto Serif SC","Source Serif 4",serif;
  font-size:40px;line-height:1;font-weight:600;
}
.num .v.lac{color:var(--lacquer)}
.num .k{margin-top:8px;font-size:12px;color:var(--ink-soft)}
.filters{margin-bottom:28px}
.fg{margin:0 0 10px}
.fl{
  display:inline-block;min-width:72px;font-size:11px;letter-spacing:0.08em;
  color:var(--ink-soft);margin-right:8px;
}
.chip{
  display:inline-block;border:1px solid var(--rule);border-radius:2px;
  padding:2px 8px;margin:0 6px 6px 0;background:var(--paper);
  font-size:12px;cursor:pointer;color:var(--ink);
}
.chip.on{border-color:var(--lacquer);color:var(--lacquer)}
.chip.long{color:var(--up);border-color:var(--rule)}
.chip.long.on{border-color:var(--up);color:var(--up)}
.chip.warn{color:var(--warn)}
.chip.warn.on{border-color:var(--warn)}
.chip.short{color:var(--lacquer)}
band h2,.band h2{
  font-family:"Noto Serif SC","Source Serif 4",serif;
  font-size:18px;font-weight:600;margin:0 0 12px;
}
.band{margin:0 0 36px}
.cards{display:grid;grid-template-columns:1fr 1fr;gap:12px}
@media(max-width:800px){
  .cards{grid-template-columns:1fr}
  .nums{grid-template-columns:1fr}
  .num{border-right:0;border-bottom:1px solid var(--rule)}
}
.card{
  border:1px solid var(--rule);padding:12px 12px 8px;background:var(--paper);
}
.card.sel{border-color:var(--lacquer)}
.card .top{display:flex;justify-content:space-between;align-items:baseline;gap:8px}
.ticker{font-family:"IBM Plex Mono",ui-monospace,monospace;font-size:13px}
.nm{font-size:13px}
.meta{margin:6px 0 8px;font-size:12px;color:var(--ink-soft)}
.kv{display:grid;grid-template-columns:1fr 1fr;gap:4px 12px;font-size:12px;margin-bottom:8px}
.kv span{color:var(--ink-soft)}
.sent{font-size:13px;margin:0 0 8px}
svg.wk{width:100%;height:72px;display:block}
.ai{font-size:12px}
.ai.L{color:var(--up)}
.ai.S{color:var(--lacquer)}
.ai.U{color:var(--warn)}
table{width:100%;border-collapse:collapse;font-size:12px}
th,td{border-bottom:1px solid var(--rule);padding:6px 8px;text-align:left;vertical-align:top}
th{
  font-weight:500;color:var(--ink-soft);background:var(--paper);
  position:sticky;top:0;z-index:1;
}
tr:nth-child(even) td{background:var(--paper-2)}
tr.sel td{outline:1px solid var(--lacquer);outline-offset:-1px}
tr.err td{color:#8A8680}
.right{text-align:right}
.search{
  width:100%;max-width:360px;border:1px solid var(--rule);border-radius:0;
  background:var(--paper);padding:6px 8px;font:inherit;margin:0 0 10px;
  color:var(--ink);
}
.search:focus{outline:1px solid var(--ink)}
.empty{color:var(--ink-soft);font-size:13px;padding:8px 0}
footer{border-top:1px solid var(--rule);padding-top:16px;color:var(--ink-soft);font-size:12px}
footer p{margin:0 0 6px}
.mark{font-size:11px;color:var(--ink-soft)}
</style>
</head>
<body>
<div class="wrap">
<header>
  <div class="brand">HENG 衡</div>
  <div class="lac-bar"></div>
  <h1>每指数冠军 ETF · Brooks 周线</h1>
  <div class="sub">ALWAYS IN / CHANNEL / RANGE / INVALIDATION</div>
  <div class="asof">__ASOF__ · A股周线已收 · 美股周线未收</div>
</header>

<section class="nums" id="nums"></section>
<section class="filters" id="filters"></section>

<section class="band">
  <h2>在结构里</h2>
  <div class="cards" id="inplay"></div>
</section>

<section class="band" id="short-band">
  <h2>空头结构</h2>
  <div id="shorts"></div>
</section>

<section class="band">
  <h2>高潮失败</h2>
  <div id="failed"></div>
</section>

<section class="band">
  <h2>全表</h2>
  <input class="search" id="q" placeholder="检索 代码 / 名称 / 指数" autocomplete="off">
  <div id="all"></div>
</section>

<footer>
  <p>只报结构，不荐股。周线 Always In 压过日线。证伪是周收。</p>
  <p>Tencent qfq weekly，universe = ETF每指数最优工具_20260830，as-of __ASOF__。A股周线已收 · 美股周线未收。只报结构，不荐股。</p>
</footer>
</div>
<script type="application/json" id="scan-data">__SCAN_JSON__</script>
<script>
(function(){
  const DATA = JSON.parse(document.getElementById('scan-data').textContent);
  const rows = DATA.rows;
  const state = {ai:'', phase:'', l0:'', family:'', q:'', sel:''};

  const $ = id => document.getElementById(id);
  const esc = s => String(s==null?'':s).replace(/[&<>"']/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
  const money = v => v==null ? '—' : Number(v).toLocaleString('zh-CN', {maximumFractionDigits:1});
  const px = v => v==null ? '—' : Number(v).toFixed(3);
  const pct = v => v==null ? '—' : (v>0?'+':'') + Number(v).toFixed(1) + '%';
  const aiLab = v => v==='Long' ? 'Long' : v==='Short' ? '空' : v ? '不清楚' : '—';
  const aiCls = v => v==='Long' ? 'L' : v==='Short' ? 'S' : 'U';
  const usOpen = r => !!(r.us_week_open || r.l0==='海外' || /QDII/i.test(r.name||''));
  const usMark = r => usOpen(r) ? '<span class="mark"> 美股周线未收</span>' : '';

  function pass(r){
    if(state.ai && r.always_in !== state.ai) return false;
    if(state.phase && r.phase !== state.phase) return false;
    if(state.l0 && r.l0 !== state.l0) return false;
    if(state.family && r.family !== state.family) return false;
    if(state.q){
      const q = state.q.toLowerCase();
      const blob = (r.code+' '+r.name+' '+r.index).toLowerCase();
      if(!blob.includes(q)) return false;
    }
    return true;
  }
  const shown = () => rows.filter(pass);

  function spark(weekly){
    if(!weekly || weekly.length<2) return '';
    const w=320, h=68, pad=4;
    const highs=weekly.map(b=>b[2]), lows=weekly.map(b=>b[3]);
    const mx=Math.max.apply(null,highs), mn=Math.min.apply(null,lows);
    const span=mx-mn || 1;
    const bw = Math.max(2, (w - pad*2) / weekly.length - 1.2);
    const x0 = pad;
    const y = v => pad + (mx-v)/span*(h-pad*2);
    let d='';
    weekly.forEach((b,i)=>{
      const x = x0 + i*((w-pad*2)/weekly.length) + 1;
      const o=b[1],hgt=b[2],l=b[3],c=b[4];
      const up = c>=o;
      const col = up ? '#1F6B4A' : '#9C3B2C';
      const y1=y(hgt), y2=y(l), yo=y(o), yc=y(c);
      d += `<line x1="${x+bw/2}" y1="${y1}" x2="${x+bw/2}" y2="${y2}" stroke="${col}" stroke-width="1"/>`;
      const top=Math.min(yo,yc), bh=Math.max(1, Math.abs(yc-yo));
      d += `<rect x="${x}" y="${top}" width="${bw}" height="${bh}" fill="${col}"/>`;
    });
    return `<svg class="wk" viewBox="0 0 ${w} ${h}" preserveAspectRatio="none">${d}</svg>`;
  }

  function chip(group, val, label, extra){
    const on = state[group]===val ? ' on' : '';
    return `<button type="button" class="chip ${extra||''}${on}" data-g="${group}" data-v="${esc(val)}">${esc(label)}</button>`;
  }

  function renderFilters(){
    const fams = Array.from(new Set(rows.map(r=>r.family).filter(Boolean))).sort();
    $('filters').innerHTML = `
      <div class="fg"><span class="fl">ALWAYS IN</span>
        ${chip('ai','Long','Long','long')}${chip('ai','Short','空','short')}${chip('ai','不清楚','不清楚','warn')}</div>
      <div class="fg"><span class="fl">三态</span>
        ${['冲击','紧通道','宽通道','震荡'].map(p=>chip('phase',p,p)).join('')}</div>
      <div class="fg"><span class="fl">L0</span>
        ${['中国权益','港股','海外','商品'].map(p=>chip('l0',p,p)).join('')}</div>
      <div class="fg"><span class="fl">FAMILY</span>
        ${fams.map(p=>chip('family',p,p)).join('')}</div>`;
    $('filters').querySelectorAll('.chip').forEach(el=>{
      el.addEventListener('click', ()=>{
        const g=el.dataset.g, v=el.dataset.v;
        state[g] = state[g]===v ? '' : v;
        render();
      });
    });
  }

  function renderNums(list){
    const n = DATA.n;
    const ail = rows.filter(r=>r.always_in==='Long').length;
    const ip = rows.filter(r=>r.in_play && r.bucket==='在结构里').length;
    $('nums').innerHTML = `
      <div class="num"><div class="v">${n}</div><div class="k">已扫描</div></div>
      <div class="num"><div class="v">${ail}</div><div class="k">Always In Long</div></div>
      <div class="num"><div class="v lac">${ip}</div><div class="k">在结构里</div></div>`;
  }

  function kindRank(r){
    return {tight_long:0, spike_ft:1, box_pending:2}[r.in_play_kind] ?? 9;
  }

  function card(r){
    const sel = state.sel===r.code ? ' sel' : '';
    const pend = r.pending_second_week ? '<span class="mark"> 待第二周确认</span>' : '';
    const thin = r.thin_history ? '<span class="mark"> 薄历史</span>' : '';
    return `<article class="card${sel}" data-code="${r.code}">
      <div class="top"><div><span class="ticker">${esc(r.code)}</span>　<span class="nm">${esc(r.name)}</span>${usMark(r)}</div>
        <div><span class="ai ${aiCls(r.always_in)}">${aiLab(r.always_in)}</span> · ${esc(r.phase||'')}${pend}${thin}</div></div>
      <div class="kv">
        <div>收 ${px(r.last_close)}</div>
        <div>距高 ${pct(r.pct_below_high)}</div>
        <div>磁铁 ${px(r.magnet)} <span>${esc(r.magnet_note||'')}</span></div>
        <div>证伪周收 ${px(r.falsify_close)}</div>
      </div>
      <div class="sent">${esc(r.sentence||'')}</div>
      ${spark(r.weekly)}
    </article>`;
  }

  function table(list, cols){
    if(!list.length) return '<p class="empty">本组无记录。</p>';
    const head = cols.map(c=>`<th class="${c.cls||''}">${c.h}</th>`).join('');
    const body = list.map(r=>{
      const err = r.data_error ? ' err' : '';
      const sel = state.sel===r.code ? ' sel' : '';
      const tds = cols.map(c=>`<td class="${c.cls||''}">${c.cell(r)}</td>`).join('');
      return `<tr class="${err}${sel}" data-code="${r.code}">${tds}</tr>`;
    }).join('');
    return `<table><thead><tr>${head}</tr></thead><tbody>${body}</tbody></table>`;
  }

  const compactCols = [
    {h:'代码', cell:r=>`<span class="ticker">${esc(r.code)}</span>`},
    {h:'名称', cell:r=>esc(r.name)+usMark(r)},
    {h:'Always In', cell:r=>`<span class="ai ${aiCls(r.always_in)}">${aiLab(r.always_in)}</span>`},
    {h:'三态', cell:r=>esc(r.phase||'—')},
    {h:'收', cls:'right', cell:r=>px(r.last_close)},
    {h:'距高', cls:'right', cell:r=>pct(r.pct_below_high)},
    {h:'证伪', cls:'right', cell:r=>px(r.falsify_close)},
    {h:'结构', cell:r=>esc(r.sentence||r.data_error||'')},
  ];
  const allCols = [
    {h:'代码', cell:r=>`<span class="ticker">${esc(r.code)}</span>`},
    {h:'名称', cell:r=>esc(r.name)+(r.thin_history?' <span class="mark">薄历史</span>':'')+usMark(r)},
    {h:'指数', cell:r=>esc(r.index)},
    {h:'族', cell:r=>esc(r.family)},
    {h:'收', cls:'right', cell:r=>px(r.last_close)},
    {h:'距高', cls:'right', cell:r=>pct(r.pct_below_high)},
    {h:'Always In', cell:r=>r.data_error?esc(r.data_error):`<span class="ai ${aiCls(r.always_in)}">${aiLab(r.always_in)}</span>`},
    {h:'三态', cell:r=>esc(r.phase||'—')},
    {h:'证伪', cls:'right', cell:r=>px(r.falsify_close)},
    {h:'AUM', cls:'right', cell:r=>money(r.aum)},
  ];

  function bindSel(root){
    root.querySelectorAll('[data-code]').forEach(el=>{
      el.addEventListener('click', ()=>{
        state.sel = state.sel===el.dataset.code ? '' : el.dataset.code;
        render(false);
      });
    });
  }

  function render(refillFilters){
    if(refillFilters!==false) renderFilters();
    const list = shown();
    renderNums(list);
    const longs = list.filter(r=>r.in_play && r.bucket==='在结构里').sort((a,b)=>kindRank(a)-kindRank(b)||(a.code>b.code?1:-1));
    $('inplay').innerHTML = longs.length ? longs.map(card).join('') : '<p class="empty">过滤后无在结构里的品种。</p>';
    const shorts = list.filter(r=>r.bucket==='空头结构');
    $('shorts').innerHTML = table(shorts, compactCols);
    $('short-band').style.display = shorts.length ? '' : 'none';
    const fails = list.filter(r=>r.bucket==='高潮失败');
    $('failed').innerHTML = table(fails, compactCols);
    const all = state.q || state.ai || state.phase || state.l0 || state.family ? list : rows.filter(r=>{
      if(state.ai && r.always_in!==state.ai) return false;
      if(state.phase && r.phase!==state.phase) return false;
      if(state.l0 && r.l0!==state.l0) return false;
      if(state.family && r.family!==state.family) return false;
      return true;
    });
    $('all').innerHTML = table(all, allCols);
    bindSel($('inplay')); bindSel($('shorts')); bindSel($('failed')); bindSel($('all'));
  }

  $('q').addEventListener('input', e=>{ state.q = e.target.value.trim(); render(false); });
  render(true);
})();
</script>
</body>
</html>
"""


def write_outputs(payload: dict[str, Any]) -> None:
    SCAN_JSON.parent.mkdir(parents=True, exist_ok=True)
    SCAN_JSON.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    blob = json.dumps(payload, ensure_ascii=False, separators=(",", ":"))
    INDEX_HTML.write_text(
        HTML.replace("__SCAN_JSON__", blob).replace("__ASOF__", payload["asof"]),
        encoding="utf-8",
    )

    defs = (
        "Always In：最近一次带跟进的成功突破所在的一侧，浅回撤延续仍算该侧，双向突破都失败则不清楚。"
        "三态：冲击是连续大实体少重叠，紧通道是回撤后趋势仍在，宽通道是趋势衰减，震荡是两边都能走且突破失败。"
        "主升/主跌反转是过程：高潮→通道破坏→极端位失败回测→反向第二腿，缺一步仍只是回撤。"
        "磁铁取冲击腿的100%等距或箱体对边。"
        "证伪是打掉当前 Always In 的那一根周收。"
    )
    readme = (
        f"截至 {payload['asof']}（Asia/Shanghai 本周五；A股周线已收 · 美股周线未收），"
        f"数据源为腾讯前复权周线（Yahoo 周线兜底），"
        f"样本为 Michael Yang《ETF每指数最优工具_20260830》每指数市值最大工具共 {payload['n']} 只，"
        f"扫描成功 {payload['scanned_ok']}、下载失败 {payload['failed']}。"
        f"{defs}"
        "本页只报结构，不荐股。\n"
    )
    README.write_text(readme, encoding="utf-8")
    print(f"wrote {SCAN_JSON} {INDEX_HTML} {README}", flush=True)
    print(
        f"ok={payload['scanned_ok']} fail={payload['failed']} "
        f"AIL={payload['always_in_long']} in_play={payload['in_play']}",
        flush=True,
    )


if __name__ == "__main__":
    t0 = time.time()
    payload = run()
    write_outputs(payload)
    print(f"elapsed {time.time()-t0:.1f}s", flush=True)
