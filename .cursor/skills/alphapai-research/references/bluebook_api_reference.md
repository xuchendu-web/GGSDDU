# 蓝宝书开放 API 接口文档

## 目录

- [接口清单](#接口清单)
- [1. 获取批次列表](#1-获取蓝宝书批次标题列表)
- [2. 搜索热门话题](#2-搜索蓝宝书热门话题内容)
- [3. 获取话题详情](#3-获取蓝宝书话题详情)
- [完整字段结构](#附bluebookbatchvo)

# 蓝宝书开放 API 接口文档

> 模块：`alpha-open-api-service`；Controller：`BlueBooksController`；路径前缀：`/open-api/v1/blue/books`
> 下文 curl 示例统一使用：`BASE=https://<网关域名>/alpha`（需携带开放平台鉴权头）。

---

## 通用约定

### 统一返回体 `Result<T>`

| 字段 | 类型 | 说明 |
|---|---|---|
| `code` | int | 业务码，成功为 `200000` |
| `message` | string | 提示信息 |
| `data` | T | 业务数据 |

### 分页返回体 `PageResult<T>`

| 字段 | 类型 | 说明 |
|---|---|---|
| `pageNum` | int | 当前页码 |
| `pageSize` | int | 每页数量 |
| `totalPageNum` | int | 总页数 |
| `totalSize` | long | 总条数 |
| `data` | array&lt;T&gt; | 结果列表 |

### 鉴权 / 用户态


### 接口清单

| # | HTTP | 开放路径 | 下游路径 | 说明 |
|---|---|---|---|---|
| 1 | POST | `/batch/list` | `/searchBatchList` | 批次标题列表 |
| 2 | POST | `/topic/list` | `/searchTopicList` | 搜索热门话题 |
| 3 | POST | `/topic/detail` | `/searchTopicDetail` | 话题详情 |

---

## 1. 获取蓝宝书批次标题列表

`POST /open-api/v1/blue/books/batch/list`

### 请求参数（Body）

| 字段 | 类型 | 必填 | 说明 |
|---|---|---|---|
| `startDate` | string | 否 | 开始日期，`yyyy-MM-dd` |
| `endDate` | string | 否 | 结束日期，`yyyy-MM-dd` |
| `batchType` | string | 是 | 批次类型，如 `morning` / `noon` / `evening` / `all` |
| `batchScope` | string | 是 | 市场范围，如 `domestic` / `global` / `all` |
| `keyword` | string | 否 | 关键词，空表示不限制 |
| `page` | int | 否 | 页码，默认 `1` |
| `pageSize` | int | 否 | 每页条数，默认 `20` |

### 调用示例

```bash
curl -X POST "$BASE/open-api/v1/blue/books/batch/list" \
  -H "Content-Type: application/json" \
  -d '{
    "startDate": "2026-01-01",
    "endDate": null,
    "batchType": "morning",
    "batchScope": "domestic",
    "keyword": "",
    "page": 1,
    "pageSize": 20
  }'
```

### 响应数据：`PageResult<BlueBookBatchVO>`

字段见 [附：BlueBookBatchVO](#附bluebookbatchvo)。

---

## 2. 搜索蓝宝书热门话题内容

`POST /open-api/v1/blue/books/topic/list`

### 请求参数（Body）

| 字段 | 类型 | 必填 | 说明 |
|---|---|---|---|
| `startDate` | string | 否 | 开始日期 |
| `endDate` | string | 否 | 结束日期 |
| `batchType` | string | 是 | 批次类型 |
| `batchScope` | string | 是 | 市场范围 |
| `keyword` | string | 否 | 关键词 |
| `stockComboSymbolTag` | array&lt;string&gt; | 否 | 股票代码过滤，如 `["BABA.US"]` |
| `stockNameTag` | array&lt;string&gt; | 否 | 股票名称过滤 |
| `minHeatLevel` | int | 否 | 最低热度 |
| `page` | int | 否 | 页码 |
| `pageSize` | int | 否 | 每页条数 |

### 股票过滤规则（下游语义）

| 场景 | 行为 |
|---|---|
| `domestic` 且不传股票 | 返回国内话题，尽量回填 `stockTag` |
| `domestic` 且传股票过滤 | 只保留匹配股票的话题 |
| `global` 且不传股票 | 返回全球话题，无 `stockTag` |
| `global` 且传股票过滤 | 返回空列表 |
| `all` 且传股票过滤 | 仅国内匹配结果 |

同时传 `stockComboSymbolTag` 与 `stockNameTag` 为 **AND**关系。

### 调用示例

```bash
curl -X POST "$BASE/open-api/v1/blue/books/topic/list" \
  -H "Content-Type: application/json" \
  -d '{
    "startDate": "2025-01-26",
    "endDate": "2025-11-26",
    "batchType": "all",
    "batchScope": "all",
    "keyword": "AI",
    "stockComboSymbolTag": ["BABA.US"],
    "minHeatLevel": 10,
    "page": 1,
    "pageSize": 20
  }'
```

### 响应数据：`PageResult<BlueBookTopicVO>`

字段见 [附：BlueBookTopicVO](#附bluebooktopicvo)。

> 注意：topic/list 返回项中 `paipaiInterpretationAnswer` / `paipaiInterpretationStockDetailList` 两个字段恒为 null，仅 topic/detail 有值。

---

## 3. 获取蓝宝书话题详情

`POST /open-api/v1/blue/books/topic/detail`

### 请求参数（Body）

| 字段 | 类型 | 必填 | 说明 |
|---|---|---|---|
| `topicId` | long | 是 | 话题 id（国内/全球 id 空间不同） |
| `batchScope` | string | 是 | `domestic` 或 `global` |

### 调用示例

```bash
# 国内
curl -X POST "$BASE/open-api/v1/blue/books/topic/detail" \
  -H "Content-Type: application/json" \
  -d '{ "topicId": 9269, "batchScope": "domestic" }'

# 全球
curl -X POST "$BASE/open-api/v1/blue/books/topic/detail" \
  -H "Content-Type: application/json" \
  -d '{ "topicId": 770, "batchScope": "global" }'
```

### 响应数据：`BlueBookTopicVO`

国内话题通常含 `paipaiInterpretationAnswer` / `paipaiInterpretationStockDetailList`；全球话题这两项一般为 `null`。

---

## 附：BlueBookBatchVO

| 字段 | 类型 | 说明 |
|---|---|---|
| `batchId` | long | 批次 id |
| `batchSeq` | int | 批次序号 |
| `batchTitle` | string | 批次标题（为内容摘要式长标题，非"早报/午报"式名称） |
| `batchDate` | string | 批次日期 |
| `batchScope` | string | 市场范围 |
| `batchScopeLabel` | string | 市场范围中文 |
| `batchType` | string | 批次类型 |
| `batchTypeLabel` | string | 批次类型中文 |

## 完整响应示例

批次列表：

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
      "batchId": 10001,
      "batchSeq": 1,
      "batchTitle": "示例蓝宝书批次标题",
      "batchDate": "2026-08-02",
      "batchScope": "domestic",
      "batchScopeLabel": "国内",
      "batchType": "evening",
      "batchTypeLabel": "晚报",
      "batchPublishedTime": "2026-08-02T20:06:21",
      "batchAudioDurationSeconds": 600,
      "batchAudioDurationLabel": "10分钟",
      "topicCount": 1,
      "topicList": [{"topicId": 20001, "topicName": "示例话题"}]
    }]
  }
}
```

国内话题详情：

```json
{
  "code": 200000,
  "message": "success",
  "data": {
    "topicId": 20001,
    "topicName": "示例话题",
    "date": "2026-08-02",
    "scope": "domestic",
    "summary": "话题摘要",
    "sourceReason": "来源与热度说明",
    "heatLevel": 10,
    "stockTag": null,
    "paipaiInterpretationAnswer": "PaiPai 解读正文",
    "paipaiInterpretationStockDetailList": [{
      "id": 1,
      "firstLevel": "一级分类",
      "secondLevel": "二级分类",
      "marketValue": "100亿元",
      "reason": "入选理由",
      "extraColumn1": null,
      "extraColumn2": "扩展值",
      "extraColumn3": null,
      "extraColumn4": "扩展值",
      "originStarNum": "3",
      "code": "600519.SH",
      "name": "贵州茅台"
    }],
    "batchId": 10001,
    "batchTitle": "示例蓝宝书批次标题",
    "batchType": "evening",
    "batchTypeLabel": "晚报"
  }
}
```

2026-08-02 当前 CLI 的 `batch-list`、`topic-list`、`topic-detail` 均实测 `200000`。实际 `topic/list` 的 `paipaiInterpretationAnswer` 与 `paipaiInterpretationStockDetailList` 为 null，而国内 `topic/detail` 返回对象数组；详情的 `stockTag` 反而可能为 null。
| `batchPublishedTime` | string | 发布时间（ISO 格式，如 `2026-08-01T20:06:21`；周末也发布，非仅交易日） |
| `batchAudioDurationSeconds` | int | 音频时长（秒） |
| `batchAudioDurationLabel` | string | 音频时长文案 |
| `topicCount` | int | 话题数量 |
| `topicList` | array | `{topicId, topicName}` |

## 附：BlueBookTopicVO

| 字段 | 类型 | 说明 |
|---|---|---|
| `topicId` | long | 话题 id |
| `topicName` | string | 话题名称 |
| `date` | string | 日期 |
| `scope` | string | 市场范围 |
| `summary` | string | 摘要 |
| `sourceReason` | string | 来源理由/详情 |
| `heatLevel` | int | 热度 |
| `stockTag` | array&lt;{code,name}&gt; | 关联股票（可为 null：topic/detail 当前恒为 null，即使 topic/list 中有股票） |
| `paipaiInterpretationAnswer` | string | 派派解读正文 |
| `paipaiInterpretationStockDetailList` | array | 派派解读个股明细（**对象数组，非字符串数组**；每项含 `id` / `firstLevel` / `secondLevel` / `marketValue` / `reason` / `code` / `name` / `originStarNum` / `extraColumn1`-`extraColumn4`） |
| `batchId` | long | 批次 id |
| `batchTitle` | string | 批次标题 |
| `batchType` | string | 批次类型 |
| `batchTypeLabel` | string | 批次类型中文 |
