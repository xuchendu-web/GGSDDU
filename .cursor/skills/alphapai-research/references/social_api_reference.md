# 社媒订阅 API 参考

## 目录

- [接口清单](#接口清单)
- [公众号列表、订阅与取消](#1-查询现有可订阅公众号列表)
- [文章列表与账号搜索](#5-查询社媒文章主列表)
- [公众号与文章详情](#7-查询公众号详情)
- [完整结构体](#附wechataccountapivo)

> 模块：`alpha-open-api-service`  
> Controller：`SocialMediaController`  
> 路径前缀：`/open-api/v1/social/media`

---

## 通用约定

### 统一返回体 `Result<T>`

| 字段 | 类型 | 说明 |
|---|---|---|
| `code` | int | 业务码，成功为 `200000` |
| `message` | string | 提示信息 |
| `data` | T | 业务数据 |

下文「响应数据」仅描述 `data` 部分。

### 分页返回体 `PageResult<T>`

| 字段 | 类型 | 说明 |
|---|---|---|
| `pageNum` | int | 当前页码 |
| `pageSize` | int | 每页数量 |
| `totalPageNum` | int | 总页数 |
| `totalSize` | long | 总条数 |
| `data` | array&lt;T&gt; | 结果列表 |

### 鉴权 / 用户态

- 用户态由网关注入的 **`@CurrentApp CurrentAppInfo`** 获取，取 `currentAppInfo.getUserUid()` 作为 `userId`。
- 调用方无需再传 Query 参数 `userId`。
- 下文 curl 示例统一使用：`BASE=https://<网关域名>`（需携带开放平台鉴权头）。

### 接口清单

| # | HTTP | 路径 | CLI | 说明 |
|---|---|---|---|---|
| 1 | GET | `/account/list` | `social account-list` | 查询可订阅公众号列表 |
| 2 | POST | `/subscribe` | `social subscribe` | 按 id 批量订阅 |
| 3 | POST | `/unsubscribe` | `social unsubscribe` | 按 id 批量取消订阅 |
| 4 | GET | `/subscribe/list` | `social subscribe-list` | 查询已订阅公众号列表 |
| 5 | POST | `/article/list` | `social article-list` | 查询社媒文章主列表 |
| 6 | GET | `/account/search` | `social account-search` | 搜索公众号账号 |
| 7 | GET | `/account/detail` | `social account-detail` | 查询公众号详情 |
| 8 | GET | `/article/detail` | `social article-detail` | 查询公众号文章详情 |

---

## 1. 查询现有（可订阅）公众号列表

`GET /open-api/v1/social/media/account/list`

### 请求参数

无业务参数，用户态由网关注入。

### 调用示例

```bash
curl -X GET "$BASE/open-api/v1/social/media/account/list"
```

### 响应数据：`List<WechatAccountApiVO>`

字段见 [附：WechatAccountApiVO](#附wechataccountapivo)。

> 注意：返回为非确定性子集（约 100 个，两次调用的数量/成员可能不同，不代表可订阅账号全集）；`isSubscribed` 标记有刷新延迟，订阅/取消后短期内可能未更新。

### 响应示例

```json
{
  "code": 200000,
  "message": "success",
  "data": [
    {
      "id": "gh_abc123",
      "supplierId": "sup_001",
      "name": "某券商策略",
      "logo": "https://s3.example.com/logo/gh_abc123.png",
      "description": "每日策略观点",
      "url": "https://mp.weixin.qq.com/xxx",
      "isDeleted": 0,
      "isSubscribed": false,
      "isStar": false
    }
  ]
}
```

---

## 2. 按 id 批量订阅公众号

`POST /open-api/v1/social/media/subscribe`  
Body：`List<String>`（公众号 id 列表）

> 仅订阅 ES 中存在的账号；未命中 id 会放入 `notExist`，不做远程补全。

### 请求参数

| 字段 | 位置 | 类型 | 必填 | 说明 |
|---|---|---|---|---|
| `ids` | Body | array&lt;string&gt; | 是 | 公众号 id 列表 |

### 调用示例

```bash
curl -X POST "$BASE/open-api/v1/social/media/subscribe" \
  -H "Content-Type: application/json" \
  -d '["gh_abc123", "gh_def456", "gh_not_in_es"]'
```

### 响应数据：`SocialMediaCountVO`

| 字段 | 类型 | 订阅语义 |
|---|---|---|
| `subscribe` | array&lt;string&gt; | 新订阅成功的 id |
| `existInSubscribe` | array&lt;string&gt; | 已订阅、无需重复订阅的 id |
| `notExist` | array&lt;string&gt; | ES 未命中、被忽略的 id |

### 响应示例

```json
{
  "code": 200000,
  "message": "success",
  "data": {
    "subscribe": ["gh_abc123"],
    "existInSubscribe": ["gh_def456"],
    "notExist": ["gh_not_in_es"]
  }
}
```

---

## 3. 按 id 批量取消订阅公众号

`POST /open-api/v1/social/media/unsubscribe`  
Body：`List<String>`（公众号 id 列表）

### 请求参数

| 字段 | 位置 | 类型 | 必填 | 说明 |
|---|---|---|---|---|
| `ids` | Body | array&lt;string&gt; | 是 | 公众号 id 列表 |

### 调用示例

```bash
curl -X POST "$BASE/open-api/v1/social/media/unsubscribe" \
  -H "Content-Type: application/json" \
  -d '["gh_abc123", "gh_def456"]'
```

### 响应数据：`SocialMediaCountVO`

| 字段 | 类型 | 取消语义 |
|---|---|---|
| `subscribe` | array&lt;string&gt; | 成功取消的 id |
| `existInSubscribe` | array&lt;string&gt; | 本就未订阅的 id |
| `notExist` | array&lt;string&gt; | ES 未命中、被忽略的 id |

### 响应示例

```json
{
  "code": 200000,
  "message": "success",
  "data": {
    "subscribe": ["gh_abc123"],
    "existInSubscribe": ["gh_def456"],
    "notExist": []
  }
}
```

---

## 4. 查询订阅的公众号列表

`GET /open-api/v1/social/media/subscribe/list`

### 请求参数（Query）

| 字段 | 类型 | 必填 | 说明 |
|---|---|---|---|
| `isStar` | boolean | 否 | 是否只查星标；不传查全部 |

### 调用示例

```bash
# 查全部订阅
curl -X GET "$BASE/open-api/v1/social/media/subscribe/list"

# 只查星标
curl -X GET "$BASE/open-api/v1/social/media/subscribe/list?isStar=true"
```

### 响应数据：`List<WechatAccountApiVO>`

字段见 [附：WechatAccountApiVO](#附wechataccountapivo)。

---

## 5. 查询社媒文章主列表

`POST /open-api/v1/social/media/article/list`  
Body：`SocialMediaKnowledgeListRequest`

### 请求参数

| 字段 | 位置 | 类型 | 必填 | 说明 |
|---|---|---|---|---|
| `pageNum` | Body | int | 是 | 当前页码，从 1 开始 |
| `pageSize` | Body | int | 是 | 每页数量，最大 100 |
| `word` | Body | string | 否 | 搜索词 |
| `industry` | Body | array&lt;string&gt; | 否 | 行业编码列表 |
| `stock` | Body | array&lt;string&gt; | 否 | 股票代码列表 |
| `institution` | Body | array&lt;string&gt; | 否 | 机构编码列表 |
| `startDate` | Body | string(date) | 否 | 开始日期，`yyyy-MM-dd` |
| `endDate` | Body | string(date) | 否 | 结束日期，`yyyy-MM-dd` |
| `sourceName` | Body | string | 否 | 来源名称 |
| `psnWrite` | Body | int | 否 | 业务类型：`1`-券商公众号，`2`-产业研究，`3`-公司官方 |
| `excludeContent` | Body | boolean | 否 | 是否排除 content 字段（性能优化）。**注意：当前服务端未生效，传 true 正文仍全量返回** |

### 调用示例

```bash
curl -X POST "$BASE/open-api/v1/social/media/article/list" \
  -H "Content-Type: application/json" \
  -d '{
    "pageNum": 1,
    "pageSize": 10,
    "word": "新能源",
    "startDate": "2026-06-01",
    "endDate": "2026-06-30",
    "excludeContent": true
  }'
```

### 响应数据：`PageResult<SocialMediaApiPageVO>`

列表元素字段见 [附：SocialMediaApiPageVO](#附socialmediaapipagevo)。

### 响应示例

```json
{
  "code": 200000,
  "message": "success",
  "data": {
    "pageNum": 1,
    "pageSize": 10,
    "totalPageNum": 5,
    "totalSize": 48,
    "data": [
      {
        "id": "art_001",
        "title": "新能源行业周报",
        "url": "https://mp.weixin.qq.com/s/xxx",
        "publishDate": "2026-06-28 09:00:00",
        "accountId": "gh_abc123",
        "accountName": "某券商策略",
        "accountLogo": "https://s3.example.com/logo/gh_abc123.png",
        "label": ["周报", "行业"],
        "selected": 1,
        "isSubscribed": true,
        "isStar": false
      }
    ]
  }
}
```

---

## 6. 搜索公众号账号

`GET /open-api/v1/social/media/account/search`

### 请求参数（Query）

| 字段 | 类型 | 必填 | 说明 |
|---|---|---|---|
| `word` | string | 是 | 搜索词 |
| `pageNum` | int | 否 | 页码，默认 `1` |
| `pageSize` | int | 否 | 每页条数，默认 `20` |

### 调用示例

```bash
curl -X GET "$BASE/open-api/v1/social/media/account/search?word=策略&pageNum=1&pageSize=20"
```

### 响应数据：`List<WechatAccountApiVO>`

字段见 [附：WechatAccountApiVO](#附wechataccountapivo)。

---

## 7. 查询公众号详情

`GET /open-api/v1/social/media/account/detail`

### 请求参数（Query）

| 字段 | 类型 | 必填 | 说明 |
|---|---|---|---|
| `id` | string | 是 | 公众号 id |
| `supplierId` | string | 否 | 供应商 id；列表常返回 null，不传时 CLI 发送字符串 `"null"` 选择默认供应商 |

### 调用示例

```bash
curl -X GET "$BASE/open-api/v1/social/media/account/detail?id=RWX100000004300&supplierId=null"
```

### 响应数据：`WechatAccountApiVO`

字段见 [附：WechatAccountApiVO](#附wechataccountapivo)。

2026-08-02 实测不显式提供 `--supplier-id` 可成功返回完整公众号详情；响应中的真实 `supplierId` 由服务端补全。

---

## 8. 查询公众号文章详情

`GET /open-api/v1/social/media/article/detail`

### 请求参数（Query）

| 字段 | 类型 | 必填 | 说明 |
|---|---|---|---|
| `id` | string | 是 | 文章 id |
| `supplierId` | string | 否 | 文章供应商 id；列表不返回该字段时不传，CLI 发送字符串 `"null"` |

### 调用示例

```bash
curl -X GET "$BASE/open-api/v1/social/media/article/detail?id=RAR100001614105&supplierId=null"
```

### 响应数据：`WechatAccountArticleApiVO`

字段见 [附：WechatAccountArticleApiVO](#附wechataccountarticleapivo)。

### 响应示例

```json
{
  "code": 200000,
  "message": "success",
  "data": {
    "id": "art_001",
    "supplierId": "sup_001",
    "url": "https://mp.weixin.qq.com/s/xxx",
    "title": "新能源行业周报",
    "publishDate": "2026-06-28 09:00:00",
    "accountId": "gh_abc123",
    "accountSupplierId": "sup_001",
    "accountLogo": "https://s3.example.com/logo/gh_abc123.png",
    "accountName": "某券商策略",
    "content": "<p>文章正文</p>",
    "label": ["周报", "行业"],
    "industry": [
      { "code": "industry_code", "name": "新能源" }
    ],
    "stock": [
      { "code": "000001", "name": "示例股票" }
    ],
    "selected": 1,
    "isSubscribed": true,
    "isStar": false,
    "selectedRecommendContent": null,
    "selectedRecommendPic": null,
    "isDeleted": 0,
    "originUrl": "https://mp.weixin.qq.com/s/xxx",
    "html": "/article/001.html"
  }
}
```

---

## 典型调用时序

```
1 现有公众号列表(拿 id) → 2 按 id 批量订阅 → 4 我的订阅列表 / 5 文章主列表 → 8 文章详情
```

---

## 附：WechatAccountApiVO

| 字段 | 类型 | 说明 |
|---|---|---|
| `id` | string | 公众号账号 id |
| `supplierId` | string/null | 供应商 id；列表/搜索常为 null，详情通常为 string |
| `name` | string | 公众号名称 |
| `logo` | string | 公众号图标 url |
| `description` | string/null | 公众号描述 |
| `url` | string/null | 公众号 url |
| `isDeleted` | int/null | 是否删除 |
| `isSubscribed` | boolean | 是否已订阅 |
| `isStar` | boolean | 是否星标 |

---

## 附：SocialMediaApiPageVO

| 字段 | 类型 | 说明 |
|---|---|---|
| `id` | string | 文章 ID |
| `title` | string | 文章标题 |
| `content` | string | 正文内容（`excludeContent=true` 时为空——**当前服务端未生效，正文仍返回**） |
| `url` | string | 正文 URL |
| `originUrl` | string | origin URL |
| `publishDate` | string | 发布时间，`yyyy-MM-dd HH:mm:ss` |
| `accountId` | string | 公众号 ID |
| `accountLogo` | string | 公众号头像 URL |
| `accountName` | string | 公众号名称 |
| `label` | array&lt;string&gt; | 标签集合 |
| `industry` | array&lt;{code,name}&gt; | 行业列表 |
| `stock` | array&lt;{code,name}&gt;/null | 关联股票 |
| `selected` | int | 是否精选，`1`-精选，`0`-普通 |
| `isSubscribed` | boolean | 当前用户是否订阅 |
| `isStar` | boolean | 当前用户是否星标 |
| `isDeleted` | int | 是否删除标记 |
| `html` | string | HTML 内部路径地址（文章列表也返回该字段） |

---

## 附：WechatAccountArticleApiVO

| 字段 | 类型 | 说明 |
|---|---|---|
| `id` | string | 文章 id |
| `supplierId` | string | 文章供应商 id |
| `url` | string | 正文 URL |
| `originUrl` | string/null | 原始正文 URL；部分详情响应不返回该字段 |
| `title` | string | 文章标题 |
| `publishDate` | string | 发布时间，格式 `yyyy-MM-dd HH:mm:ss`，时区 GMT+8 |
| `accountId` | string | 公众号 id |
| `accountSupplierId` | string | 公众号供应商 id |
| `accountLogo` | string | 公众号头像 URL |
| `accountName` | string | 公众号名称 |
| `content` | string | 正文内容 |
| `label` | array&lt;string&gt; | 标签集合 |
| `industry` | array&lt;{code,name}&gt; | 行业列表 |
| `stock` | array&lt;{code,name}&gt;/null | 关联股票 |
| `selected` | int | 是否精选，`1`-精选、`0`-普通 |
| `isSubscribed` | boolean | 当前用户是否已订阅该公众号 |
| `isStar` | boolean | 当前用户是否已星标 |
| `selectedRecommendContent` | string/null | 精选推荐内容 |
| `selectedRecommendPic` | string/null | 精选推荐图片 |
| `isDeleted` | int | 是否删除 |
| `html` | string | HTML 内部路径地址 |


---

## 附：SocialMediaCountVO 分组语义

| 字段 | 订阅语义 | 取消语义 |
|---|---|---|
| `subscribe` | 新订阅 | 成功取消 |
| `existInSubscribe` | 已订阅 | 本就未订阅 |
| `notExist` | ES 未命中 | ES 未命中 |
