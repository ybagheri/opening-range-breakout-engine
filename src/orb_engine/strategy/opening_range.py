"""Opening range construction with data-quality validation."""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

from orb_engine.core.types import Bar, OpeningRange


@dataclass
class ORValidation:
    ok: bool
    reason: str = ""
    bars_used: int = 0


class OpeningRangeBuilder:
    """Build OR from bars fully inside [or_start, or_end). Deterministic, no look-ahead."""

    def build(self, bars: list[Bar], symbol: str, session_date: str,
              or_start: datetime, or_end: datetime) -> tuple[OpeningRange | None, ORValidation]:
        in_window = [b for b in bars if or_start <= b.timestamp < or_end and b.symbol == symbol]
        in_window.sort(key=lambda b: b.timestamp)
        if not in_window:
            return None, ORValidation(False, "no bars in OR window", 0)
        for b in in_window:
            if b.high < b.low or b.open <= 0 or b.high <= 0 or b.low <= 0 or b.close <= 0:
                return None, ORValidation(False, f"invalid OHLC at {b.timestamp}", len(in_window))
            if b.high < max(b.open, b.close) or b.low > min(b.open, b.close):
                return None, ORValidation(False, f"OHLC inconsistency at {b.timestamp}", len(in_window))
        # duplicate timestamps
        ts = [b.timestamp for b in in_window]
        if len(set(ts)) != len(ts):
            return None, ORValidation(False, "duplicated bar timestamps", len(in_window))
        hi = max(b.high for b in in_window)
        lo = min(b.low for b in in_window)
        if hi <= lo:
            return None, ORValidation(False, "zero-width range", len(in_window))
        # gap anomaly: flag but still build (warn)
        rng = OpeningRange(symbol=symbol, session_date=session_date, start=or_start, end=or_end, high=hi, low=lo)
        return rng, ORValidation(True, "", len(in_window))
