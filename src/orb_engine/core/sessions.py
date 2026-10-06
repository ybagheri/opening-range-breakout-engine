"""Session / trading-window management. All datetimes tz-aware (market tz)."""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

from orb_engine.utils.time_utils import combine_market_time, get_zone, session_date_str


@dataclass(frozen=True)
class SessionConfig:
    timezone: str
    or_start: str
    or_end: str
    trading_start: str
    trading_end: str
    force_close_time: str = ""
    allow_overnight: bool = False


class SessionManager:
    def __init__(self, cfg: SessionConfig):
        self.cfg = cfg
        self._zone = get_zone(cfg.timezone)

    def market_now(self, dt: datetime) -> datetime:
        if dt.tzinfo is None:
            raise ValueError("naive datetime not allowed")
        return dt.astimezone(self._zone)

    def session_date(self, dt: datetime) -> str:
        return session_date_str(self.market_now(dt))

    def _at(self, date_str: str, hhmm: str) -> datetime:
        return combine_market_time(date_str, hhmm, self.cfg.timezone)

    def in_or_window(self, dt: datetime) -> bool:
        m = self.market_now(dt)
        d = session_date_str(m)
        return self._at(d, self.cfg.or_start) <= m < self._at(d, self.cfg.or_end)

    def or_complete(self, dt: datetime) -> bool:
        m = self.market_now(dt)
        return m >= self._at(session_date_str(m), self.cfg.or_end)

    def in_entry_window(self, dt: datetime) -> bool:
        m = self.market_now(dt)
        d = session_date_str(m)
        return self._at(d, self.cfg.trading_start) <= m <= self._at(d, self.cfg.trading_end)

    def force_close_due(self, dt: datetime) -> bool:
        if not self.cfg.force_close_time:
            return False
        m = self.market_now(dt)
        return m >= self._at(session_date_str(m), self.cfg.force_close_time)
