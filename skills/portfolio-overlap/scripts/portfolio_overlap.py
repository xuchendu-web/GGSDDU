#!/usr/bin/env python3
"""
持仓重叠分析引擎 — 重叠度矩阵 + 组合集中度 + HTML 热力图报告
"""

import json
import sys
import argparse
import math
from datetime import datetime
from pathlib import Path
from collections import defaultdict

try:
    import cjpy
    HAS_CJPY = True
except ImportError:
    HAS_CJPY = False


def compute_return_correlation(fund_codes: list, fund_labels: list = None, months: int = 24) -> dict:
    """计算基金间收益率相关性矩阵
    
    Args:
        fund_codes: 基金代码列表 (OF前缀)
        fund_labels: 基金名称列表 (用于矩阵标注)
        months: 回看月数
    
    Returns:
        dict with 'matrix' (dict of dict), 'period_start', 'period_end', 'fund_labels'
    """
    if not HAS_CJPY:
        return None
    if fund_labels is None:
        fund_labels = fund_codes
    
    # 收集各基金周收益率序列
    fund_returns = {}
    period_start = None
    period_end = None
    
    for code, label in zip(fund_codes, fund_labels):
        try:
            df = cjpy.get_table_data(code, "基金净值收益率")
            if df.empty:
                continue
            # 取最近 months 个月的数据
            df = df.sort_values("截止日")
            latest = df["截止日"].max()
            if period_end is None or latest > period_end:
                period_end = latest
            
            # 过滤最近 N 个月
            cutoff = int(str(latest)[:8]) - months * 100  # 粗略月份截断
            df = df[df["截止日"] >= cutoff]
            
            if df.empty:
                continue
            
            if period_start is None or df["截止日"].min() < period_start:
                period_start = df["截止日"].min()
            
            # 提取周收益率序列 (对齐日期)
            returns = {}
            for _, row in df.iterrows():
                d = row["截止日"]
                r = row.get("净值收益率(%)", row.get("净值增长率(%)", 0))
                returns[d] = r
            fund_returns[label] = returns
        except Exception:
            continue
    
    if len(fund_returns) < 2:
        return None
    
    # 对齐日期：取所有基金共有的交易日
    all_dates = sorted(set().union(*[set(r.keys()) for r in fund_returns.values()]))
    common_dates = []
    for d in all_dates:
        if all(d in fund_returns[f] for f in fund_returns):
            common_dates.append(d)
    
    if len(common_dates) < 8:
        return None  # 数据太少，不计算
    
    # 构建收益率矩阵
    labels = list(fund_returns.keys())
    n = len(labels)
    ret_array = {label: [] for label in labels}
    for d in common_dates:
        for label in labels:
            ret_array[label].append(fund_returns[label][d])
    
    # 计算 Pearson 相关系数
    def pearson(x, y):
        n_pt = len(x)
        if n_pt < 3:
            return 0
        mx = sum(x) / n_pt
        my = sum(y) / n_pt
        sx = math.sqrt(sum((v - mx)**2 for v in x) / (n_pt - 1))
        sy = math.sqrt(sum((v - my)**2 for v in y) / (n_pt - 1))
        if sx == 0 or sy == 0:
            return 0
        cov = sum((x[i] - mx) * (y[i] - my) for i in range(n_pt)) / (n_pt - 1)
        return round(cov / (sx * sy), 4)
    
    corr_matrix = {}
    for i in range(n):
        corr_matrix[labels[i]] = {}
        for j in range(n):
            if i == j:
                corr_matrix[labels[i]][labels[j]] = 1.0
            elif j in corr_matrix and labels[i] in corr_matrix[labels[j]]:
                corr_matrix[labels[i]][labels[j]] = corr_matrix[labels[j]][labels[i]]
            else:
                c = pearson(ret_array[labels[i]], ret_array[labels[j]])
                corr_matrix[labels[i]][labels[j]] = c
    
    return {
        "matrix": corr_matrix,
        "period_start": str(period_start) if period_start else "",
        "period_end": str(period_end) if period_end else "",
        "fund_labels": labels,
        "common_dates": len(common_dates),
    }


def compute_pairwise_overlap(funds_data: dict) -> dict:
    """计算两两基金重叠度矩阵
    
    公式：
    1. 归一化：个股在前十大中的权重 = 个股占净值比例 / 前十大权重之和
    2. 重叠度 = Σ_{共同持仓} max(归一化权重_A, 归一化权重_B)，上限 100%
    
    只对两只基金共同持有的股票求和，取各自归一化权重的最大值。
    两只基金前十大完全相同且权重一致 → 100%；零共同持仓 → 0%。
    """
    fund_names = list(funds_data.keys())

    # 构建每只基金的归一化权重 {stock_code: normalized_weight}
    fund_holdings = {}
    for fname, holdings in funds_data.items():
        raw_weights = {}
        for h in holdings:
            code = h.get("stock_code", "")
            weight = h.get("weight", 0)
            if code and weight > 0:
                raw_weights[code] = weight
        total = sum(raw_weights.values())
        # 归一化：个股权重 / 前十大权重之和
        weight_map = {}
        if total > 0:
            for code, w in raw_weights.items():
                weight_map[code] = w / total
        fund_holdings[fname] = weight_map

    overlap_matrix = {}
    for f1 in fund_names:
        overlap_matrix[f1] = {}
        for f2 in fund_names:
            if f1 == f2:
                overlap_matrix[f1][f2] = 1.0
            elif f2 in overlap_matrix and f1 in overlap_matrix[f2]:
                overlap_matrix[f1][f2] = overlap_matrix[f2][f1]
            else:
                h1 = fund_holdings.get(f1, {})
                h2 = fund_holdings.get(f2, {})
                overlap_sum = 0.0
                # 只对共同持仓求和
                common_codes = set(h1.keys()) & set(h2.keys())
                for code in common_codes:
                    w1 = h1.get(code, 0)
                    w2 = h2.get(code, 0)
                    overlap_sum += max(w1, w2)
                # 上限 100%
                overlap_matrix[f1][f2] = round(min(overlap_sum, 1.0), 4)
    return overlap_matrix


def compute_concentration(funds_data: dict) -> dict:
    """计算组合层面集中度"""
    merged = defaultdict(float)  # {stock_code: total_weight}
    num_funds = len(funds_data)

    for fname, holdings in funds_data.items():
        for h in holdings:
            code = h.get("stock_code", "")
            weight = h.get("weight", 0) / 100.0
            if code and weight > 0:
                merged[code] += weight / num_funds  # equal fund weight

    total_w = sum(merged.values())
    if total_w > 0:
        for code in merged:
            merged[code] /= total_w

    hhi = sum(w * w for w in merged.values()) * 10000
    effective_n = 1.0 / sum(w * w for w in merged.values()) if merged else 0

    # 各基金有效持仓数
    fund_eff = {}
    for fname, holdings in funds_data.items():
        wmap = defaultdict(float)
        for h in holdings:
            w = h.get("weight", 0) / 100.0
            if w > 0:
                wmap[h.get("stock_code", "")] += w
        total = sum(wmap.values())
        if total > 0:
            for c in wmap:
                wmap[c] /= total
        fund_hhi = sum(w * w for w in wmap.values())
        fund_eff[fname] = round(1.0 / fund_hhi if fund_hhi > 0 else len(wmap), 1)

    avg_fund_eff = sum(fund_eff.values()) / len(fund_eff) if fund_eff else 0
    diversification_efficiency = round(effective_n / (avg_fund_eff * num_funds) * 100, 1) if avg_fund_eff > 0 else 0

    # 重叠个股排名
    stock_appearances = defaultdict(lambda: {"count": 0, "total_weight": 0, "max_weight": 0, "name": ""})
    for fname, holdings in funds_data.items():
        for h in holdings:
            code = h.get("stock_code", "")
            w = h.get("weight", 0)
            if code:
                stock_appearances[code]["count"] += 1
                stock_appearances[code]["total_weight"] += w
                stock_appearances[code]["max_weight"] = max(stock_appearances[code]["max_weight"], w)
                stock_appearances[code]["name"] = h.get("stock_name", code)

    overlap_stocks = sorted(
        [(k, v) for k, v in stock_appearances.items() if v["count"] >= 2],
        key=lambda x: x[1]["count"] * x[1]["total_weight"],
        reverse=True
    )

    return {
        "hhi": round(hhi, 1),
        "effective_n": round(effective_n, 1),
        "total_stocks": len(merged),
        "fund_eff_n": fund_eff,
        "avg_fund_eff_n": round(avg_fund_eff, 1),
        "div_efficiency": diversification_efficiency,
        "overlap_stocks": overlap_stocks,
    }


def analyze_fund_clusters(funds_data, overlap_matrix, concentration, corr_data=None):
    """分析基金赛道聚类 & 生成文字分析（机构投资者版本）"""
    fund_names = list(funds_data.keys())
    n = len(fund_names)

    # 计算统计量
    pairs = []
    for i in range(n):
        for j in range(i + 1, n):
            ov = overlap_matrix[fund_names[i]].get(fund_names[j], 0) * 100
            pairs.append((fund_names[i], fund_names[j], ov))
    pairs.sort(key=lambda x: x[2], reverse=True)

    avg_overlap = sum(p[2] for p in pairs) / len(pairs) if pairs else 0
    high_pairs = [p for p in pairs if p[2] > 60]
    mid_pairs = [p for p in pairs if 30 < p[2] <= 60]
    low_pairs = [p for p in pairs if p[2] <= 30]

    eff_n = concentration["effective_n"]
    hhi = concentration["hhi"]
    div_eff = concentration["div_efficiency"]

    # 1. 整体判定
    if avg_overlap > 70:
        verdict_level = "🔴 高度重叠"
        verdict_color = "red"
        verdict_text = (
            f"这{n}只基金的持仓结构高度相似（平均重叠度 {avg_overlap:.1f}%），"
            f"实质上形成了「虚假分散」——表面持有{n}只基金，底层却集中在极其相似的股票池中。"
            f"组合 HHI 达 {hhi:.0f}，分散效率仅 {div_eff:.0f}%，说明叠加多只基金并未显著提升分散度。"
        )
    elif avg_overlap > 30:
        verdict_level = f"🟡 中度重叠（最高 {pairs[0][2]:.0f}%）"
        verdict_color = "yellow"
        verdict_text = (
            f"这{n}只基金整体分散尚可（平均重叠度 {avg_overlap:.1f}%），"
            f"但存在 {len(high_pairs) + len(mid_pairs)} 对中高重叠组合，需重点关注。"
            f"组合 HHI 为 {hhi:.0f}，分散效率 {div_eff:.0f}%，"
            f"合并后有效持仓数为 {eff_n:.0f}，具有一定的分散效果，但特定基金对之间可能存在冗余配置。"
        )
    else:
        verdict_level = "🟢 分散优良"
        verdict_color = "green"
        verdict_text = (
            f"这{n}只基金的持仓结构差异显著（平均重叠度仅 {avg_overlap:.1f}%），"
            f"组合 HHI 仅 {hhi:.0f}，分散效率 {div_eff:.0f}%，"
            f"合并后有效持仓数达 {eff_n:.0f}，分散效果良好。"
            f"各基金经理的选股框架和赛道偏好存在明显差异化。"
        )

    # 2. 矩阵解读 — 逐对分析
    pair_analysis = ""
    for f1, f2, ov in pairs:
        if ov > 60:
            pair_analysis += f"<li>🔴 <strong>{f1[:20]} ↔ {f2[:20]}</strong>：重叠度 {ov:.1f}%，"
            pair_analysis += "两只基金持仓高度同质化，建议只保留其中一只，避免冗余配置。</li>"
        elif ov > 30:
            pair_analysis += f"<li>🟡 <strong>{f1[:20]} ↔ {f2[:20]}</strong>：重叠度 {ov:.1f}%，"
            pair_analysis += "存在明显的赛道/风格交集，建议关注共同持仓并评估是否需要调整比例。</li>"
        elif ov > 5:
            pair_analysis += f"<li>🟢 <strong>{f1[:20]} ↔ {f2[:20]}</strong>：重叠度 {ov:.1f}%，"
            pair_analysis += "个别标的略有交集但整体独立，分散效果可接受。</li>"
        else:
            pair_analysis += f"<li>🟢 <strong>{f1[:20]} ↔ {f2[:20]}</strong>：重叠度 {ov:.1f}%，"
            pair_analysis += "前十大持仓完全独立，分散效果优良。</li>"

    # 3. 赛道聚类推测（基于重叠度高的小团体）
    cluster_text = ""
    cluster_map = defaultdict(list)
    for f1, f2, ov in pairs:
        if ov > 30:
            cluster_map[f1].append((f2, ov))
            cluster_map[f2].append((f1, ov))

    if cluster_map:
        cluster_text = "<p>从重叠度矩阵可以看出以下潜在赛道聚类：</p><ul>"
        seen = set()
        for f in fund_names:
            if f in cluster_map and f not in seen:
                friends = [ff for ff, _ in cluster_map[f]]
                cluster_names = [f] + friends
                all_in = set(cluster_names)
                if all_in not in [set(g) for g in [seen]]:
                    seen.update(all_in)
                    names_str = "、".join(c[:15] for c in sorted(all_in))
                    avg_c = sum(ov for _, ov in cluster_map[f]) / len(cluster_map[f]) if cluster_map[f] else 0
                    cluster_text += f"<li><strong>{names_str}</strong>：平均重叠 {avg_c:.0f}%，"
                    cluster_text += "可能共享相似的行业/风格偏好，建议在同类中精简至1只。</li>"
        cluster_text += "</ul>"
    else:
        cluster_text = "<p>未检测到明显的赛道聚类，所有基金持仓差异足够大，不存在需精简的冗余对。</p>"

    # 4. 集中度解读
    if hhi > 2500:
        conc_interpret = "🔴 <strong>高度集中</strong>：合并后少数个股占据过大权重，组合风险集中于特定标的。"
    elif hhi > 1000:
        conc_interpret = "🟡 <strong>中度集中</strong>：组合有一定集中度，建议关注 HHI 的变化趋势。"
    else:
        conc_interpret = f"🟢 <strong>充分分散</strong>：HHI 仅 {hhi:.0f}，叠加{n}只基金后整体持仓均匀分布。"

    if div_eff < 50:
        div_interpret = f"⚠️ 分散效率仅 {div_eff:.0f}%，低于 50% 警戒线。虽然持有{n}只基金，但叠加后有效持仓提升有限，存在虚假分散风险。"
    elif div_eff < 80:
        div_interpret = f"分散效率 {div_eff:.0f}%，处于 50-80% 可接受区间，叠加多只基金有一定增量分散效果。"
    else:
        div_interpret = f"分散效率 {div_eff:.0f}%，超过 80% 优良线，叠加多只基金显著提升了整体分散度。"

    # 5. 重叠个股风险分析
    overlap_stocks = concentration.get("overlap_stocks", [])
    stock_risk = ""
    high_risk_stocks = [s for s in overlap_stocks[:10] if s[1]["count"] >= n / 2]
    if high_risk_stocks:
        stock_risk = "<p>⚠️ 以下个股出现在半数以上基金中，是组合层面最集中的风险来源：</p><ul>"
        for code, info in high_risk_stocks[:5]:
            stock_risk += f"<li><strong>{info['name']}</strong>：出现在 {info['count']}/{n} 只基金中，合计权重 {info['total_weight']:.1f}%</li>"
        stock_risk += "</ul>"
    elif overlap_stocks:
        stock_risk = f"<p>重叠个股主要集中在 {len(overlap_stocks)} 只标的上，但每只最多出现在 {max(s[1]['count'] for s in overlap_stocks)} 只基金中，风险相对可控。</p>"
    else:
        stock_risk = "<p>前十大持仓中无跨基金重叠标的，不同基金经理选股框架差异足够大。</p>"

    # 6. 综合配置建议（机构投资者版本）
    # ========================================
    
    # 提取相关性数据
    corr_pairs_list = []
    avg_corr = None
    min_corr = None
    max_corr = None
    if corr_data and corr_data.get("matrix"):
        corr_m = corr_data["matrix"]
        corr_labels = corr_data["fund_labels"]
        for i in range(len(corr_labels)):
            for j in range(i+1, len(corr_labels)):
                v = corr_m.get(corr_labels[i], {}).get(corr_labels[j], 0)
                corr_pairs_list.append((corr_labels[i], corr_labels[j], v))
        if corr_pairs_list:
            avg_corr = sum(p[2] for p in corr_pairs_list) / len(corr_pairs_list)
            min_corr = min(p[2] for p in corr_pairs_list)
            max_corr = max(p[2] for p in corr_pairs_list)
    
    # 构建完整的机构级建议
    suggestion_parts = []
    
    # --- Part A: 总体评估 ---
    suggestion_parts.append('<div class="advice-section">')
    suggestion_parts.append('<h3 style="font-size:14px;font-weight:600;margin-bottom:8px;">A. 总体评估</h3>')
    
    if avg_overlap > 60:
        risk_level = "高"
        risk_color = "#c62828"
    elif avg_overlap > 30 or (avg_corr and avg_corr > 0.8):
        risk_level = "中高"
        risk_color = "#ef6c00"
    elif avg_corr and avg_corr > 0.6:
        risk_level = "中等"
        risk_color = "#f57f17"
    else:
        risk_level = "较低"
        risk_color = "#2e7d32"
    
    suggestion_parts.append(f'<p>综合持仓重叠度（均值 {avg_overlap:.1f}%）与收益率相关性（均值 {avg_corr:.3f}）双维度评估，该组合的<b style="color:{risk_color}">实质分散风险等级为「{risk_level}」</b>。</p>')
    
    # 持仓分散 vs 走势趋同的矛盾
    if avg_corr and avg_overlap < 20 and avg_corr > 0.6:
        suggestion_parts.append('<p>⚠️ <b>持仓分散但走势趋同</b>：虽然前十大持仓重叠度较低，但收益率相关性均值达 '
            f'{avg_corr:.3f}，最低也有 {min_corr:.3f}。这表明所有成分基金共享同一风格因子（AI/科技成长）'
            '的系统性暴露。当该因子出现回撤时，组合将面临"分散失效"——净值同步下行，无法通过基金间差异对冲风险。</p>')
    elif avg_corr and avg_corr > 0.85:
        suggestion_parts.append(f'<p>🔴 <b>严重同质化</b>：持仓重叠与收益率相关性均处于高位（最大相关性 {max_corr:.3f}），组合本质上是对同一策略的重复暴露，未实现有效的风险分散。</p>')
    
    suggestion_parts.append('</div>')
    
    # --- Part B: 持仓层面核心发现 ---
    suggestion_parts.append('<div class="advice-section">')
    suggestion_parts.append('<h3 style="font-size:14px;font-weight:600;margin-bottom:8px;">B. 持仓维度核心发现</h3>')
    suggestion_parts.append('<ul>')
    
    # 高重叠对
    if high_pairs:
        for f1, f2, ov in high_pairs:
            suggestion_parts.append(f'<li><b>高重叠对</b>：{f1[:20]} 与 {f2[:20]}，前十大归一化重叠度 {ov:.1f}%。'
                f'两只基金在个股层面的暴露高度重合，建议<em>仅保留其中一只</em>，释放出的仓位配置到差异化赛道。</li>')
    
    # 中度重叠对
    if mid_pairs:
        for f1, f2, ov in mid_pairs[:3]:
            suggestion_parts.append(f'<li><b>中度重叠对</b>：{f1[:20]} 与 {f2[:20]}，重叠度 {ov:.1f}%。'
                f'共享部分子赛道标的，但选股框架仍有差异。可视作同一大类下的互补品种，但需注意共振风险。</li>')
    
    # 零重叠对
    zero_pairs = [p for p in pairs if p[2] == 0]
    if zero_pairs:
        names_set = set()
        for f1, f2, _ in zero_pairs:
            names_set.add(f1); names_set.add(f2)
        suggestion_parts.append(f'<li><b>完全独立对</b>：{len(zero_pairs)} 对基金前十大持仓零重叠，分布在 {len(names_set)} 只基金中。'
            f'这些组合在个股层面实现了完全差异化，是组合中真正的分散来源。</li>')
    
    # 集中度
    suggestion_parts.append(f'<li>组合 HHI = {hhi:.0f}（{"高度集中" if hhi>2500 else "中度集中" if hhi>1000 else "充分分散"}），'
        f'合并有效持仓数 {eff_n:.0f}，分散效率 {div_eff:.0f}%。'
        f'{"⚠️ 叠加多只基金后分散度提升有限" if div_eff<50 else ""}</li>')
    suggestion_parts.append('</ul></div>')
    
    # --- Part C: 业绩相关性层面 ---
    if corr_data:
        suggestion_parts.append('<div class="advice-section">')
        suggestion_parts.append('<h3 style="font-size:14px;font-weight:600;margin-bottom:8px;">C. 业绩相关性维度</h3>')
        suggestion_parts.append('<ul>')
        
        high_c = [(a,b,v) for a,b,v in corr_pairs_list if v > 0.9]
        mid_c = [(a,b,v) for a,b,v in corr_pairs_list if 0.7 < v <= 0.9]
        
        if high_c:
            items = "、".join(f"{a[:12]}↔{b[:12]}" for a,b,_ in high_c[:3])
            suggestion_parts.append(f'<li><b>极高正相关（ρ>0.9）</b>：{items}。这些基金对的净值走势几乎完全同步，'
                f'在组合中可视作同一风险暴露单元，建议合并处理。</li>')
        if mid_c:
            items = "、".join(f"{a[:12]}↔{b[:12]}" for a,b,_ in mid_c[:3])
            suggestion_parts.append(f'<li><b>中高正相关（0.7<ρ≤0.9）</b>：{items}。'
                f'虽有一定差异化空间，但在极端行情下大概率同向波动。</li>')
        
        suggestion_parts.append(f'<li>全组合相关性均值 {avg_corr:.3f}，最低 {min_corr:.3f}。'
            f'{"组合内不存在真正的低相关/负相关对，所有基金均为同一风格方向的暴露。若需降低组合波动率，需引入非AI/非科技赛道的品种（如红利低波、消费、医药等）。" if min_corr > 0.4 else ""}</li>')
        suggestion_parts.append('</ul></div>')
    
    # --- Part D: 具体配置方案 ---
    suggestion_parts.append('<div class="advice-section">')
    suggestion_parts.append('<h3 style="font-size:14px;font-weight:600;margin-bottom:8px;">D. 配置优化方案</h3>')
    
    if avg_overlap > 60:
        # 高度重叠：大幅精简
        suggestion_parts.append(f'<p><b>方案一（推荐）：精简至核心 1-2 只</b></p>')
        suggestion_parts.append(f'<p>当前组合过度冗余，建议仅保留规模适中、费率合理、回撤控制最优的品种作为核心持仓，剩余仓位配置至完全不同赛道的基金。</p>')
    elif avg_overlap > 30:
        suggestion_parts.append(f'<p><b>方案一（推荐）：去重 + 赛道均衡</b></p>')
        suggestion_parts.append(f'<p>针对 {len(high_pairs) + len(mid_pairs)} 对中高重叠基金：每对保留 1 只（优选流动性好、规模适中、风格稳定的），'
            f'可将组合基金数从 {n} 只精简至 {n - len(high_pairs) - max(0, len(mid_pairs)//2)} 只，同时保持赛道覆盖不降。</p>')
    else:
        suggestion_parts.append(f'<p><b>方案一（推荐）：等权配置 + 风格补缺</b></p>')
        suggestion_parts.append(f'<p>当前 {n} 只基金在个股层面分散度良好，可按等权或风险平价配置。建议在以下维度补缺：</p>')
        
    suggestion_parts.append('<ul>')
    suggestion_parts.append('<li><b>风格对冲</b>：当前组合高度集中于 AI/科技成长风格。建议配置 20-30% 仓位的非科技品种（如红利低波、消费龙头、医药主题），以降低组合整体波动率和最大回撤。</li>')
    suggestion_parts.append('<li><b>市值补缺</b>：如重仓均偏向中大盘成长，可考虑加入小盘价值或微盘策略基金，提升市值因子分散度。</li>')
    suggestion_parts.append('<li><b>跨境分散</b>：考虑加入 QDII 基金（如纳斯达克 100 或全球科技），分散单一市场系统性风险。</li>')
    suggestion_parts.append('</ul>')
    
    if n >= 4:
        suggestion_parts.append(f'<p><b>方案二（进取）：核心-卫星结构</b></p>')
        suggestion_parts.append(f'<p>核心仓位（60%）：选取 2 只持仓最分散、回撤控制最优的基金作为底仓；'
            f'卫星仓位（40%）：选取赛道纯度最高、锐度最强的 1-2 只基金作为弹性配置。'
            f'定期再平衡（建议季度），控制单一基金权重不超过 30%。</p>')
    
    suggestion_parts.append('</div>')
    
    # --- Part E: 风险监控框架 ---
    suggestion_parts.append('<div class="advice-section">')
    suggestion_parts.append('<h3 style="font-size:14px;font-weight:600;margin-bottom:8px;">E. 风险监控指标</h3>')
    suggestion_parts.append('<table style="font-size:12px;">')
    suggestion_parts.append('<thead><tr><th>监控指标</th><th>预警阈值</th><th>频率</th><th>触发动作</th></tr></thead>')
    suggestion_parts.append('<tr><td>持仓重叠度（均值）</td><td>>40%</td><td>每季报后</td><td>检查是否有风格漂移，评估是否需要调仓</td></tr>')
    suggestion_parts.append('<tr><td>收益率相关性（均值）</td><td>>0.85</td><td>月度</td><td>考虑引入低相关品种对冲</td></tr>')
    suggestion_parts.append('<tr><td>组合 HHI</td><td>>1500</td><td>每季报后</td><td>检查是否有个股过度集中</td></tr>')
    suggestion_parts.append('<tr><td>单一基金最大回撤</td><td>>-25%</td><td>周度</td><td>评估基金经理是否仍在有效执行策略</td></tr>')
    suggestion_parts.append('<tr><td>基金经理变更</td><td>任一</td><td>即时</td><td>立即启动替代基金评估流程</td></tr>')
    suggestion_parts.append('</table></div>')
    
    suggestion_parts.append('<div style="margin-top:16px;font-size:12px;color:#888;line-height:1.6;">')
    suggestion_parts.append('<b>免责声明：</b>本报告基于公开持仓数据与历史收益率序列的定量分析，所有建议均为数据驱动的参考框架，不构成具体投资指令。投资决策需结合市场环境、流动性约束、委托人风险偏好等因素综合判断。历史数据不代表未来表现。')
    suggestion_parts.append('</div>')
    
    suggestion = "\n".join(suggestion_parts)

    return {
        "verdict_level": verdict_level,
        "verdict_color": verdict_color,
        "verdict_text": verdict_text,
        "pair_analysis": pair_analysis,
        "cluster_text": cluster_text,
        "conc_interpret": conc_interpret,
        "div_interpret": div_interpret,
        "stock_risk": stock_risk,
        "suggestion": suggestion,
    }


def generate_html(funds_data, overlap_matrix, concentration, corr_data=None) -> str:
    """生成 HTML 报告（含文字分析 + 可选收益率相关性矩阵）"""
    fund_names = list(funds_data.keys())
    n = len(fund_names)
    avg_overlap = round(sum(
        overlap_matrix[f1].get(f2, 0)
        for i, f1 in enumerate(fund_names)
        for j, f2 in enumerate(fund_names)
        if i < j
    ) / (n * (n - 1) / 2) * 100 if n > 1 else 0, 1)

    eff_n = concentration["effective_n"]
    hhi = concentration["hhi"]
    div_eff = concentration["div_efficiency"]

    # 生成文字分析
    analysis = analyze_fund_clusters(funds_data, overlap_matrix, concentration, corr_data)

    # 热力图
    heatmap_html = '<table class="matrix"><tr><th></th>'
    for f in fund_names:
        short = f[:12] + ".." if len(f) > 14 else f
        heatmap_html += f'<th>{short}</th>'
    heatmap_html += '</tr>'

    for f1 in fund_names:
        short1 = f1[:12] + ".." if len(f1) > 14 else f1
        heatmap_html += f'<tr><th>{short1}</th>'
        for f2 in fund_names:
            val = overlap_matrix[f1].get(f2, 0) * 100
            if f1 == f2:
                bg = "#e0e0e0"
                color = "#999"
            elif val > 80:
                bg = "#c62828"; color = "#fff"
            elif val > 60:
                bg = "#e65100"; color = "#fff"
            elif val > 30:
                bg = "#fff8e1"; color = "#f57f17"
            else:
                bg = "#e8f5e9"; color = "#2e7d32"
            heatmap_html += f'<td style="background:{bg};color:{color};font-weight:700;">{val:.0f}%</td>'
        heatmap_html += '</tr>'
    heatmap_html += '</table>'

    # 各基金前十大持仓对比表（标红重复）
    # 先找出所有跨基金重复的股票代码
    stock_fund_map = defaultdict(set)
    for fname, holdings in funds_data.items():
        for h in holdings:
            code = h.get("stock_code", "")
            if code:
                stock_fund_map[code].add(fname)
    duplicate_stocks = {code for code, fset in stock_fund_map.items() if len(fset) >= 2}

    # 每只基金的前十大（按权重降序）
    fund_top10 = {}
    for fname, holdings in funds_data.items():
        sorted_h = sorted(holdings, key=lambda x: x.get("weight", 0), reverse=True)[:10]
        fund_top10[fname] = sorted_h

    # 生成对比表 HTML
    top10_rows = ""
    max_rows = max(len(v) for v in fund_top10.values())
    for rank in range(max_rows):
        top10_rows += f"<tr><td style='text-align:center;font-weight:600;color:#888;'>{rank+1}</td>"
        for fname in fund_names:
            if rank < len(fund_top10[fname]):
                h = fund_top10[fname][rank]
                stock = h.get("stock_name", h.get("stock_code", "?"))
                w = h.get("weight", 0)
                code = h.get("stock_code", "")
                # 标红重复持仓
                if code in duplicate_stocks:
                    bg = "#ffebee"
                    color = "#c62828"
                    marker = " 🔁"
                    style = f"background:{bg};color:{color};font-weight:700;"
                else:
                    style = ""
                    marker = ""
                top10_rows += f'<td style="{style}">{stock}<span style="font-size:11px;color:#888;"> ({w:.1f}%)</span>{marker}</td>'
            else:
                top10_rows += '<td style="color:#ccc;">—</td>'
        top10_rows += "</tr>\n"

    # 生成表头
    top10_header = '<tr><th style="text-align:center;width:40px;">#</th>'
    for fname in fund_names:
        short = fname[:16] + ".." if len(fname) > 18 else fname
        top10_header += f"<th>{short}</th>"
    top10_header += "</tr>"

    # 重复持仓图例
    dup_note = ""
    if duplicate_stocks:
        dup_count = len(duplicate_stocks)
        dup_examples = list(duplicate_stocks)[:5]
        dup_names = []
        for code in dup_examples:
            for fname, holdings in fund_top10.items():
                for h in holdings:
                    if h.get("stock_code") == code:
                        dup_names.append(h.get("stock_name", code))
                        break
                else:
                    continue
                break
        dup_note = f'<p style="font-size:12px;color:#c62828;margin-top:8px;">🔁 红色标记 = 跨基金重复持仓（共 {dup_count} 只个股），同时持有需注意集中风险</p>'
    conc_rows = ""
    for fname, eff in concentration["fund_eff_n"].items():
        short = fname[:15] + ".." if len(fname) > 17 else fname
        conc_rows += f'<tr><td>{short}</td><td style="text-align:center;">{eff}</td></tr>'

    # 重叠个股
    overlap_stocks_html = ""
    for code, info in concentration["overlap_stocks"][:10]:
        name = info["name"]
        count = info["count"]
        tw = info["total_weight"]
        mw = info["max_weight"]
        overlap_stocks_html += f"""
        <tr>
            <td>{name}</td>
            <td style="text-align:center;">{count}/{n}只基金</td>
            <td style="text-align:center;">{tw:.1f}%</td>
            <td style="text-align:center;">{mw:.1f}%</td>
        </tr>"""

    # FOF 配置建议（旧版兼容，新版用 analysis['suggestion']）
    advice = analysis.get('suggestion', '')

    # ===== 收益率相关性矩阵 =====
    corr_html = ""
    if corr_data and corr_data.get("matrix"):
        corr_labels = corr_data["fund_labels"]
        corr_m = corr_data["matrix"]
        corr_n = len(corr_labels)
        corr_html = '<div class="section"><div class="section-title">📈 收益率相关性矩阵</div>'
        corr_html += f'<p style="font-size:12px;color:#888;margin-bottom:12px;">基于近{corr_data.get("common_dates","?")}周收益率序列的 Pearson 相关系数 · 数据区间 {corr_data.get("period_start","")[:8]}~{corr_data.get("period_end","")[:8]}</p>'
        corr_html += '<table class="matrix"><tr><th></th>'
        for l in corr_labels:
            short = l[:12] + ".." if len(l) > 14 else l
            corr_html += f'<th>{short}</th>'
        corr_html += '</tr>'
        for l1 in corr_labels:
            short1 = l1[:12] + ".." if len(l1) > 14 else l1
            corr_html += f'<tr><th>{short1}</th>'
            for l2 in corr_labels:
                val = corr_m.get(l1, {}).get(l2, 0)
                if l1 == l2:
                    bg = "#e0e0e0"; color = "#999"
                elif val > 0.9:
                    bg = "#c62828"; color = "#fff"
                elif val > 0.7:
                    bg = "#e65100"; color = "#fff"
                elif val > 0.5:
                    bg = "#fff8e1"; color = "#f57f17"
                elif val > 0.2:
                    bg = "#e8f5e9"; color = "#2e7d32"
                else:
                    bg = "#e3f2fd"; color = "#1565c0"
                corr_html += f'<td style="background:{bg};color:{color};font-weight:700;">{val:.2f}</td>'
            corr_html += '</tr>'
        corr_html += '</table>'
        # 相关性解读
        corr_vals = []
        for i in range(corr_n):
            for j in range(i+1, corr_n):
                v = corr_m.get(corr_labels[i], {}).get(corr_labels[j], 0)
                corr_vals.append((corr_labels[i], corr_labels[j], v))
        corr_vals.sort(key=lambda x: x[2], reverse=True)
        
        high_corr = [(a,b,v) for a,b,v in corr_vals if v > 0.8]
        mid_corr = [(a,b,v) for a,b,v in corr_vals if 0.5 < v <= 0.8]
        low_corr = [(a,b,v) for a,b,v in corr_vals if v <= 0.5]
        
        corr_html += '<div style="display:flex;gap:16px;margin-top:12px;font-size:12px;">'
        corr_html += '<span>🔴 &gt;0.9 强正相关</span><span>🟠 0.7-0.9</span><span>🟡 0.5-0.7</span><span>🟢 0.2-0.5</span><span>🔵 &lt;0.2 弱/负相关</span>'
        corr_html += '</div>'
        
        corr_html += '<div class="text-block" style="margin-top:12px;">'
        if high_corr:
            items = "; ".join(f"{a[:12]}↔{b[:12]}:{v:.2f}" for a,b,v in high_corr[:5])
            corr_html += f'<p>🔴 <strong>强正相关</strong>：{items}。这些基金的净值走势高度同步，持有其中多只并不能降低组合波动。</p>'
        if mid_corr:
            items = "; ".join(f"{a[:12]}↔{b[:12]}:{v:.2f}" for a,b,v in mid_corr[:3])
            corr_html += f'<p>🟡 <strong>中等相关</strong>：{items}。有一定同涨同跌特征，可视作同一风格暴露。</p>'
        if low_corr:
            items = "; ".join(f"{a[:12]}↔{b[:12]}:{v:.2f}" for a,b,v in low_corr[:3])
            corr_html += f'<p>🟢 <strong>弱相关/独立</strong>：{items}。走势独立性较强，搭配持有可提升组合的波动平滑效果。</p>'
        corr_html += '</div></div>'

    html = f"""<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>持仓重叠分析 — {n}只基金</title>
<style>
* {{ margin:0; padding:0; box-sizing:border-box; }}
body {{ font-family: -apple-system, BlinkMacSystemFont, "Microsoft YaHei", sans-serif; background: #f5f6fa; color: #2c3e50; padding: 20px; }}
.header {{ text-align: center; padding: 24px 0 16px; background: linear-gradient(135deg, #1b5e20 0%, #2e7d32 100%); color: white; border-radius: 12px; margin-bottom: 20px; }}
.header h1 {{ font-size: 26px; font-weight: 700; margin-bottom: 4px; }}
.header .sub {{ font-size: 13px; opacity: 0.8; }}

.summary-cards {{ display:flex; gap:12px; margin-bottom:20px; flex-wrap:wrap; }}
.card {{ flex:1; min-width:140px; background:white; border-radius:10px; padding:16px; box-shadow:0 2px 8px rgba(0,0,0,0.05); text-align:center; }}
.card-label {{ font-size:12px; color:#999; margin-bottom:4px; }}
.card-value {{ font-size:28px; font-weight:700; }}

.section {{ background:white; border-radius:12px; padding:20px; box-shadow:0 2px 8px rgba(0,0,0,0.05); margin-bottom:16px; }}
.section-title {{ font-size:16px; font-weight:700; margin-bottom:16px; border-bottom:2px solid #f0f0f0; padding-bottom:8px; }}

.matrix {{ width:100%; border-collapse:collapse; font-size:12px; }}
.matrix th {{ background:#f5f5f5; padding:8px 6px; text-align:center; font-weight:600; white-space:nowrap; max-width:120px; overflow:hidden; }}
.matrix td {{ border:1px solid #eee; padding:8px 6px; text-align:center; }}

table {{ width:100%; border-collapse:collapse; font-size:13px; }}
th {{ background:#f5f5f5; padding:8px; text-align:left; font-weight:600; }}
td {{ padding:8px; border-bottom:1px solid #f0f0f0; }}

.analysis-list {{ padding-left:20px; line-height:2; font-size:13px; color:#444; }}

.advice {{ padding:16px; border-radius:10px; margin-top:12px; font-size:14px; line-height:1.6; }}
.advice.red {{ background:#fce4ec; border-left:4px solid #c62828; }}
.advice.yellow {{ background:#fff8e1; border-left:4px solid #f57f17; }}
.advice.green {{ background:#e8f5e9; border-left:4px solid #2e7d32; }}

.advice-section {{ margin-bottom:16px; font-size:13px; line-height:1.8; }}
.advice-section h3 {{ border-bottom:1px solid #e0e0e0; padding-bottom:4px; }}
.advice-section ul {{ padding-left:20px; margin:8px 0; }}
.advice-section li {{ margin-bottom:6px; }}
.advice-section table {{ font-size:12px; }}
.advice-section table th {{ font-size:12px; padding:6px 8px; }}
.advice-section table td {{ font-size:12px; padding:6px 8px; }}

.text-block {{ font-size:13px; line-height:1.8; color:#444; margin-bottom:8px; }}
.text-block p {{ margin-bottom:8px; }}
.text-block ul {{ padding-left:20px; margin-bottom:8px; }}
.text-block li {{ margin-bottom:4px; }}

.holdings-table td {{ font-size:12px; white-space:nowrap; }}
.holdings-table .dup {{ background:#ffebee; color:#c62828; font-weight:700; }}

.footer {{ text-align:center; color:#bbb; font-size:12px; margin-top:20px; padding:10px; }}
</style>
</head>
<body>

<div class="header">
    <h1>持仓重叠分析</h1>
    <div class="sub">{n} 只基金 · 平均两两重叠度 {avg_overlap}% · {datetime.now().strftime("%Y-%m-%d")}</div>
</div>

<div class="summary-cards">
    <div class="card">
        <div class="card-label">基金数量</div>
        <div class="card-value" style="color:#1565c0;">{n}</div>
    </div>
    <div class="card">
        <div class="card-label">合并有效持仓数</div>
        <div class="card-value" style="color:#2e7d32;">{eff_n}</div>
    </div>
    <div class="card">
        <div class="card-label">HHI 指数</div>
        <div class="card-value" style="color:{'#c62828' if hhi>2500 else '#f57f17' if hhi>1000 else '#2e7d32'};">{hhi:.0f}</div>
    </div>
    <div class="card">
        <div class="card-label">分散效率</div>
        <div class="card-value" style="color:{'#c62828' if div_eff<50 else '#f57f17' if div_eff<80 else '#2e7d32'};">{div_eff}%</div>
    </div>
    <div class="card">
        <div class="card-label">平均两两重叠度</div>
        <div class="card-value" style="color:{'#c62828' if avg_overlap>70 else '#f57f17' if avg_overlap>40 else '#2e7d32'};">{avg_overlap}%</div>
    </div>
</div>

<!-- ===== 各基金前十大持仓对比表 ===== -->
<div class="section">
    <div class="section-title">📋 各基金前十大重仓对比（标红=跨基金重复持仓）</div>
    <div style="overflow-x:auto;">
    <table>
        <thead>{top10_header}</thead>
        <tbody>{top10_rows}</tbody>
    </table>
    </div>
    {dup_note}
</div>

<!-- ===== 矩阵 + 逐对解读 ===== -->
<div class="section">
    <div class="section-title">📊 两两重叠度矩阵</div>
    {heatmap_html}
    <div style="display:flex;gap:16px;margin-top:12px;font-size:12px;">
        <span>🔴 &gt;80% 高度重叠</span><span>🟠 60-80%</span><span>🟡 30-60%</span><span>🟢 &lt;30%</span>
    </div>
</div>

<div class="section">
    <div class="section-title">📝 逐对重叠度解读</div>
    <ul class="analysis-list">
        {analysis['pair_analysis']}
    </ul>
</div>

<!-- ===== 收益率相关性矩阵 ===== -->
{corr_html}

<!-- ===== 赛道聚类 ===== -->
<div class="section">
    <div class="section-title">🏷️ 赛道聚类分析</div>
    <div class="text-block">
        {analysis['cluster_text']}
    </div>
</div>

<!-- ===== 集中度 + 文字解读 ===== -->
<div class="section">
    <div class="section-title">📈 组合集中度</div>
    <div style="display:grid;grid-template-columns: 1fr 1fr; gap:16px;">
        <div>
            <div style="font-size:13px;font-weight:600;margin-bottom:8px;">各基金有效持仓数</div>
            <table>
                <thead><tr><th>基金</th><th>有效持仓数</th></tr></thead>
                <tbody>{conc_rows if conc_rows else '<tr><td colspan="2" style="color:#ccc;">—</td></tr>'}</tbody>
            </table>
        </div>
        <div>
            <div style="font-size:13px;font-weight:600;margin-bottom:8px;">合并组合</div>
            <table>
                <tr><td>总股票数</td><td style="font-weight:700;text-align:right;">{concentration['total_stocks']}</td></tr>
                <tr><td>有效持仓数</td><td style="font-weight:700;text-align:right;color:#2e7d32;">{eff_n}</td></tr>
                <tr><td>HHI</td><td style="font-weight:700;text-align:right;">{hhi:.0f}</td></tr>
                <tr><td>单基金均值</td><td style="text-align:right;">{concentration['avg_fund_eff_n']}</td></tr>
                <tr><td>分散效率</td><td style="font-weight:700;text-align:right;color:{'#c62828' if div_eff<50 else '#f57f17' if div_eff<80 else '#2e7d32'};">{div_eff}%</td></tr>
            </table>
        </div>
    </div>
    <div class="text-block" style="margin-top:16px;">
        <p>{analysis['conc_interpret']}</p>
        <p>{analysis['div_interpret']}</p>
    </div>
</div>

<!-- ===== 重叠个股 + 风险分析 ===== -->
<div class="section">
    <div class="section-title">🎯 重叠个股曝光 Top 10</div>
    <table>
        <thead><tr><th>股票</th><th>覆盖</th><th>合计权重</th><th>最大单基权重</th></tr></thead>
        <tbody>{overlap_stocks_html if overlap_stocks_html else '<tr><td colspan="4" style="color:#ccc;">无显著重叠个股</td></tr>'}</tbody>
    </table>
    <div class="text-block" style="margin-top:12px;">
        {analysis['stock_risk']}
    </div>
</div>

<!-- ===== 综合配置建议 ===== -->
<div class="section">
    <div class="section-title">📋 综合配置建议</div>
    {analysis['suggestion']}
    {"<p style='margin-top:8px;font-size:13px;color:#c62828;'>⚠️ 分散效率仅 {div_eff}%，表明 N 只基金实质上仅覆盖了相当于 {eff_n:.0f} 只个股的有效分散。考虑替换高重叠基金或补充差异化品种。</p>" if div_eff < 50 else ""}
</div>

<div class="footer">
    数据来源：cjpy 基金持股明细 · 生成时间：{datetime.now().strftime("%Y-%m-%d %H:%M")} · 仅供参考
</div>

</body>
</html>"""

    return html


def main():
    parser = argparse.ArgumentParser(description="持仓重叠分析引擎")
    parser.add_argument("--data", help="JSON 数据文件路径")
    parser.add_argument("--output", help="输出 HTML 路径")
    parser.add_argument("--corr-codes", help="计算收益率相关性的基金代码（逗号分隔，如 OF018815,OF501046）")
    parser.add_argument("--corr-labels", help="相关性矩阵的基金名称（逗号分隔，与codes一一对应）")
    args = parser.parse_args()

    if args.data:
        data_path = Path(args.data)
        with open(data_path, "r", encoding="utf-8") as f:
            data = json.load(f)
    else:
        print("请提供 --data 参数指定 JSON 数据文件")
        sys.exit(1)

    funds_data = data.get("funds", {})
    overlap_matrix = compute_pairwise_overlap(funds_data)
    concentration = compute_concentration(funds_data)

    # 可选：收益率相关性
    corr_data = None
    if args.corr_codes:
        codes = [c.strip() for c in args.corr_codes.split(",")]
        labels = None
        if args.corr_labels:
            labels = [l.strip() for l in args.corr_labels.split(",")]
        corr_data = compute_return_correlation(codes, labels)

    html = generate_html(funds_data, overlap_matrix, concentration, corr_data)

    output_path = args.output or f"outputs/portfolio_overlap_{datetime.now().strftime('%Y%m%d')}.html"
    Path(output_path).parent.mkdir(parents=True, exist_ok=True)
    Path(output_path).write_text(html, encoding="utf-8")
    print(f"✅ 持仓重叠分析报告已生成：{Path(output_path).resolve()}")

    # 摘要
    fund_names = list(funds_data.keys())
    n = len(fund_names)
    total_pairs = n * (n - 1) / 2
    high_overlap = sum(1 for i, f1 in enumerate(fund_names) for j, f2 in enumerate(fund_names) if i < j and overlap_matrix[f1].get(f2, 0) > 0.6)
    print(f"\n📊 分析摘要：")
    print(f"  基金数量: {n}")
    print(f"  合并有效持仓数: {concentration['effective_n']}")
    print(f"  平均两两重叠度: {round(sum(overlap_matrix[f1].get(f2,0) for i,f1 in enumerate(fund_names) for j,f2 in enumerate(fund_names) if i<j)/(total_pairs)*100 if total_pairs>0 else 0,1)}%")
    print(f"  高重叠对(>60%): {high_overlap}/{int(total_pairs)}")
    print(f"  分散效率: {concentration['div_efficiency']}%")


if __name__ == "__main__":
    main()
