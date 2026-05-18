# 资产配置视角下的公募FOF投资新思路 —— 演示稿生成

面向银行总部、约 60 分钟、42 页中文 `.pptx` 演示稿，由 Python 脚本一键生成。

## 主题与结构

双主线：

1. **全球多元资产研究与对比** —— A 股 / 港股 / 海外权益 / 黄金 / 商品 / 利率债 / 信用债 / REITs
2. **组合管理** —— 风险预算 / 风险控制 / 收益拆解，全部围绕**公募 FOF**可用工具与监管边界展开。

七大章节 + Q&A，共 42 页（封面、目录、正文 40 页、结语）。完整大纲见 `outline.md`。

## 环境要求

- Python ≥ 3.10
- 系统中存在任意中文字体（脚本会自动探测 `WenQuanYi Micro Hei` / `Noto Sans CJK SC` / `SimHei` / `Microsoft YaHei`）

## 一键构建

```bash
pip install -r requirements.txt
python scripts/charts.py        # 生成 6 张图表 PNG 到 charts/
python scripts/build_pptx.py    # 生成 output/FOF资产配置新思路.pptx
```

或直接：

```bash
make all        # 若有 make
```

## 文件结构

```
.
├── README.md
├── requirements.txt
├── outline.md                  # 42 页逐页讲稿（演讲者备注）
├── scripts/
│   ├── charts.py               # matplotlib 生成数据图
│   └── build_pptx.py           # python-pptx 生成 PPT
├── charts/                     # 运行后生成的图表 PNG
└── output/
    └── FOF资产配置新思路.pptx  # 最终交付物
```

## 数据合规说明

所有数据为基于公开市场口径（指数年度收益、波动率、相关性等）的**示意性估算**，每张数据页页脚已标注"数据来源：公开市场口径整理，仅供示意"。正式分享前请使用 Wind / Bloomberg 实际数据进行校核与替换。

## 二次编辑

生成后的 `.pptx` 可在 PowerPoint / WPS / Keynote 中直接打开并套用银行的母版样式。
