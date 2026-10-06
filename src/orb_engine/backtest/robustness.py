"""Robustness suite: slippage sweep, drop-best/worst, long/short split, param sensitivity."""
from __future__ import annotations

import copy


def slippage_sensitivity(run_fn, base_settings, multipliers=(1, 2, 3)) -> dict:
    out = {}
    for m in multipliers:
        s = copy.copy(base_settings)
        s.backtest_slippage_points = base_settings.backtest_slippage_points * m
        out[f"slip_{m}x"] = run_fn(s)
    return out


def drop_extremes(trades: list[dict], k: int = 5) -> dict:
    if not trades:
        return {"drop_best5_R": 0.0, "drop_worst5_R": 0.0, "base_R": 0.0}
    rs = sorted([t["r_multiple"] for t in trades])
    base = sum(rs)
    return {"base_R": base, "drop_best5_R": base - sum(rs[-k:]), "drop_worst5_R": base - sum(rs[:k])}


def long_short_split(trades: list[dict]) -> dict:
    l = [t["r_multiple"] for t in trades if t["direction"] == "LONG"]
    s = [t["r_multiple"] for t in trades if t["direction"] == "SHORT"]
    return {"long_trades": len(l), "long_R": sum(l), "short_trades": len(s), "short_R": sum(s)}
