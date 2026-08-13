# 会议纪要 API 参考

路径前缀：`/alpha/open-api/v1/summary`。包含全局检索和详情两个接口。

## 目录

- [1. 搜索会议纪要列表](#1-搜索会议纪要列表)
- [2. 查看纪要详情](#2-查看纪要详情)

## 1. 搜索会议纪要列表

`POST /alpha/open-api/v1/summary/list`

### 请求

| JSON | CLI | 类型 | 必填 | 枚举/说明 |
|---|---|---|---|---|
| `meetingMarketType` | `--market-type` | string | 是 | `A` / `HK` / `US` |
| `pageNum` / `pageSize` | `--page-num` / `--page-size` | integer | 否 | 默认 1 / 20，`pageSize` 最大 100 |
| `keyword` | `--keyword` | string | 否 | 匹配标题、摘要、正文 |
| `beginTime` / `endTime` | `--begin-time` / `--end-time` | string | 否 | `yyyy-MM-dd HH:mm:ss` |
| `meetingTag` | `--meeting-tag` | string[] | 否 | `executive_attended` / `new_fortune` / `china_concept` |
| `meetingContentType` | `--content-type` | string[] | 否 | 见下表 |
| `industryCode` | `--industry-code` | string[] | 否 | 行业 code |
| `stockCombSymbol` | `--stock-symbol` | string[] | 否 | 如 `600519.SH` |
| `institutionCode` | `--institution-code` | string[] | 否 | 机构 code |
| `durationCategory` | `--duration` | string | 否 | `lt_30m` / `between_30m_60m` / `gt_60m` |

`meetingContentType`：`company_communication`、`performance_meeting`、`expert_communication`、`company_analysis`、`industry_analysis`、`conference`、`fund_manager_view`。

不同筛选维度之间为 AND，同一数组内为 OR。

### 返回

返回 `PageResult<MeetingSummary>`，分页字段为 `pageNum`、`pageSize`、`totalPageNum`、`totalSize`、`data[]`。

`MeetingSummary` 完整实测字段：

| 字段 | 类型 | nullable | 说明 |
|---|---|---:|---|
| `summaryId` | string | 否 | 纪要记录 ID |
| `roadshowId` | string | 否 | 详情接口使用的会议 ID |
| `title` | string | 否 | 会议标题 |
| `meetingMarketType` / `meetingMarketTypeLabel` | string | 否 | 市场代码与展示名 |
| `meetingTag` | `Tag[]` | 是 | 会议标签 |
| `meetingContentType` | `Tag[]` | 是 | 内容类型 |
| `industryTag` / `stockTag` | `Tag[]` | 是 | 行业、股票 |
| `institutionTag` / `subjectTag` | `Tag[]` | 是 | 机构、题材 |
| `guestTag` / `hostTag` / `analystTag` | `Tag[]` | 是 | 嘉宾、主持、分析师 |
| `meetingTime` / `publishTime` | string | 否 | 会议时间、发布时间 |
| `availableNoteTypes` | string[] | 否 | 当前条目可用的 `ai_note` / `asr_note` |
| `hasRadio` | boolean | 否 | 是否有音频 |
| `durationSeconds` | integer | 否 | 会议时长秒数 |
| `containsPpt` | boolean | 否 | 是否含 PPT |
| `pv` / `heat` | integer | 否 | 浏览量、热度 |
| `changePct` | number | 是 | 涨跌幅，常为 null |

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
      "summaryId": "<SUMMARY_ID>",
      "roadshowId": "<实时会议ID>",
      "title": "示例会议",
      "meetingMarketType": "A",
      "meetingMarketTypeLabel": "A股",
      "meetingTag": [],
      "meetingContentType": [{"code": "company_communication", "name": "公司交流"}],
      "industryTag": [{"code": "<行业编码>", "name": "电子"}],
      "stockTag": [],
      "institutionTag": [{"code": "<机构编码>", "name": "示例机构"}],
      "subjectTag": [],
      "guestTag": [],
      "hostTag": [],
      "analystTag": [],
      "meetingTime": "2026-08-01 10:00:00",
      "publishTime": "2026-08-01 12:00:00",
      "availableNoteTypes": ["ai_note", "asr_note"],
      "hasRadio": true,
      "durationSeconds": 3600,
      "containsPpt": false,
      "pv": 1,
      "heat": 1,
      "changePct": null
    }]
  }
}
```

## 2. 查看纪要详情

`POST /alpha/open-api/v1/summary/detail`

请求体：

```json
{
  "roadshowId": "<列表返回的roadshowId>",
  "noteType": "ai_note"
}
```

`noteType` 必须存在于该列表项的 `availableNoteTypes` 中。

完整返回字段：

| 字段 | 类型 | 说明 |
|---|---|---|
| `summaryId` | string | 纪要 ID |
| `roadshowId` | string | 会议 ID |
| `noteType` | string | `ai_note` / `asr_note` |
| `meetingMarketType` / `meetingMarketTypeLabel` | string | 市场 |
| `title` | string | 标题 |
| `publishTime` | string | 发布时间 |
| `content` | string | 完整正文；AI 纪要或 ASR 逐字稿 |
| `aiContent` | string | AI 摘要；`asr_note` 下通常为空串 |
| `markdownContent` | string | Markdown 形式正文 |

```json
{
  "code": 200000,
  "message": "success",
  "data": {
    "summaryId": "<SUMMARY_ID>",
    "roadshowId": "<ROADSHOW_ID>",
    "noteType": "ai_note",
    "meetingMarketType": "A",
    "meetingMarketTypeLabel": "A股",
    "title": "示例会议",
    "publishTime": "2026-08-01 12:00:00",
    "content": "完整会议纪要正文",
    "aiContent": "会议摘要",
    "markdownContent": "# 会议纪要\n\n完整正文"
  }
}
```

2026-08-02 使用当前 CLI 对 A 股列表和一条 `availableNoteTypes` 非空的详情均实测 `200000`。US 等市场的条目可能没有任何可用纪要；此时不得猜测 `noteType`，详情会返回 `400000`“未查询到对应的会议纪要数据”。
