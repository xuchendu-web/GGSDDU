# 实现 · VOL-TARGET-10-15-B45

- **入口**：`python3 run.py`（依赖见 `requirements.txt`；数据只读 `../cloud_batch/CLOUD-BATCH-2026-10-26/`）。
- **共享周频账本**：`simulate()` 生成 B45+spike_ft+SHARPE20+E0+EQ5 max5 持仓；四叠加仅改 `run_live_tv()` 的 `sigma_star`（10% / 15% / 12% / None）。
- **波动缩放**：`σ̂=max(σ20,σ60)` 于未杠杆日收益；`L=min(1, σ*/σ̂)`；换手 0.2% RT。
- **自检**：`python3 test_vol_scale.py`（合成数据，无行情缓存）。
- **产出**：`table.csv`（含 Sortino）、`conclusion.md`、`summary.json` 及 nav/持仓附属文件。
