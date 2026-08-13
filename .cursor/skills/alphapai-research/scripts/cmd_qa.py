"""投研知识问答 CLI 子命令"""

import sys
from typing import Dict, List, Optional

from alphapai_base import (
    AlphaPaiClient,
    SseApiError,
    print_json,
    require_config,
)


def qa_text(
    client: AlphaPaiClient,
    question: str,
    context: Optional[List[str]] = None,
    mode: str = "Flash",
    is_auto_route: bool = True,
    is_web_search: bool = False,
    is_deep_reasoning: bool = False,
    start_time: Optional[str] = None,
    end_time: Optional[str] = None,
    question_id: Optional[str] = None,
) -> Dict:
    """投研知识问答接口（SSE 流式）。

    线上服务无论 isStream 取值均返回 SSE 流，因此本接口固定按流式处理，
    聚合后返回 {"code","message","questionId","answer","references"}。
    """
    payload = {
        "question": question,
        "mode": mode,
        "isStream": True,
        "isAutoRoute": is_auto_route,
    }
    if context:
        payload["context"] = context
    if is_web_search:
        payload["isWebSearch"] = True
    if is_deep_reasoning:
        payload["isDeepReasoning"] = True
    if start_time:
        payload["requestSelectStartTime"] = start_time
    if end_time:
        payload["requestSelectEndTime"] = end_time
    if question_id:
        payload["questionId"] = question_id

    return client.parse_sse(
        client._post("/alpha/open-api/v1/paipai/qa-text", payload, stream=True)
    )


def register_parser(sub):
    p = sub.add_parser("qa", help="投研知识问答")
    p.add_argument("--question", "-q", required=True, help="问题内容")
    p.add_argument(
        "--mode",
        default="Flash",
        choices=["Flash", "Think"],
        help="问答模式: Flash=简单搜索问答，一问一搜一答（默认）; Think=Wide Search，一问多搜一答",
    )
    p.add_argument(
        "--context",
        "-c",
        nargs="+",
        metavar="MSG",
        help="多轮对话上下文，按顺序传入历史消息列表",
    )
    p.add_argument("--web-search", action="store_true", help="开启联网搜索")
    p.add_argument("--deep-reasoning", action="store_true", help="开启深度推理")
    p.add_argument(
        "--auto-route",
        dest="auto_route",
        action="store_true",
        default=True,
        help="开启自动路由（默认开启）",
    )
    p.add_argument(
        "--no-auto-route",
        dest="auto_route",
        action="store_false",
        help="关闭自动路由",
    )
    p.add_argument("--question-id", help="并发请求标识（相同 id 的流式事件可关联）")
    p.add_argument("--start", metavar="YYYY-MM-DD", help="数据筛选开始日期")
    p.add_argument("--end", metavar="YYYY-MM-DD", help="数据筛选结束日期")
    return p


def run(args):
    client = AlphaPaiClient(require_config())
    try:
        result = qa_text(
            client,
            question=args.question,
            context=args.context or None,
            mode=args.mode,
            is_auto_route=args.auto_route,
            is_web_search=args.web_search,
            is_deep_reasoning=args.deep_reasoning,
            start_time=args.start,
            end_time=args.end,
            question_id=args.question_id,
        )
    except SseApiError as e:
        print(f"[错误] 问答接口业务错误: {e}", file=sys.stderr)
        sys.exit(1)
    print_json(result)
