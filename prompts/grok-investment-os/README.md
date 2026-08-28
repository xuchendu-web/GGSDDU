# Grok 首席助理任命包

Grok Custom Agents 只有 **4 个槽位**，指令大约 **4000 字**。正确写法不是把一个超级提示词塞进一个人，而是：

**1 个首席助理编排 + 3 个专家执行 + 全局身份 + 4 条 Skill。**

Grok 不能真正调度 Cursor / AlphaPai。首席助理的产品是**可复制派工单**，由你 @ 专家或粘贴到别的工具。

## 10 分钟装上

1. grok.com 登录 SuperGrok 或 X Premium+
2. Settings → Customize → Custom Instructions：粘贴 `00-global-custom-instructions.txt`
3. Create Agent × 4：按 `agent-slots.md` 填 Name / Description / Auto-engage，指令分别粘贴 01–04
4. Settings → Skills：把 `skills/` 四个文件建成 `/立项` `/季报` `/决策` `/周会`
5. 建 Workspace「投研」；Memory 开；Fun Mode 关
6. **新开对话**，粘贴 `first-messages.md` 里的任命词

## 写 prompt 的原则（Grok 特别吃这一套）

- 合同，不是散文：ALWAYS / NEVER / OUTPUT 分块
- 负向规则比“请专业”有效：禁止愿景估值、禁止年化一次性利润
- 首席只做编排，专家互不抢活
- 每条新对话丢短锚点，长线程约 20 轮就新开，防人格漂移
- 重大标的开 Heavy，让四槽并行，再回首席合成

## 体系怎么变强

不是多问“XX 有没有投资价值”，而是固定节奏：

| 触发 | 命令 | 谁主责 |
| --- | --- | --- |
| 新标的 | `/立项` | 首席出派工 |
| 新财报 | `/季报` | 事实官 → 证伪官 |
| 要下单 | `/决策` | 组合官闸门，默认先别做 |
| 每周 | `/周会` | 打过程分，不荐股 |

完整可复制文本在本目录。浏览器说明页见同目录 `playbook.html`。
