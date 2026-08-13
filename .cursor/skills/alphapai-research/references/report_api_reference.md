# 股票公告列表 API 参考

**URL**: `POST /alpha/open-api/v1/paipai/stock/report`

根据股票代码获取上市公司在交易所公开的公告列表，常用于查询业绩点评所需的 `stockReportId`。

## 请求参数

| 字段 | 必填 | 类型   | 说明     | 示例值        |
| ---- | ---- | ------ | -------- | ------------- |
| code | 是   | String | 股票编码 | `"603380.SH"` |

## 响应参数 (data 列表每条)

| 字段             | 类型   | 说明     |
| ---------------- | ------ | -------- |
| stockCode        | String | 股票编码 |
| stockName        | String | 股票名称 |
| reportType       | String | 报告类型 |
| reportPeriod     | String | 报告期   |
| stockReportId    | String | 公告ID   |
| stockReportTitle | String | 报告标题 |
