const $ = (sel, el = document) => el.querySelector(sel);
const $$ = (sel, el = document) => [...el.querySelectorAll(sel)];

const C = {
  blue: "#1677ff",
  blueSoft: "rgba(22,119,255,0.18)",
  purple: "#8b6cff",
  up: "#e5484d",
  down: "#2ba471",
  fi: "#5b7cfa",
  eq: "#5dcaa5",
  fof: "#f2c14e",
  mm: "#f08a8a",
  sma: "#5ec4d4",
  mmf: "#8bb7f0",
  text3: "#86909c",
  grid: "#eef2f6",
  lastYear: "#4a6fdc",
  thisYear: "#fa8c16"
};

const charts = {};
function make(id, option) {
  const el = document.getElementById(id);
  if (!el) return;
  if (charts[id]) charts[id].dispose();
  const inst = echarts.init(el);
  inst.setOption(option);
  charts[id] = inst;
  return inst;
}

function axis() {
  return {
    axisLabel: { color: C.text3, fontSize: 10 },
    axisLine: { lineStyle: { color: "#d5e0ec" } },
    splitLine: { lineStyle: { color: C.grid, type: "dashed" } }
  };
}

function renderLifecycle() {
  const data = COCKPIT.lifecycle.filter((d) => d.name !== "已到期");
  make("chart-life", {
    grid: { left: 28, right: 8, top: 16, bottom: 22 },
    tooltip: { trigger: "item", formatter: (p) => `${p.name}：${p.value} 只` },
    xAxis: {
      type: "category",
      data: data.map((d) => d.name),
      axisTick: { show: false },
      ...axis()
    },
    yAxis: { type: "value", max: 300, splitNumber: 3, ...axis() },
    series: [
      {
        type: "scatter",
        symbolSize: (v) => Math.max(18, Math.sqrt(v[1]) * 9),
        data: data.map((d) => [d.name, d.value]),
        itemStyle: {
          color: C.purple,
          shadowBlur: 10,
          shadowColor: "rgba(139,108,255,0.35)"
        },
        label: { show: true, formatter: (p) => p.data[1], color: "#fff", fontWeight: 700, fontSize: 11 }
      }
    ]
  });
}

function renderNetSub() {
  make("chart-net", {
    grid: { left: 28, right: 8, top: 12, bottom: 22 },
    tooltip: { trigger: "axis" },
    xAxis: { type: "category", data: COCKPIT.netSub7d.map((d) => d.d), axisTick: { show: false }, ...axis() },
    yAxis: { type: "value", ...axis() },
    series: [
      {
        type: "bar",
        barWidth: 10,
        data: COCKPIT.netSub7d.map((d) => ({
          value: d.v,
          itemStyle: { color: d.v >= 0 ? C.up : C.down, borderRadius: 6 }
        }))
      }
    ]
  });
}

let peerMode = "latest";
function renderPeer() {
  const p = COCKPIT.peer[peerMode];
  $("#peer-rank").textContent = p.rank;
  $("#peer-share").textContent = p.share;
  make("chart-radar", {
    radar: {
      indicator: COCKPIT.peer.indicators.map((n) => ({ name: n, max: 100 })),
      axisName: { color: C.text3, fontSize: 10 },
      splitLine: { lineStyle: { color: "#e6eef6" } },
      splitArea: { areaStyle: { color: ["#fff", "#f7fbff"] } }
    },
    tooltip: {},
    series: [
      {
        type: "radar",
        data: [{ value: p.series, name: peerMode === "latest" ? "最新披露" : "上年末" }],
        symbol: "circle",
        symbolSize: 5,
        lineStyle: { color: C.blue, width: 2 },
        itemStyle: { color: C.blue },
        areaStyle: { color: C.blueSoft }
      }
    ]
  });
}

let trendRange = "ytd";
function trendSlice() {
  const m = COCKPIT.scaleTrend.months;
  const s = COCKPIT.scaleTrend.series;
  const n = trendRange === "1m" ? 2 : trendRange === "3m" ? 4 : m.length;
  const months = m.slice(-n);
  const out = { months };
  Object.keys(s).forEach((k) => (out[k] = s[k].slice(-n)));
  return out;
}
function renderTrend() {
  const t = trendSlice();
  const keys = ["固收公募", "权益公募", "FOF公募", "货币", "一对一专户", "一对多专户"];
  const colors = [C.fi, C.eq, C.fof, C.mm, C.sma, C.mmf];
  make("chart-trend", {
    color: colors,
    legend: { top: 0, left: 0, itemWidth: 10, itemHeight: 8, textStyle: { fontSize: 11, color: "#4e5969" } },
    grid: { left: 42, right: 12, top: 28, bottom: 22 },
    tooltip: { trigger: "axis" },
    xAxis: { type: "category", data: t.months, boundaryGap: false, ...axis() },
    yAxis: { type: "value", name: "亿", nameTextStyle: { color: C.text3, fontSize: 10 }, ...axis() },
    series: keys.map((k) => ({
      name: k,
      type: "line",
      stack: "total",
      areaStyle: { opacity: 0.92 },
      showSymbol: false,
      lineStyle: { width: 0 },
      emphasis: { focus: "series" },
      data: t[k]
    }))
  });
}

function renderRanks(cat = "固收") {
  const list = COCKPIT.ranks[cat] || [];
  const html = list
    .map((row, i) => {
      const medal =
        i === 0
          ? `<span class="medal g">1</span>`
          : i === 1
            ? `<span class="medal s">2</span>`
            : i === 2
              ? `<span class="medal b">3</span>`
              : `<span class="rank-idx">${i + 1}</span>`;
      return `<li data-name="${row[0]}"><span>${medal}</span><span class="rank-name">${row[0]}</span><span class="rank-val num">${row[1].toFixed(2)}亿</span></li>`;
    })
    .join("");
  $("#rank-list").innerHTML = html;
}

function renderFees() {
  make("chart-fee", {
    legend: { top: 0, itemWidth: 10, itemHeight: 8, textStyle: { fontSize: 11 } },
    grid: { left: 40, right: 12, top: 28, bottom: 22 },
    tooltip: { trigger: "axis" },
    xAxis: { type: "category", data: COCKPIT.fees.months, ...axis() },
    yAxis: { type: "value", name: "亿", nameTextStyle: { color: C.text3, fontSize: 10 }, ...axis() },
    series: [
      { name: "去年月度", type: "bar", barWidth: 8, itemStyle: { color: C.lastYear, borderRadius: [3, 3, 0, 0] }, data: COCKPIT.fees.lastYear },
      { name: "今年月度", type: "bar", barWidth: 8, itemStyle: { color: C.thisYear, borderRadius: [3, 3, 0, 0] }, data: COCKPIT.fees.thisYear },
      { name: "累计(全口径)", type: "line", smooth: true, symbolSize: 5, itemStyle: { color: "#3d5afe" }, data: COCKPIT.fees.cumTotal },
      { name: "累计(货基)", type: "line", smooth: true, symbolSize: 4, itemStyle: { color: C.mm }, data: COCKPIT.fees.cumMm },
      { name: "累计(非货)", type: "line", smooth: true, symbolSize: 4, itemStyle: { color: C.eq }, data: COCKPIT.fees.cumNonMm }
    ]
  });
}

function renderChannel() {
  const types = ["银行", "券商", "三方", "直销"];
  const colors = { 银行: "#274c9b", 券商: "#4aa3ff", 三方: "#7dcea0", 直销: "#f2c14e" };
  make("chart-channel", {
    legend: { top: 0, data: types, textStyle: { fontSize: 11 } },
    grid: { left: 48, right: 16, top: 28, bottom: 28 },
    tooltip: {
      formatter: (p) => `${p.data[2]}<br/>规模 ${p.data[0]} 万<br/>管理费 ${p.data[1]} 亿`
    },
    xAxis: {
      type: "log",
      name: "规模(万)",
      nameLocation: "middle",
      nameGap: 18,
      min: 10000,
      ...axis()
    },
    yAxis: { type: "value", name: "管理费(亿)", nameTextStyle: { color: C.text3, fontSize: 10 }, ...axis() },
    series: types.map((t) => ({
      name: t,
      type: "scatter",
      symbolSize: 14,
      itemStyle: { color: colors[t], opacity: 0.85 },
      data: COCKPIT.channels.filter((d) => d.type === t).map((d) => [d.scale, d.fee, d.name])
    }))
  });
}

function renderSpark() {
  make("chart-spark", {
    grid: { left: 28, right: 8, top: 8, bottom: 18 },
    xAxis: { type: "category", show: false, data: COCKPIT.invest.spark.map((_, i) => i) },
    yAxis: { type: "value", show: false, min: "dataMin" },
    tooltip: { trigger: "axis" },
    series: [
      {
        type: "line",
        smooth: true,
        showSymbol: false,
        data: COCKPIT.invest.spark,
        lineStyle: { color: C.blue, width: 2 },
        areaStyle: {
          color: new echarts.graphic.LinearGradient(0, 0, 0, 1, [
            { offset: 0, color: "rgba(22,119,255,0.28)" },
            { offset: 1, color: "rgba(22,119,255,0.02)" }
          ])
        }
      }
    ]
  });
}

function pctCell(v) {
  if (v > 0) return `<span class="up">+${v.toFixed(2)}</span>`;
  if (v < 0) return `<span class="down">${v.toFixed(2)}</span>`;
  return `<span class="muted">${v.toFixed(2)}</span>`;
}

function renderTable() {
  const rows = COCKPIT.invest.products
    .map(
      (p, i) => `<tr data-i="${i}">
      <td>${p.code}</td><td>${p.name}</td>
      <td class="num">${p.nav.toFixed(4)}</td>
      <td class="num">${p.scale.toFixed(2)}</td>
      <td>${pctCell(p.d1)}</td>
      <td>${pctCell(p.mtd)}</td>
      <td>${pctCell(p.ytd)}</td>
      <td>${p.rank}</td>
      <td>${p.pct}</td>
      <td class="num">${p.lev}</td>
      <td class="num">${p.t1}</td>
      <td class="num">${p.t2}</td>
      <td class="num">${p.t5}</td>
    </tr>`
    )
    .join("");
  $("#product-body").innerHTML = rows;
}

function renderGauge() {
  make("chart-gauge", {
    series: [
      {
        type: "gauge",
        startAngle: 180,
        endAngle: 0,
        min: 0,
        max: 24,
        splitNumber: 4,
        radius: "120%",
        center: ["50%", "78%"],
        axisLine: {
          lineStyle: {
            width: 14,
            color: [
              [0.12, C.blue],
              [0.35, "#91caff"],
              [1, C.up]
            ]
          }
        },
        pointer: { show: false },
        axisTick: { show: false },
        splitLine: { show: false },
        axisLabel: { show: false },
        detail: { show: false }
      }
    ]
  });
  $("#risk-break").innerHTML = COCKPIT.risk.buckets
    .map((b) => `<div>${b.label}：<b>${b.n}</b> 项</div>`)
    .join("");
}

function renderEval() {
  const html = COCKPIT.research.ranking
    .map((row, i) => {
      const medal =
        i === 0
          ? `<span class="medal g">1</span>`
          : i === 1
            ? `<span class="medal s">2</span>`
            : i === 2
              ? `<span class="medal b">3</span>`
              : `<span class="rank-idx">${i + 1}</span>`;
      return `<li data-name="${row[0]}"><span>${medal}</span><span class="rank-name">${row[0]}</span><span class="rank-val num">${row[1].toFixed(2)}</span></li>`;
    })
    .join("");
  $("#eval-list").innerHTML = html;
}

let portName = "机械行业";
let navRange = "6m";
function renderNav() {
  const p = COCKPIT.research.portfolios[portName];
  const n = navRange === "1y" ? 10 : navRange === "3y" ? 12 : 8;
  const dates = COCKPIT.research.dates.slice(-n);
  make("chart-nav", {
    legend: { top: 0, textStyle: { fontSize: 11 } },
    grid: { left: 42, right: 12, top: 28, bottom: 22 },
    tooltip: { trigger: "axis", valueFormatter: (v) => v.toFixed(1) + "%" },
    xAxis: { type: "category", data: dates, ...axis() },
    yAxis: { type: "value", axisLabel: { formatter: "{value}%" , color: C.text3, fontSize: 10 }, splitLine: { lineStyle: { color: C.grid, type: "dashed" } } },
    series: [
      { name: portName + "组合", type: "line", showSymbol: false, smooth: true, lineStyle: { width: 2, color: C.down }, data: p.ret.slice(-n) },
      { name: p.bench, type: "line", showSymbol: false, smooth: true, lineStyle: { width: 2, color: C.blue }, data: p.benchS.slice(-n) }
    ]
  });
}

function renderBars() {
  make("chart-bars", {
    grid: { left: 52, right: 36, top: 12, bottom: 12 },
    tooltip: { trigger: "axis", axisPointer: { type: "shadow" } },
    xAxis: { type: "value", axisLabel: { formatter: "{value}%", color: C.text3, fontSize: 10 }, splitLine: { lineStyle: { color: C.grid, type: "dashed" } } },
    yAxis: { type: "category", data: COCKPIT.research.bars.map((d) => d[0]).reverse(), axisTick: { show: false }, axisLine: { show: false }, axisLabel: { color: "#4e5969", fontSize: 11 } },
    series: [
      {
        type: "bar",
        barWidth: 12,
        data: COCKPIT.research.bars
          .map((d) => d[1])
          .reverse()
          .map((v) => ({
            value: v,
            itemStyle: {
              borderRadius: [0, 6, 6, 0],
              color: new echarts.graphic.LinearGradient(0, 0, 1, 0, [
                { offset: 0, color: "#3c8dff" },
                { offset: 1, color: "#bae0ff" }
              ])
            }
          })),
        label: { show: true, position: "right", formatter: (p) => p.value.toFixed(2) + "%", color: C.up, fontSize: 10 }
      }
    ]
  });
}

function applyDept(dept) {
  const snap = COCKPIT.invest.snapshot[dept];
  $("#dept-count").textContent = snap.count;
  $("#dept-scale").textContent = snap.scale.toLocaleString("zh-CN", { minimumFractionDigits: 2 });
  const mgrSel = $("#mgr-select");
  mgrSel.innerHTML = COCKPIT.invest.managers[dept].map((m) => `<option>${m}</option>`).join("");
}

function bind() {
  $$("[data-peer]").forEach((btn) => {
    btn.addEventListener("click", () => {
      peerMode = btn.dataset.peer;
      $$("[data-peer]").forEach((b) => b.classList.toggle("active", b === btn));
      renderPeer();
    });
  });
  $$("[data-trend]").forEach((btn) => {
    btn.addEventListener("click", () => {
      trendRange = btn.dataset.trend;
      $$("[data-trend]").forEach((b) => b.classList.toggle("active", b === btn));
      renderTrend();
    });
  });
  $$("[data-rank]").forEach((btn) => {
    btn.addEventListener("click", () => {
      $$("[data-rank]").forEach((b) => b.classList.toggle("active", b === btn));
      renderRanks(btn.dataset.rank);
    });
  });
  $$("[data-nav]").forEach((btn) => {
    btn.addEventListener("click", () => {
      navRange = btn.dataset.nav;
      $$("[data-nav]").forEach((b) => b.classList.toggle("active", b === btn));
      renderNav();
    });
  });
  $("#port-select").addEventListener("change", (e) => {
    portName = e.target.value;
    renderNav();
  });
  $("#dept-select").addEventListener("change", (e) => applyDept(e.target.value));
  $("#start-date").value = "2026-01-01";
  $("#end-date").value = COCKPIT.asOf;
  $("#start-date").addEventListener("change", () => {
    trendRange = "ytd";
    $$("[data-trend]").forEach((b) => b.classList.toggle("active", b.dataset.trend === "ytd"));
    renderTrend();
  });
}

function resize() {
  Object.values(charts).forEach((c) => c && c.resize());
}

function boot() {
  $("#asof").textContent = COCKPIT.asOf;
  renderLifecycle();
  renderNetSub();
  renderPeer();
  renderTrend();
  renderRanks("固收");
  renderFees();
  renderChannel();
  renderSpark();
  renderTable();
  renderGauge();
  renderEval();
  renderNav();
  renderBars();
  applyDept("固收投资");
  bind();
  window.addEventListener("resize", resize);
}

document.addEventListener("DOMContentLoaded", boot);
