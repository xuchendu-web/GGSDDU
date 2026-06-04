#!/usr/bin/env python3
"""Serve the local Serenity clone dashboard and JSON API."""

from __future__ import annotations

import argparse
import json
import sqlite3
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, unquote, urlparse


ROOT = Path(__file__).resolve().parents[1]
DB_PATH = ROOT / "data" / "serenity.sqlite"
DASHBOARD_DIR = ROOT / "dashboard"


def connect() -> sqlite3.Connection:
    con = sqlite3.connect(DB_PATH)
    con.row_factory = sqlite3.Row
    return con


def scalar_row(con: sqlite3.Connection, sql: str, params: tuple = ()) -> dict:
    row = con.execute(sql, params).fetchone()
    return dict(row) if row else {}


def summary(con: sqlite3.Connection) -> dict:
    stats = scalar_row(
        con,
        """
        select
          (select count(*) from tweets) tweets,
          (select count(*) from mentions) mentions,
          (select count(distinct symbol) from mentions) symbols,
          (select count(distinct symbol) from prices) priced_symbols,
          (select max(mentioned_at) from mentions) latest_mention
        """,
    )
    symbols = []
    for row in con.execute(
        """
        select
          m.symbol,
          count(*) mention_count,
          min(m.mentioned_at) first_mention,
          max(m.mentioned_at) latest_mention,
          (select close from prices p where p.symbol = m.symbol order by p.date desc limit 1) last_close,
          (select count(*) from prices p where p.symbol = m.symbol) price_bars
        from mentions m
        group by m.symbol
        order by mention_count desc, latest_mention desc, m.symbol
        """
    ):
        item = dict(row)
        item["has_prices"] = item.pop("price_bars") > 0
        symbols.append(item)
    return {"stats": stats, "symbols": symbols}


def feed(con: sqlite3.Connection, limit: int) -> dict:
    rows = con.execute(
        """
        select m.symbol, m.mentioned_at, m.text, m.source, t.author, t.url, t.favorite_count, t.reply_count, t.retweet_count
        from mentions m
        join tweets t on t.tweet_id = m.tweet_id
        order by m.mentioned_at desc, m.symbol
        limit ?
        """,
        (max(1, min(limit, 200)),),
    )
    return {"items": [dict(row) for row in rows]}


def symbol_detail(con: sqlite3.Connection, symbol: str) -> dict:
    prices = [
        dict(row)
        for row in con.execute(
            "select date, close, volume from prices where symbol = ? order by date",
            (symbol,),
        )
    ]
    mentions = [
        dict(row)
        for row in con.execute(
            """
            select m.symbol, m.mentioned_at, m.text, m.source, t.author, t.url, t.favorite_count, t.reply_count, t.retweet_count
            from mentions m
            join tweets t on t.tweet_id = m.tweet_id
            where m.symbol = ?
            order by m.mentioned_at
            """,
            (symbol,),
        )
    ]
    neighbors = [
        dict(row)
        for row in con.execute(
            """
            select m2.symbol, count(*) count
            from mentions m1
            join mentions m2 on m1.tweet_id = m2.tweet_id and m1.symbol <> m2.symbol
            where m1.symbol = ?
            group by m2.symbol
            order by count desc, m2.symbol
            limit 20
            """,
            (symbol,),
        )
    ]
    return {"symbol": symbol, "prices": prices, "mentions": mentions, "neighbors": neighbors}


class Handler(SimpleHTTPRequestHandler):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, directory=str(DASHBOARD_DIR), **kwargs)

    def do_GET(self) -> None:
        parsed = urlparse(self.path)
        if parsed.path.startswith("/api/"):
            self.handle_api(parsed.path, parse_qs(parsed.query))
            return
        if parsed.path == "/":
            self.path = "/index.html"
        super().do_GET()

    def handle_api(self, path: str, query: dict[str, list[str]]) -> None:
        try:
            if path == "/api/health":
                self.send_json({"ok": True, "database": str(DB_PATH), "exists": DB_PATH.exists()})
                return
            if not DB_PATH.exists():
                self.send_json({"error": "database not found; run `python3 scripts/ingest.py seed --reset` first"}, 404)
                return
            with connect() as con:
                if path == "/api/summary":
                    self.send_json(summary(con))
                    return
                if path == "/api/feed":
                    limit = int((query.get("limit") or ["80"])[0])
                    self.send_json(feed(con, limit))
                    return
                if path.startswith("/api/symbol/"):
                    symbol = unquote(path.rsplit("/", 1)[-1]).upper()
                    self.send_json(symbol_detail(con, symbol))
                    return
            self.send_json({"error": "unknown endpoint"}, 404)
        except Exception as exc:
            self.send_json({"error": str(exc)}, 500)

    def send_json(self, payload: dict, status: int = 200) -> None:
        body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        self.send_response(status)
        self.send_header("content-type", "application/json; charset=utf-8")
        self.send_header("cache-control", "no-store")
        self.send_header("content-length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)


def main() -> None:
    parser = argparse.ArgumentParser(description="Serve the Serenity clone dashboard.")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8787)
    args = parser.parse_args()

    server = ThreadingHTTPServer((args.host, args.port), Handler)
    print(f"dashboard: http://{args.host}:{args.port}")
    server.serve_forever()


if __name__ == "__main__":
    main()
