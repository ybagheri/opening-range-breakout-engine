"""Break-even manager: move SL to entry (+buffer) once +trigger_R reached."""
from __future__ import annotations

from orb_engine.core.types import Direction


class BreakEvenManager:
    def __init__(self, enabled: bool = True, trigger_r: float = 1.0, buffer_points: float = 0.0):
        self.enabled = enabled
        self.trigger_r = trigger_r
        self.buffer_points = buffer_points

    def should_trigger(self, direction: Direction, entry: float, current: float,
                       stop: float) -> bool:
        if not self.enabled:
            return False
        risk = abs(entry - stop)
        if risk <= 0:
            return False
        if direction == Direction.LONG:
            return (current - entry) >= self.trigger_r * risk
        return (entry - current) >= self.trigger_r * risk

    def new_stop(self, direction: Direction, entry: float, point: float) -> float:
        buf = self.buffer_points * point
        return entry + buf if direction == Direction.LONG else entry - buf
