"""Take-profit calculation."""
from __future__ import annotations

from orb_engine.core.types import Direction


class TakeProfitCalculator:
    def __init__(self, mode: str = "risk_reward", value: float = 2.0, risk_reward: float = 2.0):
        self.mode = mode
        self.value = value
        self.risk_reward = risk_reward

    def compute(self, direction: Direction, entry: float, stop: float,
                or_high: float = 0.0, or_low: float = 0.0, point: float = 0.01) -> float:
        risk = abs(entry - stop)
        if risk <= 0:
            raise ValueError("stop distance must be positive")
        if direction == Direction.LONG:
            if self.mode == "risk_reward":
                return entry + self.risk_reward * risk
            if self.mode == "or_width_multiple":
                return entry + self.value * (or_high - or_low)
            if self.mode == "fixed_points":
                return entry + self.value * point
        else:
            if self.mode == "risk_reward":
                return entry - self.risk_reward * risk
            if self.mode == "or_width_multiple":
                return entry - self.value * (or_high - or_low)
            if self.mode == "fixed_points":
                return entry - self.value * point
        raise ValueError(f"unknown tp mode {self.mode}")
