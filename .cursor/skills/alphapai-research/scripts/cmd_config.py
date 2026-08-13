"""配置管理 CLI 子命令"""

import sys

from alphapai_base import DEFAULT_CONFIG_PATH, load_config, mask_key, save_config


def register_parser(sub):
    p = sub.add_parser("config", help="查看或设置API配置")
    p.add_argument("--show", action="store_true", help="显示当前配置")
    p.add_argument("--set-key", metavar="KEY", help="设置api_key")
    p.add_argument(
        "--set-url",
        metavar="URL",
        help="设置base_url（默认 https://open-api.rabyte.cn）",
    )
    return p


def run(args):
    config_path = DEFAULT_CONFIG_PATH
    if args.set_key or args.set_url:
        config = load_config(config_path) or {}
        if args.set_key:
            config["api_key"] = args.set_key
        if args.set_url:
            config["base_url"] = args.set_url
        config.setdefault("base_url", "https://open-api.rabyte.cn")
        if not config.get("api_key"):
            print("[错误] 未设置 api_key，请同时使用 --set-key 指定", file=sys.stderr)
            sys.exit(1)
        save_config(config["api_key"], config["base_url"], config_path)
        print(f"配置已保存: api_key={mask_key(config['api_key'])}  base_url={config['base_url']}")
        print(f"路径: {config_path}")
    elif args.show:
        config = load_config(config_path)
        if not config:
            print(
                "未找到配置，请先运行: python alphapai_client.py config --set-key YOUR_KEY"
            )
            sys.exit(1)
        print(f"api_key : {mask_key(config['api_key'])}")
        print(f"base_url: {config['base_url']}")
        print(f"路径    : {config_path}")
    else:
        print(
            "用法: python alphapai_client.py config --show | --set-key KEY [--set-url URL]"
        )
