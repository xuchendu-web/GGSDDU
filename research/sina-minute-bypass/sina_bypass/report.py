"""CSV + 摘要。"""

from __future__ import annotations

import csv
import json
from collections import Counter
from datetime import datetime
from pathlib import Path
from typing import Iterable

from .bars import Bar
from .compare import CSV_COLUMNS, CompareResult


def write_bars_csv(path: Path, bars: Iterable[Bar]) -> int:
    path.parent.mkdir(parents=True, exist_ok=True)
    rows = [b.as_row() for b in bars]
    with path.open("w", encoding="utf-8", newline="") as fh:
        writer = csv.DictWriter(fh, fieldnames=CSV_COLUMNS)
        writer.writeheader()
        for row in rows:
            writer.writerow({k: row.get(k, "") for k in CSV_COLUMNS})
    return len(rows)


def write_compare_csv(path: Path, rows: Iterable[CompareResult]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    items = [r.as_row() for r in rows]
    fields = list(items[0].keys()) if items else ["code", "flag"]
    with path.open("w", encoding="utf-8", newline="") as fh:
        writer = csv.DictWriter(fh, fieldnames=fields)
        writer.writeheader()
        writer.writerows(items)


def render_summary(
    *,
    session: dict,
    compares: list[CompareResult],
    scales: list[int],
    money_finance_notes: list[str],
    generated_at: str,
) -> str:
    counts = Counter(c.flag for c in compares)
    yellows = [c for c in compares if c.flag == "YELLOW"]
    reds = [c for c in compares if c.flag == "RED"]
    lines = [
        "# 新浪分钟旁路对照摘要",
        "",
        f"- 生成：{generated_at}",
        f"- 会话：`{session.get('session')}` / 时钟 `{session.get('clock_state')}` / {session.get('clock')}",
        f"- 自判交易日：`{session.get('trading_day')}`（今日 {session.get('today')}；{session.get('note')}）",
        f"- 周期：{', '.join(f'{s}m' for s in scales)}",
        f"- 对照条数：{len(compares)}（GREEN {counts.get('GREEN', 0)} / YELLOW {counts.get('YELLOW', 0)} / RED {counts.get('RED', 0)}）",
        "",
        "## 红黄判据",
        "",
        "- GREEN：两边有重叠分钟，收盘价相对偏差 ≤ 0.3%，OHLC 合法。",
        "- YELLOW：重叠分钟上 `|新浪收-腾讯收|/腾讯收 > 0.3%`。",
        "- RED：新浪失败/空表、开盘时段腾讯失败、无重叠、OHLC 非法、开盘时段最后一根相差 >3 分钟。",
        "- 休市自判为 `inferred_closed` / `closed_prior` 时，缺今日分钟不升 RED。",
        "",
        "## money.finance",
        "",
    ]
    if money_finance_notes:
        lines.extend(f"- {n}" for n in money_finance_notes)
    else:
        lines.append("- 未探测")
    lines += ["", "## 标黄 / 标红", ""]
    if not yellows and not reds:
        lines.append("无。")
    else:
        lines.append("| flag | code | name | scale | last_ts | sina | tencent | last% | max% | reasons |")
        lines.append("|---|---|---|---:|---|---:|---:|---:|---:|---|")
        for c in reds + yellows:
            last_pct = "" if c.last_abs_pct is None else f"{c.last_abs_pct:.3%}"
            max_pct = "" if c.max_abs_pct is None else f"{c.max_abs_pct:.3%}"
            lines.append(
                f"| {c.flag} | {c.code} | {c.name} | {c.scale} | {c.last_ts or ''} | "
                f"{c.sina_close if c.sina_close is not None else ''} | "
                f"{c.tencent_close if c.tencent_close is not None else ''} | "
                f"{last_pct} | {max_pct} | {';'.join(c.reasons)} |"
            )
    lines += ["", "## 全样本最后一根", ""]
    lines.append("| flag | code | name | scale | last_ts | sina | tencent | last% | overlap |")
    lines.append("|---|---|---|---:|---|---:|---:|---:|---:|")
    for c in compares:
        last_pct = "" if c.last_abs_pct is None else f"{c.last_abs_pct:.3%}"
        lines.append(
            f"| {c.flag} | {c.code} | {c.name} | {c.scale} | {c.last_ts or ''} | "
            f"{c.sina_close if c.sina_close is not None else ''} | "
            f"{c.tencent_close if c.tencent_close is not None else ''} | "
            f"{last_pct} | {c.overlap} |"
        )
    lines += [
        "",
        "## 禁区",
        "",
        "- 不走进门 / 中金 / Alpha派。",
        "- 不改 `strategy_exec` / LIVE。",
        "- 东财 `*_em` 不当主力。回测日线不当实时权威。无 AUM。",
        "",
    ]
    return "\n".join(lines) + "\n"


def write_summary(path: Path, markdown: str, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(markdown, encoding="utf-8")
    json_path = path.with_suffix(".json")
    json_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def now_stamp() -> str:
    from .calendar import now_shanghai

    return now_shanghai().strftime("%Y-%m-%d %H:%M:%S %Z")
