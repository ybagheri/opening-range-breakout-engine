"""Robust timezone-aware time handling.

Conventions:
- Market time: the exchange/session timezone given by TIMEZONE (e.g. America/New_York).
- Broker time: MT5 server time (queried from terminal; may differ from market time).
- UTC: internal canonical representation for persistence/comparison.
- Local computer time: only for display; never for trading decisions.
All trading datetimes must be timezone-aware. Naive datetimes are rejected.
"""
from __future__ import annotations

from datetime import datetime, timezone
from datetime import time as dtime
from zoneinfo import ZoneInfo


def get_zone(tz_name: str) -> ZoneInfo:
    return ZoneInfo(tz_name)


def now_utc() -> datetime:
    return datetime.now(timezone.utc)


def ensure_aware(dt: datetime, tz_name: str = "UTC") -> datetime:
    if dt.tzinfo is not None:
        return dt
    return dt.replace(tzinfo=get_zone(tz_name))


def to_utc(dt: datetime) -> datetime:
    if dt.tzinfo is None:
        raise ValueError("naive datetime cannot be converted; pass tz-aware datetime")
    return dt.astimezone(timezone.utc)


def to_market_time(dt: datetime, tz_name: str) -> datetime:
    if dt.tzinfo is None:
        raise ValueError("naive datetime cannot be converted; pass tz-aware datetime")
    return dt.astimezone(get_zone(tz_name))


def parse_hhmm(s: str) -> dtime:
    h, m = s.strip().split(":")
    return dtime(hour=int(h), minute=int(m))


def session_date_str(dt_market: datetime) -> str:
    return dt_market.strftime("%Y-%m-%d")


def combine_market_time(date_str: str, hhmm: str, tz_name: str) -> datetime:
    """Build tz-aware market-time datetime from session date + HH:MM."""
    t = parse_hhmm(hhmm)
    naive = datetime.strptime(  # noqa: DTZ007 - tz attached on next line
        f"{date_str} {t.hour:02d}:{t.minute:02d}", "%Y-%m-%d %H:%M")
    return naive.replace(tzinfo=get_zone(tz_name))


def is_dst(dt: datetime) -> bool:
    """Whether DST is in effect for dt's timezone (best-effort)."""
    if dt.tzinfo is None:
        return False
    dst, jan_dst, jul_dst = dt.dst(), dt.replace(month=1, day=1).dst(), dt.replace(month=7, day=1).dst()
    if dst is None:
        return False
    try:
        base = min(d for d in (jan_dst, jul_dst) if d is not None)
        return bool(dst and dst != base or dst)
    except (TypeError, ValueError):
        return False
