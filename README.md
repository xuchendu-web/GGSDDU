# ShanghaoJin Signal Tracker

这是一个本地优先的 Serenity 风格复刻版，默认跟踪 `@ShanghaoJin` 的 X/Twitter 推文：从导出的 JSON 中抽取 `$SYMBOL`，写入 SQLite，并在静态 dashboard 里把观点时间点叠加到价格曲线上。

> 仅用于研究和可视化，不构成投资建议。

## 功能

- Python 标准库实现，无需前端构建工具。
- SQLite 存储 tweets、mentions、prices 和导入批次。
- 支持导入 X/Twitter GraphQL JSON 文件，并默认过滤为 `@ShanghaoJin` 的推文。
- 支持从 Yahoo Finance 拉取日线价格。
- 自带 demo seed，无需 X 登录态也能立即体验。
- 静态 dashboard 支持 symbol 搜索、过滤、价格曲线、mention 标记和 `@ShanghaoJin` 最新观点流。

## 快速开始

```bash
python3 scripts/ingest.py seed --reset
python3 scripts/server.py --port 8787
```

打开：

```text
http://127.0.0.1:8787
```

## 常用命令

生成可演示的本地数据：

```bash
python3 scripts/ingest.py seed --reset
```

查看数据库统计：

```bash
python3 scripts/ingest.py stats
```

导入你保存的 X/Twitter GraphQL JSON；默认只保留 `@ShanghaoJin` 的推文：

```bash
python3 scripts/ingest.py import-json --path data/raw --source x-json
```

如果要跟踪其他账号：

```bash
python3 scripts/ingest.py import-json --path data/raw --target OtherHandle
```

如果要导入文件中的全部作者：

```bash
python3 scripts/ingest.py import-json --path data/raw --include-all
```

按已提及的 symbol 下载 Yahoo 日线价格：

```bash
python3 scripts/ingest.py prices --days 500 --min-mentions 1
```

启动 dashboard：

```bash
python3 scripts/server.py --host 127.0.0.1 --port 8787
```

## 数据位置

- SQLite: `data/serenity.sqlite`
- 可选原始 JSON: `data/raw/*.json`
- 前端: `dashboard/index.html`, `dashboard/styles.css`, `dashboard/app.js`
- API: `scripts/server.py`
- 数据管道: `scripts/ingest.py`

## API

- `GET /api/health`
- `GET /api/summary`
- `GET /api/feed?limit=40`
- `GET /api/symbol/NVDA`

## 说明

本项目参考 Serenity 的产品形态和数据流重新实现，没有直接复制上游源码。真实 X/Twitter cookie、curl 文件或登录态导出不应提交到仓库。
