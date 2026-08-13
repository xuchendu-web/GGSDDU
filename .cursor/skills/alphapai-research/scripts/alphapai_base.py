#!/usr/bin/env python3
"""
AlphaPai 基础模块
=================
配置管理、HTTP 客户端、SSE 解析、公共工具。

供 alphapai_client.py 及各功能 cmd_*.py 模块导入使用。
新功能扩展时只需新增独立的 cmd_<feature>.py，从此模块导入公共能力即可。
"""

import codecs
import json
import os
import re
import sys
from typing import Any, Dict, List, Optional

import requests

# ============================================================
# 公共异常
# ============================================================


class SseApiError(RuntimeError):
    """SSE 流中出现业务错误事件（顶层 code != 200000，或 data 内 type == 500）。"""

    def __init__(self, code, message):
        self.code = code
        self.message = message
        hint = "（限流，请稍后重试）" if code == 42900 else ""
        super().__init__(f"code={code} message={message}{hint}")


class DownloadApiError(RuntimeError):
    """下载接口返回 HTTP 200 但响应体是错误 JSON 信封（code != 200000）时抛出。"""

    def __init__(self, code, message):
        self.code = code
        self.message = message
        super().__init__(f"code={code} message={message}")


# ============================================================
# 配置管理
# ============================================================

DEFAULT_CONFIG_PATH = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "config.json"
)


def load_config(config_path: str = DEFAULT_CONFIG_PATH) -> Optional[Dict]:
    """加载API配置，返回 {"api_key": "...", "base_url": "..."} 或 None"""
    config: Dict = {}
    if os.path.exists(config_path):
        with open(config_path, "r", encoding="utf-8") as f:
            config = json.load(f)
    # 环境变量优先，便于在 CI/Agent 环境使用而不把真实密钥写进仓库。
    if os.environ.get("ALPHAPAI_API_KEY"):
        config["api_key"] = os.environ["ALPHAPAI_API_KEY"]
    if os.environ.get("ALPHAPAI_BASE_URL"):
        config["base_url"] = os.environ["ALPHAPAI_BASE_URL"]
    if not config.get("api_key"):
        return None
    config.setdefault("base_url", "https://open-api.rabyte.cn")
    return config


def save_config(
    api_key: str,
    base_url: str = "https://open-api.rabyte.cn",
    config_path: str = DEFAULT_CONFIG_PATH,
) -> Dict:
    """保存API配置到 config.json"""
    config = {"api_key": api_key, "base_url": base_url}
    os.makedirs(os.path.dirname(config_path), exist_ok=True)
    with open(config_path, "w", encoding="utf-8") as f:
        json.dump(config, f, indent=2, ensure_ascii=False)
    # API Key 属于本地凭据，限制为仅当前用户可读写。
    try:
        os.chmod(config_path, 0o600)
    except OSError:
        # 某些平台或文件系统不支持 POSIX 权限；不影响配置本身可用。
        pass
    return config


def require_config() -> Dict:
    """加载配置，未配置时打印错误并退出"""
    config = load_config()
    if not config:
        print(
            "[错误] 未找到配置，请先运行: python alphapai_client.py config --set-key YOUR_KEY",
            file=sys.stderr,
        )
        sys.exit(1)
    return config


def mask_key(key: str) -> str:
    """脱敏显示 api_key"""
    return key[:4] + "****" + key[-4:] if len(key) > 8 else "****"


# ============================================================
# API Client
# ============================================================


class AlphaPaiClient:
    """AlphaPai Open API 客户端"""

    def __init__(self, config: Dict):
        self.base_url = config["base_url"].rstrip("/")
        self.headers = {
            "app-agent": config["api_key"],
            "Content-Type": "application/json; charset=utf-8",
        }

    def _post(
        self,
        endpoint: str,
        payload: Any = None,
        stream: bool = False,
        timeout: int = 600,
        headers: Optional[Dict] = None,
    ) -> Any:
        """通用POST请求。payload可以是dict或list；stream=True时返回原始Response，False时返回解析后的JSON。"""
        url = f"{self.base_url}{endpoint}"
        body = None if payload is None else json.dumps(payload, ensure_ascii=False).encode("utf-8")
        merged_headers = dict(self.headers)
        if headers:
            merged_headers.update(headers)
        response = requests.post(
            url,
            headers=merged_headers,
            data=body,
            stream=stream,
            timeout=timeout,
        )
        try:
            response.raise_for_status()
        except requests.HTTPError:
            print(
                f"[错误] HTTP {response.status_code} url={url}\n"
                f"响应前500字符: {response.text[:500]}",
                file=sys.stderr,
            )
            raise
        if stream:
            return response
        try:
            return response.json()
        except ValueError:
            print(
                f"[错误] 响应非 JSON，status={response.status_code} url={url}\n"
                f"响应前500字符: {response.text[:500]}",
                file=sys.stderr,
            )
            raise

    def _post_multipart(
        self,
        endpoint: str,
        file_path: str,
        data: Optional[Dict] = None,
        timeout: int = 600,
    ) -> Any:
        """multipart/form-data 文件上传。file_path 为本地文件路径，data 为额外表单字段。"""
        url = f"{self.base_url}{endpoint}"
        # 上传时不带 Content-Type，由 requests 自动设置 multipart boundary
        merged_headers = {k: v for k, v in self.headers.items() if k.lower() != "content-type"}
        files = {"file": open(file_path, "rb")}
        try:
            response = requests.post(
                url,
                headers=merged_headers,
                files=files,
                data=data or {},
                timeout=timeout,
            )
            try:
                response.raise_for_status()
            except requests.HTTPError:
                print(
                    f"[错误] HTTP {response.status_code} url={url}\n"
                    f"响应前500字符: {response.text[:500]}",
                    file=sys.stderr,
                )
                raise
            try:
                return response.json()
            except ValueError:
                print(
                    f"[错误] 响应非 JSON，status={response.status_code} url={url}\n"
                    f"响应前500字符: {response.text[:500]}",
                    file=sys.stderr,
                )
                raise
        finally:
            files["file"].close()

    def _get(
        self,
        endpoint: str,
        params: Optional[Dict] = None,
        stream: bool = False,
        timeout: int = 600,
        headers: Optional[Dict] = None,
    ) -> Any:
        """通用GET请求。params为query参数dict。stream=True时返回原始Response，否则返回解析后的JSON。GET 不带 Content-Type。"""
        url = f"{self.base_url}{endpoint}"
        # GET 请求不带 body，不发送 Content-Type，避免部分网关/WAF 异常
        merged_headers = {k: v for k, v in self.headers.items() if k.lower() != "content-type"}
        if headers:
            merged_headers.update(headers)
        response = requests.get(
            url,
            headers=merged_headers,
            params=params,
            stream=stream,
            timeout=timeout,
        )
        try:
            response.raise_for_status()
        except requests.HTTPError:
            print(
                f"[错误] HTTP {response.status_code} url={response.url}\n"
                f"响应前500字符: {response.text[:500]}",
                file=sys.stderr,
            )
            raise
        if stream:
            return response
        try:
            return response.json()
        except ValueError:
            print(
                f"[错误] 响应非 JSON，status={response.status_code} url={response.url}\n"
                f"响应前500字符: {response.text[:500]}",
                file=sys.stderr,
            )
            raise

    @staticmethod
    def parse_sse(response) -> Dict:
        """解析SSE流式响应，返回聚合结果。

        返回结构：
            {
              "code": int,         # 末事件业务码（正常为 200000）
              "message": str,      # 末事件提示信息
              "questionId": str,   # 服务端问题 id（可能为 None）
              "answer": str,       # 跨事件拼接的完整回答
              "references": list,  # 按 id 去重后的引用来源
            }

        容错与错误透传：
          - 兼容 CRLF、`: ` 心跳注释行、流尾无空行的最后一个事件；
          - 事件 data 不是 dict 时跳过该事件（偶发字符串型 data）；
          - 顶层 code != 200000（如 42900 限流、500303 参数错误）→ 抛 SseApiError；
          - data 内 type == 500（业务失败，如“没有提到关键词”）→ 抛 SseApiError。
        """
        decoder = codecs.getincrementaldecoder("utf-8")(errors="replace")
        buffer, answer = "", ""
        references: List[Dict] = []
        seen_ref_ids = set()
        code, message, question_id = 200000, "success", None

        def _handle_event(event: str):
            nonlocal answer, code, message, question_id
            event = event.strip()
            if not event.startswith("data:"):
                return
            line = event[5:].strip()
            if not line:
                return
            try:
                payload = json.loads(line)
            except json.JSONDecodeError:
                return
            if not isinstance(payload, dict):
                return
            evt_code = payload.get("code", 200000)
            if evt_code != 200000:
                raise SseApiError(evt_code, payload.get("message") or payload.get("msg"))
            d = payload.get("data", payload)
            if not isinstance(d, dict):
                # 偶发 data 为字符串（如错误信封外的异常情况），跳过
                return
            if d.get("type") == 500:
                raise SseApiError(500, d.get("answer") or "Agent 业务失败")
            code = payload.get("code", code)
            message = payload.get("message", message)
            if d.get("questionId"):
                question_id = d["questionId"]
            if d.get("answer"):
                answer += d["answer"]
            for ref in d.get("references") or []:
                if not isinstance(ref, dict):
                    continue
                ref_id = ref.get("id")
                if ref_id is not None and ref_id in seen_ref_ids:
                    continue
                if ref_id is not None:
                    seen_ref_ids.add(ref_id)
                references.append(ref)

        for chunk in response.iter_content(chunk_size=4096):
            if not chunk:
                continue
            buffer += decoder.decode(chunk)
            # 统一 CRLF，按空行切分事件
            buffer = buffer.replace("\r\n", "\n")
            while "\n\n" in buffer:
                event, buffer = buffer.split("\n\n", 1)
                _handle_event(event)
        remaining = decoder.decode(b"", final=True)
        if remaining:
            buffer += remaining
        # 处理流尾未以空行结尾的最后一个事件
        if buffer.strip():
            for event in buffer.split("\n\n"):
                _handle_event(event)
        return {
            "code": code,
            "message": message,
            "questionId": question_id,
            "answer": answer,
            "references": references,
        }

    def health_check(self) -> Dict:
        """健康检查接口，验证 API 连通性与鉴权是否正常"""
        return self._post("/alpha/open-api/v1/sync/auth/hello", {})


# ============================================================
# 公共工具
# ============================================================

TYPE_LABEL = {
    "comment": "点评",
    "vps": "基金定期报告",
    "report": "内资研报",
    "foreign_report": "外资研报",
    "social_media": "社媒",
    "third_report": "三方研报",
    "ann": "公司公告",
    "roadShow": "路演纪要",
    "roadShow_ir": "上市公司披露投关纪要",
    "roadShow_us": "美股纪要",
    "edb": "EDB数据库",
}


def type_label(type_val: str) -> str:
    return TYPE_LABEL.get(type_val, type_val)


def require_success(result: Dict):
    """检查响应码，非成功则打印错误并退出"""
    if result.get("code") != 200000:
        print(
            f"[错误] code={result.get('code')} "
            f"message={result.get('message') or result.get('msg')}",
            file=sys.stderr,
        )
        sys.exit(1)


def parse_stock(s: str) -> Dict:
    """解析 CODE:NAME 格式的股票参数"""
    parts = s.split(":", 1)
    return {"code": parts[0], "name": parts[1] if len(parts) == 2 else ""}


def format_references(references: List[Dict]) -> List[str]:
    """格式化引用来源列表"""
    lines = []
    if references:
        lines.append(f"\n[引用来源 {len(references)} 条]")
        for i, ref in enumerate(references, 1):
            date = f" ({ref.get('publishDate', '')})" if ref.get("publishDate") else ""
            lines.append(
                f"  {i}. [{type_label(ref.get('type', ''))}] {ref.get('title', '')}{date}"
            )
    return lines


def print_json(result: Dict) -> None:
    """输出完整 API JSON 响应"""
    print(json.dumps(result, ensure_ascii=False, indent=2))


def output_json_or_text(result: Dict, formatter, args):
    """兼容旧调用，始终输出 JSON"""
    print_json(result)


# ============================================================
# 文件下载公共工具
# ============================================================


def resolve_save_path(resp, output_path: Optional[str], default_name: str) -> str:
    """确定下载文件保存路径。

    output_path 为目录时拼接 default_name；缺省时尝试从响应头
    Content-Disposition 解析文件名。无论来源如何，最终文件名都
    只取 basename，防止路径穿越或意外覆盖目录外文件。
    """
    if output_path:
        if os.path.isdir(output_path):
            return os.path.join(output_path, default_name)
        # 调用方显式指定的文件路径，只允许落在其父目录内（防透传文件名注入）
        return os.path.join(os.path.dirname(output_path) or ".", os.path.basename(output_path))
    cd = resp.headers.get("Content-Disposition", "")
    m = re.search(r'filename\*?=(?:UTF-8\'\')?"?([^";]+)"?', cd)
    if m:
        try:
            import urllib.parse
            name = urllib.parse.unquote(m.group(1).strip())
        except Exception:
            name = m.group(1).strip()
        name = os.path.basename(name)
        if name:
            return name
    return default_name


def save_download_response(
    resp,
    output_path: Optional[str],
    default_name: str,
    expect_prefix: Optional[bytes] = None,
) -> str:
    """将下载类流式响应落盘，返回保存路径。

    下载接口在鉴权/权限/参数错误时仍可能返回 HTTP 200，响应体是
    {"code": <非200000>, "message"/"msg": "..."} 错误信封（网关用 msg）。
    本函数先读取首个 chunk 探测错误信封：是错误或空响应则抛
    DownloadApiError 且不创建文件；否则按 chunk 流式写盘，避免整文件载入内存。

    expect_prefix：可选的 magic 前缀（如 b"%PDF"），首 chunk 不以该前缀
    开头且不是错误信封时同样报错，防止把异常内容写成目标文件。
    """
    save_path = resolve_save_path(resp, output_path, default_name)
    first_chunk = b""
    stream = resp.iter_content(chunk_size=8192)
    for chunk in stream:
        if chunk:
            first_chunk = chunk
            break
    if not first_chunk:
        raise DownloadApiError(None, "下载响应为空，目标文件可能不存在")
    head = first_chunk.lstrip()[:1]
    if head in (b"{", b"["):
        # 可能是错误信封：错误 JSON 都很小，读完全部再解析
        body = first_chunk + b"".join(stream)
        try:
            obj = json.loads(body)
        except ValueError:
            obj = None
        if isinstance(obj, dict):
            code = obj.get("code", 200000)
            if code != 200000:
                raise DownloadApiError(code, obj.get("message") or obj.get("msg"))
        # 首字符是 { 但不是错误信封（如合法的 JSON 解析产物下载）：
        # 若声明了 expect_prefix 且不匹配，视为异常内容
        if expect_prefix and not first_chunk.startswith(expect_prefix):
            raise DownloadApiError(
                None, f"响应内容与预期格式不符（期望 {expect_prefix!r}，实际为 JSON 文本）"
            )
        with open(save_path, "wb") as f:
            f.write(body)
        return save_path
    if expect_prefix and not first_chunk.startswith(expect_prefix):
        raise DownloadApiError(
            None,
            f"响应内容与预期格式不符（期望 {expect_prefix!r}，实际前 16 字节 {first_chunk[:16]!r}）",
        )
    with open(save_path, "wb") as f:
        f.write(first_chunk)
        for chunk in stream:
            if chunk:
                f.write(chunk)
    return save_path
