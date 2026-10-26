#!/usr/bin/env python3
"""Inventory only — no NAV. See COMPOSER.md §2."""

from __future__ import annotations

import csv
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd

from vs_tsmom_lib import (
    ROOT,
    CMD,
    EVAL_END_TS,
    KIT,
    OX,
    PRE2019_CUTOFF,
    RATES,
    WEEKLY_PANEL,
    load_daily_close,
    load_listing_date,
    load_rebalance_fridays,
    resolve_pool_path,
    daily_to_weekly_close,
    local_data_paths,
    name_eligible,
    HERE,
    TASK,
)

OUT_JSON = HERE / "inventory.json"
OUT_NAMES = HERE / "inventory_names.csv"
REPORT = HERE / "REPORT.md"


def main() -> int:
    fail_reasons: list[str] = []
    names_rows: list[dict] = []

    try:
        pool_path = resolve_pool_path()
    except FileNotFoundError:
        fail_reasons.append("research pool CSV missing")
        pool_path = None

    ox_status = "OK"
    cmd_status = "OK"
    rates_status = "SKIP"
    rates_reason = ""
    pre2019_ok = False
    covers_eval_end = False
    drift_flag = False
    honest_from = ""
    honest_to = ""

    if pool_path is not None:
        df = pd.read_csv(pool_path)
        df["code"] = df["code"].astype(str).str.zfill(6)
        aum2 = df[df["aum"] >= 2]
        ox_pool = set(aum2.loc[aum2["l0"] == "海外权益", "code"])
        cmd_pool = set(aum2.loc[aum2["l0"] == "商品", "code"])
        if ox_pool != OX:
            ox_status = "FAIL"
            fail_reasons.append(f"OX set mismatch: pool={sorted(ox_pool)} expected={sorted(OX)}")
        if cmd_pool != CMD:
            cmd_status = "FAIL"
            fail_reasons.append(f"CMD set mismatch: pool={sorted(cmd_pool)} expected={sorted(CMD)}")
        bonds_in_pool = set(aum2["code"]) & RATES
        if bonds_in_pool:
            fail_reasons.append(f"bond codes in research pool: {sorted(bonds_in_pool)}")
            ox_status = "FAIL"
            cmd_status = "FAIL"

    all_codes = sorted(OX | CMD | RATES)
    for code in all_codes:
        daily, src, drift = load_daily_close(code)
        listing = load_listing_date(code)
        listing_proxy = False
        if listing is None and not daily.empty:
            listing = pd.Timestamp(daily.index[0])
            listing_proxy = True
        first_date = str(daily.index[0].date()) if not daily.empty else ""
        last_date = str(daily.index[-1].date()) if not daily.empty else ""
        names_rows.append(
            {
                "code": code,
                "source_path": src,
                "source_ref": src,
                "first_date": first_date,
                "last_date": last_date,
                "n_bars": len(daily),
                "fields": "date,close" if code in RATES and src.endswith(".csv") else "date,c",
                "listing_proxy": listing_proxy,
                "drift_flag": drift,
            }
        )

    # RATES sleeve
    rate_series = {}
    for code in RATES:
        s, _, drift = load_daily_close(code)
        drift_flag = drift_flag or drift
        if not s.empty:
            rate_series[code] = s
    if rate_series:
        honest_from = min(str(s.index[0].date()) for s in rate_series.values())
        honest_to = max(str(s.index[-1].date()) for s in rate_series.values())
        first_ts = min(s.index[0] for s in rate_series.values())
        last_ts = max(s.index[-1] for s in rate_series.values())
        pre2019_ok = first_ts <= PRE2019_CUTOFF and not drift_flag
        covers_eval_end = last_ts >= EVAL_END_TS
        if pre2019_ok and covers_eval_end and not drift_flag:
            rates_status = "OK"
            rates_reason = "honest bond panel covers eval window"
        else:
            rates_status = "SKIP"
            if drift_flag:
                rates_reason = "drift/backward metadata on bond series"
            elif not pre2019_ok:
                rates_reason = f"earliest honest bar {honest_from} after 2019-01-03"
            elif not covers_eval_end:
                rates_reason = f"last honest bar {honest_to} before eval end {EVAL_END_TS.date()}"
            else:
                rates_reason = "rates panel insufficient"
    else:
        rates_status = "SKIP"
        rates_reason = "no bond price files found"

    local_paths = local_data_paths()
    if rates_status != "OK" and any(p["exists"] for p in local_paths):
        rates_reason += "; local mounts present but not queried in this run"

    declared: list[str] = []
    if ox_status == "OK":
        declared.append("OX")
    if cmd_status == "OK":
        declared.append("CMD")
    if rates_status == "OK":
        declared.append("RATES")

    # Weekly calendar
    if not WEEKLY_PANEL.is_file():
        fail_reasons.append(f"missing weekly panel: {WEEKLY_PANEL}")

    # Eligibility smoke: any week n_s>=1 per sleeve
    if not fail_reasons and WEEKLY_PANEL.is_file():
        try:
            weeks = load_rebalance_fridays()
            weekly_panel = {c: daily_to_weekly_close(load_daily_close(c)[0]) for c in (OX | CMD)}
            listings = {c: load_listing_date(c) for c in weekly_panel}
            ox_any = cmd_any = False
            for i in range(len(weeks)):
                ox_elig = [c for c in OX if name_eligible(c, i, weeks, weekly_panel[c], listings.get(c))]
                cmd_elig = [c for c in CMD if name_eligible(c, i, weeks, weekly_panel[c], listings.get(c))]
                if ox_elig:
                    ox_any = True
                if cmd_elig:
                    cmd_any = True
            if not ox_any and not cmd_any:
                fail_reasons.append("OX and CMD both have zero eligibility weeks in eval window")
            elif not ox_any:
                fail_reasons.append("OX has zero eligibility weeks")
            elif not cmd_any:
                cmd_status = "SKIP"
        except Exception as exc:  # noqa: BLE001
            fail_reasons.append(f"eligibility check failed: {exc}")

    verdict_if_stop = None
    if fail_reasons or ox_status == "FAIL" or (cmd_status == "FAIL"):
        verdict_if_stop = "BLOCKED"

    inv = {
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "task": TASK,
        "ox": {"status": ox_status, "n": 16, "codes": sorted(OX)},
        "cmd": {"status": cmd_status, "n": 5, "codes": sorted(CMD)},
        "rates": {
            "status": rates_status,
            "reason": rates_reason,
            "pre2019_ok": pre2019_ok,
            "covers_eval_end": covers_eval_end,
            "drift_flag": drift_flag,
            "honest_from": honest_from,
            "honest_to": honest_to,
        },
        "n_declared": len(declared),
        "declared_sleeves": declared,
        "triple_sleeve_claim": "SKIP" if rates_status != "OK" else "SCORED",
        "local_data_paths": local_paths,
        "verdict_if_stop": verdict_if_stop,
        "fail_reasons": fail_reasons,
        "pool_path": str(pool_path.relative_to(ROOT)) if pool_path else None,
    }

    OUT_JSON.write_text(json.dumps(inv, ensure_ascii=False, indent=2), encoding="utf-8")
    with OUT_NAMES.open("w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(
            f,
            fieldnames=[
                "code",
                "source_path",
                "source_ref",
                "first_date",
                "last_date",
                "n_bars",
                "fields",
                "listing_proxy",
                "drift_flag",
            ],
        )
        w.writeheader()
        w.writerows(names_rows)

    if verdict_if_stop == "BLOCKED":
        lines = [
            "# VS-TSMOM-SLEEVE · REPORT (BLOCKED)",
            "",
            "## 缺数据 / 断言失败",
            "",
        ]
        for r in fail_reasons:
            lines.append(f"- {r}")
        lines.append("")
        lines.append("库存未通过，未生成回测主表数字。")
        REPORT.write_text("\n".join(lines), encoding="utf-8")
        print("BLOCKED:", "; ".join(fail_reasons))
        return 1

    print(json.dumps(inv, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
