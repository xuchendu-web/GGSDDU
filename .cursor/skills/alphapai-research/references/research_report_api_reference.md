# 机构研报 API 参考

机构研报支持检索、详情、PDF 与解析结果下载。路径前缀 `/alpha/open-api/v1/report`；解析下载使用公共路径 `/alpha/open-api/v1/common/parsing/download`。

## 目录

- [接口清单](#接口清单)
- [1. 搜索机构研报](#1-搜索机构研报)
- [2. 机构研报详情](#2-机构研报详情)
- [3. 下载 PDF](#3-下载-pdf)
- [4. 下载解析结果](#4-下载解析结果)

## 接口清单

| 功能 | HTTP | 路径 | CLI |
|---|---|---|---|
| 搜索机构研报 | POST | `/report/list` | `research-report list` |
| 机构研报详情 | POST | `/report/detail` | `research-report detail` |
| 下载 PDF | POST | `/report/pdf/download` | `research-report pdf-download` |
| 下载解析结果 | POST | `/common/parsing/download` | `research-report parsing-download` |

## 1. 搜索机构研报

### 请求字段

| JSON | CLI | 类型 | 必填 | 说明 |
|---|---|---|---|---|
| `reportScope` | `--scope` | string | 是 | `domestic` / `foreign` / `independent` |
| `page` / `pageSize` | `--page` / `--page-size` | integer | 否 | 默认 1 / 20 |
| `keyword` | `--keyword` | string | 否 | 标题/正文关键词 |
| `startDate` / `endDate` | `--start` / `--end` | string | 否 | `yyyy-MM-dd` |
| `reportType` | `--report-type` | string[] | 否 | 见枚举 |
| `reportFeature` | `--report-feature` | string[] | 否 | `deep` / `new_fortune` |
| `industryCode` / `industryName` | 同名 CLI 参数 | string[] | 否 | 行业 |
| `stockCombSymbol` / `stockName` | `--stock-symbol` / `--stock-name` | string[] | 否 | 股票 |
| `institutionCode` / `institutionName` | 同名 CLI 参数 | string[] | 否 | 机构 |
| `countryRegion` | `--country-region` | string[] | 否 | 地区代码 |
| `language` | `--language` | string[] | 否 | 语言代码 |
| `pageCountRange` | `--page-count-range` | string | 否 | 页数范围 |

有效枚举：

```text
reportType:
  macro strategy industry company hk_research us_research fixed_income
  exchange_rate financial_engineering esg daily stock_recommend fund
  new_stock other

reportFeature: deep new_fortune
pageCountRange: lt_10 between_10_30 gt_30
language: zh_cn en fr ja es de nl it
countryRegion:
  china hong_kong taiwan united_states global japan korea india singapore
  germany united_kingdom france canada asia europe middle_east
  latin_america africa oceania
```

不要传 `English`、`zh`、`hk`、`1-10` 等展示名称或旧值；CLI 已做本地枚举校验。

### 返回

`PageResult<ResearchReport>`，分页字段为 `pageNum`、`pageSize`、`totalPageNum`、`totalSize`、`data[]`。

`ResearchReport` 完整实测字段：

| 字段 | 类型 | nullable | 说明 |
|---|---|---:|---|
| `reportId` | string | 否 | 加密时效 ID，详情/下载使用 |
| `title` / `titleCn` | string | `titleCn` 是 | 原标题/中文标题 |
| `reportTime` | string | 否 | 研报时间 |
| `reportScope` / `reportScopeLabel` | string | 否 | 范围代码/展示名 |
| `reportType` / `reportTypeLabel` | string | 否 | 类型代码/展示名；服务端可能返回数字字符串代码 |
| `reportFeatureTag` | `Tag[]` | 是 | 研报特征 |
| `industryTag` / `stockTag` | `Tag[]` | 是 | 行业、股票 |
| `institutionTag` / `conceptTag` | `Tag[]` | 是 | 机构、概念 |
| `sectorTag` | `Tag[]` | 是 | 板块 |
| `authorTag` / `analystTag` | `Tag[]` | 是 | 作者、分析师；`code` 可为 null |
| `pageCount` | integer | 否 | 页数，独立研报可能为 0 |
| `heat` | integer | 是 | 热度；外资样本实测可为 null |
| `hasPdf` | boolean | 否 | 是否有 PDF |

`Tag` 为 `{"code":string|null,"name":string}`。

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
      "reportId": "<实时加密ID>",
      "title": "示例行业研报",
      "titleCn": null,
      "reportTime": "2026-08-01 00:00:00",
      "reportScope": "domestic",
      "reportScopeLabel": "内资研报",
      "reportType": "industry",
      "reportTypeLabel": "行业研究",
      "reportFeatureTag": [],
      "industryTag": [{"code": "<行业编码>", "name": "电子"}],
      "stockTag": null,
      "institutionTag": [{"code": "<机构编码>", "name": "示例机构"}],
      "conceptTag": [],
      "sectorTag": null,
      "authorTag": [{"code": null, "name": "示例作者"}],
      "analystTag": [{"code": null, "name": "示例分析师"}],
      "pageCount": 20,
      "heat": 0,
      "hasPdf": true
    }]
  }
}
```

## 2. 机构研报详情

请求体：`{"reportId":"<列表实时返回的reportId>"}`。

详情返回列表字段，并增加：

| 字段 | 类型 | nullable | 说明 |
|---|---|---:|---|
| `content` / `contentCn` | string | 是 | 正文/中文正文 |
| `summary` | string | 是 | 摘要 |
| `fullContent` / `fullContentCn` | string | 是 | 完整正文/中文完整正文 |
| `htmlContent` | string | 是 | HTML 正文 |
| `summaryCnHtml` / `summaryEnHtml` | string | 是 | 中英文 HTML 摘要 |

不同来源的 nullable 差异很大，Agent 必须逐字段判空，不能只根据 `reportScope` 推断。

## 3. 下载 PDF

请求体：`{"reportId":"<reportId>"}`，响应为文件流。只有 `hasPdf=true` 才应尝试下载。

```bash
python scripts/alphapai_client.py research-report pdf-download \
  --report-id '<REPORT_ID>' --output ./report.pdf
```

已验证样本为 PDF 1.7、16,511,699 bytes。错误 JSON 信封可能仍使用 HTTP 200，CLI 会检查并拒绝保存成 PDF。

## 4. 下载解析结果

```json
{
  "documentId": "<reportId>",
  "documentType": "report",
  "downloadType": "markdown"
}
```

`downloadType`：`markdown`、`json`、`zip`。成功返回文件流；ZIP 应以 `PK` 开头并通过完整性校验，JSON 应可解析。解析结果可能尚未生成，此时返回业务错误而不是空文件。

`documentType=announcement` 虽也被公共端点接受，但公告场景应优先使用更明确的 `announcement parsing-download` 命令。
