# NOTES · RESEARCH-WF-OOS-B45-FACE

- **引擎**：`face_run.py` + `CLOUD-BATCH-2026-10-26` 研究缓存（classify / 14:30 / face）。
- **持仓路径**：每周 `simulate()`（B45 risk_on + spike_ft max5 + SHARPE20）；**TV 仅进入** `run_live_tv` 杠杆层。
- **WF 实现**：每折在 train+test 连续日历上重跑 simulate（仓位跨 train→test 连续），TV 在 train 日收益上选型后固定用于该折 test 日收益；OOS 段按时间拼接。
- **未改**：`strategy_exec` / LIVE / champion；本目录纯研究。
- **Kit**：`/workspace/research/cloud_batch/CLOUD-BATCH-2026-10-26`

## 覆盖

```json
{
  "knife_id": "RESEARCH-WF-OOS-B45-FACE",
  "kit": "/workspace/research/cloud_batch/CLOUD-BATCH-2026-10-26",
  "calendar": "2020-01-03 → 2026-10-23",
  "n_weeks": 349,
  "n_codes_aum2": 324,
  "listed_1430_nonnull_rate": 0.9998374798542736,
  "n_qfq_1430_mapped": 73793,
  "retune_axis": "TV_sigma",
  "tv_grid": {
    "TV22": 0.22,
    "TV25": 0.25,
    "TV28": 0.28,
    "TV33": 0.33
  },
  "wf": {
    "train_w": 104,
    "test_w": 26,
    "step_w": 26
  }
}
```
