# -*- coding: utf-8 -*-
"""多资产 ETF 轮动策略回测。

规则
----
- 标的池:全部 A 股场内 ETF;每个调仓日动态保留过去 liq_win 日均成交额
  > 1000 万元、且上市满 min_days 个交易日的基金。
- 大类映射:在达标池内按资产类别(货币/黄金/A 股宽基/港股/美股/商品等)
  各取当日成交额最大的 1 只作为该类代表,再在代表之间做轮动。
- 双动量:
    相对动量 — 多窗口收益(可选波动率调整)给各类代表打分,取 top_k;
    绝对动量 — 原始动量须 > abs_thresh,且复权价在均线上方;
    否则该腿切换到货币类代表。始终 100% 满仓,不持现金。
- 执行:T 日收盘算信号,T+1 生效;换手按买卖两侧成交金额计费。

新浪行情为不复权价。|日收益|>25% 视为份额折算,当日收益记 0。
"""
from __future__ import annotations

import argparse
import os

import numpy as np
import pandas as pd

from universe import asset_class

DATA_PATH = os.path.join(os.path.dirname(__file__), "data", "etf_daily.parquet")
AMOUNT_FLOOR = 1e7
JUMP_THRESH = 0.25


def load_wide():
    df = pd.read_parquet(DATA_PATH)
    close = df.pivot_table(index="date", columns="code", values="close")
    amount = df.pivot_table(index="date", columns="code", values="amount")
    names = df.drop_duplicates("code").set_index("code")["name"]
    return close, amount, names


def clean_returns(close: pd.DataFrame, jump_thresh: float = JUMP_THRESH):
    ret = close.pct_change(fill_method=None)
    ret = ret.where(ret.abs() <= jump_thresh, 0.0)
    adj = (1 + ret.fillna(0)).cumprod().where(close.notna())
    return ret, adj


def run_backtest(
    close,
    amount,
    names,
    *,
    mom_wins=(60, 120),
    top_k=1,
    rebal_n=20,
    liq_win=20,
    min_days=120,
    risk_adj=True,
    vol_win=20,
    fee=5e-4,
    start="2019-01-01",
    end=None,
    abs_thresh=0.0,
    ma_win=60,
    trail_stop=0.0,
):
    close = close.loc[:, close.notna().sum() > 0]
    amount = amount.reindex_like(close)
    names = names.reindex(close.columns)
    ret, adj = clean_returns(close)

    liq_ok = amount.rolling(liq_win, min_periods=liq_win).mean() > AMOUNT_FLOOR
    listed_ok = close.notna().rolling(min_days, min_periods=min_days).count() >= min_days

    rawmom = sum(adj / adj.shift(w) - 1 for w in mom_wins) / len(mom_wins)
    vol = ret.rolling(vol_win, min_periods=max(5, vol_win // 2)).std()
    score = rawmom / vol.replace(0, np.nan) if risk_adj else rawmom
    eligible = liq_ok & listed_ok & close.notna() & score.notna()
    score = score.where(eligible)
    rawmom = rawmom.where(eligible)
    ma = adj.rolling(ma_win, min_periods=ma_win).mean() if ma_win else None
    above_ma = (adj > ma) if ma_win else pd.DataFrame(True, index=adj.index, columns=adj.columns)

    classes = np.array([asset_class(n) if pd.notna(n) else None for n in names])
    is_money = classes == "货币"

    dates = close.index
    if end is None:
        end = dates[-1]
    bt_dates = dates[(dates >= pd.Timestamp(start)) & (dates <= pd.Timestamp(end))]

    codes = close.columns
    score_np = score.to_numpy()
    rawmom_np = rawmom.to_numpy()
    above_np = above_ma.to_numpy()
    amount_np = amount.to_numpy()
    ret_np = ret.to_numpy()
    date_pos = {d: i for i, d in enumerate(dates)}

    holdings: list[int] | None = None
    pending: list[int] | None = None
    daily_ret = []
    daily_hold: dict = {}
    since_rebal = rebal_n
    peak: dict[int, float] = {}
    adj_np = adj.to_numpy()

    for d in bt_dates:
        i = date_pos[d]
        if pending is not None:
            def to_w(lst):
                w = {}
                for j in lst:
                    w[j] = w.get(j, 0.0) + 1.0 / len(lst)
                return w

            new_w = to_w(pending)
            old_w = to_w(holdings) if holdings else {}
            trade = sum(abs(new_w.get(j, 0) - old_w.get(j, 0)) for j in set(new_w) | set(old_w))
            holdings = pending
            pending = None
        else:
            trade = 0.0

        if holdings:
            vals = ret_np[i, holdings]
            vals = vals[~np.isnan(vals)]
            r = float(vals.mean()) if len(vals) else 0.0
            r -= trade * fee
        else:
            r = 0.0
        daily_ret.append(r)
        daily_hold[d] = [str(codes[j]) for j in (holdings or [])]

        # 跟踪止损:收盘跌破持仓期间高点 trail_stop,下一交易日切到货币
        stopped = False
        if trail_stop and holdings:
            for j in holdings:
                px = adj_np[i, j]
                if np.isnan(px):
                    continue
                peak[j] = max(peak.get(j, px), px)
                if (not is_money[j]) and px < peak[j] * (1.0 - trail_stop):
                    stopped = True
                    break
            if stopped:
                # 找当日货币代表
                s_now = score_np[i]
                valid_now = np.where(~np.isnan(s_now))[0]
                money_j = None
                best_amt = -1
                for j in valid_now:
                    if not is_money[j]:
                        continue
                    amt = amount_np[i, j]
                    if not np.isnan(amt) and amt > best_amt:
                        best_amt = amt
                        money_j = int(j)
                if money_j is not None:
                    pending = [money_j]
                    peak = {}
                    since_rebal = 0
                    continue

        since_rebal += 1
        if since_rebal < rebal_n:
            continue

        s = score_np[i]
        valid = np.where(~np.isnan(s))[0]
        if len(valid) == 0:
            continue

        # 每类取成交额最大的代表
        best_of_class: dict[str, int] = {}
        for j in valid:
            cls = classes[j]
            if cls is None:
                continue
            prev = best_of_class.get(cls)
            amt = amount_np[i, j]
            if np.isnan(amt):
                continue
            if prev is None or amt > (amount_np[i, prev] if not np.isnan(amount_np[i, prev]) else -1):
                best_of_class[cls] = int(j)
        if not best_of_class:
            continue

        money_j = best_of_class.get("货币")
        risk_js = [j for cls, j in best_of_class.items() if cls != "货币"]
        if not risk_js and money_j is not None:
            pending = [money_j]
            since_rebal = 0
            continue

        # 相对动量排序
        risk_js = sorted(risk_js, key=lambda j: s[j], reverse=True)
        picked = []
        for j in risk_js[:top_k]:
            if rawmom_np[i, j] > abs_thresh and above_np[i, j]:
                picked.append(j)
            elif money_j is not None:
                picked.append(money_j)
        if not picked:
            picked = [money_j if money_j is not None else risk_js[0]]
        pending = picked
        peak = {}
        since_rebal = 0

    ser = pd.Series(daily_ret, index=bt_dates, name="ret")
    stats = calc_stats(ser)
    stats["hold"] = daily_hold
    stats["names"] = names
    return ser, daily_hold, stats


def calc_stats(ret: pd.Series) -> dict:
    nav = (1 + ret).cumprod()
    n = len(ret)
    years = n / 248.0  # A 股常用年化交易日
    if years <= 0 or nav.iloc[-1] <= 0:
        ann = -1.0
    else:
        ann = float(nav.iloc[-1] ** (1 / years) - 1)
    dd = nav / nav.cummax() - 1
    mdd = float(-dd.min()) if len(dd) else 0.0
    calmar = ann / mdd if mdd > 1e-12 else float("inf")
    sharpe = float(ret.mean() / ret.std() * np.sqrt(248)) if ret.std() > 0 else float("inf")
    yearly = (1 + ret).groupby(ret.index.year).prod() - 1
    return {
        "total_return": float(nav.iloc[-1] - 1),
        "annual_return": ann,
        "max_drawdown": mdd,
        "calmar": float(calmar),
        "sharpe": sharpe,
        "years": years,
        "yearly": yearly,
        "nav": nav,
        "drawdown": dd,
        "ret": ret,
    }


def fmt_stats(stats, label=""):
    return "\n".join([
        f"===== {label} =====",
        f"回测年数: {stats['years']:.2f}",
        f"累计收益: {stats['total_return'] * 100:.1f}%",
        f"年化收益: {stats['annual_return'] * 100:.2f}%",
        f"最大回撤: {stats['max_drawdown'] * 100:.2f}%",
        f"Calmar : {stats['calmar']:.2f}",
        f"Sharpe : {stats['sharpe']:.2f}",
        "年度收益: " + ", ".join(f"{y}: {v * 100:.1f}%" for y, v in stats["yearly"].items()),
    ])


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--mom", type=str, default="20,60")
    ap.add_argument("--topk", type=int, default=1)
    ap.add_argument("--rebal", type=int, default=10)
    ap.add_argument("--start", type=str, default="2024-12-01")
    ap.add_argument("--end", type=str, default="2026-01-31")
    ap.add_argument("--abs-thresh", type=float, default=0.0)
    ap.add_argument("--ma", type=int, default=20)
    ap.add_argument("--no-risk-adj", action="store_true")
    ap.add_argument("--trail", type=float, default=0.08)
    args = ap.parse_args()

    close, amount, names = load_wide()
    mom_wins = tuple(int(x) for x in args.mom.split(","))
    _, hold, stats = run_backtest(
        close, amount, names,
        mom_wins=mom_wins, top_k=args.topk, rebal_n=args.rebal,
        risk_adj=not args.no_risk_adj, start=args.start, end=args.end,
        abs_thresh=args.abs_thresh, ma_win=args.ma, trail_stop=args.trail,
    )
    print(fmt_stats(stats, f"mom={mom_wins} k={args.topk} rebal={args.rebal} "
                           f"abs={args.abs_thresh} ma={args.ma} start={args.start}"))
    last = list(hold.items())[-1]
    print("最近持仓:", [(c, names.get(c, "")) for c in last[1]])
