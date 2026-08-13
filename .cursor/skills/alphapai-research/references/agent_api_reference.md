# Agent功能（PaiPai Agent）API 参考

**URL**: `POST /alpha/open-api/v1/paipai/stock/agent`

专业 Agentic-Workflow，SSE 流式返回，响应结构与文本问答接口一致（外层 `{"code":200000,"message":"success","data":{...}}` 包装，详见 base_api_reference.md）。

## 目录

- [公共约定](#公共约定)
- [各 Agent mode](#agentmode1--个股业绩点评)
- [CLI 聚合响应](#cli-聚合响应)
- [mode 1 的公告辅助接口](#mode-1-的公告辅助接口)

## 公共约定

所有模式均需传 `question`（String，必填），不同 Mode 下 question 含义不同。

> SSE 事件补充说明：
>
> - 当前各 mode 的全部内容事件均为 `type=200`、`routeName=null`；base_api_reference.md 类型码表中的 101/102/103/104 阶段事件当前均不出现。
> - `data` 内含 `answerType` 字段（如 `"text"`）。
> - references 条目另含 `page` 字段，`rank` 为 String。
> - 业务失败以 `data.type=500` 事件返回（HTTP 200、外层 code 可为 200000）；限流/参数错误以 `data` 为字符串的错误事件返回（如 42900、500303）。

---

## agentMode=1 — 个股业绩点评

| 字段              | 必填 | 类型    | 说明                                                    |
| ----------------- | :--: | ------- | ------------------------------------------------------- |
| question          |  是  | String  | `{stock.name}{stockReportPeriod}业绩点评`               |
| stock             |  是  | Dict    | `{"code": "603380.SH", "name": "易德龙"}`               |
| reportType        |  是  | String  | 报告类型，如 `季报` `年报`                              |
| stockReportId     |  是  | String  | 公告ID（先从 report 接口查询）                          |
| stockReportTitle  |  是  | String  | 公告标题                                                |
| stockReportPeriod |  是  | String  | 报告期，如 `2025年一季报`                               |
| template          |  是  | Integer | `0`（alpha派模板）或 `1`（用户模板，需填 templateText） |
| templateText      |  否  | String  | 用户自己的业绩点评模板                                  |
| templateConcern   |  否  | String  | 用户关注的话题、要点                                    |

---

## agentMode=2 — 公司一页纸

| 字段         | 必填 | 类型    | 说明                                       |
| ------------ | :--: | ------- | ------------------------------------------ |
| question     |  是  | String  | `{stock.name}（{stock.code}）的公司一页纸` |
| stock        |  是  | Dict    | 股票信息                                   |
| template     |  是  | Integer | `0` 或 `1`                                 |
| templateText |  否  | String  | 用户自定义模板                             |
| language     |  否  | String  | 语言，美股可选 `中文` / `英文`             |

---

## agentMode=3 — 个股调研大纲

| 字段         | 必填 | 类型    | 说明                                         |
| ------------ | :--: | ------- | -------------------------------------------- |
| question     |  是  | String  | `{stock.name}（{stock.code}）的调研问题大纲` |
| stock        |  是  | Dict    | 股票信息                                     |
| template     |  是  | Integer | `0`（固定）                                  |
| templateText |  否  | String  | 调研大纲中关注的内容要点                     |

---

## agentMode=5 — 主题选股

| 字段         | 必填 | 类型    | 说明                                   |
| ------------ | :--: | ------- | -------------------------------------- |
| question     |  是  | String  | 选股主题描述，与 templateText 保持一致 |
| template     |  是  | Integer | `1`（固定）                            |
| templateText |  是  | String  | 选股主题描述                           |

---

## agentMode=7 — 投资逻辑

| 字段         | 必填 | 类型    | 说明                                         |
| ------------ | :--: | ------- | -------------------------------------------- |
| question     |  是  | String  | `{stock.name}（{stock.code}）的公司投资逻辑` |
| stock        |  是  | Dict    | 股票信息                                     |
| template     |  是  | Integer | `0`（固定）                                  |
| templateText |  否  | String  | 关注的分析要点、维度、指标                   |
| onlyAnswer   |  否  | Boolean | 是否只返回最终答案（默认 false）             |

---

## agentMode=8 — 可比公司

| 字段            | 必填 | 类型    | 说明                                     |
| --------------- | :--: | ------- | ---------------------------------------- |
| question        |  是  | String  | `{stock.name}（{stock.code}）的可比公司` |
| stock           |  是  | Dict    | 股票信息                                 |
| template        |  是  | Integer | `1`（固定）                              |
| templateConcern |  否  | String  | 对比过程中关注的话题                     |

> 已知问题：`templateConcern` 当前服务端不生效（带/不带输出完全相同），且本 mode 的 references 恒为 0。

---

## agentMode=9 — 观点 Challenge

| 字段                   | 必填 | 类型    | 说明                              |
| ---------------------- | :--: | ------- | --------------------------------- |
| question               |  是  | String  | `Challenge该观点：{templateText}` |
| template               |  是  | Integer | `1`（固定）                       |
| templateText           |  是  | String  | 待 Challenge 的观点内容           |
| templateConcern        |  否  | String  | 关注焦点                          |
| requestSelectStartTime |  否  | String  | 检索起始时间 yyyy-MM-dd           |
| requestSelectEndTime   |  否  | String  | 检索截止时间 yyyy-MM-dd           |

---

## agentMode=11 — 行业一页纸

| 字段          | 必填 | 类型    | 说明                          |
| ------------- | :--: | ------- | ----------------------------- |
| question      |  是  | String  | `{inputIndustry}的行业一页纸` |
| inputIndustry |  是  | String  | 行业名称                      |
| template      |  是  | Integer | `0` 或 `1`                    |
| templateText  |  否  | String  | 用户自定义模板                |

---

## agentMode=12 — 个股选基

| 字段       | 必填 | 类型       | 说明                                                                                      |
| ---------- | :--: | ---------- | ----------------------------------------------------------------------------------------- |
| question   |  是  | String     | 自然语言描述查询条件                                                                      |
| stockList  |  是  | List[Dict] | 股票列表，每项 `{"code": "...", "name": "..."}`                                           |
| reportDate |  是  | String     | 报告期日期 yyyy-MM-dd                                                                     |
| fundType   |  是  | String     | `全部` / `主动` / `指数` / `ETF`                                                          |
| template   |  是  | Integer    | `0`（固定）                                                                               |
| ifAnnual   |  是  | Integer    | 是否年报：`0`=否，`1`=是（**服务端必填，缺失报 500303「个股选基是否年度标识不能为空」**） |

---

## agentMode=13 — 主题选基

| 字段       | 必填 | 类型    | 说明                                                                                      |
| ---------- | :--: | ------- | ----------------------------------------------------------------------------------------- |
| question   |  是  | String  | 自然语言描述查询条件                                                                      |
| reportDate |  是  | String  | 报告期日期 yyyy-MM-dd                                                                     |
| fundType   |  是  | String  | `全部` / `主动` / `指数` / `ETF`                                                          |
| template   |  是  | Integer | `0`（固定）                                                                               |
| ifAnnual   |  是  | Integer | 是否年报：`0`=否，`1`=是（**服务端必填，缺失报 500303「主题选基是否年度标识不能为空」**） |

> 已知问题：mode 13 生成阶段当前不稳定——偶发仅返回一个 type=500 事件，answer 为内部调试串（路由名错写"个股选基"），且无 references；`fundType=主动` 分支失败更频发，`fundType=全部` 也可能偶发。建议使用 `全部` 并在失败时重试。

---

## agentMode=15 — 画图

| 字段         | 必填 | 类型         | 说明                                                            |
| ------------ | :--: | ------------ | --------------------------------------------------------------- |
| question     |  是  | String       | 画图主题                                                        |
| pictureColor |  是  | List[String] | 颜色HEX值，主色和辅色，不含 `#` 前缀，如 `["2A66F6", "A5A8AF"]` |
| pictureStyle |  是  | String       | `PPT风格` / `科普风格`                                          |
| source       |  否  | Integer      | `0`=仅图片（默认），`1`=图文                                    |

---

## CLI 聚合响应

所有 mode 的原始响应均为 SSE。CLI 使用与 PaiPai问答相同的聚合结构：

```json
{
  "code": 200000,
  "message": "success",
  "questionId": "<QUESTION_ID>",
  "answer": "完整 Agent Markdown 输出",
  "references": []
}
```

`references` 结构见 `base_api_reference.md`；mode 8/12/13 等模式可以正常返回空引用，不能仅凭引用数量判断失败。成功还需检查 `answer` 非空且内容符合对应 mode。

仓库当前 `ai_test_run/` 已通过公开 CLI 实跑 11 个 mode，所有 mode 均取得非空最终结果。mode 13 仍有服务端偶发 `type=500` 风险，CLI 会报错而不是吞掉。

## mode 1 的公告辅助接口

先调用 `POST /alpha/open-api/v1/paipai/stock/report`：

```json
{"code":"603380.SH"}
```

返回每项完整字段：

```json
{
  "code": 200000,
  "message": "success",
  "data": [{
    "stockName": "易德龙",
    "stockCode": "603380.SH",
    "reportType": "季报",
    "reportPeriod": "2026年一季报",
    "stockReportId": "<实时公告ID>",
    "stockReportTitle": "易德龙:2026年第一季度报告"
  }]
}
```

字段映射：`reportPeriod` → Agent `stockReportPeriod`；其余 `reportType`、`stockReportId`、`stockReportTitle` 同名传入。公告 ID 有时效性，必须查询后立即调用 mode 1。
