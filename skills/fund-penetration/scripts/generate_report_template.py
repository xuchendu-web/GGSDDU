"""
Generate HTML penetration & Brinson attribution report
"""
import json

with open('/tmp/penetration_results.json', 'r') as f:
    data = json.load(f)

s = data['summary']
num_funds = s['num_funds']

ind_data = data['industry_comparison']
brinson_data = data['brinson']
stock_data = data['stock_contribution']
fund_data = data['fund_info']

pos_color = '#e74c3c'
neg_color = '#27ae60'

def color_pct(v):
    if v is None: return '#333'
    c = pos_color if v > 0 else neg_color if v < 0 else '#333'
    sign = '+' if v > 0 else ''
    return '<span style="color:' + c + '">' + sign + '%.2f' % v + '%</span>'

def plain_pct(v):
    if v is None: return '--'
    return '%.2f%%' % v

# Build industry chart data
ind_labels = []
port_weights = []
bm_weights = []
for d in sorted(ind_data, key=lambda x: abs(x.get('active_weight', 0)), reverse=True):
    pw = d.get('portfolio_weight_pct', 0)
    bw = d.get('benchmark_weight_pct', 0)
    if abs(pw) > 0.01 or abs(bw) > 0.01:
        ind_labels.append(d['industry'] if d['industry'] else '港股/其他')
        port_weights.append(round(pw, 2))
        bm_weights.append(round(bw, 2))

# Brinson chart top 15
brinson_labels = []
alloc_effects = []
sel_effects = []
int_effects = []
for d in brinson_data[:15]:
    brinson_labels.append(d['industry'] if d['industry'] else '港股/其他')
    alloc_effects.append(d['allocation_effect'])
    sel_effects.append(d['selection_effect'])
    int_effects.append(d['interaction_effect'])

# Build row strings
top_stocks = stock_data[:10]
bottom_stocks = list(reversed(stock_data[-10:]))

top_rows = ''
for i, st in enumerate(top_stocks):
    ind = st['industry'][:4] if st['industry'] else '其他'
    top_rows += '<tr><td class="rank">%d</td><td style="text-align:left">%s</td><td>%s</td><td>%.2f%%</td><td>%s</td><td class="value pos">%s</td></tr>' % (
        i+1, st['stock_name'], ind, st['weight'], color_pct(st['return']), plain_pct(st['contribution']))

bottom_rows = ''
for i, st in enumerate(bottom_stocks):
    ind = st['industry'][:4] if st['industry'] else '其他'
    bottom_rows += '<tr><td class="rank">%d</td><td style="text-align:left">%s</td><td>%s</td><td>%.2f%%</td><td>%s</td><td class="value neg">%s</td></tr>' % (
        i+1, st['stock_name'], ind, st['weight'], color_pct(st['return']), plain_pct(st['contribution']))

brinson_table_rows = ''
for d in brinson_data:
    ind = d['industry'] if d['industry'] else '港股/其他'
    brinson_table_rows += '<tr><td style="text-align:left;font-weight:600">%s</td><td>%s</td><td>%s</td><td>%s</td><td>%s</td><td>%s</td><td>%s</td><td>%s</td><td>%s</td><td style="font-weight:700">%s</td></tr>' % (
        ind, plain_pct(d['portfolio_weight']), plain_pct(d['benchmark_weight']),
        color_pct(d['active_weight']), color_pct(d['portfolio_return']),
        color_pct(d['benchmark_return']), color_pct(d['allocation_effect']),
        color_pct(d['selection_effect']), color_pct(d['interaction_effect']),
        color_pct(d['total_effect']))

fund_rows = ''
for i, f in enumerate(fund_data):
    color = '#e74c3c' if f['weight'] > 5 else '#f39c12' if f['weight'] > 2 else '#95a5a6'
    fund_rows += '<tr><td>%d</td><td>%s</td><td style="text-align:left">%s</td><td style="color:%s;font-weight:bold">%.2f%%</td></tr>' % (
        i+1, f['code'], f['name'], color, f['weight'])

# JSON data for charts
ind_labels_json = json.dumps(ind_labels, ensure_ascii=False)
port_weights_json = json.dumps(port_weights)
bm_weights_json = json.dumps(bm_weights)
brinson_labels_json = json.dumps(brinson_labels, ensure_ascii=False)
alloc_json = json.dumps(alloc_effects)
sel_json = json.dumps(sel_effects)
int_json = json.dumps(int_effects)

# Build HTML with template substitution via %s
template = '''<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>华夏久盈-长江金工Q3组合 · 穿透归因分析</title>
<script src="https://cdn.jsdelivr.net/npm/chart.js@4.4.0/dist/chart.umd.min.js"></script>
<style>
* {margin:0;padding:0;box-sizing:border-box}
body {font-family:-apple-system,BlinkMacSystemFont,"Segoe UI",sans-serif;background:#f5f7fa;color:#2c3e50;line-height:1.6}
.container {max-width:1200px;margin:0 auto;padding:30px 20px}
.header {text-align:center;margin-bottom:30px}
.header h1 {font-size:28px;color:#1a1a2e;margin-bottom:8px}
.header .subtitle {color:#7f8c8d;font-size:14px}
.cards {display:grid;grid-template-columns:repeat(auto-fit,minmax(180px,1fr));gap:16px;margin-bottom:30px}
.card {background:white;border-radius:12px;padding:20px;box-shadow:0 2px 12px rgba(0,0,0,0.06);text-align:center}
.card .label {font-size:12px;color:#95a5a6;margin-bottom:6px;text-transform:uppercase;letter-spacing:0.5px}
.card .value {font-size:26px;font-weight:700}
.card .value.pos {color:#e74c3c}
.card .value.neg {color:#27ae60}
.section {background:white;border-radius:12px;padding:24px;margin-bottom:20px;box-shadow:0 2px 12px rgba(0,0,0,0.06)}
.section h2 {font-size:18px;margin-bottom:16px;color:#1a1a2e;border-bottom:2px solid #e74c3c;padding-bottom:8px;display:inline-block}
.chart-wrap {position:relative;height:400px;margin:10px 0}
.chart-wrap.tall {height:500px}
table {width:100%%;border-collapse:collapse;font-size:13px}
th {background:#f8f9fa;padding:10px 8px;text-align:center;font-weight:600;color:#555;border-bottom:2px solid #dee2e6;white-space:nowrap}
td {padding:8px;text-align:center;border-bottom:1px solid #eee}
tr:hover {background:#f8f9fa}
.two-col {display:grid;grid-template-columns:1fr 1fr;gap:20px}
@media (max-width:768px) {.two-col{grid-template-columns:1fr}}
.footnote {color:#95a5a6;font-size:12px;margin-top:20px;text-align:center}
.rank {font-weight:700;width:30px}
</style>
</head>
<body>
<div class="container">

<div class="header">
  <h1>华夏久盈 · 长江金工 Q3 组合穿透归因分析</h1>
  <div class="subtitle">归因周期: %(period_start)s ~ %(period_end)s · 基准: 沪深300 · 基金数: %(num_funds)d只 · 穿透个股: %(num_stocks)d只</div>
</div>

<div class="cards">
  <div class="card"><div class="label">组合收益率</div><div class="value pos">%(port_ret)s</div></div>
  <div class="card"><div class="label">基准收益率</div><div class="value">%(bm_ret)s</div></div>
  <div class="card"><div class="label">超额收益</div><div class="value pos">%(excess)s</div></div>
  <div class="card"><div class="label">配置效应</div><div class="value pos">%(alloc)s</div></div>
  <div class="card"><div class="label">选股效应</div><div class="value pos">%(select)s</div></div>
  <div class="card"><div class="label">交互效应</div><div class="value pos">%(inter)s</div></div>
</div>

<div class="section">
  <h2>行业配置对比：组合 vs 沪深300</h2>
  <div class="chart-wrap"><canvas id="industryChart"></canvas></div>
</div>

<div class="section">
  <h2>Brinson 归因分解（按行业）</h2>
  <div class="chart-wrap tall"><canvas id="brinsonChart"></canvas></div>
</div>

<div class="two-col">
  <div class="section">
    <h2>收益贡献 TOP10 个股</h2>
    <table>
      <tr><th class="rank">#</th><th>股票</th><th>行业</th><th>权重</th><th>收益率</th><th>贡献</th></tr>
      %(top_rows)s
    </table>
  </div>
  <div class="section">
    <h2>收益拖累 BOTTOM10 个股</h2>
    <table>
      <tr><th class="rank">#</th><th>股票</th><th>行业</th><th>权重</th><th>收益率</th><th>贡献</th></tr>
      %(bottom_rows)s
    </table>
  </div>
</div>

<div class="section">
  <h2>Brinson 归因明细表</h2>
  <div style="overflow-x:auto">
  <table>
    <tr>
      <th>行业</th><th>组合权重</th><th>基准权重</th><th>主动权重</th>
      <th>组合收益</th><th>基准收益</th>
      <th>配置效应</th><th>选股效应</th><th>交互效应</th><th>总效应</th>
    </tr>
    %(brinson_table_rows)s
  </table>
  </div>
</div>

<div class="section">
  <h2>基金组合明细（%(num_funds)d只）</h2>
  <table>
    <tr><th>#</th><th>基金代码</th><th>基金名称</th><th>组合权重</th></tr>
    %(fund_rows)s
  </table>
</div>

<div class="footnote">
  数据来源: cjpy量化金融数据库 · 持仓截止: 2026Q2季报 · 收益率计算周期: 2026-01-05 至 2026-06-30 (116个交易日) · 归因模型: Brinson (配置+选股+交互)
</div>

</div>

<script>
Chart.defaults.color = "#666";
Chart.defaults.font.family = "-apple-system,BlinkMacSystemFont,Segoe UI,sans-serif";
Chart.defaults.font.size = 12;

(function() {
  var ctx = document.getElementById("industryChart").getContext("2d");
  new Chart(ctx, {
    type: "bar",
    data: {
      labels: %(ind_labels_json)s,
      datasets: [
        { label: "组合权重", data: %(port_weights_json)s, backgroundColor: "#e74c3c", borderRadius: 4 },
        { label: "沪深300权重", data: %(bm_weights_json)s, backgroundColor: "#3498db", borderRadius: 4 }
      ]
    },
    options: {
      responsive: true,
      maintainAspectRatio: false,
      plugins: {
        legend: { position: "top" },
        tooltip: { callbacks: { label: function(ctx) { return ctx.dataset.label + ": " + ctx.raw.toFixed(2) + "%%"; } } }
      },
      scales: {
        y: { title: { display: true, text: "权重(%%)" }, ticks: { callback: function(v) { return v + "%%"; } } },
        x: { ticks: { maxRotation: 45, minRotation: 0 } }
      }
    }
  });
})();

(function() {
  var ctx = document.getElementById("brinsonChart").getContext("2d");
  new Chart(ctx, {
    type: "bar",
    data: {
      labels: %(brinson_labels_json)s,
      datasets: [
        { label: "配置效应", data: %(alloc_json)s, backgroundColor: "#e74c3c", borderRadius: 2 },
        { label: "选股效应", data: %(sel_json)s, backgroundColor: "#3498db", borderRadius: 2 },
        { label: "交互效应", data: %(int_json)s, backgroundColor: "#f39c12", borderRadius: 2 }
      ]
    },
    options: {
      responsive: true,
      maintainAspectRatio: false,
      plugins: {
        legend: { position: "top" },
        tooltip: { callbacks: { label: function(ctx) { return ctx.dataset.label + ": " + (ctx.raw >= 0 ? "+" : "") + ctx.raw.toFixed(2) + "%%"; } } }
      },
      scales: {
        y: { title: { display: true, text: "效应(%%)" }, ticks: { callback: function(v) { return (v >= 0 ? "+" : "") + v + "%%"; } } },
        x: { stacked: true, ticks: { maxRotation: 45, minRotation: 0 } }
      }
    }
  });
})();
</script>

</body>
</html>'''

values = {
    'period_start': s['period_start'],
    'period_end': s['period_end'],
    'num_funds': num_funds,
    'num_stocks': s['num_stocks'],
    'port_ret': '%+.2f%%' % s['portfolio_return'],
    'bm_ret': '%+.2f%%' % s['benchmark_return'],
    'excess': '%+.2f%%' % s['excess_return'],
    'alloc': '%+.2f%%' % s['allocation_effect'],
    'select': '%+.2f%%' % s['selection_effect'],
    'inter': '%+.2f%%' % s['interaction_effect'],
    'top_rows': top_rows,
    'bottom_rows': bottom_rows,
    'brinson_table_rows': brinson_table_rows,
    'fund_rows': fund_rows,
    'ind_labels_json': ind_labels_json,
    'port_weights_json': port_weights_json,
    'bm_weights_json': bm_weights_json,
    'brinson_labels_json': brinson_labels_json,
    'alloc_json': alloc_json,
    'sel_json': sel_json,
    'int_json': int_json,
}

html = template % values

import os
output_path = 'C:/Users/Administrator/WorkBuddy/2026-07-27-15-45-09/outputs/penetration_report.html'
os.makedirs(os.path.dirname(output_path), exist_ok=True)
with open(output_path, 'w', encoding='utf-8') as f:
    f.write(html)

print("HTML report generated: " + output_path)
print("Report size: %d bytes" % len(html))
