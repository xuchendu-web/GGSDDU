"""公告 API CLI 子命令。"""

import argparse
import sys
from typing import Dict, List, Optional

from alphapai_base import (
    AlphaPaiClient,
    print_json,
    require_config,
    require_success,
    save_download_response,
)

ANN_PREFIX = "/alpha/open-api/v1/announcement"


def ann_list(
    client: AlphaPaiClient,
    page_num: int = 1,
    page_size: int = 20,
    keyword: Optional[str] = None,
    end_date_from: Optional[str] = None,
    end_date_to: Optional[str] = None,
    publish_from: Optional[str] = None,
    publish_to: Optional[str] = None,
    industry_code: Optional[List[str]] = None,
    industry_name: Optional[List[str]] = None,
    stock_code: Optional[List[str]] = None,
    stock_name: Optional[List[str]] = None,
    market: Optional[List[str]] = None,
    announcement_type_code: Optional[List[str]] = None,
    announcement_type: Optional[List[str]] = None,
    sort_by: Optional[str] = None,
    sort_order: Optional[str] = None,
) -> Dict:
    """查询公告列表"""
    payload: Dict = {"pageNum": page_num, "pageSize": page_size}
    if keyword:
        payload["keyword"] = keyword
    if end_date_from:
        payload["endDateFrom"] = end_date_from
    if end_date_to:
        payload["endDateTo"] = end_date_to
    if publish_from:
        payload["publishFrom"] = publish_from
    if publish_to:
        payload["publishTo"] = publish_to
    if industry_code:
        payload["industryCode"] = industry_code
    if industry_name:
        payload["industryName"] = industry_name
    if stock_code:
        payload["stockCode"] = stock_code
    if stock_name:
        payload["stockName"] = stock_name
    if market:
        payload["market"] = market
    if announcement_type_code:
        payload["announcementTypeCode"] = announcement_type_code
    if announcement_type:
        payload["announcementType"] = announcement_type
    if sort_by:
        payload["sortBy"] = sort_by
    if sort_order:
        payload["sortOrder"] = sort_order
    return client._post(f"{ANN_PREFIX}/list", payload)


def ann_pdf_download(
    client: AlphaPaiClient,
    ann_id: str,
    output_path: Optional[str] = None,
) -> str:
    """下载公告 PDF，返回保存路径。错误信封抛 DownloadApiError，非 PDF 响应报错。"""
    payload = {"id": ann_id}
    resp = client._post(f"{ANN_PREFIX}/pdf/download", payload, stream=True)
    return save_download_response(
        resp, output_path, default_name=f"announcement_{ann_id}.pdf", expect_prefix=b"%PDF"
    )


def ann_parsing_download(
    client: AlphaPaiClient,
    ann_id: str,
    download_type: str,
    output_path: Optional[str] = None,
) -> str:
    """下载公告 PDF 深度解析产物（Markdown / JSON / ZIP）。"""
    payload = {
        "documentId": ann_id,
        "documentType": "announcement",
        "downloadType": download_type,
    }
    resp = client._post(
        "/alpha/open-api/v1/common/parsing/download", payload, stream=True
    )
    ext = {"markdown": "md", "json": "json", "zip": "zip"}[download_type]
    expect = b"PK\x03\x04" if download_type == "zip" else None
    return save_download_response(
        resp,
        output_path,
        default_name=f"announcement_{ann_id}_parsing.{ext}",
        expect_prefix=expect,
    )


def register_parser(sub: argparse._SubParsersAction) -> argparse.ArgumentParser:
    p = sub.add_parser("announcement", help="公告：检索、PDF 下载、解析结果下载")
    ann_sub = p.add_subparsers(dest="ann_action", required=True)

    # list
    p_list = ann_sub.add_parser("list", help="查询公告列表")
    p_list.add_argument("--page-num", "--pn", type=int, default=1, help="页码，默认 1")
    p_list.add_argument("--page-size", "--ps", type=int, default=20, help="每页条数，默认 20，最大 100")
    p_list.add_argument("--keyword", "-k", help="标题短语匹配")
    p_list.add_argument("--end-date-from", metavar="YYYY-MM-DD", help="报告期起")
    p_list.add_argument("--end-date-to", metavar="YYYY-MM-DD", help="报告期止")
    p_list.add_argument("--publish-from", metavar="YYYY-MM-DD", help="发布日期起")
    p_list.add_argument("--publish-to", metavar="YYYY-MM-DD", help="发布日期止")
    p_list.add_argument("--industry-code", nargs="+", help="行业 code（组内 OR）")
    p_list.add_argument("--industry-name", nargs="+", help="行业名称（组内 OR）")
    p_list.add_argument("--stock-code", nargs="+", help="股票代码（组内 OR），如 600519.SH")
    p_list.add_argument("--stock-name", nargs="+", help="股票名称（组内 OR）")
    p_list.add_argument("--market", nargs="+", choices=["A", "HK", "US"], help="市场：A/HK/US")
    p_list.add_argument("--type-code", nargs="+", help="公告类型 code（可多个）")
    p_list.add_argument("--type-name", nargs="+", help="公告类型名称（可多个）")
    p_list.add_argument("--sort-by",
                        choices=["actual_publish_time", "publish_time", "end_date", "score"],
                        help="排序字段")
    p_list.add_argument("--sort-order", choices=["asc", "desc"], help="排序方向")

    # pdf-download
    p_pdf = ann_sub.add_parser("pdf-download", help="下载公告 PDF")
    p_pdf.add_argument("--id", required=True, help="公告 ID（必填）")
    p_pdf.add_argument("--output", "-o", help="输出路径（文件或目录，缺省从响应头解析）")

    # parsing-download
    p_parsing = ann_sub.add_parser(
        "parsing-download", help="下载公告 PDF 深度解析结果"
    )
    p_parsing.add_argument("--id", required=True, help="公告 ID（从 list 实时获取）")
    p_parsing.add_argument(
        "--download-type",
        required=True,
        choices=["markdown", "json", "zip"],
        help="解析产物类型",
    )
    p_parsing.add_argument(
        "--output", "-o", help="输出路径（文件或目录，缺省从响应头解析）"
    )

    return p


def run(args):
    client = AlphaPaiClient(require_config())
    action = args.ann_action

    if action == "list":
        result = ann_list(
            client,
            page_num=args.page_num, page_size=args.page_size,
            keyword=args.keyword,
            end_date_from=args.end_date_from, end_date_to=args.end_date_to,
            publish_from=args.publish_from, publish_to=args.publish_to,
            industry_code=args.industry_code, industry_name=args.industry_name,
            stock_code=args.stock_code, stock_name=args.stock_name,
            market=args.market,
            announcement_type_code=args.type_code, announcement_type=args.type_name,
            sort_by=args.sort_by, sort_order=args.sort_order,
        )
        require_success(result)
        print_json(result)
    elif action == "pdf-download":
        try:
            saved = ann_pdf_download(client, ann_id=args.id, output_path=args.output)
            print(f"[公告 PDF 下载成功] {saved}")
        except Exception as e:
            print(f"[错误] 下载失败: {e}", file=sys.stderr)
            sys.exit(1)
    elif action == "parsing-download":
        try:
            saved = ann_parsing_download(
                client,
                ann_id=args.id,
                download_type=args.download_type,
                output_path=args.output,
            )
            print(f"[公告解析结果下载成功] {saved}")
        except Exception as e:
            print(f"[错误] 下载失败: {e}", file=sys.stderr)
            sys.exit(1)
    else:
        print(f"[错误] 未知的 announcement 子命令: {action}")
