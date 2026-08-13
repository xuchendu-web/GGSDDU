# 预约会议 API 参考

路径前缀：`/alpha/open-api/v1/reservation/meeting`。以下字段于 2026-08-02 使用当前配置做过真实只读调用；删除接口仅沿用此前对不存在 ID 的安全验证，不得删除用户真实预约。

## 目录

- [接口清单](#接口清单)
- [1. 预约记录列表](#1-预约记录列表)
- [2. 删除预约](#2-删除预约)
- [3. 已生成会议列表](#3-已生成会议列表)
- [4. 会议详情](#4-会议详情)
- [5. 会议纪要详情](#5-会议纪要详情)
- [公共响应结构](#公共响应结构)

## 接口清单

| 功能 | HTTP | 路径 | CLI |
|---|---|---|---|
| 预约记录列表 | POST | `/list` | `meeting-booking list` |
| 删除预约 | POST | `/delete` | `meeting-booking delete` |
| 已生成会议列表 | POST | `/generated/list` | `meeting-booking generated-list` |
| 会议详情 | POST | `/detail` | `meeting-booking detail` |
| 会议纪要详情 | POST | `/summary/detail` | `meeting-booking summary-detail` |

## 1. 预约记录列表

请求体字段：

| JSON | CLI | 类型 | 必填 | 说明 |
|---|---|---|---|---|
| `scope` | `--scope` | string | 否 | 当前仅支持 `my`，CLI 默认 `my` |
| `status` | `--status` | string[] | 否 | `success` / `fail` |
| `keyword` | `--keyword` | string | 否 | 标题关键词 |
| `meetingTimeFrom` / `meetingTimeTo` | 同名 CLI 参数 | string | 否 | 会议时间范围 |
| `reservedTimeFrom` / `reservedTimeTo` | 同名 CLI 参数 | string | 否 | 预约时间范围 |
| `industryTag` | `--industry-tag` | string[] | 否 | 行业标签 |
| `organizations` | `--organizations` | string[] | 否 | 机构 code |
| `marketTag` | `--market-tag` | string[] | 否 | `A` / `HK` / `US` |
| `page` / `pageSize` | `--page` / `--page-size` | integer | 否 | 默认 1 / 20 |

返回 `PageResult<ReservationMeeting>`。

## 2. 删除预约

请求：`{"msgId":"<预约列表返回的msgId>","scope":"my"}`。

返回 `data`：

| 字段 | 类型 | 说明 |
|---|---|---|
| `state` | string | `success` / `fail` |
| `message` | string | 删除结果说明 |
| `roadshowId` | string/null | 关联会议 ID |

这是破坏性操作。只在用户明确要求删除，或 ID 是本次验证创建的临时预约时调用。

## 3. 已生成会议列表

基础分页字段同接口 1，并支持：

| JSON | CLI | 类型 | 说明 |
|---|---|---|---|
| `stockTag` | `--stock-tag` | string[] | 股票过滤 |
| `contentTypeTag` | `--content-type-tag` | string[] | 使用中文标签，如 `专家交流`、`公司交流` |
| `hasAsrNote` | `--has-asr-note true|false` | boolean | 是否已生成 ASR |
| `hasAiNote` | `--has-ai-note true|false` | boolean | 是否已生成 AI 纪要 |

返回元素也是 `ReservationMeeting`；区别是 `availableNoteTypeList` 通常为 `ai_note`、`asr_note` 的数组。调用纪要详情前必须检查此字段。

## 4. 会议详情

| JSON | CLI | 类型 | 必填 | 说明 |
|---|---|---|---|---|
| `meetingId` | `--meeting-id` | string | 是 | `roadshowId` |
| `includeNotes` | `--include-notes` | boolean | 否 | CLI 默认 true |
| `notePreviewLength` | `--note-preview-length` | integer | 条件必填 | `includeNotes=true` 时必须携带；CLI 默认 200 |

返回 `ReservationMeetingDetail`，即 `ReservationMeeting` 的全部字段，另含 `noteList`。

## 5. 会议纪要详情

| JSON | CLI | 类型 | 必填 | 说明 |
|---|---|---|---|---|
| `meetingId` | `--meeting-id` | string | 是 | `roadshowId` |
| `noteType` | `--note-type` | string | 是 | `ai_note` / `asr_note`；必须在 `availableNoteTypeList` 内 |
| `format` | `--format` | string | 否 | 仅支持 `markdown` |
| `includeSegments` | `--include-segments` | boolean | 否 | 当前传 true 时 `asrNoteSegmentList` 仍可能为 null |

完整返回字段：

| 字段 | 类型 | nullable | 说明 |
|---|---|---:|---|
| `transId` | string | 否 | AI/ASR 转换任务 ID |
| `noteType` | string | 否 | `ai_note` 或 `asr_note` |
| `title` | string | 否 | 纪要标题 |
| `wordCount` | integer | 否 | 正文字数 |
| `generatedAt` | string | 否 | ISO 8601 生成时间 |
| `links` | array/object | 是 | 关联链接，当前样本为 null |
| `aiJsonContentRawText` | string | 是 | AI 原始 JSON 文本 |
| `asrJsonContentRawText` | string | 是 | ASR 原始 JSON 文本 |
| `format` | string | 否 | 当前为 `markdown` |
| `content` | string | 否 | 完整纪要 Markdown/逐字稿，可能非常长 |
| `contentPreview` | string | 是 | 预览文本 |
| `asrNoteSegmentList` | array | 是 | ASR 分段；当前实测可为 null |

```json
{
  "code": 200000,
  "message": "success",
  "data": {
    "transId": "TRANSAI00003703243",
    "noteType": "ai_note",
    "title": "示例会议会议纪要",
    "wordCount": 11310,
    "generatedAt": "2026-06-18T19:08:37+08:00",
    "links": null,
    "aiJsonContentRawText": null,
    "asrJsonContentRawText": null,
    "format": "markdown",
    "content": "# 会议要点\n\n## 1. 行业趋势……",
    "contentPreview": null,
    "asrNoteSegmentList": null
  }
}
```

## 公共响应结构

分页信封字段为 `pageNum`、`pageSize`、`totalPageNum`、`totalSize`、`data[]`。

`ReservationMeeting` 完整实测字段：

| 字段 | 类型 | nullable | 说明 |
|---|---|---:|---|
| `huid` | integer | 否 | 内部记录 ID |
| `roadshowId` | string | 否 | 会议 ID，详情与纪要详情使用 |
| `msgId` | string | 否 | 预约消息 ID，删除使用 |
| `title` / `platform` | string | 否 | 标题、会议平台 |
| `industryTag` / `stockTag` | `Tag[]` | 是 | 行业、股票标签 |
| `marketTag` | `Tag[]` | 是 | 市场标签 |
| `meetingOrgCode` / `meetingOrgName` | string | 是 | 会议机构 |
| `reservedByUserId` / `reservedByUserName` | string | 否 | 预约用户 |
| `reservedByInstitutionId` | string | 否 | 预约机构 ID |
| `reservedByInstitutionCode` / `reservedByInstitutionName` | string | 否 | 预约机构编码与名称 |
| `meetingTime` / `reservedTime` | string | 否 | ISO 8601 时间 |
| `status` / `errorMsg` | string | 否 | 状态及状态说明 |
| `meetingInfoCode` | integer | 否 | 会议信息状态码 |
| `link` | string | 否 | 会议链接 |
| `transIdMt` / `transIdAi` | string | 否 | ASR/AI 转换 ID，未生成时可为空串 |
| `content` / `roadshowContent` | string | 否 | 预约内容、会议内容类型 |
| `hisvalid` | integer | 否 | 有效标记（服务端字段拼写如此） |
| `availableNoteTypeList` | string[] | 是 | 可用纪要类型；预约列表可为 null |
| `noteList` | `MeetingNotePreview[]` | 是 | 仅详情接口返回 |

`Tag` 为 `{"code":string,"name":string}`。标签字段可能是 null 或空数组，Agent 必须同时兼容。

实际成功路径：`generated-list` → 读取 `roadshowId` 与 `availableNoteTypeList` → `detail` → `summary-detail`。无效/不可用纪要通常返回 `400000`。
