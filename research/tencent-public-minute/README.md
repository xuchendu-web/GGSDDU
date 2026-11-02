# 腾讯公开分钟对照 / 探活（研究侧）

pytdx 断供时，用腾讯公开 HTTP 对研究池做交叉检查。**research-only。**

审阅锚点：腾讯已审为实盘实时旁路（2026-10-31）；2026-11-02 Michael（经悟空）要求把腾讯及旁路做完整。本目录只补对照/探活，不改 `strategy_exec` / LIVE 参数。

## 硬闸

- 腾讯无 token、无 SLA，可拉 qt / 当日 1m / 分时做对照。
- **回测不当权威。** 日线/周线回测仍走研究池既有缓存与 cjpy 口径；不要把本脚本的分钟当成历史真源。
- **不可替 cjpy AUM。** `qt` 的市值类字段不写出、不当规模。
- **不碰 LIVE。** 不写执行参数、不下单、不改实盘名单。
- 禁止接入进门 / 中金 / Alpha派行情；禁止扩东财未审口 / 国金 QMT。
- 14:30 须滤 `time<=14:30`（默认开，对齐 LIVE1430 栅格的旁路对照）。
- 休市腾讯常吐**最近交易日**，必须自判（`session_kind=replay|stale|live`），禁止把回放当今日实时。

## 两轨

| 轨 | 用途 | 权威？ |
|---|---|---|
| **盘中旁路** | pytdx 挂了或要交叉验活：拉 qt 现价、当日 1m、近端分时，看灯号 | 否。只回答「腾讯这口现在能不能对照」 |
| **回测不当权威** | 研究池回测、AUM、LIVE1430 快照、成交裁决 | 否。本工具不生产回测面板，也不覆盖 cjpy |

盘中旁路绿灯 ≠ 可以改 LIVE。黄灯可以继续看，但不能当执行依据。

已用公开口（均无鉴权，仓库 cloud_batch 已用过 qt / ifzq 日周线）：

- 快照 `https://qt.gtimg.cn/q=sh510300,sz159915`
- 当日 1m `https://ifzq.gtimg.cn/appstock/app/kline/mkline?param=sh510300,m1,,320`（窗口可能带上一日，脚本按会话日裁切）
- 分时 `https://web.ifzq.gtimg.cn/appstock/app/minute/query?code=sh510300`
- 日线只用来核 qt 昨收（同家族，不当第二权威）`fqkline/get … day … qfq`

## 断供红黄判据（pytdx 挂了以后怎么读腾讯）

在**交易时段**对研究池跑本脚本：

| 灯 | 判据 | 动作 |
|---|---|---|
| **红** | qt 无有效价；或交易时段会话日 ≠ 北京今日；或最新点停滞；或盘中 **1m 与分时皆空** | 腾讯旁路也断，不能交叉；等口子恢复或改走已审的其他旁路（本目录不扩口） |
| **黄** | 休市/未开盘回放最近交易日；qt vs 1m vs 分时（或同日仓库价源）价差 **>0.3%**；仅 1m 空但分时仍有（QDII 盘初 mkline 常滞后）；近端分时 <5 点；部分端点失败 | 可看、须人工；不当执行；回放只对照昨收 |
| **绿** | 会话日=今日，三端有价，对照 ≤0.3% | 仅表示本窗口腾讯可对照 |

退出码：有红灯 `2`，全非红 `0`（黄灯仍 0，避免把「需人工」当成脚本崩溃）。

低价品种（约 0.3 元）1 个 tick（0.001）就会过 0.3% 黄线，这是阈值本身，不是解析错误。QDII 盘初 `mkline` 可能仍是上一日，脚本按会话日裁切后 1m 为空、分时仍活 → 黄，不红。

仓库已有价源（`research/cloud_batch/.../research_cache/day/{code}.json` 或 `--ref-csv`）**仅当日期与腾讯会话日相同**才比现价，否则写 `仓库价源日 ≠ 会话日`，避免拿过期缓存制造假黄。

## 复现

标准库，无第三方依赖。

```bash
# 单测（不联网）
python3 research/tencent-public-minute/tests/test_probe_tencent_minute.py

# 动量池样本 24 只（默认名单）
python3 research/tencent-public-minute/probe_tencent_minute.py \
  --codes-file research/tencent-public-minute/universe_sample.csv \
  --out-dir research/tencent-public-minute/sample_out

# 自带代码
python3 research/tencent-public-minute/probe_tencent_minute.py \
  --codes 510300,159915,518880 \
  --out-dir /tmp/tencent-probe
```

产出：`snapshot.csv`、`minutes_1m.csv`、`timeline_near.csv`、`summary.md`、`summary.json`。

可选对照：

```bash
# 研究分支上的日线缓存（同日才比现价）
python3 research/tencent-public-minute/probe_tencent_minute.py \
  --ref-dir research/cloud_batch/CLOUD-BATCH-2026-10-26/data/research_cache/day \
  --out-dir /tmp/tencent-probe

# 或自己的 CSV：code,date,close
python3 research/tencent-public-minute/probe_tencent_minute.py \
  --ref-csv /path/to/ref_last_close.csv \
  --out-dir /tmp/tencent-probe
```

关 14:30 过滤（只为看全日 1m，不当 LIVE1430 对照）：`--no-cutoff-1430`。

## 样本名单与扩展

`universe_sample.csv` 从研究分支 `universe_replace_only_436.csv`（CLOUD-BATCH-2026-10-26，436 只 replace-only 动量池）抽 **24 只**：宽基市值阶梯 / 科创 / 创业板、红利、证券、半导体、医药、新能源、TMT、消费、有色、AI、机器人、港股、QDII、黄金。本分支不搬运 436 全表。

扩到全池或任意子切片：

```bash
# 若本地有 436 名单（其他研究分支）
python3 research/tencent-public-minute/probe_tencent_minute.py \
  --codes-file /path/to/universe_replace_only_436.csv \
  --out-dir /tmp/tencent-probe-436

# 或只要 code 列
cut -d, -f1 /path/to/universe_replace_only_436.csv | tail -n +2 > /tmp/codes.txt
python3 research/tencent-public-minute/probe_tencent_minute.py \
  --codes-file /tmp/codes.txt \
  --out-dir /tmp/tencent-probe-436
```

货币/债基袖不在 436 主池；不要把本工具的腾讯字段当规模或申赎依据。

## 不做什么

- 不改 `strategy_exec`、LIVE 参数、实盘名单。
- 不把腾讯分钟写进回测引擎。
- 不把腾讯市值当 AUM。
- 不接进门 / 中金 / Alpha派 / 东财未审口 / 国金 QMT。
