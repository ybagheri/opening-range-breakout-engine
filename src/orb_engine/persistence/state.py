"""SQLite state store for restart/recovery + idempotency."""
from __future__ import annotations

import sqlite3
from pathlib import Path


class StateStore:
    def __init__(self, path: str):
        Path(path).parent.mkdir(parents=True, exist_ok=True)
        self.path = path
        self._init()

    def _con(self) -> sqlite3.Connection:
        return sqlite3.connect(self.path)

    def _init(self) -> None:
        with self._con() as c:
            c.execute("""CREATE TABLE IF NOT EXISTS day_state(
              symbol TEXT, session_date TEXT, or_high REAL, or_low REAL,
              signal TEXT, traded INTEGER DEFAULT 0, ticket INTEGER,
              breakeven_done INTEGER DEFAULT 0, updated_utc TEXT,
              PRIMARY KEY(symbol, session_date))""")

    def upsert_or(self, symbol: str, date: str, hi: float, lo: float) -> None:
        import datetime as dt
        with self._con() as c:
            c.execute("""INSERT INTO day_state(symbol,session_date,or_high,or_low,updated_utc)
              VALUES(?,?,?,?,?) ON CONFLICT(symbol,session_date) DO UPDATE SET
              or_high=excluded.or_high, or_low=excluded.or_low, updated_utc=excluded.updated_utc""",
              (symbol, date, hi, lo, dt.datetime.now(dt.timezone.utc).isoformat()))

    def mark_traded(self, symbol: str, date: str, ticket: int | None, signal: str = "") -> None:
        with self._con() as c:
            c.execute("""INSERT INTO day_state(symbol,session_date,traded,ticket,signal)
              VALUES(?,?,1,?,?) ON CONFLICT(symbol,session_date) DO UPDATE SET
              traded=1, ticket=excluded.ticket, signal=excluded.signal""",
              (symbol, date, ticket, signal))

    def already_traded(self, symbol: str, date: str, max_trades: int = 1) -> bool:
        with self._con() as c:
            row = c.execute("SELECT traded FROM day_state WHERE symbol=? AND session_date=?",
                            (symbol, date)).fetchone()
        return bool(row and row[0] >= max_trades)

    def get(self, symbol: str, date: str) -> dict | None:
        with self._con() as c:
            c.row_factory = sqlite3.Row
            row = c.execute("SELECT * FROM day_state WHERE symbol=? AND session_date=?",
                            (symbol, date)).fetchone()
        return dict(row) if row else None
