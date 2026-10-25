# MF-HOLD-BGRID 同步说明

- **本跑产物根目录**：`/workspace/research/cloud_batch/MF-HOLD-BGRID/`
- **母环境目标路径**：`/workspace/etf-multifreq/MF-HOLD-BGRID/`（本跑已通过 `mf_common.deliver` 镜像 metrics / REPORT / nav / ATTRIBUTION）
- **引擎脚本**：`engine/run_hold_bgrid.py`（依赖 `engine/mom_engine.py`、`engine/panel_build.py`、`engine/mf_common.py`）
- **价量面板**：`../panel/mf_panel_v1.pkl`；增量日线下载：`../prices_daily/`
- **批次包**：`../CLOUD-BATCH-2026-10-26/`（刀法 `knives/MF-HOLD-BGRID.md`）
