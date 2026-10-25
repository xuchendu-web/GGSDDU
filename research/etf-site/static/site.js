/** 净值 / 回撤 SVG 图：悬停十字线与 tooltip（无外部图表库） */
(function () {
  const TIP_ID = "chart-tooltip-el";

  function ensureTooltip() {
    let el = document.getElementById(TIP_ID);
    if (!el) {
      el = document.createElement("div");
      el.id = TIP_ID;
      el.className = "chart-tooltip";
      el.setAttribute("role", "status");
      el.setAttribute("aria-live", "polite");
      document.body.appendChild(el);
    }
    return el;
  }

  function parseMeta(panel) {
    const raw = panel.getAttribute("data-series");
    if (!raw) return null;
    try {
      return JSON.parse(raw);
    } catch {
      return null;
    }
  }

  function clientToSvg(svg, clientX, clientY) {
    const pt = svg.createSVGPoint();
    pt.x = clientX;
    pt.y = clientY;
    const ctm = svg.getScreenCTM();
    if (!ctm) return null;
    return pt.matrixTransform(ctm.inverse());
  }

  function nearestIndex(dates, n, svgX, pad, innerW) {
    if (n <= 1) return 0;
    const t = Math.max(0, Math.min(1, (svgX - pad) / innerW));
    return Math.round(t * (n - 1));
  }

  function fmtNav(v) {
    if (v == null || Number.isNaN(v)) return "—";
    return Number(v).toFixed(3);
  }

  function fmtPct(v) {
    if (v == null || Number.isNaN(v)) return "—";
    return (Number(v) * 100).toFixed(2) + "%";
  }

  function bindPanel(panel) {
    const meta = parseMeta(panel);
    if (!meta || !meta.dates || !meta.dates.length) return;

    const navSvg = panel.querySelector("svg.chart--nav");
    const ddSvg = panel.querySelector("svg.chart--dd");
    const tip = ensureTooltip();

    const dates = meta.dates;
    const strat = meta.strat || [];
    const bench = meta.bench || null;
    const dd = meta.dd || null;
    const pad = meta.pad || 40;
    const w = meta.width || 600;
    const innerW = w - pad - 10;
    const n = dates.length;

    let crossV = null;
    let crossH = null;
    let dotS = null;
    let dotB = null;

    function ensureLayers(svg) {
      if (!svg) return;
      let g = svg.querySelector(".chart-overlay");
      if (!g) {
        g = document.createElementNS("http://www.w3.org/2000/svg", "g");
        g.setAttribute("class", "chart-overlay");
        svg.appendChild(g);
      }
      return g;
    }

    const navG = ensureLayers(navSvg);
    const ddG = ensureLayers(ddSvg);

    function clearOverlay(g) {
      if (g) g.innerHTML = "";
    }

    function hide() {
      tip.classList.remove("visible");
      clearOverlay(navG);
      clearOverlay(ddG);
    }

    function show(clientX, clientY, idx) {
      idx = Math.max(0, Math.min(n - 1, idx));
      const date = dates[idx];
      const sv = strat[idx];
      const bv = bench ? bench[idx] : null;
      const dv = dd ? dd[idx] : null;

      let html = `<div class="date">${date}</div>`;
      html += `<div class="row"><span>策略净值</span><b>${fmtNav(sv)}</b></div>`;
      if (bench) {
        html += `<div class="row"><span>偏股基准</span><b>${fmtNav(bv)}</b></div>`;
      }
      if (dd) {
        html += `<div class="row"><span>回撤</span><b>${fmtPct(dv)}</b></div>`;
      }
      tip.innerHTML = html;
      tip.classList.add("visible");

      const margin = 12;
      const rect = tip.getBoundingClientRect();
      let left = clientX + margin;
      let top = clientY + margin;
      if (left + rect.width > window.innerWidth - 8) {
        left = clientX - rect.width - margin;
      }
      if (top + rect.height > window.innerHeight - 8) {
        top = clientY - rect.height - margin;
      }
      tip.style.left = `${left}px`;
      tip.style.top = `${top}px`;

      if (navSvg && navG && meta.yStrat) {
        clearOverlay(navG);
        const x = meta.x[idx];
        const yS = meta.yStrat[idx];
        crossV = line(navG, x, 15, x, 280, "chart-crosshair");
        dotS = circle(navG, x, yS, "chart-dot");
        if (bench && meta.yBench) {
          dotB = circle(navG, x, meta.yBench[idx], "chart-dot bench");
        }
      }

      if (ddSvg && ddG && meta.yDd) {
        clearOverlay(ddG);
        const x = meta.x[idx];
        crossV = line(ddG, x, 8, x, 100, "chart-crosshair");
      }
    }

    function line(g, x1, y1, x2, y2, cls) {
      const el = document.createElementNS("http://www.w3.org/2000/svg", "line");
      el.setAttribute("x1", x1);
      el.setAttribute("y1", y1);
      el.setAttribute("x2", x2);
      el.setAttribute("y2", y2);
      el.setAttribute("class", cls);
      g.appendChild(el);
      return el;
    }

    function circle(g, cx, cy, cls) {
      const el = document.createElementNS("http://www.w3.org/2000/svg", "circle");
      el.setAttribute("cx", cx);
      el.setAttribute("cy", cy);
      el.setAttribute("r", 4);
      el.setAttribute("class", cls);
      g.appendChild(el);
      return el;
    }

    function onMove(ev) {
      const svg = navSvg || ddSvg;
      if (!svg) return;
      const p = clientToSvg(svg, ev.clientX, ev.clientY);
      if (!p) return;
      const idx = nearestIndex(dates, n, p.x, pad, innerW);
      show(ev.clientX, ev.clientY, idx);
    }

    panel.addEventListener("mousemove", onMove);
    panel.addEventListener("touchmove", (ev) => {
      if (ev.touches[0]) onMove(ev.touches[0]);
    }, { passive: true });
    panel.addEventListener("mouseleave", hide);
    panel.addEventListener("touchend", hide);
  }

  function init() {
    document.querySelectorAll(".chart-panel[data-series]").forEach(bindPanel);
  }

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", init);
  } else {
    init();
  }
})();
