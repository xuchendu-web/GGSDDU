# PaiPai问答 API 参考

**URL**: `POST /alpha/open-api/v1/paipai/qa-text`

> 根据用户输入问题，采用 RAG 技术从 Alpha派平台获取投研参考资料，然后进行总结推理回答。

## 请求参数

| 字段                   | 必填 | 类型         | 说明                                  |
| ---------------------- | ---- | ------------ | ------------------------------------- |
| question               | 是   | String       | 问题内容                              |
| mode                   | 是   | String       | `Flash`（默认）或 `Think`             |
| context                | 否   | List[String] | 多轮对话上下文                        |
| questionId             | 否   | String       | 唯一标识，并发时区分问题              |
| isAutoRoute            | 否   | Boolean      | 自动路由(默认true)                    |
| isStream               | 否   | Boolean      | 流式返回(默认false)。**注意：无论 isStream 取值均返回 SSE 流（含 `: ` 心跳行），不存在非流式 JSON 响应，调用方应一律按 SSE 处理** |
| isWebSearch            | 否   | Boolean      | 联网搜索(默认false)                   |
| isDeepReasoning        | 否   | Boolean      | 深度推理(默认false)                   |
| requestSelectStartTime | 否   | String       | 筛选开始时间 yyyy-MM-dd               |
| requestSelectEndTime   | 否   | String       | 筛选结束时间 yyyy-MM-dd               |

## 响应参数

| 字段        | 类型       | 说明                           |
| ----------- | ---------- | ------------------------------ |
| answer      | String     | 回答内容，stream模式逐字返回   |
| answerOrder | Integer    | stream回答序号                 |
| references  | List[Dict] | 引用数据列表（条目字段见 base_api_reference.md；条目另含 `page` 字段，`rank` 为 String） |
| type        | Integer    | 回答类型码（见 base_api_reference.md；当前内容事件均为 type=200） |
| isEnd       | Boolean    | 本次回答是否完结               |
| routeName   | String     | 处理逻辑路由名称（当前恒为 null） |
| questionId  | String     | 问题唯一标识                   |
| answerType  | String     | 回答类型（如 `"text"`） |

## 请求示例

```json
{
    "question": "讯兔科技首席科学家是谁？",
    "mode": "Flash",
    "isStream": true,
    "isAutoRoute": false
}
```

## CLI 聚合响应

原始接口为 SSE 事件流；`cmd_qa.py` 保留顶层状态并聚合所有 `answer`，按引用 `id` 去重后输出：

| 字段 | 类型 | 说明 |
|---|---|---|
| `code` | integer | 成功为 `200000` |
| `message` | string | 顶层业务消息 |
| `questionId` | string/null | 服务端问题 ID |
| `answer` | string | 按事件顺序拼接的完整回答 |
| `references` | `Reference[]` | 去重后的引用 |

```json
{
  "code": 200000,
  "message": "success",
  "questionId": "<QUESTION_ID>",
  "answer": "完整回答正文",
  "references": [{
    "id": "<RESOURCE_ID>",
    "rank": "1",
    "sentence": "命中的引用句",
    "chunk": "引用上下文",
    "type": "report",
    "title": "引用标题",
    "publishDate": "2026-08-01",
    "isSelfPrivate": null,
    "url": "https://example.com/resource",
    "teamName": null,
    "instShortName": "示例机构",
    "page": "1",
    "filePath": null
  }]
}
```

`Reference` 字段的 nullable 会随来源变化，完整解释见 `base_api_reference.md`。2026-08-02 的 Flash 实测返回 44 条去重引用；Think 已由仓库当前 100 题实测覆盖。

## 错误

- 顶层 `code=42900`：限流，`data` 可能是空字符串。
- 顶层 `code=500303`：参数错误。
- SSE `data.type=500`：生成阶段业务失败。
- CLI 对上述情况非零退出，不输出伪成功 JSON。

公共字段定义（引用类型、响应码等）见 `base_api_reference.md`。
