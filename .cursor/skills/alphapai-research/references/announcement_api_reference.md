# 公告 API 参考

面向 AI/Agent 的公告调用契约。用户说明见 `doc/公告.md`。

## 目录

- [接口清单](#接口清单)
- [1. 查询公告列表](#1-查询公告列表)
- [2. 下载公告 PDF](#2-下载公告-pdf)
- [3. 下载公告解析结果](#3-下载公告解析结果)
- [调用顺序与错误处理](#调用顺序与错误处理)

## 接口清单

| 功能 | HTTP | 完整路径 | CLI |
|---|---|---|---|
| 查询公告列表 | POST | `/alpha/open-api/v1/announcement/list` | `announcement list` |
| 下载公告 PDF | POST | `/alpha/open-api/v1/announcement/pdf/download` | `announcement pdf-download` |
| 下载公告解析结果 | POST | `/alpha/open-api/v1/common/parsing/download` | `announcement parsing-download` |

统一 JSON 信封：`{"code":200000,"message":"success","data":...}`。两个下载接口使用列表实时返回的 `announcementId`；该 ID 是加密时效串，不可拼造或长期保存。

## 1. 查询公告列表

### 请求

| JSON 字段 | CLI 参数 | 类型 | 必填 | 约束 |
|---|---|---|---|---|
| `pageNum` | `--page-num` | integer | 否 | 默认 1 |
| `pageSize` | `--page-size` | integer | 否 | 默认 20，范围 1–100 |
| `keyword` | `--keyword` | string | 否 | 标题短语匹配 |
| `endDateFrom` / `endDateTo` | `--end-date-from` / `--end-date-to` | string | 否 | 报告期，`yyyy-MM-dd` |
| `publishFrom` / `publishTo` | `--publish-from` / `--publish-to` | string | 否 | 按 `actualPublishTime` 过滤 |
| `industryCode` / `industryName` | `--industry-code` / `--industry-name` | string[] | 否 | 数组内 OR |
| `stockCode` / `stockName` | `--stock-code` / `--stock-name` | string[] | 否 | 数组内 OR |
| `market` | `--market` | string[] | 否 | `A` / `HK` / `US` |
| `announcementTypeCode` / `announcementType` | `--type-code` / `--type-name` | string[] | 否 | 公告类型过滤 |
| `sortBy` | `--sort-by` | string | 否 | `actual_publish_time` / `publish_time` / `end_date` / `score` |
| `sortOrder` | `--sort-order` | string | 否 | `asc` / `desc` |

### 返回

`data` 为分页对象：

| 字段 | 类型 | 说明 |
|---|---|---|
| `pageNum` / `pageSize` | integer | 当前页与每页数量 |
| `totalPageNum` / `totalSize` | integer | 总页数与总条数 |
| `data` | `Announcement[]` | 公告列表 |

`Announcement` 完整字段：

| 字段 | 类型 | nullable | 说明 |
|---|---|---:|---|
| `announcementId` | string | 否 | 后续 PDF/解析结果下载使用的时效 ID |
| `title` | string | 否 | 公告标题 |
| `publishTime` | string | 否 | 名义发布时间，`yyyy-MM-dd HH:mm:ss` |
| `actualPublishTime` | string | 否 | 实际发布/入库时间 |
| `endDate` | string | 否 | 报告期 |
| `announcementType` | string | 是 | 公告类型名称 |
| `announcementTypeCode` | string | 是 | 公告类型编码 |
| `market` | string | 否 | `A` / `HK` / `US` |
| `stockTag` | `{code:string,name:string}[]` | 是 | 关联股票 |
| `industryTag` | `{code:string,name:string}[]` | 是 | 关联行业 |
| `hasPdf` | boolean | 否 | 是否可下载 PDF |

实际响应结构示例（2026-08-02 验证）：

```json
{
  "code": 200000,
  "message": "success",
  "data": {
    "pageNum": 1,
    "pageSize": 1,
    "totalPageNum": 570,
    "totalSize": 570,
    "data": [{
      "announcementId": "<实时加密ID>",
      "title": "贵州茅台(600519.SH):贵州茅台重大事项公告",
      "publishTime": "2026-07-18 00:00:00",
      "actualPublishTime": "2026-07-17 23:35:20",
      "endDate": "2026-07-18 00:00:00",
      "announcementType": "日常经营其他",
      "announcementTypeCode": "010910",
      "market": "A",
      "stockTag": [{"code": "600519.SH", "name": "贵州茅台"}],
      "industryTag": [{"code": "HINDUSTRY00000001028", "name": "食品饮料"}],
      "hasPdf": true
    }]
  }
}
```

## 2. 下载公告 PDF

请求体：`{"id":"<announcementId>"}`。成功响应为 PDF 文件流，不是 JSON。

```bash
python scripts/alphapai_client.py announcement pdf-download \
  --id '<ANNOUNCEMENT_ID>' --output ./announcement.pdf
```

实测文件：PDF 1.7、67,261 bytes、magic `%PDF-1.7`。错误时即使 HTTP 为 200，也可能返回含 `code` 和 `message`/`msg` 的 JSON 信封，CLI 会拒绝把它保存成 PDF。

## 3. 下载公告解析结果

公共端点请求体：

```json
{
  "documentId": "<announcementId>",
  "documentType": "announcement",
  "downloadType": "markdown"
}
```

| 字段 | 类型 | 必填 | 取值 |
|---|---|---|---|
| `documentId` | string | 是 | 实时公告 ID |
| `documentType` | string | 是 | 公告固定为 `announcement` |
| `downloadType` | string | 是 | `markdown` / `json` / `zip` |

```bash
python scripts/alphapai_client.py announcement parsing-download \
  --id '<ANNOUNCEMENT_ID>' --download-type json --output ./announcement.json
```

实测产物（同一公告、2026-08-02）：

| 类型 | 实际格式 | 观察结果 |
|---|---|---|
| `markdown` | UTF-8 Markdown | 781 bytes，标题和完整正文 |
| `json` | JSON array | 1,193 bytes，共 5 个内容元素 |
| `zip` | ZIP | 4,766 bytes，4 个文件，`unzip -t` 通过 |

JSON 内容元素不是统一固定字段；文本元素实测为：

```json
{
  "type": "text",
  "text": "贵州茅台酒股份有限公司重大事项公告",
  "text_level": 1,
  "page_idx": 0
}
```

`text_level` 只在标题类文本中出现，AI 解析时必须按 `type` 分支并容忍可选字段。ZIP 实测包含 `*_middle.json`、`*_model.json`、`*.md`、`*_content_list.json`。

## 调用顺序与错误处理

1. 调 `announcement list` 获取实时 ID。
2. 检查 `hasPdf`；需要原文时调用 `pdf-download`。
3. 需要完整解析文本/结构时调用 `parsing-download`。
4. 解析结果尚未生成时可能返回 `400000`；换公告或稍后重试，不要把错误 JSON 当文件。
