# AlphaPai Open API 基础参考

本文档涵盖鉴权配置、健康检查及公共约定。各功能接口详见 `references/` 下对应文档。

## 目录

- [鉴权](#鉴权)
- [健康检查](#健康检查)
- [通用响应码](#通用响应码)
- [SSE 流式响应](#sse-流式响应约定)
- [引用结构与类型](#引用类型枚举)

## 鉴权

所有请求需在 Header 中携带：

| Header       | 说明              |
| ------------ | ----------------- |
| app-agent    | API Key           |
| Content-Type | application/json; charset=utf-8 |

配置方式见 SKILL.md「首次使用：配置 API Key」。

## 健康检查

**URL**: `POST /alpha/open-api/v1/sync/auth/hello`

**请求体**: `{}`

**响应示例**:

```json
{
    "code": 200000,
    "message": "success",
    "data": "success"
}
```

## 通用响应码

| code   | 说明     |
| ------ | -------- |
| 200000 | 成功     |
| 其他   | 失败，见 message 字段 |

## SSE 流式响应约定

qa-text、stock/agent 等接口支持 SSE 流式返回。约定如下：

每条事件外层为 `{"code":200000,"message":"success","data":{...}}` 包装，`data` 内为业务字段：

```
data: {"code":200000,"message":"success","data":{"questionId":"...","answerOrder":1,"answer":"...","type":200,"routeName":null,"references":[...],"isEnd":false,"answerType":"text"}}
```

`data` 内字段：`questionId` / `answerOrder` / `answer` / `type` / `routeName` / `references` / `isEnd` / `answerType`（如 `"text"`）。

补充说明：

- 当前所有被测内容事件均为 `type=200`、`routeName=null`；下文「回答类型码」中的 101/102/103/104 阶段事件当前不出现。
- 流中夹杂 `: ` 心跳注释行（SSE comment），解析时需跳过非 `data:` 开头的行。
- 业务错误以 HTTP 200 + 错误事件返回：`data` 为字符串而非对象，形如 `{"code":<非200000>,"message":"...","data":""}`（网关场景错误字段为 `msg` 而非 `message`），如 `42900` 限流、`500303` 参数错误。解析器必须兼容 `data` 为字符串的情况，不能假设其恒为对象。
- `data` 内 `type=500` 表示业务失败（此时 HTTP 与外层 code 仍可能为 200/200000）。

客户端需按 `\n\n` 分割事件，解析 `data:` 前缀后的 JSON。

## 引用类型枚举

| 值              | 说明                                      |
| --------------- |-----------------------------------------|
| `roadShow`      | 【内资纪要】A股、港股全市场公开会议内容             |
| `roadShow_ir`   | 【上市公司官方路演纪要】上市公司官方披露会议内容    |
| `roadShow_us`   | 【美股 earnings 纪要】美股业绩发布会内容          |
| `report`        | 【内资研报】国内券商发布研究报告                  |
| `foreign_report`| 【外资研报】头部外资机构发布研究报告              |
| `third_report`  | 【三方研报】第三方研究报告                        |
| `ann`           | 【公告库】上市公司在交易所的官方披露              |
| `comment`       | 【点评】brokerage commentary                     |
| `vps`           | 【基金定期报告】基金经理季报/年报观点             |
| `social_media`  | 【社媒】专业金融机构或分析师发布的社媒信息        |
| `edb`           | 【指标库】宏观经济、行业数据、个股财务数据        |

## 引用数据结构 (references)

| 字段          | 说明         |
| ------------- | ------------ |
| sentence      | 引用句子     |
| rank          | 排序号（String 类型） |
| chunk         | 上下文文本   |
| id            | 引用资源id   |
| type          | 引用资源类型 |
| title         | 标题         |
| publishDate   | 发布日期     |
| isSelfPrivate | 是否私有纪要 |
| url           | 引用资源链接 |
| teamName      | 团队名称     |
| instShortName | 机构名称     |
| filePath      | 引用文件路径 |
| page          | 页码 |

## 回答类型码 (SSE type)

| 值  | 含义             |
| --- | ---------------- |
| 101 | 问题分析阶段     |
| 102 | 获取资料阶段     |
| 103 | 获取资料完成     |
| 104 | 正在生成回答     |
| 108 | 思维链           |
| 200 | 成功             |
| 201 | 结果为空         |
| 500 | 失败             |

## 功能接口索引

| 文档 | 接口 |
| ---- | ---- |
| `qa_api_reference.md` | 投研知识问答 |
| `recall_api_reference.md` | 投研知识检索 |
| `agent_api_reference.md` | Agent功能（PaiPai Agent） |
| `watchlist_public_api_reference.md` | 自选股 |
| `image_api_reference.md` | 搜图表 |
