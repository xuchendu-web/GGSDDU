"""
news_search 工具原型 —— 借鉴 cn-web-search 的多引擎聚合思路，工程化为对话层可注册的工具。

与 cn-web-search（提示词层 Skill）的区别：
1. 引擎适配器代码化：每个引擎一个解析器，输出统一的 SearchResult 结构，而非让 LLM 现场读网页；
2. 来源可信度分层：官方公告(T1) > 权威财经媒体(T2) > 聚合搜索(T3) > 社区(T4)，进入报告的引用按层级过滤；
3. 多源交叉验证：同一事实被多少个独立引擎命中，输出 corroboration 计数；
4. 证据留痕：每次检索保存快照（查询、引擎、原始命中、抓取时间），供证据包引用；
5. 降级链：引擎失败自动切换下一引擎，全部失败返回明确的"检索不可用"而非幻觉。
"""

from __future__ import annotations

import concurrent.futures
import dataclasses
import hashlib
import json
import re
import time
import urllib.parse
from typing import Callable

import requests
from bs4 import BeautifulSoup

UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/126.0 Safari/537.36")
TIMEOUT = 10

# 可信度分层：数字仅允许引用 T1；T2 可作定性引用；T3/T4 仅作线索，须标注
TIER_OFFICIAL = 1      # 交易所/指数公司/基金公司公告（site: 限定检索）
TIER_FIN_MEDIA = 2     # 权威财经媒体
TIER_AGGREGATOR = 3    # 通用聚合搜索
TIER_COMMUNITY = 4     # 投资社区


@dataclasses.dataclass
class SearchResult:
    title: str
    url: str
    snippet: str
    engine: str
    tier: int
    fetched_at: str
    corroboration: int = 1
    engines: list[str] = dataclasses.field(default_factory=list)

    def to_dict(self) -> dict:
        return dataclasses.asdict(self)


def _get(url: str) -> str:
    resp = requests.get(url, headers={"User-Agent": UA}, timeout=TIMEOUT)
    resp.raise_for_status()
    if not resp.encoding or resp.encoding.lower() == "iso-8859-1":
        resp.encoding = resp.apparent_encoding
    return resp.text


def _clean(text: str) -> str:
    return re.sub(r"\s+", " ", text or "").strip()


# ---------------- 引擎适配器 ----------------

def search_sogou(query: str) -> list[SearchResult]:
    url = f"https://www.sogou.com/web?query={urllib.parse.quote(query)}"
    soup = BeautifulSoup(_get(url), "html.parser")
    now = time.strftime("%Y-%m-%d %H:%M:%S")
    out = []
    for block in soup.select("div.vrwrap"):
        a = block.select_one("h3 a")
        if not a or not _clean(a.get_text()):
            continue
        href = a.get("href", "")
        if href.startswith("/"):
            href = "https://www.sogou.com" + href
        snippet_el = block.select_one(".space-txt, .text-layout, .str_info")
        out.append(SearchResult(
            title=_clean(a.get_text()), url=href,
            snippet=_clean(snippet_el.get_text())[:200] if snippet_el else "",
            engine="sogou", tier=TIER_AGGREGATOR, fetched_at=now))
    return out


def search_so360(query: str) -> list[SearchResult]:
    url = f"https://m.so.com/s?q={urllib.parse.quote(query)}"
    soup = BeautifulSoup(_get(url), "html.parser")
    now = time.strftime("%Y-%m-%d %H:%M:%S")
    out = []
    for block in soup.select("div.res-list, li.res-list"):
        a = block.select_one("h3 a, a.res-title, a")
        if not a or len(_clean(a.get_text())) < 6:
            continue
        snippet_el = block.select_one(".res-desc, .res-summary, p")
        out.append(SearchResult(
            title=_clean(a.get_text()), url=a.get("href", ""),
            snippet=_clean(snippet_el.get_text())[:200] if snippet_el else "",
            engine="so360", tier=TIER_AGGREGATOR, fetched_at=now))
    return out


def search_bing_cn(query: str, site_filter: str | None = None,
                   engine_name: str = "bing_cn", tier: int = TIER_AGGREGATOR) -> list[SearchResult]:
    q = f"site:{site_filter} {query}" if site_filter else query
    url = f"https://cn.bing.com/search?q={urllib.parse.quote(q)}"
    soup = BeautifulSoup(_get(url), "html.parser")
    now = time.strftime("%Y-%m-%d %H:%M:%S")
    out = []
    for block in soup.select("li.b_algo"):
        a = block.select_one("h2 a")
        if not a:
            continue
        snippet_el = block.select_one(".b_caption p, .b_lineclamp2, .b_paractl")
        out.append(SearchResult(
            title=_clean(a.get_text()), url=a.get("href", ""),
            snippet=_clean(snippet_el.get_text())[:200] if snippet_el else "",
            engine=engine_name, tier=tier, fetched_at=now))
    return out


def search_official(query: str) -> list[SearchResult]:
    """T1 官方来源：用 site: 限定检索交易所/指数公司/证监会域名。"""
    sites = "csindex.com.cn OR sse.com.cn OR szse.cn OR csrc.gov.cn"
    return search_bing_cn(query, site_filter=f"({sites})".replace("site:(", "(").replace(")", ")"),
                          engine_name="official", tier=TIER_OFFICIAL) or \
        _official_fallback(query)


def _official_fallback(query: str) -> list[SearchResult]:
    out = []
    for site in ("csindex.com.cn", "sse.com.cn"):
        try:
            out.extend(search_bing_cn(query, site_filter=site,
                                      engine_name="official", tier=TIER_OFFICIAL))
        except Exception:
            continue
    return out


def search_jisilu(query: str) -> list[SearchResult]:
    url = f"https://www.jisilu.cn/explore/?keyword={urllib.parse.quote(query)}"
    soup = BeautifulSoup(_get(url), "html.parser")
    now = time.strftime("%Y-%m-%d %H:%M:%S")
    out = []
    for block in soup.select(".aw-question-content"):
        a = block.select_one("h4 a, a")
        if not a or len(_clean(a.get_text())) < 6:
            continue
        href = a.get("href", "")
        if href.startswith("/"):
            href = "https://www.jisilu.cn" + href
        out.append(SearchResult(
            title=_clean(a.get_text()), url=href, snippet="",
            engine="jisilu", tier=TIER_COMMUNITY, fetched_at=now))
    return out


ENGINES: dict[str, Callable[[str], list[SearchResult]]] = {
    "official": search_official,   # T1
    "sogou": search_sogou,         # T3
    "bing_cn": search_bing_cn,     # T3
    "so360": search_so360,         # T3
    "jisilu": search_jisilu,       # T4
}


# ---------------- 聚合与交叉验证 ----------------

def _title_key(title: str) -> set:
    t = re.sub(r"[^\w\u4e00-\u9fff]", "", title.lower())
    return {t[i:i + 2] for i in range(len(t) - 1)} if len(t) > 1 else {t}


def _similar(a: str, b: str) -> float:
    ka, kb = _title_key(a), _title_key(b)
    if not ka or not kb:
        return 0.0
    return len(ka & kb) / len(ka | kb)


def aggregate(results: list[SearchResult], sim_threshold: float = 0.55) -> list[SearchResult]:
    """按标题相似度去重合并，统计跨引擎佐证数（corroboration）。"""
    merged: list[SearchResult] = []
    for r in results:
        hit = None
        for m in merged:
            if _similar(r.title, m.title) >= sim_threshold:
                hit = m
                break
        if hit:
            if r.engine not in hit.engines:
                hit.engines.append(r.engine)
                hit.corroboration += 1
            if r.tier < hit.tier:      # 保留更高可信来源的链接
                hit.url, hit.tier, hit.engine = r.url, r.tier, r.engine
            if len(r.snippet) > len(hit.snippet):
                hit.snippet = r.snippet
        else:
            r.engines = [r.engine]
            merged.append(r)
    # 排序：先按可信层级，再按佐证数
    merged.sort(key=lambda x: (x.tier, -x.corroboration))
    return merged


def news_search(query: str, engines: list[str] | None = None,
                top_k: int = 10) -> dict:
    """对话层注册的工具入口。返回结构化结果 + 检索快照元数据。"""
    engines = engines or ["official", "sogou", "bing_cn", "so360"]
    raw: list[SearchResult] = []
    trace = {}
    with concurrent.futures.ThreadPoolExecutor(max_workers=5) as ex:
        futures = {ex.submit(ENGINES[e], query): e for e in engines if e in ENGINES}
        for fut in concurrent.futures.as_completed(futures):
            name = futures[fut]
            try:
                hits = fut.result()
                raw.extend(hits)
                trace[name] = {"status": "ok", "hits": len(hits)}
            except Exception as exc:
                trace[name] = {"status": "error", "error": str(exc)[:120]}
    merged = aggregate(raw)[:top_k]
    snapshot_id = "NS-" + hashlib.md5(
        f"{query}{time.time()}".encode()).hexdigest()[:8]
    return {
        "snapshot_id": snapshot_id,
        "query": query,
        "searched_at": time.strftime("%Y-%m-%d %H:%M:%S"),
        "engine_trace": trace,
        "results": [r.to_dict() for r in merged],
        "usage_rule": ("T1 可作数字与事实引用；T2 可作定性引用；"
                       "T3/T4 仅作线索，报告引用须标注层级。"
                       "新闻内容不得生成数值结论，数值仅来自信号引擎。"),
    }


if __name__ == "__main__":
    import sys
    q = sys.argv[1] if len(sys.argv) > 1 else "沪深300 指数 调样"
    print(json.dumps(news_search(q), ensure_ascii=False, indent=2))
