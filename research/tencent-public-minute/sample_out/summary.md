# 腾讯公开分钟对照摘要

- 探测时刻（北京）：`2026-11-02 09:52:45 +0800`
- 代码数：24；灯号 绿 22 / 黄 2 / 红 0
- 会话：live=24
- 14:30 过滤：开；近端分时保留末 30 点
- 仓库价源：未挂载仓库日线缓存（同日才比现价；扩展见 README）
- 黄线：对照价差 > 0.3%（qt vs 1m vs 分时；同日仓库价；qt 昨收 vs 腾讯日线完整 K）
- 硬闸：盘中旁路 ≠ 回测权威；不替 cjpy AUM；不碰 LIVE / strategy_exec；无 SLA

| 灯 | 代码 | 名称 | 会话 | qt | 1m末 | 分时末 | qt-1m | qt-分时 | 仓库 | 说明 |
|---|---|---|---|---:|---:|---:|---:|---:|---:|---|
| <span style="background:#d4edda;padding:0 4px">绿</span> | `510300` | 华泰柏瑞沪深300ETF | live | 4.082 | 4.082 | 4.082 | 0.0000% | 0.0000% | — | qt/1m/分时可用且对照≤0.3% |
| <span style="background:#d4edda;padding:0 4px">绿</span> | `510500` | 南方中证500ETF | live | 6.33 | 6.327 | 6.325 | 0.0474% | 0.0791% | — | qt/1m/分时可用且对照≤0.3% |
| <span style="background:#d4edda;padding:0 4px">绿</span> | `512100` | 南方中证1000ETF | live | 2.515 | 2.513 | 2.513 | 0.0796% | 0.0796% | — | qt/1m/分时可用且对照≤0.3% |
| <span style="background:#d4edda;padding:0 4px">绿</span> | `510050` | 华夏上证50ETF | live | 2.875 | 2.876 | 2.876 | 0.0348% | 0.0348% | — | qt/1m/分时可用且对照≤0.3% |
| <span style="background:#d4edda;padding:0 4px">绿</span> | `563300` | 华泰柏瑞中证2000ETF | live | 1.201 | 1.2 | 1.2 | 0.0833% | 0.0833% | — | qt/1m/分时可用且对照≤0.3% |
| <span style="background:#d4edda;padding:0 4px">绿</span> | `588000` | 华夏上证科创板50ETF | live | 1.234 | 1.233 | 1.232 | 0.0811% | 0.1623% | — | qt/1m/分时可用且对照≤0.3% |
| <span style="background:#d4edda;padding:0 4px">绿</span> | `159915` | 易方达创业板ETF | live | 2.439 | 2.438 | 2.438 | 0.0410% | 0.0410% | — | qt/1m/分时可用且对照≤0.3% |
| <span style="background:#d4edda;padding:0 4px">绿</span> | `159949` | 华安创业板50ETF | live | 1.104 | 1.102 | 1.102 | 0.1815% | 0.1815% | — | qt/1m/分时可用且对照≤0.3% |
| <span style="background:#d4edda;padding:0 4px">绿</span> | `510180` | 华安上证180ETF | live | 3.613 | 3.614 | 3.614 | 0.0277% | 0.0277% | — | qt/1m/分时可用且对照≤0.3% |
| <span style="background:#d4edda;padding:0 4px">绿</span> | `512890` | 华泰柏瑞红利低波动ETF | live | 1.25 | 1.251 | 1.251 | 0.0799% | 0.0799% | — | qt/1m/分时可用且对照≤0.3% |
| <span style="background:#d4edda;padding:0 4px">绿</span> | `512880` | 国泰中证全指证券公司ETF | live | 0.994 | 0.995 | 0.995 | 0.1005% | 0.1005% | — | qt/1m/分时可用且对照≤0.3% |
| <span style="background:#d4edda;padding:0 4px">绿</span> | `588200` | 嘉实上证科创板芯片ETF | live | 0.782 | 0.781 | 0.78 | 0.1280% | 0.2564% | — | qt/1m/分时可用且对照≤0.3% |
| <span style="background:#fff3cd;padding:0 4px">黄</span> | `512170` | 华宝中证医疗ETF | live | 0.331 | 0.332 | 0.332 | 0.3012% | 0.3012% | — | 对照价差 >0.3% |
| <span style="background:#d4edda;padding:0 4px">绿</span> | `159755` | 广发国证新能源车电池ETF | live | 0.728 | 0.728 | 0.728 | 0.0000% | 0.0000% | — | qt/1m/分时可用且对照≤0.3% |
| <span style="background:#d4edda;padding:0 4px">绿</span> | `515880` | 国泰中证全指通信设备ETF | live | 0.43 | 0.43 | 0.43 | 0.0000% | 0.0000% | — | qt/1m/分时可用且对照≤0.3% |
| <span style="background:#d4edda;padding:0 4px">绿</span> | `159928` | 汇添富中证主要消费ETF | live | 0.688 | 0.689 | 0.689 | 0.1451% | 0.1451% | — | qt/1m/分时可用且对照≤0.3% |
| <span style="background:#d4edda;padding:0 4px">绿</span> | `512400` | 南方中证申万有色金属ETF | live | 1.371 | 1.369 | 1.369 | 0.1461% | 0.1461% | — | qt/1m/分时可用且对照≤0.3% |
| <span style="background:#d4edda;padding:0 4px">绿</span> | `159819` | 易方达中证人工智能ETF | live | 1.34 | 1.338 | 1.339 | 0.1495% | 0.0747% | — | qt/1m/分时可用且对照≤0.3% |
| <span style="background:#d4edda;padding:0 4px">绿</span> | `513180` | 华夏恒生科技ETF | live | 0.472 | 0.471 | 0.471 | 0.2123% | 0.2123% | — | qt/1m/分时可用且对照≤0.3% |
| <span style="background:#d4edda;padding:0 4px">绿</span> | `159920` | 华夏恒生ETF | live | 1.37 | 1.37 | 1.37 | 0.0000% | 0.0000% | — | qt/1m/分时可用且对照≤0.3% |
| <span style="background:#d4edda;padding:0 4px">绿</span> | `513500` | 博时标普500ETF | live | 2.633 | 2.633 | 2.633 | 0.0000% | 0.0000% | — | qt/1m/分时可用且对照≤0.3% |
| <span style="background:#fff3cd;padding:0 4px">黄</span> | `159941` | 广发纳斯达克100ETF | live | 1.649 |  | 1.649 | — | 0.0000% | — | 当日 1m 空包（分时仍有；常见于 QDII 盘初 mkline 滞后） |
| <span style="background:#d4edda;padding:0 4px">绿</span> | `518880` | 华安黄金ETF | live | 7.953 | 7.949 | 7.949 | 0.0503% | 0.0503% | — | qt/1m/分时可用且对照≤0.3% |
| <span style="background:#d4edda;padding:0 4px">绿</span> | `562500` | 华夏中证机器人ETF | live | 0.813 | 0.812 | 0.812 | 0.1232% | 0.1232% | — | qt/1m/分时可用且对照≤0.3% |

## 断供旁路怎么读

- **红**：qt 无价 / 交易时段会话日错或最新点停滞 / 盘中 1m 与分时皆空 → pytdx 断供时腾讯也不可用。
- **黄**：休市回放、对照 >0.3%、仅 1m 空、近端过稀、部分端点失败 → 可交叉看，不当执行依据。
- **绿**：仅表示本探活窗口腾讯公开口可对照，**不是**回测或 LIVE 授权。

## 产出

- `snapshot.csv` — 每只一只一行对照
- `minutes_1m.csv` — 当日 1m（含 `le_1430`）
- `timeline_near.csv` — 近端分时（已按 14:30 过滤）
- `summary.json` — 机读摘要

