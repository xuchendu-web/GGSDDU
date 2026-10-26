# Cloud batch research (2026-10-26)

Unpack `CLOUD-BATCH-2026-10-26` kit (from batch tarball) beside knife deliverables.

```bash
PYTHONPATH=research/cloud_batch/CLOUD-BATCH-2026-10-26/scripts \
  python3 research/cloud_batch/SPIKE-S20-BTHETA-GRID-LIVE1430/run.py

PYTHONPATH=research/cloud_batch/CLOUD-BATCH-2026-10-26/scripts \
  python3 research/cloud_batch/SPIKE-S20-CASH-BOND-SLEEVE-LIVE1430/run.py
```

Red lines: research only; no `strategy_exec` / LIVE writes.
