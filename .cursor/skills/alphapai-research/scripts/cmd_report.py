"""股票公告列表 CLI 子命令"""

from typing import Dict

from alphapai_base import AlphaPaiClient, print_json, require_config, require_success


def stock_report(client: AlphaPaiClient, code: str) -> Dict:
    """获取某个股票的公告列表"""
    return client._post("/alpha/open-api/v1/paipai/stock/report", {"code": code})


def register_parser(sub):
    p = sub.add_parser("report", help="获取股票公告列表（供业绩点评查询公告ID）")
    p.add_argument("--code", "-c", required=True, help="股票编码，如 603380.SH")
    return p


def run(args):
    client = AlphaPaiClient(require_config())
    result = stock_report(client, code=args.code)
    require_success(result)
    print_json(result)
