const MARKET_LABELS = {
  A: { title: "A-share", hint: "红涨绿跌" },
  HK: { title: "Hong Kong", hint: "绿涨红跌" },
  US: { title: "United States", hint: "绿涨红跌" },
};

const CLOCK_ZONES = [
  { id: "shanghai", label: "上海", tz: "Asia/Shanghai", market: "A" },
  { id: "hongkong", label: "香港", tz: "Asia/Hong_Kong", market: "HK" },
  { id: "london", label: "伦敦", tz: "Europe/London", market: "EU" },
  { id: "newyork", label: "纽约", tz: "America/New_York", market: "US" },
  { id: "chicago", label: "芝加哥", tz: "America/Chicago", market: "US" },
  { id: "tokyo", label: "东京", tz: "Asia/Tokyo", market: "JP" },
];

const PHASE_LABEL = {
  open: "盘中",
  pre: "盘前",
  closed: "休市",
  after: "盘后",
};

const MAX_ALERTS = 40;
let transport = "ws";
let socket = null;
let eventSource = null;
let tickCount = 0;
let tickWindowStart = Date.now();
const prevPrices = new Map();
let lastSessions = [];

function wsUrl() {
  const proto = location.protocol === "https:" ? "wss:" : "ws:";
  return `${proto}//${location.host}/ws/ticks`;
}

function sseUrl() {
  return `${location.origin}/sse/ticks`;
}

function setConn(state, label) {
  const el = document.getElementById("conn-status");
  const lbl = document.getElementById("conn-label");
  el.classList.remove("connected", "reconnecting");
  if (state) el.classList.add(state);
  lbl.textContent = label;
}

function chgClass(market, pct) {
  const up = pct >= 0;
  if (market === "A") return up ? "up-cn" : "down-cn";
  return up ? "up-us" : "down-us";
}

function formatPct(pct, digits = 2) {
  const sign = pct >= 0 ? "+" : "";
  return `${sign}${pct.toFixed(digits)}%`;
}

function flashRow(el, market, pct) {
  const up = pct >= 0;
  el.classList.remove("flash-up", "flash-down", "us");
  if (market !== "A") el.classList.add("us");
  el.classList.add(up ? "flash-up" : "flash-down");
  window.setTimeout(() => el.classList.remove("flash-up", "flash-down"), 400);
}

function formatTimeInZone(tz) {
  try {
    return new Intl.DateTimeFormat("zh-CN", {
      timeZone: tz,
      hour: "2-digit",
      minute: "2-digit",
      second: "2-digit",
      hour12: false,
    }).format(new Date());
  } catch {
    return "—";
  }
}

function sessionPhaseFor(id) {
  const hit = lastSessions.find((s) => s.id === id);
  return hit?.phase || "closed";
}

function renderClockStrip() {
  const root = document.getElementById("clock-strip");
  root.innerHTML = CLOCK_ZONES
    .map((z) => {
      const phase = sessionPhaseFor(z.id);
      const phaseCls = phase === "open" ? "phase-open" : phase === "pre" || phase === "after" ? "phase-warn" : "phase-closed";
      return `
        <div class="clock-card ${phaseCls}" data-id="${z.id}">
          <span class="clock-city">${z.label}</span>
          <span class="clock-time" data-tz="${z.tz}">${formatTimeInZone(z.tz)}</span>
          <span class="clock-phase">${PHASE_LABEL[phase] || phase}</span>
        </div>`;
    })
    .join("");

  const utcEl = document.getElementById("clock-utc");
  utcEl.textContent = new Intl.DateTimeFormat("en-GB", {
    timeZone: "UTC",
    hour: "2-digit",
    minute: "2-digit",
    second: "2-digit",
    hour12: false,
  }).format(new Date());
}

function startClockTicker() {
  renderClockStrip();
  window.setInterval(() => {
    document.querySelectorAll(".clock-time").forEach((el) => {
      const tz = el.getAttribute("data-tz");
      if (tz) el.textContent = formatTimeInZone(tz);
    });
    const utcEl = document.getElementById("clock-utc");
    if (utcEl) {
      utcEl.textContent = new Intl.DateTimeFormat("en-GB", {
        timeZone: "UTC",
        hour: "2-digit",
        minute: "2-digit",
        second: "2-digit",
        hour12: false,
      }).format(new Date());
    }
  }, 1000);
}

function renderIndices(indices) {
  const root = document.getElementById("indices-root");
  const byMarket = { A: [], HK: [], US: [] };
  for (const row of indices) {
    if (byMarket[row.market]) byMarket[row.market].push(row);
  }

  root.innerHTML = "";
  for (const mkt of ["A", "HK", "US"]) {
    const rows = byMarket[mkt];
    if (!rows.length) continue;
    const group = document.createElement("div");
    group.className = "market-group";
    const meta = MARKET_LABELS[mkt];
    group.innerHTML = `<div class="market-label">${meta.title} <small>${meta.hint}</small></div>`;
    const grid = document.createElement("div");
    grid.className = "index-grid";

    for (const r of rows) {
      const rowEl = document.createElement("div");
      rowEl.className = "index-row";
      rowEl.dataset.id = r.id;
      const cls = chgClass(r.market, r.change_pct);
      rowEl.innerHTML = `
        <div class="idx-name">${r.name}<code>${r.symbol}</code></div>
        <div class="idx-price">${r.price}</div>
        <div class="idx-chg ${cls}">${formatPct(r.change_pct)}</div>`;
      grid.appendChild(rowEl);

      const prev = prevPrices.get(r.id);
      if (prev !== undefined && prev !== r.price) {
        flashRow(rowEl, r.market, r.change_pct);
      }
      prevPrices.set(r.id, r.price);
    }
    group.appendChild(grid);
    root.appendChild(group);
  }

  document.getElementById("kpi-indices").textContent = String(indices.length);
}

function renderFx(fx) {
  const body = document.getElementById("fx-body");
  if (!fx?.length) return;
  body.innerHTML = fx
    .map((r) => {
      const cls = r.change_pct >= 0 ? "up-us" : "down-us";
      const label = r.name || r.pair;
      return `<tr>
        <td>${label}</td>
        <td>${r.price}</td>
        <td class="${cls}">${formatPct(r.change_pct, 3)}</td>
      </tr>`;
    })
    .join("");
}

function renderBreadthSparkline(series) {
  if (!series?.length) return;
  const svg = document.getElementById("breadth-spark");
  if (!svg) return;
  const w = 240;
  const h = 56;
  const pad = 4;
  const min = Math.min(...series);
  const max = Math.max(...series);
  const span = max - min || 0.01;
  const pts = series.map((v, i) => {
    const x = pad + (i / (series.length - 1 || 1)) * (w - pad * 2);
    const y = h - pad - ((v - min) / span) * (h - pad * 2);
    return `${x},${y}`;
  });
  const linePath = `M ${pts.join(" L ")}`;
  const area = `M ${pad},${h - pad} L ${pts.join(" L ")} L ${w - pad},${h - pad} Z`;
  svg.innerHTML = `
    <path class="fill" d="${area}"></path>
    <path d="${linePath}"></path>`;
}

function renderRates(rates) {
  const root = document.getElementById("rates-root");
  if (!rates?.length) return;
  root.innerHTML = rates
    .map((r) => {
      const cls = r.change_bp >= 0 ? "rate-up" : "rate-down";
      const sign = r.change_bp >= 0 ? "+" : "";
      return `
        <div class="rate-card">
          <div class="rate-name">${r.name}<span class="rate-region">${r.region}</span></div>
          <div class="rate-yield">${r.yield_pct.toFixed(3)}%</div>
          <div class="rate-delta ${cls}">${sign}${r.change_bp.toFixed(1)} bp</div>
        </div>`;
    })
    .join("");
}

function renderCommodities(rows) {
  const root = document.getElementById("commodities-root");
  if (!rows?.length) return;
  root.innerHTML = rows
    .map((r) => {
      const cls = r.change_pct >= 0 ? "up-us" : "down-us";
      return `
        <div class="commodity-tile">
          <div class="commodity-head">
            <span>${r.name}</span>
            <code>${r.symbol}</code>
          </div>
          <div class="commodity-price">${r.price}</div>
          <div class="commodity-meta">
            <span class="${cls}">${formatPct(r.change_pct)}</span>
            <small>${r.unit}</small>
          </div>
        </div>`;
    })
    .join("");
}

function renderCrypto(rows) {
  const root = document.getElementById("crypto-root");
  if (!rows?.length) return;
  root.innerHTML = rows
    .map(
      (r) => `
      <div class="crypto-row">
        <div>
          <strong>${r.symbol}</strong>
          <span class="crypto-name">${r.name}</span>
        </div>
        <div class="crypto-price">${r.price.toLocaleString()}</div>
        <div class="${r.change_pct >= 0 ? "up-us" : "down-us"}">${formatPct(r.change_pct)}</div>
      </div>`
    )
    .join("");
}

function renderBreadth(breadth) {
  const root = document.getElementById("breadth-root");
  if (!breadth) return;
  const markets = [
    { key: "A", title: "A股" },
    { key: "HK", title: "港股" },
    { key: "US", title: "美股" },
  ];
  root.innerHTML = markets
    .map(({ key, title }) => {
      const b = breadth[key];
      if (!b) return "";
      const total = b.adv + b.dec + b.unch || 1;
      const advPct = (b.adv / total) * 100;
      const decPct = (b.dec / total) * 100;
      const unchPct = 100 - advPct - decPct;
      let extra = "";
      if (key === "A") {
        extra = `<div class="breadth-limits">涨停 <b>${b.limit_up}</b> · 跌停 <b>${b.limit_down}</b></div>`;
      }
      return `
        <div class="breadth-card">
          <div class="breadth-title">${title} <small>涨 ${b.adv_ratio ?? advPct.toFixed(1)}%</small></div>
          <div class="breadth-bar" title="涨/平/跌">
            <span class="seg adv" style="width:${advPct}%"></span>
            <span class="seg unch" style="width:${unchPct}%"></span>
            <span class="seg dec" style="width:${decPct}%"></span>
          </div>
          <div class="breadth-legend">
            <span>涨 ${b.adv}</span>
            <span>平 ${b.unch}</span>
            <span>跌 ${b.dec}</span>
          </div>
          ${extra}
        </div>`;
    })
    .join("");

  const aShare = breadth.A;
  if (aShare?.advance_ratio != null) {
    document.getElementById("kpi-breadth").textContent = `${(aShare.advance_ratio * 100).toFixed(1)}%`;
  } else if (aShare?.adv_ratio != null) {
    document.getElementById("kpi-breadth").textContent = `${aShare.adv_ratio}%`;
  }
  if (aShare?.sparkline) renderBreadthSparkline(aShare.sparkline);
}

function heatColor(intensity, changePct) {
  const t = Math.min(1, Math.max(0, intensity));
  if (changePct >= 0) {
    return `rgba(21, 128, 61, ${0.12 + t * 0.35})`;
  }
  return `rgba(185, 28, 28, ${0.12 + t * 0.35})`;
}

function renderVolumeHeat(rows) {
  const root = document.getElementById("heat-root");
  if (!rows?.length) return;
  root.innerHTML = rows
    .map((r) => {
      const bg = heatColor(r.intensity, r.change_pct);
      const cls = chgClass(r.market, r.change_pct);
      return `
        <div class="heat-cell" style="background:${bg}">
          <div class="heat-name">${r.name} <span class="heat-mkt">${r.market}</span></div>
          <div class="heat-chg ${cls}">${formatPct(r.change_pct)}</div>
          <div class="heat-vol">量比 <b>${r.vol_ratio.toFixed(2)}x</b></div>
        </div>`;
    })
    .join("");
}

function renderMovers(movers) {
  const body = document.getElementById("movers-body");
  body.innerHTML = "";
  for (const r of movers) {
    const tr = document.createElement("tr");
    const cls = chgClass(r.market, r.change_pct);
    tr.innerHTML = `
      <td>${r.name}<br><small class="muted-inline">${r.symbol} · ${r.market}</small></td>
      <td>${r.price}</td>
      <td class="${cls}">${formatPct(r.change_pct)}</td>`;
    body.appendChild(tr);
  }
}

function pushAlert(alert) {
  if (!alert) return;
  const list = document.getElementById("alerts-list");
  const li = document.createElement("li");
  li.className = alert.severity || "info";
  li.innerHTML = `<time>${alert.ts}</time><span class="mkt">${alert.market}</span>${alert.message}`;
  list.prepend(li);
  while (list.children.length > MAX_ALERTS) {
    list.removeChild(list.lastChild);
  }
}

function onTick(payload) {
  if (payload.type !== "tick") return;
  tickCount += 1;
  const now = Date.now();
  if (now - tickWindowStart > 60000) {
    tickWindowStart = now;
    tickCount = 1;
  }
  const rate = Math.round((tickCount / ((now - tickWindowStart) / 1000)) * 60) || tickCount * 50;
  document.getElementById("kpi-rate").textContent = String(Math.min(rate, 120));
  document.getElementById("kpi-ts").textContent = payload.ts?.slice(11, 19) || "—";

  if (payload.indices) renderIndices(payload.indices);
  if (payload.fx) renderFx(payload.fx);
  if (payload.rates) renderRates(payload.rates);
  if (payload.commodities) renderCommodities(payload.commodities);
  if (payload.crypto) renderCrypto(payload.crypto);
  if (payload.breadth) renderBreadth(payload.breadth);
  if (payload.volume_heat) renderVolumeHeat(payload.volume_heat);
  if (payload.movers) renderMovers(payload.movers);
  if (payload.alert) pushAlert(payload.alert);

  if (payload.fx && payload.rates) {
    document.getElementById("kpi-fx-rates").textContent = `${payload.fx.length} / ${payload.rates.length}`;
  }

  if (payload.sessions) {
    lastSessions = payload.sessions;
    renderClockStrip();
  }

  document.querySelectorAll(".session-chips .chip").forEach((chip) => {
    chip.classList.add("live");
  });
}

function disconnect() {
  if (socket) {
    socket.close();
    socket = null;
  }
  if (eventSource) {
    eventSource.close();
    eventSource = null;
  }
}

function connectWs() {
  disconnect();
  setConn("reconnecting", "WebSocket 连接中…");
  socket = new WebSocket(wsUrl());
  socket.addEventListener("open", () => {
    setConn("connected", "Live · WebSocket");
  });
  socket.addEventListener("message", (ev) => {
    try {
      onTick(JSON.parse(ev.data));
    } catch {
      /* ignore */
    }
  });
  socket.addEventListener("close", () => {
    setConn("reconnecting", "重连中…");
    window.setTimeout(() => {
      if (transport === "ws") connectWs();
    }, 2000);
  });
  window.setInterval(() => {
    if (socket?.readyState === WebSocket.OPEN) socket.send("ping");
  }, 25000);
}

function connectSse() {
  disconnect();
  setConn("reconnecting", "SSE 连接中…");
  eventSource = new EventSource(sseUrl());
  eventSource.onopen = () => setConn("connected", "Live · SSE");
  eventSource.onmessage = (ev) => {
    try {
      onTick(JSON.parse(ev.data));
    } catch {
      /* ignore */
    }
  };
  eventSource.onerror = () => {
    setConn("reconnecting", "SSE 重连中…");
  };
}

function connect() {
  if (transport === "ws") connectWs();
  else connectSse();
}

document.getElementById("transport-toggle").addEventListener("click", () => {
  transport = transport === "ws" ? "sse" : "ws";
  document.getElementById("transport-toggle").textContent =
    transport === "ws" ? "使用 SSE" : "使用 WebSocket";
  connect();
});

document.getElementById("alert-seed-ts").textContent = new Date().toISOString();

startClockTicker();
connect();
