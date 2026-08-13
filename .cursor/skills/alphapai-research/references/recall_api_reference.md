# 投研知识检索 API 参考

**URL**: `POST /alpha/open-api/v1/paipai/recall-data`

> 根据用户输入问题，从 Alpha派平台检索召回投研参考资料。

## 请求参数

| 字段       | 必填 | 类型         | 说明                                                                            |
| ---------- | ---- | ------------ | ------------------------------------------------------------------------------- |
| query      | 是   | String       | 查询问题                                                                        |
| recallType | 是   | List[String] | 召回数据类型筛选，`[]` 表示不限制                                               |
| isCutOff   | 否   | Boolean      | 是否截断数据(默认true)。true=与送入大模型一致；false=返回截断前完整内容。**注意：当前 isCutOff=true/false 返回内容无差异，参数暂无观测效果** |
| startTime  | 否   | String       | 开始日期 yyyy-MM-dd                                                             |
| endTime    | 否   | String       | 结束日期 yyyy-MM-dd                                                             |

## recallType 可选值

| 值              | 说明                                      |
| --------------- |-----------------------------------------|
| `roadShow`      | 【内资纪要】                                |
| `roadShow_ir`   | 【上市公司官方路演纪要】                    |
| `roadShow_us`   | 【美股 earnings 纪要】                      |
| `report`        | 【内资研报】                                |
| `foreign_report`| 【外资研报】                                |
| `third_report`  | 【三方研报】                                |
| `ann`           | 【公告库】                                  |
| `comment`       | 【点评】brokerage commentary                |
| `vps`           | 【基金定期报告】                            |
| `social_media`  | 【社媒】                                    |
| `edb`           | 【指标库】                                  |

## 响应参数

返回 `data` 为 List，每条：

| 字段        | 类型         | 说明                             |
| ----------- | ------------ | -------------------------------- |
| id          | String       | 数据ID                           |
| type        | String       | 数据类型（**可能返回枚举外值，如 `us_announcement` 会在 `ann` 召回中混入**） |
| contextInfo | String       | 上下文信息（含发布时间、标题等） |
| chunks      | List[String] | 文本块内容                       |
| sentenceIds | List[String] | 句子ID列表                       |
| contextText | String       | 问题文本（仅qa类型有值）         |
| answer      | String       | 回答文本（仅qa类型有值）         |
| highlights  | List[String] | 命中的句子/片段 ID   |
| industry    | String       | 行业名称；可为空串   |
| institution | String       | 机构名称；可为空串   |
| time        | String       | 时间                 |
| title       | String       | 标题                 |

## 请求示例

```json
{
    "query": "贵州茅台2024年市值多少?",
    "isCutOff": false,
    "recallType": ["comment", "report"],
    "startTime": "2025-02-18",
    "endTime": "2025-03-20"
}
```

## 完整响应示例

```json
{
  "code": 200000,
  "message": "success",
  "data": [{
    "id": "<RESOURCE_ID>",
    "type": "report",
    "contextInfo": "发布时间为: 2026-08-01,行业: 食品饮料,机构: 示例机构,标题: 示例研报",
    "chunks": ["召回的完整文本块"],
    "sentenceIds": [],
    "contextText": "",
    "answer": "",
    "title": "示例研报",
    "time": "2026-08-01",
    "industry": "食品饮料",
    "institution": "示例机构",
    "highlights": ["<HIGHLIGHT_ID>"]
  }]
}
```

2026-08-02 使用当前 CLI 对 `report` 实测返回 27 条。不同 `recallType` 可能缺少 `title/time/industry/institution/highlights` 等扩展字段，解析时使用可选访问；`type` 也可能出现请求枚举以外的细分值。
