# 搜图表 API 参考

**URL**: `POST /alpha/open-api/v1/paipai/search-image`

根据语义从研报和公告中搜索相关图片和表格。

## 请求参数

| 字段       | 必填 | 类型         | 说明                                                                 |
| ---------- | ---- | ------------ | -------------------------------------------------------------------- |
| queryText  | 是   | String       | 检索查询的文本内容                                                   |
| filesRange | 否   | List[String] | 来源类型代码：`3`=内资研报 `8`=外资研报 `6`=公告 `9`=三方研报       |
| topk       | 否   | Integer      | 返回结果数量，范围1-100，默认50（超过 100 时服务端不报错，静默返回空数组） |
| recallMode | 否   | String       | 召回模式: both(默认)/vector_only/es_only                             |
| useLlmRank | 否   | Boolean      | 是否使用LLM重排序，默认false                                         |
| startDate  | 否   | String       | 开始日期 yyyy-MM-dd                                                  |
| endDate    | 否   | String       | 结束日期 yyyy-MM-dd                                                  |

## 响应参数 (data 列表每条)

| 字段            | 类型         | 说明                                    |
| --------------- | ------------ | --------------------------------------- |
| articleId       | String       | 文章ID                                  |
| articleTitle    | String       | 文章标题                                |
| articleType     | String       | 文章类型                                |
| publishDate     | String       | 发布日期 yyyy-MM-dd HH:mm:ss            |
| pageIndex       | Integer      | 页码索引                                |
| bbox            | String       | 图片在页面上的位置坐标 [x1, y1, x2, y2] |
| captionList     | List[String] | 图片标题列表                            |
| footnoteList    | List[String] | 脚注列表                                |
| imageUrl        | String       | 图片URL                                 |
| source          | String       | 图片来源                                |
| llmScore        | Float/null   | LLM评分；未启用/未产生重排时为 null     |
| llmReason       | String/null  | LLM评分理由；可能为 null                |
| institutionList | List[Dict]   | 机构信息列表 (code, name, logo)         |
| authorList      | List[String]/null | 作者列表；可能为 null               |

## 完整响应示例

```json
{
  "code": 200000,
  "message": "success",
  "data": [{
    "articleId": "<ARTICLE_ID>",
    "articleTitle": "示例机构研报",
    "articleType": "report",
    "publishDate": "2026-08-01 00:00:00",
    "pageIndex": 3,
    "bbox": "[10,20,300,400]",
    "captionList": ["图 1：收入趋势"],
    "footnoteList": ["资料来源：示例机构"],
    "imageUrl": "https://example.com/image.png",
    "source": "示例机构",
    "llmScore": null,
    "llmReason": null,
    "institutionList": [{
      "code": "<机构编码>",
      "name": "示例机构",
      "logo": "https://example.com/logo.png"
    }],
    "authorList": null
  }]
}
```

2026-08-02 使用当前 CLI 对研报+公告来源、`topk=1` 实测 `code=200000`。`topk` 应限制在 1–100；服务端对更大值可能静默返回空数组而非参数错误。
