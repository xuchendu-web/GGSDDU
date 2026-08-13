"""投研知识检索 CLI 子命令"""

from typing import Dict, List, Optional

from alphapai_base import AlphaPaiClient, print_json, require_config, require_success


def recall_data(
    client: AlphaPaiClient,
    query: str,
    is_cut_off: bool = True,
    recall_type: Optional[List[str]] = None,
    start_time: Optional[str] = None,
    end_time: Optional[str] = None,
) -> Dict:
    """获取问题召回数据"""
    payload = {"query": query, "isCutOff": is_cut_off}
    payload["recallType"] = recall_type if recall_type else []
    if start_time:
        payload["startTime"] = start_time
    if end_time:
        payload["endTime"] = end_time
    return client._post("/alpha/open-api/v1/paipai/recall-data", payload)


def register_parser(sub):
    p = sub.add_parser("recall", help="获取问题召回的底层数据")
    p.add_argument("--query", "-q", required=True, help="查询问题")
    p.add_argument(
        "--type",
        "-t",
        metavar="TYPES",
        help="数据类型，逗号分隔，如 comment,qa,report（不传则全类型）",
    )
    p.add_argument(
        "--no-cutoff",
        action="store_true",
        help="返回截断前完整内容（默认截断，与送入大模型的数据一致）",
    )
    p.add_argument("--start", metavar="YYYY-MM-DD", help="数据筛选开始日期")
    p.add_argument("--end", metavar="YYYY-MM-DD", help="数据筛选结束日期")
    return p


def run(args):
    client = AlphaPaiClient(require_config())
    recall_type = [t.strip() for t in args.type.split(",")] if args.type else []
    result = recall_data(
        client,
        query=args.query,
        is_cut_off=not args.no_cutoff,
        recall_type=recall_type,
        start_time=args.start,
        end_time=args.end,
    )
    require_success(result)
    print_json(result)
