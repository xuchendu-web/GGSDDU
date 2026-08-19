"""
平台突破 HTML 图表生成器
========================
生成 ECharts 交互式 K线 + 布林带 + 转折点 + 阻力位 图表。
可作为命令行工具或 import 使用。

用法:
  python chart.py SH600000                    # 默认最近400天
  python chart.py SH600000 20250101 20260729   # 指定日期范围
"""

import sys, json, os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import cjpy, numpy as np, pandas as pd
from breakout import (
    calc_bollinger_bands, identify_high_lows, hsar_resistance,
    prepare_df_from_cjpy, DEFAULT_PARAMS,
)

# 图表最近多少个交易日
CHART_DAYS = 120

def generate_chart(code, start="20250101", end=None, output_dir=None, chart_days=CHART_DAYS):
    """
    生成单只股票的平台突破 HTML 图表。

    Parameters:
        code: 股票代码 (天软格式, 如 'SH600000')
        start: 起始日期 'yyyymmdd'
        end: 结束日期, 默认今天
        output_dir: 输出目录, 默认当前工作目录
        chart_days: 图表展示的最近交易日数

    Returns:
        (html_path, result_dict)
    """
    if end is None:
        end = pd.Timestamp.now().strftime("%Y%m%d")
    if output_dir is None:
        output_dir = os.getcwd()

    # 获取数据
    raw = cjpy.get_market_data(code, start, end, cycle="day", rate="前复权")
    if raw is None or len(raw) == 0:
        raise ValueError(f"无法获取 {code} 行情数据")

    name = str(raw['简称'].iloc[0]) if '简称' in raw.columns else code
    df = prepare_df_from_cjpy(raw, code)

    # 获取因子
    try:
        f = cjpy.get_factor_data(code=[code], date=[end], factors=["换手率", "总市值"])
        if f is not None and len(f) > 0:
            if '换手率' in f.columns: df['turn'] = float(f['换手率'].iloc[0])
            if '总市值' in f.columns: df['cap'] = float(f['总市值'].iloc[0])
    except:
        pass

    # 计算布林带与转折点
    df_bb = calc_bollinger_bands(df)
    points, direction = identify_high_lows(df_bb)
    high_points = [p for p in points if p.point_type == 'high']
    resistance = hsar_resistance(df_bb, high_points)

    # 取最近 N 个交易日
    chart_df = df_bb.iloc[-chart_days:].copy()
    dates = [str(d.date()) for d in chart_df.index]

    # 价格序列
    def safe_vals(col):
        return [round(float(x), 2) if not pd.isna(x) else None for x in chart_df[col]]

    close_data = safe_vals('close')
    open_data = safe_vals('open')
    high_data = safe_vals('high')
    low_data = safe_vals('low')
    ub_data = safe_vals('UB')
    ma_data = safe_vals('MA')
    lb_data = safe_vals('LB')

    # 转折点标记 (筛选图表范围内的)
    high_markers = []
    low_markers = []
    for p in points:
        pdate = str(pd.Timestamp(p.date).date())
        if pdate in dates:
            idx = dates.index(pdate)
            if p.point_type == 'high':
                high_markers.append({'coord': [pdate, round(p.price, 2)]})
            else:
                low_markers.append({'coord': [pdate, round(p.price, 2)]})

    # 阻力位
    res_price = resistance.price if resistance else None
    res_date = resistance.effective_date if resistance else None

    # 概要
    latest = chart_df.iloc[-1]
    ub_v = float(latest['UB']) if not pd.isna(latest.get('UB')) else None
    summary = {
        'name': name, 'code': code, 'date': dates[-1],
        'close': round(float(latest['close']), 2),
        'direction': direction,
        'ub': round(ub_v, 2) if ub_v else None,
        'ma': round(float(latest['MA']), 2) if not pd.isna(latest.get('MA')) else None,
        'lb': round(float(latest['LB']), 2) if not pd.isna(latest.get('LB')) else None,
        'pct_to_ub': round((float(latest['close'])/ub_v-1)*100, 2) if ub_v and ub_v > 0 else None,
        'resistance': res_price,
        'resistance_date': res_date,
    }

    # 构建 HTML
    html = _build_html(name, code, dates, open_data, close_data, high_data, low_data,
                       ub_data, ma_data, lb_data, high_markers, low_markers,
                       res_price, summary)

    # 写入文件
    safe_name = code.replace('.', '_')
    html_path = os.path.join(output_dir, f"breakout_{safe_name}.html")
    with open(html_path, 'w', encoding='utf-8') as f:
        f.write(html)

    return html_path, summary


def _build_html(name, code, dates, open_data, close_data, high_data, low_data,
                ub_data, ma_data, lb_data, high_markers, low_markers,
                res_price, summary):
    """构建 HTML 模板"""

    tl = f'{dates[0]} ~ {dates[-1]}'
    dir_text = "↑ 上升" if summary['direction'] == 'up' else "↓ 下降"
    dir_class = "up" if summary['direction'] == 'up' else "down"
    ub_str = f"{summary['ub']}" if summary['ub'] else "N/A"
    pct_str = f"{summary['pct_to_ub']:+.1f}%" if summary['pct_to_ub'] is not None else "N/A"
    res_str = f"{res_price}" if res_price else "无"
    res_sub = f"HSAR {summary['resistance_date']}" if summary.get('resistance_date') else "暂无有效阻力位"

    html = f'''<!DOCTYPE html>
<html lang="zh">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>{name}({code}) 平台突破分析</title>
<script src="https://cdn.jsdelivr.net/npm/echarts@5.5.0/dist/echarts.min.js"></script>
<style>
*{{margin:0;padding:0;box-sizing:border-box}}
body{{font-family:"Microsoft YaHei","PingFang SC",sans-serif;background:#f5f7fa;padding:20px}}
.container{{max-width:1100px;margin:0 auto}}
.header{{background:#fff;border-radius:12px;padding:20px 24px;margin-bottom:16px;box-shadow:0 1px 4px rgba(0,0,0,.06)}}
.header h1{{font-size:22px;color:#1a1a2e}}
.header .sub{{color:#888;font-size:13px;margin-top:4px}}
.cards{{display:grid;grid-template-columns:repeat(4,1fr);gap:12px;margin-bottom:16px}}
.card{{background:#fff;border-radius:10px;padding:16px;text-align:center;box-shadow:0 1px 4px rgba(0,0,0,.04)}}
.card .label{{font-size:12px;color:#999;margin-bottom:6px}}
.card .value{{font-size:22px;font-weight:700}}
.card .sub-val{{font-size:12px;color:#888;margin-top:2px}}
.chart-box{{background:#fff;border-radius:12px;padding:16px;box-shadow:0 1px 4px rgba(0,0,0,.04)}}
.chart-box h2{{font-size:16px;color:#333;margin-bottom:12px;padding-left:8px;border-left:3px solid #4e79f6}}
#mainChart{{width:100%;height:520px}}
.legend{{display:flex;gap:20px;justify-content:center;margin-top:12px;font-size:12px;color:#666;flex-wrap:wrap}}
.legend span{{display:flex;align-items:center;gap:4px}}
.legend .dot{{display:inline-block;width:10px;height:10px;border-radius:50%}}
.up{{color:#e74c3c}}.down{{color:#27ae60}}
</style>
</head>
<body>
<div class="container">
<div class="header">
<h1>{name} <span style="font-size:14px;color:#888;">{code}</span></h1>
<div class="sub">平台突破分析 · 最近{len(dates)}个交易日 · {tl}</div>
</div>
<div class="cards">
<div class="card"><div class="label">最新收盘</div><div class="value">{summary['close']}</div><div class="sub-val">{summary['date']}</div></div>
<div class="card"><div class="label">趋势方向</div><div class="value {dir_class}">{dir_text}</div><div class="sub-val">布林带趋势分段</div></div>
<div class="card"><div class="label">布林上轨</div><div class="value">{ub_str}</div><div class="sub-val">收盘距上轨 {pct_str}</div></div>
<div class="card"><div class="label">阻力位</div><div class="value">{res_str}</div><div class="sub-val">{res_sub}</div></div>
</div>
<div class="chart-box">
<h2>K线走势 · 布林带 · 转折点 · 阻力位</h2>
<div id="mainChart"></div>
<div class="legend">
<span><span class="dot" style="background:#4e79f6"></span>布林上/下轨</span>
<span><span class="dot" style="background:#ff9800"></span>布林中轨(MA20)</span>
<span><span class="dot" style="background:#e74c3c"></span>局部高点</span>
<span><span class="dot" style="background:#27ae60"></span>局部低点</span>
<span><span style="border-bottom:2px dashed #e91e63;padding:0 4px">阻力位</span></span>
</div>
</div>
</div>
<script>
var rp={json.dumps(res_price)};
var chart=echarts.init(document.getElementById("mainChart"));
var kd=[];
for(var i=0;i<{json.dumps(len(dates))};i++){{
  kd.push([{json.dumps(open_data)}[i],{json.dumps(close_data)}[i],{json.dumps(low_data)}[i],{json.dumps(high_data)}[i]]);
}}
chart.setOption({{
  tooltip:{{trigger:"axis",axisPointer:{{type:"cross"}},
    formatter:function(p){{
      var d=p[0].axisValue,h="<b>"+d+"</b><br/>";
      p.forEach(function(x){{
        if(x.seriesName==="K线"){{
          var k=x.data;if(Array.isArray(k)&&k.length>=4){{
            var o=k[1],c=k[2],l=k[3],hi=k[4]||k[0],chg=c-o,pct=(chg/o*100).toFixed(2);
            h+="开:"+o+" 收:"+c+" 高:"+hi+" 低:"+l+"<br/>";
            h+="涨跌:<b style=\"color:"+(chg>=0?"#e74c3c":"#27ae60")+"\">"+(chg>=0?"+":"")+chg.toFixed(2)+" ("+(chg>=0?"+":"")+pct+"%)</b>";
          }}
        }}
      }});return h;
    }}
  }},
  grid:{{left:"8%",right:"6%",top:20,bottom:40}},
  xAxis:{{type:"category",data:{json.dumps(dates)},
    axisLine:{{lineStyle:{{color:"#ccc"}}}},
    axisLabel:{{fontSize:10,color:"#888",formatter:function(v){{return v.slice(5)}}}}
  }},
  yAxis:{{type:"value",scale:true,splitLine:{{lineStyle:{{color:"#f0f0f0"}}}},
    axisLabel:{{fontSize:10,color:"#888"}}
  }},
  series:[
    {{name:"布林上轨",type:"line",data:{json.dumps(ub_data)},lineStyle:{{color:"#4e79f6",width:1,type:"dashed"}},symbol:"none",smooth:true,z:1}},
    {{name:"布林中轨",type:"line",data:{json.dumps(ma_data)},lineStyle:{{color:"#ff9800",width:1.5}},symbol:"none",smooth:true,z:1}},
    {{name:"布林下轨",type:"line",data:{json.dumps(lb_data)},lineStyle:{{color:"#4e79f6",width:1,type:"dashed"}},symbol:"none",smooth:true,z:1,areaStyle:{{color:"rgba(78,121,246,0.04)"}}}},
    {f'''{{name:"阻力位",type:"line",data:new Array({len(dates)}).fill(rp),
      lineStyle:{{color:"#e91e63",width:2,type:"dashed"}},symbol:"none",z:2,
      markLine:{{silent:true,symbol:"none",lineStyle:{{color:"#e91e63",type:"dashed",width:2}},
        label:{{formatter:"阻力 ¥"+rp,fontSize:11,color:"#e91e63"}},data:[{{yAxis:rp}}]}}}},''' if res_price else ''}
    {{name:"K线",type:"candlestick",data:kd,z:3,
      itemStyle:{{color:"#e74c3c",color0:"#27ae60",borderColor:"#e74c3c",borderColor0:"#27ae60"}},
      markPoint:{{symbol:"pin",symbolSize:30,data:[
        {','.join(f'{{name:"H {m["coord"][1]}",coord:{json.dumps(m["coord"])},value:"H",itemStyle:{{color:"#e74c3c"}},label:{{fontSize:9,color:"#fff"}}}}' for m in high_markers)}
        {',' if high_markers and low_markers else ''}
        {','.join(f'{{name:"L {m["coord"][1]}",coord:{json.dumps(m["coord"])},value:"L",itemStyle:{{color:"#27ae60"}},label:{{fontSize:9,color:"#fff"}}}}' for m in low_markers)}
      ]}}
    }}
  ]
}});
window.addEventListener("resize",function(){{chart.resize()}});
</script>
</body>
</html>'''
    return html


# CLI
if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("用法: python chart.py <code> [start_date] [end_date]")
        print("示例: python chart.py SH600000 20250101 20260729")
        sys.exit(1)

    code = sys.argv[1]
    start = sys.argv[2] if len(sys.argv) > 2 else "20250101"
    end = sys.argv[3] if len(sys.argv) > 3 else None

    path, summary = generate_chart(code, start, end)
    print(f"✅ {path}")
    print(f"   {summary['name']}({code}): 收盘 {summary['close']} | "
          f"方向 {summary['direction']} | 阻力 {summary['resistance']}")
