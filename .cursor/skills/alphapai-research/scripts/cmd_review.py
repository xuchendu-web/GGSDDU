"""点评（券商点评）CLI 子命令"""

import argparse
from typing import Dict, List, Optional

from alphapai_base import AlphaPaiClient, print_json, require_config

REVIEW_PREFIX = "/alpha/open-api/v1/comments"


def comment_list(
    client: AlphaPaiClient,
    page: int = 1,
    page_size: int = 20,
    comment_scope: Optional[str] = None,
    keyword: Optional[str] = None,
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
    industry_code: Optional[List[str]] = None,
    industry_name: Optional[List[str]] = None,
    subject_code: Optional[List[str]] = None,
    subject_name: Optional[List[str]] = None,
    stock_comb_symbol: Optional[List[str]] = None,
    stock_name: Optional[List[str]] = None,
) -> Dict:
    """搜索点评列表"""
    payload: Dict = {"page": page, "pageSize": page_size}
    if comment_scope:
        payload["commentScope"] = comment_scope
    if keyword:
        payload["keyword"] = keyword
    if start_date:
        payload["startDate"] = start_date
    if end_date:
        payload["endDate"] = end_date
    if industry_code:
        payload["industryCode"] = industry_code
    if industry_name:
        payload["industryName"] = industry_name
    if subject_code:
        payload["subjectCode"] = subject_code
    if subject_name:
        payload["subjectName"] = subject_name
    if stock_comb_symbol:
        payload["stockCombSymbol"] = stock_comb_symbol
    if stock_name:
        payload["stockName"] = stock_name
    return client._post(f"{REVIEW_PREFIX}/list", payload)


def event_list(
    client: AlphaPaiClient,
    page: int = 1,
    page_size: int = 20,
    market_scope: Optional[str] = None,
    event_type: Optional[List[str]] = None,
    stock_comb_symbol: Optional[List[str]] = None,
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
) -> Dict:
    """业绩点评专属列表"""
    payload: Dict = {"page": page, "pageSize": page_size}
    if market_scope:
        payload["marketScope"] = market_scope
    if event_type:
        payload["eventType"] = event_type
    if stock_comb_symbol:
        payload["stockCombSymbol"] = stock_comb_symbol
    if start_date:
        payload["startDate"] = start_date
    if end_date:
        payload["endDate"] = end_date
    return client._post(f"{REVIEW_PREFIX}/event/list", payload)


def comment_detail(
    client: AlphaPaiClient,
    comment_id: List[str],
) -> Dict:
    """查看点评详情（支持一个或多个 commentId）"""
    payload: Dict = {"commentId": comment_id}
    return client._post(f"{REVIEW_PREFIX}/detail", payload)


def register_parser(sub: argparse._SubParsersAction) -> argparse.ArgumentParser:
    p = sub.add_parser("review", help="点评：搜索点评列表、业绩点评专属列表")
    rv_sub = p.add_subparsers(dest="rv_action", required=True)

    # comment-list
    p_clist = rv_sub.add_parser("list", help="搜索点评列表")
    p_clist.add_argument("--page", type=int, default=1, help="页码，默认 1")
    p_clist.add_argument("--page-size", type=int, default=20, help="每页条数，默认 20")
    p_clist.add_argument("--scope", choices=["all", "valuable", "regular"],
                         help="点评范围: all=全部 valuable=有价值 regular=常规")
    p_clist.add_argument("--keyword", "-k", help="匹配标题/正文关键词")
    p_clist.add_argument("--start", metavar="YYYY-MM-DD", help="开始日期")
    p_clist.add_argument("--end", metavar="YYYY-MM-DD", help="结束日期")
    p_clist.add_argument("--industry-code", nargs="+", help="行业编码过滤")
    p_clist.add_argument("--industry-name", nargs="+", help="行业名称过滤")
    p_clist.add_argument("--subject-code", nargs="+", help="题材编码过滤")
    p_clist.add_argument("--subject-name", nargs="+", help="题材名称过滤")
    p_clist.add_argument("--stock-symbol", nargs="+", help="股票代码过滤，如 600519.SH")
    p_clist.add_argument("--stock-name", nargs="+", help="股票名称过滤")

    # event-list
    p_elist = rv_sub.add_parser("event-list", help="业绩点评专属列表")
    p_elist.add_argument("--page", type=int, default=1, help="页码，默认 1")
    p_elist.add_argument("--page-size", type=int, default=20, help="每页条数，默认 20")
    p_elist.add_argument("--market-scope", choices=["ah", "a", "hk"],
                         help="市场范围: ah=A+H a=A股 hk=港股")
    p_elist.add_argument("--event-type", nargs="+",
                         choices=["performance_forecast", "performance_flash", "performance_report"],
                         help="事件类型: performance_forecast=业绩预告 performance_flash=业绩快报 performance_report=业绩报告")
    p_elist.add_argument("--stock-symbol", nargs="+", help="股票代码过滤")
    p_elist.add_argument("--start", metavar="YYYY-MM-DD", help="开始日期")
    p_elist.add_argument("--end", metavar="YYYY-MM-DD", help="结束日期")

    # detail
    p_detail = rv_sub.add_parser("detail", help="查看点评详情")
    p_detail.add_argument("--comment-id", nargs="+", required=True, help="点评 ID（可传多个）")

    return p


def run(args):
    client = AlphaPaiClient(require_config())
    action = args.rv_action

    if action == "list":
        result = comment_list(
            client,
            page=args.page,
            page_size=args.page_size,
            comment_scope=args.scope,
            keyword=args.keyword,
            start_date=args.start,
            end_date=args.end,
            industry_code=args.industry_code,
            industry_name=args.industry_name,
            subject_code=args.subject_code,
            subject_name=args.subject_name,
            stock_comb_symbol=args.stock_symbol,
            stock_name=args.stock_name,
        )
    elif action == "event-list":
        result = event_list(
            client,
            page=args.page,
            page_size=args.page_size,
            market_scope=args.market_scope,
            event_type=args.event_type,
            stock_comb_symbol=args.stock_symbol,
            start_date=args.start,
            end_date=args.end,
        )
    elif action == "detail":
        result = comment_detail(
            client,
            comment_id=args.comment_id,
        )
    else:
        print(f"[错误] 未知的 review 子命令: {action}")
        return

    print_json(result)
