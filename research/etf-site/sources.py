BENCH=dict(name="中证偏股基金指数 930950",csv="/workspace/strategy-weekly/etf_replace_only_436/from2016_aum2/excess_daily_vs_930950.csv",col="bm_nav")
"""Data sources: every page pulls from workspace files (refreshable by cron)."""
W = "/workspace"
STRATEGIES = [  # ETF项目
 dict(slug="champion", name="冠军主钉 · 行业ETF轮动", status="现任冠军（模拟实盘）",oneliner="市场普涨时持有最强的≤5只行业ETF，普跌时全部空仓。",book="/workspace/strategy_exec/books/champion_mast.json",
      csv=f"{W}/strategy-weekly/spike_mom_rank/SPIKE-SHARPE20-LIVE1430/equity.csv", col="LIVE1430-AUM-max5",
      rules=["宇宙：A股行业ETF池（replace-only，436 槽）","开关：宽度 breadth ≥45%（站上 MA20 的比例），否则全现金",
             "选股：spike_ft 冲击形态，最多 5 只，按 AUM 填席","仓位：TV25 目标波动，实盘 L≤1；E0",
             "时点：周五 ≥14:30 信号 / 收盘成交，扣 0.2% 双边"],
      note="回测口径（LIVE1430），非实盘业绩。"),
 dict(slug="fcf35", name="红利袖 · FCF@3.5 动态", status="研究完成",oneliner="买自由现金流为正、股息率高的 30 只个股，股息率加权。",
      csv=f"{W}/div30/nav_a30_dyn35_fcf.csv", col="A30_yw_dyn35_fcf3y_cost",
      rules=["高股息池 A30，股息率加权","动态门槛 3.5%，3 年自由现金流为正过滤","含交易成本"],
      note="个股组合回测，非 ETF；作为固收+/组合的权益袖参考。"),
]
FUTURE = [("XS-MOM","截面动量 12-1","过去一年（剔除最近一周）涨得最多的 5 只行业ETF，等权持有。","10/18"),
 ("TS-MOM","时序动量","每只ETF自己过去一年为正才持有，否则空仓。","10/18"),
 ("DUAL-MOM","双动量","既要排名靠前，又要自身上涨，否则空仓。","10/20"),
 ("RA-MOM","风险调整动量","按“涨幅/波动”排序，少追高波动品种。","10/20"),
 ("ACC-MOM","加速度动量","短期动量减长期动量，抓刚开始加速的板块。","10/22"),
 ("RES-MOM","残差动量","扣掉大盘涨跌后，选真正强的行业。","10/22"),
 ("MOM+VOL","动量+目标波动","最佳动量策略 + 目标波动率控仓，压回撤。","10/27")]
MOMENTUM_DIR = f"{W}/etf-momentum"   # <ID>/nav.csv(date,nav) + REPORT.md
TREND_DIR = f"{W}/etf-trend"
# 趋势轨：未证伪进主对比表；证伪/止损标 status，有 nav 可进页但不进主表
TREND = [
 dict(id="T-MA", name="T-MA · 周收>MA60", oneliner="逐只 ETF 价上 MA60 才持有，否则货币；约半仓+弱择时。",
      col="T-MA MA60", status="未证伪", in_cmp=True, tag="核心旁注"),
 dict(id="T-TSM", name="T-TSM · TSM26", oneliner="26 周时间序列动量为正才持有；与 T-MA 同质旁注。",
      col="T-TSM TSM26", status="未证伪", in_cmp=True, tag="核心旁注"),
 dict(id="T-ADX", name="T-ADX · ADX>20", oneliner="MA60 之上再过滤 ADX>20；回撤最浅，仓位约三成。",
      col="T-ADX ADX>20", status="未证伪", in_cmp=True, tag="半仓择时"),
 dict(id="T-MAX", name="T-MAX · 双均线", oneliner="MA20/MA60 金叉持有。",
      col="T-MAX MA20/60", status="实质失效", in_cmp=False, tag="证伪"),
 dict(id="T-DON", name="T-DON · 唐奇安", oneliner="破 N 周高入、破 M 周低出。",
      col="T-DON DON20/10", status="证伪(非早入场)", in_cmp=False, tag="证伪"),
 dict(id="T-ATR", name="T-ATR · ATR止损", oneliner="MA60 入场 + k×ATR 追踪止损。",
      col="T-ATR ATR k3", status="证伪", in_cmp=False, tag="证伪"),
 dict(id="T-VOL", name="T-VOL · 趋势+TV", oneliner="ADX 底座叠 TV25；TV 几乎不触发已止损。",
      col=None, status="止损", in_cmp=False, tag="止损"),
]
# 多频可用积木：有独立主版 nav 则加载；否则用 SUMMARY 静态行
MULTIFREQ = [
 dict(id="MF-6040", name="多频 · 固定60/40", oneliner="周频 T-MA60（A宽基）60% + 债腿 B1 40%；核心压舱。",
      csv=f"{W}/etf-multifreq/MF-C2/nav.csv", col="固定60/40(T-MA60/B1)",
      status="可用·核心", in_cmp=True, tag="核心压舱",
      # SUMMARY 10-17 手填兜底（nav 缺列时）
      summary=dict(ret="37.9%", mdd="-9.4%", calmar="0.52", src="etf-multifreq/SUMMARY 10-17")),
 dict(id="MF-B4", name="多频 · B4 逆波动", oneliner="行业 XS52 取5 + 60日逆波动加权；卫星旁注，不单飞。",
      csv=f"{W}/etf-multifreq/MF-B4/nav.csv", col="MF-B4 XS52取5·逆波动加权(主版)",
      status="未证伪·旁注", in_cmp=True, tag="卫星旁注",
      summary=dict(ret="116.7%", mdd="-42.8%", calmar="0.28", src="etf-multifreq/SUMMARY 10-17")),
]
# 三轨对照（SUMMARY 原文数字，不新算）——供 projects 页「三轨对照」小节
TRACK_COMPARE = {
 "footnote": "口径：周五≥14:30、收盘成交、0.2%RT、L≤1。动量 v1016（→10-16）、趋势 →10-16、多频 10-17。不换冠军、不下单。",
 "tracks": [
  dict(name="动量", usable="MOM-VOL（XS52+TV25）旁注：147.6% / −30.7% / Calmar 0.47；仍逊冠军",
       dead="TS / DUAL / RA / ACC / RES、FILTER-FIRST、R4b 等已证伪；RA-TV-ROBUST 窗长脆弱不作主结论",
       src="etf-momentum/SUMMARY v1016"),
  dict(name="趋势", usable="T-MA60、T-TSM26、T-ADX>20 三条旁注（半仓择时）；收益 38–45% 不接近冠军",
       dead="T-MAX / T-DON / T-ATR / T-VOL / COMBO-EW·RP 证伪或止损",
       src="etf-trend/SUMMARY →10-16"),
  dict(name="多频", usable="固定 60/40（T-MA60:B1）核心压舱 37.9%/−9.4%/0.52；B4 逆波动卫星旁注、不单飞",
       dead="日频 A 线、合层 STACK v1–v4 全部暂停",
       src="etf-multifreq/SUMMARY 10-17"),
 ],
}
PORTFOLIOS = [  # 模拟组合
 dict(slug="champion", name="冠军主钉 ETF 轮动",enabled=True,oneliner="行业ETF轮动，开关关闭时100%现金。", book=f"{W}/strategy_exec/books/champion_mast.json",
      csv=f"{W}/strategy-weekly/spike_mom_rank/SPIKE-SHARPE20-LIVE1430/equity.csv", col="LIVE1430-AUM-max5"),
 dict(slug="fiplus", name="固收+ E2",enabled=True,  # ← 改 False 即隐藏固收+
      oneliner="约80%债券ETF底仓 + 15–22%权益（冠军/红利低波），目标稳健。", book=f"{W}/strategy_exec/books/fixed_income_plus.json",
      csv=f"{W}/strategy-weekly/fi_plus_champ_fill/equity.csv", col="long_02"),
 dict(slug="fcf35", name="红利袖 FCF@3.5",enabled=True,oneliner="高股息+正自由现金流个股组合。", book=None,
      csv=f"{W}/div30/nav_a30_dyn35_fcf.csv", col="A30_yw_dyn35_fcf3y_cost"),
]
MARKET_DIRS = [f"{W}/weekly-tape-review"]  # 只放盘面复盘；不含个人持仓
