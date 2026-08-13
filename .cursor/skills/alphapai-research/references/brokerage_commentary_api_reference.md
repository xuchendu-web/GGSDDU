# 点评（brokerage commentary）API 参考

路径前缀：`/alpha/open-api/v1/comments`。公开 CLI 名称为 `brokerage-commentary`；`review` 仅为兼容别名。

## 目录

- [接口清单](#接口清单)
- [1. 搜索点评列表](#1-搜索点评列表)
- [2. 查看点评详情](#2-查看点评详情)
- [3. 业绩点评专属列表](#3-业绩点评专属列表)

## 接口清单

| 功能 | HTTP | 路径 | CLI |
|---|---|---|---|
| 搜索点评列表 | POST | `/comments/list` | `brokerage-commentary list` |
| 查看点评详情 | POST | `/comments/detail` | `brokerage-commentary detail` |
| 业绩点评专属列表 | POST | `/comments/event/list` | `brokerage-commentary event-list` |

## 1. 搜索点评列表

请求字段：

| JSON | CLI | 类型 | 必填 | 说明 |
|---|---|---|---|---|
| `page` / `pageSize` | `--page` / `--page-size` | integer | 否 | 默认 1 / 20 |
| `commentScope` | `--scope` | string | 否 | `all` / `valuable` / `regular` |
| `keyword` | `--keyword` | string | 否 | 匹配标题或正文 |
| `startDate` / `endDate` | `--start` / `--end` | string | 否 | `yyyy-MM-dd`；均缺省时服务端默认近 30 天 |
| `industryCode` / `industryName` | 同名 CLI 参数 | string[] | 否 | 行业过滤 |
| `subjectCode` / `subjectName` | 同名 CLI 参数 | string[] | 否 | 题材过滤 |
| `stockCombSymbol` / `stockName` | `--stock-symbol` / `--stock-name` | string[] | 否 | 股票过滤 |

返回 `PageResult<Commentary>`。分页字段为 `pageNum`、`pageSize`、`totalPageNum`、`totalSize`、`data[]`。

`Commentary` 完整实测字段：

| 字段 | 类型 | 说明 |
|---|---|---|
| `commentId` | string | 时效加密 ID，详情接口使用 |
| `title` / `content` | string | 标题与正文；列表已可能返回完整正文 |
| `commentTime` / `updateTime` | string | 点评时间与更新时间 |
| `commentScope` / `commentScopeLabel` | string | 范围代码与展示名 |
| `industryTag` / `subjectTag` / `stockTag` | `Tag[]` | 行业、题材、股票 |
| `conceptTag` / `institutionTag` | `Tag[]` | 概念、机构 |
| `teamTag` / `analystTag` | `Tag[]` | 团队、分析师 |

`Tag` 为 `{"code":string|null,"name":string}`。各标签数组可为空。

```json
{
  "code": 200000,
  "message": "success",
  "data": {
    "pageNum": 1,
    "pageSize": 1,
    "totalPageNum": 100,
    "totalSize": 100,
    "data": [{
      "commentId": "<实时加密ID>",
      "title": "示例点评标题",
      "content": "示例点评正文",
      "commentTime": "2026-08-02 10:00:00",
      "updateTime": "2026-08-02 10:10:00",
      "commentScope": "regular",
      "commentScopeLabel": "常规点评",
      "industryTag": [],
      "subjectTag": [],
      "stockTag": [{"code": "600519.SH", "name": "贵州茅台"}],
      "conceptTag": [],
      "institutionTag": [{"code": "<机构编码>", "name": "示例机构"}],
      "teamTag": [{"code": "<团队编码>", "name": "示例团队"}],
      "analystTag": []
    }]
  }
}
```

## 2. 查看点评详情

请求体：

```json
{"commentId": ["<COMMENT_ID>"]}
```

`commentId` 是数组，支持多个；CLI 为 `--comment-id ID [ID ...]`。返回 `data` 也是 `Commentary[]`，不是单对象，字段与上表一致。

ID 每次列表请求可能重新生成且有时效性。批量传入过期 ID 可能导致整批失败；需要可靠处理时先实时列表，再尽快逐个详情。

## 3. 业绩点评专属列表

| JSON | CLI | 类型 | 必填 | 说明 |
|---|---|---|---|---|
| `marketScope` | `--market-scope` | string | 是 | `ah` / `a` / `hk` |
| `eventType` | `--event-type` | string[] | 否 | `performance_forecast` / `performance_flash` / `performance_report` |
| `stockCombSymbol` | `--stock-symbol` | string[] | 否 | 股票代码 |
| `startDate` / `endDate` | `--start` / `--end` | string | 否 | 日期范围 |
| `page` / `pageSize` | `--page` / `--page-size` | integer | 否 | 分页 |

返回 `PageResult<CommentaryEvent>`：

| 字段 | 类型 | 说明 |
|---|---|---|
| `eventId` | string | 时效事件 ID |
| `title` | string | 事件标题 |
| `stock` | `{code:string,name:string}` | 股票 |
| `marketScope` / `marketScopeLabel` | string | 市场代码与展示名 |
| `eventType` / `eventTypeLabel` | string | 事件代码与展示名 |
| `eventDate` | string | 事件日期 |
| `commentCount` | integer | 关联点评数量 |

```json
{
  "code": 200000,
  "message": "success",
  "data": {
    "pageNum": 1,
    "pageSize": 1,
    "totalPageNum": 1,
    "totalSize": 1,
    "data": [{
      "eventId": "<实时加密ID>",
      "title": "示例业绩报告事件",
      "stock": {"code": "600519.SH", "name": "贵州茅台"},
      "marketScope": "a",
      "marketScopeLabel": "A股",
      "eventType": "performance_report",
      "eventTypeLabel": "业绩报告",
      "eventDate": "2026-08-01",
      "commentCount": 3
    }]
  }
}
```

上述三个 CLI 于 2026-08-02 使用当前配置均实测 `code=200000`。
