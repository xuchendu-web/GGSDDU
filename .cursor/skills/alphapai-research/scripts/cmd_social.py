"""社媒（公众号订阅）CLI 子命令"""

import argparse
from typing import Dict, List, Optional

from alphapai_base import AlphaPaiClient, print_json, require_config, require_success

SOCIAL_PREFIX = "/alpha/open-api/v1/social/media"


def account_list(client: AlphaPaiClient) -> Dict:
    return client._get(f"{SOCIAL_PREFIX}/account/list")


def subscribe(client: AlphaPaiClient, ids: List[str]) -> Dict:
    return client._post(f"{SOCIAL_PREFIX}/subscribe", ids)


def unsubscribe(client: AlphaPaiClient, ids: List[str]) -> Dict:
    return client._post(f"{SOCIAL_PREFIX}/unsubscribe", ids)


def subscribe_list(client: AlphaPaiClient, is_star: Optional[bool] = None) -> Dict:
    params = None
    if is_star is not None:
        params = {"isStar": is_star}
    return client._get(f"{SOCIAL_PREFIX}/subscribe/list", params=params)


def article_list(
    client: AlphaPaiClient,
    page_num: int,
    page_size: int,
    word: Optional[str] = None,
    industry: Optional[List[str]] = None,
    stock: Optional[List[str]] = None,
    institution: Optional[List[str]] = None,
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
    source_name: Optional[str] = None,
    psn_write: Optional[int] = None,
    exclude_content: bool = False,
) -> Dict:
    payload: Dict = {
        "pageNum": page_num,
        "pageSize": page_size,
        "excludeContent": exclude_content,
    }
    if word:
        payload["word"] = word
    if industry:
        payload["industry"] = industry
    if stock:
        payload["stock"] = stock
    if institution:
        payload["institution"] = institution
    if start_date:
        payload["startDate"] = start_date
    if end_date:
        payload["endDate"] = end_date
    if source_name:
        payload["sourceName"] = source_name
    if psn_write is not None:
        payload["psnWrite"] = psn_write
    return client._post(f"{SOCIAL_PREFIX}/article/list", payload)


def account_search(
    client: AlphaPaiClient,
    word: str,
    page_num: int = 1,
    page_size: int = 20,
) -> Dict:
    return client._get(
        f"{SOCIAL_PREFIX}/account/search",
        params={"word": word, "pageNum": page_num, "pageSize": page_size},
    )


def account_detail(client: AlphaPaiClient, account_id: str, supplier_id: Optional[str] = None) -> Dict:
    # 列表/搜索接口返回的 supplierId 普遍为 null；缺省传字符串 "null"，
    # 当前服务端会选择默认供应商并返回详情。
    params = {"id": account_id, "supplierId": supplier_id if supplier_id is not None else "null"}
    return client._get(f"{SOCIAL_PREFIX}/account/detail", params=params)


def article_detail(client: AlphaPaiClient, article_id: str, supplier_id: Optional[str] = None) -> Dict:
    # 与 account-detail 一致：列表结果通常不含 supplierId，缺省传字符串 "null" 取默认供应商
    return client._get(
        f"{SOCIAL_PREFIX}/article/detail",
        params={"id": article_id, "supplierId": supplier_id if supplier_id is not None else "null"},
    )


def register_parser(sub: argparse._SubParsersAction) -> argparse.ArgumentParser:
    p = sub.add_parser(
        "social", help="社媒订阅：公众号查询/详情/订阅与文章检索/详情"
    )
    social_sub = p.add_subparsers(dest="social_action", required=True)

    social_sub.add_parser("account-list", help="查询可订阅公众号列表")

    p_subscribe = social_sub.add_parser("subscribe", help="按 id 批量订阅公众号")
    p_subscribe.add_argument("--ids", nargs="+", required=True, help="公众号 id 列表")

    p_unsub = social_sub.add_parser("unsubscribe", help="按 id 批量取消订阅公众号")
    p_unsub.add_argument("--ids", nargs="+", required=True, help="公众号 id 列表")

    p_sub_list = social_sub.add_parser("subscribe-list", help="查询已订阅公众号列表")
    p_sub_list.add_argument("--star", action="store_true", help="仅查询星标公众号")

    p_articles = social_sub.add_parser("article-list", help="查询社媒文章主列表")
    p_articles.add_argument("--page-num", "--pn", type=int, default=1, help="页码，默认 1")
    p_articles.add_argument("--page-size", "--ps", type=int, default=10, help="每页数量，默认 10，最大 100")
    p_articles.add_argument("--word", "-w", help="搜索词")
    p_articles.add_argument("--industry", nargs="+", help="行业编码列表")
    p_articles.add_argument("--stock", nargs="+", help="股票代码列表，如 600519.SH")
    p_articles.add_argument("--institution", nargs="+", help="机构编码列表")
    p_articles.add_argument("--start", metavar="YYYY-MM-DD", help="开始日期")
    p_articles.add_argument("--end", metavar="YYYY-MM-DD", help="结束日期")
    p_articles.add_argument("--source-name", help="来源名称")
    p_articles.add_argument(
        "--psn-write",
        type=int,
        choices=[1, 2, 3],
        help="业务类型: 1=券商公众号 2=产业研究 3=公司官方",
    )
    p_articles.add_argument("--exclude-content", action="store_true", help="排除 content 字段（性能优化）")

    p_search = social_sub.add_parser("account-search", help="搜索公众号账号")
    p_search.add_argument("--word", "-w", required=True, help="搜索词")
    p_search.add_argument("--page-num", "--pn", type=int, default=1, help="页码，默认 1")
    p_search.add_argument("--page-size", "--ps", type=int, default=20, help="每页数量，默认 20")

    p_detail = social_sub.add_parser("account-detail", help="查询公众号详情")
    p_detail.add_argument("--id", required=True, help="公众号 id")
    p_detail.add_argument("--supplier-id", default=None, help="供应商 id（可选，默认传 \"null\"）")

    p_art_detail = social_sub.add_parser("article-detail", help="查询公众号文章详情")
    p_art_detail.add_argument("--id", required=True, help="文章 id")
    p_art_detail.add_argument("--supplier-id", default=None,
                              help="文章供应商 id（可选，默认传 \"null\"；列表结果不含该字段时无需指定）")

    return p


def run(args):
    client = AlphaPaiClient(require_config())
    action = args.social_action

    if action == "account-list":
        result = account_list(client)
    elif action == "subscribe":
        result = subscribe(client, args.ids)
    elif action == "unsubscribe":
        result = unsubscribe(client, args.ids)
    elif action == "subscribe-list":
        is_star = True if args.star else None
        result = subscribe_list(client, is_star=is_star)
    elif action == "article-list":
        result = article_list(
            client,
            page_num=args.page_num,
            page_size=args.page_size,
            word=args.word,
            industry=args.industry,
            stock=args.stock,
            institution=args.institution,
            start_date=args.start,
            end_date=args.end,
            source_name=args.source_name,
            psn_write=args.psn_write,
            exclude_content=args.exclude_content,
        )
    elif action == "account-search":
        result = account_search(
            client,
            word=args.word,
            page_num=args.page_num,
            page_size=args.page_size,
        )
    elif action == "account-detail":
        result = account_detail(
            client,
            account_id=args.id,
            supplier_id=args.supplier_id,
        )
    elif action == "article-detail":
        result = article_detail(
            client,
            article_id=args.id,
            supplier_id=args.supplier_id,
        )
    else:
        print(f"[错误] 未知的 social 子命令: {action}")
        return

    require_success(result)
    print_json(result)
