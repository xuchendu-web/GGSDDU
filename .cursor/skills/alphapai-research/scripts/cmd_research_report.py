"""机构研报 API CLI 子命令。"""

import argparse
import sys

from alphapai_base import (
    AlphaPaiClient,
    print_json,
    require_config,
    require_success,
    save_download_response,
)

REPORT_PREFIX = "/alpha/open-api/v1/report"
REPORT_TYPES = [
    "macro", "strategy", "industry", "company", "hk_research", "us_research",
    "fixed_income", "exchange_rate", "financial_engineering", "esg", "daily",
    "stock_recommend", "fund", "new_stock", "other",
]
REPORT_FEATURES = ["deep", "new_fortune"]
COUNTRY_REGIONS = [
    "china", "hong_kong", "taiwan", "united_states", "global", "japan",
    "korea", "india", "singapore", "germany", "united_kingdom", "france",
    "canada", "asia", "europe", "middle_east", "latin_america", "africa",
    "oceania",
]
LANGUAGES = ["zh_cn", "en", "fr", "ja", "es", "de", "nl", "it"]
PAGE_COUNT_RANGES = ["lt_10", "between_10_30", "gt_30"]


def report_list(
    client: AlphaPaiClient,
    page: int = 1,
    page_size: int = 20,
    report_scope: str | None = None,
    keyword: str | None = None,
    start_date: str | None = None,
    end_date: str | None = None,
    report_type: list[str] | None = None,
    report_feature: list[str] | None = None,
    industry_code: list[str] | None = None,
    industry_name: list[str] | None = None,
    stock_comb_symbol: list[str] | None = None,
    stock_name: list[str] | None = None,
    institution_code: list[str] | None = None,
    institution_name: list[str] | None = None,
    country_region: list[str] | None = None,
    language: list[str] | None = None,
    page_count_range: str | None = None,
) -> dict:
    """搜索研报列表"""
    payload: dict = {"page": page, "pageSize": page_size}
    if report_scope:
        payload["reportScope"] = report_scope
    if keyword:
        payload["keyword"] = keyword
    if start_date:
        payload["startDate"] = start_date
    if end_date:
        payload["endDate"] = end_date
    if report_type:
        payload["reportType"] = report_type
    if report_feature:
        payload["reportFeature"] = report_feature
    if industry_code:
        payload["industryCode"] = industry_code
    if industry_name:
        payload["industryName"] = industry_name
    if stock_comb_symbol:
        payload["stockCombSymbol"] = stock_comb_symbol
    if stock_name:
        payload["stockName"] = stock_name
    if institution_code:
        payload["institutionCode"] = institution_code
    if institution_name:
        payload["institutionName"] = institution_name
    if country_region:
        payload["countryRegion"] = country_region
    if language:
        payload["language"] = language
    if page_count_range:
        payload["pageCountRange"] = page_count_range
    return client._post(f"{REPORT_PREFIX}/list", payload)


def report_detail(client: AlphaPaiClient, report_id: str) -> dict:
    """获取研报详情"""
    return client._post(f"{REPORT_PREFIX}/detail", {"reportId": report_id})


def report_pdf_download(
    client: AlphaPaiClient,
    report_id: str,
    output_path: str | None = None,
) -> str:
    """下载研报 PDF，返回保存路径。若接口返回错误 JSON 信封则抛 DownloadApiError。"""
    resp = client._post(
        f"{REPORT_PREFIX}/pdf/download", {"reportId": report_id}, stream=True
    )
    return save_download_response(
        resp, output_path, default_name=f"report_{report_id}.pdf", expect_prefix=b"%PDF"
    )


def parsing_download(
    client: AlphaPaiClient,
    document_id: str,
    document_type: str,
    download_type: str,
    output_path: str | None = None,
) -> str:
    """下载研报或公告的解析结果（markdown / json / zip），返回保存路径。若接口返回错误 JSON 信封则抛 DownloadApiError。"""
    payload = {
        "documentId": document_id,
        "documentType": document_type,
        "downloadType": download_type,
    }
    # 注意：解析下载接口挂在 /common 下，不是 /report 下
    resp = client._post(
        "/alpha/open-api/v1/common/parsing/download", payload, stream=True
    )
    ext_map = {"markdown": "md", "json": "json", "zip": "zip"}
    ext = ext_map.get(download_type, "bin")
    default_name = f"{document_type}_{document_id}_parsing.{ext}"
    # zip 有明确 magic；markdown/json 本身就是文本/JSON，不做前缀校验
    expect = b"PK\x03\x04" if download_type == "zip" else None
    return save_download_response(
        resp, output_path, default_name=default_name, expect_prefix=expect
    )


def register_parser(sub: argparse._SubParsersAction) -> argparse.ArgumentParser:
    p = sub.add_parser(
        "research-report", help="机构研报：列表、详情、PDF下载、解析结果下载"
    )
    rr_sub = p.add_subparsers(dest="rr_action", required=True)

    # list
    p_list = rr_sub.add_parser("list", help="搜索研报列表")
    p_list.add_argument("--page", type=int, default=1, help="页码，默认 1")
    p_list.add_argument("--page-size", type=int, default=20, help="每页条数，默认 20")
    p_list.add_argument(
        "--scope",
        required=True,
        choices=["domestic", "foreign", "independent"],
        help="研报范围（必填）: domestic=内资 foreign=外资 independent=独立",
    )
    p_list.add_argument("--keyword", "-k", help="关键词")
    p_list.add_argument("--start", metavar="YYYY-MM-DD", help="开始日期")
    p_list.add_argument("--end", metavar="YYYY-MM-DD", help="结束日期")
    p_list.add_argument("--report-type", nargs="+", choices=REPORT_TYPES, help="研报类型（可多个）")
    p_list.add_argument("--report-feature", nargs="+", choices=REPORT_FEATURES, help="研报特征（可多个）")
    p_list.add_argument("--industry-code", nargs="+", help="行业 code")
    p_list.add_argument("--industry-name", nargs="+", help="行业名称")
    p_list.add_argument("--stock-symbol", nargs="+", help="股票代码，如 600519.SH")
    p_list.add_argument("--stock-name", nargs="+", help="股票名称")
    p_list.add_argument("--institution-code", nargs="+", help="机构 code")
    p_list.add_argument("--institution-name", nargs="+", help="机构名称")
    p_list.add_argument("--country-region", nargs="+", choices=COUNTRY_REGIONS, help="国家地区")
    p_list.add_argument("--language", nargs="+", choices=LANGUAGES, help="语种")
    p_list.add_argument("--page-count-range", choices=PAGE_COUNT_RANGES, help="页数区间")

    # detail
    p_det = rr_sub.add_parser("detail", help="获取研报详情")
    p_det.add_argument("--report-id", required=True, help="研报 ID（必填）")

    # pdf-download
    p_pdf = rr_sub.add_parser("pdf-download", help="下载研报 PDF")
    p_pdf.add_argument("--report-id", required=True, help="研报 ID（必填）")
    p_pdf.add_argument(
        "--output", "-o", help="输出路径（文件或目录，缺省从响应头解析）"
    )

    # parsing-download
    p_par = rr_sub.add_parser("parsing-download", help="下载研报或公告解析结果")
    p_par.add_argument("--document-id", required=True, help="研报或公告 ID（必填）")
    p_par.add_argument(
        "--document-type",
        required=True,
        choices=["report", "announcement"],
        help="文档类型: report=研报 announcement=公告",
    )
    p_par.add_argument(
        "--download-type",
        required=True,
        choices=["markdown", "json", "zip"],
        help="解析结果类型: markdown/json/zip",
    )
    p_par.add_argument(
        "--output", "-o", help="输出路径（文件或目录，缺省从响应头解析）"
    )

    return p


def run(args):
    client = AlphaPaiClient(require_config())
    action = args.rr_action

    if action == "list":
        result = report_list(
            client,
            page=args.page,
            page_size=args.page_size,
            report_scope=args.scope,
            keyword=args.keyword,
            start_date=args.start,
            end_date=args.end,
            report_type=args.report_type,
            report_feature=args.report_feature,
            industry_code=args.industry_code,
            industry_name=args.industry_name,
            stock_comb_symbol=args.stock_symbol,
            stock_name=args.stock_name,
            institution_code=args.institution_code,
            institution_name=args.institution_name,
            country_region=args.country_region,
            language=args.language,
            page_count_range=args.page_count_range,
        )
        require_success(result)
        print_json(result)
    elif action == "detail":
        result = report_detail(client, report_id=args.report_id)
        require_success(result)
        print_json(result)
    elif action == "pdf-download":
        try:
            saved = report_pdf_download(
                client, report_id=args.report_id, output_path=args.output
            )
            print(f"[研报 PDF 下载成功] {saved}")
        except Exception as e:
            print(f"[错误] 下载失败: {e}", file=sys.stderr)
            sys.exit(1)
    elif action == "parsing-download":
        try:
            saved = parsing_download(
                client,
                document_id=args.document_id,
                document_type=args.document_type,
                download_type=args.download_type,
                output_path=args.output,
            )
            print(f"[解析结果下载成功] {saved}")
        except Exception as e:
            print(f"[错误] 下载失败: {e}", file=sys.stderr)
            sys.exit(1)
    else:
        print(f"[错误] 未知的 research-report 子命令: {action}")
