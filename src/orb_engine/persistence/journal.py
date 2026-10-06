"""Persistent trade journal (SQLite) for post-trade statistics."""
from __future__ import annotations

import sqlite3
from pathlib import Path

COLS = ["trade_id","symbol","direction","session_date","or_high","or_low","signal_time",
"entry_time","entry_price","stop_price","target_price","volume","risk_pct","risk_amount",
"exit_time","exit_price","exit_reason","gross_pnl","commission","swap","net_pnl","r_multiple",
"breakeven_used","config_hash","extra"]


class TradeJournal:
    def __init__(self, path: str):
        Path(path).parent.mkdir(parents=True, exist_ok=True)
        self.path = path
        with sqlite3.connect(path) as c:
            c.execute("""CREATE TABLE IF NOT EXISTS trades(
              trade_id TEXT PRIMARY KEY, symbol TEXT, direction TEXT, session_date TEXT,
              or_high REAL, or_low REAL, signal_time TEXT, entry_time TEXT,
              entry_price REAL, stop_price REAL, target_price REAL, volume REAL,
              risk_pct REAL, risk_amount REAL, exit_time TEXT, exit_price REAL,
              exit_reason TEXT, gross_pnl REAL, commission REAL, swap REAL,
              net_pnl REAL, r_multiple REAL, breakeven_used INTEGER, config_hash TEXT, extra TEXT)""")

    def record(self, t: dict) -> None:
        row = {k: t.get(k) for k in COLS}
        import json as j
        if isinstance(row["extra"], dict):
            row["extra"] = j.dumps(row["extra"])
        row["breakeven_used"] = int(bool(row["breakeven_used"]))
        with sqlite3.connect(self.path) as c:
            c.execute(f"INSERT OR REPLACE INTO trades({','.join(COLS)}) VALUES({','.join('?'*len(COLS))})",
                      [row[k] for k in COLS])

    def all(self) -> list[dict]:
        with sqlite3.connect(self.path) as c:
            c.row_factory = sqlite3.Row
            return [dict(r) for r in c.execute("SELECT * FROM trades ORDER BY exit_time")]
