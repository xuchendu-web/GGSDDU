const MARKET_LABELS = {
  A: { title: "A-share", hint: "红涨绿跌" },
  HK: { title: "Hong Kong", hint: "绿涨红跌" },
  US: { title: "United States", hint: "绿涨红跌" },
};

const MAX_ALERTS = 30;
let transport = "ws";
let socket = null;
let eventSource = null;
let tickCount = 0;
let tickWindowStart = Date.now();
const prevPrices = new Map();

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

function formatPct(pct) {
  const sign = pct >= 0 ? "+" : "";
  return `${sign}${pct.toFixed(2)}%`;
}

function flashRow(el, market, pct) {
  const up = pct >= 0;
  el.classList.remove("flash-up", "flash-down", "us");
  if (market !== "A") el.classList.add("us");
  if (market === "A") {
    el.classList.add(up ? "flash-up" : "flash-down");
  } else {
    el.classList.add(up ? "flash-up" : "flash-down");
  }
  window.setTimeout(() => el.classList.remove("flash-up", "flash-down"), 400);
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

function renderMovers(movers) {
  const body = document.getElementById("movers-body");
  body.innerHTML = "";
  for (const r of movers) {
    const tr = document.createElement("tr");
    const cls = chgClass(r.market, r.change_pct);
    tr.innerHTML = `
      <td>${r.name}<br><small style="color:#9ca3af">${r.symbol} · ${r.market}</small></td>
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
  if (payload.movers) renderMovers(payload.movers);
  if (payload.alert) pushAlert(payload.alert);

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

connect();
