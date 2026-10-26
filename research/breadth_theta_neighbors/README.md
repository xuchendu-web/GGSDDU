# breadth_theta_neighbors — θ 邻档 B40 / B45 / B50

**RESEARCH ONLY**：研究池；不触 LIVE_OPS / 冠军。

冻结 **spike_ft max5 + S20 + E0 + TV25 + LIVE1430 + 0.2%RT + L≤1**，仅扫 **θ∈{0.40, 0.45, 0.50}**（基线 B45；邻档 B40/B50）。**四件套**：`HYPOTHESIS.md`、`main_table.md`、`NOTES.md`、`scan_result.json` + 本 README。

```bash
pip install -r requirements.txt
python run_btheta_neighbor_scan.py
```

旁注 **B55** 在引擎 CSV 中保留，不参与 B40/B45/B50 邻档判定（见 `main_table.md` 集外段）。
