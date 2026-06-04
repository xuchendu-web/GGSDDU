const state = { symbols: [], active: "", filter: "all" };
const $ = (id) => document.getElementById(id);

const fmtDate = (value) => {
  if (!value) return "-";
  return new Date(value).toLocaleString("zh-CN", {
    timeZone: "Asia/Shanghai",
    month: "2-digit",
    day: "2-digit",
    hour: "2-digit",
    minute: "2-digit",
  });
};
const dateOnly = (value) => String(value || "").slice(0, 10);
const money = (value) => value == null ? "-" : `$${Number(value).toFixed(2)}`;
const esc = (value) => String(value || "").replace(/[&<>"']/g, (c) => ({
  "&": "&amp;",
  "<": "&lt;",
  ">": "&gt;",
  '"': "&quot;",
  "'": "&#39;",
}[c]));
const clip = (value, length = 260) => value && value.length > length ? `${value.slice(0, length)}...` : (value || "");

async function getJson(url) {
  const response = await fetch(url);
  const payload = await response.json();
  if (!response.ok || payload.error) throw new Error(payload.error || `${response.status} ${url}`);
  return payload;
}

async function init() {
  const summary = await getJson("/api/summary");
  state.symbols = summary.symbols || [];
  renderKpis(summary.stats || {});
  renderSymbols();
  const feed = await getJson("/api/feed?limit=40");
  renderFeed(feed.items || []);
  const first = state.symbols.find((item) => item.has_prices) || state.symbols[0];
  if (first) await selectSymbol(first.symbol);
}

function renderKpis(stats) {
  const items = [
    ["tweets", "帖子"],
    ["mentions", "提及"],
    ["symbols", "唯一代码"],
    ["priced_symbols", "有价格"],
    ["latest_mention", "最新提及"],
  ];
  $("kpis").innerHTML = items.map(([key, label]) => `
    <article class="kpi">
      <strong>${key === "latest_mention" ? fmtDate(stats[key]) : (stats[key] ?? 0)}</strong>
      <span>${label}</span>
    </article>
  `).join("");
}

function visibleSymbols() {
  const query = $("symbolSearch").value.trim().toUpperCase();
  return state.symbols.filter((item) => {
    if (query && !item.symbol.includes(query)) return false;
    if (state.filter === "priced" && !item.has_prices) return false;
    if (state.filter === "hot" && item.mention_count < 2) return false;
    return true;
  });
}

function renderSymbols() {
  const rows = visibleSymbols();
  $("symbols").innerHTML = rows.map((item) => `
    <button class="symbol-row ${state.active === item.symbol ? "active" : ""}" data-symbol="${item.symbol}">
      <span class="ticker">${esc(item.symbol)}</span>
      <span>
        <b>${item.mention_count}</b> mentions
        <small>latest ${fmtDate(item.latest_mention)}</small>
      </span>
      <em>${item.has_prices ? money(item.last_close) : "no price"}</em>
    </button>
  `).join("") || `<p class="empty">没有匹配的 symbol。</p>`;
  document.querySelectorAll(".symbol-row").forEach((button) => {
    button.addEventListener("click", () => selectSymbol(button.dataset.symbol));
  });
}

async function selectSymbol(symbol) {
  state.active = symbol;
  renderSymbols();
  const data = await getJson(`/api/symbol/${encodeURIComponent(symbol)}`);
  const info = state.symbols.find((item) => item.symbol === symbol) || {};
  $("activeTitle").textContent = `$${symbol}`;
  $("activeMeta").innerHTML = [
    `${info.mention_count || 0} mentions`,
    `${(data.prices || []).length} bars`,
    `first ${fmtDate(info.first_mention)}`,
    `latest ${fmtDate(info.latest_mention)}`,
  ].map((item) => `<span>${esc(item)}</span>`).join("");
  $("neighbors").innerHTML = (data.neighbors || []).map((item) => `<span>${esc(item.symbol)} x${item.count}</span>`).join("");
  renderChart(data);
}

function renderChart(data) {
  const chart = $("chart");
  const tooltip = $("tooltip");
  tooltip.hidden = true;

  const mentions = data.mentions || [];
  const firstMention = mentions.reduce((min, item) => {
    const day = dateOnly(item.mentioned_at);
    return day && (!min || day < min) ? day : min;
  }, "");
  const prices = firstMention ? (data.prices || []).filter((item) => item.date >= firstMention) : (data.prices || []);
  if (!prices.length) {
    chart.innerHTML = `<div class="empty">没有 ${esc(data.symbol)} 的价格数据。运行 <code>python3 scripts/ingest.py prices</code> 后刷新。</div>`;
    return;
  }

  const width = 900;
  const height = 410;
  const pad = { left: 54, right: 24, top: 26, bottom: 42 };
  const values = prices.map((item) => Number(item.close));
  const min = Math.min(...values);
  const max = Math.max(...values);
  const ySpan = max - min || 1;
  const x = (index) => pad.left + index * ((width - pad.left - pad.right) / Math.max(1, prices.length - 1));
  const y = (value) => height - pad.bottom - ((value - min) / ySpan) * (height - pad.top - pad.bottom);
  const path = prices.map((item, index) => `${index ? "L" : "M"}${x(index).toFixed(1)} ${y(item.close).toFixed(1)}`).join(" ");
  const priceIndex = new Map(prices.map((item, index) => [item.date, index]));
  const firstPriceByDate = (day) => prices.findIndex((item) => item.date >= day);

  const dots = mentions.map((mention) => {
    const day = dateOnly(mention.mentioned_at);
    const index = priceIndex.has(day) ? priceIndex.get(day) : firstPriceByDate(day);
    if (index == null || index < 0) return "";
    const price = prices[index];
    return `
      <button class="mention-dot" style="left:${(x(index) / width) * 100}%; top:${(y(price.close) / height) * 100}%"
        data-date="${esc(fmtDate(mention.mentioned_at))}" data-price="${esc(money(price.close))}" data-text="${esc(mention.text)}" data-url="${esc(mention.url || "")}"
        aria-label="${esc(data.symbol)} mention ${fmtDate(mention.mentioned_at)}"></button>
    `;
  }).join("");

  const ticks = [0, Math.floor(prices.length / 2), prices.length - 1]
    .filter((value, index, all) => all.indexOf(value) === index)
    .map((index) => `<text x="${x(index)}" y="${height - 12}" text-anchor="middle">${prices[index].date.slice(5)}</text>`)
    .join("");

  chart.innerHTML = `
    <svg viewBox="0 0 ${width} ${height}" preserveAspectRatio="none">
      <defs>
        <linearGradient id="fill" x1="0" x2="0" y1="0" y2="1">
          <stop offset="0%" stop-color="#76d6a2" stop-opacity=".45"></stop>
          <stop offset="100%" stop-color="#76d6a2" stop-opacity="0"></stop>
        </linearGradient>
      </defs>
      <line class="axis" x1="${pad.left}" x2="${width - pad.right}" y1="${height - pad.bottom}" y2="${height - pad.bottom}"></line>
      <line class="axis" x1="${pad.left}" x2="${pad.left}" y1="${pad.top}" y2="${height - pad.bottom}"></line>
      <text class="axis-label" x="12" y="${y(max) + 5}">${money(max)}</text>
      <text class="axis-label" x="12" y="${y(min) + 5}">${money(min)}</text>
      ${ticks}
      <path class="area" d="${path} L${x(prices.length - 1)} ${height - pad.bottom} L${pad.left} ${height - pad.bottom} Z"></path>
      <path class="line" d="${path}"></path>
    </svg>
    ${dots}
  `;

  chart.querySelectorAll(".mention-dot").forEach((dot) => {
    dot.addEventListener("mouseenter", () => showTooltip(dot, tooltip));
    dot.addEventListener("focus", () => showTooltip(dot, tooltip));
    dot.addEventListener("mouseleave", () => { tooltip.hidden = true; });
    dot.addEventListener("blur", () => { tooltip.hidden = true; });
    dot.addEventListener("click", () => {
      const url = dot.dataset.url;
      if (url) window.open(url, "_blank", "noopener,noreferrer");
    });
  });
}

function showTooltip(dot, tooltip) {
  tooltip.innerHTML = `
    <b>${dot.dataset.price}</b>
    <span>${dot.dataset.date}</span>
    <p>${esc(clip(dot.dataset.text, 220))}</p>
  `;
  tooltip.style.left = `min(calc(${dot.style.left} + 14px), calc(100% - 280px))`;
  tooltip.style.top = `calc(${dot.style.top} + 14px)`;
  tooltip.hidden = false;
}

function renderFeed(items) {
  $("feed").innerHTML = items.map((item) => `
    <article class="feed-item">
      <div><span class="ticker">$${esc(item.symbol)}</span><small>${fmtDate(item.mentioned_at)} / ${esc(item.source)}</small></div>
      <p>${esc(clip(item.text, 340))}</p>
      <a href="${esc(item.url)}" target="_blank" rel="noreferrer">打开原文</a>
    </article>
  `).join("") || `<p class="empty">暂无导入内容。</p>`;
}

document.querySelectorAll(".tabs button").forEach((button) => {
  button.addEventListener("click", () => {
    document.querySelectorAll(".tabs button").forEach((item) => item.classList.remove("active"));
    button.classList.add("active");
    state.filter = button.dataset.filter;
    renderSymbols();
  });
});
$("symbolSearch").addEventListener("input", renderSymbols);
init().catch((error) => {
  document.body.insertAdjacentHTML("afterbegin", `<pre class="error">${esc(error.message)}</pre>`);
});
