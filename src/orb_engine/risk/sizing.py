"""Fixed-fractional position sizing using real MT5 symbol specs. Never 1pt=$1."""
from __future__ import annotations

import math
from dataclasses import dataclass

from orb_engine.core.types import SymbolInfo


@dataclass
class SizeResult:
    volume: float
    risk_amount: float
    stop_distance_price: float
    loss_per_unit_volume: float
    capped_or_floored: str  # ok | below_min | above_max
    expected_max_loss: float


def normalize_volume(vol: float, info: SymbolInfo) -> tuple[float, str]:
    if info.volume_step <= 0:
        raise ValueError("volume_step must be positive")
    steps = math.floor(vol / info.volume_step + 1e-9)
    norm = round(steps * info.volume_step, 8)
    if norm < info.volume_min:
        return info.volume_min, "below_min"
    if norm > info.volume_max:
        return info.volume_max, "above_max"
    return norm, "ok"


def position_size(balance: float, risk_pct: float, entry: float, stop: float,
                  info: SymbolInfo) -> SizeResult:
    """Money at risk = balance * risk_pct/100. Loss per 1.0 volume for stop distance
    = (stop_distance / tick_size) * tick_value. volume = risk_amount / loss_per_unit."""
    if balance <= 0:
        raise ValueError("balance must be positive")
    if not (0 < risk_pct <= 100):
        raise ValueError("risk_pct must be in (0,100]")
    stop_dist = abs(entry - stop)
    if stop_dist <= 0:
        raise ValueError("stop distance must be positive")
    if info.tick_size <= 0 or info.tick_value <= 0:
        raise ValueError("tick_size/tick_value must be positive")
    risk_amount = balance * risk_pct / 100.0
    ticks_at_risk = stop_dist / info.tick_size
    loss_per_unit = ticks_at_risk * info.tick_value
    raw_vol = risk_amount / loss_per_unit
    norm, flag = normalize_volume(raw_vol, info)
    expected_loss = (norm * loss_per_unit)
    return SizeResult(norm, risk_amount, stop_dist, loss_per_unit, flag, expected_loss)
