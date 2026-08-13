"""录音转记 CLI 子命令。"""

import argparse
import os
import sys
from typing import Dict, Optional
from urllib.parse import urlencode

from alphapai_base import (
    AlphaPaiClient,
    print_json,
    require_config,
    require_success,
    save_download_response,
)

RECORD_PREFIX = "/alpha/open-api/v1/record/convert"


def _post_with_query(client: AlphaPaiClient, endpoint: str, params: Dict) -> Dict:
    """POST 请求但参数放在 query string（rename/delete 接口是这种形式），body 为空对象"""
    url = f"{endpoint}?{urlencode(params, doseq=True)}"
    return client._post(url, {})


def submit_url(
    client: AlphaPaiClient,
    url: str,
    need_translate: bool = False,
    target_language: Optional[str] = None,
    source_language: Optional[str] = None,
    asr_version: Optional[int] = None,
) -> Dict:
    payload: Dict = {"url": url, "needTranslate": need_translate}
    if target_language:
        payload["targetLanguage"] = target_language
    if source_language:
        payload["sourceLanguage"] = source_language
    if asr_version is not None:
        payload["asrVersion"] = asr_version
    return client._post(f"{RECORD_PREFIX}/task/url/submit", payload)


def upload_file(
    client: AlphaPaiClient,
    file_path: str,
    file_type: int,
    title: Optional[str] = None,
    memo: Optional[str] = None,
    update_memo: Optional[int] = None,
    city: Optional[str] = None,
    city_distinct: Optional[str] = None,
) -> Dict:
    data: Dict = {"fileType": file_type}
    if title:
        data["title"] = title
    if memo:
        data["memo"] = memo
    if update_memo is not None:
        data["updateMemo"] = update_memo
    if city:
        data["city"] = city
    if city_distinct:
        data["cityDistinct"] = city_distinct
    return client._post_multipart(f"{RECORD_PREFIX}/file/upload", file_path, data=data)


def add_task(
    client: AlphaPaiClient,
    upload_file_name: str,
    file_id: int,
    language_type: int,
    file_type: int,
    upload_file_url: Optional[str] = None,
    company_id: Optional[str] = None,
    company_name: Optional[str] = None,
    email: Optional[str] = None,
    city: Optional[str] = None,
    city_distinct: Optional[str] = None,
    source_language: Optional[str] = None,
    asr_version: Optional[int] = None,
) -> Dict:
    payload: Dict = {
        "uploadFileName": upload_file_name,
        "fileId": file_id,
        "languageType": language_type,
        "fileType": file_type,
    }
    if upload_file_url:
        payload["uploadFileUrl"] = upload_file_url
    if company_id:
        payload["companyId"] = company_id
    if company_name:
        payload["companyName"] = company_name
    if email:
        payload["email"] = email
    if city:
        payload["city"] = city
    if city_distinct:
        payload["cityDistinct"] = city_distinct
    if source_language:
        payload["sourceLanguage"] = source_language
    if asr_version is not None:
        payload["asrVersion"] = asr_version
    return client._post(f"{RECORD_PREFIX}/task/add", payload)


def query_tasks(
    client: AlphaPaiClient,
    upload_file_name: Optional[str] = None,
    status: Optional[int] = None,
    record_id: Optional[str] = None,
    page_num: int = 1,
    page_size: int = 10,
) -> Dict:
    payload: Dict = {"pageNum": page_num, "pageSize": page_size}
    if upload_file_name:
        payload["uploadFileName"] = upload_file_name
    if status is not None:
        payload["status"] = status
    if record_id:
        payload["recordId"] = record_id
    return client._post(f"{RECORD_PREFIX}/task/query", payload)


def newest_task(client: AlphaPaiClient) -> Dict:
    return client._get(f"{RECORD_PREFIX}/task/newest")


def task_detail(client: AlphaPaiClient, task_id: str) -> Dict:
    return client._get(f"{RECORD_PREFIX}/task/detail", params={"taskId": task_id})


def download_task_result(
    client: AlphaPaiClient,
    task_id: str,
    output_path: Optional[str] = None,
) -> str:
    """下载任务结果（接口直接返回包含最终产物的 zip 文件流），返回保存路径。"""
    resp = client._get(
        f"{RECORD_PREFIX}/task/download",
        params={"taskId": task_id},
        stream=True,
    )
    default_name = f"recording_task_{task_id}.zip"
    return save_download_response(resp, output_path, default_name)


def rename_task(client: AlphaPaiClient, task_id: str, title: str) -> Dict:
    return _post_with_query(
        client,
        f"{RECORD_PREFIX}/task/rename",
        {"taskId": task_id, "title": title},
    )


def delete_task(client: AlphaPaiClient, task_id: str) -> Dict:
    return _post_with_query(
        client,
        f"{RECORD_PREFIX}/task/delete",
        {"taskId": task_id},
    )


def quota(client: AlphaPaiClient) -> Dict:
    return client._get(f"{RECORD_PREFIX}/quota")


def download_file_stream(
    client: AlphaPaiClient,
    file_type: str,
    file_path: str,
    output_path: Optional[str] = None,
) -> str:
    """下载文件流（AI 纪要 Markdown/docx、转写稿、原始媒体），返回保存路径。"""
    payload = {"type": file_type, "filePath": file_path}
    # 该接口属于通用文件下载模块，前缀为 /alpha/open-api/v1/file
    resp = client._post("/alpha/open-api/v1/file/download", payload, stream=True)
    default_name = f"download_{os.path.basename(file_path)}"
    return save_download_response(resp, output_path, default_name)


def download_ai_summary(
    client: AlphaPaiClient,
    task_id: str,
    output_path: Optional[str] = None,
) -> str:
    """下载任务最终产物（接口直接返回包含 AI 纪要/逐字稿等的 zip 文件流）。"""
    return download_task_result(client, task_id, output_path=output_path)


def register_parser(sub: argparse._SubParsersAction) -> argparse.ArgumentParser:
    p = sub.add_parser("recording", help="录音转记：提交链接/文件任务、查询/下载/管理")
    rec_sub = p.add_subparsers(dest="rec_action", required=True)

    p_sub_url = rec_sub.add_parser("submit-url", help="提交链接音视频转纪要任务")
    p_sub_url.add_argument("--url", required=True, help="音视频或文章链接")
    p_sub_url.add_argument("--translate", action="store_true", help="是否需要翻译")
    p_sub_url.add_argument("--target-language", help="目标语言")
    p_sub_url.add_argument("--source-language", help="源语言")
    p_sub_url.add_argument("--asr-version", type=int, choices=[0, 1], help="asr版本: 0=原版 1=新版")

    p_upload = rec_sub.add_parser("upload", help="上传录音或文本文件（返回 fileId）")
    p_upload.add_argument("--file-path", required=True, help="本地文件路径")
    p_upload.add_argument(
        "--file-type", type=int, choices=[10, 20, 40], required=True,
        help="文件类型: 10=语音 20=文件 40=现场录音"
    )
    p_upload.add_argument("--title", help="文件标题")
    p_upload.add_argument("--memo", help="备注")
    p_upload.add_argument("--update-memo", type=int, choices=[0, 1], help="是否编辑过备注: 1=已编辑")
    p_upload.add_argument("--city", help="城市")
    p_upload.add_argument("--city-distinct", help="区县")

    p_sub_file = rec_sub.add_parser("submit-file", help="创建文件转纪要任务（需先 upload 获取 fileId）")
    p_sub_file.add_argument("--file-id", type=int, required=True, help="上传接口返回的 fileId")
    p_sub_file.add_argument("--file-name", required=True, help="待解析文件名")
    p_sub_file.add_argument(
        "--language-type", type=int, choices=[10, 20], required=True, help="语言类型: 10=中文 20=英文"
    )
    p_sub_file.add_argument(
        "--file-type", type=int, choices=[10, 20], required=True, help="文件类型: 10=语音 20=文件"
    )
    p_sub_file.add_argument("--file-url", help="待解析文件的 S3 地址（可选，通常无需传入）")
    p_sub_file.add_argument("--company-id", help="公司 id")
    p_sub_file.add_argument("--company-name", help="公司名称")
    p_sub_file.add_argument("--email", help="邮件地址")
    p_sub_file.add_argument("--city", help="城市")
    p_sub_file.add_argument("--city-distinct", help="区县")
    p_sub_file.add_argument("--source-language", help="源语言类型")
    p_sub_file.add_argument("--asr-version", type=int, choices=[0, 1], help="asr版本: 0=原版 1=新版")

    p_query = rec_sub.add_parser("query", help="查询转纪要任务列表")
    p_query.add_argument("--file-name", help="文件名模糊匹配")
    p_query.add_argument(
        "--status",
        type=int,
        choices=[0, 1, 2, 3, 4, 5, 6, 8, 9, 10, 11, 12],
        help="任务状态: 0=进行中 1=成功 2=失败 3=超时 4=取消 5=等待 6=费用不足 "
        "8=录音中 9=传输中 10=转码中 11=文件过大 12=时长过大",
    )
    p_query.add_argument("--record-id", help="App 录音 record id（非任务 id/fileId，来源于 App 录音列表）")
    p_query.add_argument("--page-num", "--pn", type=int, default=1, help="页码，默认 1")
    p_query.add_argument("--page-size", "--ps", type=int, default=10, help="每页条数，默认 10")

    rec_sub.add_parser("newest", help="查询最新一条纪要生成信息")

    p_detail = rec_sub.add_parser("detail", help="查询任务详情")
    p_detail.add_argument("--task-id", required=True, help="任务 id")

    p_dl = rec_sub.add_parser(
        "download",
        help="下载任务最终产物（接口直接返回包含 AI 纪要/逐字稿等的 zip 文件流）",
    )
    p_dl.add_argument("--task-id", required=True, help="任务 id")
    p_dl.add_argument("--output", "-o", help="输出路径（文件或目录，缺省从响应头解析）")

    p_ai_dl = rec_sub.add_parser(
        "ai-summary-download",
        help="下载任务最终产物 zip（download 的别名，接口直接返回文件流）",
    )
    p_ai_dl.add_argument("--task-id", required=True, help="任务 id")
    p_ai_dl.add_argument("--output", "-o", help="输出路径（文件或目录）")

    p_dl_file = rec_sub.add_parser(
        "download-file",
        help="通过通用文件下载接口下载单个文件（需先取得 type 与 filePath）",
    )
    p_dl_file.add_argument(
        "--type",
        required=True,
        help="文件类型，AI 纪要 Markdown/docx 与转写稿实测使用 \"2\"",
    )
    p_dl_file.add_argument(
        "--file-path", required=True,
        help="文件 S3 key 路径（去掉域名的路径部分）",
    )
    p_dl_file.add_argument("--output", "-o", help="输出路径（文件或目录，缺省从响应头解析）")

    p_rename = rec_sub.add_parser("rename", help="重命名任务标题")
    p_rename.add_argument("--task-id", required=True, help="任务 id")
    p_rename.add_argument("--title", required=True, help="新标题")

    p_del = rec_sub.add_parser("delete", help="删除任务")
    p_del.add_argument("--task-id", required=True, help="任务 id")

    rec_sub.add_parser("quota", help="查询本月转纪要额度")

    return p


def run(args):
    client = AlphaPaiClient(require_config())
    action = args.rec_action

    if action == "submit-url":
        result = submit_url(
            client,
            url=args.url,
            need_translate=args.translate,
            target_language=args.target_language,
            source_language=args.source_language,
            asr_version=args.asr_version,
        )
    elif action == "upload":
        result = upload_file(
            client,
            file_path=args.file_path,
            file_type=args.file_type,
            title=args.title,
            memo=args.memo,
            update_memo=args.update_memo,
            city=args.city,
            city_distinct=args.city_distinct,
        )
    elif action == "submit-file":
        result = add_task(
            client,
            upload_file_name=args.file_name,
            file_id=args.file_id,
            language_type=args.language_type,
            file_type=args.file_type,
            upload_file_url=args.file_url,
            company_id=args.company_id,
            company_name=args.company_name,
            email=args.email,
            city=args.city,
            city_distinct=args.city_distinct,
            source_language=args.source_language,
            asr_version=args.asr_version,
        )
    elif action == "query":
        result = query_tasks(
            client,
            upload_file_name=args.file_name,
            status=args.status,
            record_id=args.record_id,
            page_num=args.page_num,
            page_size=args.page_size,
        )
    elif action == "newest":
        result = newest_task(client)
    elif action == "detail":
        result = task_detail(client, task_id=args.task_id)
    elif action == "download":
        try:
            saved = download_task_result(
                client,
                task_id=args.task_id,
                output_path=args.output,
            )
            print(f"[任务产物下载成功] path={saved}")
            return
        except Exception as e:
            print(f"[错误] 下载失败: {e}", file=sys.stderr)
            sys.exit(1)
    elif action == "ai-summary-download":
        try:
            saved = download_ai_summary(
                client,
                task_id=args.task_id,
                output_path=args.output,
            )
            print(f"[任务产物下载成功] path={saved}")
            return
        except Exception as e:
            print(f"[错误] 下载失败: {e}", file=sys.stderr)
            sys.exit(1)
    elif action == "download-file":
        try:
            saved = download_file_stream(
                client,
                file_type=args.type,
                file_path=args.file_path,
                output_path=args.output,
            )
            print(f"[文件下载成功] {saved}")
            return
        except Exception as e:
            print(f"[错误] 下载失败: {e}", file=sys.stderr)
            sys.exit(1)
    elif action == "rename":
        result = rename_task(client, task_id=args.task_id, title=args.title)
    elif action == "delete":
        result = delete_task(client, task_id=args.task_id)
    elif action == "quota":
        result = quota(client)
    else:
        print(f"[错误] 未知的 recording 子命令: {action}")
        return

    require_success(result)
    print_json(result)
