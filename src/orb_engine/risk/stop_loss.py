"""Stop-loss calculation — isolated from signal generation."""
from __future__ import annotations

from orb_engine.core.types import Direction


class StopLossCalculator:
    def __init__(self, mode: str = "opposite", value: float = 1.0):
        self.mode = mode
        self.value = value

    def compute(self, direction: Direction, entry: float, or_high: float, or_low: float,
                point: float = 0.01, atr: float | None = None) -> float:
        or_width = or_high - or_low
        if direction == Direction.LONG:
            if self.mode == "opposite":
                return or_low
            if self.mode == "or_width_multiple":
                return entry - self.value * or_width
            if self.mode == "fixed_points":
                return entry - self.value * point
            if self.mode == "percent":
                return entry * (1 - self.value / 100.0)
            if self.mode == "atr":
                if atr is None or atr <= 0:
                    raise ValueError("ATR stop requires positive atr")
                return entry - self.value * atr
        else:
            if self.mode == "opposite":
                return or_high
            if self.mode == "or_width_multiple":
                return entry + self.value * or_width
            if self.mode == "fixed_points":
                return entry + self.value * point
            if self.mode == "percent":
                return entry * (1 + self.value / 100.0)
            if self.mode == "atr":
                if atr is None or atr <= 0:
                    raise ValueError("ATR stop requires positive atr")
                return entry + self.value * atr
        raise ValueError(f"unknown stop mode {self.mode}")
