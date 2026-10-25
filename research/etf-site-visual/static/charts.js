/**
 * Interactive polish for inline SVG charts (.chart-wrap + .chart).
 * Expects optional data-chart-points JSON on .chart-wrap.
 */
(function () {
  "use strict";

  function parsePoints(wrap) {
    var raw = wrap.getAttribute("data-chart-points");
    if (raw) {
      try {
        return JSON.parse(raw);
      } catch (e) {
        /* fall through */
      }
    }
    var svg = wrap.querySelector("svg.chart");
    if (!svg) return null;
    var sl = svg.querySelector(".sl");
    if (!sl || !sl.getAttribute("d")) return null;
    var nums = sl
      .getAttribute("d")
      .match(/[\d.]+/g);
    if (!nums || nums.length < 4) return null;
    var pts = [];
    for (var i = 0; i + 1 < nums.length; i += 2) {
      pts.push({ x: parseFloat(nums[i]), y: parseFloat(nums[i + 1]) });
    }
    return pts.length ? pts : null;
  }

  function initWrap(wrap) {
    var svg = wrap.querySelector("svg.chart");
    if (!svg) return;

    var tooltip = document.createElement("div");
    tooltip.className = "chart-tooltip";
    tooltip.setAttribute("role", "status");
    tooltip.setAttribute("aria-live", "polite");
    wrap.appendChild(tooltip);

    var ns = "http://www.w3.org/2000/svg";
    var vbH = svg.viewBox.baseVal.height || 200;
    var vLine = document.createElementNS(ns, "line");
    vLine.setAttribute("class", "chart-crosshair chart-crosshair-v");
    vLine.setAttribute("y1", "0");
    vLine.setAttribute("y2", String(vbH));
    svg.appendChild(vLine);

    var meta = wrap.dataset;
    var labels = {
      strategy: meta.labelStrategy || "策略净值",
      benchmark: meta.labelBenchmark || "CSI偏股",
      drawdown: meta.labelDrawdown || "回撤",
    };

    var points = parsePoints(wrap);
    var dates = [];
    try {
      dates = JSON.parse(wrap.getAttribute("data-chart-dates") || "[]");
    } catch (e2) {
      dates = [];
    }

    var values = { strategy: [], benchmark: [], drawdown: [] };
    try {
      var v = JSON.parse(wrap.getAttribute("data-chart-values") || "{}");
      values.strategy = v.strategy || [];
      values.benchmark = v.benchmark || [];
      values.drawdown = v.drawdown || [];
    } catch (e3) {
      /* demo fallbacks */
    }

    function svgPoint(clientX) {
      var rect = svg.getBoundingClientRect();
      var vb = svg.viewBox.baseVal;
      var w = vb.width || rect.width;
      var x = ((clientX - rect.left) / rect.width) * w;
      return { x: x, rect: rect, vb: vb };
    }

    function nearestIndex(x, pts) {
      if (!pts || !pts.length) return 0;
      var best = 0;
      var bestD = Infinity;
      for (var i = 0; i < pts.length; i++) {
        var d = Math.abs(pts[i].x - x);
        if (d < bestD) {
          bestD = d;
          best = i;
        }
      }
      return best;
    }

    function showTip(clientX, clientY) {
      var sp = svgPoint(clientX);
      var idx = nearestIndex(sp.x, points);
      var px = points ? points[idx].x : sp.x;
      var pct = (px / (sp.vb.width || 1)) * 100;
      vLine.setAttribute("x1", px);
      vLine.setAttribute("x2", px);
      if (sp.vb.height) {
        vLine.setAttribute("y2", sp.vb.height);
      }

      var date = dates[idx] || "—";
      var s = values.strategy[idx];
      var b = values.benchmark[idx];
      var d = values.drawdown[idx];

      var html =
        '<div class="tt-date">' +
        date +
        "</div>";
      if (s != null) {
        html +=
          '<div class="tt-row"><span><span class="tt-dot" style="background:#2563eb"></span>' +
          labels.strategy +
          '</span><span>' +
          s +
          "</span></div>";
      }
      if (b != null) {
        html +=
          '<div class="tt-row"><span><span class="tt-dot" style="background:#94a3b8"></span>' +
          labels.benchmark +
          '</span><span>' +
          b +
          "</span></div>";
      }
      if (d != null) {
        html +=
          '<div class="tt-row"><span><span class="tt-dot" style="background:#f87171"></span>' +
          labels.drawdown +
          '</span><span>' +
          d +
          "</span></div>";
      }
      if (s == null && b == null && d == null) {
        html += '<div class="tt-row"><span>索引</span><span>' + (idx + 1) + "</span></div>";
      }
      tooltip.innerHTML = html;
      tooltip.classList.add("visible");

      var left = (sp.rect.left - wrap.getBoundingClientRect().left) + (pct / 100) * sp.rect.width;
      var top = clientY - wrap.getBoundingClientRect().top;
      tooltip.style.left = Math.min(Math.max(left, 70), wrap.clientWidth - 70) + "px";
      tooltip.style.top = Math.max(top - 12, 8) + "px";
      wrap.classList.add("is-hover");
    }

    function hideTip() {
      tooltip.classList.remove("visible");
      wrap.classList.remove("is-hover");
    }

    wrap.addEventListener("mousemove", function (e) {
      showTip(e.clientX, e.clientY);
    });
    wrap.addEventListener("mouseleave", hideTip);
    wrap.addEventListener("touchmove", function (e) {
      if (e.touches[0]) showTip(e.touches[0].clientX, e.touches[0].clientY);
    }, { passive: true });
    wrap.addEventListener("touchend", hideTip);
  }

  function boot() {
    document.querySelectorAll(".chart-wrap").forEach(initWrap);
  }

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", boot);
  } else {
    boot();
  }
})();
