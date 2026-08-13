"""蓝宝书 CLI 子命令"""

import argparse
from typing import Dict, List, Optional

from alphapai_base import AlphaPaiClient, print_json, require_config, require_success

BLUEBOOK_PREFIX = "/alpha/open-api/v1/blue/books"


def batch_list(
    client: AlphaPaiClient,
    batch_type: str,
    batch_scope: str,
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
    keyword: Optional[str] = None,
    page: int = 1,
    page_size: int = 20,
) -> Dict:
    """获取蓝宝书批次标题列表"""
    payload: Dict = {
        "batchType": batch_type,
        "batchScope": batch_scope,
        "page": page,
        "pageSize": page_size,
    }
    if start_date:
        payload["startDate"] = start_date
    if end_date:
        payload["endDate"] = end_date
    if keyword is not None:
        payload["keyword"] = keyword
    return client._post(f"{BLUEBOOK_PREFIX}/batch/list", payload)


def topic_list(
    client: AlphaPaiClient,
    batch_type: str,
    batch_scope: str,
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
    keyword: Optional[str] = None,
    stock_combo_symbol_tag: Optional[List[str]] = None,
    stock_name_tag: Optional[List[str]] = None,
    min_heat_level: Optional[int] = None,
    page: int = 1,
    page_size: int = 20,
) -> Dict:
    """搜索蓝宝书热门话题内容"""
    payload: Dict = {
        "batchType": batch_type,
        "batchScope": batch_scope,
        "page": page,
        "pageSize": page_size,
    }
    if start_date:
        payload["startDate"] = start_date
    if end_date:
        payload["endDate"] = end_date
    if keyword is not None:
        payload["keyword"] = keyword
    if stock_combo_symbol_tag:
        payload["stockComboSymbolTag"] = stock_combo_symbol_tag
    if stock_name_tag:
        payload["stockNameTag"] = stock_name_tag
    if min_heat_level is not None:
        payload["minHeatLevel"] = min_heat_level
    return client._post(f"{BLUEBOOK_PREFIX}/topic/list", payload)


def topic_detail(
    client: AlphaPaiClient,
    topic_id: int,
    batch_scope: str,
) -> Dict:
    """获取蓝宝书话题详情"""
    payload: Dict = {
        "topicId": topic_id,
        "batchScope": batch_scope,
    }
    return client._post(f"{BLUEBOOK_PREFIX}/topic/detail", payload)


def register_parser(sub: argparse._SubParsersAction) -> argparse.ArgumentParser:
    p = sub.add_parser("bluebook", help="蓝宝书：批次列表、热门话题、话题详情")
    bb_sub = p.add_subparsers(dest="bb_action", required=True)

    # batch-list
    p_batch = bb_sub.add_parser("batch-list", help="获取蓝宝书批次标题列表")
    p_batch.add_argument("--batch-type", "--bt", required=True,
                         choices=["morning", "noon", "evening", "all"],
                         help="批次类型: morning=早报 noon=午报 evening=晚报 all=全部")
    p_batch.add_argument("--batch-scope", "--bs", required=True,
                         choices=["domestic", "global", "all"],
                         help="市场范围: domestic=国内 global=全球 all=全部")
    p_batch.add_argument("--start", metavar="YYYY-MM-DD", help="开始日期")
    p_batch.add_argument("--end", metavar="YYYY-MM-DD", help="结束日期")
    p_batch.add_argument("--keyword", "-k", default="", help="关键词，默认空")
    p_batch.add_argument("--page", type=int, default=1, help="页码，默认 1")
    p_batch.add_argument("--page-size", type=int, default=20, help="每页条数，默认 20")

    # topic-list
    p_tlist = bb_sub.add_parser("topic-list", help="搜索蓝宝书热门话题")
    p_tlist.add_argument("--batch-type", "--bt", required=True,
                         choices=["morning", "noon", "evening", "all"],
                         help="批次类型")
    p_tlist.add_argument("--batch-scope", "--bs", required=True,
                         choices=["domestic", "global", "all"],
                         help="市场范围")
    p_tlist.add_argument("--start", metavar="YYYY-MM-DD", help="开始日期")
    p_tlist.add_argument("--end", metavar="YYYY-MM-DD", help="结束日期")
    p_tlist.add_argument("--keyword", "-k", help="关键词")
    p_tlist.add_argument("--stock-symbol", nargs="+", help="股票代码过滤，如 BABA.US")
    p_tlist.add_argument("--stock-name", nargs="+", help="股票名称过滤")
    p_tlist.add_argument("--min-heat", type=int, help="最低热度")
    p_tlist.add_argument("--page", type=int, default=1, help="页码，默认 1")
    p_tlist.add_argument("--page-size", type=int, default=20, help="每页条数，默认 20")

    # topic-detail
    p_tdetail = bb_sub.add_parser("topic-detail", help="获取蓝宝书话题详情")
    p_tdetail.add_argument("--topic-id", type=int, required=True, help="话题 id")
    p_tdetail.add_argument("--batch-scope", "--bs", required=True,
                           choices=["domestic", "global"],
                           help="市场范围: domestic=国内 global=全球")

    return p


def run(args):
    client = AlphaPaiClient(require_config())
    action = args.bb_action

    if action == "batch-list":
        result = batch_list(
            client,
            batch_type=args.batch_type,
            batch_scope=args.batch_scope,
            start_date=args.start,
            end_date=args.end,
            keyword=args.keyword,
            page=args.page,
            page_size=args.page_size,
        )
    elif action == "topic-list":
        result = topic_list(
            client,
            batch_type=args.batch_type,
            batch_scope=args.batch_scope,
            start_date=args.start,
            end_date=args.end,
            keyword=args.keyword,
            stock_combo_symbol_tag=args.stock_symbol,
            stock_name_tag=args.stock_name,
            min_heat_level=args.min_heat,
            page=args.page,
            page_size=args.page_size,
        )
    elif action == "topic-detail":
        result = topic_detail(
            client,
            topic_id=args.topic_id,
            batch_scope=args.batch_scope,
        )
    else:
        print(f"[错误] 未知的 bluebook 子命令: {action}")
        return

    require_success(result)
    print_json(result)
