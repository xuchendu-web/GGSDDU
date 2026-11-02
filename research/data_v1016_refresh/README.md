# data_v1016 刷新（研究 only）

本树是 `data_v1016` 的应达交易日审查与旁路刷新，**不改 LIVE / strategy_exec**。

仓库主树没有原始 `etf-momentum/data_v1016`。已提交代理是 CLOUD-BATCH-2026-10-26 研究缓存（日频截到 `2026-10-23`）。本次把可核验序列补到完整交易日 `2026-10-30`（运行日 `2026-11-02` 仍是未完成 bar，不当作应达日）。

## 产物

- `REFRESH.md` — 绿/黄、源缺口、复现命令
- `out/status.json` — 机器可读状态（审计读这个）
- `out/calendar_expected.json` — 应达日历（国庆 `10-01..10-07` 无 bar，不臆造）
- `out/listing_436.json` — 只替换 ETF 宇宙 436
- `out/panel_core_tail.csv` / `out/panel_coverage.json` — 核心 8 只尾部 + 436×会话覆盖
- `out/000985_csi.csv` — 中证全指（`indexcode=14110`）
- `out/bm_930950.csv` — 中证偏股型基金（`indexcode=121882`，**无 2026-10-30**）
- `out/champ_equity_asof_20261023.csv` — 已发布冠军净值，截到 `2026-10-23`
- `out/fri_1430_20261030.csv` — 腾讯 m30 周五 14:30，436/436（pytdx 空口旁路）

## 复现

```bash
# 默认真金 10 只；全宇宙：--codes "$(python3 -c 'import json; print(",".join(json.load(open("research/data_v1016_refresh/out/listing_436.json"))))')"
python3 research/data_v1016_refresh/scripts/tencent_fri1430.py
python3 research/data_v1016_refresh/scripts/audit_refresh.py
```

允许源：`zsmcp` + 腾讯 `ifzq.gtimg.cn` m30。本环境 `pytdx` / `cjpy` 为空。禁止进门 / 中金 / Alpha派。
