# -*- coding: utf-8 -*-
"""industry-quadrant-monitor · 打分层（第三期 D2 scoring，纯函数、可单测）

职责（规划文档 S1）：winsorize / zscore / 基本面打分 / 技术面打分 / 象限 / 改善表。
全部为纯函数，只在进程内对 DataFrame 做变换，不碰网络、不读全局变量（S2）。
industry_col 由调用方显式传入，便于在同一进程跑多级别（SW1/SW2 对比）。
"""

import logging

import numpy as np
import pandas as pd

import config
from config import (
    WINSOR_LOWER, WINSOR_UPPER, PCT_CLIP, FUND_W, TECH_W,
    IMPROVE_TECH_W, IMPROVE_FUND_W, REPORT_TYPES,
    DataError, EmptyResultError,
)

logger = logging.getLogger("iqm")


# ═══════════════════════════════════════════════════════════════
# 基础变换（与历史版本数学一致）
# ═══════════════════════════════════════════════════════════════
def winsorize(series, lower=WINSOR_LOWER, upper=WINSOR_UPPER):
    lo, hi = series.quantile(lower), series.quantile(upper)
    return series.clip(lo, hi)


def zscore(series):
    mu, sd = series.mean(), series.std()
    if sd == 0 or np.isnan(sd):
        return pd.Series(0, index=series.index)
    return (series - mu) / sd


def safe_pct_change(curr, prev):
    curr = pd.to_numeric(curr, errors="coerce")
    prev = pd.to_numeric(prev, errors="coerce")
    denom = prev.abs().replace(0, np.nan)
    return ((curr - prev) / denom * 100).clip(*PCT_CLIP)


# ═══════════════════════════════════════════════════════════════
# 基本面打分
# ═══════════════════════════════════════════════════════════════
def calc_fundamental_scores(fin_df, industry_col, industry_map,
                            latest_quarter=None, universe_size=None, meta=None):
    """基本面打分（TTM 同比，第三期起）。

    口径：从累计利润表还原滚动四季度
        TTM(D) = C(D) + C(去年Dec31) - C(去年同期同季)
    再做 TTM 同比 = TTM(D) / TTM(D-1年) - 1。需 5 个报告期齐全：
        D, D-1y, D-2y, 去年年报, 前年年报。
    两处工程改动：
      1. 覆盖率分母改为 universe_size（请求的股票数），修 [清单#8] 自夸满分。
      2. TTM 还原取代原累计同比（用户要求全换 TTM）。
    打分数学（Winsorize / z-score / 0.5/0.5 权重 / 行业内中位数聚合）不变。
    industry_col 显式传入（S2）。
    """
    meta = meta if meta is not None else {}
    logger.info("[5/6] 基本面打分")
    fin = fin_df.copy()
    fin["截止日"] = fin["截止日"].astype(str)

    seen_types = sorted(set(fin["报告类型"].astype(str).unique()))
    fin = fin[fin["报告类型"].isin(REPORT_TYPES)]
    if len(fin) == 0:
        raise DataError(
            "按报告类型 {} 过滤后没有任何数据。服务端实际返回的报告类型是：{}。"
            "接口口径可能已变更，请更新 REPORT_TYPES。".format(REPORT_TYPES, seen_types[:12]))

    fetched = fin["CODE"].nunique()
    total = int(universe_size) if universe_size else fetched
    meta["fin_universe"] = total
    meta["fin_fetched"] = fetched

    available = set(fin["截止日"].astype(str).unique())

    if latest_quarter is None:
        candidates = []
        for q in sorted(available, reverse=True):
            curr_cnt = fin.loc[fin["截止日"] == q, "CODE"].nunique()
            cov = curr_cnt / total if total > 0 else 0
            try:
                yoy_q = "{}{}".format(int(q[:4]) - 1, q[4:])
                yoy_cnt = fin.loc[fin["截止日"] == yoy_q, "CODE"].nunique()
                yoy_cov = yoy_cnt / total if total > 0 else 0
            except (ValueError, IndexError):
                yoy_cov = 0
            # TTM 同比还需：去年同期同季、前年同期、去年年报、前年年报
            y = int(q[:4]); md = q[4:]
            need = {yoy_q, "{:04d}{}".format(y - 2, md),
                    "{:04d}1231".format(y - 1), "{:04d}1231".format(y - 2)}
            ttm_ok = need.issubset(available)
            candidates.append((q, cov, yoy_cov, curr_cnt, ttm_ok))

        chosen = None
        for q, cov, yoy_cov, _, ttm_ok in candidates:
            if ttm_ok and cov > 0.7 and yoy_cov > 0.6:
                chosen = q
                break
        if chosen is None:
            ok_cands = [c for c in candidates if c[4]]
            ok_cands.sort(key=lambda x: (x[1] + x[2]), reverse=True)
            chosen = (ok_cands[0][0] if ok_cands else candidates[0][0])

        latest_quarter = chosen
        cov_info = next((c for c in candidates if c[0] == chosen), None)
        if cov_info:
            logger.info("  自动选定报告期: %s (当期覆盖 %.0f%% / YoY 覆盖 %.0f%%，分母=%d 只)",
                        latest_quarter, cov_info[1] * 100, cov_info[2] * 100, total)
            meta["quarter_coverage"] = cov_info[1]
            meta["quarter_yoy_coverage"] = cov_info[2]
        meta["quarter_source"] = "自动选定"
    else:
        latest_quarter = str(latest_quarter)
        if latest_quarter not in available:
            raise DataError(
                "指定的报告期 {} 在数据中不存在。可用报告期（最近 12 个）：{}。"
                "提示：若目标报告期早于 --history-start，请把起始日期提前。".format(
                    latest_quarter, sorted(available, reverse=True)[:12]))
        logger.info("  指定报告期: %s", latest_quarter)
        cnt = fin.loc[fin["截止日"] == latest_quarter, "CODE"].nunique()
        meta["quarter_coverage"] = cnt / total if total > 0 else 0
        meta["quarter_source"] = "用户指定"

    # ── TTM 同比：从累计利润表还原滚动四季度（用户要求全换 TTM）──
    # TTM(D) = C(D) + C(去年Dec31) - C(去年同期同季)
    # 同比基准 = TTM(D-1年)，故需 5 个报告期：D, D-1y, D-2y, 去年年报, 前年年报
    y = int(latest_quarter[:4]); md = latest_quarter[4:]
    nd = {
        "D":  latest_quarter,
        "D1": "{:04d}{}".format(y - 1, md),
        "D2": "{:04d}{}".format(y - 2, md),
        "A1": "{:04d}1231".format(y - 1),
        "A2": "{:04d}1231".format(y - 2),
    }
    meta["latest_quarter"] = latest_quarter
    meta["yoy_quarter"] = nd["D1"]
    meta["fund_method"] = "TTM同比"
    meta["ttm_anchor"] = nd["D"]
    meta["ttm_basis"] = nd["D1"]

    missing = [k for k, v in nd.items() if v not in available]
    if missing:
        raise DataError(
            "TTM 同比需要报告期 {}，但数据中缺失 {}。\n"
            "  可用报告期（最近 16 个）：{}\n"
            "  处理办法：把 --history-start 提前到 {} 之前（需覆盖前年年报 {}）。".format(
                nd, missing, sorted(available, reverse=True)[:16], nd["A2"][:4], nd["A2"]))

    # 透视出每只股票在各报告期的累计值（营收 / 归母净利润）
    rev = fin.pivot_table(index="CODE", columns="截止日",
                          values="营业总收入", aggfunc="first")
    prof = fin.pivot_table(index="CODE", columns="截止日",
                           values="归属于母公司所有者净利润", aggfunc="first")
    rev = rev.apply(pd.to_numeric, errors="coerce")
    prof = prof.apply(pd.to_numeric, errors="coerce")

    def _ttm(cum, d, a, dp):
        """TTM = 当年累计 + 去年年报 - 去年同期同季累计。三者任一缺失/NaN 返回 None。"""
        x = cum.get(d); xa = cum.get(a); xp = cum.get(dp)
        if x is None or xa is None or xp is None:
            return None
        if pd.isna(x) or pd.isna(xa) or pd.isna(xp):
            return None
        return float(x) + float(xa) - float(xp)

    recs = []
    for code in rev.index:
        rc = rev.loc[code]; pc = prof.loc[code]
        trc = _ttm(rc, nd["D"], nd["A1"], nd["D1"])   # 营收 TTM 当期
        trp = _ttm(rc, nd["D1"], nd["A2"], nd["D2"])  # 营收 TTM 同比基准
        tpc = _ttm(pc, nd["D"], nd["A1"], nd["D1"])   # 净利润 TTM 当期
        tpp = _ttm(pc, nd["D1"], nd["A2"], nd["D2"])  # 净利润 TTM 同比基准
        if None in (trc, trp, tpc, tpp):
            continue
        recs.append((code, trc, trp, tpc, tpp))

    if not recs:
        raise EmptyResultError(
            "TTM 样本为 0：无法为报告期 {} 还原任何滚动四季度数据（需 {} 齐全）。".format(
                latest_quarter, nd))
    merged = pd.DataFrame(
        recs, columns=["CODE", "营收TTM", "营收TTM_prev", "净利润TTM", "净利润TTM_prev"])
    logger.info("  TTM 有效样本: %d 只（锚点 %s / 同比基准 TTM@%s）",
                len(merged), nd["D"], nd["D1"])
    meta["yoy_matched"] = len(merged)

    merged["净利润增速"] = safe_pct_change(merged["净利润TTM"], merged["净利润TTM_prev"])
    merged["营收增速"] = safe_pct_change(merged["营收TTM"], merged["营收TTM_prev"])
    merged = merged.merge(industry_map, left_on="CODE", right_on="代码", how="inner")
    # D14：ST/停牌退市已在宇宙层面用因子剔除，此处不再做字符串匹配
    merged = merged.dropna(subset=["净利润增速", "营收增速"])

    if len(merged) == 0:
        raise EmptyResultError(
            "基本面样本为 0：TTM 同比无法配出任何有效增速（报告期 {}）。".format(latest_quarter))
    meta["fund_sample"] = len(merged)

    merged["净利润增速_w"] = winsorize(merged["净利润增速"])
    merged["营收增速_w"] = winsorize(merged["营收增速"])
    merged["净利润增速_z"] = zscore(merged["净利润增速_w"])
    merged["营收增速_z"] = zscore(merged["营收增速_w"])

    ind = (
        merged.groupby(industry_col)
        .agg(
            净利润增速中位数=("净利润增速_w", "median"),
            营收增速中位数=("营收增速_w", "median"),
            净利润增速_z=("净利润增速_z", "median"),
            营收增速_z=("营收增速_z", "median"),
            成分股数=("CODE", "count"),
        )
        .reset_index()
    )
    ind["基本面得分"] = ind["净利润增速_z"] * FUND_W + ind["营收增速_z"] * FUND_W
    logger.info("  基本面样本 %d 只，覆盖 %d 个行业", len(merged), len(ind))
    return ind


# ═══════════════════════════════════════════════════════════════
# 技术面打分（双口径，D11）
# ═══════════════════════════════════════════════════════════════
def calc_technical_scores(tech_df, industry_col, industry_map, meta=None):
    """三截面技术面：T0→T1 和 T1→T2 两段动量，检测变化（D11 双口径）。

    相对(z 相减) 用于象限/得分比较；绝对(原始价格动量中位差) 更直观。
    """
    meta = meta if meta is not None else {}
    logger.info("  计算技术面得分（含动量变化，双口径）")

    df = tech_df.copy()
    dates = sorted(df["截止日"].unique())
    if len(dates) != 3:
        raise DataError("技术面需要 3 个时间截面，实际拿到 {} 个：{}".format(len(dates), dates))

    t0, t1, t2 = dates[0], dates[1], dates[2]
    sample_counts = {}

    def calc_window(df_a, df_b, industry_col):
        """计算 df_a → df_b 期间的技术面动量"""
        a = df_a[["代码", "收盘价", "换手率"]].copy()
        b = df_b[["代码", "收盘价", "换手率"]].copy()
        m = b.merge(a, on="代码", suffixes=("_b", "_a"), how="inner")
        m["价格动量"] = (m["收盘价_b"] / m["收盘价_a"] - 1) * 100
        m["量能变化"] = m["换手率_b"] / m["换手率_a"] - 1
        m = m.merge(industry_map, on="代码", how="inner")
        # D14：ST/停牌退市已在宇宙层面用因子剔除
        m = m.dropna(subset=["价格动量", "量能变化"])
        m = m[np.isfinite(m["价格动量"]) & np.isfinite(m["量能变化"])]
        m["价格动量_w"] = winsorize(m["价格动量"])
        m["量能变化_w"] = winsorize(m["量能变化"])
        m["价格动量_z"] = zscore(m["价格动量_w"])
        m["量能变化_z"] = zscore(m["量能变化_w"])

        ind = (
            m.groupby(industry_col)
            .agg(
                价格动量中位数=("价格动量_w", "median"),
                量能变化中位数=("量能变化_w", "median"),
                价格动量_z=("价格动量_z", "median"),
                量能变化_z=("量能变化_z", "median"),
            )
            .reset_index()
        )
        ind["技术面得分"] = ind["价格动量_z"] * TECH_W + ind["量能变化_z"] * TECH_W
        return ind, len(m)

    df_t0 = df[df["截止日"] == t0]
    df_t1 = df[df["截止日"] == t1]
    df_t2 = df[df["截止日"] == t2]

    prev_scores, n_prev = calc_window(df_t0, df_t1, industry_col)
    prev_scores = prev_scores.rename(columns={
        "价格动量中位数": "上期价格动量",
        "量能变化中位数": "上期量能变化",
        "技术面得分": "上期技术得分",
    })
    curr_scores, n_curr = calc_window(df_t1, df_t2, industry_col)
    sample_counts["T0→T1"] = n_prev
    sample_counts["T1→T2"] = n_curr

    combined = curr_scores.merge(prev_scores, on=industry_col, how="inner")
    combined["技术面变化"] = combined["技术面得分"] - combined["上期技术得分"]
    # D11 双口径：绝对 = 原始价格动量中位差（不经 z 标准化），更直观
    combined["技术面变化(绝对)"] = combined["价格动量中位数"] - combined["上期价格动量"]
    combined["量能变化(绝对)"] = combined["量能变化中位数"] - combined["上期量能变化"]
    # L6：象限门槛 f>=0&t>=0 与改善表门槛统一为 >=0
    combined["技术面改善"] = combined["技术面变化"] >= 0

    if len(combined) == 0:
        raise EmptyResultError("技术面结果为空：两个窗口没有共同的行业。")

    meta["tech_sample_prev"] = n_prev
    meta["tech_sample_curr"] = n_curr
    logger.info("  技术面样本 T0→T1=%d 只 / T1→T2=%d 只，覆盖 %d 个行业",
                n_prev, n_curr, len(combined))
    return combined


# ═══════════════════════════════════════════════════════════════
# 改善表（L6/L7：统一门槛 + 单一排序规则）
# ═══════════════════════════════════════════════════════════════
def build_improvement(df, industry_col, min_stocks, improve_tech_w=IMPROVE_TECH_W,
                      improve_fund_w=IMPROVE_FUND_W):
    """筛选「基本面较好 + 技术面改善」行业，并用单一确定排序规则排序（L6/L7）。

    门槛：基本面得分 >= 0 且 技术面改善（技术面变化 >= 0），与象限口径统一。
    排序分 = 技术面相对变化 × improve_tech_w + 基本面得分 × improve_fund_w，降序。
    该规则在报告内与控制台摘要一致，消除 run() 与 build_improvement_html 两次不同排序。
    """
    before = len(df)
    df = df[df["成分股数"] >= min_stocks]
    if len(df) == 0:
        raise EmptyResultError(
            "--min-stocks={} 把所有 {} 个行业都筛掉了。请调小该值后重试。".format(
                min_stocks, before))
    improvement = df[(df["基本面得分"] >= 0) & (df["技术面改善"])].copy()
    improvement["排序分"] = (improvement["技术面变化"] * improve_tech_w
                            + improvement["基本面得分"] * improve_fund_w)
    improvement = improvement.sort_values("排序分", ascending=False)
    return improvement
