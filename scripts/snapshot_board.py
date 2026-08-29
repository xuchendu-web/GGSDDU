"""导出看板静态 HTML，便于核对数字和做截图。"""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from etf_board.assemble import build_board, rows_to_frame
from etf_board.market import market_status
from etf_board.store import connect, load_watchlist
from etf_board.ui import TABLE_CSS, render_table


def main(out: Path) -> None:
    cfg = load_watchlist()
    conn = connect()
    return_days = int(cfg.get("return_days", 19))
    bias_days = int(cfg.get("bias_days", 20))
    targets = cfg.get("target_bias_pct", [10, 15])
    rows = build_board(conn, cfg["etfs"], return_days=return_days, bias_days=bias_days, targets=targets, adjust=cfg.get("adjust", "qfq"))
    frame = rows_to_frame(rows, return_days, bias_days, targets)
    status = market_status()
    table = render_table(frame, return_days, bias_days, targets)
    html = f"""<!doctype html><html><head><meta charset="utf-8"><title>ETF 个性化行情看板</title>
<style>
body {{ margin:0; background:#0b1220; font-family: ui-sans-serif, system-ui, sans-serif; }}
.wrap {{ max-width: 1400px; margin: 0 auto; padding: 28px; }}
{TABLE_CSS}
</style></head><body><div class="wrap">
<div class="hero"><div><h1>ETF 个性化行情看板</h1>
<div class="sub">AKShare 快照 + SQLite 日线 · 溢价率本地按 IOPV 重算</div></div>
<div style="text-align:right"><span class="badge {status['state']}">{status['label']}</span>
<div class="clock">{status['clock']}</div></div></div>
{table}
</div></body></html>"""
    out.write_text(html, encoding="utf-8")
    cols = [c for c in frame.columns if c != "近N日走势"]
    print(frame[cols].to_string())
    print("wrote", out)


if __name__ == "__main__":
    dest = Path(sys.argv[1]) if len(sys.argv) > 1 else Path("/opt/cursor/artifacts/etf_board.html")
    dest.parent.mkdir(parents=True, exist_ok=True)
    main(dest)
