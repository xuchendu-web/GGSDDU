#!/usr/bin/env python3
"""Build a local Serenity-style signal database.

The script is intentionally dependency-free. It can seed demo data, import raw
X/Twitter GraphQL JSON exports, and fetch daily Yahoo Finance candles.
"""

from __future__ import annotations

import argparse
import datetime as dt
import html
import json
import math
import re
import sqlite3
import sys
import urllib.parse
import urllib.request
from pathlib import Path
from typing import Any, Iterable


ROOT = Path(__file__).resolve().parents[1]
DB_PATH = ROOT / "data" / "serenity.sqlite"
RAW_DIR = ROOT / "data" / "raw"
TARGET_HANDLE = "ShanghaoJin"
CASHTAG_RE = re.compile(r"(?<![A-Za-z0-9_])\$([A-Z][A-Z0-9.]{0,9})(?![A-Za-z0-9_])")
NOISE_SYMBOLS = {"A", "I", "AI", "CEO", "ETF", "IPO", "USD", "US"}


def utc_now() -> str:
    return dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z")


def clean_handle(value: str | None) -> str:
    return str(value or "").strip().lstrip("@")


def handle_key(value: str | None) -> str:
    return clean_handle(value).lower()


def connect(reset: bool = False) -> sqlite3.Connection:
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    if reset and DB_PATH.exists():
        DB_PATH.unlink()

    con = sqlite3.connect(DB_PATH)
    con.row_factory = sqlite3.Row
    con.executescript(
        """
        pragma journal_mode = wal;

        create table if not exists tweets (
            tweet_id text primary key,
            source text not null,
            author text,
            created_at text not null,
            text text not null,
            url text,
            favorite_count integer default 0,
            reply_count integer default 0,
            retweet_count integer default 0,
            raw_json text not null
        );

        create table if not exists mentions (
            id integer primary key autoincrement,
            symbol text not null,
            tweet_id text not null references tweets(tweet_id) on delete cascade,
            mentioned_at text not null,
            text text not null,
            source text not null,
            unique(symbol, tweet_id)
        );

        create table if not exists prices (
            symbol text not null,
            date text not null,
            close real not null,
            volume integer default 0,
            primary key(symbol, date)
        );

        create table if not exists raw_imports (
            id integer primary key autoincrement,
            source text not null,
            file_path text,
            imported_at text not null,
            tweet_count integer not null,
            raw_json text
        );

        create index if not exists idx_mentions_symbol_time on mentions(symbol, mentioned_at);
        create index if not exists idx_prices_symbol_date on prices(symbol, date);
        """
    )
    return con


def walk_json(value: Any) -> Iterable[dict[str, Any]]:
    if isinstance(value, dict):
        yield value
        for child in value.values():
            yield from walk_json(child)
    elif isinstance(value, list):
        for child in value:
            yield from walk_json(child)


def parse_x_date(value: str | None) -> str | None:
    if not value:
        return None
    formats = ("%a %b %d %H:%M:%S %z %Y", "%Y-%m-%dT%H:%M:%S.%fZ", "%Y-%m-%dT%H:%M:%SZ")
    for fmt in formats:
        try:
            parsed = dt.datetime.strptime(value, fmt)
            if parsed.tzinfo is None:
                parsed = parsed.replace(tzinfo=dt.timezone.utc)
            return parsed.astimezone(dt.timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z")
        except ValueError:
            continue
    return None


def extract_symbols(text: str, *entity_sets: dict[str, Any]) -> list[str]:
    found = {match.group(1).upper().rstrip(".") for match in CASHTAG_RE.finditer(text or "")}
    for entities in entity_sets:
        for item in entities.get("symbols") or []:
            symbol = item.get("text") or item.get("ticker")
            if symbol:
                found.add(str(symbol).upper().strip().rstrip("."))
    return sorted(s for s in found if 1 < len(s) <= 10 and s not in NOISE_SYMBOLS)


def extract_screen_name(node: dict[str, Any], legacy: dict[str, Any]) -> str:
    user_result = (((node.get("core") or {}).get("user_results") or {}).get("result") or {})
    author_obj = node.get("author") if isinstance(node.get("author"), dict) else {}
    candidates = [
        ((user_result.get("core") or {}).get("screen_name")),
        ((user_result.get("legacy") or {}).get("screen_name")),
        legacy.get("screen_name"),
        legacy.get("user_screen_name"),
        author_obj.get("screen_name"),
        author_obj.get("username"),
        node.get("author") if isinstance(node.get("author"), str) else None,
        ((node.get("user") or {}).get("screen_name") if isinstance(node.get("user"), dict) else None),
    ]
    for candidate in candidates:
        handle = clean_handle(candidate)
        if handle:
            return handle
    return "unknown"


def normalize_tweet(node: dict[str, Any], default_source: str, target_handle: str | None = TARGET_HANDLE) -> dict[str, Any] | None:
    legacy = node.get("legacy") if isinstance(node.get("legacy"), dict) else node
    tweet_id = str(legacy.get("id_str") or node.get("rest_id") or legacy.get("id") or "").strip()
    text = html.unescape(str(legacy.get("full_text") or legacy.get("text") or node.get("text") or "").strip())
    created_at = parse_x_date(legacy.get("created_at") or node.get("created_at"))

    if not tweet_id or not text or not created_at:
        return None

    screen_name = extract_screen_name(node, legacy)
    if target_handle and handle_key(screen_name) != handle_key(target_handle):
        return None

    note = (((node.get("note_tweet") or {}).get("note_tweet_results") or {}).get("result") or {})
    note_text = html.unescape(str(note.get("text") or "").strip())
    full_text = note_text or text
    symbols = extract_symbols(full_text, legacy.get("entities") or {}, note.get("entity_set") or {})

    return {
        "tweet_id": tweet_id,
        "source": default_source,
        "author": screen_name,
        "created_at": created_at,
        "text": full_text,
        "url": legacy.get("url") or f"https://x.com/{screen_name}/status/{tweet_id}",
        "favorite_count": int(legacy.get("favorite_count") or 0),
        "reply_count": int(legacy.get("reply_count") or 0),
        "retweet_count": int(legacy.get("retweet_count") or 0),
        "symbols": symbols,
        "raw_json": json.dumps(node, ensure_ascii=False, separators=(",", ":")),
    }


def upsert_tweet(con: sqlite3.Connection, tweet: dict[str, Any]) -> None:
    con.execute(
        """
        insert into tweets(tweet_id, source, author, created_at, text, url, favorite_count, reply_count, retweet_count, raw_json)
        values(:tweet_id, :source, :author, :created_at, :text, :url, :favorite_count, :reply_count, :retweet_count, :raw_json)
        on conflict(tweet_id) do update set
            source=excluded.source,
            author=excluded.author,
            created_at=excluded.created_at,
            text=excluded.text,
            url=excluded.url,
            favorite_count=excluded.favorite_count,
            reply_count=excluded.reply_count,
            retweet_count=excluded.retweet_count,
            raw_json=excluded.raw_json
        """,
        tweet,
    )
    con.execute("delete from mentions where tweet_id = ?", (tweet["tweet_id"],))
    for symbol in tweet["symbols"]:
        con.execute(
            "insert into mentions(symbol, tweet_id, mentioned_at, text, source) values(?, ?, ?, ?, ?)",
            (symbol, tweet["tweet_id"], tweet["created_at"], tweet["text"], tweet["source"]),
        )


def import_json_file(con: sqlite3.Connection, path: Path, source: str, target_handle: str | None) -> int:
    payload = json.loads(path.read_text(encoding="utf-8"))
    tweets: dict[str, dict[str, Any]] = {}
    for node in walk_json(payload):
        tweet = normalize_tweet(node, source, target_handle)
        if tweet and tweet["symbols"]:
            tweets[tweet["tweet_id"]] = tweet

    for tweet in tweets.values():
        upsert_tweet(con, tweet)

    con.execute(
        "insert into raw_imports(source, file_path, imported_at, tweet_count, raw_json) values(?, ?, ?, ?, ?)",
        (source, str(path), utc_now(), len(tweets), json.dumps(payload, ensure_ascii=False)[:500000]),
    )
    con.commit()
    return len(tweets)


def import_json_dir(source: str, path: Path, target_handle: str | None) -> None:
    con = connect()
    files = sorted(path.glob("*.json")) if path.is_dir() else [path]
    total = 0
    for file_path in files:
        count = import_json_file(con, file_path, source, target_handle)
        print(f"imported {count:>3} tweets from {file_path}")
        total += count
    target = f" @{clean_handle(target_handle)}" if target_handle else ""
    print(f"done: {total}{target} tweets with cashtags stored in {DB_PATH}")


def yahoo_chart(symbol: str, start: dt.datetime, end: dt.datetime) -> dict[str, Any]:
    url = "https://query1.finance.yahoo.com/v8/finance/chart/{symbol}?{query}".format(
        symbol=urllib.parse.quote(symbol),
        query=urllib.parse.urlencode(
            {
                "period1": int(start.timestamp()),
                "period2": int(end.timestamp()),
                "interval": "1d",
                "events": "history",
            }
        ),
    )
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0 SerenityClone/1.0"})
    with urllib.request.urlopen(req, timeout=20) as resp:
        return json.loads(resp.read().decode("utf-8"))


def fetch_prices(days: int, min_mentions: int) -> None:
    con = connect()
    symbols = [
        row["symbol"]
        for row in con.execute(
            """
            select symbol from mentions
            group by symbol
            having count(*) >= ?
            order by count(*) desc, symbol
            """,
            (min_mentions,),
        )
    ]
    if not symbols:
        print("no symbols found; run seed or import-json first")
        return

    end = dt.datetime.now(dt.timezone.utc) + dt.timedelta(days=1)
    start = end - dt.timedelta(days=days)
    for symbol in symbols:
        try:
            data = yahoo_chart(symbol, start, end)
            result = ((data.get("chart") or {}).get("result") or [None])[0]
            if not result:
                print(f"{symbol}: no Yahoo result")
                continue
            timestamps = result.get("timestamp") or []
            quote = ((result.get("indicators") or {}).get("quote") or [{}])[0]
            closes = quote.get("close") or []
            volumes = quote.get("volume") or []
            inserted = 0
            for ts, close, volume in zip(timestamps, closes, volumes):
                if close is None:
                    continue
                day = dt.datetime.fromtimestamp(ts, dt.timezone.utc).date().isoformat()
                con.execute(
                    "insert or replace into prices(symbol, date, close, volume) values(?, ?, ?, ?)",
                    (symbol, day, float(close), int(volume or 0)),
                )
                inserted += 1
            con.commit()
            print(f"{symbol}: {inserted} bars")
        except Exception as exc:
            print(f"{symbol}: price fetch failed: {exc}", file=sys.stderr)


def synthetic_price(symbol_index: int, day_index: int, base: float) -> tuple[float, int]:
    wave = math.sin(day_index / 5 + symbol_index) * 2.8
    trend = day_index * (0.18 + symbol_index * 0.025)
    pullback = -4.5 if day_index in {11, 12, 26} else 0
    close = round(base + trend + wave + pullback, 2)
    volume = int(18_000_000 + symbol_index * 3_100_000 + day_index * 210_000)
    return close, volume


def seed(reset: bool, target_handle: str = TARGET_HANDLE) -> None:
    con = connect(reset=reset)
    base_time = dt.datetime.now(dt.timezone.utc).replace(hour=13, minute=30, second=0, microsecond=0)
    author = clean_handle(target_handle) or TARGET_HANDLE
    samples = [
        ("NVDA", "Tracking @ShanghaoJin demo: AI capex keeps rotating back into $NVDA; watch data-center backlog quality.", 0, 890.0),
        ("TSM", "@ShanghaoJin demo note: $TSM is the quiet toll road in this cycle; utilization matters.", 3, 142.0),
        ("AMD", "If inference demand broadens, $AMD gets a cleaner second look. I want proof in gross margin first.", 5, 158.0),
        ("ASML", "$ASML remains the scarcity asset for leading-edge supply chains, but order timing matters.", 8, 960.0),
        ("SMCI", "$SMCI is high beta infrastructure exposure. Great upside tape, unforgiving downside tape.", 13, 790.0),
        ("NVDA", "Second @ShanghaoJin-style mention: $NVDA pullbacks only work if hyperscaler budgets hold.", 18, 890.0),
        ("TSM", "$TSM and $ASML are still the cleaner picks-and-shovels read on semi confidence.", 22, 142.0),
        ("AMD", "Keeping $AMD on the watchlist for accelerator share gains, not treating it as confirmed yet.", 29, 158.0),
    ]

    for idx, (primary_symbol, text, offset, _) in enumerate(samples, start=1):
        when = base_time - dt.timedelta(days=35 - offset)
        tweet = {
            "tweet_id": f"demo-{idx}",
            "source": "seed",
            "author": author,
            "created_at": when.isoformat(timespec="seconds").replace("+00:00", "Z"),
            "text": text,
            "url": f"https://x.com/{author}/status/demo-{idx}",
            "favorite_count": 100 + idx * 17,
            "reply_count": 8 + idx,
            "retweet_count": 12 + idx * 2,
            "symbols": extract_symbols(text) or [primary_symbol],
            "raw_json": json.dumps({"seed": True, "text": text}, ensure_ascii=False),
        }
        upsert_tweet(con, tweet)

    start_day = (base_time - dt.timedelta(days=42)).date()
    symbols = [("NVDA", 890.0), ("TSM", 142.0), ("AMD", 158.0), ("ASML", 960.0), ("SMCI", 790.0)]
    for symbol_index, (symbol, base) in enumerate(symbols):
        for day_index in range(43):
            date = (start_day + dt.timedelta(days=day_index)).isoformat()
            close, volume = synthetic_price(symbol_index, day_index, base)
            con.execute(
                "insert or replace into prices(symbol, date, close, volume) values(?, ?, ?, ?)",
                (symbol, date, close, volume),
            )
    con.commit()
    print(f"seeded demo database at {DB_PATH}")


def stats() -> None:
    con = connect()
    counters = con.execute(
        """
        select
          (select count(*) from tweets) tweets,
          (select count(*) from mentions) mentions,
          (select count(distinct symbol) from mentions) symbols,
          (select count(*) from prices) prices
        """
    ).fetchone()
    print(dict(counters))
    for row in con.execute(
        """
        select symbol, count(*) mentions, min(mentioned_at) first_mention, max(mentioned_at) latest_mention
        from mentions
        group by symbol
        order by mentions desc, latest_mention desc
        """
    ):
        print(dict(row))


def main() -> None:
    parser = argparse.ArgumentParser(description="Create and maintain a local Serenity-style signal database.")
    sub = parser.add_subparsers(dest="command", required=True)

    seed_parser = sub.add_parser("seed", help="create demo data that works without external accounts")
    seed_parser.add_argument("--reset", action="store_true", help="replace the existing SQLite database")
    seed_parser.add_argument("--target", default=TARGET_HANDLE, help="demo author handle; default: ShanghaoJin")

    import_parser = sub.add_parser("import-json", help="import X/Twitter GraphQL JSON files")
    import_parser.add_argument("--path", type=Path, default=RAW_DIR, help="JSON file or directory")
    import_parser.add_argument("--source", default="x-json", help="source label stored with mentions")
    import_parser.add_argument("--target", default=TARGET_HANDLE, help="only import tweets by this handle; default: ShanghaoJin")
    import_parser.add_argument("--include-all", action="store_true", help="disable author filtering")

    prices_parser = sub.add_parser("prices", help="download Yahoo daily closes for mentioned symbols")
    prices_parser.add_argument("--days", type=int, default=420)
    prices_parser.add_argument("--min-mentions", type=int, default=1)

    sub.add_parser("stats", help="print local database counts")
    args = parser.parse_args()

    if args.command == "seed":
        seed(reset=args.reset, target_handle=args.target)
    elif args.command == "import-json":
        import_json_dir(args.source, args.path, None if args.include_all else args.target)
    elif args.command == "prices":
        fetch_prices(args.days, args.min_mentions)
    elif args.command == "stats":
        stats()


if __name__ == "__main__":
    main()
