"""会议纪要 CLI 子命令"""

import argparse
from typing import Dict, List, Optional

from alphapai_base import AlphaPaiClient, print_json, require_config, require_success

MINUTES_PREFIX = "/alpha/open-api/v1/summary"


def minutes_list(
    client: AlphaPaiClient,
    meeting_market_type: str,
    page_num: int = 1,
    page_size: int = 20,
    keyword: Optional[str] = None,
    begin_time: Optional[str] = None,
    end_time: Optional[str] = None,
    meeting_tag: Optional[List[str]] = None,
    meeting_content_type: Optional[List[str]] = None,
    industry_code: Optional[List[str]] = None,
    stock_comb_symbol: Optional[List[str]] = None,
    institution_code: Optional[List[str]] = None,
    duration_category: Optional[str] = None,
) -> Dict:
    """搜索会议纪要列表"""
    payload: Dict = {
        "meetingMarketType": meeting_market_type,
        "pageNum": page_num,
        "pageSize": page_size,
    }
    if keyword:
        payload["keyword"] = keyword
    if begin_time:
        payload["beginTime"] = begin_time
    if end_time:
        payload["endTime"] = end_time
    if meeting_tag:
        payload["meetingTag"] = meeting_tag
    if meeting_content_type:
        payload["meetingContentType"] = meeting_content_type
    if industry_code:
        payload["industryCode"] = industry_code
    if stock_comb_symbol:
        payload["stockCombSymbol"] = stock_comb_symbol
    if institution_code:
        payload["institutionCode"] = institution_code
    if duration_category:
        payload["durationCategory"] = duration_category
    return client._post(f"{MINUTES_PREFIX}/list", payload)


def minutes_detail(
    client: AlphaPaiClient,
    roadshow_id: str,
    note_type: str,
) -> Dict:
    """查看纪要详情"""
    payload: Dict = {"roadshowId": roadshow_id, "noteType": note_type}
    return client._post(f"{MINUTES_PREFIX}/detail", payload)


def register_parser(sub: argparse._SubParsersAction) -> argparse.ArgumentParser:
    p = sub.add_parser("meeting-minutes", help="会议纪要：搜索列表、查看纪要详情")
    mm_sub = p.add_subparsers(dest="mm_action", required=True)

    # list
    p_list = mm_sub.add_parser("list", help="搜索会议纪要列表")
    p_list.add_argument("--market-type", required=True,
                        choices=["A", "HK", "US"],
                        help="会议市场类型: A=A股 HK=港股 US=美股（必填）")
    p_list.add_argument("--page-num", "--pn", type=int, default=1, help="页码，默认 1")
    p_list.add_argument("--page-size", "--ps", type=int, default=20, help="每页条数，默认 20，最大 100")
    p_list.add_argument("--keyword", "-k", help="搜索关键词（标题/摘要/正文）")
    p_list.add_argument("--begin-time", metavar="YYYY-MM-DD HH:MM:SS",
                        help="会议时间起点")
    p_list.add_argument("--end-time", metavar="YYYY-MM-DD HH:MM:SS",
                        help="会议时间终点")
    p_list.add_argument("--meeting-tag", nargs="+",
                        choices=["executive_attended", "new_fortune", "china_concept"],
                        help="会议标签: executive_attended=高管出席 new_fortune=新财富 china_concept=中概股")
    p_list.add_argument("--content-type", nargs="+",
                        choices=["company_communication", "performance_meeting",
                                 "expert_communication", "company_analysis",
                                 "industry_analysis", "conference", "fund_manager_view"],
                        help="会议内容类型")
    p_list.add_argument("--industry-code", nargs="+", help="行业 code 过滤")
    p_list.add_argument("--stock-symbol", nargs="+", help="股票代码过滤，如 600519.SH")
    p_list.add_argument("--institution-code", nargs="+", help="机构 code 过滤")
    p_list.add_argument("--duration", choices=["lt_30m", "between_30m_60m", "gt_60m"],
                        help="会议时长: lt_30m=30分钟内 between_30m_60m=30-60分钟 gt_60m=60分钟以上")

    # detail
    p_det = mm_sub.add_parser("detail", help="查看纪要详情")
    p_det.add_argument("--roadshow-id", required=True, help="会议 id（roadshowId）")
    p_det.add_argument("--note-type", required=True,
                       choices=["ai_note", "asr_note"],
                       help="纪要类型: ai_note=AI结构化纪要 asr_note=ASR原始转写")

    return p


def run(args):
    client = AlphaPaiClient(require_config())
    action = args.mm_action

    if action == "list":
        result = minutes_list(
            client,
            meeting_market_type=args.market_type,
            page_num=args.page_num,
            page_size=args.page_size,
            keyword=args.keyword,
            begin_time=args.begin_time,
            end_time=args.end_time,
            meeting_tag=args.meeting_tag,
            meeting_content_type=args.content_type,
            industry_code=args.industry_code,
            stock_comb_symbol=args.stock_symbol,
            institution_code=args.institution_code,
            duration_category=args.duration,
        )
    elif action == "detail":
        result = minutes_detail(
            client,
            roadshow_id=args.roadshow_id,
            note_type=args.note_type,
        )
    else:
        print(f"[错误] 未知的 meeting-minutes 子命令: {action}")
        return

    require_success(result)
    print_json(result)
