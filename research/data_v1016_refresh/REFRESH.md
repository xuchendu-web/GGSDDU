# data_v1016 刷新报告（研究 only）

- 运行时刻：`2026-11-02T01:40Z`（北京时间约 09:43，当日 bar 未完成）
- 应达完整交易日：`2026-10-30`（周五）
- 已提交缓存截点：`2026-10-23`
- 延展会话：`2026-10-26` … `2026-10-30`
- LIVE / `strategy_exec`：**未改**
- 禁区源（进门 / 中金 / Alpha派）：**未接**
- 本环境空口：`pytdx`、`cjpy` → 继续 `zsmcp` + 腾讯 m30 旁路

仓库没有原始 `/workspace/etf-momentum/data_v1016`。本树按 CLOUD-BATCH 宇宙（436 只替换 ETF）+ 聚源中证表复核。

## 谁绿谁黄

| 序列 | 色 | 最后完整日 | 说明 |
| --- | --- | --- | --- |
| panel 日频 | **GREEN** | 2026-10-30 | 436/436 在 `10-23` 与五个延展日均有 `volume>0` 日 bar |
| 000985 中证全指 | **GREEN** | 2026-10-30 | 收盘 4952.4953（−2.3267%） |
| bm_930950 | **YELLOW** | 2026-10-29 | CSI 表无 `10-30`；腾讯 `sh930950` 空。**不臆造** |
| champ_equity | **YELLOW** | 2026-10-23 | 已发布 LIVE1430 冠军净值只到 10-23；禁止重算引擎 |
| fri_1430 | **GREEN** | 2026-10-30 | pytdx 空；腾讯 m30 旁路 436/436，stamp=`202610301430` |

## 源缺口（只记实查空口，不补日）

1. **930950 / 2026-10-30**  
   `qt_csiindexquote` `indexcode=121882` 最后一行是 `2026-10-29` 收盘 1578.8144。同窗 `000985`（`indexcode=14110`）已有 `10-30`。腾讯 `sh930950` 无 m30。不写 `10-30` 行，不引用 cnfin 等量纲不合的旁证。

2. **champ_equity / 2026-10-26 … 10-30**  
   已发布净值止于 `2026-10-23`。延展需要 LIVE / `strategy_exec`，本次禁止。

3. **fri_1430 原生 pytdx**  
   pytdx 本环境为空，未接。腾讯 m30 旁路已取齐 436/436（`202610301430`）。`510300` 14:30=4.075，当日日收=4.065。这是旁路 bar，不是 pytdx 分笔。

4. **2026-11-02**  
   运行时未收盘，不当作应达完整日。`000985` / `930950` 均无该日完成 bar。

5. **国庆 2026-10-01 … 10-07**  
   `000985` 无 bar。不是源缺失，是休市。日历不写入这些日。

6. **SecuCode 碰撞**  
   `563xxx` 等代码在 `secumain` 可能撞非基金行，出现 close=100 / volume=0。覆盖统计强制 `secucategory=8` 且 `turnovervolume>0`。

## 核对点

- 000985 `2026-10-30` close = 4952.4953（中证全指，**不是**股票 大庆华科）
- 510300 日收：缓存 `2026-10-23` = 4.178（未改写）；`2026-10-30` = 4.065
- 510300 周五 14:30（腾讯 m30）= 4.075
- 930950 最后日 = `2026-10-29`，文件中**没有** `2026-10-30`
- champ 最后日 = `2026-10-23`
- panel 覆盖：`10-23/26/27/28/29/30` 均为 436/436

## 复现命令

```bash
# 周五 14:30（腾讯旁路；默认真金 10 只）
# 全宇宙 436：--codes "$(python3 -c 'import json; print(",".join(json.load(open("research/data_v1016_refresh/out/listing_436.json"))))')"
python3 research/data_v1016_refresh/scripts/tencent_fri1430.py

# 断言：不臆造 930950 10-30；000985 到 10-30；champ 停 10-23
python3 research/data_v1016_refresh/scripts/audit_refresh.py
```

聚源复核（zsmcp `query`，只读）：

```sql
-- 中证全指 14110 / 偏股基金 121882
SELECT indexcode, DATE(tradingday) AS d, closeprice, changepct
FROM qt_csiindexquote
WHERE indexcode IN (14110, 121882)
  AND tradingday BETWEEN '2026-10-28' AND '2026-11-02'
ORDER BY indexcode, d;

-- 436 宇宙日频覆盖（需带 listing IN 列表）
SELECT DATE(q.tradingday) AS d, COUNT(DISTINCT s.secucode) AS n_codes
FROM qt_dailyquote q
JOIN secumain s ON q.innercode = s.innercode
WHERE s.secucategory = 8
  AND IFNULL(q.turnovervolume, 0) > 0
  AND q.tradingday BETWEEN '2026-10-23' AND '2026-10-30'
  AND s.secucode IN (/* listing_436.json keys */)
GROUP BY DATE(q.tradingday)
ORDER BY d;
```

腾讯旁路：`https://ifzq.gtimg.cn/appstock/app/kline/mkline?param={sh|sz}{code},m30,,80`，取 stamp=`202610301430`。

## 空口策略

| 源 | 本环境 | 处理 |
| --- | --- | --- |
| zsmcp 聚源 | 可用 | panel / 000985 / 930950 主源 |
| 腾讯 m30 | 可用 | fri_1430 旁路 |
| cjpy / 天软 | 空 | 不阻塞；有则优先复权/因子，本次未用 |
| pytdx | 空 | 不阻塞；继续 zsmcp + 腾讯 |
| 进门 / 中金 / Alpha派 | 禁区 | 不接 |

## 未做

- 不提交 436×5 全量日频宽表（只提交核心 8 只尾部 + 覆盖计数）
- 不重算 champ / LIVE1430
- 不把 `2026-10-30` 写入 `bm_930950.csv`
- 不把 `2026-11-02` 标成完整交易日
