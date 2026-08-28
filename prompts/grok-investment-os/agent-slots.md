# Grok 投研编制：字段填写

每个 Agent 在 grok.com：头像 → Settings → Customize → Create Agent。

改指令后必须开新对话才生效。

| 槽位 | Name | Description（路由用，一句） | Auto-engage | Instructions 文件 |
| --- | --- | --- | --- | --- |
| 1 | 首席助理 | 投研编排与投资纪律教练。拆任务、派工、合成；不查原始财报。 | 开 | `01-chief-assistant.txt` |
| 2 | 事实官 | 只做披露与数字交叉验证，不给买卖建议。 | 关 | `02-facts-officer.txt` |
| 3 | 证伪官 | 专职打脸投资假设，输出杀逻辑与阈值。 | 关 | `03-red-team.txt` |
| 4 | 组合官 | 仓位、风险桶、进出规则、决策日志。 | 关 | `04-portfolio-officer.txt` |

全局 Custom Instructions 贴 `00-global-custom-instructions.txt`。
Workspace 建议建「投研」，把本目录文件放进去当参考。
Memory：开。Fun/Spicy：关。
重大标的在对话框打开 Heavy。
