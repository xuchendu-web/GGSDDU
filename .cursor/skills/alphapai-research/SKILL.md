---
name: alphapai-research
description: 调用 Alpha派 OpenPai 金融投研 API，并基于不同金融信源规范使用返回数据。用于公告、机构研报、会议纪要、点评（brokerage commentary）、蓝宝书、机构热议、投研知识检索、PaiPai问答、Agent功能（PaiPai Agent）、录音转记、自选股、社媒订阅、预约会议，以及公告/研报下载、公众号详情、文章详情、选股、选基、公司或行业研究等任务。用户提到 Alpha派、AlphaPai、OpenPai、PaiPai 或上述投研功能时使用本 skill。
metadata:
    version: 2.0.1
---

# AlphaPai Research

通过 `scripts/alphapai_client.py` 调用 OpenPai API。优先执行现有 CLI，不手写重复请求代码。

## 操作规则

1. 先根据下方路由表定位产品功能，再读取对应 reference。
2. 使用列表接口实时获取 ID；公告、研报、点评等加密 ID 可能过期，不复用旧示例 ID。
3. JSON 接口完整保留服务端响应；PaiPai问答和 PaiPai Agent 将 SSE 聚合为 `code`、`message`、`questionId`、`answer`、`references`。
4. 用户要求查看接口原文、原始资料或 PaiPai 原回答时，完整呈现正文、Markdown 结构和引用，不擅自截断或改写。
5. `code != 200000` 视为失败。兼容错误字段 `message` 和 `msg`，不要把 HTTP 200 当作业务成功。
6. 下载后检查文件类型。PDF 应以 `%PDF` 开头，ZIP 应可解压校验，JSON 应可解析。
7. 处理公告或研报正文时，默认下载深度解析的 Markdown 版本；它最适合 AI/Agent 阅读。仅在用户明确需要原始版式、结构化数据或完整解析包时，分别下载 PDF、JSON 或 ZIP。
8. 执行关注、订阅、创建、重命名、删除等写操作前确认目标；验证写接口时仅操作本次创建的临时资源并清理。
9. 未获得真实响应时不要猜测字段。查阅 reference；仍不确定时使用当前配置实际调用。

## 投研数据使用规则

1. 只使用本次 OpenPai 返回内容和用户提供的材料；资料不足时说明缺口，不用外部知识或推测补全事实、数据和观点。
2. 优先使用具体数据和原始披露。遇到以“指标：”开头的结构化数据时优先分析，并核对指标定义、报告期、频率、单位和统计口径。
3. 明确区分已披露事实、管理层口径、卖方观点和自主测算；不得把预测写成实际值，也不得把计算结果写成原文结论。
4. 关键数据尽量用两个独立来源交叉验证。来源冲突时检查时间、范围、单位、合并口径、调整前后及实际值/预测值，并说明采用的口径。
5. 优先使用近期资料。财务数据使用最新已披露报告期，事件和观点同时标明发生时间与资料发布时间，不使用未来时间作为检索范围。
6. 自主测算只能使用资料中的原始数据和明确假设，需展示输入、公式与单位，并标注为“测算”或“推演”。
7. 来源标注优先指向公告、财报、会议纪要等底层原文；仅展示标题、机构/作者、发布日期和可访问链接，不暴露内部文档 ID 或检索实现细节。

## 检索方法

1. 多类文档分别检索，例如公告、研报和纪要各走对应接口，不把一次语义查询当作全部样本。
2. 第一轮用较宽关键词和合理时间范围建立全局认知，随后按公司、指标、事件和分歧点精确补缺。
3. 任一查询连续两次没有有效新增信息时，调整关键词、筛选条件或切换互补工具，不重复无效调用。
4. 时间参数表示资料发布时间；不得使用未来日期。财务分析优先最新已披露报告期并检查预告/快报，行业与公司事件优先近一个月，研报与纪要优先近三个月；重大事项回溯完整事件链。
5. 记录已检索的数据源、时间范围、筛选条件和明显缺口，避免把“没有召回”误判为“没有发生”。

## 金融数据信源特征

| 信源                                                   | 主要价值                               | 使用注意                                           |
| ------------------------------------------------------ | -------------------------------------- | -------------------------------------------------- |
| 公司公告、定期报告（`ann`）                            | 权威的财务数据、正式条款和重大事项     | 作为事实基准；检查报告期、单位、合并口径和修订公告 |
| 指标库（`edb`）                                        | 宏观、行业、财务和行情的结构化定量数据 | 适合趋势和对比分析；先核对指标定义、频率与数据日期 |
| 官方路演（`roadShow_ir`）                              | 管理层对经营现状和未来指引的直接说明   | 属于一手口径，但主观预期仍需与公告和后续数据验证   |
| 路演与会议纪要（`roadShow`、`roadShow_us`）            | 业绩会、渠道和产业边际变化，时效性高   | 确认发言主体；关键事实尽量回到公告或其他独立来源   |
| 机构研报（`report`、`foreign_report`、`third_report`） | 分析框架、盈利预测和行业比较           | 属于加工观点；关注机构、日期、预测期和核心假设     |
| 券商点评（`comment`）                                  | 快速捕捉事件与短期边际变化             | 更新快但深度不稳定，适合作为线索而非事实基准       |
| 社媒（`social_media`）                                 | 补充公司动态、产业观察和非正式观点     | 主观性较强，需核验作者身份、时间和原始出处         |

确认关键事实时，一般遵循：**公告/定期报告 > 结构化指标 > 官方路演 > 其他纪要 > 研报 > 点评 > 社媒**。权威性与时效性应分开判断：二手来源可用于发现最新线索，最终结论尽量回到一手来源。

## 配置

推荐使用环境变量，避免把 API Key 写入仓库：

```bash
export ALPHAPAI_API_KEY='<YOUR_API_KEY>'
export ALPHAPAI_BASE_URL='https://open-api.rabyte.cn'  # 可省略
```

也可写入本地 `config.json`：

```bash
python scripts/alphapai_client.py config --set-key '<YOUR_API_KEY>'
python scripts/alphapai_client.py hello
```

默认完整地址为：

```text
https://open-api.rabyte.cn/alpha/open-api/v1/<path>
```

## 产品功能路由

名称严格采用 `doc/产品概述.md`。

| 产品分类        | 功能                         | CLI                    | 需要读取的 reference                               |
| --------------- | ---------------------------- | ---------------------- | -------------------------------------------------- |
| 文档类数据      | 公告                         | `announcement`         | `references/announcement_api_reference.md`         |
| 文档类数据      | 机构研报                     | `research-report`      | `references/research_report_api_reference.md`      |
| 文档类数据      | 会议纪要                     | `meeting-minutes`      | `references/meeting_minutes_api_reference.md`      |
| 文档类数据      | 点评（brokerage commentary） | `brokerage-commentary` | `references/brokerage_commentary_api_reference.md` |
| Alpha派特色数据 | 蓝宝书                       | `bluebook`             | `references/bluebook_api_reference.md`             |
| Alpha派特色数据 | 机构热议                     | `hot-topics`           | `references/hot_topics_api_reference.md`           |
| AI功能          | 投研知识检索                 | `recall`               | `references/recall_api_reference.md`               |
| AI功能          | PaiPai问答                   | `qa`                   | `references/qa_api_reference.md`                   |
| AI功能          | Agent功能（PaiPai Agent）    | `agent`                | `references/agent_api_reference.md`                |
| Alpha派功能     | 录音转记                     | `recording`            | `references/recording_summary_api_reference.md`    |
| Alpha派功能     | 自选股                       | `watchlist`            | `references/watchlist_public_api_reference.md`     |
| Alpha派功能     | 社媒订阅                     | `social`               | `references/social_api_reference.md`               |
| Alpha派功能     | 预约会议                     | `meeting-booking`      | `references/meeting_booking_api_reference.md`      |
| 辅助能力        | 个股公告期列表               | `report`               | `references/agent_api_reference.md`                |
| 辅助能力        | 投研图表搜索                 | `image`                | `references/image_api_reference.md`                |

公共鉴权、响应、SSE 和引用结构见 `references/base_api_reference.md`；总索引见 `references/api_reference.md`。

## 会议与纪要数据边界

| 数据类别 | 数据来源与范围                                                            | CLI               | AI 纪要与 ASR 逐字稿                                                                         |
| -------- | ------------------------------------------------------------------------- | ----------------- | -------------------------------------------------------------------------------------------- |
| 会议纪要 | Alpha派聚合的公开投研会议数据，包括公司交流、业绩会、专家交流和行业分析等 | `meeting-minutes` | 列表用 `availableNoteTypes` 判断可用类型，详情指定 `ai_note` 或 `asr_note` 读取              |
| 录音转记 | 当前用户通过 Alpha派上传的文件、音视频链接或现场录音生成的个人转记任务    | `recording`       | 任务完成后 `download` 直接返回包含 AI 纪要/逐字稿等产物的 zip 文件流；不再返回分别的下载 URL |
| 预约会议 | 当前用户通过会议机器人预约并录制的会议，以及由录音生成的个人纪要          | `meeting-booking` | 已生成列表用 `availableNoteTypeList` 判断可用类型，详情指定 `ai_note` 或 `asr_note` 读取     |

三类能力都支持 **AI 纪要**和 **ASR 逐字稿**：`ai_note` 是 AI 提炼的结构化纪要，`asr_note` 是语音识别生成的原始逐字转写。单条记录不一定同时具备两种内容，调用详情或下载前必须检查可用类型或任务状态。

根据数据来源选择接口：查公开投研会议用 `meeting-minutes`；查用户自行上传、链接提交或现场录音生成的纪要用 `recording`；查会议机器人预约录制的会议用 `meeting-booking`。三类数据的权限和任务标识不同，不在接口之间混用 `roadshowId`、`taskId` 或 `msgId`。

## 快速调用

### 公告

```bash
# 列表：先获取实时 announcementId
python scripts/alphapai_client.py announcement list \
  --stock-code 600519.SH --page-size 5 \
  --sort-by actual_publish_time --sort-order desc

# 默认下载适合 AI/Agent 阅读的深度解析 Markdown
python scripts/alphapai_client.py announcement parsing-download \
  --id '<ANNOUNCEMENT_ID>' --download-type markdown \
  --output ./announcement_parsing.md

# 仅在用户明确需要原始 PDF 时下载
python scripts/alphapai_client.py announcement pdf-download \
  --id '<ANNOUNCEMENT_ID>' --output ./announcement.pdf
```

公告解析产物支持 `markdown`、`json`、`zip`，默认只下载 `markdown`；JSON 用于结构化处理，ZIP 用于获取完整解析包。`hasPdf=true` 只证明可下载 PDF，不保证已生成所有解析产物。

### 机构研报

```bash
python scripts/alphapai_client.py research-report list \
  --scope domestic --keyword 人工智能 --page-size 5
python scripts/alphapai_client.py research-report detail --report-id '<REPORT_ID>'

# 默认下载适合 AI/Agent 阅读的深度解析 Markdown
python scripts/alphapai_client.py research-report parsing-download \
  --document-id '<REPORT_ID>' --document-type report \
  --download-type markdown --output ./report.md

# 仅在用户明确需要原始 PDF 时下载
python scripts/alphapai_client.py research-report pdf-download \
  --report-id '<REPORT_ID>' --output ./report.pdf
```

研报解析产物同样默认只下载 `markdown`；JSON 用于结构化处理，ZIP 用于获取完整解析包。筛选枚举必须使用 reference 中的代码值，例如 `--language en`、`--country-region united_states`、`--page-count-range lt_10`。

### 会议纪要与点评

```bash
python scripts/alphapai_client.py meeting-minutes list \
  --market-type A --keyword 光模块 --page-size 5
python scripts/alphapai_client.py meeting-minutes detail \
  --roadshow-id '<ROADSHOW_ID>' --note-type ai_note

python scripts/alphapai_client.py brokerage-commentary list \
  --scope all --keyword 新能源 --page-size 5
python scripts/alphapai_client.py brokerage-commentary detail \
  --comment-id '<COMMENT_ID>'
python scripts/alphapai_client.py brokerage-commentary event-list \
  --market-scope a --event-type performance_report --page-size 5
```

旧命令名 `review` 仅作为兼容别名；新调用统一使用 `brokerage-commentary`。

### 蓝宝书与机构热议

```bash
python scripts/alphapai_client.py bluebook batch-list \
  --batch-type all --batch-scope all --page-size 5
python scripts/alphapai_client.py bluebook topic-list \
  --batch-type all --batch-scope domestic --keyword AI --page-size 5
python scripts/alphapai_client.py bluebook topic-detail \
  --topic-id '<TOPIC_ID>' --batch-scope domestic

python scripts/alphapai_client.py hot-topics board-list \
  --inst-type 公募 私募 --limit 10
```

### 投研知识检索与 PaiPai问答

```bash
python scripts/alphapai_client.py recall \
  --query '宁德时代储能业务进展' --type roadShow,report,ann

python scripts/alphapai_client.py qa \
  --question '贵州茅台近期经营情况如何？' --mode Flash

python scripts/alphapai_client.py qa \
  --question '比较三家光模块公司的竞争力' --mode Think \
  --web-search --deep-reasoning
```

`qa` 在线上始终按 SSE 处理。需要多轮上下文时使用 `--context`，需要日期范围时使用 `--start`、`--end`。

### Agent功能（PaiPai Agent）

| mode | 产品能力       | 必填业务参数                                                                   |
| ---: | -------------- | ------------------------------------------------------------------------------ |
|    1 | 个股业绩点评   | `--stock`、`--report-type`、`--report-id`、`--report-title`、`--report-period` |
|    2 | 公司一页纸     | `--stock`                                                                      |
|    3 | 个股调研大纲   | `--stock`                                                                      |
|    5 | 主题选股       | `--template-text`                                                              |
|    7 | 投资逻辑       | `--stock`                                                                      |
|    8 | 可比公司       | `--stock`                                                                      |
|    9 | 观点 Challenge | `--template-text`                                                              |
|   11 | 行业一页纸     | `--industry`                                                                   |
|   12 | 个股选基       | `--stock-list`、`--report-date`、`--fund-type`                                 |
|   13 | 主题选基       | `--report-date`、`--fund-type`                                                 |
|   15 | 画图           | 两个 `--picture-color` 值、`--picture-style`                                   |

通用形式：

```bash
python scripts/alphapai_client.py agent --mode <MODE> \
  --question '<QUESTION>' <MODE_SPECIFIC_ARGS>
```

mode 1 先执行：

```bash
python scripts/alphapai_client.py report --code 603380.SH
```

将返回的 `stockReportId`、`stockReportTitle`、`reportPeriod`、`reportType` 分别映射到 `--report-id`、`--report-title`、`--report-period`、`--report-type`。

mode 12/13 缺少 `--if-annual` 时 CLI 补 `0`，建议显式传 `--if-annual 0|1`。mode 15 的两个颜色为不含 `#` 的 HEX，例如 `2A66F6 A5A8AF`。

### 录音转记

```bash
python scripts/alphapai_client.py recording quota
python scripts/alphapai_client.py recording submit-url --url '<MEDIA_URL>'

# 本地文件需先上传，再用 fileId 创建任务
python scripts/alphapai_client.py recording upload \
  --file-path ./meeting.mp3 --file-type 10
python scripts/alphapai_client.py recording submit-file \
  --file-id '<FILE_ID>' --file-name meeting.mp3 \
  --language-type 10 --file-type 10

python scripts/alphapai_client.py recording query --page-size 10
python scripts/alphapai_client.py recording detail --task-id '<TASK_ID>'

# download 直接下载任务最终产物（接口返回 zip 文件流，内含 AI 纪要/逐字稿等）
python scripts/alphapai_client.py recording download \
  --task-id '<TASK_ID>' --output ./recording_result.zip

# ai-summary-download 是 download 的别名，行为一致
python scripts/alphapai_client.py recording ai-summary-download \
  --task-id '<TASK_ID>' --output ./recording_result.zip
```

创建任务返回 `true` 而不是任务 ID；使用 `query` 或 `newest` 找到任务。任务处理完成（`status=1`）后，`download` 接口直接返回包含最终产物（AI 纪要、ASR 逐字稿等）的 zip 文件流，CLI 流式落盘；不再返回分别的下载 URL，也无需再手动派生或二次下载。若只拿到了单个文件的 `type` 与 S3 `filePath`，仍可用 `download-file` 走通用文件下载接口。

### 自选股

```bash
python scripts/alphapai_client.py watchlist list
python scripts/alphapai_client.py watchlist exist --stock-code 600519.SH
python scripts/alphapai_client.py watchlist num
python scripts/alphapai_client.py watchlist group-list
python scripts/alphapai_client.py watchlist group-add --name 临时验证组
python scripts/alphapai_client.py watchlist follow \
  --codes 600519.SH --group-code '<GROUP_CODE>'
python scripts/alphapai_client.py watchlist unfollow \
  --codes 600519.SH --group-code '<GROUP_CODE>'
python scripts/alphapai_client.py watchlist group-delete \
  --group-codes '<GROUP_CODE>'
```

不带 `--group-code` 查询全部时不要传空字符串。删除分组会连带删除组内关注。

### 社媒订阅

```bash
python scripts/alphapai_client.py social account-list
python scripts/alphapai_client.py social account-search --word 策略 --page-size 5
python scripts/alphapai_client.py social account-detail --id '<ACCOUNT_ID>'
python scripts/alphapai_client.py social article-list \
  --word 新能源 --page-size 5 --exclude-content
python scripts/alphapai_client.py social article-detail --id '<ARTICLE_ID>'
python scripts/alphapai_client.py social subscribe --ids '<ACCOUNT_ID>'
python scripts/alphapai_client.py social unsubscribe --ids '<ACCOUNT_ID>'
```

账号或文章列表通常不返回 `supplierId`；不传 `--supplier-id` 时 CLI 会传字符串 `"null"`，由服务端选择默认供应商。

### 预约会议

```bash
python scripts/alphapai_client.py meeting-booking list --page-size 5
python scripts/alphapai_client.py meeting-booking generated-list --page-size 5
python scripts/alphapai_client.py meeting-booking detail \
  --meeting-id '<MEETING_ID>' --include-notes true --note-preview-length 200
python scripts/alphapai_client.py meeting-booking summary-detail \
  --meeting-id '<MEETING_ID>' --note-type ai_note --format markdown
```

删除预约属于破坏性操作，只能删除用户明确指定或本次验证创建的记录。

## 参考文档读取规则

- 处理具体功能前读取对应 reference，不要只依赖本文件的快速示例。
- 调试鉴权、错误码、SSE、引用结构或下载时读取 `references/base_api_reference.md`。
- reference 与真实响应冲突时，以当前实际调用为准，并同步修订 reference。
- 长响应中的正文、HTML、Markdown 可以很长；处理字段结构时仍须保留其类型与 nullable 信息。

## 文件结构

| 路径                         | 职责                                             |
| ---------------------------- | ------------------------------------------------ |
| `scripts/alphapai_client.py` | CLI 入口与命令注册                               |
| `scripts/alphapai_base.py`   | 配置、HTTP、SSE、下载和公共错误处理              |
| `scripts/cmd_*.py`           | 各产品功能的确定性调用实现                       |
| `references/*.md`            | 面向各功能接口的参数、响应结构、示例和已验证限制 |
