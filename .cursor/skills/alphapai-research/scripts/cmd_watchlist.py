"""自选股 CLI 子命令（新版 Open API，共 8 个接口 + 旧版列表）

新版接口前缀 /alpha/open-api/v1/stock/follow，支持批量关注/取关、
分组管理、是否自选、关注数量。旧版 /sync/auth/stock-follow/list 保留为
legacy-list 子命令。
"""

import argparse
from typing import Dict, List, Optional

from alphapai_base import AlphaPaiClient, print_json, require_config, require_success

WATCHLIST_PREFIX = "/alpha/open-api/v1/stock/follow"


def follow(client: AlphaPaiClient, stock_codes: List[str], group_code: Optional[str] = None) -> Dict:
    """批量关注个股"""
    payload: Dict = {"stockCodes": stock_codes, "groupCode": group_code or ""}
    return client._post(f"{WATCHLIST_PREFIX}/follow/multi", payload)


def unfollow(client: AlphaPaiClient, stock_codes: List[str], group_code: Optional[str] = None) -> Dict:
    """批量取消关注个股。不传 group_code 时从所有分组移除。"""
    payload: Dict = {"stockCodes": stock_codes}
    if group_code:
        payload["groupCode"] = group_code
    return client._post(f"{WATCHLIST_PREFIX}/unfollow/multi", payload)


def follow_list(client: AlphaPaiClient, group_code: Optional[str] = None, check_group: bool = False) -> Dict:
    """查询关注股票列表。check_group=True 时返回全部自选股并用 inGroup 标记是否在指定分组。

    注意：服务端将 groupCode 空串按字面分组匹配（返回空），因此未指定分组时
    不能传 groupCode 键，必须完全缺省。
    """
    payload: Dict = {"checkGroup": check_group}
    if group_code:
        payload["groupCode"] = group_code
    return client._post(f"{WATCHLIST_PREFIX}/list", payload)


def exist(client: AlphaPaiClient, stock_code: str) -> Dict:
    """查询某只股票是否已自选（按分组返回记录）"""
    return client._get(f"{WATCHLIST_PREFIX}/exist", params={"stockCode": stock_code})


def follow_num(client: AlphaPaiClient) -> Dict:
    """查询关注数量（口径为“股票×分组”关注记录数）"""
    return client._get(f"{WATCHLIST_PREFIX}/num")


def group_list(client: AlphaPaiClient) -> Dict:
    """查询自选分组列表（不含默认分组）"""
    return client._get(f"{WATCHLIST_PREFIX}/group/list")


def group_add(client: AlphaPaiClient, group_name: str) -> Dict:
    """新增自选分组（不返回新分组编码，需再查 group-list）"""
    return client._post(f"{WATCHLIST_PREFIX}/group/add", {"groupName": group_name})


def group_delete(client: AlphaPaiClient, group_codes: List[str]) -> Dict:
    """删除自选分组（连带删除组内关注；body 为裸字符串数组）"""
    return client._post(f"{WATCHLIST_PREFIX}/group/delete", group_codes)


def legacy_list(client: AlphaPaiClient) -> Dict:
    """旧版自选股列表（/sync/auth/stock-follow/list）"""
    return client._post("/alpha/open-api/v1/sync/auth/stock-follow/list", {})


def register_parser(sub):
    p = sub.add_parser("watchlist", help="自选股：关注/取关/分组/查询（新版 8 接口）")
    wl_sub = p.add_subparsers(dest="wl_action", required=True)

    p_follow = wl_sub.add_parser("follow", help="批量关注个股")
    p_follow.add_argument("--codes", nargs="+", required=True, help="股票代码，如 600519.SH 000858.SZ")
    p_follow.add_argument("--group-code", help="目标分组编码（不传进默认分组）")

    p_unfollow = wl_sub.add_parser("unfollow", help="批量取消关注个股")
    p_unfollow.add_argument("--codes", nargs="+", required=True, help="股票代码")
    p_unfollow.add_argument("--group-code", help="只移除该分组内的关注（不传则从所有分组移除）")

    p_list = wl_sub.add_parser("list", help="查询关注股票列表")
    p_list.add_argument("--group-code", help="分组编码（不传查全部）")
    p_list.add_argument("--check-group", action="store_true",
                        help="返回全部自选股并用 inGroup 标记是否在 --group-code 指定分组")

    p_exist = wl_sub.add_parser("exist", help="查询某只股票是否已自选")
    p_exist.add_argument("--stock-code", required=True, help="股票代码，如 600519.SH")

    wl_sub.add_parser("num", help="查询关注数量（股票×分组记录数）")

    wl_sub.add_parser("group-list", help="查询自选分组列表（不含默认分组）")

    p_gadd = wl_sub.add_parser("group-add", help="新增自选分组")
    p_gadd.add_argument("--name", required=True, help="分组名称")

    p_gdel = wl_sub.add_parser("group-delete", help="删除自选分组（连带删除组内关注）")
    p_gdel.add_argument("--group-codes", nargs="+", required=True, help="分组编码（可多个）")

    wl_sub.add_parser("legacy-list", help="旧版自选股列表（/sync/auth/stock-follow/list）")

    return p


def run(args):
    client = AlphaPaiClient(require_config())
    action = args.wl_action

    if action == "follow":
        result = follow(client, args.codes, args.group_code)
    elif action == "unfollow":
        result = unfollow(client, args.codes, args.group_code)
    elif action == "list":
        result = follow_list(client, args.group_code, args.check_group)
    elif action == "exist":
        result = exist(client, args.stock_code)
    elif action == "num":
        result = follow_num(client)
    elif action == "group-list":
        result = group_list(client)
    elif action == "group-add":
        result = group_add(client, args.name)
    elif action == "group-delete":
        result = group_delete(client, args.group_codes)
    elif action == "legacy-list":
        result = legacy_list(client)
    else:
        print(f"[错误] 未知的 watchlist 子命令: {action}")
        return

    require_success(result)
    print_json(result)
