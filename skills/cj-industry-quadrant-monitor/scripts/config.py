# -*- coding: utf-8 -*-
"""industry-quadrant-monitor · 配置与常量（第三期模块拆分）

集中所有魔数、阈值、权重、行业列映射、象限定义与自定义异常。
其他模块只从这里 import，避免散落各处的硬编码（规划文档 S3）。
"""

from pathlib import Path

# 本模块（scripts 目录）与技能根目录，供 datasource / cache / CLI 复用
HERE = Path(__file__).resolve().parent
SKILL_ROOT = HERE.parent

# ═══════════════════════════════════════════════════════════════
# 退出码语义（供自动化 / agent 判断，见 EXIT_*）
# ═══════════════════════════════════════════════════════════════
EXIT_OK = 0
EXIT_ENV = 2      # 依赖缺失 / 环境不可用
EXIT_ARGS = 3     # 参数非法
EXIT_DATA = 4     # 数据获取失败或覆盖率不达标
EXIT_EMPTY = 5    # 计算结果为空
EXIT_IO = 6       # 输出路径不可写


class EnvError(RuntimeError):
    """环境/依赖问题"""


class ArgError(RuntimeError):
    """参数问题"""


class DataError(RuntimeError):
    """数据获取或质量问题"""


class EmptyResultError(RuntimeError):
    """计算结果为空"""


class OutputError(RuntimeError):
    """输出不可写"""


# ═══════════════════════════════════════════════════════════════
# 取数与打分默认参数（D2/S3：集中管理，影响结论的暴露为 CLI 参数）
# ═══════════════════════════════════════════════════════════════
DEFAULT_FIN_BATCH = 300     # v2 是 500，实测 11 批超时 6 批；300 + 重试后 18 批全过
DEFAULT_FACTOR_BATCH = 800  # get_factor_data 实测超过约 800 只代码容易超时
DEFAULT_MAX_RETRY = 5
DEFAULT_MIN_COVERAGE = 0.95

# 财务表字段（合并利润表）
FIN_FIELDS = ["截止日", "数据报告期", "报告类型", "营业总收入", "归属于母公司所有者净利润"]
REPORT_TYPES = ["一季报", "三季报", "年报", "半年报"]

# 申万行业列名（随 --sw-level 切换）
SW_LEVEL_MAP = {
    "1": "申万一级行业名称",
    "2": "申万二级行业名称",
    "3": "申万三级行业名称",
}
SW_LEVEL_LABEL = {"1": "申万一级", "2": "申万二级", "3": "申万三级"}

# 报告期末日合法后缀（参数校验用）
QUARTER_ENDS = ("0331", "0630", "0930", "1231")

# Winsorize 分位（截断极端值，规划文档 S3）
WINSOR_LOWER = 0.01
WINSOR_UPPER = 0.99
# 增速截断（L8：扭亏/微利基数噪声，靠双层压制）
PCT_CLIP = (-1000.0, 1000.0)
# 行业 PE 上限过滤（PETTM 合理区间）
PE_FLOOR = 0.0
PE_CEIL = 1000.0
# PE 分位最小样本（行业窗口内点数）
PE_MIN_POINTS = 5

# 权重（规划文档 S3：影响结论，本工具锁死 0.5/0.5 + 0.7/0.3，未暴露 CLI）
FUND_W = 0.5          # 净利润增速_z / 营收增速_z 各 0.5
TECH_W = 0.5          # 价格动量_z / 量能变化_z 各 0.5
IMPROVE_TECH_W = 0.7  # 改善表排序：技术面相对变化权重
IMPROVE_FUND_W = 0.3  # 改善表排序：基本面得分权重

# 气泡尺寸范围（create_report 中 clip）
BUBBLE_MIN = 5
BUBBLE_MAX = 95

# SW3（~340 个行业）可视化降级（D22）：行业数超阈值时散点只标注 TopN
SW3_WARN_N = 100
SW3_LABEL_TOPN = 12


# ═══════════════════════════════════════════════════════════════
# 象限定义：数据层只存 Q1~Q4，显示名/颜色/emoji 走映射表（S4）
# ═══════════════════════════════════════════════════════════════
QUADRANT_ORDER = ["Q1", "Q2", "Q3", "Q4"]
QUADRANT_LABEL = {
    "Q1": "🔴 相对较强行业",
    "Q2": "🟡 情绪驱动",
    "Q3": "🟢 相对较弱行业",
    "Q4": "🔵 价值洼地",
}
QUADRANT_COLOR = {
    "Q1": "#E74C3C",
    "Q2": "#F39C12",
    "Q3": "#27AE60",
    "Q4": "#3498DB",
}
# emoji 单一真相源（与 QUADRANT_COLOR / 中国习惯 红=强 绿=弱 对齐，避免散点填充色与标签 emoji 相反）
QUADRANT_EMOJI = {
    "Q1": "🔴",
    "Q2": "🟡",
    "Q3": "🟢",
    "Q4": "🔵",
}
# 判定用的语义键（与 QUADRANT_LABEL 中文子串匹配解耦，见 S4/L7）
QUADRANT_KEY = {
    "Q1": "相对较强",
    "Q2": "情绪",
    "Q3": "相对较弱",
    "Q4": "洼地",
}


def assign_quadrant(fund, tech):
    """纯函数：根据基本面/技术面得分返回象限键 Q1~Q4（不含 emoji）。

    数据层只存 Q1~Q4，显示名由 QUADRANT_LABEL 映射（S4）。
    阈值统一为 >=0（L6：象限与改善表同一口径）。
    """
    if fund >= 0 and tech >= 0:
        return "Q1"
    if fund < 0 and tech >= 0:
        return "Q2"
    if fund < 0 and tech < 0:
        return "Q3"
    return "Q4"
