# 录音转记 API 参考

## 目录

- [接口清单](#接口清单)
- [提交 URL 与文件任务](#1-提交链接音视频转纪要任务)
- [查询、详情与下载](#4-查询转纪要任务列表)
- [重命名、删除与额度](#8-重命名任务标题)
- [文件流下载](#11-下载文件markdown--docx--媒体流)
- [状态码与完整结构](#任务状态码)

> 模块：`alpha-open-api-service`  
> Controller：`RecordConvertController`  
> 路径前缀：`/open-api/v1/record/convert`

---

## 通用约定

### 统一返回体 `Result<T>`

| 字段 | 类型 | 说明 |
|---|---|---|
| `code` | int | 业务码，成功为 `200000` |
| `message` | string | 提示信息 |
| `data` | T | 业务数据 |

下文「响应数据」仅描述 `data` 部分。写操作返回 `Result<Boolean>`，`data=true` 表示成功。

### 分页返回体 `PageResult<T>`

| 字段 | 类型 | 说明 |
|---|---|---|
| `pageNum` | int | 当前页码 |
| `pageSize` | int | 每页数量 |
| `totalPageNum` | int | 总页数 |
| `totalSize` | long | 总条数 |
| `data` | array&lt;T&gt; | 结果列表 |

### 鉴权 / 用户态

- 用户态由网关注入的 **`@CurrentApp CurrentAppInfo`** 获取，取 `currentAppInfo.getUserUid()` 作为 `userId`。

- 调用方无需再传 Query 参数 `userId`。
- 下文 curl 示例统一使用：`BASE=https://<网关域名>/alpha`（需携带开放平台鉴权头）。

### 接口清单

| # | HTTP | 路径 | 说明 |
|---|---|---|---|
| 1 | POST | `/task/url/submit` | 提交链接音视频转纪要任务 |
| 2 | POST | `/file/upload` | 上传录音或文本文件 |
| 3 | POST | `/task/add` | 创建文件转纪要任务 |
| 4 | POST | `/task/query` | 查询转纪要任务列表 |
| 5 | GET | `/task/newest` | 查询最新一条纪要 |
| 6 | GET | `/task/detail` | 查询任务详情 |
| 7 | GET | `/task/download` | 获取任务下载地址 |
| 8 | POST | `/task/rename` | 重命名任务标题 |
| 9 | POST | `/task/delete` | 删除任务 |
| 10 | GET | `/quota` | 查询本月转纪要额度 |

---

## 1. 提交链接音视频转纪要任务

`POST /open-api/v1/record/convert/task/url/submit`  
Body：`RecordConvertUrlSubmitApiRequest`

### 请求参数

| 字段 | 位置 | 类型 | 必填 | 说明 |
|---|---|---|---|---|
| `url` | Body | string | 是 | 音视频或文章链接 |
| `needTranslate` | Body | boolean | 否 | 是否需要翻译，默认 `false` |
| `targetLanguage` | Body | string | 否 | 目标语言 语言枚举在文档末尾|
| `sourceLanguage` | Body | string | 否 | 源语言 |
| `asrVersion` | Body | int | 否 | asr 版本，`0`-原版本 `1`-新版本 |

### 调用示例

```bash
curl -X POST "$BASE/open-api/v1/record/convert/task/url/submit" \
  -H "Content-Type: application/json" \
  -d '{
    "url": "https://www.example.com/share/meeting.mp4",
    "needTranslate": false,
    "asrVersion": 1
  }'
```

### 响应示例

```json
{ "code": 200000, "message": "success", "data": true }
```

---

## 2. 上传录音或文本文件

`POST /open-api/v1/record/convert/file/upload`  
Content-Type：`multipart/form-data`

> 上传文件至 S3 并登记文件信息，不创建转纪要任务。创建任务时使用响应中的 `fileId`。

### 请求参数

| 字段 | 位置 | 类型 | 必填 | 说明 |
|---|---|---|---|---|
| `file` | Form | file | 是 | 待上传的录音或文本文件 |
| `fileType` | Form | int | 是 | 文件类型，`10`-语音、`20`-文件、`40`-现场录音 |
| `title` | Form | string | 否 | 文件标题 |
| `memo` | Form | string | 否 | 备注 |
| `updateMemo` | Form | int | 否 | 是否编辑过备注，`1`-已编辑，默认 `0` |
| `city` | Form | string | 否 | 城市 |
| `cityDistinct` | Form | string | 否 | 区县 |

### 调用示例

```bash
curl -X POST "$BASE/open-api/v1/record/convert/file/upload" \
  -F "file=@./季度策略电话会.mp3" \
  -F "fileType=10" \
  -F "title=季度策略电话会"
```

### 响应数据：`RecordUploadApiVO`

| 字段 | 类型 | 说明 |
|---|---|---|
| `s3Url` | string | 上传后的 S3 路径 |
| `duration` | long | 录音时长（秒）或文本长度（字数） |
| `freeNum` | int | 免费次数 |
| `fileId` | int | 文件 id，创建任务时必填 |
| `fileOriginName` | string | 文件原始名称（**可为 null**，创建任务时 uploadFileName 请以上传的本地文件名为准） |

### 响应示例

```json
{
  "code": 200000,
  "message": "success",
  "data": {
    "s3Url": "mix-server/recordSummary/meeting.mp3",
    "duration": 3600,
    "freeNum": 0,
    "fileId": 123456,
    "fileOriginName": "季度策略电话会.mp3"
  }
}
```

---

## 3. 创建文件转纪要任务

`POST /open-api/v1/record/convert/task/add`  
Body：`RecordConvertTaskAddApiRequest`

> 必须先调用文件上传接口。`fileId` 取上传响应中的 `data.fileId`；服务端会根据 `fileId` 查询已登记文件的 S3 地址和时长。  
> 原 `/task/file/submit` 已移除，不再对接。

### 请求参数

| 字段 | 位置 | 类型 | 必填 | 说明 |
|---|---|---|---|---|
| `uploadFileName` | Body | string | 是 | 待解析文件名；可以使用上传响应的 `fileOriginName` |
| `fileId` | Body | int | 是 | 上传响应中的 `fileId` |
| `languageType` | Body | int | 是 | 语言类型，`10`-中文、`20`-英文 |
| `fileType` | Body | int | 是 | 文件类型，`10`-语音、`20`-文件 |
| `uploadFileUrl` | Body | string | 否 | 待解析文件的 S3 地址；当前流程会根据 `fileId` 读取登记地址，无需传入 |
| `companyId` | Body | string | 否 | 公司 id |
| `companyName` | Body | string | 否 | 公司名称，最长 100 个字符 |
| `email` | Body | string | 否 | 邮件地址 |
| `city` | Body | string | 否 | 城市 |
| `cityDistinct` | Body | string | 否 | 区县 |
| `sourceLanguage` | Body | string | 否 | 源语言类型 |
| `asrVersion` | Body | int | 否 | ASR 版本，`0`-原版本、`1`-新版本 |

### 调用示例

```bash
curl -X POST "$BASE/open-api/v1/record/convert/task/add" \
  -H "Content-Type: application/json" \
  -d '{
    "uploadFileName": "季度策略电话会.mp3",
    "fileId": 123456,
    "languageType": 10,
    "fileType": 10,
    "asrVersion": 1
  }'
```

### 响应示例

```json
{ "code": 200000, "message": "success", "data": true }
```

---

## 4. 查询转纪要任务列表

`POST /open-api/v1/record/convert/task/query`  
Body：`RecordConvertQueryApiRequest`

### 请求参数

| 字段 | 位置 | 类型 | 必填 | 说明 |
|---|---|---|---|---|
| `uploadFileName` | Body | string | 否 | 文件名（模糊匹配） |
| `status` | Body | int | 否 | 任务状态，见下方「任务状态码」 |
| `recordId` | Body | string | 否 | 录音 ID |
| `pageNum` | Body | int | 否 | 页码，默认 `1` |
| `pageSize` | Body | int | 否 | 每页条数，默认 `10` |

### 调用示例

```bash
curl -X POST "$BASE/open-api/v1/record/convert/task/query" \
  -H "Content-Type: application/json" \
  -d '{ "status": 1, "pageNum": 1, "pageSize": 10 }'
```

### 响应数据：`PageResult<RecordTaskVO>`

字段见 [附：RecordTaskVO](#附recordtaskvo)。

---

## 5. 查询最新一条纪要生成信息

`GET /open-api/v1/record/convert/task/newest`

### 调用示例

```bash
curl -X GET "$BASE/open-api/v1/record/convert/task/newest"
```

### 响应数据：`RecordTaskVO`

> 注意：本接口**不过滤已删除任务**，已删除任务仍会作为"最新一条"返回；且 VO 填充与 query 接口不一致（部分字段如 type/mediaType 为 null）。

---

## 6. 查询任务详情

`GET /open-api/v1/record/convert/task/detail`

### 请求参数（Query）

| 字段 | 类型 | 必填 | 说明 |
|---|---|---|---|
| `taskId` | string | 是 | 任务 id |

### 调用示例

```bash
curl -X GET "$BASE/open-api/v1/record/convert/task/detail?taskId=100231"
```

### 响应数据：`RecordTaskVO`

---

## 7. 获取任务下载地址

`GET /open-api/v1/record/convert/task/download`

### 请求参数（Query）

| 字段 | 类型 | 必填 | 说明 |
|---|---|---|---|
| `taskId` | string | 是 | 任务 id |

### 调用示例

```bash
curl -X GET "$BASE/open-api/v1/record/convert/task/download?taskId=100231"
```

### 响应数据：文件流



---

## 8. 重命名任务标题

`POST /open-api/v1/record/convert/task/rename`

### 请求参数（Query）

| 字段 | 类型 | 必填 | 说明 |
|---|---|---|---|
| `taskId` | string | 是 | 任务 id |
| `title` | string | 是 | 新标题 |

### 调用示例

```bash
curl -X POST "$BASE/open-api/v1/record/convert/task/rename?taskId=100231&title=Q2策略会纪要"
```

### 响应示例

```json
{ "code": 200000, "message": "success", "data": true }
```

> 注意：rename 后 detail 接口可能仍返回旧 title（更新不及时）；任务列表 query 接口已更新，请以 query 为准。

---

## 9. 删除任务

`POST /open-api/v1/record/convert/task/delete`

### 请求参数（Query）

| 字段 | 类型 | 必填 | 说明 |
|---|---|---|---|
| `taskId` | string | 是 | 任务 id |

### 调用示例

```bash
curl -X POST "$BASE/open-api/v1/record/convert/task/delete?taskId=100231"
```

### 响应示例

```json
{ "code": 200000, "message": "success", "data": true }
```

> 注意：连续删除会触发限流；删除后任务在 list/detail 均不可见。

---

## 10. 查询本月转纪要额度

`GET /open-api/v1/record/convert/quota`

### 调用示例

```bash
curl -X GET "$BASE/open-api/v1/record/convert/quota"
```

### 响应数据：`RecordFundApiVO`

| 字段 | 类型 | 说明 |
|---|---|---|
| `totalWordCount` | int | 文字总数 |
| `usedWordCount` | int | 已使用的文字字数 |
| `totalMediaCount` | int | 媒体文件总时长 |
| `usedMediaCount` | int | 已使用的媒体文件时长 |
| `remainWordCount` | int | 待使用的字数额度 |
| `remainMediaCount` | int | 待使用的媒体额度 |

---

## 典型调用时序

**链接转纪要**
```
[可选] 10 查额度 → 1 提交(url) → 轮询 4/5 直到 status=1 → AI 纪要默认派生 .md → 7 下载文件流
```

**文件转纪要**
```
[可选] 10 查额度 → 2 上传文件(拿 fileId) → 3 创建任务(传 fileId) → 轮询 4 直到 status=1 → AI 纪要默认派生 .md → 7 下载文件流
```

> 上传成功但创建任务失败时，可使用同一个 `fileId` 修正参数后重试创建，无需重复上传。  
> 创建任务成功仅返回 `true`，不直接返回任务 id；后续状态和结果通过查询接口获取。

## 任务状态码

`0 进行中 / 1 成功 / 2 失败 / 3 超时 / 4 取消 / 5 等待 / 6 费用不足 / 8 录音中 / 9 传输中 / 10 转码中 / 11 文件过大 / 12 时长过大`

---

## 附：RecordTaskVO

| 字段 | 类型 | 说明 |
|---|---|---|
| `id` | string | 任务 id |
| `uploadFileName` | string | 上传的文件名 |
| `uploadFileUrl` | string | 原内容地址 |
| `title` | string | 标题 |
| `status` | int | 任务状态 |
| `type` | int/null | 业务类型：`10`-文件 `20`-文字 `30`-url `40`-app录音；newest 可为 null |
| `mediaType` | int/null | 媒体类型：`0`-未知 `1`-视频 `2`-音频 |
| `durationDetail` | int/null | 计数详情：媒体秒数 / 文字字数 |
| `platform` | string/null | 平台（中文） |
| `summaryDocxUrl` | string | AI 纪要 docx 下载地址 |
| `summaryRadioDocxUrl` | string | 转写稿 docx 下载地址 |
| `originMediaUrl` | string | 原始媒体下载地址 |
| `sourceLanguage` | string/null | 源语言 |
| `targetLanguage` | string/null | 目标语言 |
| `needTranslate` | int/null | 是否翻译 |
| `memo` | string/null | 备注 |
| `asrVersion` | int/null | asr 版本 |
| `createTime` | string | 创建时间，`yyyy-MM-dd HH:mm:ss` |

## 附：语言枚举
English-英语
Simplified Chinese-简体中文
Traditional Chinese-繁体中文
French-法语
German-德语
Russian-俄语
Japanese-日语
Arabic-阿拉伯语
Spanish-西班牙语
Korean-韩语
Italian-意大利语
Thai-泰语
Vietnamese-越南语
Latin American Spanish-拉美西班牙语
Canadian French-加拿大法语
Hindi-印地语
Bengali-孟加拉语
Portuguese-葡萄牙语
Brazilian Portuguese-巴西葡萄牙语
Kazakh-哈萨克语
Turkish-土耳其语
Dutch-荷兰语
Polish-波兰语
Ukrainian-乌克兰语
Romanian-罗马尼亚语
Indonesian-印尼语
Czech-捷克语
Hungarian-匈牙利语
Slovak-斯洛伐克语
Bulgarian-保加利亚语
Serbian-塞尔维亚语
Serbian (Latin letters)-塞尔维亚语(拉丁字母)
Serbian (Cyrillic letters)-塞尔维亚语(西里尔字母)
Croatian-克罗地亚语
Slovenian-斯洛文尼亚语
Icelandic-冰岛语
Finnish-芬兰语
Swedish-瑞典语
Danish-丹麦语
Norwegian-挪威语
Persian-波斯语
Albanian-阿尔巴尼亚语
Hebrew-希伯来语
Armenian-亚美尼亚语
Azerbaijani-阿塞拜疆语
Belarusian-白俄罗斯语
Catalan-加泰罗尼亚语
Estonian-爱沙尼亚语
Filipino-菲律宾语
Greek-希腊语
Gujarati-古吉拉特语
Haitian Creole-海地克里奥尔语
Irish-爱尔兰语
Latvian-拉脱维亚语
Lithuanian-立陶宛语
Macedonian-马其顿语
Malay-马来语
Marathi-马拉地语
Maltese-马耳他语
Mongolian (Cyrillic)-蒙古语(西里尔字)
Punjabi-旁遮普语
Sinhala-僧伽罗语
Tamil-泰米尔语
Lao-老挝语
Tibetan-藏语
Khmer-柬埔寨语
Latin-拉丁语
Uzbek-乌兹别克语
Burmese-缅甸语
Georgian-格鲁吉亚语
Telugu-泰卢固语
Malayalam-马拉雅拉姆语
Oriya-奥里亚语
Kannada-卡纳达语
Chinese Yueyu-粤语
