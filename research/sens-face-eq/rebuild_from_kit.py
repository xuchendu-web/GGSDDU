#!/usr/bin/env python3
"""Rebuild Face EQ T-1 vs SENS1430 (and close-lookahead diagnostic) from PR#50 kit.

Research pool only. Does not touch LIVE / strategy_exec / champion_mast.

Environment:
  FACE_EQ_KIT  directory of CLOUD-BATCH-2026-10-26
               (from origin/cursor/spike-s20-size-eq-hyst-m2m3-live1430-4a23)
  FACE_EQ_RUN  optional path to that branch's
               research/SPIKE-S20-SIZE-EQ-HYST-M2M3-LIVE1430/run.py

The only research change vs PR#50 Face EQ:
  LIVE/T-1  sharpe_n_on  window ends strictly BEFORE signal day
  SENS1430  last Sharpe point = signal-day qfq_1430 (never Friday close)
  LOOKAHEAD last Sharpe point = Friday qfq close (diagnostic; not an anchor)
"""
from __future__ import annotations

import os
import runpy
import sys
from pathlib import Path


def _patch(src: str, out_dir: Path) -> str:
    t = src
    t = t.replace(
        "OUT = Path(__file__).resolve().parent",
        f"OUT = Path({str(out_dir)!r})",
    )
    old = '''def sharpe_n_on(closes: pd.Series, d: str, n: int) -> float | None:
    """Annualized Sharpe of last n daily returns ending strictly BEFORE d."""
    ts = pd.Timestamp(d)
    sub = closes.loc[: ts - pd.Timedelta(days=1)]
'''
    new = '''def sharpe_n_on(closes: pd.Series, d: str, n: int, include_asof: bool = False) -> float | None:
    """Annualized Sharpe of last n daily returns.

    LIVE / T-1 (include_asof=False): window ends strictly BEFORE d.
    SENS (include_asof=True): window includes d. Caller must put signal-day
    14:30 qfq on d (never the Friday close).
    """
    ts = pd.Timestamp(d)
    sub = closes.loc[:ts] if include_asof else closes.loc[: ts - pd.Timedelta(days=1)]
'''
    if old not in t:
        raise SystemExit("sharpe_n_on block not found in kit run.py")
    t = t.replace(old, new)
    t = t.replace(
        """    sharpe_n: int | None,
    max_pos: int,
    sizing_mode: SizingMode,
    hyst_m: int | None = None,
) -> tuple[list[dict[str, Any]], dict[str, list[str]], dict[str, dict[str, float]], dict[str, Any]]:
""",
        """    sharpe_n: int | None,
    max_pos: int,
    sizing_mode: SizingMode,
    hyst_m: int | None = None,
    include_asof: bool = False,
) -> tuple[list[dict[str, Any]], dict[str, list[str]], dict[str, dict[str, float]], dict[str, Any]]:
""",
    )
    t = t.replace(
        "                sh = sharpe_n_on(daily[code], d, sharpe_n)\n",
        "                sh = sharpe_n_on(daily[code], d, sharpe_n, include_asof=include_asof)\n",
    )
    old_v = '''    # (rank_fn, require_sharpe, sharpe_n, sizing_mode, hyst_m)
    variants: dict[str, tuple[RankFn, bool, int | None, SizingMode, int | None]] = {
        "LIVE1430-EQ-S20": (sharpe_key, True, 20, "eq", None),
        "LIVE1430-EQ-HYST-M2-S20": (sharpe_key, True, 20, "eq", 2),
        "LIVE1430-EQ-HYST-M3-S20": (sharpe_key, True, 20, "eq", 3),
        "LIVE1430-INV-HYST-M3-S20": (sharpe_key, True, 20, "inv20w", 3),
    }
'''
    new_v = '''    daily_sens: dict[str, pd.Series] = {}
    n_over = 0
    for code, ser in daily.items():
        s = ser.copy()
        for td, px1430 in (noon_d.get(code) or {}).items():
            ts = pd.Timestamp(td)
            s.loc[ts] = float(px1430)
            n_over += 1
        daily_sens[code] = s.sort_index()
    print(f"SENS daily: overwrite {n_over} signal-day points with qfq_1430", flush=True)
    variants: dict[str, tuple] = {
        "FACE-EQ-T1": (sharpe_key, True, 20, "eq", None, False, daily),
        "FACE-EQ-SENS1430": (sharpe_key, True, 20, "eq", None, True, daily_sens),
        "FACE-EQ-LOOKAHEAD-CLOSE": (sharpe_key, True, 20, "eq", None, True, daily),
    }
'''
    if old_v not in t:
        raise SystemExit("variants block not found in kit run.py")
    t = t.replace(old_v, new_v)
    t = t.replace(
        """    for name, (rfn, req, sn, sm, hm) in variants.items():
        print(f"simulate {name} (sizing={sm} hyst_m={hm})…", flush=True)
        trades, hold, wby, st = simulate(
            calendar,
            snaps,
            closes_w_sig,
            closes_w_close,
            alias,
            aum,
            daily,
            risk_on_by_fri,
            rfn,
            name,
            req,
            sn,
            MAX_POS,
            sm,
            hm,
        )
""",
        """    for name, (rfn, req, sn, sm, hm, inc, daily_map) in variants.items():
        print(f"simulate {name} (sizing={sm} hyst_m={hm} include_asof={inc})…", flush=True)
        trades, hold, wby, st = simulate(
            calendar,
            snaps,
            closes_w_sig,
            closes_w_close,
            alias,
            aum,
            daily_map,
            risk_on_by_fri,
            rfn,
            name,
            req,
            sn,
            MAX_POS,
            sm,
            hm,
            include_asof=inc,
        )
""",
    )
    idx = t.find('    base = "LIVE1430-EQ-S20"')
    idx2 = t.find("    all_codes: set[str] = set()")
    if idx < 0 or idx2 < 0:
        raise SystemExit("could not strip HYST report header")
    t = t[:idx] + t[idx2:]
    idx3 = t.find("    y = yearly_table(series[base])")
    if idx3 < 0:
        raise SystemExit("yearly block not found")
    t = t[:idx3] + """
    ys = [yearly_table(series[k]).assign(book=k) for k in variants]
    pd.concat(ys, ignore_index=True).to_csv(OUT / "yearly.csv", index=False)
    eq = pd.DataFrame({k: (1 + series[k]).cumprod() for k in variants})
    eq.to_csv(OUT / "equity.csv")
    for name in variants:
        series[name].to_csv(OUT / f"nav_{name}.csv", header=["r"])
    summary = {
        "title": "SENS-FACE-EQ information-set alignment rebuild",
        "sample": f"{EVAL_START} → {END_S}",
        "table": table_rows,
        "sim_stats": sim_stats,
        "elapsed_sec": round(time.time() - t0, 1),
        "isolation": "research only; no LIVE / strategy_exec / champion writes",
    }
    (OUT / "summary.json").write_text(
        json.dumps(summary, ensure_ascii=False, indent=2, default=str), encoding="utf-8"
    )
    print("DONE", {r["book"]: {k: r[k] for k in ("ret", "maxDD", "Calmar")} for r in table_rows}, flush=True)


if __name__ == "__main__":
    main()
"""
    return t


def main() -> None:
    here = Path(__file__).resolve().parent
    kit = Path(os.environ.get("FACE_EQ_KIT", "")).expanduser()
    run_py = Path(os.environ.get("FACE_EQ_RUN", "")).expanduser() if os.environ.get("FACE_EQ_RUN") else None
    if run_py is None:
        # default: sibling extract used in this cloud run
        guess = Path("/tmp/face-eq-kit/research/SPIKE-S20-SIZE-EQ-HYST-M2M3-LIVE1430/run.py")
        if guess.exists() and "include_asof" not in guess.read_text():
            run_py = guess
        else:
            # if already patched locally, require FACE_EQ_RUN pointing at the *original* PR#50 file
            raise SystemExit(
                "Set FACE_EQ_RUN to PR#50 research/SPIKE-S20-SIZE-EQ-HYST-M2M3-LIVE1430/run.py "
                "and FACE_EQ_KIT to that branch's CLOUD-BATCH-2026-10-26"
            )
    if not kit.exists():
        # original run.py locates kit as parents[1]/cloud_batch/CLOUD-BATCH-2026-10-26
        kit_guess = run_py.resolve().parents[1] / "cloud_batch" / "CLOUD-BATCH-2026-10-26"
        if kit_guess.exists():
            kit = kit_guess
        else:
            raise SystemExit(f"FACE_EQ_KIT not found: {kit}")
    out = here / "out"
    out.mkdir(parents=True, exist_ok=True)
    patched = here / "_patched_run.py"
    text = run_py.read_text(encoding="utf-8")
    if "FACE-EQ-SENS1430" in text:
        raise SystemExit(f"{run_py} looks already patched; pass the original PR#50 run.py")
    patched.write_text(_patch(text, out), encoding="utf-8")
    print(f"patched {run_py} → {patched}\nkit={kit}\nout={out}", flush=True)
    sys.argv = [str(patched)]
    runpy.run_path(str(patched), run_name="__main__")


if __name__ == "__main__":
    main()
