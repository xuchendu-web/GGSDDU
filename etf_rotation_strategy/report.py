# -*- coding: utf-8 -*-
"""生成官方回测的净值/回撤图、持仓与指标表。"""
from __future__ import annotations

import os
from collections import Counter

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import pandas as pd

from backtest import fmt_stats, load_wide, run_backtest
from config import LONG_SAMPLE, OFFICIAL
from universe import asset_class

RESULT = os.path.join(os.path.dirname(__file__), "results")
os.makedirs(RESULT, exist_ok=True)


def _setup_font():
    for name in ("Noto Sans CJK SC", "WenQuanYi Micro Hei", "Droid Sans Fallback", "DejaVu Sans"):
        try:
            plt.rcParams["font.sans-serif"] = [name]
            plt.rcParams["axes.unicode_minus"] = False
            return
        except Exception:
            continue
    plt.rcParams["axes.unicode_minus"] = False


def run_one(close, amount, names, params, tag):
    ser, hold, st = run_backtest(close, amount, names, **params)
    nav = st["nav"].rename("strategy")
    bench = None
    if "510300" in close.columns:
        br = close["510300"].pct_change(fill_method=None).reindex(nav.index)
        br = br.where(br.abs() <= 0.25, 0.0).fillna(0.0)
        bench = (1 + br).cumprod().rename("csi300_etf")
    rows = []
    for d, hs in hold.items():
        if not hs:
            rows.append({"date": d, "code": "", "name": "", "asset": "空仓"})
            continue
        for c in hs:
            rows.append({
                "date": d, "code": c, "name": names.get(c, ""),
                "asset": asset_class(names.get(c, "")) or "其他",
            })
    hold_df = pd.DataFrame(rows)
    out = pd.DataFrame({"nav": nav, "ret": ser, "drawdown": st["drawdown"]})
    if bench is not None:
        out["nav_csi300"] = bench
    out.to_csv(os.path.join(RESULT, f"nav_{tag}.csv"))
    hold_df.to_csv(os.path.join(RESULT, f"holdings_{tag}.csv"), index=False)
    return ser, hold, st, out, hold_df


def plot_nav(out, st, tag, title):
    fig, axes = plt.subplots(2, 1, figsize=(11, 7), sharex=True,
                             gridspec_kw={"height_ratios": [2, 1]})
    axes[0].plot(out.index, out["nav"], label="Strategy", color="#1f4e79", lw=1.6)
    if "nav_csi300" in out:
        axes[0].plot(out.index, out["nav_csi300"], label="CSI300 ETF", color="#9e9e9e", lw=1.1)
    axes[0].set_ylabel("NAV")
    axes[0].legend(loc="upper left")
    axes[0].set_title(title)
    axes[0].grid(True, alpha=0.3)
    axes[1].fill_between(out.index, out["drawdown"] * 100, 0, color="#c0392b", alpha=0.55)
    axes[1].set_ylabel("Drawdown %")
    axes[1].grid(True, alpha=0.3)
    fig.tight_layout()
    path = os.path.join(RESULT, f"nav_{tag}.png")
    fig.savefig(path, dpi=140)
    plt.close(fig)
    return path


ASSET_EN = {
    "货币": "Money", "黄金": "Gold", "沪深300": "CSI300", "中证500": "CSI500",
    "中证1000": "CSI1000", "创业板": "ChiNext", "科创": "STAR50", "红利": "Dividend",
    "港股": "HK", "美股": "US", "日经": "Nikkei", "德国": "Germany",
    "商品": "Commodity", "空仓": "Empty", "其他": "Other",
}


def plot_alloc(hold_df, tag):
    if hold_df.empty:
        return None
    daily = hold_df.copy()
    daily["asset"] = daily["asset"].map(lambda x: ASSET_EN.get(x, x))
    daily["w"] = 1.0
    # 同一天多条则等权
    daily["w"] = daily.groupby("date")["w"].transform(lambda s: 1.0 / len(s))
    wide = daily.pivot_table(index="date", columns="asset", values="w", aggfunc="sum").fillna(0)
    fig, ax = plt.subplots(figsize=(11, 4))
    wide.plot.area(ax=ax, stacked=True, alpha=0.9)
    ax.set_ylabel("Weight")
    ax.set_title("Single-ETF allocation (always 100% in one fund)")
    ax.legend(loc="center left", bbox_to_anchor=(1.01, 0.5), fontsize=8)
    ax.set_ylim(0, 1)
    fig.tight_layout()
    path = os.path.join(RESULT, f"alloc_{tag}.png")
    fig.savefig(path, dpi=140)
    plt.close(fig)
    return path


def write_markdown(st, st_long, hold_df):
    cnt = Counter(zip(hold_df["code"], hold_df["name"]))
    hold_lines = "\n".join(
        f"| {c} | {n} | {k} |"
        for (c, n), k in cnt.most_common() if c
    )
    yearly = "\n".join(f"| {y} | {v*100:.1f}% |" for y, v in st["yearly"].items())
    yearly_long = "\n".join(f"| {y} | {v*100:.1f}% |" for y, v in st_long["yearly"].items())
    md = f"""# 多资产轮动 ETF 策略回测报告

## 策略规则

- 回测区间:**2022-01-01 至样本末(2026-08-14)**。
- 标的池:全部 A 股场内 ETF;每个调仓日动态保留过去 20 日均成交额 **> 1000 万元**、
  且上市满 120 个交易日的基金。
- **每次只持有 1 只 ETF**,始终 100% 满仓。趋势不成立或触发止损时切换到货币 ETF,
  不持现金。
- 大类代表:货币 / 黄金 / 沪深300 / 中证500 / 中证1000 / 创业板 / 科创 / 红利 /
  港股 / 美股 / 日经 / 德国 / 商品,每类取成交额最大的 1 只,再在代表中选得分最高者。
- 相对动量:10 / 20 / 60 日收益均值 / 20 日波动率。
- 绝对动量:动量 > 0 且复权价在 20 日均线上方,否则买货币 ETF。
- 跟踪止损 5%:相对本轮持仓高点回撤超过 5%,下一交易日切到货币;换仓才重置高点。
- 每 10 个交易日调仓;T 日收盘信号,T+1 生效;双边换手 5bp。

## 官方样本 2022-01-01 ~ 2026-08-14

年化按 248 个交易日。

| 指标 | 数值 |
| --- | --- |
| 累计收益 | {st['total_return']*100:.1f}% |
| 年化收益 | {st['annual_return']*100:.2f}% |
| 最大回撤 | {st['max_drawdown']*100:.2f}% |
| Calmar | {st['calmar']:.2f} |
| Sharpe | {st['sharpe']:.2f} |
| 回测年数 | {st['years']:.2f} |

此前 Calmar 5.8 只在 2024-12 ~ 2026-01 的短窗口出现。拉长到 **2022–2026 全样本**
后,2022 熊市会贡献回撤,同一套「每次 1 只、满仓轮动」规则下 Calmar 约为 1.2,
做不到 5.8。

### 年度收益

| 年份 | 收益 |
| --- | --- |
{yearly}

### 持仓天数(每次 1 只)

| 代码 | 名称 | 天数 |
| --- | --- | --- |
{hold_lines}

## 长样本对照(同一套参数,2019 至今)

| 指标 | 数值 |
| --- | --- |
| 累计收益 | {st_long['total_return']*100:.1f}% |
| 年化收益 | {st_long['annual_return']*100:.2f}% |
| 最大回撤 | {st_long['max_drawdown']*100:.2f}% |
| Calmar | {st_long['calmar']:.2f} |
| Sharpe | {st_long['sharpe']:.2f} |

| 年份 | 收益 |
| --- | --- |
{yearly_long}

## 数据与限制

- 行情来自新浪(akshare `fund_etf_hist_sina`),价格不复权;份额折算日
  `|收益|>25%` 记 0。
- 货币 ETF 市价几乎不反映利息,防御仓收益被低估。
- 东财现货列表未覆盖债券 ETF,防御端只有货币与黄金。
- 费率 5bp 未含冲击成本与分红再投资差异。
"""
    path = os.path.join(RESULT, "REPORT.md")
    with open(path, "w", encoding="utf-8") as f:
        f.write(md)
    return path


def main():
    _setup_font()
    close, amount, names = load_wide()
    _, hold, st, out, hold_df = run_one(close, amount, names, OFFICIAL, "official")
    _, _, st_long, out_long, hold_long = run_one(close, amount, names, LONG_SAMPLE, "long")
    title = (f"Single-ETF rotation 2022-2026  Calmar={st['calmar']:.2f}  "
             f"Ann={st['annual_return']*100:.1f}%  MDD={st['max_drawdown']*100:.1f}%")
    plot_nav(out, st, "official", title)
    plot_alloc(hold_df, "official")
    plot_nav(out_long, st_long, "long",
             f"Same rules since 2019  Calmar={st_long['calmar']:.2f}")
    md = write_markdown(st, st_long, hold_df)
    print(fmt_stats(st, "official"))
    print()
    print(fmt_stats(st_long, "long"))
    print("wrote", md)


if __name__ == "__main__":
    main()
