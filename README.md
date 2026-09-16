# 投资反思卡微信小程序

微信原生 `TypeScript + WXML + WXSS` 小程序：从 144 条人工审核白名单中随机展示一张投资者教育与决策反思卡，并支持本地收藏、最近记录、`drawId` 分享还原、匿名归因、实验分组和事件上报。

产品不采集用户心中所想，不提供个股或产品推荐、买卖指令、目标价、收益承诺或行情方向判断。

## 目录

- `miniprogram/`：小程序页面、本地白名单和本地存储。
- `cloudfunctions/draw/`：抽取、还原、远程下线、实验和事件上报。
- `tests/`：内容池、分享隐私、云端生命周期与工程结构测试。
- `docs/product-spec.md`：产品规格、八场景、增长闭环与指标。
- `docs/content-review.md`：内容双审、版本、下线与熔断。
- `docs/launch-runbook.md`：云开发配置、验收、提审和回滚。

## 本地验证

```bash
npm ci
npm run verify
```

## 微信开发者工具

使用仓库根目录导入项目。开发阶段可使用 `touristappid` 做静态预览；部署与真机测试前须在 `project.config.json` 配置正式 AppID，并按 `docs/launch-runbook.md` 创建云环境及部署函数。
