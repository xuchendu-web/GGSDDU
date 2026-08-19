#!/usr/bin/env python
"""
平台突破选股 — 执行脚本
======================
两种模式:
  analyze <code>       个股平台突破分析
  screen [--pool POOL] 股票池批量筛选

数据源: cjpy 行情 + 因子数据

用法:
  C:\Python314\python.exe screen.py analyze SH600000
  C:\Python314\python.exe screen.py screen --pool hs300
  C:\Python314\python.exe screen.py screen --codes SH600000,SZ000001,SZ300308
  C:\Python314\python.exe screen.py screen --pool csi1000 --date 20260725
"""

import sys
import os
import argparse
from datetime import datetime, timedelta

# 将 scripts 目录加入路径
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from breakout import (
    DEFAULT_PARAMS,
    analyze_single,
    screen_batch,
    format_analysis_report,
    format_screen_report,
    prepare_df_from_cjpy,
)


def get_cjpy_data(code: str, lookback_days: int = 400) -> dict:
    """
    通过 cjpy 获取单只股票的行情和因子数据。

    Returns:
        {'df': DataFrame, 'name': str, 'industry': str, 'cap': float}
    """
    import cjpy

    end_date = datetime.now().strftime("%Y%m%d")
    start_date = (datetime.now() - timedelta(days=lookback_days)).strftime("%Y%m%d")

    # 获取行情数据
    try:
        raw = cjpy.get_market_data(code, start_date, end_date, cycle="day", rate="前复权")
        if raw is None or len(raw) == 0:
            print(f"  [WARN] {code}: 无行情数据")
            return None
    except Exception as e:
        print(f"  [WARN] {code}: 行情获取失败 - {e}")
        return None

    # 获取因子数据 (换手率、市值)
    try:
        factors_df = cjpy.get_factor_data(
            code=[code],
            date=[end_date],
            factors=["换手率", "总市值"],
        )
        if factors_df is not None and len(factors_df) > 0:
            # cjpy 返回的因子数据包含 code/date 列
            for col in ['换手率', 'turnover']:
                if col in factors_df.columns:
                    df['turn'] = float(factors_df[col].iloc[0])
                    break
            for col in ['总市值', 'cap']:
                if col in factors_df.columns:
                    df['cap'] = float(factors_df[col].iloc[0])
                    break
    except Exception as e:
        pass  # 因子缺失不影响主流程

    # 获取股票名称
    name = code
    industry = ""
    try:
        info = cjpy.search_code(code)
        if info and len(info) > 0:
            name = info[0].get('name', code)
            industry = info[0].get('industry', '')
    except Exception:
        pass

    return {
        'df': df,
        'name': name,
        'industry': industry,
    }


def cmd_analyze(code: str, params: dict = None):
    """个股分析模式"""
    print(f"\n正在获取 {code} 数据...\n")
    data = get_cjpy_data(code)

    if data is None:
        print(f"无法获取 {code} 的数据")
        return

    result = analyze_single(data['df'], code, data['name'], data['industry'], params)
    report = format_analysis_report(result)
    print(report)


def cmd_screen(pool: str = None, codes_str: str = None, date: str = None,
               params: dict = None):
    """批量筛选模式"""
    import cjpy

    if codes_str:
        codes = [c.strip() for c in codes_str.split(",") if c.strip()]
        pool_name = f"自定义({len(codes)}只)"
    elif pool:
        pool_name = pool.upper()
        # 获取指数成分或全市场
        if pool.lower() == "all":
            try:
                codes = cjpy.get_stocks()
                pool_name = "全市场"
            except Exception as e:
                print(f"获取全市场股票列表失败: {e}")
                return
        else:
            # 默认使用 cjpy 获取
            try:
                codes = cjpy.get_stocks()
                # 简化: 取前100只演示
                codes = codes[:100]
                pool_name = f"{pool.upper()}(Top100)"
            except Exception:
                print(f"无法获取 {pool} 成分股列表")
                return
    else:
        # 默认: 尝试获取沪深300
        try:
            codes = cjpy.get_stocks()
            codes = codes[:50]
            pool_name = "全市场(Top50)"
        except Exception:
            print("请指定股票池: --pool hs300/csi500/csi1000 或 --codes")
            return

    print(f"\n股票池: {pool_name} ({len(codes)}只)")
    print("正在逐只分析平台突破状态...\n")

    # 逐只获取数据并分析
    df_map = {}
    names_map = {}
    industries_map = {}

    for i, code in enumerate(codes):
        pct = (i + 1) / len(codes) * 100
        sys.stdout.write(f"\r进度: {i+1}/{len(codes)} ({pct:.0f}%) - {code}")
        sys.stdout.flush()

        data = get_cjpy_data(code, lookback_days=400)
        if data:
            df_map[code] = data['df']
            names_map[code] = data['name']
            industries_map[code] = data['industry']

    print("\n")
    sys.stdout.flush()

    # 批量筛选
    signals = screen_batch(list(df_map.keys()), df_map, names_map, industries_map, params)
    report = format_screen_report(signals, pool_name, params)
    print(report)

    # 输出信号列表
    if signals:
        print(f"\n共筛选出 {len(signals)} 只有效突破股票")
        print("\n代码列表 (可按拟合收益率排序):")
        for i, s in enumerate(signals[:20], 1):
            print(f"  {i:2d}. {s.code} {s.name:<10} 拟合收益: {s.predicted_return:+.1f}%  "
                  f"突破: +{s.breakout_pct}%")


def main():
    parser = argparse.ArgumentParser(
        description="平台突破时序选股模型",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
示例:
  python screen.py analyze SH600000           # 分析单只股票
  python screen.py screen --pool hs300         # 沪深300平台突破筛选
  python screen.py screen --codes SH600000,SZ000001  # 自定义列表
  python screen.py screen --pool all --date 20260725  # 指定日期
        """
    )
    subparsers = parser.add_subparsers(dest="command", help="模式")

    # analyze 子命令
    parser_analyze = subparsers.add_parser("analyze", help="个股平台突破分析")
    parser_analyze.add_argument("code", help="股票代码 (如 SH600000)")

    # screen 子命令
    parser_screen = subparsers.add_parser("screen", help="股票池批量筛选")
    parser_screen.add_argument("--pool", default=None,
                               help="股票池: hs300 / csi500 / csi1000 / all")
    parser_screen.add_argument("--codes", default=None,
                               help="自定义代码列表，逗号分隔")
    parser_screen.add_argument("--date", default=None,
                               help="筛选日期 (YYYYMMDD)")
    parser_screen.add_argument("--min-return", type=float, default=0,
                               help="最低拟合收益率阈值 (默认0)")
    parser_screen.add_argument("--buffer", type=float, default=0.03,
                               help="突破缓冲比例 (默认0.03=3%%)")

    args = parser.parse_args()

    if args.command is None:
        parser.print_help()
        return

    # 构建参数
    params = DEFAULT_PARAMS.copy()
    if args.command == "screen":
        params["prediction_threshold"] = args.min_return
        params["breakout_buffer"] = args.buffer

    if args.command == "analyze":
        cmd_analyze(args.code, params)
    elif args.command == "screen":
        cmd_screen(args.pool, args.codes, args.date, params)


if __name__ == "__main__":
    main()
