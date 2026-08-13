"""投研 Agent CLI 子命令"""

import sys
from typing import Dict, List, Optional

from alphapai_base import (
    AlphaPaiClient,
    SseApiError,
    print_json,
    parse_stock,
    require_config,
)

VALID_MODES = [1, 2, 3, 5, 7, 8, 9, 11, 12, 13, 15]

# 各 mode 的本地必填校验：(必填 argparse 属性列表, 中文说明)
_MODE_REQUIREMENTS = {
    1: (["stock", "report_type", "report_id", "report_title", "report_period"],
        "业绩点评需 --stock 及公告四要素（--report-type/--report-id/--report-title/--report-period，先经 report 命令查询）"),
    2: (["stock"], "公司一页纸需 --stock"),
    3: (["stock"], "调研大纲需 --stock"),
    5: (["template_text"], "主题选股需 --template-text（选股主题，与 --question 一致）"),
    7: (["stock"], "投资逻辑需 --stock"),
    8: (["stock"], "可比公司需 --stock"),
    9: (["template_text"], "观点 Challenge 需 --template-text（待 Challenge 的观点）"),
    11: (["industry"], "行业一页纸需 --industry"),
    12: (["stock_list", "report_date", "fund_type"],
         "个股选基需 --stock-list --report-date --fund-type"),
    13: (["report_date", "fund_type"], "主题选基需 --report-date --fund-type"),
    15: (["picture_color", "picture_style"], "画图需 --picture-color 与 --picture-style"),
}


def stock_agent(
    client: AlphaPaiClient,
    question: str,
    agent_mode: int,
    stock: Optional[Dict] = None,
    template: int = 0,
    template_text: str = "",
    report_type: Optional[str] = None,
    stock_report_id: Optional[str] = None,
    stock_report_title: Optional[str] = None,
    stock_report_period: Optional[str] = None,
    template_concern: Optional[str] = None,
    request_select_start_time: Optional[str] = None,
    request_select_end_time: Optional[str] = None,
    input_industry: Optional[str] = None,
    report_date: Optional[str] = None,
    fund_type: Optional[str] = None,
    if_annual: Optional[int] = None,
    stock_list: Optional[List[Dict]] = None,
    picture_color: Optional[List[str]] = None,
    picture_style: Optional[str] = None,
    source: Optional[int] = None,
    language: Optional[str] = None,
    only_answer: Optional[bool] = None,
) -> Dict:
    """Alpha派投研Agent接口，SSE 流式请求"""
    payload: Dict = {
        "question": question,
        "agentMode": agent_mode,
        "template": template,
        "templateText": template_text,
    }
    if stock:
        payload["stock"] = stock
    if report_type:
        payload["reportType"] = report_type
    if stock_report_id:
        payload["stockReportId"] = stock_report_id
    if stock_report_title:
        payload["stockReportTitle"] = stock_report_title
    if stock_report_period:
        payload["stockReportPeriod"] = stock_report_period
    if template_concern:
        payload["templateConcern"] = template_concern
    if request_select_start_time:
        payload["requestSelectStartTime"] = request_select_start_time
    if request_select_end_time:
        payload["requestSelectEndTime"] = request_select_end_time
    if input_industry:
        payload["inputIndustry"] = input_industry
    if report_date:
        payload["reportDate"] = report_date
    if fund_type:
        payload["fundType"] = fund_type
    if if_annual is not None:
        payload["ifAnnual"] = if_annual
    if stock_list:
        payload["stockList"] = stock_list
    if picture_color:
        payload["pictureColor"] = picture_color
    if picture_style:
        payload["pictureStyle"] = picture_style
    if source is not None:
        payload["source"] = source
    if language:
        payload["language"] = language
    if only_answer is not None:
        payload["onlyAnswer"] = only_answer
    return client.parse_sse(
        client._post("/alpha/open-api/v1/paipai/stock/agent", payload, stream=True)
    )


def register_parser(sub):
    p = sub.add_parser(
        "agent", help="Agent功能（PaiPai Agent）：公司一页纸、业绩点评、调研大纲等"
    )
    p.add_argument(
        "--mode",
        "-m",
        type=int,
        required=True,
        choices=VALID_MODES,
        help="Agent模式: 1=业绩点评 2=公司一页纸 3=调研大纲 5=主题选股 "
        "7=投资逻辑 8=可比公司 9=观点Challenge 11=行业一页纸 "
        "12=个股选基 13=主题选基 15=画图",
    )
    p.add_argument("--question", "-q", required=True, help="问题内容")
    p.add_argument(
        "--stock",
        metavar="CODE:NAME",
        help="股票信息，格式 CODE:NAME，如 300014.SZ:亿纬锂能",
    )
    p.add_argument(
        "--template",
        type=int,
        default=0,
        help="模版类型: 0=alpha派模板(默认) 1=用户模板",
    )
    p.add_argument(
        "--template-text", metavar="TEXT", help="用户模版正文（template=1时需传）"
    )
    p.add_argument(
        "--report-type", metavar="TYPE", help="报告类型（业绩点评必填），如: 季报"
    )
    p.add_argument("--report-id", metavar="ID", help="公告ID（业绩点评必填）")
    p.add_argument(
        "--report-title", metavar="TITLE", help="报告标题（业绩点评必填）"
    )
    p.add_argument(
        "--report-period",
        metavar="PERIOD",
        help="报告期（业绩点评必填），如: 2025年一季报",
    )
    p.add_argument(
        "--concern", metavar="TEXT", help="用户关注内容（业绩点评/观点Challenge选填）"
    )
    p.add_argument(
        "--industry", metavar="NAME", help="行业信息（行业一页纸必填），如: 白酒"
    )
    p.add_argument(
        "--report-date",
        metavar="DATE",
        help="报告期（个股选基/主题选基必填），如: 2025-09-30",
    )
    p.add_argument(
        "--fund-type",
        metavar="TYPE",
        help="基金类型（个股选基/主题选基必填）: 全部|主动|指数|ETF",
    )
    p.add_argument(
        "--if-annual", type=int, choices=[0, 1], help="是否年报: 0=否 1=是"
    )
    p.add_argument(
        "--stock-list",
        nargs="+",
        metavar="CODE:NAME",
        help="股票列表（个股选基必填），如: 601231.SH:环旭电子 300308.SZ:中际旭创",
    )
    p.add_argument(
        "--picture-color",
        nargs="+",
        metavar="HEX",
        help="图片颜色HEX值（画图必填），如: 2A66F6 A5A8AF",
    )
    p.add_argument(
        "--picture-style",
        metavar="STYLE",
        help="图片风格（画图必填）: PPT风格|科普风格",
    )
    p.add_argument(
        "--source",
        type=int,
        choices=[0, 1],
        help="画图样式: 0=仅图片(默认) 1=图文",
    )
    p.add_argument(
        "--language", metavar="LANG", help="语言（美股公司一页纸可选）: 中文|英文"
    )
    p.add_argument(
        "--only-answer",
        action="store_true",
        help="仅返回最终答案（mode 7 投资逻辑可选）",
    )
    p.add_argument("--start", metavar="YYYY-MM-DD", help="数据开始日期")
    p.add_argument("--end", metavar="YYYY-MM-DD", help="数据结束日期")
    return p


def _validate_args(args) -> None:
    """按 mode 做本地必填校验，避免把参数错误留到数分钟的 SSE 之后才发现。"""
    required, hint = _MODE_REQUIREMENTS.get(args.mode, ([], ""))
    missing = [f"--{name.replace('_', '-')}" for name in required if getattr(args, name) is None]
    if missing:
        print(f"[错误] mode {args.mode} 缺少必填参数 {', '.join(missing)}。{hint}", file=sys.stderr)
        sys.exit(2)
    if args.mode == 15 and len(args.picture_color) != 2:
        print("[错误] mode 15 的 --picture-color 需恰好 2 个 HEX 值（主色 辅色），不含 # 前缀", file=sys.stderr)
        sys.exit(2)


def run(args):
    _validate_args(args)
    client = AlphaPaiClient(require_config())
    stock = parse_stock(args.stock) if args.stock else None
    stock_list = [parse_stock(s) for s in args.stock_list] if args.stock_list else None
    template = 1 if args.mode in (5, 8, 9) else args.template

    # 服务端对 mode 12/13 强制要求 ifAnnual，缺省时本地补 0（文档建议显式传）
    if_annual = args.if_annual
    if args.mode in (12, 13) and if_annual is None:
        if_annual = 0

    try:
        result = stock_agent(
            client,
            question=args.question,
            agent_mode=args.mode,
            stock=stock,
            template=template,
            template_text=args.template_text or "",
            report_type=args.report_type,
            stock_report_id=args.report_id,
            stock_report_title=args.report_title,
            stock_report_period=args.report_period,
            template_concern=args.concern,
            request_select_start_time=args.start,
            request_select_end_time=args.end,
            input_industry=args.industry,
            report_date=args.report_date,
            fund_type=args.fund_type,
            if_annual=if_annual,
            stock_list=stock_list,
            picture_color=args.picture_color,
            picture_style=args.picture_style,
            source=args.source,
            language=args.language,
            only_answer=True if args.only_answer else None,
        )
    except SseApiError as e:
        print(f"[错误] Agent 接口业务错误: {e}", file=sys.stderr)
        sys.exit(1)
    print_json(result)
