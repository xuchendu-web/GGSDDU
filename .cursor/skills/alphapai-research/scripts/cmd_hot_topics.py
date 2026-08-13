"""机构热议 CLI 子命令"""

import argparse
from typing import Dict, List, Optional

from alphapai_base import AlphaPaiClient, print_json, require_config, require_success

HOT_PREFIX = "/alpha/open-api/v1/hot/stocks"


def board_list(
    client: AlphaPaiClient,
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
    inst_type_tag: Optional[List[str]] = None,
    stock_combo_symbol_tag: Optional[List[str]] = None,
    stock_name_tag: Optional[List[str]] = None,
    limit: int = 10,
) -> Dict:
    """查询机构热议股票榜单"""
    payload: Dict = {"limit": limit}
    if start_date:
        payload["startDate"] = start_date
    if end_date:
        payload["endDate"] = end_date
    if inst_type_tag:
        payload["instTypeTag"] = inst_type_tag
    if stock_combo_symbol_tag:
        payload["stockComboSymbolTag"] = stock_combo_symbol_tag
    if stock_name_tag:
        payload["stockNameTag"] = stock_name_tag
    return client._post(f"{HOT_PREFIX}/board/list", payload)


def register_parser(sub: argparse._SubParsersAction) -> argparse.ArgumentParser:
    p = sub.add_parser("hot-topics", help="机构热议：查询机构热议股票榜单")
    hot_sub = p.add_subparsers(dest="hot_action", required=True)

    p_board = hot_sub.add_parser("board-list", help="查询机构热议股票榜单")
    p_board.add_argument("--start", metavar="YYYY-MM-DD", help="开始日期")
    p_board.add_argument("--end", metavar="YYYY-MM-DD", help="结束日期")
    p_board.add_argument("--inst-type", nargs="+",
                         choices=["公募", "私募", "保险"],
                         help="机构类型过滤，如: 公募 私募 保险；不传默认全部")
    p_board.add_argument("--stock-symbol", nargs="+", help="股票代码过滤，如 300308.SZ")
    p_board.add_argument("--stock-name", nargs="+", help="股票名称过滤")
    p_board.add_argument("--limit", type=int, default=10,
                         help="每个交易日每个机构类型返回数量，默认 10，最大 50")

    return p


def run(args):
    client = AlphaPaiClient(require_config())
    action = args.hot_action

    if action == "board-list":
        result = board_list(
            client,
            start_date=args.start,
            end_date=args.end,
            inst_type_tag=args.inst_type,
            stock_combo_symbol_tag=args.stock_symbol,
            stock_name_tag=args.stock_name,
            limit=args.limit,
        )
    else:
        print(f"[错误] 未知的 hot-topics 子命令: {action}")
        return

    require_success(result)
    print_json(result)
