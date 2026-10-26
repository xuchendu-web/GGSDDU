# SPIKE-S20-VOL-TARGET-12

12% annualized vol-target overlay on the frozen **B45+S20 face weekly** book, versus **unscaled (L=1)**. TV25 is the current-face reference. Research pool only — no LIVE / `strategy_exec`.

```bash
cd research/cloud_batch/SPIKE-S20-VOL-TARGET-12
python3 test_vol_scale.py
python3 run.py
```

Four-pack: `run.py` / `criterion.md` / `REPORT.md` / `summary.json`.
