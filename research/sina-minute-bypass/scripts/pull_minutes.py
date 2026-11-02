#!/usr/bin/env python3
"""批量拉新浪 1m/5m，与腾讯互校，输出 CSV + 摘要。研究 only，禁 LIVE。"""

from __future__ import annotations

import argparse
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from sina_bypass.akshare_client import fetch_akshare_minute
from sina_bypass.calendar import infer_session, now_shanghai
from sina_bypass.compare import compare_symbol
from sina_bypass.report import now_stamp, render_summary, write_bars_csv, write_compare_csv, write_summary
from sina_bypass.sina_client import FetchResult, fetch_money_finance, fetch_sina_cn
from sina_bypass.tencent_client import fetch_tencent_mkline, load_tencent_csv
from sina_bypass.universe import load_universe


def _parse_scales(raw: str) -> list[int]:
    out = []
    for part in raw.split(","):
        part = part.strip().lower().replace("m", "")
        if not part:
            continue
        val = int(part)
        if val not in (1, 5, 15, 30, 60):
            raise SystemExit(f"不支持周期 {val}")
        out.append(val)
    if not out:
        raise SystemExit("scales 为空")
    return out


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description="新浪/AKShare 分钟旁路对照（研究轨）")
    p.add_argument("--scales", default="1,5", help="逗号分隔，默认 1,5")
    p.add_argument("--datalen", type=int, default=240)
    p.add_argument("--sleep", type=float, default=0.25)
    p.add_argument("--out", type=Path, default=ROOT / "out")
    p.add_argument("--universe", type=Path, default=None)
    p.add_argument("--codes", default="", help="逗号分隔，覆盖 universe")
    p.add_argument("--limit", type=int, default=0, help="只跑前 N 只，调试用")
    p.add_argument("--tencent-csv", type=Path, default=None, help="腾讯旁路已落 CSV，优先于现场拉腾讯")
    p.add_argument("--skip-akshare", action="store_true")
    p.add_argument("--skip-money-finance", action="store_true")
    p.add_argument("--probe-money-finance-n", type=int, default=2, help="只对前 N 只探测 money.finance")
    args = p.parse_args(argv)

    scales = _parse_scales(args.scales)
    if args.codes:
        etfs = [{"code": c.strip(), "name": c.strip()} for c in args.codes.split(",") if c.strip()]
    else:
        etfs = load_universe(args.universe)
    if args.limit:
        etfs = etfs[: args.limit]
    if not etfs:
        raise SystemExit("无标的")

    tencent_csv: dict[tuple[str, int], list] = {}
    if args.tencent_csv:
        for scale in scales:
            for code, bars in load_tencent_csv(str(args.tencent_csv), scale=scale).items():
                tencent_csv[(code, scale)] = bars

    sina_all = []
    tec_all = []
    ak_all = []
    mf_notes = []
    pairs: list[tuple[dict, int, FetchResult, FetchResult]] = []

    for i, etf in enumerate(etfs):
        code = etf["code"]
        for scale in scales:
            sina = fetch_sina_cn(code, scale=scale, datalen=args.datalen)
            if sina.ok:
                sina_all.extend(sina.bars)
            if (code, scale) in tencent_csv:
                tec = FetchResult(
                    "tencent_csv",
                    code,
                    scale,
                    True,
                    bars=tencent_csv[(code, scale)],
                    note=str(args.tencent_csv),
                )
            else:
                tec = fetch_tencent_mkline(code, scale=scale, datalen=args.datalen)
            if tec.ok:
                tec_all.extend(tec.bars)
            if not args.skip_akshare:
                ak = fetch_akshare_minute(code, scale=scale)
                if ak.ok:
                    ak_all.extend(ak.bars)
            pairs.append((etf, scale, sina, tec))
            time.sleep(args.sleep)
        if not args.skip_money_finance and i < args.probe_money_finance_n:
            for scale in scales:
                mf = fetch_money_finance(code, scale=scale, datalen=min(args.datalen, 8))
                mf_notes.append(
                    f"{code} {scale}m → ok={mf.ok} note={mf.note or '-'} err={mf.error or '-'} n={len(mf.bars)}"
                )
                time.sleep(args.sleep)

    session = infer_session(now_shanghai(), (sina.bars for _, _, sina, _ in pairs if sina.bars))
    compares = [
        compare_symbol(sina, tec, name=etf.get("name") or etf["code"], session=session.get("session") or "open")
        for etf, scale, sina, tec in pairs
    ]

    out = args.out
    bars_dir = out / "bars"
    write_bars_csv(bars_dir / "sina_cn.csv", sina_all)
    write_bars_csv(bars_dir / "tencent.csv", tec_all)
    if ak_all:
        write_bars_csv(bars_dir / "akshare.csv", ak_all)
    write_compare_csv(out / "compare.csv", compares)
    generated = now_stamp()
    md = render_summary(
        session=session,
        compares=compares,
        scales=scales,
        money_finance_notes=mf_notes,
        generated_at=generated,
    )
    payload = {
        "generated_at": generated,
        "session": session,
        "n_etf": len(etfs),
        "scales": scales,
        "flags": {
            "GREEN": sum(1 for c in compares if c.flag == "GREEN"),
            "YELLOW": sum(1 for c in compares if c.flag == "YELLOW"),
            "RED": sum(1 for c in compares if c.flag == "RED"),
        },
        "money_finance": mf_notes,
        "research_only": True,
        "live_forbidden": True,
    }
    write_summary(out / "summary.md", md, payload)
    print(md)
    print(f"wrote {out / 'summary.md'}", file=sys.stderr)
    return 0 if payload["flags"]["RED"] == 0 else 2


if __name__ == "__main__":
    raise SystemExit(main())
