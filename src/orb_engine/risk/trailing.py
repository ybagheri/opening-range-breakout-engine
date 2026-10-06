"""Trailing-stop management: lock in profit once a trade moves far enough.

Definition: after the favorable excursion from entry reaches `trigger_r` multiples
of the trade's initial risk, the stop ratchets to
    LONG:  extreme_high - offset_r * risk
    SHORT: extreme_low  + offset_r * risk
and thereafter only ever moves in the protective direction (ratchet).

It composes with breakeven: callers take the most protective of the BE level and
the trail level. Disabled entirely when `enabled` is False. All distances are in
R multiples of initial risk — never in points — so one setting works across
US30/US500/US100 without per-symbol tuning.
"""
from __future__ import annotations

from dataclasses import dataclass

from orb_engine.core.types import Direction


@dataclass(frozen=True)
class TrailingStop:
    enabled: bool = False
    trigger_r: float = 1.5
    offset_r: float = 0.5

    def candidate(self, direction: Direction, entry: float, extreme: float,
                  risk: float) -> float | None:
        """Trail level given the best favorable price seen so far, or None if the
        trigger has not been reached. `extreme` is the highest high (LONG) or
        lowest low (SHORT) observed since entry."""
        if not self.enabled or risk <= 0:
            return None
        if direction == Direction.LONG:
            if (extreme - entry) < self.trigger_r * risk:
                return None
            return extreme - self.offset_r * risk
        if (entry - extreme) < self.trigger_r * risk:
            return None
        return extreme + self.offset_r * risk

    @staticmethod
    def ratchet(direction: Direction, current_stop: float,
                levels: list[float | None]) -> float:
        """Most protective of (current, candidates); never moves backwards."""
        best = current_stop
        for lv in levels:
            if lv is None:
                continue
            if direction == Direction.LONG:
                best = max(best, lv)
            else:
                best = min(best, lv)
        return best
