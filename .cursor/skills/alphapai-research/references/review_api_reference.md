# 点评开放 API 接口文档

> 模块：`alpha-open-api-service`  
> Controller：`CommentsController`  
> 路径前缀：`/open-api/v1/comments`  
> 下游：`/alpha/api/openpai/api/v1/alpha-pai/comment`  
> 说明：当前已对接文档第 1、2、3 个接口（搜索点评列表、查看点评详情、业绩点评专属列表）

---

## 通用约定

- 成功码：`200000`
- 用户态：`@CurrentApp` 取 `userUid`，写入请求体 `userId`，并透传 Header `X-User-Id`
- 下游调用失败会进入 `handleInvokeFailure` 扩展点，后续可补业务

### 接口清单

| # | HTTP | 开放路径 | 下游路径 | 说明 |
|---|---|---|---|---|
| 1 | POST | `/list` | `/searchCommentList` | 搜索点评列表 |
| 2 | POST | `/detail` | `/viewCommentDetail` | 查看点评详情 |
| 3 | POST | `/event/list` | `/searchCommentEventList` | 业绩点评专属列表 |

---

## 1. 搜索点评列表

`POST /open-api/v1/comments/list`

### 主要入参

| 字段 | 类型 | 说明 |
|---|---|---|
| `commentScope` | string | `all` / `valuable` / `regular` |
| `keyword` | string | 匹配标题/正文 |
| `startDate` / `endDate` | string | `yyyy-MM-dd`；都不传默认最近 30 天 |
| `industryCode` / `industryName` | array | 行业筛选（组内 OR） |
| `subjectCode` / `subjectName` | array | 题材筛选（组内 OR） |
| `stockCombSymbol` / `stockName` | array | 股票筛选（组内 OR） |
| `page` / `pageSize` | int | 分页 |

行业、题材、股票三组之间为 AND。

### 出参

`PageResult<CommentsVO>`：含 `commentId`、`title`、`content`、时间、范围及各类标签。

---

## 2. 查看点评详情

`POST /open-api/v1/comments/detail`

### 入参

| 字段 | 类型 |必填 | 说明 |
|---|---|---|---|
| `commentId` | array | 是 | 点评 ID |

### 出参

`CommentsVO`：与列表项字段一致；`content` 为完整正文。

---

## 3. 业绩点评专属列表

`POST /open-api/v1/comments/event/list`

### 主要入参

| 字段 | 类型 | 说明 |
|---|---|---|
| `marketScope` | string | `ah` / `a` / `hk` |
| `eventType` | array | `performance_forecast` / `performance_flash` / `performance_report` |
| `stockCombSymbol` | array | 股票代码过滤 |
| `startDate` / `endDate` | string | 日期范围 |
| `page` / `pageSize` | int | 分页 |

### 出参

`PageResult<CommentsEventVO>`：含 `eventId`、`title`、`stock`、市场/事件类型及 `commentCount`。