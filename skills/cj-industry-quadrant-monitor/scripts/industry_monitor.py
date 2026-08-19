# -*- coding: utf-8 -*-
"""申万行业四象限监控 · CLI 编排（第三期 D2 industry_monitor，仅编排 < 200 行）

v3.1.0 —— 完整模块拆分（config / datasource / scoring / render / cache）+ 
分层缓存（D16）+ 三格式输出 HTML/Excel/PDF（D18）+ logging（D19）+ 渲染修复（N3/C3/N-5/N-3/D22）。

算法与 v2.2.0-phase2 完全一致（D9 全市场 z、D13 累计同比、D14 因子剔除、D11 双口径、
L6/L7 统一门槛与排序），本版只做工程化，不碰打分数学。
"""

import argparse
import json
import logging
import re
import sys
import time
from datetime import datetime, timedelta
from pathlib import Path
from uuid import uuid4

import config
import cache as cache_mod
import datasource
import scoring
import render

SCRIPT_VERSION = "3.1.0"

logger = logging.getLogger("iqm")

# ═══════════════════════════════════════════════════════════════
# logging（D19）：文件纯文本（去 emoji）+ 控制台（TTY 才显示 emoji）
# ═══════════════════════════════════════════════════════════════
import re as _re
_EMOJI = _re.compile(r"[\U0001F000-\U0001FAFF\U00002600-\U000027BF\U0001F1E6-\U0001F1FF]")


class NoEmojiFilter(logging.Filter):
    def filter(self, record):
        if isinstance(record.msg, str):
            record.msg = _EMOJI.sub("", record.msg)
        return True


def setup_logging(verbose, quiet, log_path):
    root = logging.getLogger("iqm")
    root.setLevel(logging.DEBUG)
    for h in list(root.handlers):
        root.removeHandler(h)
    fmt = logging.Formatter("%(asctime)s %(levelname)s %(message)s")

    fh = logging.FileHandler(log_path, encoding="utf-8")
    fh.setLevel(logging.DEBUG)
    fh.setFormatter(fmt)
    fh.addFilter(NoEmojiFilter())
    root.addHandler(fh)

    ch = logging.StreamHandler(sys.stdout)
    level = logging.DEBUG if verbose else (logging.WARNING if quiet else logging.INFO)
    ch.setLevel(level)
    ch.setFormatter(logging.Formatter("%(message)s"))
    # 非 TTY 终端（如流水线/文件重定向）也去掉 emoji，避免 GBK 乱码（E14）
    if not sys.stdout.isatty():
        ch.addFilter(NoEmojiFilter())
    root.addHandler(ch)


def close_logging():
    root = logging.getLogger("iqm")
    for h in list(root.handlers):
        h.flush()
        h.close()
        root.removeHandler(h)


# ═══════════════════════════════════════════════════════════════
# 参数校验与输出前置检查（E1/E2/E6/E7/E8/E9）
# ═══════════════════════════════════════════════════════════════
QUARTER_ENDS = config.QUARTER_ENDS


def normalize_quarter(value):
    """把 2026Q1 / 2026-03-31 / 20260331 统一成 20260331，非法则报错（L5）。"""
    if value is None:
        return None
    s = str(value).strip().upper().replace("-", "").replace("/", "")
    m = re.fullmatch(r"(\d{4})Q([1-4])", s)
    if m:
        s = m.group(1) + QUARTER_ENDS[int(m.group(2)) - 1]
    if not re.fullmatch(r"\d{8}", s):
        raise config.ArgError(
            "--fundamental-quarter 格式非法：{!r}。"
            "支持 YYYYMMDD（如 20260331）或 YYYYQn（如 2026Q1）。".format(value))
    if s[4:] not in QUARTER_ENDS:
        raise config.ArgError(
            "--fundamental-quarter 必须是报告期末日（{}），收到 {}。".format(
                "/".join(QUARTER_ENDS), s))
    year = int(s[:4])
    if not (1990 <= year <= datetime.now().year + 1):
        raise config.ArgError("--fundamental-quarter 年份 {} 超出合理范围。".format(year))
    return s


def validate_args(args):
    """所有参数在跑任何网络请求之前校验完毕，fail fast。"""
    if args.lookback < 1:
        raise config.ArgError(
            "--lookback 必须 >= 1，收到 {}。\n"
            "  说明：lookback=0 会让三个时间截面重合、动量恒为 0；负数会时间倒流。".format(args.lookback))
    if args.lookback > 250:
        raise config.ArgError("--lookback 最大 250（约一年），收到 {}。".format(args.lookback))
    if args.lookback < 5:
        logger.warning("[!] --lookback=%d 偏小，单期动量噪声会很大，建议 >= 5", args.lookback)

    if args.min_stocks < 1:
        raise config.ArgError("--min-stocks 必须 >= 1，收到 {}。".format(args.min_stocks))
    if args.min_stocks > 100:
        logger.warning("[!] --min-stocks=%d 偏大，可能把绝大多数行业筛掉", args.min_stocks)

    if not (1 <= args.batch_size <= 1000):
        raise config.ArgError("--batch-size 需在 1~1000 之间，收到 {}。".format(args.batch_size))
    if args.batch_size > 300:
        logger.warning("[!] --batch-size=%d 大于推荐值 300，超时风险上升", args.batch_size)

    if not (1 <= args.factor_batch_size <= 2000):
        raise config.ArgError("--factor-batch-size 需在 1~2000 之间，收到 {}。".format(args.factor_batch_size))
    if not (0.0 <= args.min_coverage <= 1.0):
        raise config.ArgError("--min-coverage 需在 0~1 之间，收到 {}。".format(args.min_coverage))
    if args.max_retry < 1:
        raise config.ArgError("--max-retry 必须 >= 1，收到 {}。".format(args.max_retry))

    args.fundamental_quarter = normalize_quarter(args.fundamental_quarter)
    if args.history_start is not None:
        s = str(args.history_start).strip().replace("-", "")
        if not re.fullmatch(r"\d{8}", s):
            raise config.ArgError("--history-start 需为 YYYYMMDD，收到 {!r}。".format(args.history_start))
        args.history_start = s
    if args.as_of is not None:
        args.as_of = str(args.as_of).replace("-", "")
        if not re.fullmatch(r"\d{8}", args.as_of):
            raise config.ArgError("--as-of 需为 YYYYMMDD，收到 {!r}".format(args.as_of))
    return args


def ensure_writable(path):
    """启动即确认输出可写，避免跑满后才发现文件被占用（E8/E9）。"""
    p = Path(path).expanduser()
    try:
        p.parent.mkdir(parents=True, exist_ok=True)
    except OSError as e:
        raise config.OutputError("无法创建输出目录 {}：{}".format(p.parent, e))
    if p.exists():
        try:
            with open(p, "a", encoding="utf-8"):
                pass
        except OSError as e:
            raise config.OutputError(
                "输出文件无法写入：{}\n  原因：{}\n  最常见是文件正被浏览器/Excel 打开，请关闭后重试。".format(p, e))
    else:
        probe = p.parent / (p.name + ".writetest")
        try:
            with open(probe, "w", encoding="utf-8") as f:
                f.write("")
        except OSError as e:
            raise config.OutputError("输出目录不可写：{}\n  原因：{}".format(p.parent, e))
        finally:
            try:
                if probe.exists():
                    probe.unlink()
            except OSError:
                pass
    return p


def coverage_gate(meta, min_coverage, allow_partial):
    """覆盖率门槛（[清单#7/#8]）：关键环节不达标即失败退出、不产出报告。"""
    checks = [
        ("行业分类", meta.get("cov_industry")),
        ("财务数据", meta.get("cov_financial")),
        ("技术面因子", meta.get("cov_technical")),
    ]
    bad = [(name, cov) for name, cov in checks
           if cov is not None and cov < min_coverage]
    meta["coverage_ok"] = not bad
    if not bad:
        return
    detail = "；".join("{} {:.1%}".format(n, c) for n, c in bad)
    if allow_partial:
        meta["coverage_ok"] = False
        meta.setdefault("degraded_notes", []).append(
            "覆盖率未达门槛 {:.0%}（{}），已通过 --allow-partial 强制继续，结论仅供参考".format(min_coverage, detail))
        logger.warning("[!] 覆盖率不达标：%s（门槛 %.0f%%）", detail, min_coverage * 100)
        return
    raise config.DataError(
        "覆盖率不达标，拒绝产出报告：{}（门槛 {:.0%}）。\n"
        "  打分用全市场截面 z-score，缺一批股票会同时改变均值/标准差和行业中位数。\n"
        "  处理：1) 稍后重试  2) 调小批次 --batch-size 200  3) 增加重试 --max-retry 8\n"
        "  4) 确实要看降级结果：--allow-partial".format(detail, min_coverage))


# ═══════════════════════════════════════════════════════════════
# 主流程
# ═══════════════════════════════════════════════════════════════
def _is_trading_day(d):
    """粗略交易日判断：周一~周五（未含法定节假日；长假会让文件名多退一天，属可接受边缘）。"""
    return d.weekday() < 5


def report_date():
    """按收盘规则返回报告日期（用于默认输出文件名）：
    - 当前为交易日且已收盘（>=15:00）→ 当日
    - 否则（盘中 / 周末 / 休市）→ 最近一个已收盘交易日（默认前一日）
    """
    now = datetime.now()
    today = now.date()
    if _is_trading_day(today) and (now.hour, now.minute) >= (15, 0):
        return today
    d = today - timedelta(days=1)
    for _ in range(15):
        if _is_trading_day(d):
            return d
        d -= timedelta(days=1)
    return today


def _output_paths(output):
    """把 -o 给定的输出路径拆成 html/xlsx/pdf/run.log 四件套（同名不同扩展名）。"""
    p = Path(output)
    if p.suffix.lower() == ".html":
        stem = p.with_suffix("")
    else:
        stem = p
    return {
        "html": str(stem.with_suffix(".html")),
        "xlsx": str(stem.with_suffix(".xlsx")),
        "pdf": str(stem.with_suffix(".pdf")),
        "log": str(stem.with_suffix(".run.log")),
        "manifest": str(stem.with_suffix(".manifest.json")),
    }


def resolve_as_of():
    today = datetime.now().strftime("%Y%m%d")
    start = (datetime.now() - timedelta(days=30)).strftime("%Y%m%d")
    days = datasource.call_with_retry(datasource.cjpy.get_trading_days, start, today,
                                      cycle="D", _what="确定最新交易日")
    if not days:
        raise config.DataError("CJPY 未返回最近交易日，无法确定统一 as-of 日期。")
    return str(days[-1])


def validate_artifacts(paths):
    html = Path(paths["html"]).read_text(encoding="utf-8")
    if "Plotly.newPlot" not in html or "\ufffd" in html:
        raise config.OutputError("HTML 结构或编码验证失败")
    try:
        import openpyxl
        wb = openpyxl.load_workbook(paths["xlsx"], read_only=True)
        if not {"四象限汇总", "行业得分", "数据血统"}.issubset(wb.sheetnames): raise ValueError("工作表不完整")
        wb.close()
        from pypdf import PdfReader
        if not PdfReader(paths["pdf"]).pages: raise ValueError("PDF 无页面")
    except Exception as e:
        raise config.OutputError("产物验证失败：{}".format(e))


def run(args):
    industry_col = config.SW_LEVEL_MAP[args.sw_level]
    sw_label = config.SW_LEVEL_LABEL[args.sw_level]
    industry_asof = args.as_of or resolve_as_of()

    if args.output is None:
        rpt = industry_asof
        args.output = "{}行业四象限监控_{}.html".format(
            config.SW_LEVEL_LABEL[args.sw_level], rpt)

    paths = _output_paths(args.output)
    out_html = Path(paths["html"])
    for p in paths.values():
        ensure_writable(p)
    tmp_dir = out_html.parent / ("." + out_html.stem + ".tmp-" + uuid4().hex)
    tmp_dir.mkdir()
    tmp_paths = {k: str(tmp_dir / Path(v).name) for k, v in paths.items()}
    setup_logging(args.verbose, args.quiet, tmp_paths["log"])

    history_start = args.history_start or "{}0101".format(datetime.now().year - 7)
    cache = cache_mod.Cache(cache_dir=args.cache_dir, enabled=not args.no_cache)

    logger.info("=" * 70)
    logger.info("%s行业四象限监控  v%s", sw_label, SCRIPT_VERSION)
    logger.info("  回看 %d 日 | 最少成分股 %d | 财务批 %d | 因子批 %d | 重试 %d | 覆盖率门槛 %.0f%%",
                args.lookback, args.min_stocks, args.batch_size, args.factor_batch_size,
                args.max_retry, args.min_coverage)
    logger.info("  财务起始 %s | 缓存=%s | 输出 %s", history_start,
                "关" if args.no_cache else "开", out_html)

    t_start = time.time()
    meta = {
        "script_version": SCRIPT_VERSION,
        "sw_level": args.sw_level,
        "sw_label": sw_label,
        "industry_col": industry_col,
        "lookback": args.lookback,
        "min_coverage": args.min_coverage,
        "python": sys.version.split()[0],
        "degraded_notes": [],
    }

    # 1. A 股列表 + 剔除 ST/停牌退市（D14，宇宙层面）
    codes = datasource.get_a_stocks()
    if not codes:
        raise config.EmptyResultError("股票池为空，get_stocks() 没有返回任何 SZ/SH 代码。")
    meta["universe_raw"] = len(codes)
    excluded, excl_info = datasource.load_exclusion_flags(
        codes, industry_col, industry_asof,
        batch_size=args.factor_batch_size, max_retry=args.max_retry)
    codes = [c for c in codes if c not in excluded]
    if not codes:
        raise config.EmptyResultError("过滤 ST/停牌退市后股票池为空，无法继续。")
    meta["excluded"] = excl_info["total"]
    meta["universe"] = len(codes)
    logger.info("\n共 %d 只 A 股；剔除 ST/停牌退市 %d 只后剩 %d 只",
                meta["universe_raw"], excl_info["total"], len(codes))

    # 2. 行业分类
    industry_map, fail_ind = datasource.get_sw_industry(
        codes, industry_col, batch_size=args.factor_batch_size,
        max_retry=args.max_retry, as_of=industry_asof)
    industry_map = industry_map[
        industry_map[industry_col].notna() & (industry_map[industry_col] != "")]
    valid_codes = industry_map["代码"].unique().tolist()
    if not valid_codes:
        raise config.EmptyResultError("没有任何股票拿到有效的{}。".format(industry_col))
    meta["industry_asof"] = industry_asof
    meta["cov_industry"] = len(valid_codes) / len(codes)
    meta["fail_industry"] = len(fail_ind)
    logger.info("  %d 个%s，%d 只股票有有效行业归属（覆盖 %.1f%%）",
                industry_map[industry_col].nunique(), industry_col,
                len(valid_codes), meta["cov_industry"])

    # 3. 财务数据（带缓存，D16）
    fin_df, fail_fin = datasource.get_financial_data(
        valid_codes, batch_size=args.batch_size, start=history_start,
        max_retry=args.max_retry, cache=cache)
    fin_codes = fin_df["CODE"].nunique() if "CODE" in fin_df.columns else 0
    meta["cov_financial"] = fin_codes / len(valid_codes)
    meta["fail_financial"] = len(fail_fin)
    logger.info("  财务覆盖 %d/%d = %.1f%%", fin_codes, len(valid_codes), meta["cov_financial"] * 100)

    # 4. 技术面
    tech_df, t0, t1, t2, fail_tech = datasource.get_technical_data(
        valid_codes, args.lookback, batch_size=args.factor_batch_size,
        max_retry=args.max_retry, as_of=industry_asof)
    tech_codes = tech_df["代码"].nunique() if "代码" in tech_df.columns else 0
    meta.update({"t0": t0, "t1": t1, "t2": t2,
                 "cov_technical": tech_codes / len(valid_codes),
                 "fail_technical": len(fail_tech)})
    logger.info("  技术面覆盖 %d/%d = %.1f%%", tech_codes, len(valid_codes), meta["cov_technical"] * 100)

    # 覆盖率门槛：所有关键取数完成后立刻判定
    coverage_gate(meta, args.min_coverage, args.allow_partial)

    # 5. 估值分位（PETTM 因子，D4；带缓存，D16）
    pe_pct = None
    pe_stats = {}
    meta["fail_pe"] = 0
    meta["cov_pe"] = None
    if args.skip_valuation:
        meta["pe_desc"] = "已用 --skip-valuation 跳过；气泡尺寸统一按 50 处理，无区分意义"
        meta["degraded_notes"].append("PE 分位未计算，气泡尺寸无意义")
    else:
        pe_start = (datetime.strptime(industry_asof, "%Y%m%d") - timedelta(days=int(365 * args.pe_window_years) + 30)).strftime("%Y%m%d")
        pe_cal = datasource.call_with_retry(
            datasource.cjpy.get_trading_days, pe_start, industry_asof,
            cycle="D", _what="PE 窗口交易日历")
        pe_dates = datasource._sample_dates(pe_cal, args.pe_granularity, args.pe_window_years)
        meta["pe_granularity"] = args.pe_granularity
        meta["pe_window_years"] = args.pe_window_years
        meta["pe_points"] = len(pe_dates)
        pe_pct = datasource.get_pe_percentile(
            valid_codes, industry_col, industry_map, pe_dates,
            batch_size=args.pe_batch_size, max_retry=args.max_retry, stats=pe_stats,
            meta=meta, cache=cache,
            pe_granularity=args.pe_granularity, pe_window_years=args.pe_window_years)
        meta["fail_pe"] = max(pe_stats.get("failed_batches", 0), 0)
        meta["cov_pe"] = pe_stats.get("coverage")
        if pe_pct is None:
            meta["pe_desc"] = "计算失败（{}），气泡尺寸统一按 50 处理，无区分意义".format(
                pe_stats.get("status", "未知原因"))
            meta["degraded_notes"].append(
                "PE 分位不可用（{}），气泡大小不代表估值".format(pe_stats.get("status", "未知")))
        else:
            meta["pe_desc"] = (
                "PETTM 因子（{} 采样，{} 个点），行业中位数 PE 在其近 {} 年历史中的分位；"
                "分位连续（0–100）；基准日 {}，{} 个行业有值{}".format(
                    args.pe_granularity, len(pe_dates), args.pe_window_years,
                    pe_stats.get("pe_latest_date", "?"), pe_stats.get("industries", "?"),
                    "（缓存命中）" if meta.get("pe_cached") else ""))
            if pe_stats.get("failed_batches"):
                meta["degraded_notes"].append(
                    "PETTM 有 {} 个批次失败，PE 分位基于部分样本".format(pe_stats["failed_batches"]))

    # 6. 打分
    logger.info("\n── 打分 ──")
    fund_scores = scoring.calc_fundamental_scores(
        fin_df, industry_col, industry_map, args.fundamental_quarter,
        universe_size=len(valid_codes), meta=meta)
    tech_scores = scoring.calc_technical_scores(tech_df, industry_col, industry_map, meta=meta)

    df = fund_scores.merge(tech_scores, on=industry_col, how="inner")
    if len(df) == 0:
        raise config.EmptyResultError("基本面与技术面没有共同的行业，无法合并打分。")
    if pe_pct is not None:
        df = df.merge(pe_pct, on=industry_col, how="left")
    else:
        df["PE分位数"] = float("nan")

    df["成分股数"] = df["成分股数"].astype(int)
    before = len(df)
    df = df[df["成分股数"] >= args.min_stocks]
    if len(df) == 0:
        raise config.EmptyResultError(
            "--min-stocks={} 把所有 {} 个行业都筛掉了。请调小该值后重试。".format(args.min_stocks, before))
    logger.info("  %d 个行业通过筛选（成分股 >= %d，筛前 %d 个）", len(df), args.min_stocks, before)
    meta["n_industries"] = len(df)

    # 象限（数据层只存 Q1~Q4，显示名走映射表，S4）
    df["象限"] = df.apply(
        lambda r: config.assign_quadrant(r["基本面得分"], r["技术面得分"]), axis=1)

    # L6/L7：改善表门槛统一 >=0 + 单一排序规则
    improvement = scoring.build_improvement(
        df, industry_col, args.min_stocks,
        improve_tech_w=config.IMPROVE_TECH_W, improve_fund_w=config.IMPROVE_FUND_W)
    logger.info("  基本面较好 + 技术面改善: %d 个行业", len(improvement))

    # 7. 输出：HTML + Excel + PDF（D18）
    logger.info("\n── 生成报告 ──")
    meta["generated_at"] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    meta["elapsed"] = time.time() - t_start
    meta["cache_summary"] = cache.summary()

    render.create_report(df, improvement, tmp_paths["html"], args.lookback,
                         meta.get("latest_quarter", "?"), meta=meta, industry_col=industry_col)
    render.build_excel(df, improvement, pe_pct, meta, industry_col, tmp_paths["xlsx"])
    render.build_pdf(df, improvement, meta, industry_col, tmp_paths["pdf"])

    render.print_summary(df, industry_col)
    if len(improvement) > 0:
        logger.info("\n基本面较好 + 技术面转好（Top 15）")
        for _, r in improvement.head(15).iterrows():
            pe_str = ("PE分位={:.0f}%".format(r["PE分位数"])
                      if not pd_isna(r.get("PE分位数")) else "")
            logger.info("  %-18s 基本面=%+.2f  技术面: %+.2f->%+.2f (Δ%+.2f) %s",
                        str(r[industry_col]), r["基本面得分"], r["上期技术得分"],
                        r["技术面得分"], r["技术面变化"], pe_str)

    elapsed = time.time() - t_start
    logger.info("\n总耗时 %.1f 秒", elapsed)
    if meta.get("degraded_notes"):
        logger.warning("[!] 本次运行存在降级项，详见报告顶部血统条：")
        for note in meta["degraded_notes"]:
            logger.warning("    - %s", note)
    validate_artifacts(tmp_paths)
    Path(tmp_paths["manifest"]).write_text(json.dumps({"script_version": SCRIPT_VERSION,
        "as_of": industry_asof, "created_at": meta["generated_at"],
        "files": {k: Path(v).name for k, v in paths.items() if k != "manifest"}}, ensure_ascii=False, indent=2), encoding="utf-8")
    close_logging()
    for key in ("html", "xlsx", "pdf", "log", "manifest"):
        Path(tmp_paths[key]).replace(paths[key])
    tmp_dir.rmdir()
    print("输出文件：HTML={}；Excel={}；PDF={}；日志={}；清单={}".format(
        paths["html"], paths["xlsx"], paths["pdf"], paths["log"], paths["manifest"]))
    return paths["html"]


def pd_isna(v):
    try:
        return v is None or (isinstance(v, float) and __import__("math").isnan(v))
    except Exception:
        return False


def build_parser():
    p = argparse.ArgumentParser(
        description="申万行业四象限监控 v{}".format(SCRIPT_VERSION),
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="退出码：0 成功 | 2 环境 | 3 参数 | 4 数据/覆盖率 | 5 空结果 | 6 输出不可写",
    )
    p.add_argument("-o", "--output", default=None,
                   help="输出路径（默认 中文名+日期，如 '申万一级行业四象限监控_20260811.html'，"
                        "自动生成 .html/.xlsx/.pdf/.run.log 四件套）")
    p.add_argument("-l", "--lookback", type=int, default=20, help="技术面回看交易日数（默认 20）")
    p.add_argument("--min-stocks", type=int, default=3, help="行业最少成分股（默认 3）")
    p.add_argument("--fundamental-quarter", default=None,
                   help="指定财报期，YYYYMMDD 或 YYYYQn；默认自动选覆盖率最高的最近报告期")
    p.add_argument("--batch-size", type=int, default=config.DEFAULT_FIN_BATCH,
                   help="财务表每批股票数（默认 {}）".format(config.DEFAULT_FIN_BATCH))
    p.add_argument("--factor-batch-size", type=int, default=config.DEFAULT_FACTOR_BATCH,
                   help="因子接口每批股票数（默认 {}）".format(config.DEFAULT_FACTOR_BATCH))
    p.add_argument("--max-retry", type=int, default=config.DEFAULT_MAX_RETRY,
                   help="单批最大重试次数，指数退避（默认 {}）".format(config.DEFAULT_MAX_RETRY))
    p.add_argument("--min-coverage", type=float, default=config.DEFAULT_MIN_COVERAGE,
                   help="关键环节最低样本覆盖率，不达标即失败退出（默认 {}）".format(config.DEFAULT_MIN_COVERAGE))
    p.add_argument("--allow-partial", action="store_true",
                   help="覆盖率不达标时仍产出报告（报告会被标红，结论不可靠）")
    p.add_argument("--history-start", default=None,
                   help="财务表起始日期 YYYYMMDD，默认 7 年前 0101（不传会拉全历史）")
    p.add_argument("--skip-valuation", action="store_true", help="跳过 PE 分位计算（加速）")
    p.add_argument("--pe-granularity", choices=["daily", "weekly", "monthly"], default="weekly",
                   help="PE 分位历史采样粒度（默认 weekly）")
    p.add_argument("--pe-window-years", type=int, default=2, help="PE 分位回溯年数（默认 2）")
    p.add_argument("--pe-batch-size", type=int, default=100, help="PETTM 因子每批股票数（默认 100）")
    p.add_argument("--sw-level", choices=["1", "2", "3"], default="2", help="申万级别 1/2/3（默认 2）")
    p.add_argument("--no-cache", action="store_true", help="禁用缓存，强制重新取数（D16）")
    p.add_argument("-q", "--quiet", action="store_true", help="只输出警告与错误（D19）")
    p.add_argument("-v", "--verbose", action="store_true", help="输出调试细节（D19）")
    p.add_argument("--check-env", action="store_true", help="只做环境自检后退出")
    p.add_argument("--cache-dir", default=None, help="自定义缓存目录（默认 %%LOCALAPPDATA%%\\cjpy-skills\\cache\\）")
    p.add_argument("--as-of", default=None, help="固定 CJPY 交易日 YYYYMMDD（回归测试/复现用；默认自动取最新交易日）")
    return p


def main(argv=None):
    parser = build_parser()
    args = parser.parse_args(argv)

    if args.check_env:
        ok = datasource.check_environment(probe_network=not datasource._IMPORT_ERRORS)
        return config.EXIT_OK if ok else config.EXIT_ENV

    try:
        datasource.require_dependencies()
        args = validate_args(args)
        run(args)
        return config.EXIT_OK
    except config.ArgError as e:
        logger.error("[参数错误] %s", e)
        return config.EXIT_ARGS
    except config.EnvError as e:
        logger.error("[环境错误] %s", e)
        return config.EXIT_ENV
    except config.OutputError as e:
        logger.error("[输出错误] %s", e)
        return config.EXIT_IO
    except config.EmptyResultError as e:
        logger.error("[结果为空] %s", e)
        return config.EXIT_EMPTY
    except config.DataError as e:
        logger.error("[数据错误] %s", e)
        return config.EXIT_DATA


if __name__ == "__main__":
    sys.exit(main())
