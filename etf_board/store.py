"""本地 SQLite：日线缓存 + 行情快照。AKShare 不是库，这才是库。"""

from __future__ import annotations

import json
import sqlite3
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parent.parent
DEFAULT_DB = ROOT / "data" / "etf_board.db"
WATCHLIST_PATH = ROOT / "watchlist.json"


def connect(db_path: Path | str | None = None) -> sqlite3.Connection:
    path = Path(db_path) if db_path else DEFAULT_DB
    path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(path), check_same_thread=False)
    conn.row_factory = sqlite3.Row
    init_schema(conn)
    return conn


def init_schema(conn: sqlite3.Connection) -> None:
    conn.executescript(
        """
        CREATE TABLE IF NOT EXISTS etf_daily (
            code TEXT NOT NULL,
            trade_date TEXT NOT NULL,
            open REAL,
            high REAL,
            low REAL,
            close REAL,
            volume REAL,
            amount REAL,
            adjust TEXT NOT NULL DEFAULT 'qfq',
            PRIMARY KEY (code, trade_date, adjust)
        );
        CREATE TABLE IF NOT EXISTS etf_spot (
            code TEXT PRIMARY KEY,
            name TEXT,
            last_price REAL,
            change_pct REAL,
            iopv REAL,
            premium_raw REAL,
            amount REAL,
            volume REAL,
            high REAL,
            low REAL,
            trade_date TEXT,
            update_time TEXT,
            fetched_at TEXT
        );
        CREATE INDEX IF NOT EXISTS idx_etf_daily_code_date
            ON etf_daily (code, trade_date);
        """
    )
    conn.commit()


def upsert_daily(conn: sqlite3.Connection, code: str, hist: pd.DataFrame, adjust: str = "qfq") -> int:
    if hist is None or hist.empty:
        return 0
    work = hist.copy()
    rename = {
        "日期": "trade_date",
        "开盘": "open",
        "最高": "high",
        "最低": "low",
        "收盘": "close",
        "成交量": "volume",
        "成交额": "amount",
    }
    work = work.rename(columns=rename)
    if "trade_date" not in work.columns:
        return 0
    work["trade_date"] = pd.to_datetime(work["trade_date"], errors="coerce").dt.strftime("%Y-%m-%d")
    work = work.dropna(subset=["trade_date", "close"])
    rows = []
    for rec in work.to_dict("records"):
        rows.append(
            (
                code,
                rec["trade_date"],
                _f(rec.get("open")),
                _f(rec.get("high")),
                _f(rec.get("low")),
                _f(rec.get("close")),
                _f(rec.get("volume")),
                _f(rec.get("amount")),
                adjust,
            )
        )
    conn.executemany(
        """
        INSERT INTO etf_daily (code, trade_date, open, high, low, close, volume, amount, adjust)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        ON CONFLICT(code, trade_date, adjust) DO UPDATE SET
            open=excluded.open,
            high=excluded.high,
            low=excluded.low,
            close=excluded.close,
            volume=excluded.volume,
            amount=excluded.amount
        """,
        rows,
    )
    conn.commit()
    return len(rows)


def load_daily(conn: sqlite3.Connection, code: str, adjust: str = "qfq", limit: int = 120) -> pd.DataFrame:
    df = pd.read_sql_query(
        """
        SELECT trade_date AS 日期, open AS 开盘, high AS 最高, low AS 最低,
               close AS 收盘, volume AS 成交量, amount AS 成交额
        FROM etf_daily
        WHERE code = ? AND adjust = ?
        ORDER BY trade_date
        """,
        conn,
        params=(code, adjust),
    )
    if df.empty:
        return df
    if limit and len(df) > limit:
        df = df.iloc[-limit:].reset_index(drop=True)
    return df


def last_daily_date(conn: sqlite3.Connection, code: str, adjust: str = "qfq") -> str | None:
    row = conn.execute(
        "SELECT MAX(trade_date) AS d FROM etf_daily WHERE code = ? AND adjust = ?",
        (code, adjust),
    ).fetchone()
    return row["d"] if row and row["d"] else None


def upsert_spot(conn: sqlite3.Connection, spot: pd.DataFrame) -> int:
    if spot is None or spot.empty:
        return 0
    now = pd.Timestamp.now(tz="Asia/Shanghai").strftime("%Y-%m-%d %H:%M:%S")
    rows = []
    for rec in spot.to_dict("records"):
        rows.append(
            (
                str(rec.get("代码", "")).zfill(6),
                rec.get("名称"),
                _f(rec.get("最新价")),
                _f(rec.get("涨跌幅")),
                _f(rec.get("IOPV实时估值")),
                _f(rec.get("基金折价率")),
                _f(rec.get("成交额")),
                _f(rec.get("成交量")),
                _f(rec.get("最高价")),
                _f(rec.get("最低价")),
                str(rec.get("数据日期") or ""),
                str(rec.get("更新时间") or ""),
                now,
            )
        )
    conn.executemany(
        """
        INSERT INTO etf_spot (
            code, name, last_price, change_pct, iopv, premium_raw,
            amount, volume, high, low, trade_date, update_time, fetched_at
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ON CONFLICT(code) DO UPDATE SET
            name=excluded.name,
            last_price=excluded.last_price,
            change_pct=excluded.change_pct,
            iopv=excluded.iopv,
            premium_raw=excluded.premium_raw,
            amount=excluded.amount,
            volume=excluded.volume,
            high=excluded.high,
            low=excluded.low,
            trade_date=excluded.trade_date,
            update_time=excluded.update_time,
            fetched_at=excluded.fetched_at
        """,
        rows,
    )
    conn.commit()
    return len(rows)


def spot_age_seconds(conn: sqlite3.Connection) -> float | None:
    row = conn.execute("SELECT MAX(fetched_at) AS t FROM etf_spot").fetchone()
    if not row or not row["t"]:
        return None
    ts = pd.Timestamp(row["t"])
    if ts.tzinfo is None:
        ts = ts.tz_localize("Asia/Shanghai")
    now = pd.Timestamp.now(tz="Asia/Shanghai")
    return float((now - ts).total_seconds())


def load_spot(conn: sqlite3.Connection, codes: list[str] | None = None) -> pd.DataFrame:
    if codes:
        placeholders = ",".join("?" * len(codes))
        df = pd.read_sql_query(
            f"SELECT * FROM etf_spot WHERE code IN ({placeholders})",
            conn,
            params=tuple(codes),
        )
    else:
        df = pd.read_sql_query("SELECT * FROM etf_spot", conn)
    return df


def load_watchlist(path: Path | str | None = None) -> dict:
    p = Path(path) if path else WATCHLIST_PATH
    if not p.exists():
        return {
            "etfs": [],
            "return_days": 19,
            "bias_days": 20,
            "target_bias_pct": [10, 15],
            "adjust": "qfq",
            "refresh_seconds": 15,
        }
    return json.loads(p.read_text(encoding="utf-8"))


def save_watchlist(data: dict, path: Path | str | None = None) -> None:
    p = Path(path) if path else WATCHLIST_PATH
    p.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")


def _f(value) -> float | None:
    if value is None or value == "":
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None
