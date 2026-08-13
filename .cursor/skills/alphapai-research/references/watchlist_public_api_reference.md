# 自选股开放 API 接口文档

## 目录

- [接口清单](#接口清单)
- [关注与取关](#1-批量关注个股)
- [列表、存在性与数量](#3-查询关注股票列表)
- [分组管理](#6-查询自选分组列表)
- [完整字段与注意事项](#附stockfollowapivo)

# 自选股开放 API 接口文档

> 模块：`alpha-open-api-service`；Controller：`StockFollowController`；路径前缀：`/open-api/v1/stock/follow`
> 下文 curl 示例统一使用：`BASE=https://<网关域名>/alpha`（需携带开放平台鉴权头）。

---

## 通用约定

### 统一返回体 `Result<T>`

| 字段 | 类型 | 说明 |
|---|---|---|
| `code` | int | 业务码，成功为 `200000` |
| `message` | string | 提示信息 |
| `data` | T | 业务数据 |

下文「响应数据」仅描述 `data` 部分。写操作返回 `Result<Boolean>`，`data=true` 表示成功。

### 鉴权


### 接口清单

| # | HTTP | 路径 | 说明 |
|---|---|---|---|
| 1 | POST | `/follow/multi` | 批量关注个股 |
| 2 | POST | `/unfollow/multi` | 批量取消关注个股 |
| 3 | POST | `/list` | 查询关注股票列表 |
| 4 | GET | `/exist` | 查询某个股是否已自选 |
| 5 | GET | `/num` | 查询关注股票数量 |
| 6 | GET | `/group/list` | 查询自选分组列表 |
| 7 | POST | `/group/add` | 添加自选分组 |
| 8 | POST | `/group/delete` | 删除自选分组 |

---

## 1. 批量关注个股

`POST /open-api/v1/stock/follow/follow/multi`  
Body：`StockFollowBatchApiRequest`

### 请求参数

| 字段 | 位置 | 类型 | 必填 | 说明 |
|---|---|---|---|---|
| `stockCodes` | Body | array&lt;string&gt; | 是 | 个股编码列表 |
| `groupCode` | Body | string | 否 | 分组编码，为空进默认分组 |

### 调用示例

```bash
curl -X POST "$BASE/open-api/v1/stock/follow/follow/multi" \
  -H "Content-Type: application/json" \
  -d '{ "stockCodes": ["600519.SH", "000858.SZ"], "groupCode": "grp_001" }'
```

### 响应示例

```json
{ "code": 200000, "message": "success", "data": true }
```

---

## 2. 批量取消关注个股

`POST /open-api/v1/stock/follow/unfollow/multi`  
Body：`StockFollowBatchApiRequest`

### 请求参数

| 字段 | 位置 | 类型 | 必填 | 说明 |
|---|---|---|---|---|
| `stockCodes` | Body | array&lt;string&gt; | 是 | 个股编码列表（按编码批量取关） |
| `groupCode` | Body | string | 否 | 分组编码，取关时一般可不传 |

### 调用示例

```bash
curl -X POST "$BASE/open-api/v1/stock/follow/unfollow/multi" \
  -H "Content-Type: application/json" \
  -d '{ "stockCodes": ["600519.SH"] }'
```

### 响应示例

```json
{ "code": 200000, "message": "success", "data": true }
```

---

## 3. 查询关注股票列表

`POST /open-api/v1/stock/follow/list`  
Body：`StockFollowQueryApiRequest`

### 请求参数

| 字段 | 位置 | 类型 | 必填 | 说明 |
|---|---|---|---|---|
| `groupCode` | Body | string | 否 | 分组编码，为空查询全部 |
| `checkGroup` | Body | boolean | 否 | 是否校验分组 |

### 调用示例

```bash
curl -X POST "$BASE/open-api/v1/stock/follow/list" \
  -H "Content-Type: application/json" \
  -d '{ "groupCode": "grp_001", "checkGroup": true }'
```

### 响应数据：`List<StockFollowApiVO>`

字段见 [附：StockFollowApiVO](#附stockfollowapivo)。

### 响应示例

```json
{
  "code": 200000,
  "message": "success",
  "data": [
    {
      "stockCode": "600519.SH",
      "stockName": "贵州茅台",
      "groupCode": "grp_001",
      "groupName": null,
      "inGroup": null
    }
  ]
}
```

---

## 4. 查询某个股是否已自选

`GET /open-api/v1/stock/follow/exist`

### 请求参数（Query）

| 字段 | 类型 | 必填 | 说明 |
|---|---|---|---|
| `stockCode` | string | 是 | 个股编码 |

### 调用示例

```bash
curl -X GET "$BASE/open-api/v1/stock/follow/exist?stockCode=600519.SH"
```

### 响应数据：`List<StockFollowApiVO>`

返回该个股命中的自选记录（可能分布在多个分组）；为空表示未自选。

```json
{
  "code": 200000,
  "message": "success",
  "data": [{
    "stockCode": "600519.SH",
    "stockName": "贵州茅台",
    "groupCode": "grp_001",
    "groupName": null,
    "inGroup": null
  }]
}
```

---

## 5. 查询关注股票数量

`GET /open-api/v1/stock/follow/num`

### 请求参数

无业务参数，用户态由网关注入。

### 调用示例

```bash
curl -X GET "$BASE/open-api/v1/stock/follow/num"
```

### 响应示例

```json
{ "code": 200000, "message": "success", "data": 12 }
```

---

## 6. 查询自选分组列表

`GET /open-api/v1/stock/follow/group/list`

### 请求参数

无业务参数，用户态由网关注入。

### 调用示例

```bash
curl -X GET "$BASE/open-api/v1/stock/follow/group/list"
```

### 响应数据：`List<StockGroupApiVO>`

| 字段 | 类型 | 说明 |
|---|---|---|
| `groupId` | int | 分组 ID |
| `groupCode` | string | 分组编码 |
| `groupName` | string | 分组名称 |

### 响应示例

```json
{
  "code": 200000,
  "message": "success",
  "data": [
    { "groupId": 1, "groupCode": "grp_001", "groupName": "白马股" }
  ]
}
```

---

## 7. 添加自选分组

`POST /open-api/v1/stock/follow/group/add`  
Body：`StockGroupAddApiRequest`

### 请求参数

| 字段 | 位置 | 类型 | 必填 | 说明 |
|---|---|---|---|---|
| `groupName` | Body | string | 是 | 分组名称 |

### 调用示例

```bash
curl -X POST "$BASE/open-api/v1/stock/follow/group/add" \
  -H "Content-Type: application/json" \
  -d '{ "groupName": "新能源" }'
```

### 响应示例

```json
{ "code": 200000, "message": "success", "data": true }
```

---

## 8. 删除自选分组

`POST /open-api/v1/stock/follow/group/delete`  
Body：`List<String>`（分组编码列表）

> 删除分组会**连带删除组内关注**。

### 请求参数

| 字段 | 位置 | 类型 | 必填 | 说明 |
|---|---|---|---|---|
| `groupCodes` | Body | array&lt;string&gt; | 是 | 分组编码列表 |

### 调用示例

```bash
curl -X POST "$BASE/open-api/v1/stock/follow/group/delete" \
  -H "Content-Type: application/json" \
  -d '["grp_001", "grp_002"]'
```

### 响应数据：`Integer`（删除的分组数量）

### 响应示例

```json
{ "code": 200000, "message": "success", "data": 2 }
```

---

## 典型调用时序

```
6 分组列表 → 1 批量关注(指定 groupCode) → 3 关注列表 / 4 查某股是否自选 / 5 关注数量
```

---

## 附：StockFollowApiVO

| 字段 | 类型 | 说明 |
|---|---|---|
| `stockCode` | string | 个股编码 |
| `stockName` | string | 个股名称 |
| `groupCode` | string | 分组编码 |
| `groupName` | string/null | 分组名称；当前 list/exist 实测为 null |
| `inGroup` | boolean/null | 是否在目标分组；只在特定 `checkGroup` 查询中可能有值 |

---

## 注意事项

- **list/exist 响应中 `groupName` 当前实测为 `null`**；`inGroup` 仅在 list 且 `checkGroup=true` 时可能有值。
- **list 传 `checkGroup=true` 时，多分组股票只返回一条**，其 `groupCode` 为多个分组编码的逗号合并串。
- **list 不传 `groupCode` 键时返回全部关注（按股去重，每股只显示一个分组）；传 `groupCode=""` 空串会按字面匹配而返回空列表**——请勿传空串，要查全部就不传该键。
- **num 统计的是"股票×分组"关注记录数**，而非唯一股票数（例如 33 只唯一股票分布于多个分组时 num=36）。
- **group/list 不含默认分组**，仅返回用户自定义分组。
- **写接口（follow/unfollow/group add/delete）有未文档化频控**：连续调用可能返回 `400000 操作过于频繁`，需自行限速/重试。
- **unfollow 的 `groupCode` 作用域**：不传＝从所有分组移除该股票；传＝仅移除该分组中的关注。
- **group/delete 删除不存在的分组编码也返回 `data:1`**，返回值不完全可信，不能据此判断分组曾存在。
- **关注已在自定义分组的股票进默认分组是静默 no-op**（返回成功但不产生新记录）。
- **分组名称长度限制：`groupName` 不超过 10 个字**，超限返回 `400001 分组名称不超过10个字`。
- **实测状态**：2026-08-02 当前 CLI 的 list/exist/num/group-list 均返回 `200000`；follow/unfollow/group-add/group-delete 已使用临时分组与临时关注做过可逆验证并清理。
