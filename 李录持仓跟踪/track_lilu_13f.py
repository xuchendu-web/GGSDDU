#!/usr/bin/env python3
"""李录(喜马拉雅资本)13F 持仓跟踪脚本。

直接从 SEC EDGAR 抓取 Himalaya Capital Management LLC(CIK 0001709323)
最近若干期 13F-HR 申报,打印每期完整持仓并计算逐季买卖变动。
同一报告期若存在修正版(13F-HR/A),自动采用最新修正版。

用法:
    python3 track_lilu_13f.py            # 默认对比最近 4 期
    python3 track_lilu_13f.py -n 8       # 对比最近 8 期

仅依赖 Python 标准库。数据滞后实际交易最多约 45 天,不含港股等非美资产。
"""

import argparse
import json
import urllib.request
import xml.etree.ElementTree as ET
from collections import defaultdict

CIK = "0001709323"
UA = {"User-Agent": "LiLu13FTracker research@example.com"}


def fetch(url: str) -> bytes:
    req = urllib.request.Request(url, headers=UA)
    with urllib.request.urlopen(req, timeout=30) as resp:
        return resp.read()


def list_13f_filings(n: int):
    """返回最近 n 个报告期的 13F 申报(同期优先取修正版),按报告期倒序。"""
    data = json.loads(fetch(f"https://data.sec.gov/submissions/CIK{CIK}.json"))
    recent = data["filings"]["recent"]
    by_period = {}
    for form, filed, period, acc in zip(
        recent["form"], recent["filingDate"], recent["reportDate"], recent["accessionNumber"]
    ):
        if form not in ("13F-HR", "13F-HR/A"):
            continue
        # submissions 列表按提交时间倒序,首个出现的即该报告期的最新版本
        if period not in by_period:
            by_period[period] = {"form": form, "filed": filed, "accession": acc}
    periods = sorted(by_period, reverse=True)[:n]
    return [(p, by_period[p]) for p in periods]


def fetch_holdings(accession: str):
    """下载并解析某期 13F 的信息表 XML,返回 {(发行人,类别,CUSIP): {value, shares}}。"""
    acc_nodash = accession.replace("-", "")
    index = fetch(f"https://www.sec.gov/Archives/edgar/data/{int(CIK)}/{acc_nodash}/index.json")
    files = json.loads(index)["directory"]["item"]
    info_xml = next(
        f["name"] for f in files
        if f["name"].endswith(".xml") and "primary_doc" not in f["name"]
    )
    raw = fetch(f"https://www.sec.gov/Archives/edgar/data/{int(CIK)}/{acc_nodash}/{info_xml}")
    root = ET.fromstring(raw)
    ns = {"n": root.tag.split("}")[0].strip("{")}
    holdings = defaultdict(lambda: {"value": 0, "shares": 0})
    for it in root.findall("n:infoTable", ns):
        key = (
            it.find("n:nameOfIssuer", ns).text.strip(),
            it.find("n:titleOfClass", ns).text.strip(),
            it.find("n:cusip", ns).text.strip(),
        )
        holdings[key]["value"] += int(it.find("n:value", ns).text)
        holdings[key]["shares"] += int(it.find("n:shrsOrPrnAmt/n:sshPrnamt", ns).text)
    return dict(holdings)


def print_holdings(period: str, meta: dict, holdings: dict):
    total = sum(v["value"] for v in holdings.values())
    print(f"\n===== 报告期 {period}({meta['form']},提交 {meta['filed']}) =====")
    print(f"美股多头总市值: ${total/1e9:.2f}B,持仓 {len(holdings)} 只")
    print(f"{'发行人':36s}{'市值':>12s}{'股数':>16s}{'占比':>8s}")
    for k, v in sorted(holdings.items(), key=lambda x: -x[1]["value"]):
        print(f"{k[0][:34]:36s}{'$%.1fM' % (v['value']/1e6):>12s}{v['shares']:>16,}{v['value']/total*100:>7.1f}%")


def print_diff(prev_period: str, cur_period: str, prev: dict, cur: dict):
    print(f"\n----- 变动: {prev_period} -> {cur_period} -----")
    changed = False
    for k in sorted(set(prev) | set(cur), key=lambda k: -cur.get(k, {"value": 0})["value"]):
        p = prev.get(k, {"shares": 0})["shares"]
        c = cur.get(k, {"shares": 0})["shares"]
        if p == 0 and c > 0:
            print(f"  [新建仓] {k[0][:32]:34s} +{c:,} 股")
        elif c == 0 and p > 0:
            print(f"  [清仓]   {k[0][:32]:34s} -{p:,} 股")
        elif c != p:
            tag = "加仓" if c > p else "减仓"
            print(f"  [{tag}]   {k[0][:32]:34s} {c-p:+,} 股 ({(c-p)/p*100:+.1f}%)")
        else:
            continue
        changed = True
    if not changed:
        print("  本季零操作(一股未买、一股未卖)")


def main():
    ap = argparse.ArgumentParser(description="李录(喜马拉雅资本)13F 持仓跟踪")
    ap.add_argument("-n", type=int, default=4, help="对比最近 n 个报告期(默认 4)")
    args = ap.parse_args()

    filings = list_13f_filings(args.n)
    if not filings:
        print("未找到 13F 申报")
        return
    # 按报告期正序处理,便于逐季对比
    filings.reverse()
    parsed = []
    for period, meta in filings:
        holdings = fetch_holdings(meta["accession"])
        parsed.append((period, meta, holdings))
        print_holdings(period, meta, holdings)

    for i in range(1, len(parsed)):
        print_diff(parsed[i-1][0], parsed[i][0], parsed[i-1][2], parsed[i][2])

    print("\n提示: 13F 每季度截止后 45 天内披露(约 2/14、5/15、8/14、11/14),"
          "不含比亚迪、邮储银行等港股持仓(需另行跟踪港交所披露易)。")


if __name__ == "__main__":
    main()
