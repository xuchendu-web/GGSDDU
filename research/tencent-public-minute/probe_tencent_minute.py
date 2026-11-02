#!/usr/bin/env python3
"""腾讯公开 HTTP：qt / 当日 1m / 近端分时 — 研究池对照与探活。

硬闸（2026-10-31 已审；2026-11-02 Michael/悟空补齐要求）：
- 腾讯是实盘实时旁路，不是回测权威，不可替 cjpy AUM，不碰 LIVE / strategy_exec。
- 无 token、无 SLA；14:30 须滤 time<=14:30；休市吐最近交易日须自判。
- 禁止接入进门 / 中金 / Alpha派行情；禁止扩东财未审口 / 国金 QMT。

仅依赖标准库。对照仓库已有价源（research_cache/day 或 --ref-csv）若挂载则比价，
价差 >0.3% 标黄。
"""

from __future__ import annotations

import argparse
import csv
import json
import ssl
import time
import urllib.error
import urllib.request
from dataclasses import dataclass, field
from datetime import datetime, time as dtime, timedelta, timezone
from pathlib import Path
from typing import Any

CST = timezone(timedelta(hours=8))
YELLOW_PCT = 0.003
UA = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
    )
}
CTX = ssl.create_default_context()

QT_URL = "https://qt.gtimg.cn/q={q}"
MKLINE_URLS = (
    "https://ifzq.gtimg.cn/appstock/app/kline/mkline?param={sym},m1,,{n}",
)
MINUTE_URLS = (
    "https://web.ifzq.gtimg.cn/appstock/app/minute/query?code={sym}",
)
DAY_URLS = (
    "https://web.ifzq.gtimg.cn/appstock/app/fqkline/get?param={sym},day,,,5,qfq",
)

HERE = Path(__file__).resolve().parent
REPO_ROOT = HERE.parents[1]
AUTO_REF_DIRS = (
    REPO_ROOT / "research/cloud_batch/CLOUD-BATCH-2026-10-26/data/research_cache/day",
)


# ---------------------------------------------------------------------------
# 纯函数（单测覆盖，不碰网络）
# ---------------------------------------------------------------------------

def market_prefix(code: str) -> str:
    """与仓库 cloud_batch 一致：5/6 开头走 sh，其余走 sz。"""
    code = code.strip()
    if not code:
        raise ValueError("empty code")
    return "sh" if code[0] in "56" else "sz"


def symbol(code: str) -> str:
    return f"{market_prefix(code)}{code.strip()}"


def parse_float(x: Any) -> float | None:
    if x is None:
        return None
    s = str(x).strip()
    if not s or s in {".", "--", "None"}:
        return None
    try:
        v = float(s)
    except ValueError:
        return None
    if v <= 0:
        return None
    return v


def hhmm_int(hhmm: str) -> int | None:
    digits = "".join(ch for ch in hhmm if ch.isdigit())
    if len(digits) < 4:
        return None
    return int(digits[-4:])


def hhmm_to_minutes(hhmm: int) -> int:
    return (hhmm // 100) * 60 + (hhmm % 100)


def parse_qt_body(raw: str) -> dict[str, dict[str, Any]]:
    """解析 qt.gtimg.cn GBK/~ 包。不把 fields[44] 当 AUM。"""
    out: dict[str, dict[str, Any]] = {}
    for line in raw.split(";"):
        line = line.strip()
        if not line or "=" not in line or "~" not in line:
            continue
        left, right = line.split("=", 1)
        fields = right.strip().strip(";").strip('"').split("~")
        if len(fields) < 6:
            continue
        code = (fields[2] if len(fields) > 2 else left.split("_")[-1][-6:]).strip()
        if len(code) < 6:
            code = left.split("_")[-1][-6:]
        ts = fields[30] if len(fields) > 30 else ""
        out[code] = {
            "code": code,
            "name": fields[1] if len(fields) > 1 else "",
            "price": parse_float(fields[3]),
            "prev_close": parse_float(fields[4]),
            "open": parse_float(fields[5]),
            "volume": parse_float(fields[6]),
            "datetime": ts,
            "session_date": ts[:8] if len(ts) >= 8 else "",
            "session_hhmmss": ts[8:14] if len(ts) >= 14 else "",
            "high": parse_float(fields[33]) if len(fields) > 33 else None,
            "low": parse_float(fields[34]) if len(fields) > 34 else None,
        }
    return out


@dataclass
class MinuteBar:
    ymdhm: str
    session_date: str
    hhmm: str
    o: float | None
    h: float | None
    l: float | None
    c: float | None
    volume: float | None

    @property
    def hhmm_i(self) -> int | None:
        return hhmm_int(self.hhmm)


def parse_m1_node(payload: dict[str, Any], code: str) -> list[MinuteBar]:
    data = payload.get("data") or {}
    key = symbol(code)
    node = data.get(key) or (next(iter(data.values())) if data else None)
    if not isinstance(node, dict):
        return []
    rows = node.get("m1") or []
    bars: list[MinuteBar] = []
    for row in rows:
        if not row or len(row) < 5:
            continue
        ymdhm = str(row[0])
        session_date = ymdhm[:8]
        hhmm = ymdhm[8:12] if len(ymdhm) >= 12 else ""
        o, cl, h, l = parse_float(row[1]), parse_float(row[2]), parse_float(row[3]), parse_float(row[4])
        vol = parse_float(row[5]) if len(row) > 5 else None
        if cl is None:
            continue
        bars.append(MinuteBar(ymdhm, session_date, hhmm, o, h, l, cl, vol))
    bars.sort(key=lambda b: b.ymdhm)
    return bars


@dataclass
class TimelinePt:
    session_date: str
    hhmm: str
    price: float
    volume: float | None
    amount: float | None

    @property
    def hhmm_i(self) -> int | None:
        return hhmm_int(self.hhmm)


def parse_minute_node(payload: dict[str, Any], code: str) -> tuple[str, list[TimelinePt]]:
    data = payload.get("data") or {}
    key = symbol(code)
    node = data.get(key) or (next(iter(data.values())) if data else None)
    if not isinstance(node, dict):
        return "", []
    inner = node.get("data") if isinstance(node.get("data"), dict) else node
    session_date = str(inner.get("date") or "")
    rows = inner.get("data") or []
    pts: list[TimelinePt] = []
    for row in rows:
        if isinstance(row, str):
            parts = row.split()
        elif isinstance(row, (list, tuple)):
            parts = [str(x) for x in row]
        else:
            continue
        if len(parts) < 2:
            continue
        hhmm = "".join(ch for ch in parts[0] if ch.isdigit()).zfill(4)[-4:]
        px = parse_float(parts[1])
        if px is None:
            continue
        vol = parse_float(parts[2]) if len(parts) > 2 else None
        amt = parse_float(parts[3]) if len(parts) > 3 else None
        pts.append(TimelinePt(session_date, hhmm, px, vol, amt))
    pts.sort(key=lambda p: p.hhmm)
    return session_date, pts


def parse_day_closes(payload: dict[str, Any], code: str) -> list[tuple[str, float]]:
    data = payload.get("data") or {}
    key = symbol(code)
    node = data.get(key) or (next(iter(data.values())) if data else None)
    if not isinstance(node, dict):
        return []
    rows = node.get("qfqday") or node.get("day") or []
    out: list[tuple[str, float]] = []
    for row in rows:
        if not row or len(row) < 3:
            continue
        d = str(row[0])[:10]
        cl = parse_float(row[2])
        if cl is None:
            continue
        out.append((d, cl))
    return out


def keep_session_bars(bars: list[MinuteBar], session_date: str) -> list[MinuteBar]:
    """mkline 窗口常带上一日，只留会话日（缺省取样本内最大日）。"""
    if not bars:
        return []
    sid = session_date or max(b.session_date for b in bars)
    return [b for b in bars if b.session_date == sid]


def filter_le_1430_bars(bars: list[MinuteBar]) -> list[MinuteBar]:
    kept: list[MinuteBar] = []
    for b in bars:
        i = b.hhmm_i
        if i is None or i <= 1430:
            kept.append(b)
    return kept


def filter_le_1430_pts(pts: list[TimelinePt]) -> list[TimelinePt]:
    kept: list[TimelinePt] = []
    for p in pts:
        i = p.hhmm_i
        if i is None or i <= 1430:
            kept.append(p)
    return kept


def rel_diff(a: float | None, b: float | None) -> float | None:
    if a is None or b is None or a <= 0 or b <= 0:
        return None
    return abs(a - b) / b


def yellow_spread(*pairs: tuple[float | None, float | None]) -> bool:
    for a, b in pairs:
        d = rel_diff(a, b)
        if d is not None and d > YELLOW_PCT:
            return True
    return False


def beijing_now(now: datetime | None = None) -> datetime:
    if now is None:
        return datetime.now(CST)
    if now.tzinfo is None:
        return now.replace(tzinfo=CST)
    return now.astimezone(CST)


def in_a_share_session(now: datetime | None = None) -> bool:
    """连续竞价（含午休，日期红判仍用）；不含集合竞价前。"""
    t = beijing_now(now)
    if t.weekday() >= 5:
        return False
    hhmm = t.hour * 100 + t.minute
    return 930 <= hhmm <= 1500


def in_lunch_break(now: datetime | None = None) -> bool:
    t = beijing_now(now)
    hhmm = t.hour * 100 + t.minute
    return 1130 <= hhmm < 1300


def classify_session(
    session_date: str,
    now: datetime | None = None,
    last_hhmm: str = "",
) -> tuple[str, str]:
    """返回 (replay|live|stale|unknown, 说明)。休市吐最近交易日须自判。"""
    t = beijing_now(now)
    today = t.strftime("%Y%m%d")
    if not session_date:
        return "unknown", "无会话日期"
    if session_date == today:
        if in_a_share_session(t) and not in_lunch_break(t) and last_hhmm:
            last_i = hhmm_int(last_hhmm)
            if last_i is not None:
                now_i = t.hour * 100 + t.minute
                lag = hhmm_to_minutes(now_i) - hhmm_to_minutes(last_i)
                if lag >= 6 and now_i <= 1500:
                    return "stale", f"会话日={session_date} 但最新点 {last_hhmm} 落后于 {t.strftime('%H:%M')}"
        return "live", f"会话日={session_date} 与北京今日一致"
    if in_a_share_session(t) and not in_lunch_break(t) and t.hour * 100 + t.minute >= 931:
        return "stale", f"交易时段内会话日={session_date} ≠ 今日 {today}（疑似断档/回放当今日）"
    return "replay", f"休市或未开盘回放最近交易日 {session_date}（今日 {today}）"


def traffic_light(
    *,
    ok_http: bool,
    price: float | None,
    n_m1: int,
    session_kind: str,
    spread_yellow: bool,
    n_near: int,
    in_session: bool,
) -> tuple[str, str]:
    if not ok_http or price is None:
        return "红", "HTTP 失败或 qt 无有效价 — 旁路不可用"
    if session_kind == "stale" and in_session:
        return "红", "交易时段会话日/最新点异常 — 不可当今日实时"
    if n_m1 <= 0 and n_near <= 0 and in_session and session_kind == "live":
        return "红", "交易时段 1m 与分时皆空"
    reasons: list[str] = []
    if session_kind == "replay":
        reasons.append("休市回放（可对照昨收，不当今日实时）")
    if spread_yellow:
        reasons.append(f"对照价差 >{YELLOW_PCT:.1%}")
    if in_session and session_kind == "live" and n_m1 <= 0:
        reasons.append("当日 1m 空包（分时仍有；常见于 QDII 盘初 mkline 滞后）")
    if in_session and session_kind == "live" and n_near < 5:
        reasons.append("近端分时不足 5 点")
    if reasons:
        return "黄", "；".join(reasons)
    return "绿", "qt/1m/分时可用且对照≤0.3%"


def load_ref_closes(ref_csv: Path | None, ref_dir: Path | None) -> dict[str, dict[str, Any]]:
    """仓库已有价源：ref_csv 或 research_cache/day/{code}.json 末根。"""
    out: dict[str, dict[str, Any]] = {}
    dirs: list[Path] = []
    if ref_dir is not None:
        dirs.append(ref_dir)
    else:
        dirs.extend(p for p in AUTO_REF_DIRS if p.is_dir())

    for d in dirs:
        for fp in sorted(d.glob("*.json")):
            try:
                rec = json.loads(fp.read_text(encoding="utf-8"))
            except (OSError, json.JSONDecodeError):
                continue
            code = str(rec.get("code") or fp.stem)
            bars = rec.get("bars") or []
            if not bars:
                continue
            last = bars[-1]
            cl = parse_float(last.get("c") if isinstance(last, dict) else None)
            dt = str(last.get("date") if isinstance(last, dict) else "")[:10]
            if cl is None:
                continue
            out[code] = {
                "date": dt,
                "close": cl,
                "source": f"repo_day_json:{fp.as_posix()}",
            }

    if ref_csv and ref_csv.is_file():
        with ref_csv.open(encoding="utf-8", newline="") as f:
            for row in csv.DictReader(f):
                code = (row.get("code") or "").strip()
                cl = parse_float(row.get("close") or row.get("c") or row.get("price"))
                if not code or cl is None:
                    continue
                out[code] = {
                    "date": (row.get("date") or "").strip()[:10],
                    "close": cl,
                    "source": f"ref_csv:{ref_csv.name}",
                }
    return out


# ---------------------------------------------------------------------------
# HTTP
# ---------------------------------------------------------------------------

def http_get(url: str, timeout: int = 20) -> bytes:
    req = urllib.request.Request(url, headers=UA)
    with urllib.request.urlopen(req, timeout=timeout, context=CTX) as resp:
        return resp.read()


def http_get_retry(url: str, tries: int = 3) -> bytes:
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


def fetch_qt(codes: list[str]) -> dict[str, dict[str, Any]]:
    out: dict[str, dict[str, Any]] = {}
    for i in range(0, len(codes), 50):
        batch = codes[i : i + 50]
        q = ",".join(symbol(c) for c in batch)
        raw = http_get_retry(QT_URL.format(q=q)).decode("gbk", "replace")
        out.update(parse_qt_body(raw))
        time.sleep(0.12)
    return out


def fetch_first_json(urls: tuple[str, ...]) -> dict[str, Any]:
    last: Exception | None = None
    for url in urls:
        try:
            return json.loads(http_get_retry(url))
        except Exception as e:
            last = e
            continue
    raise last or RuntimeError("no url")


def fetch_m1(code: str, n: int) -> list[MinuteBar]:
    payload = fetch_first_json(tuple(u.format(sym=symbol(code), n=n) for u in MKLINE_URLS))
    return parse_m1_node(payload, code)


def fetch_timeline(code: str) -> tuple[str, list[TimelinePt]]:
    payload = fetch_first_json(tuple(u.format(sym=symbol(code)) for u in MINUTE_URLS))
    return parse_minute_node(payload, code)


def fetch_day(code: str) -> list[tuple[str, float]]:
    payload = fetch_first_json(tuple(u.format(sym=symbol(code)) for u in DAY_URLS))
    return parse_day_closes(payload, code)


# ---------------------------------------------------------------------------
# 名单 / 写出
# ---------------------------------------------------------------------------

def load_codes(path: Path, extra: list[str]) -> list[tuple[str, str, str]]:
    rows: list[tuple[str, str, str]] = []
    seen: set[str] = set()
    if path.is_file():
        with path.open(encoding="utf-8", newline="") as f:
            sample = f.read(2048)
            f.seek(0)
            if "," in sample.splitlines()[0]:
                for rec in csv.DictReader(f):
                    code = (rec.get("code") or rec.get("codes") or "").strip()
                    if not code or not code[0].isdigit():
                        continue
                    if code in seen:
                        continue
                    seen.add(code)
                    rows.append((code, (rec.get("name") or "").strip(), (rec.get("family") or "").strip()))
            else:
                for line in f:
                    code = line.strip().split()[0] if line.strip() else ""
                    if not code or code.startswith("#") or not code[0].isdigit():
                        continue
                    if code in seen:
                        continue
                    seen.add(code)
                    rows.append((code, "", ""))
    for c in extra:
        for part in c.split(","):
            code = part.strip()
            if not code or code in seen:
                continue
            seen.add(code)
            rows.append((code, "", ""))
    return rows


@dataclass
class CodeResult:
    code: str
    name: str
    family: str
    qt: dict[str, Any] = field(default_factory=dict)
    m1: list[MinuteBar] = field(default_factory=list)
    m1_cut: list[MinuteBar] = field(default_factory=list)
    timeline: list[TimelinePt] = field(default_factory=list)
    timeline_cut: list[TimelinePt] = field(default_factory=list)
    timeline_date: str = ""
    tencent_days: list[tuple[str, float]] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)
    flag: str = ""
    flag_reason: str = ""
    session_kind: str = ""
    session_note: str = ""
    diffs: dict[str, float | None] = field(default_factory=dict)


def last_completed_day_close(
    days: list[tuple[str, float]], session_date: str, today_ymd: str
) -> tuple[str, float] | None:
    """日线末根若是今日未完成 K，退一格。"""
    if not days:
        return None
    d, cl = days[-1]
    compact = d.replace("-", "")
    if compact == today_ymd or compact == session_date:
        if len(days) >= 2:
            return days[-2]
        return None
    return days[-1]


def run_probe(
    codes: list[tuple[str, str, str]],
    *,
    m1_n: int,
    near_n: int,
    cutoff_1430: bool,
    refs: dict[str, dict[str, Any]],
    now: datetime | None = None,
) -> list[CodeResult]:
    now = beijing_now(now)
    today = now.strftime("%Y%m%d")
    in_sess = in_a_share_session(now)
    code_list = [c for c, _, _ in codes]
    qt_map: dict[str, dict[str, Any]] = {}
    try:
        qt_map = fetch_qt(code_list)
    except Exception as e:
        # 全批次失败：每只记红，仍尝试单只分钟以区分「qt 挂了但 1m 活着」
        qt_err = str(e)
        for code, name, family in codes:
            qt_map[code] = {"_err": qt_err, "name": name}

    results: list[CodeResult] = []
    for code, name, family in codes:
        rec = CodeResult(code=code, name=name, family=family)
        rec.qt = qt_map.get(code) or {}
        if rec.qt.get("name") and not rec.name:
            rec.name = str(rec.qt["name"])
        if rec.qt.get("_err"):
            rec.errors.append(f"qt:{rec.qt['_err']}")
        try:
            rec.m1 = fetch_m1(code, m1_n)
        except Exception as e:
            rec.errors.append(f"m1:{e}")
        time.sleep(0.12)
        try:
            rec.timeline_date, rec.timeline = fetch_timeline(code)
        except Exception as e:
            rec.errors.append(f"minute:{e}")
        time.sleep(0.12)
        try:
            rec.tencent_days = fetch_day(code)
        except Exception as e:
            rec.errors.append(f"day:{e}")
        time.sleep(0.08)

        session_date = (
            str(rec.qt.get("session_date") or "")
            or rec.timeline_date
            or (rec.m1[-1].session_date if rec.m1 else "")
        )
        rec.m1 = keep_session_bars(rec.m1, session_date)
        rec.m1_cut = filter_le_1430_bars(rec.m1) if cutoff_1430 else list(rec.m1)
        rec.timeline_cut = filter_le_1430_pts(rec.timeline) if cutoff_1430 else list(rec.timeline)
        if near_n > 0:
            rec.timeline_cut = rec.timeline_cut[-near_n:]
        last_hhmm = ""
        if rec.timeline:
            last_hhmm = rec.timeline[-1].hhmm
        elif rec.m1:
            last_hhmm = rec.m1[-1].hhmm
        rec.session_kind, rec.session_note = classify_session(session_date, now, last_hhmm)

        qt_px = rec.qt.get("price") if isinstance(rec.qt.get("price"), (int, float)) else None
        m1_last = rec.m1_cut[-1].c if rec.m1_cut else None
        tl_last = rec.timeline_cut[-1].price if rec.timeline_cut else None
        rec.diffs["qt_vs_m1"] = rel_diff(qt_px, m1_last)
        rec.diffs["qt_vs_timeline"] = rel_diff(qt_px, tl_last)
        rec.diffs["m1_vs_timeline"] = rel_diff(m1_last, tl_last)

        prev = rec.qt.get("prev_close") if isinstance(rec.qt.get("prev_close"), (int, float)) else None
        day_prev = last_completed_day_close(rec.tencent_days, session_date, today)
        if day_prev and prev:
            rec.diffs["qt_prev_vs_tencent_day"] = rel_diff(prev, day_prev[1])
        else:
            rec.diffs["qt_prev_vs_tencent_day"] = None

        ref = refs.get(code)
        rec.diffs["qt_vs_repo"] = None
        rec.diffs["repo_date"] = None  # type: ignore[assignment]
        if ref:
            rec.diffs["repo_date"] = ref.get("date")  # type: ignore[assignment]
            ref_d = str(ref.get("date") or "").replace("-", "")
            # 同日才比现价；否则只在 ref 日 == 腾讯昨收日时比 prev_close
            if ref_d and session_date and ref_d == session_date:
                rec.diffs["qt_vs_repo"] = rel_diff(qt_px, float(ref["close"]))
            elif prev is not None:
                # 日期对不上：标到 diffs 但不强制黄，除非调用方把 stale cache 当同日
                rec.diffs["qt_vs_repo"] = None
                rec.diffs["repo_skipped"] = f"仓库价源日 {ref.get('date')} ≠ 会话日 {session_date}"  # type: ignore[assignment]

        spread = yellow_spread(
            (qt_px, m1_last),
            (qt_px, tl_last),
            (m1_last, tl_last),
            (prev, day_prev[1] if day_prev else None),
            (qt_px, float(ref["close"])) if ref and rec.diffs.get("qt_vs_repo") is not None else (None, None),
        )
        ok_http = "qt:" not in "".join(rec.errors) and qt_px is not None
        rec.flag, rec.flag_reason = traffic_light(
            ok_http=ok_http,
            price=qt_px,
            n_m1=len(rec.m1_cut),
            session_kind=rec.session_kind,
            spread_yellow=spread,
            n_near=len(rec.timeline_cut),
            in_session=in_sess,
        )
        if rec.errors and rec.flag == "绿":
            rec.flag, rec.flag_reason = "黄", "部分端点失败：" + "；".join(rec.errors)
        results.append(rec)
    return results


def write_csvs(results: list[CodeResult], out_dir: Path, refs: dict[str, dict[str, Any]]) -> None:
    out_dir.mkdir(parents=True, exist_ok=True)

    snap_fp = out_dir / "snapshot.csv"
    with snap_fp.open("w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(
            f,
            fieldnames=[
                "code",
                "name",
                "family",
                "flag",
                "flag_reason",
                "session_kind",
                "session_note",
                "qt_price",
                "qt_prev_close",
                "qt_datetime",
                "m1_last",
                "m1_n",
                "m1_n_le1430",
                "timeline_last",
                "timeline_n",
                "timeline_n_near",
                "timeline_date",
                "diff_qt_m1",
                "diff_qt_timeline",
                "diff_m1_timeline",
                "diff_qt_prev_tencent_day",
                "diff_qt_repo",
                "repo_source",
                "repo_date",
                "errors",
            ],
        )
        w.writeheader()
        for r in results:
            ref = refs.get(r.code) or {}
            w.writerow(
                {
                    "code": r.code,
                    "name": r.name,
                    "family": r.family,
                    "flag": r.flag,
                    "flag_reason": r.flag_reason,
                    "session_kind": r.session_kind,
                    "session_note": r.session_note,
                    "qt_price": r.qt.get("price"),
                    "qt_prev_close": r.qt.get("prev_close"),
                    "qt_datetime": r.qt.get("datetime"),
                    "m1_last": r.m1_cut[-1].c if r.m1_cut else "",
                    "m1_n": len(r.m1),
                    "m1_n_le1430": len(r.m1_cut),
                    "timeline_last": r.timeline_cut[-1].price if r.timeline_cut else "",
                    "timeline_n": len(r.timeline),
                    "timeline_n_near": len(r.timeline_cut),
                    "timeline_date": r.timeline_date,
                    "diff_qt_m1": _pct(r.diffs.get("qt_vs_m1")),
                    "diff_qt_timeline": _pct(r.diffs.get("qt_vs_timeline")),
                    "diff_m1_timeline": _pct(r.diffs.get("m1_vs_timeline")),
                    "diff_qt_prev_tencent_day": _pct(r.diffs.get("qt_prev_vs_tencent_day")),
                    "diff_qt_repo": _pct(r.diffs.get("qt_vs_repo")),
                    "repo_source": ref.get("source", ""),
                    "repo_date": ref.get("date", ""),
                    "errors": "|".join(r.errors),
                }
            )

    m1_fp = out_dir / "minutes_1m.csv"
    with m1_fp.open("w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(
            f,
            fieldnames=["code", "ymdhm", "session_date", "hhmm", "open", "high", "low", "close", "volume", "le_1430"],
        )
        w.writeheader()
        for r in results:
            cut_set = {b.ymdhm for b in r.m1_cut}
            for b in r.m1:
                w.writerow(
                    {
                        "code": r.code,
                        "ymdhm": b.ymdhm,
                        "session_date": b.session_date,
                        "hhmm": b.hhmm,
                        "open": b.o,
                        "high": b.h,
                        "low": b.l,
                        "close": b.c,
                        "volume": b.volume,
                        "le_1430": int(b.ymdhm in cut_set),
                    }
                )

    tl_fp = out_dir / "timeline_near.csv"
    with tl_fp.open("w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(
            f,
            fieldnames=["code", "session_date", "hhmm", "price", "volume", "amount"],
        )
        w.writeheader()
        for r in results:
            for p in r.timeline_cut:
                w.writerow(
                    {
                        "code": r.code,
                        "session_date": p.session_date,
                        "hhmm": p.hhmm,
                        "price": p.price,
                        "volume": p.volume,
                        "amount": p.amount,
                    }
                )


def _pct(v: Any) -> str:
    if v is None or isinstance(v, str):
        return ""
    try:
        return f"{float(v):.4%}"
    except (TypeError, ValueError):
        return ""


def _md_flag(flag: str) -> str:
    if flag == "黄":
        return '<span style="background:#fff3cd;padding:0 4px">黄</span>'
    if flag == "红":
        return '<span style="background:#f8d7da;padding:0 4px">红</span>'
    if flag == "绿":
        return '<span style="background:#d4edda;padding:0 4px">绿</span>'
    return flag


def write_summary(
    results: list[CodeResult],
    out_dir: Path,
    *,
    refs: dict[str, dict[str, Any]],
    now: datetime,
    cutoff_1430: bool,
    near_n: int,
) -> None:
    n = len(results)
    counts = {"红": 0, "黄": 0, "绿": 0}
    for r in results:
        counts[r.flag] = counts.get(r.flag, 0) + 1
    kinds = {}
    for r in results:
        kinds[r.session_kind] = kinds.get(r.session_kind, 0) + 1

    repo_note = (
        f"已挂载 {len(refs)} 只仓库价源"
        if refs
        else "未挂载仓库日线缓存（同日才比现价；扩展见 README）"
    )

    lines = [
        "# 腾讯公开分钟对照摘要",
        "",
        f"- 探测时刻（北京）：`{now.strftime('%Y-%m-%d %H:%M:%S %z')}`",
        f"- 代码数：{n}；灯号 绿 {counts.get('绿', 0)} / 黄 {counts.get('黄', 0)} / 红 {counts.get('红', 0)}",
        f"- 会话：{', '.join(f'{k}={v}' for k, v in sorted(kinds.items())) or '无'}",
        f"- 14:30 过滤：{'开' if cutoff_1430 else '关'}；近端分时保留末 {near_n} 点",
        f"- 仓库价源：{repo_note}",
        f"- 黄线：对照价差 > {YELLOW_PCT:.1%}（qt vs 1m vs 分时；同日仓库价；qt 昨收 vs 腾讯日线完整 K）",
        "- 硬闸：盘中旁路 ≠ 回测权威；不替 cjpy AUM；不碰 LIVE / strategy_exec；无 SLA",
        "",
        "| 灯 | 代码 | 名称 | 会话 | qt | 1m末 | 分时末 | qt-1m | qt-分时 | 仓库 | 说明 |",
        "|---|---|---|---|---:|---:|---:|---:|---:|---:|---|",
    ]
    for r in results:
        qt_px = r.qt.get("price")
        m1_last = r.m1_cut[-1].c if r.m1_cut else ""
        tl_last = r.timeline_cut[-1].price if r.timeline_cut else ""
        repo_d = _pct(r.diffs.get("qt_vs_repo")) or (str(r.diffs.get("repo_skipped") or "")[:18] or "—")
        lines.append(
            "| {flag} | `{code}` | {name} | {sk} | {qt} | {m1} | {tl} | {d1} | {d2} | {repo} | {why} |".format(
                flag=_md_flag(r.flag),
                code=r.code,
                name=(r.name or "—").replace("|", "/"),
                sk=r.session_kind or "—",
                qt="" if qt_px is None else qt_px,
                m1=m1_last,
                tl=tl_last,
                d1=_pct(r.diffs.get("qt_vs_m1")) or "—",
                d2=_pct(r.diffs.get("qt_vs_timeline")) or "—",
                repo=repo_d,
                why=(r.flag_reason or "").replace("|", "/"),
            )
        )
    lines += [
        "",
        "## 断供旁路怎么读",
        "",
        "- **红**：qt 无价 / 交易时段会话日错或最新点停滞 / 盘中 1m 与分时皆空 → pytdx 断供时腾讯也不可用。",
        "- **黄**：休市回放、对照 >0.3%、仅 1m 空、近端过稀、部分端点失败 → 可交叉看，不当执行依据。",
        "- **绿**：仅表示本探活窗口腾讯公开口可对照，**不是**回测或 LIVE 授权。",
        "",
        "## 产出",
        "",
        "- `snapshot.csv` — 每只一只一行对照",
        "- `minutes_1m.csv` — 当日 1m（含 `le_1430`）",
        "- `timeline_near.csv` — 近端分时（已按 14:30 过滤）",
        "- `summary.json` — 机读摘要",
        "",
    ]
    (out_dir / "summary.md").write_text("\n".join(lines) + "\n", encoding="utf-8")

    payload = {
        "generated_at_cst": now.strftime("%Y-%m-%d %H:%M:%S %z"),
        "n": n,
        "flags": counts,
        "session_kinds": kinds,
        "cutoff_1430": cutoff_1430,
        "near_n": near_n,
        "yellow_pct": YELLOW_PCT,
        "repo_ref_n": len(refs),
        "hard_gates": [
            "tencent_is_live_bypass_not_backtest_authority",
            "not_a_cjpy_aum_replacement",
            "do_not_touch_LIVE_or_strategy_exec",
            "no_comein_cicc_alphapai_eastmoney_unreviewed_qmt",
        ],
        "rows": [
            {
                "code": r.code,
                "name": r.name,
                "flag": r.flag,
                "session_kind": r.session_kind,
                "qt_price": r.qt.get("price"),
                "diffs": {k: v for k, v in r.diffs.items() if not isinstance(v, str) or k.endswith("skipped")},
                "errors": r.errors,
            }
            for r in results
        ],
    }
    (out_dir / "summary.json").write_text(
        json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    p = argparse.ArgumentParser(description="腾讯公开分钟对照/探活（research-only）")
    p.add_argument("--codes-file", type=Path, default=HERE / "universe_sample.csv")
    p.add_argument("--codes", default="", help="逗号分隔代码，叠加到 --codes-file")
    p.add_argument("--out-dir", type=Path, default=HERE / "sample_out")
    p.add_argument("--m1-n", type=int, default=320, help="mkline 根数，全日约 240")
    p.add_argument("--near-minutes", type=int, default=30, help="近端分时保留末 N 点")
    p.add_argument("--no-cutoff-1430", action="store_true", help="关闭 time<=14:30 过滤")
    p.add_argument("--ref-csv", type=Path, default=None, help="仓库对照 CSV：code,date,close")
    p.add_argument("--ref-dir", type=Path, default=None, help="research_cache/day 目录")
    return p.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    codes = load_codes(args.codes_file, [args.codes] if args.codes else [])
    if not codes:
        raise SystemExit("名单为空：给 --codes-file 或 --codes")
    refs = load_ref_closes(args.ref_csv, args.ref_dir)
    now = beijing_now()
    results = run_probe(
        codes,
        m1_n=args.m1_n,
        near_n=args.near_minutes,
        cutoff_1430=not args.no_cutoff_1430,
        refs=refs,
        now=now,
    )
    args.out_dir.mkdir(parents=True, exist_ok=True)
    write_csvs(results, args.out_dir, refs)
    write_summary(
        results,
        args.out_dir,
        refs=refs,
        now=now,
        cutoff_1430=not args.no_cutoff_1430,
        near_n=args.near_minutes,
    )
    n_red = sum(1 for r in results if r.flag == "红")
    n_yel = sum(1 for r in results if r.flag == "黄")
    print(
        f"wrote {args.out_dir}  n={len(results)} 绿={sum(1 for r in results if r.flag=='绿')} "
        f"黄={n_yel} 红={n_red}  refs={len(refs)}"
    )
    return 0 if n_red == 0 else 2


if __name__ == "__main__":
    raise SystemExit(main())
