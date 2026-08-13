"""健康检查 CLI 子命令"""

from alphapai_base import AlphaPaiClient, print_json, require_config, require_success


def register_parser(sub):
    p = sub.add_parser("hello", help="健康检查（验证API连通性与鉴权）")
    return p


def run(args):
    config = require_config()
    client = AlphaPaiClient(config)
    result = client.health_check()
    require_success(result)
    print_json(result)
