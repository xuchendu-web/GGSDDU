"""
平台突破时序选股模型 — 核心算法模块
=========================================
基于长江证券研究所金工团队方法论实现。
包含: 布林带趋势分段 / HSAR阻力位 / 突破检测 / 26因子回归 / 批量筛选

数据源: cjpy (行情 + 因子)
"""

import numpy as np
import pandas as pd
from typing import List, Dict, Tuple, Optional
from dataclasses import dataclass, field
from datetime import datetime, timedelta


# ============================================================
# 默认参数
# ============================================================
DEFAULT_PARAMS = {
    "bollinger_window": 20,       # N: 布林带均线周期
    "bollinger_std_mult": 1.0,    # K: 标准差倍数
    "cleanup_interval": 4,        # P: 清洗间隔(日)
    "hsar_bins": 10,              # M: HSAR分箱数
    "hsar_min_cluster": 2,        # Q: 最少聚集次数
    "hsar_lookback": 252,         # HSAR回溯窗口(日)
    "breakout_buffer": 0.03,      # 突破缓冲(3%)
    "min_listed_days": 60,        # 最少上市天数
    "max_daily_pct": 0.09,        # 当日涨幅上限
    "prediction_threshold": 0.0,  # 拟合收益率阈值
    "weight_factor": "PriceMA20Dev",  # 赋权因子
}

# 逐步回归系数（来源: 长江证券研究所, 2017-2026样本）
REGRESSION_COEFFS = {
    "const":           16.693,
    "TurnMean20d":     -1.153,
    "TurnMean45d":      0.787,
    "LnCap":           -0.947,
    "Vol45d":        -107.430,
    "AmtRatio45d":     -0.362,
    "TurnVol5d":       -0.371,
    "AmtMean20d":       0.000,    # 系数接近0但显著
    "Ret5d":            0.091,
    "PriceMA20Dev":     0.091,
    "Ret45d":          -0.024,
}


# ============================================================
# 数据结构
# ============================================================
@dataclass
class TurningPoint:
    """转折点"""
    date: str
    price: float
    point_type: str  # "high" or "low"
    index: int


@dataclass
class ResistanceLevel:
    """阻力位"""
    price: float
    effective_date: str
    expire_date: str
    num_highs: int      # 参与聚集的高点数量
    bin_index: int      # 所在箱编号


@dataclass
class BreakoutSignal:
    """突破信号"""
    code: str
    name: str
    date: str
    close: float
    resistance: float
    breakout_pct: float
    predicted_return: float
    is_valid: bool
    factors: Dict[str, float] = field(default_factory=dict)
    direction: str = "unknown"


# ============================================================
# Step 1: 布林带计算 & 高低点识别
# ============================================================

def calc_bollinger_bands(df: pd.DataFrame, window: int = 20, std_mult: float = 1.0) -> pd.DataFrame:
    """
    计算布林带。

    Parameters:
        df: 含 'close' 列的日线DataFrame
        window: 均线周期(N)
        std_mult: 标准差倍数(K)

    Returns:
        添加列: MA, STD, UB(上轨), LB(下轨)
    """
    df = df.copy()
    df['MA'] = df['close'].rolling(window).mean()
    df['STD'] = df['close'].rolling(window).std()
    df['UB'] = df['MA'] + std_mult * df['STD']  # 上轨
    df['LB'] = df['MA'] - std_mult * df['STD']  # 下轨
    return df


def identify_high_lows(df: pd.DataFrame, params: dict = None) -> Tuple[List[TurningPoint], str]:
    """
    基于布林带识别局部高低点。

    逻辑:
    - 最高价 > 上轨 → 确认上升段
    - 最低价 < 下轨 → 确认下降段
    - 方向反转时确认前一段的高点/低点
    - 清洗: 去除间隔 < P 日的相邻转折点

    Parameters:
        df: 含 'high','low','close','UB','LB' 的DataFrame
        params: 参数字典

    Returns:
        (转折点列表, 当前趋势方向)
    """
    p = params or DEFAULT_PARAMS
    window = p.get("bollinger_window", 20)
    cleanup = p.get("cleanup_interval", 4)

    df = calc_bollinger_bands(df, window, p.get("bollinger_std_mult", 1.0))

    if len(df) < window + 1:
        return [], "insufficient_data"

    # 初始化: 从第一个有效布林带日开始判断方向
    valid_start = df['MA'].first_valid_index()
    if valid_start is None:
        return [], "no_valid_data"

    start_idx = df.index.get_loc(valid_start)
    current_direction = None
    segment_start_idx = start_idx
    segment_extreme_price = df.iloc[start_idx]['close']
    segment_extreme_idx = start_idx
    raw_points = []  # (date, price, type, index)

    for i in range(start_idx + 1, len(df)):
        row = df.iloc[i]
        prev_row = df.iloc[i - 1]

        high_break = row['high'] > row['UB'] if not pd.isna(row['UB']) else False
        low_break = row['low'] < row['LB'] if not pd.isna(row['LB']) else False

        # 判断当前信号方向
        if high_break and not low_break:
            signal_dir = "up"
        elif low_break and not high_break:
            signal_dir = "down"
        else:
            signal_dir = current_direction  # 延续

        if current_direction is None:
            current_direction = signal_dir if signal_dir else "up"
            continue

        # 方向一致: 更新段内极值
        if signal_dir == current_direction or signal_dir is None:
            if current_direction == "up":
                if row['high'] > segment_extreme_price:
                    segment_extreme_price = row['high']
                    segment_extreme_idx = i
            else:
                if row['low'] < segment_extreme_price:
                    segment_extreme_price = row['low']
                    segment_extreme_idx = i
        else:
            # 方向反转: 确认前一段极值为转折点
            point_type = "high" if current_direction == "up" else "low"
            date_str = str(df.index[segment_extreme_idx])[:10]
            raw_points.append(TurningPoint(
                date=date_str,
                price=float(segment_extreme_price),
                point_type=point_type,
                index=segment_extreme_idx
            ))
            # 开始新段
            current_direction = signal_dir
            segment_start_idx = i
            segment_extreme_price = row['high'] if signal_dir == "up" else row['low']
            segment_extreme_idx = i

    # 数据清洗: 去除间隔 < P 日的相邻点
    cleaned = _cleanup_points(raw_points, cleanup)

    # 判断当前方向
    final_direction = current_direction if current_direction else "unknown"

    return cleaned, final_direction


def _cleanup_points(points: List[TurningPoint], min_interval: int) -> List[TurningPoint]:
    """清洗转折点: 去除间隔不足 min_interval 的相邻点，连续同类型保留更极端者"""
    if len(points) <= 1:
        return points

    # 第一轮: 合并连续同类型
    merged = []
    i = 0
    while i < len(points):
        if not merged:
            merged.append(points[i])
            i += 1
            continue
        last = merged[-1]
        curr = points[i]
        if last.point_type == curr.point_type:
            # 同类型: 保留更极端者
            if curr.point_type == "high" and curr.price > last.price:
                merged[-1] = curr
            elif curr.point_type == "low" and curr.price < last.price:
                merged[-1] = curr
        else:
            merged.append(curr)
        i += 1

    # 第二轮: 去除间隔不足的点 (保留更近期的)
    if len(merged) <= 1:
        return merged

    cleaned = [merged[0]]
    for i in range(1, len(merged)):
        if merged[i].index - cleaned[-1].index >= min_interval:
            cleaned.append(merged[i])
        else:
            # 间隔不足: 保留更极端的
            if merged[i].point_type == cleaned[-1].point_type:
                if merged[i].point_type == "high" and merged[i].price > cleaned[-1].price:
                    cleaned[-1] = merged[i]
                elif merged[i].point_type == "low" and merged[i].price < cleaned[-1].price:
                    cleaned[-1] = merged[i]
            # 不同类型: 跳过(保留已有)

    return cleaned


# ============================================================
# Step 2: HSAR 阻力位定位
# ============================================================

def hsar_resistance(df: pd.DataFrame, high_points: List[TurningPoint],
                    params: dict = None, anchor_date: str = None) -> Optional[ResistanceLevel]:
    """
    HSAR 水平支撑阻力算法 — 定位阻力位。

    步骤:
    1. 取过去 lookback 日的日线高低点范围
    2. 等宽分箱 (M=10)
    3. 将局部高点分入各箱
    4. 找同时满足"高点聚集"和"位置偏高"的箱
    5. 输出阻力位 = 该箱上边界

    Parameters:
        df: 完整日线DataFrame (需包含历史数据)
        high_points: 局部高点列表
        params: 参数字典
        anchor_date: 锚定日期 (阻力位生效日, 默认最新)

    Returns:
        ResistanceLevel 或 None
    """
    p = params or DEFAULT_PARAMS
    M = p.get("hsar_bins", 10)
    Q = p.get("hsar_min_cluster", 2)
    lookback = p.get("hsar_lookback", 252)

    if not high_points:
        return None

    # 确定数据范围
    if anchor_date:
        end_date = pd.Timestamp(anchor_date)
    else:
        end_date = df.index[-1]
    start_date = end_date - timedelta(days=lookback * 2)  # 宽松覆盖

    window_df = df.loc[start_date:end_date]
    if len(window_df) < 20:
        return None

    # 价格范围: 过去 lookback 日的所有日线高低点
    recent_df = window_df.iloc[-lookback:] if len(window_df) > lookback else window_df
    price_min = recent_df['low'].min()
    price_max = recent_df['high'].max()

    if price_max <= price_min:
        return None

    bin_width = (price_max - price_min) / M

    # 筛选在回溯窗口内的局部高点
    recent_highs = [hp for hp in high_points
                    if pd.Timestamp(hp.date) >= recent_df.index[0]
                    and pd.Timestamp(hp.date) <= recent_df.index[-1]]

    if len(recent_highs) < Q:
        return None

    # 分箱
    bin_counts = [0] * M
    for hp in recent_highs:
        k = int((hp.price - price_min) / bin_width)
        k = min(k, M - 1)
        k = max(k, 0)
        bin_counts[k] += 1

    # 从高到低找阻力位
    for k in range(M - 1, -1, -1):
        # 条件①: 该箱及下方一箱内高点 >= Q
        cluster_count = bin_counts[k]
        if k > 0:
            cluster_count += bin_counts[k - 1]

        # 条件②: 上方一箱无更高高点
        has_higher = False
        for j in range(k + 1, M):
            if bin_counts[j] > 0:
                has_higher = True
                break

        if cluster_count >= Q and not has_higher:
            resistance_price = price_min + (k + 1) * bin_width
            effective = str(end_date.date())
            expire = str((end_date + timedelta(days=7)).date())
            return ResistanceLevel(
                price=round(resistance_price, 2),
                effective_date=effective,
                expire_date=expire,
                num_highs=cluster_count,
                bin_index=k,
            )

    return None


# ============================================================
# Step 3: 突破检测
# ============================================================

def detect_breakout(df: pd.DataFrame, resistance: ResistanceLevel,
                    params: dict = None) -> List[BreakoutSignal]:
    """
    检测突破信号。

    Parameters:
        df: 日线DataFrame
        resistance: 阻力位对象
        params: 参数字典

    Returns:
        突破信号列表 (最近的一次)
    """
    p = params or DEFAULT_PARAMS
    buffer_pct = p.get("breakout_buffer", 0.03)

    signals = []
    eff_date = pd.Timestamp(resistance.effective_date)
    exp_date = pd.Timestamp(resistance.expire_date)

    for i in range(len(df)):
        row_date = df.index[i]
        if row_date < eff_date or row_date > exp_date:
            continue

        close = float(df.iloc[i]['close'])
        threshold = resistance.price * (1 + buffer_pct)

        if close > threshold:
            breakout_pct = (close / resistance.price - 1) * 100
            signals.append(BreakoutSignal(
                code="",
                name="",
                date=str(row_date.date()),
                close=close,
                resistance=resistance.price,
                breakout_pct=round(breakout_pct, 2),
                predicted_return=0.0,
                is_valid=False,
            ))

    # 去重: 连续突破只保留首次
    if len(signals) > 1:
        deduped = [signals[0]]
        for s in signals[1:]:
            prev_date = pd.Timestamp(deduped[-1].date)
            curr_date = pd.Timestamp(s.date)
            if (curr_date - prev_date).days > 5:  # 至少间隔5天
                deduped.append(s)
        signals = deduped

    return signals


# ============================================================
# Step 4: 26因子计算 & 回归预测
# ============================================================

def calc_volume_factors(df: pd.DataFrame, signal_date: str) -> Dict[str, float]:
    """
    计算突破时点的26个价量因子。

    Parameters:
        df: 含 open/high/low/close/volume/turn/cap 的日线DataFrame
        signal_date: 突破信号日期

    Returns:
        因子名 → 值 字典
    """
    idx = df.index.get_loc(pd.Timestamp(signal_date))
    if idx is None:
        return {}

    factors = {}
    row = df.iloc[idx]

    # --- 换手率类 (7个) ---
    if 'turn' in df.columns:
        factors['Turn'] = float(row.get('turn', 0))
        for d in [5, 20, 45]:
            if idx >= d:
                factors[f'TurnMean{d}d'] = float(df['turn'].iloc[idx-d:idx+1].mean())
                factors[f'TurnVol{d}d'] = float(df['turn'].iloc[idx-d:idx+1].std())
            else:
                factors[f'TurnMean{d}d'] = factors.get('Turn', 0)
                factors[f'TurnVol{d}d'] = 0.0

    # --- 成交额类 (6个) ---
    if 'amount' in df.columns:
        amount = float(row.get('amount', 0))
        for d in [5, 20, 45]:
            if idx >= d:
                mean_amt = float(df['amount'].iloc[idx-d:idx+1].mean())
                factors[f'AmtMean{d}d'] = mean_amt
                factors[f'AmtRatio{d}d'] = amount / mean_amt if mean_amt > 0 else 1.0
            else:
                factors[f'AmtMean{d}d'] = amount
                factors[f'AmtRatio{d}d'] = 1.0

    # --- 动量类 (3个) ---
    close = float(row['close'])
    for d in [5, 20, 45]:
        if idx >= d:
            past_close = float(df['close'].iloc[idx - d])
            factors[f'Ret{d}d'] = (close / past_close - 1) * 100
        else:
            factors[f'Ret{d}d'] = 0.0

    # --- 波动率类 (3个) ---
    if 'close' in df.columns:
        returns = df['close'].pct_change()
        for d in [5, 20, 45]:
            if idx >= d:
                factors[f'Vol{d}d'] = float(returns.iloc[idx-d:idx].std() * 100)
            else:
                factors[f'Vol{d}d'] = 0.0

    # --- 市值类 (4个) ---
    if 'cap' in df.columns:
        cap = float(row.get('cap', 1e8))
        factors['LnCap'] = np.log(cap)
        cap_returns = df['cap'].pct_change()
        for d in [5, 20, 45]:
            if idx >= d:
                factors[f'CapVol{d}d'] = float(cap_returns.iloc[idx-d:idx].std() * 100)
            else:
                factors[f'CapVol{d}d'] = 0.0
    else:
        factors['LnCap'] = np.log(1e8)
        for d in [5, 20, 45]:
            factors[f'CapVol{d}d'] = 0.0

    # --- 均线偏离度 (3个) ---
    for d in [5, 20, 45]:
        if idx >= d:
            ma = float(df['close'].iloc[idx-d:idx+1].mean())
            factors[f'PriceMA{d}Dev'] = (close / ma - 1) * 100 if ma > 0 else 0.0
        else:
            factors[f'PriceMA{d}Dev'] = 0.0

    return factors


def predict_return(factors: Dict[str, float]) -> float:
    """
    根据逐步回归系数计算拟合收益率。

    Parameters:
        factors: 26因子值字典

    Returns:
        拟合的45日持有期收益率(%)
    """
    pred = REGRESSION_COEFFS["const"]
    for var, coef in REGRESSION_COEFFS.items():
        if var == "const":
            continue
        if var in factors:
            pred += coef * factors[var]
    return round(pred, 2)


def is_valid_breakout(df: pd.DataFrame, signal_date: str,
                      params: dict = None) -> Tuple[bool, float, Dict[str, float]]:
    """
    判断突破信号是否有效(通过价量筛选)。

    Returns:
        (是否有效, 拟合收益率, 因子字典)
    """
    p = params or DEFAULT_PARAMS
    threshold = p.get("prediction_threshold", 0.0)

    factors = calc_volume_factors(df, signal_date)
    if not factors:
        return False, 0.0, {}

    pred = predict_return(factors)
    is_valid = pred > threshold

    return is_valid, pred, factors


# ============================================================
# Step 5: 动量赋权
# ============================================================

def calc_momentum_weights(signals: List[BreakoutSignal],
                          weight_factor: str = "PriceMA20Dev") -> List[float]:
    """
    根据动量因子计算持仓权重。

    Parameters:
        signals: 有效突破信号列表 (需含factors)
        weight_factor: "PriceMA20Dev" 或 "Ret5d"

    Returns:
        权重列表 (和为1)
    """
    if not signals:
        return []

    scores = []
    for s in signals:
        factors = s.factors
        if weight_factor == "PriceMA20Dev":
            score = max(factors.get("PriceMA20Dev", 0), 0)
        elif weight_factor == "Ret5d":
            score = max(factors.get("Ret5d", 0), 0)
        else:
            score = 1.0  # 等权

        scores.append(score)

    total = sum(scores)
    if total == 0:
        return [1.0 / len(signals)] * len(signals)

    return [s / total for s in scores]


# ============================================================
# 综合个股分析
# ============================================================

def analyze_single(df: pd.DataFrame, code: str = "", name: str = "",
                   industry: str = "", params: dict = None) -> dict:
    """
    对单只股票执行完整的平台突破分析。

    Parameters:
        df: 日线DataFrame (index=date, columns: open/high/low/close/volume/[turn]/[cap])
        code: 股票代码
        name: 股票名称
        industry: 行业
        params: 参数字典

    Returns:
        分析结果字典
    """
    p = params or DEFAULT_PARAMS
    result = {
        "code": code,
        "name": name,
        "industry": industry,
        "analysis_date": str(df.index[-1].date()),
        "direction": "unknown",
        "bollinger": {},
        "turning_points": [],
        "resistance": None,
        "breakout_signals": [],
        "latest_signal": None,
        "factors": {},
        "predicted_return": 0.0,
        "is_valid": False,
        "signal_strength": 0,
        "risk_notes": [],
    }

    if len(df) < 20:
        result["risk_notes"].append("数据不足(少于20个交易日)")
        return result

    # Step 1: 布林带 & 高低点
    df_bb = calc_bollinger_bands(df, p["bollinger_window"], p["bollinger_std_mult"])
    turning_points, direction = identify_high_lows(df_bb, p)

    last_row = df_bb.iloc[-1]
    result["direction"] = direction
    result["bollinger"] = {
        "MA": round(float(last_row.get('MA', 0)), 2) if not pd.isna(last_row.get('MA', 0)) else None,
        "UB": round(float(last_row.get('UB', 0)), 2) if not pd.isna(last_row.get('UB', 0)) else None,
        "LB": round(float(last_row.get('LB', 0)), 2) if not pd.isna(last_row.get('LB', 0)) else None,
        "close": round(float(last_row['close']), 2),
    }
    if result["bollinger"]["UB"] and result["bollinger"]["UB"] > 0:
        result["bollinger"]["pct_to_ub"] = round(
            (result["bollinger"]["close"] / result["bollinger"]["UB"] - 1) * 100, 2
        )

    result["turning_points"] = [
        {"date": tp.date, "price": tp.price, "type": tp.point_type}
        for tp in turning_points[-10:]  # 最近10个
    ]

    # Step 2: HSAR阻力位
    high_points = [tp for tp in turning_points if tp.point_type == "high"]
    resistance = hsar_resistance(df_bb, high_points, p)
    if resistance:
        result["resistance"] = {
            "price": resistance.price,
            "effective_date": resistance.effective_date,
            "expire_date": resistance.expire_date,
            "num_highs": resistance.num_highs,
        }
        current_close = float(df_bb.iloc[-1]['close'])
        result["resistance"]["distance_pct"] = round(
            (current_close / resistance.price - 1) * 100, 2
        )

    # Step 3 & 4: 突破检测 & 价量筛选
    if resistance:
        signals = detect_breakout(df_bb, resistance, p)
        for s in signals:
            s.code = code
            s.name = name
            is_valid, pred, factors = is_valid_breakout(df, s.date, p)
            s.is_valid = is_valid
            s.predicted_return = pred
            s.factors = factors
            s.direction = direction

        result["breakout_signals"] = [
            {
                "date": s.date,
                "close": s.close,
                "breakout_pct": s.breakout_pct,
                "predicted_return": s.predicted_return,
                "is_valid": s.is_valid,
            }
            for s in signals
        ]

        if signals:
            latest = signals[-1]
            result["latest_signal"] = {
                "date": latest.date,
                "close": latest.close,
                "breakout_pct": latest.breakout_pct,
                "predicted_return": latest.predicted_return,
                "is_valid": latest.is_valid,
            }
            result["predicted_return"] = latest.predicted_return
            result["is_valid"] = latest.is_valid
            result["factors"] = latest.factors

    # 信号强度评分 (0-5)
    strength = 0
    if result.get("resistance"):
        strength += 1  # 有阻力位基准1分
    if result["is_valid"]:
        strength += 2
    if result["direction"] == "up":
        strength += 1
    if result.get("resistance") and result["resistance"].get("distance_pct", -100) > -3:
        strength += 1
    if result["predicted_return"] > 5:
        strength += 1
    result["signal_strength"] = min(strength, 5)

    # 风险提示
    if direction == "down":
        result["risk_notes"].append("当前趋势向下，突破信号可靠性降低")
    if result.get("resistance") and result["resistance"].get("num_highs", 0) < 3:
        result["risk_notes"].append("阻力位仅由少量高点确认，可信度有限")
    if result.get("latest_signal") and result["latest_signal"].get("breakout_pct", 0) < 5:
        result["risk_notes"].append("突破幅度偏小，可能为假突破")

    return result


# ============================================================
# 批量筛选
# ============================================================

def screen_batch(codes: List[str], df_map: Dict[str, pd.DataFrame],
                 names: Dict[str, str] = None, industries: Dict[str, str] = None,
                 params: dict = None) -> List[BreakoutSignal]:
    """
    在股票池中批量筛选平台突破信号。

    Parameters:
        codes: 股票代码列表
        df_map: {code: DataFrame} 日线数据映射
        names: {code: name} 名称映射
        industries: {code: industry} 行业映射
        params: 参数字典

    Returns:
        有效突破信号列表 (按 predicted_return 降序)
    """
    p = params or DEFAULT_PARAMS
    results = []

    for code in codes:
        if code not in df_map:
            continue
        df = df_map[code]
        if len(df) < p.get("min_listed_days", 60):
            continue

        name = names.get(code, code) if names else code
        industry = industries.get(code, "") if industries else ""

        analysis = analyze_single(df, code, name, industry, p)

        if analysis.get("latest_signal") and analysis["latest_signal"].get("is_valid"):
            s = BreakoutSignal(
                code=code,
                name=name,
                date=analysis["latest_signal"]["date"],
                close=analysis["latest_signal"]["close"],
                resistance=analysis.get("resistance", {}).get("price", 0) if analysis.get("resistance") else 0,
                breakout_pct=analysis["latest_signal"]["breakout_pct"],
                predicted_return=analysis["predicted_return"],
                is_valid=True,
                factors=analysis.get("factors", {}),
                direction=analysis.get("direction", "unknown"),
            )
            # 附加上下文信息
            s.industry = industry
            s.signal_strength = analysis.get("signal_strength", 0)
            cap_val = analysis.get("factors", {}).get("LnCap", 0)
            s.market_cap = round(np.exp(cap_val) / 1e8, 1) if cap_val else 0
            results.append(s)

    # 按预测收益率降序
    results.sort(key=lambda x: x.predicted_return, reverse=True)

    return results


# ============================================================
# 格式化输出
# ============================================================

def format_analysis_report(result: dict) -> str:
    """将个股分析结果格式化为文本报告"""
    lines = []
    lines.append("═" * 55)
    lines.append("        平台突破分析报告")
    lines.append("═" * 55)
    lines.append(f"股票: {result['code']}({result['name']})  |  "
                 f"分析日期: {result['analysis_date']}")
    if result.get('industry'):
        lines.append(f"行业: {result['industry']}")
    lines.append("─" * 55)

    # 一、趋势方向
    lines.append("【一、趋势方向】")
    direction_map = {"up": "上升 ↑", "down": "下降 ↓", "unknown": "震荡 ↔"}
    lines.append(f"  当前方向: {direction_map.get(result['direction'], '未知')}")
    bb = result.get("bollinger", {})
    if bb:
        lines.append(f"  布林带: 上轨 {bb.get('UB', 'N/A')}  |  "
                     f"中轨 {bb.get('MA', 'N/A')}  |  下轨 {bb.get('LB', 'N/A')}")
        if bb.get('pct_to_ub') is not None:
            lines.append(f"  收盘价 {bb.get('close', 'N/A')} (相对上轨 {bb['pct_to_ub']:+.1f}%)")
    points = result.get("turning_points", [])
    if points:
        recent_high = [p for p in points if p['type'] == 'high']
        recent_low = [p for p in points if p['type'] == 'low']
        if recent_high:
            lines.append(f"  最近高点: {recent_high[-1]['price']:.2f} ({recent_high[-1]['date']})")
        if recent_low:
            lines.append(f"  最近低点: {recent_low[-1]['price']:.2f} ({recent_low[-1]['date']})")

    # 二、阻力位
    lines.append("")
    lines.append("【二、阻力位分析】")
    res = result.get("resistance")
    if res:
        lines.append(f"  阻力位: {res['price']} (生效: {res['effective_date']}, "
                     f"到期: {res['expire_date']})")
        lines.append(f"  来源: {res['num_highs']} 个局部高点聚集")
        lines.append(f"  当前距离: {res.get('distance_pct', 0):+.1f}%")
    else:
        lines.append("  当前无有效阻力位")

    # 三、突破信号
    lines.append("")
    lines.append("【三、突破信号】")
    sig = result.get("latest_signal")
    if sig:
        status = "✅ 有效突破" if sig['is_valid'] else "❌ 未通过筛选"
        lines.append(f"  突破状态: {status}")
        lines.append(f"  突破日期: {sig['date']}")
        lines.append(f"  收盘价: {sig['close']}  |  突破幅度: +{sig['breakout_pct']}%")
        lines.append(f"  拟合收益: {sig['predicted_return']:+.1f}%")
    else:
        lines.append("  暂无突破信号")

    # 四、价量
    lines.append("")
    lines.append("【四、价量评估】")
    factors = result.get("factors", {})
    if factors:
        key_factors = ["Ret5d", "Ret45d", "PriceMA20Dev", "TurnMean20d", "LnCap", "Vol45d"]
        for f in key_factors:
            if f in factors:
                val = factors[f]
                sign = "+" if val > 0 else ""
                lines.append(f"  {f}: {sign}{val:.2f}")
    else:
        lines.append("  暂无价量数据")

    # 五、综合
    lines.append("")
    lines.append("【五、综合建议】")
    stars = "⭐" * result.get("signal_strength", 0)
    lines.append(f"  信号强度: {stars} ({result.get('signal_strength', 0)}/5)")
    pred = result.get("predicted_return", 0)
    if pred > 10:
        lines.append("  操作建议: 🔥 重点关注")
    elif pred > 5:
        lines.append("  操作建议: ✅ 可关注")
    elif pred > 0:
        lines.append("  操作建议: ⏳ 观望(信号偏弱)")
    else:
        lines.append("  操作建议: ❌ 回避")
    for note in result.get("risk_notes", []):
        lines.append(f"  ⚠ {note}")
    lines.append("─" * 55)
    return "\n".join(lines)


def format_screen_report(signals: List[BreakoutSignal], pool_name: str = "全市场",
                         params: dict = None) -> str:
    """格式化批量筛选报告"""
    lines = []
    lines.append("═" * 75)
    lines.append("      平台突破批量筛选报告")
    lines.append("═" * 75)
    screening_date = signals[0].date if signals else datetime.now().strftime("%Y-%m-%d")
    lines.append(f"筛选日期: {screening_date}  |  股票池: {pool_name}")
    lines.append(f"有效突破: {len(signals)}只")
    lines.append("─" * 75)

    if not signals:
        lines.append("  当前股票池无有效突破信号")
        return "\n".join(lines)

    # 排名表
    lines.append(f"{'排名':<5}{'代码':<12}{'名称':<10}{'市值(亿)':<10}"
                 f"{'拟合收益':<10}{'距阻力%':<10}{'信号':<8}")
    lines.append("─" * 75)
    for i, s in enumerate(signals[:30], 1):  # Top 30
        cap = getattr(s, 'market_cap', 0)
        strength = getattr(s, 'signal_strength', 0)
        stars = "⭐" * max(strength, 1)
        lines.append(f"{i:<5}{s.code:<12}{s.name:<10}{cap:<10.1f}"
                     f"{s.predicted_return:+.1f}%{'':>4}{s.breakout_pct:+.1f}%{'':>4}{stars}")

    # 行业分布
    if hasattr(signals[0], 'industry'):
        lines.append("")
        lines.append("【行业分布 Top 5】")
        from collections import Counter
        ind_counts = Counter(getattr(s, 'industry', '未知') for s in signals)
        for ind, cnt in ind_counts.most_common(5):
            pct = cnt / len(signals) * 100
            lines.append(f"  {ind}: {cnt}只 ({pct:.0f}%)")

    # 市值分布
    caps = [getattr(s, 'market_cap', 0) for s in signals if getattr(s, 'market_cap', 0) > 0]
    if caps:
        lines.append("")
        lines.append("【市值分布】")
        lines.append(f"  最小: {min(caps):.0f}亿  |  中位: {np.median(caps):.0f}亿  |  "
                     f"最大: {max(caps):.0f}亿")
        small = sum(1 for c in caps if c < 100)
        mid = sum(1 for c in caps if 100 <= c < 500)
        large = sum(1 for c in caps if c >= 500)
        lines.append(f"  <100亿: {small}只  |  100-500亿: {mid}只  |  >500亿: {large}只")

    lines.append("─" * 75)
    return "\n".join(lines)


# ============================================================
# 工具函数
# ============================================================

def prepare_df_from_cjpy(raw_df: pd.DataFrame, code: str = "",
                         factors_df: pd.DataFrame = None) -> pd.DataFrame:
    """
    将 cjpy 返回的行情数据转换为分析所需的 DataFrame。

    cjpy get_market_data 返回格式:
      时间 | open | high | low | close | vol | amount | ...

    额外需要的列: turn(换手率), cap(总市值) — 通过 get_factor_data 补充
    """
    df = raw_df.copy()

    # === 列名标准化 ===
    # cjpy 可能返回 '时间' 或索引中已含时间
    # 重命名: vol -> volume
    col_map = {
        'vol': 'volume',
    }
    for old, new in col_map.items():
        if old in df.columns and new not in df.columns:
            df[new] = df[old]

    # 确保必要列存在
    for col in ['open', 'high', 'low', 'close', 'volume']:
        if col not in df.columns:
            raise ValueError(f"缺少必要列: {col}, 可用列: {df.columns.tolist()}")

    # === 日期索引处理 ===
    if '时间' in df.columns:
        # cjpy 标准格式: 时间列
        df['时间'] = pd.to_datetime(df['时间'])
        df = df.set_index('时间').sort_index()
    elif 'time' in df.columns:
        df['time'] = pd.to_datetime(df['time'])
        df = df.set_index('time').sort_index()
    elif not isinstance(df.index, pd.DatetimeIndex):
        # 尝试将第一列字符串列或当前索引转为时间
        for col in df.columns:
            if df[col].dtype == 'object':
                try:
                    parsed = pd.to_datetime(df[col])
                    if parsed.notna().sum() > 0.5 * len(parsed):
                        df['_time'] = parsed
                        df = df.set_index('_time').sort_index()
                        break
                except Exception:
                    continue
        if not isinstance(df.index, pd.DatetimeIndex):
            raise ValueError(f"无法解析日期索引, 列: {df.columns.tolist()}, 索引类型: {type(df.index)}")

    # === 因子数据合并 ===
    if factors_df is not None and len(factors_df) > 0:
        if '换手率' in factors_df.columns:
            df['turn'] = float(factors_df['换手率'].iloc[0])
        elif 'turnover' in factors_df.columns:
            df['turn'] = float(factors_df['turnover'].iloc[0])
        if '总市值' in factors_df.columns:
            df['cap'] = float(factors_df['总市值'].iloc[0])
        elif 'cap' in factors_df.columns:
            df['cap'] = float(factors_df['cap'].iloc[0])

    # === 补充缺失列 ===
    # amount
    if 'amount' not in df.columns:
        df['amount'] = df['volume'] * df['close']  # 估算

    # turn (换手率) — 如果没有则从 amount 近似
    if 'turn' not in df.columns:
        df['turn'] = df['amount'] / df['amount'].rolling(20).mean()  # 相对均量比

    # cap (总市值) — 默认
    if 'cap' not in df.columns:
        df['cap'] = 1e8  # 1亿默认

    return df


def get_index_constituents(index_name: str) -> List[str]:
    """
    获取指数成分股列表。

    支持的指数: hs300, csi500, csi1000
    通过 cjpy 获取成分股列表。
    """
    index_map = {
        "hs300": "沪深300",
        "csi500": "中证500",
        "csi1000": "中证1000",
    }

    if index_name.lower() not in index_map:
        raise ValueError(f"不支持的指数: {index_name}，可选: {list(index_map.keys())}")

    # 使用 cjpy 获取指数成分
    try:
        import cjpy
        # get_factor_data 获取指数成分
        # 指数成分因子通常包含 'is_hs300' 等
        all_stocks = cjpy.get_stocks()
        # 简化处理: 返回前N只
        return all_stocks
    except Exception:
        # Fallback: 返回空列表
        return []
