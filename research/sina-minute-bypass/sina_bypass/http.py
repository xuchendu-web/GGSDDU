"""极简 HTTP。研究轨，不走进门/中金/Alpha派。"""

from __future__ import annotations

import json
import ssl
import time
import urllib.error
import urllib.request
from typing import Any

DEFAULT_UA = "GGSDDU-sina-minute-bypass/0.1 (research-only)"
CTX = ssl.create_default_context()


class HttpError(RuntimeError):
    pass


def fetch_text(
    url: str,
    *,
    headers: dict[str, str] | None = None,
    timeout: float = 12.0,
    retries: int = 2,
    pause: float = 0.4,
) -> str:
    hdrs = {"User-Agent": DEFAULT_UA, **(headers or {})}
    last: Exception | None = None
    for i in range(retries + 1):
        req = urllib.request.Request(url, headers=hdrs)
        try:
            with urllib.request.urlopen(req, timeout=timeout, context=CTX) as resp:
                raw = resp.read()
                charset = "utf-8"
                ctype = resp.headers.get("Content-Type") or ""
                if "gbk" in ctype.lower() or "gb2312" in ctype.lower():
                    charset = "gbk"
                return raw.decode(charset, errors="replace")
        except (urllib.error.URLError, TimeoutError, OSError) as exc:
            last = exc
            if i < retries:
                time.sleep(pause * (i + 1))
    raise HttpError(f"GET 失败 {url}: {last}") from last


def parse_jsonp(text: str) -> Any:
    body = text.strip()
    if body == "" or body == "null":
        return None
    eq = body.find("=")
    start = body.find("[", eq if eq != -1 else 0)
    brace = body.find("{", eq if eq != -1 else 0)
    if start == -1 or (brace != -1 and brace < start):
        start = brace
    if start == -1:
        raise ValueError("jsonp 无 JSON 起点")
    chunk = body[start:].rstrip()
    if chunk.endswith(";"):
        chunk = chunk[:-1]
    if chunk.endswith(")"):
        chunk = chunk[:-1]
    return json.loads(chunk)
