# -*- coding: utf-8 -*-
"""industry-quadrant-monitor · 取数层（第三期 D2 datasource）

职责（规划文档 S1）：
  · 依赖/环境自检（[清单#1/2/3]）
  · cjpy 取数封装：指数退避重试 + 分批（[清单#4/#5/#6]、P8）
  · 财务表 / PETTM 分层缓存接入（D16，仅财务表 + PETTM）
  · 覆盖率登记（供 coverage_gate 判定）

industry_col 由调用方显式传入（S2：去掉全局可变变量）。
"""

import logging
import sys
import time
from datetime import datetime, timedelta

import numpy as np
import pandas as pd

import config
from config import (
    DEFAULT_FIN_BATCH, DEFAULT_FACTOR_BATCH, DEFAULT_MAX_RETRY,
    FIN_FIELDS, REPORT_TYPES, SW_LEVEL_MAP, SW_LEVEL_LABEL,
    EnvError, DataError,
)

logger = logging.getLogger("iqm")

# ═══════════════════════════════════════════════════════════════
# 控制台编码加固（[清单#25] / E14）：GBK 终端下 emoji 不崩溃
# ═══════════════════════════════════════════════════════════════
def init_console():
    for name in ("stdout", "stderr"):
        stream = getattr(sys, name, None)
        if stream is None or not hasattr(stream, "reconfigure"):
            continue
        try:
            enc = (getattr(stream, "encoding", "") or "").lower()
            if enc in ("", "ascii", "ansi_x3.4-1968"):
                stream.reconfigure(encoding="utf-8", errors="replace")
            else:
                stream.reconfigure(errors="replace")
        except Exception:
            pass


init_console()


# ═══════════════════════════════════════════════════════════════
# 依赖导入（先收集再统一报告，[清单#1/2/3]）
# ═══════════════════════════════════════════════════════════════
_IMPORT_ERRORS = {}
for _mod, _imp in (
    ("numpy", "import numpy as np"),
    ("pandas", "import pandas as pd"),
    ("cjpy", "import cjpy"),
    ("plotly", "import plotly, plotly.graph_objects as go; from plotly.subplots import make_subplots"),
    ("openpyxl", "import openpyxl"),
    ("reportlab", "import reportlab"),
    ("pypdf", "import pypdf"),
):
    try:
        exec(_imp)
    except Exception as _e:  # pragma: no cover
        _IMPORT_ERRORS[_mod] = _e

# 让后续模块能直接用 np/pd/cjpy（已在 guarded import 中绑定到本模块命名空间）
np = globals().get("np")
pd = globals().get("pd")
cjpy = globals().get("cjpy")

# 别名补全：check_environment 按标准包名（numpy/pandas）探测，
# 但 guarded import 绑定的是 np/pd，这里补上规范名避免误报「未安装」
globals()["numpy"] = np
globals()["pandas"] = pd


HERE = config.HERE
SKILL_ROOT = config.SKILL_ROOT
REQUIREMENTS = SKILL_ROOT / "requirements.txt"


def _install_hint():
    return (
        '  "{exe}" -m pip install -r "{req}"\n'
        "  若 cjpy 装不上（通常不在公共 PyPI），请用内部渠道的 CJPY 安装包安装。\n"
        "  想换一个解释器：先跑 python scripts/preflight.py 探测。"
    ).format(exe=sys.executable, req=REQUIREMENTS)


def require_dependencies():
    """任一依赖缺失就立刻报错，并给出可直接复制的修复命令。"""
    if not _IMPORT_ERRORS:
        return
    lines = ["缺少运行依赖，当前解释器：{}".format(sys.executable), ""]
    for mod, err in _IMPORT_ERRORS.items():
        lines.append("  [X] {:<8s} {}: {}".format(mod, type(err).__name__, err))
    lines.append("")
    lines.append("修复命令：")
    lines.append(_install_hint())
    raise EnvError("\n".join(lines))


def check_environment(probe_network=True, script_version="3.1.0"):
    """--check-env：把所有会在运行中途才炸的问题提前暴露（[清单#3]）。"""
    print("=" * 72)
    print("环境自检  |  cj-industry-quadrant-monitor v{}".format(script_version))
    print("=" * 72)
    ok = True

    print("解释器  : {}".format(sys.executable))
    print("Python  : {}".format(sys.version.split()[0]))
    if sys.version_info < (3, 8):
        print("  [X] 需要 Python >= 3.8")
        ok = False

    for mod_name in ("numpy", "pandas", "cjpy", "plotly", "openpyxl", "reportlab", "pypdf"):
        mod = globals().get(mod_name)
        if mod is None:
            print("{:<8s}: [X] 未安装 —— {}".format(
                mod_name, _IMPORT_ERRORS.get(mod_name, "")))
            ok = False
        else:
            print("{:<8s}: {}".format(mod_name, getattr(mod, "__version__", "installed")))

    # plotly 版本区间校验（[清单#26]）
    plotly = globals().get("plotly")
    if plotly is not None:
        ver = getattr(plotly, "__version__", "0")
        try:
            major = int(str(ver).split(".")[0])
            if major >= 7:
                print("  [!] plotly {} 未经回归验证，建议 pip install 'plotly>=5.18,<7'".format(ver))
            elif major < 5:
                print("  [X] plotly {} 过旧，请升级到 >=5.18".format(ver))
                ok = False
        except Exception:
            pass

    if probe_network and cjpy is not None:
        print("-" * 72)
        print("连通性  : 正在用一次轻量调用验证 token 与网络 ...")
        try:
            t0 = time.time()
            days = cjpy.get_trading_days(
                (datetime.now() - timedelta(days=15)).strftime("%Y%m%d"),
                datetime.now().strftime("%Y%m%d"),
                cycle="D",
            )
            print("  [OK] 通 ({:.1f}s)，最近交易日 {}".format(
                time.time() - t0, days[-1] if len(days) else "?"))
        except Exception as e:
            print("  [X] 失败：{}: {}".format(type(e).__name__, e))
            print("      常见原因：token 未配置/已过期（~/.cjpy/config.json）、"
                  "网络不通、服务端限流。")
            ok = False

    print("=" * 72)
    print("结论：{}".format("环境可用" if ok else "环境不可用，请先修复上面标 [X] 的项"))
    return ok


# ═══════════════════════════════════════════════════════════════
# 取数基础设施：重试 + 分批（[清单#4/#5/#6]、P8）
# ═══════════════════════════════════════════════════════════════
def chunked(seq, size):
    for i in range(0, len(seq), size):
        yield i // size, seq[i:i + size]


def call_with_retry(fn, *args, **kwargs):
    """指数退避重试（Tinysoft 后端 30s ReadTimeout 是常态，[清单#4]）。"""
    what = kwargs.pop("_what", "请求")
    max_retry = kwargs.pop("_max_retry", DEFAULT_MAX_RETRY)
    base_delay = kwargs.pop("_base_delay", 1.0)
    quiet = kwargs.pop("_quiet", False)

    last = None
    for attempt in range(1, max_retry + 1):
        try:
            return fn(*args, **kwargs)
        except Exception as e:
            last = e
            if attempt >= max_retry:
                break
            delay = base_delay * (2 ** (attempt - 1))
            if not quiet:
                logger.warning("↻ %s 第 %d/%d 次失败（%s），%.0fs 后重试",
                               what, attempt, max_retry, type(e).__name__, delay)
            time.sleep(delay)
    raise DataError("{} 连续 {} 次失败：{}: {}".format(
        what, max_retry, type(last).__name__, last))


def fetch_factor_batched(codes, dates, factors, batch_size=DEFAULT_FACTOR_BATCH,
                         max_retry=DEFAULT_MAX_RETRY, label="因子"):
    """分批 + 重试地取因子数据，返回 (df, 失败批次列表)（[清单#6]）。"""
    total_batches = (len(codes) - 1) // batch_size + 1
    logger.info("%s : %d 只 / %d 个日期，分 %d 批", label, len(codes), len(dates), total_batches)
    frames, failed = [], []
    for n, batch in chunked(codes, batch_size):
        try:
            df = call_with_retry(
                cjpy.get_factor_data,
                code=batch, date=list(dates), factors=list(factors),
                _what="{} 批次 {}/{}".format(label, n + 1, total_batches),
                _max_retry=max_retry,
            )
            frames.append(df)
        except DataError as e:
            failed.append({"batch": n + 1, "size": len(batch), "error": str(e)})
            logger.error("[X] %s 批次 %d/%d 最终失败", label, n + 1, total_batches)
    if not frames:
        raise DataError("{}：全部 {} 个批次都失败，无任何数据".format(label, total_batches))
    out = pd.concat(frames, ignore_index=True)
    logger.info("%s : 取回 %d 行，失败 %d/%d 批", label, len(out), len(failed), total_batches)
    return out, failed


# ═══════════════════════════════════════════════════════════════
# 数据获取
# ═══════════════════════════════════════════════════════════════
def get_a_stocks():
    stocks = call_with_retry(cjpy.get_stocks, _what="全市场股票列表")
    # SZ/SH 前缀过滤会同时排除北交所（BJ 前缀）
    return [s for s in stocks if s.startswith("SZ") or s.startswith("SH")]


def get_sw_industry(codes, industry_col, batch_size=DEFAULT_FACTOR_BATCH,
                    max_retry=DEFAULT_MAX_RETRY, as_of=None):
    """获取申万行业分类（级别由 industry_col 决定）。

    注：as_of 默认「今天」，即今日快照解释历史区间走势，存在前视偏差
    （规划文档 N4 / D15），第三期暂不处理。
    """
    as_of = as_of or datetime.now().strftime("%Y%m%d")
    logger.info("[1/6] 行业分类（%s，截面 %s）", industry_col, as_of)
    df, failed = fetch_factor_batched(
        codes, [as_of], [industry_col],
        batch_size=batch_size, max_retry=max_retry, label="行业分类",
    )
    missing = {"代码", "名称", industry_col} - set(df.columns)
    if missing:
        raise DataError("行业分类返回缺少字段 {}，实际字段：{}".format(
            sorted(missing), list(df.columns)))
    return df[["代码", "名称", industry_col]].copy(), failed


def get_financial_data(codes, batch_size=DEFAULT_FIN_BATCH, start=None,
                      max_retry=DEFAULT_MAX_RETRY, cache=None):
    """取合并利润表（N1：传 start 裁剪历史，避免拉回 1992 年至今全量）。

    缓存（D16）：同一 (代码集, start) 复跑直接命中，省掉最耗时的 7 年利润表拉取。
    """
    codes_key = tuple(sorted(codes))
    if cache is not None:
        cached = cache.get_financial(codes_key, start)
        if cached is not None:
            return cached, []

    total_batches = (len(codes) - 1) // batch_size + 1
    logger.info("[2/6] 财务数据：%d 只 / %d 批（%d 只每批，起始 %s）",
                len(codes), total_batches, batch_size, start or "不限（拉全历史）")

    frames, failed = [], []
    for n, batch in chunked(codes, batch_size):
        kw = {"fields": FIN_FIELDS}
        if start:
            kw["start"] = start
        try:
            df = call_with_retry(
                cjpy.get_table_data, batch, "合并利润表",
                _what="财务批次 {}/{}".format(n + 1, total_batches),
                _max_retry=max_retry, **kw
            )
            frames.append(df)
            logger.info("  批次 %d/%d  取回 %d 行", n + 1, total_batches, len(df))
        except DataError as e:
            failed.append({"batch": n + 1, "size": len(batch), "error": str(e)})
            logger.error("  批次 %d/%d  [X] 最终失败", n + 1, total_batches)

    if not frames:
        raise DataError("财务数据：全部 {} 个批次都失败".format(total_batches))
    out = pd.concat(frames, ignore_index=True)
    logger.info("  合计 %d 行，失败 %d/%d 批", len(out), len(failed), total_batches)
    if cache is not None and not failed:
        cache.put_financial(codes_key, start, out, meta={"failed_batches": 0})
    return out, failed


def get_technical_data(codes, lookback_days=20, batch_size=DEFAULT_FACTOR_BATCH,
                      max_retry=DEFAULT_MAX_RETRY, as_of=None):
    """三时间截面的技术面数据（用于检测动量变化）。"""
    logger.info("[3/6] 技术面：%d 日回看，三截面", lookback_days)

    today_str = as_of or datetime.now().strftime("%Y%m%d")
    start = (datetime.strptime(today_str, "%Y%m%d") - timedelta(days=lookback_days * 5 + 30)).strftime("%Y%m%d")
    trading_days = call_with_retry(
        cjpy.get_trading_days, start, today_str, cycle="D", _what="交易日历")

    need = lookback_days * 2 + 1
    if len(trading_days) < need:
        raise DataError(
            "交易日不足：需要 {} 个（lookback={}），区间 {}~{} 只有 {} 个。"
            "请调小 --lookback。".format(need, lookback_days, start, today_str, len(trading_days)))

    t2 = trading_days[-1]
    t1 = trading_days[-(lookback_days + 1)]
    t0 = trading_days[-(lookback_days * 2 + 1)]

    if len({t0, t1, t2}) != 3:
        raise DataError("三个时间截面出现重合（T0={} T1={} T2={}），"
                        "动量将恒为 0，拒绝继续。".format(t0, t1, t2))
    logger.info("  截面: T0=%s  ->  T1=%s  ->  T2=%s", t0, t1, t2)

    df, failed = fetch_factor_batched(
        codes, [t0, t1, t2], ["收盘价", "换手率"],
        batch_size=batch_size, max_retry=max_retry, label="技术面因子",
    )
    return df, t0, t1, t2, failed


def _sample_dates(cal, granularity, window_years):
    """从交易日历抽取 PE 历史采样点（D4）。

    daily  : 全部交易日（最细但全量调用多）
    weekly : 约每周 1 点（~100 点/2年，默认，平衡细度与耗时）
    monthly: 每月最后 1 点（~26 点/2年，最快）
    """
    cal = sorted(cal)
    if granularity == "daily":
        return cal
    if granularity == "monthly":
        from collections import defaultdict
        by_m = defaultdict(list)
        for d in cal:
            by_m[d[:6]].append(d)
        return sorted(v[-1] for v in by_m.values())
    step = max(1, len(cal) // max(1, int(52 * window_years)))
    sampled = cal[::step]
    return sampled if sampled and sampled[-1] == cal[-1] else sampled + [cal[-1]]


def get_pe_percentile(codes, industry_col, industry_map, window_dates,
                      batch_size=100, max_retry=DEFAULT_MAX_RETRY,
                      stats=None, meta=None, cache=None,
                      pe_granularity="weekly", pe_window_years=2):
    """PETTM 因子算各行业 PE 分位数（D4），带缓存（D16，用户要求的 PE_TTM 缓存）。

    用现成 PETTM 日频因子替代 v2 手算的 5 个年报点 TTM PE：
      - 分位连续（不再卡 {0,20,40,60,80} 五档，[清单#13]）；
      - 「当前」PE 用最新交易日，不再滞后 7 个月；
      - 不再请求 2.6 万行市值表（消除 v2 致命失败点，[清单#6]）。
    缓存命中时直接返回历史计算结果，PETTM 全量序列不再重取。
    pe_granularity / pe_window_years 显式传入，作为缓存 key 的一部分（避免依赖
    尚未写入 meta 的字段导致 key 错配）。
    """
    stats = stats if stats is not None else {}
    meta = meta if meta is not None else {}
    codes_key = tuple(sorted(codes))

    if cache is not None:
        cached = cache.get_pettm(codes_key, pe_granularity, pe_window_years, window_dates, industry_col)
        if cached is not None:
            stats["status"] = "正常(缓存命中)"
            cm = getattr(cache, "last_meta", {}).get("pettm", {})
            stats["failed_batches"] = cm.get("failed_batches", 0)
            stats["coverage"] = cm.get("coverage")
            stats["pe_latest_date"] = cm.get("pe_latest_date")
            stats["industries"] = cm.get("industries")
            meta["pe_cached"] = True
            return cached

    total_batches = (len(codes) - 1) // batch_size + 1
    logger.info("[4/6] 估值分位（PETTM 因子，%d 个采样点，%d 批）",
                len(window_dates), total_batches)

    frames, failed = [], []
    for n, batch in chunked(codes, batch_size):
        try:
            df = call_with_retry(
                cjpy.get_factor_data, code=batch,
                date=list(window_dates), factors=["PETTM"],
                _what="PETTM 批次 {}/{}".format(n + 1, total_batches),
                _max_retry=max_retry)
            frames.append(df)
        except DataError as e:
            failed.append({"batch": n + 1, "size": len(batch), "error": str(e)})
            logger.error("[X] PETTM 批次 %d/%d 最终失败", n + 1, total_batches)
    if not frames:
        logger.warning("[!] PETTM 全部批次失败")
        stats["status"] = "PETTM 获取失败"
        stats["failed_batches"] = -1
        return None
    pe = pd.concat(frames, ignore_index=True)
    pe["PETTM"] = pd.to_numeric(pe["PETTM"], errors="coerce")

    got = pe["代码"].nunique() if "代码" in pe.columns else 0
    stats["coverage"] = got / len(codes) if codes else 0.0
    stats["failed_batches"] = len(failed)
    if failed:
        logger.warning("[!] PETTM 有 %d 个批次失败，覆盖率 %.1f%%",
                       len(failed), stats["coverage"] * 100)

    pe = pe[(pe["PETTM"] > config.PE_FLOOR) & (pe["PETTM"] < config.PE_CEIL)]
    pe = pe.dropna(subset=["PETTM"])
    if len(pe) == 0:
        logger.warning("[!] PETTM 有效数据为空")
        stats["status"] = "PETTM 为空"
        return None

    pe = pe.merge(industry_map[["代码", industry_col]], on="代码", how="inner")
    ind_ts = pe.groupby([industry_col, "截止日"])["PETTM"].median().reset_index()
    latest = ind_ts["截止日"].max()

    rows = []
    for ind, g in ind_ts.groupby(industry_col):
        hist = g["PETTM"].dropna().sort_values()
        if len(hist) < config.PE_MIN_POINTS:
            continue
        cur = g.loc[g["截止日"] == latest, "PETTM"]
        cur = float(cur.iloc[0]) if len(cur) else np.nan
        if pd.isna(cur):
            continue
        pct = float((hist < cur).mean() * 100)
        rows.append({
            industry_col: ind,
            "PE分位数": round(pct, 1),
            "PE最新": round(cur, 1),
            "PE窗口低": round(float(hist.min()), 1),
            "PE窗口高": round(float(hist.max()), 1),
        })
    if not rows:
        logger.warning("[!] 没有行业能算出 PE 分位数")
        stats["status"] = "无行业可算"
        return None
    df = pd.DataFrame(rows)
    stats["status"] = "正常" if not failed else "部分批次失败"
    stats["pe_latest_date"] = str(latest)
    stats["industries"] = len(df)
    logger.info("%d 个行业有 PE 分位数（PETTM 基准日 %s）", len(df), latest)

    if cache is not None and not failed:
        cache.put_pettm(codes_key, pe_granularity, pe_window_years, window_dates, df, industry_col,
                        meta={"failed_batches": 0, "coverage": stats.get("coverage"),
                              "pe_latest_date": stats.get("pe_latest_date"), "industries": stats.get("industries")})
    return df


def load_exclusion_flags(codes, industry_col, as_of, batch_size=DEFAULT_FACTOR_BATCH,
                         max_retry=DEFAULT_MAX_RETRY):
    """样本过滤（D14）：用「是否ST」「是否交易」因子剔除 ST/*ST 与停牌/退市。

    v2 完全没做停牌/退市过滤，ST 过滤又是永不生效的死代码（[清单#14/#15/#16]）。
    这里改用因子口径，比字符串匹配准，且对应当前真实状态。
    """
    logger.info("[0/6] 样本过滤（ST / 停牌退市，因子口径，截面 %s）", as_of)
    df, failed = fetch_factor_batched(
        codes, [as_of], ["是否ST", "是否交易"],
        batch_size=batch_size, max_retry=max_retry, label="过滤因子",
    )
    if "是否ST" not in df.columns or "是否交易" not in df.columns:
        raise DataError("过滤因子返回缺少字段，实际字段：{}".format(list(df.columns)))
    df["是否ST"] = pd.to_numeric(df["是否ST"], errors="coerce").fillna(0)
    df["是否交易"] = pd.to_numeric(df["是否交易"], errors="coerce").fillna(0)
    df["排除"] = (df["是否ST"] != 0) | (df["是否交易"] == 0)
    n_st = int((df["是否ST"] != 0).sum())
    n_susp = int((df["是否交易"] == 0).sum())
    excluded = set(df.loc[df["排除"], "代码"].astype(str))
    logger.info("  过滤因子覆盖率 %d/%d；剔除 ST=%d 只、停牌/退市=%d 只，共 %d 只",
                len(df), len(codes), n_st, n_susp, len(excluded))
    return excluded, {"st": n_st, "suspended": n_susp, "total": len(excluded)}
