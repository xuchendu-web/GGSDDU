# 机构热议开放 API 接口文档

## 目录

- [接口与请求](#1-查询机构热议股票榜单)
- [响应示例](#响应数据listhotstockdayboardvo)
- [完整字段](#附字段说明)

# 机构热议开放 API 接口文档

> 模块：`alpha-open-api-service`；Controller：`HotStocksController`；路径前缀：`/open-api/v1/hot/stocks`
> 下文 curl 示例统一使用：`BASE=https://<网关域名>/alpha`（需携带开放平台鉴权头）。

---

## 通用约定

### 统一返回体 `Result<T>`

| 字段 | 类型 | 说明 |
|---|---|---|
| `code` | int | 业务码，成功为 `200000` |
| `message` | string | 提示信息 |
| `data` | T | 业务数据 |

### 鉴权 / 用户态



### 接口清单

| # | HTTP | 开放路径 | 下游路径 | 说明 |
|---|---|---|---|---|
| 1 | POST | `/board/list` | `/searchBoardList` | 查询机构热议股票榜单 |

---

## 1. 查询机构热议股票榜单

`POST /open-api/v1/hot/stocks/board/list`

按日期分组，每个日期下按机构类型（公募/私募/保险）返回榜单。日频数据，不含实时行情。

> 注意：**周末（周六/周日）也有完整榜单数据**，并非仅交易日有数据；`tradingDay` 字段名不代表只含交易日。

### 请求参数（Body）

| 字段 | 类型 | 必填 | 说明 |
|---|---|---|---|
| `startDate` | string | 否 | 开始日期，`yyyy-MM-dd` |
| `endDate` | string | 否 | 结束日期，`yyyy-MM-dd` |
| `instTypeTag` | array&lt;string&gt; | 否 | 机构类型，可选 `公募` / `私募` / `保险`；不传默认全部 |
| `stockComboSymbolTag` | array&lt;string&gt; | 否 | 股票代码过滤，如 `300308.SZ` |
| `stockNameTag` | array&lt;string&gt; | 否 | 股票名称过滤（**精确匹配**，需传完整股票名称） |
| `limit` | int | 否 | **每个交易日每机构类型返回条数上限（1-50），默认 `10`，最大 `50`；不过滤排名，返回条目的 rank 可能大于 limit** |

### 调用示例

```bash
curl -X POST "$BASE/open-api/v1/hot/stocks/board/list" \
  -H "Content-Type: application/json" \
  -d '{
    "startDate": "2026-06-09",
    "endDate": "2026-06-13",
    "instTypeTag": ["公募", "私募", "保险"],
    "stockComboSymbolTag": ["300308.SZ", "301377.SZ"],
    "stockNameTag": ["联芸科技"],
    "limit": 12
  }'
```

### 响应数据：`List<HotStockDayBoardVO>`

```json
{
  "code": 200000,
  "message": "SUCCESS",
  "data": [
    {
      "tradingDay": "2026-06-13",
      "instBoardList": [
        {
          "instType": "公募",
          "instTypeLabel": "公募榜",
          "itemList": [
            {
              "comboSymbol": "300308.SZ",
              "hcode": "SEC000119729",
              "name": "中际旭创",
              "rank": 1,
              "hotCount": 10
            }
          ]
        }
      ]
    }
  ]
}
```

---

## 附：字段说明

### HotStockDayBoardVO

| 字段 | 类型 | 说明 |
|---|---|---|
| `tradingDay` | string | 交易日（周末日期也会出现，含完整榜单） |
| `instBoardList` | array | 当日各机构类型榜单 |

### HotStockInstBoardVO

| 字段 | 类型 | 说明 |
|---|---|---|
| `instType` | string | 机构类型 |
| `instTypeLabel` | string | 展示名，如公募榜 |
| `itemList` | array | 股票列表 |

### HotStockItemVO

| 字段 | 类型 | 说明 |
|---|---|---|
| `comboSymbol` | string | 股票交易代码 |
| `hcode` | string | 内部证券编码 |
| `name` | string | 股票名称 |
| `rank` | int | 排名 |
| `hotCount` | int | 热议次数 |

2026-08-02 当前 CLI 使用 `limit=1` 实测返回 29 个日期分组，每日含公募/私募/保险榜单，顶层 `code=200000`。`message` 当前为 `success`；调用方不应区分大小写判断成功，应以 `code` 为准。
