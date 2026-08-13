"""预约会议 CLI 子命令"""

import argparse
from typing import Dict, List, Optional

from alphapai_base import AlphaPaiClient, print_json, require_config, require_success

BOOKING_PREFIX = "/alpha/open-api/v1/reservation/meeting"


def reservation_list(
    client: AlphaPaiClient,
    page: int = 1,
    page_size: int = 20,
    scope: str = "my",
    status: Optional[List[str]] = None,
    keyword: Optional[str] = None,
    meeting_time_from: Optional[str] = None,
    meeting_time_to: Optional[str] = None,
    reserved_time_from: Optional[str] = None,
    reserved_time_to: Optional[str] = None,
    industry_tag: Optional[List[str]] = None,
    organizations: Optional[List[str]] = None,
    market_tag: Optional[List[str]] = None,
) -> Dict:
    """查看预约记录列表"""
    payload: Dict = {"scope": scope, "page": page, "pageSize": page_size}
    if status:
        payload["status"] = status
    if keyword:
        payload["keyword"] = keyword
    if meeting_time_from:
        payload["meetingTimeFrom"] = meeting_time_from
    if meeting_time_to:
        payload["meetingTimeTo"] = meeting_time_to
    if reserved_time_from:
        payload["reservedTimeFrom"] = reserved_time_from
    if reserved_time_to:
        payload["reservedTimeTo"] = reserved_time_to
    if industry_tag:
        payload["industryTag"] = industry_tag
    if organizations:
        payload["organizations"] = organizations
    if market_tag:
        payload["marketTag"] = market_tag
    return client._post(f"{BOOKING_PREFIX}/list", payload)


def reservation_delete(client: AlphaPaiClient, msg_id: str, scope: str = "my") -> Dict:
    """删除预约记录"""
    payload: Dict = {"msgId": msg_id, "scope": scope}
    return client._post(f"{BOOKING_PREFIX}/delete", payload)


def generated_list(
    client: AlphaPaiClient,
    page: int = 1,
    page_size: int = 20,
    scope: str = "my",
    keyword: Optional[str] = None,
    stock_tag: Optional[List[str]] = None,
    content_type_tag: Optional[List[str]] = None,
    has_asr_note: Optional[bool] = None,
    has_ai_note: Optional[bool] = None,
) -> Dict:
    """查看已生成会议列表"""
    payload: Dict = {"scope": scope, "page": page, "pageSize": page_size}
    if keyword:
        payload["keyword"] = keyword
    if stock_tag:
        payload["stockTag"] = stock_tag
    if content_type_tag:
        payload["contentTypeTag"] = content_type_tag
    if has_asr_note is not None:
        payload["hasAsrNote"] = has_asr_note
    if has_ai_note is not None:
        payload["hasAiNote"] = has_ai_note
    return client._post(f"{BOOKING_PREFIX}/generated/list", payload)


def meeting_detail(
    client: AlphaPaiClient,
    meeting_id: str,
    include_notes: Optional[bool] = None,
    note_preview_length: Optional[int] = None,
) -> Dict:
    """查看会议详情"""
    payload: Dict = {"meetingId": meeting_id}
    if include_notes is not None:
        payload["includeNotes"] = include_notes
    if note_preview_length is not None:
        payload["notePreviewLength"] = note_preview_length
    return client._post(f"{BOOKING_PREFIX}/detail", payload)


def summary_detail(
    client: AlphaPaiClient,
    meeting_id: str,
    note_type: Optional[str] = None,
    format: str = "markdown",
    include_segments: Optional[bool] = None,
) -> Dict:
    """查看会议纪要详情"""
    payload: Dict = {"meetingId": meeting_id, "format": format}
    if note_type:
        payload["noteType"] = note_type
    if include_segments is not None:
        payload["includeSegments"] = include_segments
    return client._post(f"{BOOKING_PREFIX}/summary/detail", payload)


def register_parser(sub: argparse._SubParsersAction) -> argparse.ArgumentParser:
    p = sub.add_parser("meeting-booking", help="预约会议：预约记录/删除/已生成会议/会议详情/纪要详情")
    mb_sub = p.add_subparsers(dest="mb_action", required=True)

    # list
    p_list = mb_sub.add_parser("list", help="查看预约记录列表")
    p_list.add_argument("--page", type=int, default=1, help="页码，默认 1")
    p_list.add_argument("--page-size", type=int, default=20, help="每页条数，默认 20")
    p_list.add_argument("--scope", default="my", help="范围，默认 my")
    p_list.add_argument("--status", nargs="+", choices=["success", "fail"],
                        help="状态: success/fail")
    p_list.add_argument("--keyword", "-k", help="标题关键词")
    p_list.add_argument("--meeting-time-from", metavar="YYYY-MM-DD", help="会议时间起")
    p_list.add_argument("--meeting-time-to", metavar="YYYY-MM-DD", help="会议时间止")
    p_list.add_argument("--reserved-time-from", metavar="YYYY-MM-DD", help="预约时间起")
    p_list.add_argument("--reserved-time-to", metavar="YYYY-MM-DD", help="预约时间止")
    p_list.add_argument("--industry-tag", nargs="+", help="行业标签")
    p_list.add_argument("--organizations", nargs="+", help="机构 code")
    p_list.add_argument("--market-tag", nargs="+", help="市场标签 A/HK/US")

    # delete
    p_del = mb_sub.add_parser("delete", help="删除预约记录")
    p_del.add_argument("--msg-id", required=True, help="消息 id（必填）")
    p_del.add_argument("--scope", default="my", help="范围，默认 my")

    # generated-list
    p_gen = mb_sub.add_parser("generated-list", help="查看已生成会议列表")
    p_gen.add_argument("--page", type=int, default=1, help="页码，默认 1")
    p_gen.add_argument("--page-size", type=int, default=20, help="每页条数，默认 20")
    p_gen.add_argument("--scope", default="my", help="范围，默认 my")
    p_gen.add_argument("--keyword", "-k", help="标题关键词")
    p_gen.add_argument("--stock-tag", nargs="+", help="个股过滤")
    p_gen.add_argument("--content-type-tag", nargs="+", help="会议内容类型（传中文标签，如 专家交流 公司交流）")
    p_gen.add_argument("--has-asr-note", choices=["true", "false"], help="是否有 ASR 纪要")
    p_gen.add_argument("--has-ai-note", choices=["true", "false"], help="是否有 AI 纪要")

    # detail
    p_det = mb_sub.add_parser("detail", help="查看会议详情")
    p_det.add_argument("--meeting-id", required=True, help="会议 id（roadshowId）")
    p_det.add_argument("--include-notes", choices=["true", "false"], default="true",
                       help="是否包含纪要（默认 true；服务端缺省等同于 false，故 CLI 显式传 true）")
    p_det.add_argument(
        "--note-preview-length",
        type=int,
        default=200,
        help="纪要预览长度，默认 200；include-notes=true 时服务端要求携带",
    )

    # summary-detail
    p_sum = mb_sub.add_parser("summary-detail", help="查看会议纪要详情")
    p_sum.add_argument("--meeting-id", required=True, help="会议 id")
    p_sum.add_argument("--note-type", required=True, choices=["asr_note", "ai_note"],
                       help="纪要类型: asr_note=原始转写 ai_note=AI 纪要")
    p_sum.add_argument("--format", default="markdown", choices=["markdown"], help="格式，仅支持 markdown")
    p_sum.add_argument("--include-segments", choices=["true", "false"],
                       help="是否返回 ASR 分段")

    return p


def _str2bool(v: Optional[str]) -> Optional[bool]:
    if v is None:
        return None
    return v.lower() == "true"


def run(args):
    client = AlphaPaiClient(require_config())
    action = args.mb_action

    if action == "list":
        result = reservation_list(
            client,
            page=args.page, page_size=args.page_size, scope=args.scope,
            status=args.status, keyword=args.keyword,
            meeting_time_from=args.meeting_time_from, meeting_time_to=args.meeting_time_to,
            reserved_time_from=args.reserved_time_from, reserved_time_to=args.reserved_time_to,
            industry_tag=args.industry_tag, organizations=args.organizations,
            market_tag=args.market_tag,
        )
    elif action == "delete":
        result = reservation_delete(client, msg_id=args.msg_id, scope=args.scope)
    elif action == "generated-list":
        result = generated_list(
            client,
            page=args.page, page_size=args.page_size, scope=args.scope,
            keyword=args.keyword, stock_tag=args.stock_tag,
            content_type_tag=args.content_type_tag,
            has_asr_note=_str2bool(args.has_asr_note),
            has_ai_note=_str2bool(args.has_ai_note),
        )
    elif action == "detail":
        result = meeting_detail(
            client,
            meeting_id=args.meeting_id,
            include_notes=_str2bool(args.include_notes),
            note_preview_length=args.note_preview_length,
        )
    elif action == "summary-detail":
        result = summary_detail(
            client,
            meeting_id=args.meeting_id,
            note_type=args.note_type,
            format=args.format,
            include_segments=_str2bool(args.include_segments),
        )
    else:
        print(f"[错误] 未知的 meeting-booking 子命令: {action}")
        return

    require_success(result)
    print_json(result)
