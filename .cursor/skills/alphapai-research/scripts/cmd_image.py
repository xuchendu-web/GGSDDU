"""搜图表 CLI 子命令"""

from typing import Dict, List, Optional

from alphapai_base import AlphaPaiClient, print_json, require_config, require_success


def search_image(
    client: AlphaPaiClient,
    query_text: str,
    files_range: Optional[List[str]] = None,
    topk: int = 50,
    recall_mode: str = "both",
    use_llm_rank: bool = False,
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
) -> Dict:
    """搜图表：从研报/公告中搜索相关图片和表格"""
    payload: Dict = {
        "queryText": query_text,
        "topk": topk,
        "recallMode": recall_mode,
        "useLlmRank": use_llm_rank,
    }
    if files_range:
        payload["filesRange"] = files_range
    if start_date:
        payload["startDate"] = start_date
    if end_date:
        payload["endDate"] = end_date
    return client._post("/alpha/open-api/v1/paipai/search-image", payload)


def register_parser(sub):
    p = sub.add_parser("image", help="搜图表（从研报/公告中搜索图片和表格）")
    p.add_argument("--query", "-q", required=True, help="搜索内容")
    p.add_argument(
        "--files-range",
        nargs="+",
        metavar="CODE",
        help="来源类型代码列表，可选值: 3=内资研报 8=外资研报 6=公告 9=三方研报",
    )
    p.add_argument("--topk", type=int, default=50, help="返回数量(1-100，默认50)")
    p.add_argument(
        "--recall-mode",
        default="both",
        choices=["both", "vector_only", "es_only"],
        help="召回模式（默认both）",
    )
    p.add_argument("--llm-rank", action="store_true", help="使用LLM重排序")
    p.add_argument("--start", metavar="YYYY-MM-DD", help="开始日期")
    p.add_argument("--end", metavar="YYYY-MM-DD", help="结束日期")
    return p


def run(args):
    client = AlphaPaiClient(require_config())
    result = search_image(
        client,
        query_text=args.query,
        files_range=args.files_range,
        topk=args.topk,
        recall_mode=args.recall_mode,
        use_llm_rank=args.llm_rank,
        start_date=args.start,
        end_date=args.end,
    )
    require_success(result)
    print_json(result)
