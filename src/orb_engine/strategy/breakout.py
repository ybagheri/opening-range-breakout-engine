"""Breakout detection — pure, broker-independent, testable."""
from __future__ import annotations

from orb_engine.core.types import Bar, OpeningRange, SignalType, TradeSignal


class BreakoutDetector:
    def __init__(self, buffer_points: float = 0.0, buffer_pct_of_or: float = 0.0,
                 require_close: bool = False):
        self.buffer_points = buffer_points
        self.buffer_pct_of_or = buffer_pct_of_or
        self.require_close = require_close

    def buffer(self, orng: OpeningRange) -> float:
        return self.buffer_points + (self.buffer_pct_of_or / 100.0) * orng.width

    def detect(self, bar: Bar, orng: OpeningRange, session_date: str) -> TradeSignal:
        buf = self.buffer(orng)
        up = orng.high + buf
        dn = orng.low - buf
        if self.require_close:
            long_hit = bar.close > up
            short_hit = bar.close < dn
        else:
            long_hit = bar.high > up
            short_hit = bar.low < dn
        # If both sides touched on same bar -> ambiguous, NO_SIGNAL (conservative)
        if long_hit and short_hit:
            return TradeSignal(bar.symbol, session_date, SignalType.NO_SIGNAL, bar.timestamp,
                               bar.close, orng.high, orng.low, "ambiguous: both sides touched")
        if long_hit:
            px = bar.close if self.require_close else max(bar.close, up)
            return TradeSignal(bar.symbol, session_date, SignalType.LONG, bar.timestamp,
                               float(px), orng.high, orng.low, "long breakout")
        if short_hit:
            px = bar.close if self.require_close else min(bar.close, dn)
            return TradeSignal(bar.symbol, session_date, SignalType.SHORT, bar.timestamp,
                               float(px), orng.high, orng.low, "short breakout")
        return TradeSignal(bar.symbol, session_date, SignalType.NO_SIGNAL, bar.timestamp,
                           bar.close, orng.high, orng.low, "no breakout")
