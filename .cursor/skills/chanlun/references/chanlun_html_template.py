"""
缠论分析 HTML 报告生成模板
============================
完整模板：包含三栏数据卡片 + Canvas K线图 + Canvas MACD图
使用方法：Python 生成 JSON 数据，注入到下面模板的占位符中

注意：
- 不要用 Python f-string 嵌套 JS 模板字面量，会有花括号冲突
- 正确做法：先 compute 所有变量，再用 .replace() 或普通字符串拼接
"""

HTML_TEMPLATE = '''<!DOCTYPE html>
<html lang="zh-CN">
<head><meta charset="UTF-8"><meta name="viewport" content="width=device-width,initial-scale=1.0">
<title>{title}</title>
<style>
*{{margin:0;padding:0;box-sizing:border-box}}
body{{font-family:"Microsoft YaHei","PingFang SC",sans-serif;background:#f0f2f5;color:#222;padding:14px}}
.c{{max-width:1500px;margin:0 auto}}
.hd{{background:linear-gradient(135deg,#1a1a2e,#16213e);color:#fff;padding:18px 24px;border-radius:12px;margin-bottom:14px;display:flex;justify-content:space-between;align-items:center}}
.hd h1{{font-size:20px}}.hd .pr{{font-size:32px;font-weight:800;color:#E60000}}
.g3{{display:grid;grid-template-columns:1fr 1fr 1fr;gap:10px;margin-bottom:14px}}
.pn{{background:#fff;border-radius:10px;padding:14px;box-shadow:0 1px 6px rgba(0,0,0,.05)}}
.pn h3{{font-size:13px;margin-bottom:8px;padding-bottom:5px;border-bottom:2px solid #eee}}
.rw{{display:flex;justify-content:space-between;padding:4px 0;font-size:12px;border-bottom:1px solid #f5f5f5}}
.rw .lb{{color:#888}}.rw .vl{{font-weight:700}}
.vr{{color:#E60000}}.vg{{color:#009900}}
.tg{{display:inline-block;padding:1px 6px;border-radius:3px;font-size:10px;font-weight:700;margin:0 1px}}
.tgr{{background:#fde8e8;color:#E60000}}.tgg{{background:#e8f5e9;color:#009900}}.tgo{{background:#fff3e0;color:#e65100}}
.ch{{background:#fff;border-radius:10px;padding:14px;box-shadow:0 1px 6px rgba(0,0,0,.05);margin-bottom:12px}}
.ch h3{{font-size:14px;margin-bottom:8px}}
canvas{{display:block;width:100%;border:1px solid #eee;border-radius:6px}}
.ft{{text-align:center;color:#bbb;font-size:11px;padding:8px}}
.lg{{display:flex;gap:14px;font-size:11px;flex-wrap:wrap;margin-bottom:4px}}
.lg span{{display:flex;align-items:center;gap:3px}}
@media(max-width:900px){{.g3{{grid-template-columns:1fr}}}}
</style></head><body><div class="c">
<div class="hd"><div><h1>{title}</h1><div style="font-size:12px;opacity:.7">{n_bars}根K线 | {date_range} | 形态学+动力学</div></div><div class="pr">{last_price}</div></div>

<!-- 三栏数据卡片 -->
<div class="g3">
<div class="pn"><h3>形态结构</h3>
{structure_rows}
</div>
<div class="pn"><h3>动力学</h3>
{dynamics_rows}
</div>
<div class="pn"><h3>买卖点 & 建议</h3>
{signal_rows}
</div>
</div>

<!-- K线图表 -->
<div class="ch"><h3>K线 + 缠论标记</h3>
<div class="lg">
<span><span style="width:16px;height:3px;background:#E60000;display:inline-block;border-radius:2px"></span>向上笔</span>
<span><span style="width:16px;height:3px;background:#009900;display:inline-block;border-radius:2px"></span>向下笔</span>
<span><span style="width:10px;height:10px;background:#ff9800;display:inline-block;border-radius:50%"></span>顶���型</span>
<span><span style="width:10px;height:10px;background:#2196F3;display:inline-block;border-radius:50%"></span>底分型</span>
<span><span style="width:16px;height:10px;background:rgba(255,152,0,.12);border:1px dashed #ff9800;display:inline-block;border-radius:2px"></span>中枢</span>
</div><canvas id="c1" height="480"></canvas></div>

<!-- MACD图表 -->
<div class="ch"><h3>MACD 指标</h3><canvas id="c2" height="200"></canvas></div>

<div class="ft">cjpy · 缠论引擎 · 仅供参考不构成投资建议</div></div>

<script>
// ===== 数据：由 Python 注入 =====
var KL = __KL_DATA__;
var FR = __FR_DATA__;
var ST = __ST_DATA__;
var HB = __HB_DATA__;
var DIFF = __DIFF_DATA__;
var DEA = __DEA_DATA__;
var BAR = __BAR_DATA__;

function drawAll(){{drawMain();drawMacd();}}

// ===== 主图：K线 + 笔/中枢/分型 =====
function drawMain(){{
var c=document.getElementById('c1');if(!c)return;
var w=c.parentElement.clientWidth-28;c.width=w*2;c.height=960;
c.style.width=w+'px';c.style.height='480px';
var ctx=c.getContext('2d');ctx.scale(2,2);
var n=KL.length;var pad={{top:30,bot:55,L:75,R:15}};
var pw=w-pad.L-pad.R,ph=480-pad.top-pad.bot;
var pMin=99999,pMax=0;
KL.forEach(function(k){{pMin=Math.min(pMin,k.l);pMax=Math.max(pMax,k.h);}});
pMin*=0.992;pMax*=1.008;
var toX=function(i){{return pad.L+i/(n-1)*pw;}};
var toY=function(p){{return pad.top+(1-(p-pMin)/(pMax-pMin))*ph;}};

// 背景+网格
ctx.fillStyle='#fafafa';ctx.fillRect(0,0,w,480);
ctx.strokeStyle='#eee';ctx.lineWidth=0.5;
for(var i=0;i<=6;i++){{var y=pad.top+i/6*ph;ctx.beginPath();ctx.moveTo(pad.L,y);ctx.lineTo(w-pad.R,y);ctx.stroke();}}
// Y轴
ctx.fillStyle='#555';ctx.font='10px Microsoft YaHei';ctx.textAlign='right';
for(var i=0;i<=6;i++){{var pv=pMin+i/6*(pMax-pMin);ctx.fillText(pv.toFixed(0),pad.L-5,toY(pv)+3);}}
// X轴
ctx.textAlign='center';ctx.fillStyle='#888';ctx.font='9px Microsoft YaHei';
var step=Math.max(1,Math.floor(n/14));
for(var i=0;i<n;i+=step){{ctx.fillText(KL[i].t.substring(5,10),toX(i),480-pad.bot+14);}}

// 中枢
HB.forEach(function(h){{
var x1=toX(h.sk),x2=toX(h.ek),yz=toY(h.ZG),yd=toY(h.ZD);
ctx.fillStyle='rgba(255,152,0,0.1)';ctx.fillRect(x1,yz,x2-x1,yd-yz);
ctx.strokeStyle='rgba(255,152,0,0.6)';ctx.setLineDash([5,3]);ctx.lineWidth=1.5;
ctx.strokeRect(x1,yz,x2-x1,yd-yz);ctx.setLineDash([]);
ctx.fillStyle='#e65100';ctx.font='bold 11px Microsoft YaHei';ctx.textAlign='left';
ctx.fillText('ZG '+h.ZG,x1+4,yz-4);ctx.fillText('ZD '+h.ZD,x1+4,yd+13);
}});

// 笔
ST.forEach(function(s){{
var x1=toX(s.sk),y1=toY(s.sv),x2=toX(s.ek),y2=toY(s.ev);
var cl=s.type==='up'?'#E60000':'#009900';
ctx.strokeStyle=cl;ctx.lineWidth=s.amp>6?3:(s.amp>3?2:1.5);ctx.globalAlpha=0.8;
ctx.beginPath();ctx.moveTo(x1,y1);ctx.lineTo(x2,y2);ctx.stroke();ctx.globalAlpha=1;
var ang=Math.atan2(y2-y1,x2-x1);
var ax=x2-Math.cos(ang)*8,ay=y2-Math.sin(ang)*8;
ctx.fillStyle=cl;ctx.beginPath();ctx.moveTo(ax,ay);
ctx.lineTo(ax-Math.cos(ang-0.5)*7,ay-Math.sin(ang-0.5)*7);
ctx.lineTo(ax-Math.cos(ang+0.5)*7,ay-Math.sin(ang+0.5)*7);
ctx.closePath();ctx.fill();
if(s.amp>2){{ctx.fillStyle=cl;ctx.font='bold 9px Microsoft YaHei';ctx.textAlign='center';
ctx.fillText((s.type==='up'?'+':'-')+s.amp.toFixed(1)+'%',(x1+x2)/2,(y1+y2)/2-6);}}
}});

// K线
var bw=Math.max(1,pw/n*0.6);
KL.forEach(function(k,i){{
var x=toX(i),oy=toY(k.o),cy=toY(k.c),hy=toY(k.h),ly=toY(k.l);
var up=k.c>=k.o,cl=up?'#E60000':'#009900';
ctx.strokeStyle=cl;ctx.lineWidth=1;ctx.beginPath();ctx.moveTo(x,hy);ctx.lineTo(x,ly);ctx.stroke();
var bh=Math.max(1,Math.abs(cy-oy));
ctx.fillStyle=up?cl:'#fff';ctx.fillRect(x-bw/2,up?cy:oy,bw,bh);
ctx.strokeStyle=cl;if(!up)ctx.strokeRect(x-bw/2,oy,bw,bh);
}});

// 分型
FR.forEach(function(f){{
var x=toX(f.ki),y=toY(f.v);var sz=f.st==='strong'?6:(f.st==='mid'?5:3.5);ctx.lineWidth=1;
if(f.type==='top'){{
ctx.fillStyle='#ff9800';ctx.strokeStyle='#e65100';
ctx.beginPath();ctx.moveTo(x,y-3);ctx.lineTo(x-sz,y+sz);ctx.lineTo(x+sz,y+sz);
ctx.closePath();ctx.fill();ctx.stroke();
}}else{{
ctx.fillStyle='#2196F3';ctx.strokeStyle='#0D47A1';
ctx.beginPath();ctx.moveTo(x,y+3);ctx.lineTo(x-sz,y-sz);ctx.lineTo(x+sz,y-sz);
ctx.closePath();ctx.fill();ctx.stroke();
}}
}});
}}

// ===== MACD 图 =====
function drawMacd(){{
var c=document.getElementById('c2');if(!c)return;
var w=c.parentElement.clientWidth-28;c.width=w*2;c.height=400;
c.style.width=w+'px';c.style.height='200px';
var ctx=c.getContext('2d');ctx.scale(2,2);
var n=DIFF.length;var pad={{top:10,bot:20,L:60,R:20}};
var pw=w-pad.L-pad.R,ph=200-pad.top-pad.bot;
var toX=function(i){{return pad.L+i/(n-1)*pw;}};
var allV=DIFF.concat(DEA).concat(BAR);
var vMax=Math.max(Math.abs(Math.min.apply(null,allV)),Math.abs(Math.max.apply(null,allV)))*1.2;
if(vMax<1)vMax=1;var zeroY=pad.top+ph/2;
var toY=function(v){{return zeroY-v/vMax*ph/2;}};

ctx.strokeStyle='#bbb';ctx.lineWidth=1;
ctx.beginPath();ctx.moveTo(pad.L,zeroY);ctx.lineTo(w-pad.R,zeroY);ctx.stroke();

var bw=Math.max(0.5,pw/n*0.6);
for(var i=0;i<n;i++){{if(BAR[i]===0)continue;
var x=toX(i),h=Math.abs(BAR[i])/vMax*ph/2;
ctx.fillStyle=BAR[i]>0?'rgba(230,0,0,0.5)':'rgba(0,153,0,0.5)';
ctx.fillRect(x-bw/2,BAR[i]>0?zeroY-h:zeroY,bw,Math.max(1,h));}}

ctx.strokeStyle='#E60000';ctx.lineWidth=1.5;ctx.beginPath();
for(var i=0;i<n;i++){{var x=toX(i),y=toY(DIFF[i]);i===0?ctx.moveTo(x,y):ctx.lineTo(x,y);}}ctx.stroke();
ctx.strokeStyle='#1565C0';ctx.lineWidth=1.5;ctx.beginPath();
for(var i=0;i<n;i++){{var x=toX(i),y=toY(DEA[i]);i===0?ctx.moveTo(x,y):ctx.lineTo(x,y);}}ctx.stroke();
ctx.font='10px Microsoft YaHei';ctx.fillStyle='#E60000';ctx.fillText('DIFF',w-pad.R-85,15);
ctx.fillStyle='#1565C0';ctx.fillText('DEA',w-pad.R-48,15);
}}

window.addEventListener('load',function(){{setTimeout(drawAll,150);}});
window.addEventListener('resize',drawAll);
</script></body></html>'''


def build_html(code, name, df, fractals, strokes, hubs, diff, dea, bar, info):
    """一键生成缠论 HTML 报告"""
    import json

    # 注入 JSON 数据
    kl_js = json.dumps([{"t": str(r['时间']), "o": float(r['open']),
                         "h": float(r['high']), "l": float(r['low']),
                         "c": float(r['close'])} for _, r in df.iterrows()],
                       ensure_ascii=False)
    fr_js = json.dumps([{"type": f['type'], "ki": f['ki'], "v": round(f['v'], 2),
                          "st": f['st']} for f in fractals], ensure_ascii=False)
    st_js = json.dumps([{"type": s['type'], "sk": s['sk'], "ek": s['ek'],
                          "sv": round(s['sv'], 2), "ev": round(s['ev'], 2),
                          "amp": s['amp']} for s in strokes], ensure_ascii=False)
    hb_js = json.dumps([{"sk": h['sk'], "ek": h['ek'], "ZD": h['ZD'],
                          "ZG": h['ZG'], "mid": h['mid']} for h in hubs],
                        ensure_ascii=False)

    html = HTML_TEMPLATE
    html = html.replace('{title}', f'{name} {code} · {info.get("period","30F")} 缠论分析')
    html = html.replace('{n_bars}', str(len(df)))
    html = html.replace('{date_range}', info.get('date_range', ''))
    html = html.replace('{last_price}', str(info.get('last_price', '')))
    html = html.replace('{structure_rows}', info.get('structure_rows', ''))
    html = html.replace('{dynamics_rows}', info.get('dynamics_rows', ''))
    html = html.replace('{signal_rows}', info.get('signal_rows', ''))
    html = html.replace('__KL_DATA__', kl_js)
    html = html.replace('__FR_DATA__', fr_js)
    html = html.replace('__ST_DATA__', st_js)
    html = html.replace('__HB_DATA__', hb_js)
    html = html.replace('__DIFF_DATA__', json.dumps(diff))
    html = html.replace('__DEA_DATA__', json.dumps(dea))
    html = html.replace('__BAR_DATA__', json.dumps(bar))

    return html
