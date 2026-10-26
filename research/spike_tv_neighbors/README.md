# spike_tv_neighbors — TV σ* 邻档机械扫

冻结 **B45 + spike_ft max5 + S20 + E0 + LIVE1430 + 0.2%RT + L≤1**，仅扫 **σ\*∈{0.20,0.22,0.28,0.30}** vs **TV25**。

```bash
pip install -r requirements.txt
python run_tv_neighbor_scan.py
python run_tv_neighbor_scan.py --engine-csv data/tv_neighbor_engine.csv
```

交付：`HYPOTHESIS.md`、`main_table.md`、`NOTES.md`、`scan_result.json`。
