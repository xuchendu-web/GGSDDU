# REBAND 邻域稳健（LIVE1430）

研究-only。跑批：

```bash
# 若缺研究缓存（首次）：
git fetch origin cursor/btheta-grid-live1430-87d9
git checkout origin/cursor/btheta-grid-live1430-87d9 -- research/cloud_batch/CLOUD-BATCH-2026-10-26/data
ln -sfn "$(pwd)/research/cloud_batch/CLOUD-BATCH-2026-10-26" /workspace/CLOUD-BATCH-2026-10-26

pip install pandas numpy matplotlib
python3 research/reband-neighbors-live1430/run_reband_neighbors.py
```

产物：`REPORT.md` · `table.csv` · `summary.json` · `nav_*.csv`
